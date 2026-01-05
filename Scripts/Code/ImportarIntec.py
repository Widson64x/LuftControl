import pandas as pd
import sys
import os
from datetime import datetime, timedelta
from sqlalchemy import text

# Setup de diretórios: Adiciona a raiz do projeto ao path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Db.Connections import get_postgres_engine

def excel_date_to_datetime(serial):
    """Converte serial de data do Excel (int) para datetime do Python"""
    try:
        if pd.isna(serial): return None
        # Excel base date é 1899-12-30 para sistemas Windows
        return datetime(1899, 12, 30) + timedelta(days=float(serial))
    except:
        return None

def importar_intec(caminho_arquivo):
    engine = get_postgres_engine()
    
    print(f"📂 Lendo arquivo: {caminho_arquivo}")
    
    if not os.path.exists(caminho_arquivo):
        print(f"❌ Erro: Arquivo não encontrado no caminho: {caminho_arquivo}")
        return

    try:
        # Lê especificamente como Excel
        df = pd.read_excel(caminho_arquivo, engine='openpyxl')
    except Exception as e:
        print(f"❌ Erro ao ler o Excel: {e}")
        print("💡 Dica: Verifique se instalou o suporte a xlsx: pip install openpyxl")
        return

    print(f"   -> Linhas encontradas: {len(df)}")

    # 1. Normalizar nomes das colunas (remover quebras de linha e espaços extras)
    df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]
    
    # 2. Mapeamento De -> Para (Excel -> Banco de Dados)
    mapa_colunas = {
        'Conta': 'Conta',
        'Título Conta': 'Título Conta',
        'Data': 'Data',
        'Número': 'Numero',
        'Descrição': 'Descricao', 
        'Contra Partida (Crédito)': 'Contra Partida - Credito',
        'Filial': 'Filial',
        'Centro de Custo': 'Centro de Custo',
        'Item': 'Item',
        'Cod Cl. Valor': 'Cod Cl. Valor',
        'Débito': 'Debito',
        'Crédito': 'Credito'
    }
    
    # Renomeia as colunas
    df_db = df.rename(columns=mapa_colunas)
    
    # ⚠️ FILTRAGEM: Mantém APENAS as colunas que existem no mapa (evita erro de coluna extra)
    colunas_validas = [col for col in mapa_colunas.values() if col in df_db.columns]
    df_db = df_db[colunas_validas]

    print("⚙️  Tratando dados...")
    
    # 3. Tratamento de Data
    if 'Data' in df_db.columns:
        if pd.api.types.is_numeric_dtype(df_db['Data']):
            df_db['Data'] = df_db['Data'].apply(excel_date_to_datetime)
        else:
            df_db['Data'] = pd.to_datetime(df_db['Data'], errors='coerce')

    # 4. Tratamento de Valores Numéricos
    cols_valor = ['Debito', 'Credito']
    for col in cols_valor:
        if col in df_db.columns:
            if df_db[col].dtype == object:
                 df_db[col] = df_db[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df_db[col] = pd.to_numeric(df_db[col], errors='coerce').fillna(0.0)

    # 5. Inserção no Banco
    print("💾 Salvando no banco de dados...")
    
    try:
        df_db.to_sql(
            'Razao_Dados_Origem_INTEC',
            engine,
            schema='Dre_Schema',
            if_exists='append', 
            index=False,
            chunksize=1000
        )
        print("🎉 Importação INTEC concluída com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro ao inserir no banco: {e}")

if __name__ == "__main__":
    # Caminho absoluto conforme solicitado, usando 'r' para raw string (evita erro com barras invertidas)
    arquivo = r'C:\Programs\T-Controllership\Data\RAZAO_INTEC.xlsx'
    
    importar_intec(arquivo)