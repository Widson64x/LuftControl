"""
Script para verificar tabelas e VIEWS existentes no banco PostgreSQL
"""
import os
import sys

# Ajusta o path para importar módulos do projeto
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Db.Connections import get_postgres_engine
from sqlalchemy import text

def verificar_banco():
    """Verifica tabelas e views no PostgreSQL"""
    print("\n" + "="*70)
    print("VERIFICANDO TABELAS E VIEWS NO POSTGRESQL")
    print("="*70 + "\n")
    
    try:
        engine = get_postgres_engine()
        
        with engine.connect() as conn:
            # Verifica TABELAS
            print("📊 TABELAS:")
            query_tabelas = text("""
                SELECT 
                    schemaname,
                    tablename
                FROM pg_tables
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                ORDER BY tablename
            """)
            
            result = conn.execute(query_tabelas)
            tabelas = result.fetchall()
            
            if not tabelas:
                print("   ⚠️  Nenhuma tabela encontrada!\n")
            else:
                for schema, nome in tabelas:
                    print(f"   ✓ {schema}.{nome}")
                print(f"\n   Total: {len(tabelas)} tabelas\n")
            
            print("-"*70)
            
            # Verifica VIEWS
            print("\n👁️  VIEWS:")
            query_views = text("""
                SELECT 
                    schemaname,
                    viewname
                FROM pg_views
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                ORDER BY viewname
            """)
            
            result = conn.execute(query_views)
            views = result.fetchall()
            
            if not views:
                print("   ⚠️  Nenhuma view encontrada!\n")
            else:
                for schema, nome in views:
                    print(f"   ✓ {schema}.{nome}")
                print(f"\n   Total: {len(views)} views\n")
            
            print("-"*70)
            
            # Procura especificamente pelas tabelas/views do DRE
            print("\n🔍 PROCURANDO OBJETOS RELACIONADOS AO DRE:")
            query_dre = text("""
                SELECT 
                    'TABLE' as tipo,
                    schemaname as schema,
                    tablename as nome
                FROM pg_tables
                WHERE tablename ILIKE '%razao%' OR tablename ILIKE '%dre%'
                UNION
                SELECT 
                    'VIEW' as tipo,
                    schemaname as schema,
                    viewname as nome
                FROM pg_views
                WHERE viewname ILIKE '%razao%' OR viewname ILIKE '%dre%'
                ORDER BY tipo, nome
            """)
            
            result = conn.execute(query_dre)
            objetos_dre = result.fetchall()
            
            if not objetos_dre:
                print("   ⚠️  Nenhum objeto encontrado com 'razao' ou 'dre' no nome!\n")
            else:
                for tipo, schema, nome in objetos_dre:
                    print(f"   {tipo:6} | {schema}.{nome}")
                print(f"\n   Total: {len(objetos_dre)} objetos relacionados\n")
        
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}\n")

if __name__ == "__main__":
    verificar_banco()