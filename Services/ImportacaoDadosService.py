import os
import uuid
import json
import pandas as pd
from datetime import datetime
from werkzeug.utils import secure_filename
from sqlalchemy.orm import sessionmaker

# --- Imports Utilitários ---
from Utils.ExcelUtils import (
    analyze_excel_sample, 
    generate_preview_value, 
    process_and_save_dynamic, 
    delete_records_by_competencia,
    apply_transformations, 
    get_competencia_from_df 
)

# --- Import do Logger ---
from Utils.Logger import RegistrarLog 

# --- Imports de Banco de Dados ---
from Db.Connections import GetPostgresEngine
from Models.POSTGRESS.ImportHistory import ImportHistory
from Models.POSTGRESS.ImportConfig import ImportConfig

class ImportacaoDadosService:
    """
    Serviço responsável por gerenciar todo o fluxo de importação de dados,
    desde o upload do arquivo até a gravação no banco de dados.
    """
    
    # Constantes da Classe
    PASTA_TEMPORARIA = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Data', 'Temp'))
    
    TABELAS_PERMITIDAS = [
        'Razao_Dados_Origem_INTEC',
        'Razao_Dados_Origem_FARMADIST',
        'Razao_Dados_Origem_FARMA',
    ]

    def __init__(self):
        """Construtor da classe."""
        pass

    def _obter_sessao(self):
        """
        Método Privado: Cria e retorna uma sessão do PostgreSQL.
        """
        engine = GetPostgresEngine()
        Session = sessionmaker(bind=engine)
        return Session()

    def _garantir_pasta_temporaria(self):
        """
        Método Privado: Verifica se a pasta temporária existe, caso contrário cria.
        """
        if not os.path.exists(self.PASTA_TEMPORARIA):
            try:
                os.makedirs(self.PASTA_TEMPORARIA)
                RegistrarLog(f"Pasta temporária criada em {self.PASTA_TEMPORARIA}", "SYSTEM")
            except Exception as e:
                RegistrarLog("Erro ao criar pasta temporária", "ERROR", e)
                raise e

    def _verificar_importacao_existente(self, session, tabela_destino, competencia):
        """
        Método Privado: Verifica se já existe importação ativa para a competência.
        """
        existe = session.query(ImportHistory).filter_by(
            Tabela_Destino=tabela_destino,
            Competencia=competencia,
            Status='Ativo'
        ).first()
        return existe is not None

    def _salvar_configuracao_atual(self, session, origem, mapeamento, transformacoes):
        """
        Método Privado: Salva as configurações de mapeamento para uso futuro.
        """
        try:
            config = session.query(ImportConfig).filter_by(Source_Table=origem).first()
            if not config:
                config = ImportConfig(Source_Table=origem)
                session.add(config)
            
            config.set_mapping(mapeamento)
            config.set_transforms(transformacoes)
            RegistrarLog(f"Configuração atualizada para {origem}", "DATABASE")
        except Exception as e:
            RegistrarLog(f"Erro ao salvar configuração para {origem}", "ERROR", e)
            raise e

    def SalvarArquivoTemporario(self, arquivo_storage):
        """
        Recebe o objeto de arquivo do Flask, define um nome único e salva em disco.
        Retorna o caminho completo e o nome único gerado.
        """
        self._garantir_pasta_temporaria()
        nome_original = secure_filename(arquivo_storage.filename)
        nome_unico = f"{uuid.uuid4()}_{nome_original}"
        caminho_arquivo = os.path.join(self.PASTA_TEMPORARIA, nome_unico)
        
        try:
            arquivo_storage.save(caminho_arquivo)
            RegistrarLog(f"Arquivo temporário salvo: {nome_unico}", "FILE")
            return caminho_arquivo, nome_unico
        except Exception as e:
            RegistrarLog(f"Falha ao salvar arquivo temporário {nome_original}", "ERROR", e)
            raise e

    def ObterAmostraAnalise(self, nome_arquivo):
        """
        Analisa o arquivo Excel salvo e retorna suas colunas e uma amostra de dados.
        """
        caminho_arquivo = os.path.join(self.PASTA_TEMPORARIA, nome_arquivo)
        try:
            return analyze_excel_sample(caminho_arquivo)
        except Exception as e:
            RegistrarLog(f"Erro ao analisar amostra do arquivo {nome_arquivo}", "ERROR", e)
            raise e

    def CarregarUltimaConfiguracao(self, origem):
        """
        Recupera o último mapeamento e transformações salvos para a origem especificada.
        """
        session = self._obter_sessao()
        try:
            config = session.query(ImportConfig).filter_by(Source_Table=origem).first()
            if config:
                RegistrarLog(f"Configuração carregada para {origem}", "DATABASE")
                return config.get_mapping(), config.get_transforms()
            return {}, {}
        except Exception as e:
            RegistrarLog(f"Erro ao carregar configuração para {origem}", "ERROR", e)
            return {}, {}
        finally:
            session.close()

    def ObterPreviaTransformacao(self, nome_arquivo, mapeamento, transformacoes):
        """
        Gera uma prévia do valor transformado para exibição no frontend.
        """
        caminho_arquivo = os.path.join(self.PASTA_TEMPORARIA, nome_arquivo)
        if not os.path.exists(caminho_arquivo):
            RegistrarLog(f"Tentativa de preview em arquivo inexistente: {nome_arquivo}", "WARNING")
            return {"error": "Arquivo temporário expirou ou foi deletado."}
        
        try:
            return generate_preview_value(caminho_arquivo, mapeamento, transformacoes)
        except Exception as e:
            RegistrarLog(f"Erro ao gerar preview de transformação", "ERROR", e)
            raise e

    def ExecutarTransacaoImportacao(self, nome_arquivo, mapeamento, tabela_destino, nome_usuario, transformacoes=None):
        """
        Executa o processo principal de importação: validação, processamento e persistência.
        """
        RegistrarLog(f"Iniciando Transação de Importação: {nome_arquivo} -> {tabela_destino} ({nome_usuario})", "SERVICE")

        if tabela_destino not in self.TABELAS_PERMITIDAS:
            RegistrarLog(f"Tentativa de importação para tabela não permitida: {tabela_destino}", "SECURITY")
            raise Exception("Tabela de destino inválida ou não permitida.")

        caminho_arquivo = os.path.join(self.PASTA_TEMPORARIA, nome_arquivo)
        if not os.path.exists(caminho_arquivo):
            RegistrarLog(f"Arquivo temporário não encontrado: {nome_arquivo}", "ERROR")
            raise Exception("O arquivo temporário não foi encontrado. Por favor, faça o upload novamente.")

        engine = GetPostgresEngine()
        session = self._obter_sessao()

        try:
            # 1. Validação de Competência
            RegistrarLog("Iniciando validação de competência (Pré-leitura)", "DEBUG")
            df_check = pd.read_excel(caminho_arquivo, engine='openpyxl', nrows=500)
            df_check.columns = [str(c).replace('\n', ' ').strip() for c in df_check.columns]
            
            col_excel_data = next((k for k, v in mapeamento.items() if v == 'Data'), None)
            if not col_excel_data:
                raise Exception("Coluna obrigatória 'Data' não foi mapeada.")
                
            if transformacoes and col_excel_data in transformacoes:
                df_check = apply_transformations(df_check, {col_excel_data: transformacoes[col_excel_data]})
                
            competencia_prevista = get_competencia_from_df(df_check, col_excel_data)
            RegistrarLog(f"Competência detectada: {competencia_prevista}", "DEBUG")
            
            if self._verificar_importacao_existente(session, tabela_destino, competencia_prevista):
                msg = f"Já existe uma importação ATIVA para {tabela_destino} na competência {competencia_prevista}."
                RegistrarLog(msg, "WARNING")
                raise Exception(msg)
                
            # 2. Executa Carga Real
            RegistrarLog("Iniciando carga real e processamento dinâmico...", "INFO")
            linhas_inseridas, competencia_real = process_and_save_dynamic(
                caminho_arquivo, mapeamento, tabela_destino, engine, transformacoes
            )

            # 3. Grava Histórico
            novo_log = ImportHistory(
                Usuario=nome_usuario,
                Tabela_Destino=tabela_destino,
                Competencia=competencia_real,
                Nome_Arquivo=nome_arquivo.split('_', 1)[1],
                Status='Ativo'
            )
            session.add(novo_log)

            # 4. Salva Configuração
            self._salvar_configuracao_atual(session, tabela_destino, mapeamento, transformacoes)

            session.commit()
            RegistrarLog(f"Importação concluída com sucesso. Registros: {linhas_inseridas}. Comp: {competencia_real}", "SUCCESS")
            return linhas_inseridas, competencia_real

        except Exception as e:
            session.rollback()
            RegistrarLog(f"Falha na Transação de Importação. Rollback executado.", "ERROR", e)
            raise e
        finally:
            session.close()
            if os.path.exists(caminho_arquivo):
                os.remove(caminho_arquivo)
                RegistrarLog(f"Arquivo temporário limpo: {nome_arquivo}", "DEBUG")

    def ExecutarReversao(self, id_log, nome_usuario, motivo):
        """
        Executa o rollback (reversão) de uma importação realizada anteriormente.
        """
        RegistrarLog(f"Solicitação de Reversão ID {id_log} por {nome_usuario}. Motivo: {motivo}", "SERVICE")
        session = self._obter_sessao()
        engine = GetPostgresEngine()
        
        try:
            entrada_log = session.query(ImportHistory).get(id_log)
            
            if not entrada_log:
                raise Exception("Registro de histórico não encontrado.")
            
            if entrada_log.Status != 'Ativo':
                raise Exception("Esta importação já foi revertida anteriormente.")
                
            delta = datetime.now() - entrada_log.Data_Importacao
            if delta.days > 127:
                msg = f"Prazo para reversão expirado ({delta.days} dias). O limite é de 7 dias."
                RegistrarLog(msg, "WARNING")
                raise Exception(msg)

            RegistrarLog(f"Deletando registros da tabela {entrada_log.Tabela_Destino} Competência {entrada_log.Competencia}", "DB_ACTION")
            qtd_deletada = delete_records_by_competencia(engine, entrada_log.Tabela_Destino, entrada_log.Competencia)
            
            entrada_log.Status = 'Revertido'
            entrada_log.Data_Reversao = datetime.now()
            entrada_log.Usuario_Reversao = nome_usuario
            entrada_log.Motivo_Reversao = motivo
            
            session.commit()
            RegistrarLog(f"Reversão concluída com sucesso. {qtd_deletada} registros removidos.", "SUCCESS")
            return qtd_deletada, entrada_log.Tabela_Destino

        except Exception as e:
            session.rollback()
            RegistrarLog("Erro crítico ao executar Reversão", "ERROR", e)
            raise e
        finally:
            session.close()

    def ObterHistoricoImportacao(self):
        """
        Retorna o histórico completo de importações.
        """
        session = self._obter_sessao()
        try:
            return session.query(ImportHistory).order_by(ImportHistory.Data_Importacao.desc()).all()
        except Exception as e:
            RegistrarLog("Erro ao buscar histórico de importações", "ERROR", e)
            return []
        finally:
            session.close()