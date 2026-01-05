import sys
import os
from sqlalchemy import text

# Setup de diretórios
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Db.Connections import get_postgres_engine
from Models.POSTGRESS.Rentabilidade import Base

def criar_tabela():
    engine = get_postgres_engine()
    print("🛠️  Criando tabela Razao_Dados_Origem_INTEC...")
    
    # Cria todas as tabelas definidas no Base que ainda não existem
    # Como adicionamos RazaoOrigemINTEC no arquivo, ela será criada agora.
    Base.metadata.create_all(engine)
    
    print("✅ Tabela criada com sucesso!")

if __name__ == "__main__":
    criar_tabela()