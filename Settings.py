import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

class LogConfig:
    """Classe específica para configurações de Log"""
    # Define caminhos
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    LOG_DIR_NAME = os.getenv("LOG_DIRECTORY", "Logs")
    
    # Caminho Completo da Pasta
    FULL_LOG_PATH = os.path.join(BASE_DIR, LOG_DIR_NAME)
    
    # Nomes dos Arquivos
    LOG_FILE_HISTORY = os.getenv("LOG_FILENAME_HISTORY", "Historico_Geral.log")
    LOG_FILE_SESSION = os.getenv("LOG_FILENAME_SESSION", "Sessao_Atual.log")

class BaseConfig:
    """Configurações Base (Banco de Dados, Secrets, etc)"""
    
    # Postgres
    PG_HOST = os.getenv("PGDB_HOST", "localhost")
    PG_PORT = os.getenv("PGDB_PORT", "5432")
    PG_USER = os.getenv("PGDB_USER", "postgres")
    PG_PASS = os.getenv("PGDB_PASSWORD", "")
    PG_DRIVER = os.getenv("PGDB_DRIVER", "psycopg")
    
    # SQL Server
    SQL_HOST = os.getenv("SQLDB_HOST")
    SQL_PORT = os.getenv("SQLDB_PORT", "1433")
    SQL_DB   = os.getenv("SQLDB_NAME")
    SQL_USER = os.getenv("SQLDB_USER")
    SQL_PASS = os.getenv("SQLDB_PASS")
    
    # Outras Configs
    SECRET_KEY = os.getenv("SECRET_PASSPHRASE")
    LDAP_SERVER = os.getenv("LDAP_SERVER")
    SHOW_DB_LOGS = os.getenv("DB_CONNECT_LOGS", "True").lower() == "true"

    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "9009"))

    def get_postgres_uri(self):
        pass_encoded = urllib.parse.quote_plus(self.PG_PASS)
        return f"postgresql+{self.PG_DRIVER}://{self.PG_USER}:{pass_encoded}@{self.PG_HOST}:{self.PG_PORT}/{self.PG_DB}"

    def get_sqlserver_uri(self):
        pass_encoded = urllib.parse.quote_plus(self.SQL_PASS)
        return (
            f"mssql+pyodbc://{self.SQL_USER}:{pass_encoded}@{self.SQL_HOST}:{self.SQL_PORT}/{self.SQL_DB}"
            "?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes"
        )

    def DataQVDPath(self):
        """Retorna o caminho base para os arquivos QVD"""
        BASEDIR = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(BASEDIR, "Data", "Fat_QVD")
    
# --- Ambientes (Herdam BaseConfig E LogConfig) ---

class DevelopmentConfig(BaseConfig, LogConfig):
    """Ambiente de Desenvolvimento"""
    PG_DB = os.getenv("PGDB_NAME_DEV", "DRE_Controladoria_DEV")
    DEBUG = False

class HomologationConfig(BaseConfig, LogConfig):
    """Ambiente de Homologação"""
    PG_DB = os.getenv("PGDB_NAME_HOMOLOG", "DRE_Controladoria_HML")
    DEBUG = False

class ProductionConfig(BaseConfig, LogConfig):
    """Ambiente de Produção"""
    PG_DB = os.getenv("PGDB_NAME_PROD", "DRE_Controladoria")
    DEBUG = False

# Config Map
config_map = {
    "development": DevelopmentConfig,
    "homologation": HomologationConfig,
    "production": ProductionConfig
}

env_name = os.getenv("APP_ENV", "development").lower()
settings = config_map.get(env_name, DevelopmentConfig)()

print(f"🔧 Settings carregado no modo: {env_name.upper()}")
print(f"📂 Banco Postgres Alvo: {settings.PG_DB}")
print(f"📝 Diretório de Logs: {settings.FULL_LOG_PATH}")