import os
import urllib.parse
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

class BaseConfig:
    """Configurações Base (Comuns a todos os ambientes)"""
    
    # Postgres
    PG_HOST = os.getenv("PGDB_HOST", "localhost")
    PG_PORT = os.getenv("PGDB_PORT", "5432")
    PG_USER = os.getenv("PGDB_USER", "postgres")
    PG_PASS = os.getenv("PGDB_PASSWORD", "")
    PG_DRIVER = os.getenv("PGDB_DRIVER", "psycopg")
    
    # SQL Server (Não muda entre ambientes conforme seu requisito, mas poderia)
    SQL_HOST = os.getenv("SQLDB_HOST")
    SQL_PORT = os.getenv("SQLDB_PORT", "1433")
    SQL_DB   = os.getenv("SQLDB_NAME")
    SQL_USER = os.getenv("SQLDB_USER")
    SQL_PASS = os.getenv("SQLDB_PASS")
    
    # Outras Configs
    SECRET_KEY = os.getenv("SECRET_PASSPHRASE")
    LDAP_SERVER = os.getenv("LDAP_SERVER")
    SHOW_DB_LOGS = os.getenv("DB_CONNECT_LOGS", "True").lower() == "true"

    def get_postgres_uri(self):
        """Gera a URI de conexão do Postgres baseada na classe atual"""
        pass_encoded = urllib.parse.quote_plus(self.PG_PASS)
        # O self.PG_DB virá da classe filha
        return f"postgresql+{self.PG_DRIVER}://{self.PG_USER}:{pass_encoded}@{self.PG_HOST}:{self.PG_PORT}/{self.PG_DB}"

    def get_sqlserver_uri(self):
        """Gera a URI de conexão do SQL Server"""
        pass_encoded = urllib.parse.quote_plus(self.SQL_PASS)
        return (
            f"mssql+pyodbc://{self.SQL_USER}:{pass_encoded}@{self.SQL_HOST}:{self.SQL_PORT}/{self.SQL_DB}"
            "?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes"
        )

class DevelopmentConfig(BaseConfig):
    """Ambiente de Desenvolvimento"""
    # Pode pegar do env ou fixar string 'DRE_Controladoria_DEV'
    PG_DB = os.getenv("PGDB_NAME_DEV", "DRE_Controladoria_DEV")
    DEBUG = False

class HomologationConfig(BaseConfig):
    """Ambiente de Homologação"""
    PG_DB = os.getenv("PGDB_NAME_HOMOLOG", "DRE_Controladoria_HML")
    DEBUG = False

class ProductionConfig(BaseConfig):
    """Ambiente de Produção"""
    PG_DB = os.getenv("PGDB_NAME_PROD", "DRE_Controladoria")
    DEBUG = False

# Dicionário para mapear a string do .env para a Classe
config_map = {
    "development": DevelopmentConfig,
    "homologation": HomologationConfig,
    "production": ProductionConfig
}

# Lógica para instanciar a configuração correta
env_name = os.getenv("APP_ENV", "development").lower()
settings = config_map.get(env_name, DevelopmentConfig)()

# Apenas para debug visual ao iniciar
print(f"🔧 Settings carregado no modo: {env_name.upper()}")
print(f"📂 Banco Postgres Alvo: {settings.PG_DB}")