import pandas as pd
import os
import re
from datetime import datetime, timedelta
from sqlalchemy import text

def excel_date_to_datetime(serial):
    """Converte serial de data do Excel (int) para datetime do Python."""
    try:
        if pd.isna(serial): return None
        # Excel base date é 1899-12-30 para sistemas Windows
        return datetime(1899, 12, 30) + timedelta(days=float(serial))
    except:
        return None

def apply_transformations(df, transformations):
    """
    Aplica transformações específicas nas colunas do DataFrame.
    transformations: dict { 'NomeColunaExcel': 'tipo_transformacao' }
    """
    if not transformations:
        return df

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
                    if pd.isna(x) or str(x).strip() == '':
                        return pd.NaT
                    if isinstance(x, (int, float)): 
                        return excel_date_to_datetime(x)
                    return pd.to_datetime(x, errors='coerce', dayfirst=True)
                
                df[col] = df[col].apply(parse_dt)

            elif trans_type == 'currency_br':
                def clean_currency(x):
                    if pd.isna(x): return 0.0
                    s = str(x)
                    if not s.strip(): return 0.0
                    s = s.replace('.', '').replace(',', '.')
                    try:
                        return float(s)
                    except:
                        return 0.0
                
                df[col] = df[col].apply(clean_currency)

            elif trans_type == 'clean_code':
                # Remove pontos, traços, barras e espaços. Mantém APENAS NÚMEROS.
                def only_numbers(x):
                    if pd.isna(x): return 0
                    s = str(x)
                    s_clean = re.sub(r'\D', '', s)
                    if not s_clean: return 0
                    return int(s_clean)
                
                df[col] = df[col].apply(only_numbers)

            elif trans_type == 'clean_spaces':
                df[col] = df[col].astype(str).str.strip()
                
            elif trans_type == 'to_int':
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

        except Exception as e:
            print(f"Erro ao transformar coluna {col} ({trans_type}): {e}")
            pass
    
    return df

def analyze_excel_sample(file_path):
    """
    Lê o ficheiro e retorna colunas, tipos e a amostra (preferencialmente a linha 5).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError("Ficheiro temporário não encontrado.")

    try:
        df_preview = pd.read_excel(file_path, engine='openpyxl', nrows=10)
        df_preview.columns = [str(c).replace('\n', ' ').strip() for c in df_preview.columns]
        columns = df_preview.columns.tolist()
        
        types = {}
        for col in columns:
            dtype = df_preview[col].dtype
            if pd.api.types.is_numeric_dtype(dtype): 
                types[col] = "Numérico"
            elif pd.api.types.is_datetime64_any_dtype(dtype): 
                types[col] = "Data"
            else: 
                types[col] = "Texto"

        sample_row = {}
        target_index = 4 
        
        if len(df_preview) > target_index:
            row_series = df_preview.iloc[target_index]
        elif not df_preview.empty:
            row_series = df_preview.iloc[-1]
        else:
            return columns, types, {c: "-" for c in columns}

        for col in columns:
            val = row_series[col]
            if pd.isna(val):
                sample_row[col] = ""
            elif isinstance(val, (datetime, pd.Timestamp)):
                sample_row[col] = val.strftime('%d/%m/%Y')
            else:
                sample_row[col] = str(val)

        return columns, types, sample_row

    except Exception as e:
        raise Exception(f"Erro na análise do Excel: {str(e)}")

def generate_preview_value(file_path, mapping, transformations):
    """Gera o preview final (formato DB) para a 5ª linha."""
    try:
        df = pd.read_excel(file_path, engine='openpyxl', nrows=10)
        df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]

        df = apply_transformations(df, transformations)

        target_index = 4
        if len(df) > target_index:
            df_row = df.iloc[[target_index]]
        elif not df.empty:
            df_row = df.iloc[[-1]]
        else:
            return {}
        
        preview_result = {}
        
        for excel_col, db_col in mapping.items():
            if db_col == 'IGNORE' or excel_col not in df_row.columns:
                continue
            
            val = df_row.iloc[0][excel_col]
            
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
            
            preview_result[excel_col] = {
                "valor": val_formatado,
                "tipo": tipo_final,
                "db_col": db_col
            }
            
        return preview_result

    except Exception as e:
        return {"error": str(e)}

def get_competencia_from_df(df, col_data_mapped):
    try:
        dates = pd.to_datetime(df[col_data_mapped], errors='coerce').dropna()
        if dates.empty:
            raise Exception("Não há datas válidas na coluna mapeada como Data.")
        mode_date = dates.dt.to_period('M').mode()[0]
        return str(mode_date)
    except Exception as e:
        raise Exception(f"Erro ao identificar competência: {str(e)}")

def delete_records_by_competencia(engine, table_name, competencia):
    schema = "Dre_Schema"
    if not competencia or '-' not in competencia:
        raise Exception("Competência inválida.")
    year, month = map(int, competencia.split('-'))
    
    sql = text(f"""
        DELETE FROM "{schema}"."{table_name}"
        WHERE EXTRACT(YEAR FROM "Data") = :year
        AND EXTRACT(MONTH FROM "Data") = :month
    """)
    
    with engine.begin() as conn:
        result = conn.execute(sql, {"year": year, "month": month})
        return result.rowcount

def process_and_save_dynamic(file_path, column_mapping, table_destination, engine, transformations=None):
    """
    Processa o arquivo completo, aplica transformações, filtra regras de negócio e salva.
    """
    try:
        # Lê arquivo completo
        df = pd.read_excel(file_path, engine='openpyxl')
        df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]

        # 1. Aplica Transformações de Usuário
        if transformations:
            df = apply_transformations(df, transformations)
        
        # 2. Filtra e Renomeia colunas
        final_mapping = {k: v for k, v in column_mapping.items() if v and v != 'IGNORE'}
        
        if not final_mapping:
            raise Exception("Nenhum mapeamento válido encontrado.")
            
        df_db = df.rename(columns=final_mapping)
        
        cols_destino = list(final_mapping.values())
        cols_existentes = [c for c in cols_destino if c in df_db.columns]
        df_db = df_db[cols_existentes]

        # --- REGRA DE NEGÓCIO: REMOVER SALDO ANTERIOR ---
        # Verifica se existe a coluna 'Descricao' (mapeada) e filtra
        if 'Descricao' in df_db.columns:
            # Normaliza para garantir (remove espaços extras) e remove a linha
            linhas_antes = len(df_db)
            df_db = df_db[df_db['Descricao'].astype(str).str.strip() != 'SALDO ANTERIOR']
            linhas_depois = len(df_db)
            
            if linhas_antes > linhas_depois:
                print(f"🧹 Filtro Aplicado: {linhas_antes - linhas_depois} linhas de 'SALDO ANTERIOR' removidas.")

        # 3. Validação Obrigatória de Coluna 'Data'
        if 'Data' not in df_db.columns:
            raise Exception("A coluna 'Data' (Data Lançamento) é obrigatória e deve ser mapeada.")
        
        df_db['Data'] = pd.to_datetime(df_db['Data'], errors='coerce')
        
        # Identifica Competência
        competencia = get_competencia_from_df(df_db, 'Data')

        # 4. Tratamento Final de Numéricos
        cols_valor = ['Debito', 'Credito']
        for col in cols_valor:
            if col in df_db.columns:
                df_db[col] = pd.to_numeric(df_db[col], errors='coerce').fillna(0.0)

        # 5. Salva no Banco
        df_db.to_sql(
            table_destination,
            engine,
            schema='Dre_Schema',
            if_exists='append', 
            index=False,
            chunksize=1000
        )
        
        return len(df_db), competencia

    except Exception as e:
        raise Exception(f"Erro no processamento final: {str(e)}")