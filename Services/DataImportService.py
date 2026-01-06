import os
import uuid
import json
import pandas as pd # Importado no topo para evitar import dentro de função
from datetime import datetime
from werkzeug.utils import secure_filename
from sqlalchemy.orm import sessionmaker

# --- Imports Utilitários (O cérebro da operação Excel) ---
from Utils.ExcelUtils import (
    analyze_excel_sample, 
    generate_preview_value, 
    process_and_save_dynamic, 
    delete_records_by_competencia,
    apply_transformations, # Trazendo para o topo
    get_competencia_from_df # Trazendo para o topo
)

# --- Import do Logger ---
from Utils.Logger import RegistrarLog 

# --- Imports de Banco de Dados ---
from Db.Connections import GetPostgresEngine
from Models.POSTGRESS.ImportHistory import ImportHistory
from Models.POSTGRESS.ImportConfig import ImportConfig

# Definição do local onde os arquivos temporários vão morar (temporariamente, claro)
TEMP_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Data', 'Temp'))

# Lista VIP: Apenas essas tabelas podem receber dados
ALLOWED_TABLES = [
    'Razao_Dados_Origem_INTEC',
    'Razao_Dados_Origem_FARMADIST',
    'Razao_Dados_Origem_FARMA',
]

def GetSession():
    """
    Fabrica uma sessão novinha com o Postgres.
    Use com sabedoria e feche quando terminar!
    """
    engine = GetPostgresEngine()
    Session = sessionmaker(bind=engine)
    return Session()

def EnsureTempFolder():
    """Garante que a pasta de arquivos temporários existe."""
    if not os.path.exists(TEMP_FOLDER):
        try:
            os.makedirs(TEMP_FOLDER)
            RegistrarLog(f"Pasta temporária criada em {TEMP_FOLDER}", "SYSTEM")
        except Exception as e:
            RegistrarLog("Erro ao criar pasta temporária", "ERROR", e)
            raise e

def SaveTempFile(file_storage):
    """
    Salva o arquivo que o usuário enviou com um nome único (UUID)
    para evitar que 'planilha.xlsx' de um sobrescreva 'planilha.xlsx' de outro.
    """
    EnsureTempFolder()
    # Limpa o nome do arquivo para evitar injeção de caminho
    original_filename = secure_filename(file_storage.filename)
    # Cria um RG único para o arquivo
    unique_name = f"{uuid.uuid4()}_{original_filename}"
    file_path = os.path.join(TEMP_FOLDER, unique_name)
    
    try:
        file_storage.save(file_path)
        RegistrarLog(f"Arquivo temporário salvo: {unique_name}", "FILE")
        return file_path, unique_name
    except Exception as e:
        RegistrarLog(f"Falha ao salvar arquivo temporário {original_filename}", "ERROR", e)
        raise e

# --- NOVAS FUNÇÕES DE CONFIGURAÇÃO (MEMÓRIA DO SISTEMA) ---

def LoadLastConfig(source):
    """
    Busca no banco se já fizemos uma importação para essa origem antes.
    Se sim, recupera o mapeamento de colunas para o usuário não ter que refazer tudo.
    """
    session = GetSession()
    try:
        config = session.query(ImportConfig).filter_by(Source_Table=source).first()
        if config:
            RegistrarLog(f"Configuração carregada para {source}", "DATABASE")
            return config.get_mapping(), config.get_transforms()
        return {}, {}
    except Exception as e:
        RegistrarLog(f"Erro ao carregar configuração para {source}", "ERROR", e)
        return {}, {}
    finally:
        session.close()

def SaveCurrentConfig(session, source, mapping, transforms):
    """
    Salva a configuração atual como a nova 'padrão' para futuras importações.
    Nota: Não faz commit aqui, aproveita a transação do pai.
    """
    try:
        config = session.query(ImportConfig).filter_by(Source_Table=source).first()
        if not config:
            config = ImportConfig(Source_Table=source)
            session.add(config)
        
        config.set_mapping(mapping)
        config.set_transforms(transforms)
        RegistrarLog(f"Configuração atualizada para {source}", "DATABASE")
    except Exception as e:
        RegistrarLog(f"Erro ao salvar configuração para {source}", "ERROR", e)
        raise e

# -------------------------------------

def GetFileAnalysisSample(filename):
    """
    Lê o cabeçalho e as primeiras linhas do Excel para mostrar na tela de mapeamento.
    """
    file_path = os.path.join(TEMP_FOLDER, filename)
    try:
        return analyze_excel_sample(file_path)
    except Exception as e:
        RegistrarLog(f"Erro ao analisar amostra do arquivo {filename}", "ERROR", e)
        raise e

def GetPreviewTransformation(filename, mapping, transformations):
    """
    Gera uma prévia de como os dados ficarão após aplicar as regras (ex: datas, valores).
    Útil para o frontend via AJAX.
    """
    file_path = os.path.join(TEMP_FOLDER, filename)
    if not os.path.exists(file_path):
        RegistrarLog(f"Tentativa de preview em arquivo inexistente: {filename}", "WARNING")
        return {"error": "Arquivo temporário expirou ou foi deletado."}
    
    try:
        return generate_preview_value(file_path, mapping, transformations)
    except Exception as e:
        RegistrarLog(f"Erro ao gerar preview de transformação", "ERROR", e)
        raise e

def CheckExistingImport(session, table_dest, competencia):
    """
    Verifica se já existe uma importação 'Ativa' para essa tabela e competência (Mês/Ano).
    Evita duplicidade de dados contábeis.
    """
    exists = session.query(ImportHistory).filter_by(
        Tabela_Destino=table_dest,
        Competencia=competencia,
        Status='Ativo'
    ).first()
    return exists is not None

def ExecuteImportTransaction(filename, mapping, table_destination, user_name, transformations=None):
    """
    O Coração da Importação:
    1. Valida integridade e regras de negócio.
    2. Lê o Excel completo.
    3. Aplica transformações.
    4. Salva no Banco.
    5. Registra Log e atualiza Configurações.
    """
    RegistrarLog(f"Iniciando Transação de Importação: {filename} -> {table_destination} ({user_name})", "SERVICE")

    if table_destination not in ALLOWED_TABLES:
        RegistrarLog(f"Tentativa de importação para tabela não permitida: {table_destination}", "SECURITY")
        raise Exception("Tabela de destino inválida ou não permitida.")

    file_path = os.path.join(TEMP_FOLDER, filename)
    if not os.path.exists(file_path):
        RegistrarLog(f"Arquivo temporário não encontrado: {filename}", "ERROR")
        raise Exception("O arquivo temporário sumiu. Por favor, faça o upload novamente.")

    engine = GetPostgresEngine()
    session = GetSession()

    try:
        # 1. Validação de Competência (Leitura Preliminar das primeiras 500 linhas)
        # Usamos pandas aqui para ser rápido
        RegistrarLog("Iniciando validação de competência (Pré-leitura)", "DEBUG")
        df_check = pd.read_excel(file_path, engine='openpyxl', nrows=500)
        # Normaliza nomes de colunas (remove quebras de linha e espaços extras)
        df_check.columns = [str(c).replace('\n', ' ').strip() for c in df_check.columns]
        
        # Descobre qual coluna do Excel foi mapeada para 'Data'
        col_excel_data = next((k for k, v in mapping.items() if v == 'Data'), None)
        if not col_excel_data:
            raise Exception("Coluna obrigatória 'Data' não foi mapeada.")
            
        # Se tiver transformação na data (ex: converter string pra date), aplica agora
        if transformations and col_excel_data in transformations:
            df_check = apply_transformations(df_check, {col_excel_data: transformations[col_excel_data]})
            
        # Calcula a competência (ex: '2023-10') baseada nos dados
        competencia_prevista = get_competencia_from_df(df_check, col_excel_data)
        RegistrarLog(f"Competência detectada: {competencia_prevista}", "DEBUG")
        
        # O Guardião: Impede importar se já existe dados ativos desse mês
        if CheckExistingImport(session, table_destination, competencia_prevista):
            msg = f"Já existe uma importação ATIVA para {table_destination} na competência {competencia_prevista}."
            RegistrarLog(msg, "WARNING")
            raise Exception(msg)
            
        # 2. Executa Carga Real (Processamento pesado)
        RegistrarLog("Iniciando carga real e processamento dinâmico...", "INFO")
        rows_inserted, competencia_real = process_and_save_dynamic(
            file_path, mapping, table_destination, engine, transformations
        )

        # 3. Grava Log de Histórico
        new_log = ImportHistory(
            Usuario=user_name,
            Tabela_Destino=table_destination,
            Competencia=competencia_real,
            Nome_Arquivo=filename.split('_', 1)[1], # Remove o UUID do nome visual
            Status='Ativo'
        )
        session.add(new_log)

        # 4. Salva essa configuração como a nova favorita do usuário
        SaveCurrentConfig(session, table_destination, mapping, transformations)

        session.commit()
        RegistrarLog(f"Importação concluída com sucesso. Registros: {rows_inserted}. Comp: {competencia_real}", "SUCCESS")
        return rows_inserted, competencia_real

    except Exception as e:
        session.rollback() # Se der ruim, desfaz tudo
        RegistrarLog(f"Falha na Transação de Importação. Rollback executado.", "ERROR", e)
        raise e
    finally:
        session.close()
        # Faxina: Remove o arquivo temporário
        if os.path.exists(file_path):
            os.remove(file_path)
            RegistrarLog(f"Arquivo temporário limpo: {filename}", "DEBUG")

def PerformRollback(log_id, user_name, reason):
    """
    Botão de Pânico: Reverte uma importação inteira.
    Regra: Só pode reverter se tiver menos de 7 dias.
    """
    RegistrarLog(f"Solicitação de Rollback ID {log_id} por {user_name}. Motivo: {reason}", "SERVICE")
    session = GetSession()
    engine = GetPostgresEngine()
    
    try:
        log_entry = session.query(ImportHistory).get(log_id)
        
        if not log_entry:
            raise Exception("Registro de histórico não encontrado.")
        
        if log_entry.Status != 'Ativo':
            raise Exception("Esta importação já foi revertida anteriormente.")
            
        # Validação de Prazo (Segurança)
        delta = datetime.now() - log_entry.Data_Importacao
        if delta.days > 7:
            msg = f"Prazo para reversão expirado ({delta.days} dias). O limite é de 7 dias."
            RegistrarLog(msg, "WARNING")
            raise Exception(msg)

        # Delete físico dos dados na tabela destino
        RegistrarLog(f"Deletando registros da tabela {log_entry.Tabela_Destino} Competência {log_entry.Competencia}", "DB_ACTION")
        deleted_count = delete_records_by_competencia(engine, log_entry.Tabela_Destino, log_entry.Competencia)
        
        # Atualiza o status no log para saber quem fez a besteira e porquê
        log_entry.Status = 'Revertido'
        log_entry.Data_Reversao = datetime.now()
        log_entry.Usuario_Reversao = user_name
        log_entry.Motivo_Reversao = reason
        
        session.commit()
        RegistrarLog(f"Rollback concluído com sucesso. {deleted_count} registros removidos.", "SUCCESS")
        return deleted_count, log_entry.Tabela_Destino

    except Exception as e:
        session.rollback()
        RegistrarLog("Erro crítico ao executar Rollback", "ERROR", e)
        raise e
    finally:
        session.close()

def GetImportHistory():
    """Retorna a lista completa de importações para o painel de controle."""
    session = GetSession()
    try:
        return session.query(ImportHistory).order_by(ImportHistory.Data_Importacao.desc()).all()
    except Exception as e:
        RegistrarLog("Erro ao buscar histórico de importações", "ERROR", e)
        return []
    finally:
        session.close()