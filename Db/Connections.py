import os
import urllib.parse
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()

# ==========================================
# CONFIGURAÇÃO POSTGRESQL
# ==========================================
PG_HOST = os.getenv("PGDB_HOST", "localhost")
PG_PORT = os.getenv("PGDB_PORT", "5432")
PG_DB   = os.getenv("PGDB_NAME", "DRE_Database")
PG_USER = os.getenv("PGDB_USER", "postgres")
PG_PASS = os.getenv("PGDB_PASSWORD", "")
PG_DRIVER = os.getenv("PGDB_DRIVER", "psycopg")

# Codifica a senha para evitar erros com caracteres especiais
pg_pass_encoded = urllib.parse.quote_plus(PG_PASS)

PG_DATABASE_URL = f"postgresql+{PG_DRIVER}://{PG_USER}:{pg_pass_encoded}@{PG_HOST}:{PG_PORT}/{PG_DB}"


# ==========================================
# CONFIGURAÇÃO SQL SERVER
# ==========================================
SQL_HOST = os.getenv("SQLDB_HOST", "172.16.200.3")
SQL_PORT = os.getenv("SQLDB_PORT", "1433")
SQL_DB   = os.getenv("SQLDB_NAME", "luftinforma")
SQL_USER = os.getenv("SQLDB_USER", "user.services")
SQL_PASS = os.getenv("SQLDB_PASS", "")

# Codifica a senha (ESSENCIAL pois sua senha tem '#')
sql_pass_encoded = urllib.parse.quote_plus(SQL_PASS)

# Driver ODBC geralmente padrão. Se der erro, verifique se tem o 'ODBC Driver 17 for SQL Server' instalado
# ou mude para 'mssql+pymssql' se preferir não usar ODBC.
SQL_DATABASE_URL = (
    f"mssql+pyodbc://{SQL_USER}:{sql_pass_encoded}@{SQL_HOST}:{SQL_PORT}/{SQL_DB}"
    "?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes"
)

def get_postgres_engine():
    """Retorna a engine do PostgreSQL"""
    return create_engine(PG_DATABASE_URL, pool_pre_ping=True)

def get_sqlserver_engine():
    """Retorna a engine do SQL Server"""
    return create_engine(SQL_DATABASE_URL, pool_pre_ping=True)


# ==========================================
# TESTE DE CONEXÃO (EXECUÇÃO DIRETA)
# ==========================================
if __name__ == "__main__":
    print("\n--- INICIANDO TESTE DE CONEXÃO ---\n")

    # 1. Teste PostgreSQL
    print(f"Tentando conectar ao POSTGRESQL ({PG_HOST}:{PG_PORT})...")
    try:
        engine_pg = get_postgres_engine()
        with engine_pg.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            print(f"✅ [SUCESSO] PostgreSQL conectado! Resposta: {result}")
    except Exception as e:
        print(f"❌ [ERRO] Falha no PostgreSQL: {e}")

    print("-" * 30)

    # 2. Teste SQL Server
    print(f"Tentando conectar ao SQL SERVER ({SQL_HOST}:{SQL_PORT})...")
    try:
        engine_sql = get_sqlserver_engine()
        with engine_sql.connect() as conn:
            # 'SELECT 1' funciona em ambos
            result = conn.execute(text("SELECT 1")).scalar()
            print(f"✅ [SUCESSO] SQL Server conectado! Resposta: {result}")
    except Exception as e:
        print(f"❌ [ERRO] Falha no SQL Server: {e}")
        print("Dica: Verifique se o driver ODBC está instalado ou tente usar 'mssql+pymssql'.")

    print("\n--- FIM DO TESTE ---")