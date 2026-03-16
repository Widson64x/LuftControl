import os
import uuid
import json
import pandas as pd
from datetime import datetime
from werkzeug.utils import secure_filename
from sqlalchemy.orm import sessionmaker

from Utils.ExcelUtils import (
    analyze_excel_sample, generate_preview_value, process_and_save_dynamic, 
    delete_records_by_competencia, apply_transformations, get_competencia_from_df 
)
from Utils.Logger import RegistrarLog 
from Db.Connections import GetPostgresEngine

# --- NOVOS IMPORTS DE SISTEMA ---
from Models.Postgress.CTL_Sistema import CtlSysHistImportacao, CtlSysConfigImportacao

class ImportacaoDadosService:
    PASTA_TEMPORARIA = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', 'Data', 'Temp'))
    
    # ATUALIZADO: Usando os novos nomes das tabelas de Razão
    TABELAS_PERMITIDAS = [
        'Tb_CTL_Razao_Intec',
        'Tb_CTL_Razao_FarmaDist',
        'Tb_CTL_Razao_Farma',
    ]

    def __init__(self):
        pass

    def _obter_sessao(self):
        engine = GetPostgresEngine()
        return sessionmaker(bind=engine)()

    def _garantir_pasta_temporaria(self):
        if not os.path.exists(self.PASTA_TEMPORARIA):
            os.makedirs(self.PASTA_TEMPORARIA)

    def _verificar_importacao_existente(self, session, tabela_destino, competencia):
        # ATUALIZADO
        existe = session.query(CtlSysHistImportacao).filter_by(
            Tabela_Destino=tabela_destino,
            Competencia=competencia,
            Status='Ativo'
        ).first()
        return existe is not None

    def _salvar_configuracao_atual(self, session, origem, mapeamento, transformacoes):
        try:
            # ATUALIZADO
            config = session.query(CtlSysConfigImportacao).filter_by(Source_Table=origem).first()
            if not config:
                config = CtlSysConfigImportacao(Source_Table=origem)
                session.add(config)
            
            config.set_mapping(mapeamento)
            config.set_transforms(transformacoes)
        except Exception as e:
            raise e

    def SalvarArquivoTemporario(self, arquivo_storage):
        self._garantir_pasta_temporaria()
        nome_original = secure_filename(arquivo_storage.filename)
        nome_unico = f"{uuid.uuid4()}_{nome_original}"
        caminho_arquivo = os.path.join(self.PASTA_TEMPORARIA, nome_unico)
        
        try:
            arquivo_storage.save(caminho_arquivo)
            return caminho_arquivo, nome_unico
        except Exception as e:
            raise e

    def ObterAmostraAnalise(self, nome_arquivo):
        caminho_arquivo = os.path.join(self.PASTA_TEMPORARIA, nome_arquivo)
        return analyze_excel_sample(caminho_arquivo)

    def CarregarUltimaConfiguracao(self, origem):
        session = self._obter_sessao()
        try:
            # ATUALIZADO
            config = session.query(CtlSysConfigImportacao).filter_by(Source_Table=origem).first()
            if config:
                return config.get_mapping(), config.get_transforms()
            return {}, {}
        finally:
            session.close()

    def ObterPreviaTransformacao(self, nome_arquivo, mapeamento, transformacoes):
        caminho_arquivo = os.path.join(self.PASTA_TEMPORARIA, nome_arquivo)
        if not os.path.exists(caminho_arquivo):
            return {"error": "Arquivo temporário expirou ou foi deletado."}
        return generate_preview_value(caminho_arquivo, mapeamento, transformacoes)

    def ExecutarTransacaoImportacao(self, nome_arquivo, mapeamento, tabela_destino, nome_usuario, transformacoes=None):
        if tabela_destino not in self.TABELAS_PERMITIDAS:
            raise Exception("Tabela de destino inválida ou não permitida.")

        caminho_arquivo = os.path.join(self.PASTA_TEMPORARIA, nome_arquivo)
        if not os.path.exists(caminho_arquivo):
            raise Exception("O arquivo temporário não foi encontrado.")

        engine = GetPostgresEngine()
        session = self._obter_sessao()

        try:
            df_check = pd.read_excel(caminho_arquivo, engine='openpyxl', nrows=500)
            df_check.columns = [str(c).replace('\n', ' ').strip() for c in df_check.columns]
            
            col_excel_data = next((k for k, v in mapeamento.items() if v == 'Data'), None)
            if not col_excel_data: raise Exception("Coluna obrigatória 'Data' não foi mapeada.")
                
            if transformacoes and col_excel_data in transformacoes:
                df_check = apply_transformations(df_check, {col_excel_data: transformacoes[col_excel_data]})
                
            competencia_prevista = get_competencia_from_df(df_check, col_excel_data)
            
            if self._verificar_importacao_existente(session, tabela_destino, competencia_prevista):
                raise Exception(f"Já existe uma importação ATIVA para {tabela_destino} na competência {competencia_prevista}.")
                
            linhas_inseridas, competencia_real = process_and_save_dynamic(
                caminho_arquivo, mapeamento, tabela_destino, engine, transformacoes
            )

            # ATUALIZADO
            novo_log = CtlSysHistImportacao(
                Usuario=nome_usuario,
                Tabela_Destino=tabela_destino,
                Competencia=competencia_real,
                Nome_Arquivo=nome_arquivo.split('_', 1)[1],
                Status='Ativo'
            )
            session.add(novo_log)
            self._salvar_configuracao_atual(session, tabela_destino, mapeamento, transformacoes)

            session.commit()
            return linhas_inseridas, competencia_real

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
            if os.path.exists(caminho_arquivo): os.remove(caminho_arquivo)

    def ExecutarReversao(self, id_log, nome_usuario, motivo):
        session = self._obter_sessao()
        engine = GetPostgresEngine()
        
        try:
            # ATUALIZADO
            entrada_log = session.query(CtlSysHistImportacao).get(id_log)
            if not entrada_log: raise Exception("Registro de histórico não encontrado.")
            if entrada_log.Status != 'Ativo': raise Exception("Esta importação já foi revertida anteriormente.")
                
            delta = datetime.now() - entrada_log.Data_Importacao
            if delta.days > 127: raise Exception(f"Prazo para reversão expirado ({delta.days} dias).")

            qtd_deletada = delete_records_by_competencia(engine, entrada_log.Tabela_Destino, entrada_log.Competencia)
            
            entrada_log.Status = 'Revertido'
            entrada_log.Data_Reversao = datetime.now()
            entrada_log.Usuario_Reversao = nome_usuario
            entrada_log.Motivo_Reversao = motivo
            
            session.commit()
            return qtd_deletada, entrada_log.Tabela_Destino

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def ObterHistoricoImportacao(self):
        session = self._obter_sessao()
        try:
            # ATUALIZADO
            return session.query(CtlSysHistImportacao).order_by(CtlSysHistImportacao.Data_Importacao.desc()).all()
        finally:
            session.close()