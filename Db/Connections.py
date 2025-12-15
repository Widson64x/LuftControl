import sys
import os
import time
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

# ==========================================
# SETUP (Settings da Raiz)
# ==========================================
# Garante que conseguimos importar o Settings.py da pasta acima
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Settings import settings, ProductionConfig

# ==========================================
# VARIÁVEIS DE URL (Globais)
# ==========================================
PG_DATABASE_URL = settings.get_postgres_uri()
SQL_DATABASE_URL = settings.get_sqlserver_uri()

# ==========================================
# FUNÇÕES DE ENGINE (Core)
# ==========================================

def get_postgres_engine():
    """
    Retorna a engine do PostgreSQL com suporte a Fallback (Segurança).
    Se o ambiente de DEV/HOMOLOG falhar, tenta conectar em PRODUÇÃO.
    """
    # 1. Tenta conectar na URL configurada (Dev ou Homolog)
    try:
        # pool_pre_ping=True ajuda a evitar conexões "fantasmas"
        engine = create_engine(PG_DATABASE_URL, pool_pre_ping=True, echo=settings.DEBUG) # Debugar a conexão se DEBUG=True
        return engine
    except Exception:
        # Se falhar a criação da engine inicial (raro, geralmente falha na conexão)
        return None

def get_postgres_engine_robust():
    """
    Versão interna que tenta conectar e, se falhar, busca a Produção.
    Usada internamente pelas funções de conexão e check.
    """
    # Tenta engine padrão
    engine = create_engine(PG_DATABASE_URL, pool_pre_ping=True, echo=False)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine, settings.PG_DB, False # False = Não é fallback
    except Exception:
        # Se falhar e NÃO for produção, tenta fallback
        if settings.PG_DB != ProductionConfig.PG_DB:
            prod_config = ProductionConfig()
            prod_url = prod_config.get_postgres_uri()
            fallback_engine = create_engine(prod_url, pool_pre_ping=True, echo=False)
            try:
                with fallback_engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return fallback_engine, prod_config.PG_DB, True # True = É fallback
            except Exception:
                pass
    return None, None, False

def get_sqlserver_engine():
    """Retorna a engine do SQL Server"""
    return create_engine(SQL_DATABASE_URL, pool_pre_ping=True, poolclass=NullPool)

# ==========================================
# NOVA FUNÇÃO DE DIAGNÓSTICO (O que você pediu)
# ==========================================

def check_connections(verbose=None):
    """
    Testa as conexões.
    Se verbose for None, usa a configuração do Settings.
    """
    # Lógica: Se o programador não passou True/False manualmente, 
    # pega o valor do arquivo .env (via settings)
    if verbose is None:
        verbose = settings.SHOW_DB_LOGS

    if verbose:
        print("\n" + "="*50)
        print(f"🛠️  DIAGNÓSTICO DE AMBIENTE: {os.getenv('APP_ENV', 'DEV').upper()}")
        print("="*50)

    # --- 1. TESTE POSTGRESQL ---
    t0 = time.time()
    pg_engine, db_name, is_fallback = get_postgres_engine_robust()
    pg_ms = (time.time() - t0) * 1000

    pg_status = False
    if pg_engine:
        pg_status = True
        if verbose:
            status_icon = "✅ [ONLINE]"
            fallback_msg = "🚨 (MODO FALLBACK)" if is_fallback else ""
            print(f"🐘 POSTGRESQL {status_icon} {fallback_msg}")
            print(f"   ├─ Host: {settings.PG_HOST}")
            print(f"   ├─ Base: {db_name}")
            print(f"   └─ ⏱️  Latência: {pg_ms:.2f} ms")
    else:
        if verbose:
            print(f"🐘 POSTGRESQL ❌ [OFFLINE]")
            print(f"   └─ ⚠️  Não foi possível conectar em DEV nem em PROD.")

    if verbose: print("-" * 30)

    # --- 2. TESTE SQL SERVER ---
    t0 = time.time()
    sql_status = False
    try:
        sql_engine = get_sqlserver_engine()
        with sql_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        sql_ms = (time.time() - t0) * 1000
        sql_status = True
        
        if verbose:
            print(f"🗄️  SQL SERVER ✅ [ONLINE]")
            print(f"   ├─ Host: {settings.SQL_HOST}")
            print(f"   ├─ Base: {settings.SQL_DB}")
            print(f"   └─ ⏱️  Latência: {sql_ms:.2f} ms")
    except Exception as e:
        if verbose:
            print(f"🗄️  SQL SERVER ❌ [OFFLINE]")
            print(f"   └─ ⚠️  Erro: {str(e).splitlines()[0]}")

    if verbose:
        print("="*50 + "\n")

    # Retorna True apenas se AMBOS estiverem conectados (ajuste conforme necessidade)
    return pg_status and sql_status