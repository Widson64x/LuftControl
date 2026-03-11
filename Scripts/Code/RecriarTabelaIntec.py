import sys
import os
from sqlalchemy import text

# Setup de diretórios
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Db.Connections import GetPostgresEngine
from Models.Postgress.Rentabilidade import Base

def recriar_tabela():
    engine = GetPostgresEngine()
    
    print("🔥 Excluindo tabela antiga Razao_Dados_Origem_INTEC...")
    with engine.connect() as conn:
        conn.execute(text('DROP TABLE IF EXISTS "Dre_Schema"."Razao_Dados_Origem_INTEC" CASCADE;'))
        conn.commit()
    
    print("🛠️  Criando nova tabela com ID...")
    # Cria apenas as tabelas que não existem (como acabamos de dropar, ela será criada)
    Base.metadata.create_all(engine)
    
    print("✅ Tabela recriada com sucesso! Agora suporta duplicatas de chave.")

if __name__ == "__main__":
    recriar_tabela()