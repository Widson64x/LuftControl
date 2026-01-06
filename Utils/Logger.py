import logging
import os
from datetime import datetime
from Settings import settings  # Importa as settings já carregadas

# Usamos as configs que vieram do Settings (seja Dev, Prod, etc.)
LOG_DIR = settings.FULL_LOG_PATH
ARQUIVO_HISTORICO = os.path.join(LOG_DIR, settings.LOG_FILE_HISTORY)
ARQUIVO_SESSAO = os.path.join(LOG_DIR, settings.LOG_FILE_SESSION)

def ConfigurarLogger():
    """
    Inicializa o sistema de logs.
    Cria a pasta e reseta o log da sessão atual.
    """
    if not os.path.exists(LOG_DIR):
        try:
            os.makedirs(LOG_DIR)
            print(f"📁 Pasta de Logs criada em: {LOG_DIR}")
        except Exception as e:
            print(f"❌ Erro ao criar pasta de logs: {e}")
            return

    # Limpa o arquivo de sessão (começa do zero)
    with open(ARQUIVO_SESSAO, 'w', encoding='utf-8') as f:
        f.write(f"--- Sessão Iniciada em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} ---\n")

    # Configura o Logger Principal
    logger = logging.getLogger('SistemaControladoria')
    logger.setLevel(logging.DEBUG) # Captura tudo, filtramos na chamada
    logger.handlers.clear()

    # Formatador simples: [DATA] Mensagem (O Tipo já virá na mensagem)
    formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%d/%m/%Y %H:%M:%S')

    # Handler 1: Histórico Geral (Append)
    h_history = logging.FileHandler(ARQUIVO_HISTORICO, mode='a', encoding='utf-8')
    h_history.setFormatter(formatter)
    logger.addHandler(h_history)

    # Handler 2: Sessão Atual (Append)
    h_session = logging.FileHandler(ARQUIVO_SESSAO, mode='a', encoding='utf-8')
    h_session.setFormatter(formatter)
    logger.addHandler(h_session)

    # Handler 3: Console
    h_console = logging.StreamHandler()
    h_console.setFormatter(formatter)
    logger.addHandler(h_console)

def RegistrarLog(mensagem, tipo="INFO", erro=None):
    """
    Registra um log no sistema.
    
    Args:
        mensagem (str): O texto do log.
        tipo (str): Categoria do log (Ex: 'System', 'Error', 'Warning', 'Database', 'Debug').
        erro (Exception, opcional): Objeto de erro para detalhar exceções.
    """
    logger = logging.getLogger('SistemaControladoria')
    
    tipo_upper = tipo.upper()
    
    # Formata a mensagem com o TIPO no início: [SYSTEM] Iniciando...
    msg_formatada = f"[{tipo_upper}] {mensagem}"
    
    if erro:
        msg_formatada += f" | 🔴 Erro Técnico: {str(erro)}"

    # Mapeamento para níveis do Python (logging.ERROR, logging.INFO, etc.)
    # Isso ajuda se um dia você quiser filtrar logs críticos
    if tipo_upper in ['ERROR', 'CRITICAL', 'ERRO', 'EXCEPTION']:
        logger.error(msg_formatada)
    elif tipo_upper in ['WARNING', 'WARN', 'AVISO']:
        logger.warning(msg_formatada)
    elif tipo_upper in ['DEBUG']:
        logger.debug(msg_formatada)
    else:
        # Qualquer outro tipo (System, Function, Database) entra como INFO
        logger.info(msg_formatada)