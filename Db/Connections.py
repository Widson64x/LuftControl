import sys
import os
import time
from decimal import Decimal, InvalidOperation

from sqlalchemy import create_engine, event, or_, text
from sqlalchemy.orm import Session, sessionmaker, with_loader_criteria
from sqlalchemy.pool import NullPool

# ==========================================
# SETUP (Settings da Raiz)
# ==========================================
# Adiciona o diretório pai ao path para conseguir importar o arquivo Settings.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Settings import settings, ProductionConfig

# ==========================================
# VARIÁVEIS DE URL (Globais)
# ==========================================
# Carregamos as strings de conexão logo de cara para não ter surpresa depois
PG_DATABASE_URL = settings.get_postgres_uri()
SQL_DATABASE_URL = settings.get_sqlserver_uri()


class SqlServerSession(Session):
    pass


def _obter_codigos_centros_off():
    try:
        from Modules.SISTEMA.Services.CentroCustoConfigService import CentroCustoConfigService

        codigos = CentroCustoConfigService.listarCodigosCentrosOff()
    except Exception:
        return ()

    codigos_normalizados = []
    for codigo in codigos:
        try:
            codigos_normalizados.append(Decimal(str(codigo).strip()))
        except (InvalidOperation, TypeError, ValueError):
            continue

    return tuple(codigos_normalizados)


@event.listens_for(SqlServerSession, 'do_orm_execute')
def _aplicar_filtro_centros_off(execute_state):
    if not execute_state.is_select:
        return

    if execute_state.session.info.get('ignore_centro_custo_off'):
        return

    codigos_off = _obter_codigos_centros_off()
    if not codigos_off:
        return

    from Models.SqlServer.Budget import BudgetItem
    from Models.SqlServer.ContaPagar import CentroCusto, ContaPagar

    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            CentroCusto,
            lambda cls: cls.Codigo_CentroCusto.notin_(codigos_off),
            include_aliases=True,
        ),
        with_loader_criteria(
            BudgetItem,
            lambda cls: or_(
                cls.Codigo_CentroCusto.is_(None),
                cls.Codigo_CentroCusto.notin_(codigos_off),
            ),
            include_aliases=True,
        ),
        with_loader_criteria(
            ContaPagar,
            lambda cls: or_(
                cls.Codigo_CentroCusto.is_(None),
                cls.Codigo_CentroCusto.notin_(codigos_off),
            ),
            include_aliases=True,
        ),
    )

# ==========================================
# FUNÇÕES DE ENGINE E SESSÃO (Core)
# ==========================================

def GetPostgresEngine():
    """
    Retorna a engine do PostgreSQL padrão.
    Utiliza 'pool_pre_ping' para verificar se a conexão está viva antes de usar.
    """
    try:
        # pool_pre_ping=True é o 'ping' cardíaco da conexão. Evita erros de "server closed connection unexpectedly".
        engine = create_engine(PG_DATABASE_URL, pool_pre_ping=True, echo=settings.DEBUG) 
        return engine
    except Exception as e:
        print(f"Erro ao criar engine Postgres: {e}")
        return None

def GetPostgresSession():
    """Retorna uma Sessão ORM pronta para o PostgreSQL"""
    engine = GetPostgresEngine()
    if engine:
        return sessionmaker(bind=engine)()
    return None

def GetPostgresEngineRobust():
    """
    Versão 'Blindada' da conexão Postgres.
    Lógica: Tenta conectar no ambiente configurado (DEV/HOMOLOG).
    Se falhar, tenta conectar automaticamente na PRODUÇÃO (Fallback) para leitura.
    
    Retorna: (engine, nome_do_banco, is_fallback)
    """
    # 1. Tentativa Principal (O que está no .env)
    engine = create_engine(PG_DATABASE_URL, pool_pre_ping=True, echo=False)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1")) # Teste real de conexão
        return engine, settings.PG_DB, False # False = Conexão normal, não é fallback
    except Exception:
        # 2. Plano B (Fallback)
        # Se falhou e a gente NÃO estava tentando conectar na produção...
        if settings.PG_DB != ProductionConfig.PG_DB:
            prod_config = ProductionConfig()
            prod_url = prod_config.get_postgres_uri()
            
            fallback_engine = create_engine(prod_url, pool_pre_ping=True, echo=False)
            try:
                with fallback_engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                # Retorna a engine de produção, mas avisa que é fallback (True)
                return fallback_engine, prod_config.PG_DB, True 
            except Exception:
                pass # Se falhou na produção também, aí não tem jeito.
                
    return None, None, False

def GetSqlServerEngine():
    """
    Retorna a engine do SQL Server (Legado/ERP).
    Usa NullPool porque o SQL Server gerencia conexões de forma diferente e 
    queremos fechar a conexão explicitamente após o uso para não travar o ERP.
    """
    return create_engine(SQL_DATABASE_URL, pool_pre_ping=True, poolclass=NullPool)

def GetSqlServerSession(ignore_centro_custo_off=False):
    """Retorna uma Sessão ORM pronta para o SQL Server (LuftInforma)"""
    engine = GetSqlServerEngine()
    sessao = sessionmaker(bind=engine, class_=SqlServerSession)()
    if ignore_centro_custo_off:
        sessao.info['ignore_centro_custo_off'] = True
    return sessao

# ==========================================
# FUNÇÃO DE DIAGNÓSTICO
# ==========================================

def CheckConnections(verbose=None):
    """
    Check-up Geral: Testa se os bancos estão respondendo e mede a latência.
    Usado na inicialização do App.py para garantir que o sistema pode subir.
    
    Args:
        verbose (bool): Se True, imprime o relatório bonitinho no terminal.
    """
    # Se não passar nada, olha no .env se o usuário quer ver logs (SHOW_DB_LOGS)
    if verbose is None:
        verbose = settings.SHOW_DB_LOGS

    if verbose:
        print("\n" + "="*50)
        print(f"🛠️  DIAGNÓSTICO DE AMBIENTE: {os.getenv('APP_ENV', 'DEV').upper()}")
        print("="*50)

    # --- 1. TESTE POSTGRESQL (Dados do Sistema/Logs) ---
    t0 = time.time()
    # Usa a versão robusta para ver se caiu no Fallback
    pg_engine, db_name, is_fallback = GetPostgresEngineRobust()
    pg_ms = (time.time() - t0) * 1000

    pg_status = False
    if pg_engine:
        pg_status = True
        if verbose:
            status_icon = "✅ [ONLINE]"
            fallback_msg = "🚨 (MODO FALLBACK - USANDO PROD)" if is_fallback else ""
            print(f"🐘 POSTGRESQL {status_icon} {fallback_msg}")
            print(f"   ├─ Host: {settings.PG_HOST}")
            print(f"   ├─ Base: {db_name}")
            print(f"   └─ ⏱️  Latência: {pg_ms:.2f} ms")
    else:
        if verbose:
            print(f"🐘 POSTGRESQL ❌ [OFFLINE]")
            print(f"   └─ ⚠️  CRÍTICO: Não foi possível conectar em DEV nem em PROD.")

    if verbose: print("-" * 30)

    # --- 2. TESTE SQL SERVER (ERP/Dados de Negócio) ---
    t0 = time.time()
    sql_status = False
    try:
        sql_engine = GetSqlServerEngine()
        with sql_engine.connect() as conn:
            conn.execute(text("SELECT 1")) # Query leve só pra testar
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
            # Pega só a primeira linha do erro pra não poluir o terminal
            erro_resumido = str(e).splitlines()[0] if str(e) else "Erro desconhecido"
            print(f"   └─ ⚠️  Erro: {erro_resumido}")

    if verbose:
        print("="*50 + "\n")

    # O sistema só está saudável se AMBOS os bancos estiverem online
    return pg_status and sql_status