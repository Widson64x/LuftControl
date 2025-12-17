import sys
import os
from sqlalchemy import text

# Setup de diretórios
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Db.Connections import get_postgres_engine

def corrigir_tabelas():
    engine = get_postgres_engine()
    print("🛠️  Iniciando correção das tabelas de origem...")

    # Lista de tabelas para corrigir (Drop e Create com Varchars)
    sqls = [
        # 1. Drop da tabela errada (se existir)
        'DROP TABLE IF EXISTS "Dre_Schema"."Razao_Dados_Origem_INTEC";',
        
        # 2. Recriação com a tipagem correta (VARCHAR para códigos)
        """
        CREATE TABLE "Dre_Schema"."Razao_Dados_Origem_INTEC" (
            "Conta" VARCHAR(50),
            "Título Conta" VARCHAR(255),
            "Data" TIMESTAMP,
            "Numero" VARCHAR(50),
            "Descricao" TEXT,
            "Contra Partida - Credito" VARCHAR(50),
            "Filial" VARCHAR(50),
            "Centro de Custo" VARCHAR(50),
            "Item" VARCHAR(50),
            "Cod Cl. Valor" VARCHAR(50),
            "Debito" NUMERIC(18, 4) DEFAULT 0,
            "Credito" NUMERIC(18, 4) DEFAULT 0
        );
        """
    ]
    
    with engine.begin() as conn:
        for sql in sqls:
            print(f"Executando: {sql.strip().splitlines()[0]}...")
            conn.execute(text(sql))
            
    print("✅ Tabela Razao_Dados_Origem_INTEC recriada com colunas VARCHAR!")
    print("   -> Agora suporta códigos como '2.1.1.01' e '005'.")

if __name__ == "__main__":
    corrigir_tabelas()