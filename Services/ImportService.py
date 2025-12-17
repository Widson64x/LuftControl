import os
import uuid
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from sqlalchemy.orm import sessionmaker

from Utils.ExcelUtils import (
    analyze_excel_sample, 
    generate_preview_value, 
    process_and_save_dynamic, 
    delete_records_by_competencia
)
from Db.Connections import get_postgres_engine
from Models.POSTGRESS.ImportHistory import ImportHistory
from Models.POSTGRESS.ImportConfig import ImportConfig # <--- Novo Import

# ... (CONSTANTES E FUNÇÕES AUXILIARES MANTIDAS IGUAIS) ...
TEMP_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Data', 'Temp'))
ALLOWED_TABLES = [
    'Razao_Dados_Origem_INTEC',
    'Razao_Dados_Origem_FARMADIST',
    'Razao_Dados_Origem_FARMA',
    'Razao_Dados_Origem_LOGISTICA'
]

def get_session():
    engine = get_postgres_engine()
    Session = sessionmaker(bind=engine)
    return Session()

def ensure_temp_folder():
    if not os.path.exists(TEMP_FOLDER):
        os.makedirs(TEMP_FOLDER)

def save_temp_file(file_storage):
    ensure_temp_folder()
    original_filename = secure_filename(file_storage.filename)
    unique_name = f"{uuid.uuid4()}_{original_filename}"
    file_path = os.path.join(TEMP_FOLDER, unique_name)
    file_storage.save(file_path)
    return file_path, unique_name

# --- NOVAS FUNÇÕES DE CONFIGURAÇÃO ---

def load_last_config(source):
    """Carrega a última configuração salva para esta origem."""
    session = get_session()
    try:
        config = session.query(ImportConfig).filter_by(Source_Table=source).first()
        if config:
            return config.get_mapping(), config.get_transforms()
        return {}, {}
    finally:
        session.close()

def save_current_config(session, source, mapping, transforms):
    """Salva/Atualiza a configuração atual como padrão."""
    config = session.query(ImportConfig).filter_by(Source_Table=source).first()
    if not config:
        config = ImportConfig(Source_Table=source)
        session.add(config)
    
    config.set_mapping(mapping)
    config.set_transforms(transforms)
    # Commit é feito pelo caller (execute_import_transaction)

# -------------------------------------

def get_file_analysis_sample(filename):
    file_path = os.path.join(TEMP_FOLDER, filename)
    return analyze_excel_sample(file_path)

def get_preview_transformation(filename, mapping, transformations):
    file_path = os.path.join(TEMP_FOLDER, filename)
    if not os.path.exists(file_path):
        return {"error": "Arquivo temporário expirou."}
    return generate_preview_value(file_path, mapping, transformations)

def check_existing_import(session, table_dest, competencia):
    exists = session.query(ImportHistory).filter_by(
        Tabela_Destino=table_dest,
        Competencia=competencia,
        Status='Ativo'
    ).first()
    return exists is not None

def execute_import_transaction(filename, mapping, table_destination, user_name, transformations=None):
    if table_destination not in ALLOWED_TABLES:
        raise Exception("Tabela de destino inválida ou não permitida.")

    file_path = os.path.join(TEMP_FOLDER, filename)
    if not os.path.exists(file_path):
        raise Exception("O arquivo temporário não foi encontrado. Faça o upload novamente.")

    engine = get_postgres_engine()
    session = get_session()

    try:
        # 1. Validação de Competência (Leitura Preliminar)
        import pandas as pd
        df_check = pd.read_excel(file_path, engine='openpyxl', nrows=500)
        df_check.columns = [str(c).replace('\n', ' ').strip() for c in df_check.columns]
        
        col_excel_data = next((k for k, v in mapping.items() if v == 'Data'), None)
        if not col_excel_data:
            raise Exception("Coluna 'Data' não mapeada.")
            
        if transformations and col_excel_data in transformations:
            from Utils.ExcelUtils import apply_transformations
            df_check = apply_transformations(df_check, {col_excel_data: transformations[col_excel_data]})
            
        from Utils.ExcelUtils import get_competencia_from_df
        competencia_prevista = get_competencia_from_df(df_check, col_excel_data)
        
        if check_existing_import(session, table_destination, competencia_prevista):
            raise Exception(f"Já existe uma importação ATIVA para {table_destination} na competência {competencia_prevista}.")
            
        # 2. Executa Carga Real
        rows_inserted, competencia_real = process_and_save_dynamic(
            file_path, mapping, table_destination, engine, transformations
        )

        # 3. Grava Log
        new_log = ImportHistory(
            Usuario=user_name,
            Tabela_Destino=table_destination,
            Competencia=competencia_real,
            Nome_Arquivo=filename.split('_', 1)[1], 
            Status='Ativo'
        )
        session.add(new_log)

        # 4. SALVA CONFIGURAÇÃO COMO PADRÃO (NOVO)
        save_current_config(session, table_destination, mapping, transformations)

        session.commit()
        return rows_inserted, competencia_real

    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
        if os.path.exists(file_path):
            os.remove(file_path)

def perform_rollback(log_id, user_name, reason):
    """
    Executa a reversão de uma importação.
    """
    session = get_session()
    engine = get_postgres_engine()
    
    try:
        log_entry = session.query(ImportHistory).get(log_id)
        
        if not log_entry:
            raise Exception("Registro não encontrado.")
        
        if log_entry.Status != 'Ativo':
            raise Exception("Importação já revertida.")
            
        # Validação de Prazo (7 dias)
        delta = datetime.now() - log_entry.Data_Importacao
        if delta.days > 7:
            raise Exception(f"Prazo expirado ({delta.days} dias). Limite de 7 dias.")

        # Delete físico
        deleted_count = delete_records_by_competencia(engine, log_entry.Tabela_Destino, log_entry.Competencia)
        
        # Update Log
        log_entry.Status = 'Revertido'
        log_entry.Data_Reversao = datetime.now()
        log_entry.Usuario_Reversao = user_name
        log_entry.Motivo_Reversao = reason
        
        session.commit()
        return deleted_count, log_entry.Tabela_Destino

    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_import_history():
    """Lista histórico ordenado por data."""
    session = get_session()
    try:
        return session.query(ImportHistory).order_by(ImportHistory.Data_Importacao.desc()).all()
    finally:
        session.close()