import sys
import os

# Adiciona o diretório raiz ao path para conseguir importar os módulos do projeto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Db.Connections import GetPostgresEngine
from Models.POSTGRESS.ImportHistory import Base

def criar_tabelas_importacao():
    engine = GetPostgresEngine()
    print("🛠️  Conectando ao banco de dados...")
    
    # O create_all verifica se a tabela existe no Schema. Se não existir, cria.
    print("⏳ Verificando/Criando tabela 'System_Import_History'...")
    Base.metadata.create_all(engine)
    
    print("✅ Tabela de Histórico criada com sucesso!")

if __name__ == "__main__":
    criar_tabelas_importacao()