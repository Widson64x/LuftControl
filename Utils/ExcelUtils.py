import pandas as pd
from qvd import qvd_reader
import os
import re
from datetime import datetime, timedelta
from sqlalchemy import text

# --- Import do Logger ---
from Utils.Logger import RegistrarLog

def excel_date_to_datetime(serial):
    """Converte serial de data do Excel (int) para datetime do Python."""
    try:
        if pd.isna(serial): return None
        # Excel base date é 1899-12-30 para sistemas Windows
        return datetime(1899, 12, 30) + timedelta(days=float(serial))
    except Exception as e:
        # Não logamos erro aqui para não floodar o log (chamado por linha), apenas retornamos None
        return None

def find_best_sample_row_index(df):
    """
    Encontra o índice da linha mais 'rica' em dados para usar como amostra.
    """
    if df.empty: return 0
    
    best_idx = 0
    max_score = -1
    
    for idx, row in df.iterrows():
        non_empty_count = 0
        has_date = False
        has_number = False
        
        for val in row:
            if pd.isna(val): continue
            s_val = str(val).strip()
            if not s_val or s_val.lower() == 'nan': continue
            
            non_empty_count += 1
            
            # Verificação de Data
            if isinstance(val, (datetime, pd.Timestamp)):
                has_date = True
            elif isinstance(s_val, str) and len(s_val) >= 8:
                if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', s_val):
                    has_date = True
            
            # Verificação de Número
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                 has_number = True
            elif re.match(r'^-?[\d\.,]+$', s_val) and any(c in s_val for c in ',.'):
                 has_number = True

        score = (non_empty_count * 1) + (10 if has_date else 0) + (2 if has_number else 0)
        
        if score > max_score:
            max_score = score
            best_idx = idx
            
    return best_idx

def apply_transformations(df, transformations):
    """Aplica transformações específicas nas colunas do DataFrame."""
    if not transformations:
        return df

    RegistrarLog(f"Aplicando transformações: {list(transformations.keys())}", "EXCEL_TRANSFORM")

    for col, trans_type in transformations.items():
        if col not in df.columns:
            continue
            
        try:
            if trans_type == 'upper':
                df[col] = df[col].astype(str).str.upper()
            elif trans_type == 'lower':
                df[col] = df[col].astype(str).str.lower()
            elif trans_type == 'date_auto':
                def parse_dt(x):
                    if pd.isna(x) or str(x).strip() == '': return pd.NaT
                    if isinstance(x, (int, float)): return excel_date_to_datetime(x)
                    return pd.to_datetime(x, errors='coerce', dayfirst=True)
                df[col] = df[col].apply(parse_dt)
            
            elif trans_type == 'currency_br':
                def clean_currency(x):
                    # 1. Se já for numérico (float/int), garante ABSOLUTO
                    if isinstance(x, (int, float)) and not pd.isna(x):
                        return abs(float(x))
                    
                    if pd.isna(x): return 0.0
                    s = str(x).strip()
                    if not s: return 0.0
                    
                    # 2. REMOVE SINAL DE MENOS, letras e espaços. 
                    # Regex mantem apenas digitos, virgula e ponto.
                    # O sinal '-' é removido aqui propositalmente.
                    s_clean = re.sub(r'[^\d,\.]', '', s)
                    
                    if not s_clean: return 0.0

                    if ',' in s_clean: s_clean = s_clean.replace('.', '').replace(',', '.')
                    
                    try: 
                        return abs(float(s_clean))
                    except: 
                        return 0.0
                
                df[col] = df[col].apply(clean_currency)

            elif trans_type == 'clean_code':
                def only_numbers(x):
                    if pd.isna(x): return 0
                    s = str(x)
                    s_clean = re.sub(r'\D', '', s)
                    if not s_clean: return 0
                    return s_clean
                df[col] = df[col].apply(only_numbers)
            elif trans_type == 'clean_spaces':
                df[col] = df[col].astype(str).str.strip()
            elif trans_type == 'to_int':
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

        except Exception as e:
            # Logamos o warning mas não paramos o processo
            RegistrarLog(f"Falha ao aplicar transformação '{trans_type}' na coluna '{col}'", "WARNING", e)
            pass
    
    return df

def analyze_excel_sample(file_path):
    """Lê o ficheiro e retorna colunas, tipos e a MELHOR linha de amostra."""
    if not os.path.exists(file_path):
        RegistrarLog(f"Arquivo não encontrado para análise: {file_path}", "ERROR")
        raise FileNotFoundError("Ficheiro temporário não encontrado.")

    try:
        # RegistrarLog(f"Iniciando análise de amostra: {os.path.basename(file_path)}", "EXCEL_READ")
        
        df_preview = pd.read_excel(file_path, engine='openpyxl', nrows=50)
        df_preview.columns = [str(c).replace('\n', ' ').strip() for c in df_preview.columns]
        columns = df_preview.columns.tolist()
        
        types = {}
        for col in columns:
            dtype = df_preview[col].dtype
            if pd.api.types.is_numeric_dtype(dtype): types[col] = "Numérico"
            elif pd.api.types.is_datetime64_any_dtype(dtype): types[col] = "Data"
            else: types[col] = "Texto"

        sample_row = {}
        if not df_preview.empty:
            best_idx = find_best_sample_row_index(df_preview)
            row_series = df_preview.loc[best_idx]
        else:
            return columns, types, {c: "-" for c in columns}

        for col in columns:
            val = row_series[col]
            if pd.isna(val): sample_row[col] = ""
            elif isinstance(val, (datetime, pd.Timestamp)): sample_row[col] = val.strftime('%d/%m/%Y')
            else: sample_row[col] = str(val)

        return columns, types, sample_row

    except Exception as e:
        RegistrarLog("Erro crítico na análise do Excel", "ERROR", e)
        raise Exception(f"Erro na análise do Excel: {str(e)}")

def generate_preview_value(file_path, mapping, transformations):
    """Gera o preview final."""
    try:
        df = pd.read_excel(file_path, engine='openpyxl', nrows=50)
        df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]
        df = apply_transformations(df, transformations)

        if not df.empty:
            best_idx = find_best_sample_row_index(df)
            df_row = df.loc[[best_idx]]
        else:
            return {}
        
        preview_result = {}
        for excel_col, db_col in mapping.items():
            if db_col == 'IGNORE' or excel_col not in df_row.columns: continue
            
            val = df_row.iloc[0][excel_col]
            
            # FORÇA VISUALIZAÇÃO ABSOLUTA NO PREVIEW TAMBÉM
            if db_col in ['Debito', 'Credito']:
                if isinstance(val, (int, float)):
                    val = abs(val)

            tipo_final = "Texto"
            val_formatado = str(val)

            if pd.isna(val) or val is pd.NaT:
                val_formatado = "NULL"
                tipo_final = "Vazio"
            elif isinstance(val, (int, float)):
                tipo_final = "Numérico"
                val_formatado = str(val)
            elif isinstance(val, (datetime, pd.Timestamp)):
                tipo_final = "Data/Hora"
                val_formatado = val.strftime('%d/%m/%Y')
            
            preview_result[excel_col] = { "valor": val_formatado, "tipo": tipo_final, "db_col": db_col }
            
        return preview_result
    except Exception as e:
        RegistrarLog("Erro ao gerar preview dinâmico", "ERROR", e)
        return {"error": str(e)}

def get_competencia_from_df(df, col_data_mapped):
    try:
        dates = pd.to_datetime(df[col_data_mapped], errors='coerce').dropna()
        if dates.empty: raise Exception("Não há datas válidas na coluna Data.")
        mode_date = dates.dt.to_period('M').mode()[0]
        return str(mode_date)
    except Exception as e:
        # Erro é capturado e relançado para ser logado no Service
        raise Exception(f"Erro ao identificar competência: {str(e)}")

def delete_records_by_competencia(engine, table_name, competencia):
    schema = "Dre_Schema"
    if not competencia or '-' not in competencia: raise Exception("Competência inválida.")
    year, month = map(int, competencia.split('-'))
    
    RegistrarLog(f"Executando DELETE em {table_name} para {month}/{year}", "DB_QUERY")
    
    sql = text(f""" DELETE FROM "{schema}"."{table_name}" WHERE EXTRACT(YEAR FROM "Data") = :year AND EXTRACT(MONTH FROM "Data") = :month """)
    with engine.begin() as conn:
        result = conn.execute(sql, {"year": year, "month": month})
        return result.rowcount

def process_and_save_dynamic(file_path, column_mapping, table_destination, engine, transformations=None):
    """
    Processa o arquivo completo, aplica transformações, filtra regras de negócio e salva.
    Versão Corrigida: Tratamento robusto de Tipos (Texto vs Inteiro) e Limpeza de Dados.
    """
    try:
        RegistrarLog(f"Iniciando leitura e processamento Pandas: {os.path.basename(file_path)}", "EXCEL_CORE")
        
        df = pd.read_excel(file_path, engine='openpyxl')
        # Normaliza nomes das colunas (remove quebras de linha e espaços extras)
        df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]

        # 1. Aplica Transformações de Usuário (se houver)
        if transformations:
            df = apply_transformations(df, transformations)
        
        # 2. Renomeia Colunas usando o mapeamento
        final_mapping = {k: v for k, v in column_mapping.items() if v and v != 'IGNORE'}
        if not final_mapping: raise Exception("Nenhum mapeamento válido encontrado.")
            
        df_db = df.rename(columns=final_mapping)
        cols_destino = list(final_mapping.values())
        cols_existentes = [c for c in cols_destino if c in df_db.columns]
        df_db = df_db[cols_existentes]

        # Regra: Validação Data (Obrigatória)
        if 'Data' not in df_db.columns: raise Exception("A coluna 'Data' é obrigatória.")
        df_db['Data'] = pd.to_datetime(df_db['Data'], errors='coerce')
        # Remove linhas onde a Data é inválida (NaT) antes de pegar a competência
        initial_rows = len(df_db)
        df_db = df_db.dropna(subset=['Data'])
        if df_db.empty: raise Exception("Arquivo sem datas válidas.")
        
        competencia = get_competencia_from_df(df_db, 'Data')
        RegistrarLog(f"Competência calculada: {competencia}. Linhas válidas (data): {len(df_db)}/{initial_rows}", "INFO")

        # Regra: Remover linha de 'SALDO ANTERIOR' se existir
        if 'Descricao' in df_db.columns:
            # Converte para string antes de comparar para evitar erro
            df_db = df_db[df_db['Descricao'].astype(str).str.strip().str.upper() != 'SALDO ANTERIOR']

        # -------------------------------------------------------------------
        # TRATAMENTO DE TIPOS BLINDADO
        # -------------------------------------------------------------------
        
        RegistrarLog("Iniciando sanitização de tipos...", "DEBUG")

        # GRUPO 1: Colunas de IDENTIFICAÇÃO TEXTUAL (VARCHAR no Banco)
        # Evita erro de conversão de números gigantes (overflow) e preserva zeros à esquerda.
        cols_text_ids = ['Conta', 'Numero', 'Cod Cl Valor', 'Descricao', 'Contra Partida - Credito']
        
        for col in cols_text_ids:
            if col in df_db.columns:
                def clean_text_id(x):
                    if pd.isna(x) or x == '': return None
                    s = str(x).strip()
                    # Se o Excel leu como float (ex: '1234.0'), remove o decimal
                    if s.endswith('.0'): s = s[:-2]
                    # Retorna limpo. Para 'Numero' e 'Conta', mantemos carateres numéricos e separadores comuns
                    return s 
                
                df_db[col] = df_db[col].apply(clean_text_id).astype(str).replace('None', None)

        # GRUPO 2: Colunas de INTEIROS (BIGINT no Banco)
        # Remove pontos e traços (ex: '2.1.1.01' -> 21101) para o banco aceitar.
        cols_int_ids = ['Filial', 'Item', 'Centro de Custo']
        
        for col in cols_int_ids:
            if col in df_db.columns:
                def clean_and_int(x):
                    if pd.isna(x): return None
                    s = str(x).strip()
                    # Remove tudo que NÃO for dígito (0-9)
                    s_clean = re.sub(r'\D', '', s)
                    if not s_clean: return None
                    return int(s_clean)
                
                # Converte para numérico (Int64 permite NaN/Null, int normal não)
                df_db[col] = df_db[col].apply(clean_and_int).astype('Int64')

        # GRUPO 3: Colunas de VALOR (DECIMAL/FLOAT)
        # Garante valor absoluto (sem sinal negativo) e trata nulos como 0.0
        cols_valor = ['Debito', 'Credito']
        for col in cols_valor:
            if col in df_db.columns:
                df_db[col] = pd.to_numeric(df_db[col], errors='coerce').fillna(0.0).abs()
            else:
                df_db[col] = 0.0

        # Regra: Filtro de Linhas Zeradas (ignora registros sem valor financeiro)
        mask_valor = (df_db['Debito'] != 0) | (df_db['Credito'] != 0)
        df_db = df_db[mask_valor]

        if df_db.empty: raise Exception("Nenhum registro válido encontrado após filtros.")

        RegistrarLog(f"Dados sanitizados. Preparando para inserir {len(df_db)} registros em {table_destination}", "INFO")

        # Inserção no Banco
        df_db.to_sql(
            table_destination,
            engine,
            schema='Dre_Schema',
            if_exists='append', 
            index=False,
            chunksize=1000 # Lotes menores para evitar timeout
        )
        
        return len(df_db), competencia

    except Exception as e:
        # Adiciona contexto ao erro para facilitar debug
        RegistrarLog("Erro durante o processamento do Excel (Pandas)", "ERROR", e)
        raise Exception(f"Erro no processamento final: {str(e)}")
    
def ler_qvd_para_dataframe(caminho_relativo):
    """
    Localiza o arquivo QVD e converte em DataFrame.
    """
    # Constrói o caminho absoluto baseado na raiz do projeto (uma pasta acima de Utils)
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    full_path = os.path.join(base_path, caminho_relativo)

    if not os.path.exists(full_path):
        RegistrarLog(f"Arquivo QVD não encontrado em: {full_path}", "ERROR")
        raise FileNotFoundError(f"Arquivo não encontrado: {full_path}")

    try:
        RegistrarLog(f"Lendo QVD: {os.path.basename(full_path)}", "QVD_LOAD")
        df = qvd_reader.read(full_path)
        return df
    except Exception as e:
        RegistrarLog(f"Erro ao processar QVD", "ERROR", e)
        raise e