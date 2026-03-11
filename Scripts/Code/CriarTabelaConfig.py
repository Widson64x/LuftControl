import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Db.Connections import GetPostgresEngine
from Models.Postgress.ImportConfig import Base

def criar_tabela_config():
    engine = GetPostgresEngine()
    print("🛠️  Criando tabela 'System_Import_Config'...")
    Base.metadata.create_all(engine)
    print("✅ Tabela de Configuração criada com sucesso!")

if __name__ == "__main__":
    criar_tabela_config()