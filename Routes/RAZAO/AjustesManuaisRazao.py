from flask import Blueprint, render_template, request
from flask_login import current_user, login_required
from sqlalchemy.orm import sessionmaker

# --- Conexões e Serviços ---
from Db.Connections import GetPostgresEngine
from Modules.RAZAO.Services.AjustesManuaisRazaoService import AjustesManuaisRazaoService
from Utils.Logger import RegistrarLog
from Modules.SISTEMA.Services.PermissaoService import RequerPermissao

# --- O Poder do LuftCore ---
from luftcore.extensions.flask_extension import (
    require_ajax,
    api_success,
    api_error
)

# Definindo a Blueprint
ajustes_manuais_razao_bp = Blueprint('AjustesManuaisRazao', __name__)

def GetSession():
    """Abre uma sessão novinha com o Postgres."""
    engine = GetPostgresEngine()
    return sessionmaker(bind=engine)()

@ajustes_manuais_razao_bp.route('/razao', methods=['GET'])
@login_required
@RequerPermissao('AJUSTES_MANUAIS_RAZAO.VISUALIZAR')
def Inicio():
    """Rota principal que entrega a página HTML."""
    user = current_user.nome
    RegistrarLog(f"Acesso à página de Ajustes do Razão. User: {user}", "HTTP")
    return render_template('Pages/Adjustments/LedgerAdjustments.html')

@ajustes_manuais_razao_bp.route('/api/gerar-intergrupo', methods=['POST'])
@login_required
@RequerPermissao('AJUSTES_MANUAIS_RAZAO.INTERGRUPO.SINCRONIZAR')
@require_ajax
def GerarIntergrupo():
    """
    Rota da API para processar e gerar os lançamentos de intergrupo.

    Retorno:
        Response: Objeto JSON contendo os dados gerados ou mensagem de erro estruturada.
    """
    session_db = GetSession()
    try:
        data = request.get_json()
        ano = int(data.get('ano'))
        mes = int(data.get('mes'))

        RegistrarLog(f"Iniciando chamada da rota GerarIntergrupo. Competência: {mes}/{ano}", "HTTP")

        svc = AjustesManuaisRazaoService(session_db)
        RegistrarLog("Instância de AjustesManuaisRazaoService criada. Chamando gerarIntergrupo.", "HTTP")

        # Chamada ao método em camelCase conforme padrão
        logs = svc.gerarIntergrupo(ano, mes)

        RegistrarLog("Processamento do serviço concluído. Realizando commit no banco.", "HTTP")
        session_db.commit()

        RegistrarLog(f"Commit realizado com sucesso. {len(logs)} logs retornados.", "HTTP")
        return api_success(data=logs, message=f"Intergrupo gerado com {len(logs)} lançamentos.")

    except Exception as e:
        RegistrarLog("Erro crítico na rota GerarIntergrupo", "ERROR", e)
        session_db.rollback()
        return api_error(message="Falha ao gerar lançamentos intergrupo.", details=str(e), status=500)
    finally:
        session_db.close()
        RegistrarLog("Sessão do banco de dados fechada na rota GerarIntergrupo.", "HTTP")

@ajustes_manuais_razao_bp.route('/api/razao/dados', methods=['GET'])
@login_required
@RequerPermissao('AJUSTES_MANUAIS_RAZAO.VISUALIZAR')
@require_ajax
def ObterDados():
    """Busca os dados para popular o grid."""
    session_db = GetSession()
    try:
        ano = request.args.get('ano')
        mes = request.args.get('mes')

        RegistrarLog(f"Rota API: GetDados (Grid) - Ano: {ano}, Mês: {mes}", "HTTP")

        svc = AjustesManuaisRazaoService(session_db)
        dados = svc.ObterDadosGrid(ano, mes)

        return api_success(data=dados, message="Grid carregado com sucesso.")
    except Exception as e:
        RegistrarLog("Erro API GetDados", "ERROR", e)
        return api_error(message="Falha ao carregar dados do grid.", details=str(e), status=500)
    finally:
        session_db.close()

@ajustes_manuais_razao_bp.route('/api/razao/criar', methods=['POST'])
@login_required
@RequerPermissao('AJUSTES_MANUAIS_RAZAO.CRIAR')
@require_ajax
def CriarAjuste():
    """Rota exclusiva para CRIAÇÃO de novos lançamentos manuais."""
    session_db = GetSession()
    try:
        user = current_user.nome
        RegistrarLog(f"Rota API: Criar Ajuste. User: {user}", "HTTP")

        svc = AjustesManuaisRazaoService(session_db)
        novo_id = svc.CriarAjusteManual(request.json, user)

        # Envia o ID no objeto data
        return api_success(data={'id': novo_id}, message='Lançamento manual criado com sucesso!')
    except Exception as e:
        RegistrarLog("Erro API Criar", "ERROR", e)
        session_db.rollback()
        return api_error(message="Erro ao criar o lançamento.", details=str(e), status=500)
    finally:
        session_db.close()

@ajustes_manuais_razao_bp.route('/api/razao/salvar', methods=['POST'])
@login_required
@RequerPermissao('AJUSTES_MANUAIS_RAZAO.EDITAR')
@require_ajax
def SalvarAjuste():
    """Salva ou edita um ajuste."""
    session_db = GetSession()
    try:
        user = current_user.nome
        RegistrarLog(f"Rota API: Salvar. User: {user}", "HTTP")

        svc = AjustesManuaisRazaoService(session_db)
        novo_id = svc.SalvarAjuste(request.json, user)

        return api_success(data={'id': novo_id}, message='Ajuste salvo com sucesso!')
    except Exception as e:
        RegistrarLog("Erro API Salvar", "ERROR", e)
        session_db.rollback()
        return api_error(message="Erro ao salvar as alterações.", details=str(e), status=500)
    finally:
        session_db.close()

@ajustes_manuais_razao_bp.route('/api/razao/aprovar', methods=['POST'])
@login_required
@RequerPermissao('AJUSTES_MANUAIS_RAZAO.APROVAR')
@require_ajax
def AprovarAjuste():
    session_db = GetSession()
    try:
        dt = request.json
        user = current_user.nome

        reg_id = dt.get('Id')
        reg_fonte = dt.get('Fonte')
        acao = dt.get('Acao')

        RegistrarLog(f"Rota API: Aprovar. User: {user}, ID: {reg_id}, Fonte: {reg_fonte}", "HTTP")

        svc = AjustesManuaisRazaoService(session_db)
        svc.AprovarAjuste(reg_id, reg_fonte, acao, user)

        return api_success(message=f"Lançamento {acao.lower()} com sucesso!")
    except Exception as e:
        RegistrarLog("Erro API Aprovar", "ERROR", e)
        return api_error(message="Falha na aprovação do ajuste.", details=str(e), status=500)
    finally:
        session_db.close()

@ajustes_manuais_razao_bp.route('/api/razao/status-invalido', methods=['POST'])
@login_required
@RequerPermissao('AJUSTES_MANUAIS_RAZAO.EDITAR')
@require_ajax
def AlterarStatusInvalido():
    session_db = GetSession()
    try:
        dt = request.json
        user = current_user.nome

        reg_id = dt.get('Id')
        reg_fonte = dt.get('Fonte')
        acao = dt.get('Acao')

        RegistrarLog(f"Rota API: Status Invalido. User: {user}, ID: {reg_id}", "HTTP")

        svc = AjustesManuaisRazaoService(session_db)
        svc.ToggleInvalido(reg_id, reg_fonte, acao, user)

        return api_success(message='Status de validade atualizado com sucesso!')
    except Exception as e:
        RegistrarLog("Erro API Status Invalido", "ERROR", e)
        session_db.rollback()
        return api_error(message="Erro ao invalidar o ajuste.", details=str(e), status=500)
    finally:
        session_db.close()

@ajustes_manuais_razao_bp.route('/api/razao/historico', methods=['GET'])
@login_required
@RequerPermissao('AJUSTES_MANUAIS_RAZAO.VISUALIZAR')
@require_ajax
def ObterHistorico():
    """Fofoca completa: mostra tudo o que aconteceu com aquele ajuste."""
    session_db = GetSession()
    try:
        reg_id = request.args.get('id')
        reg_fonte = request.args.get('fonte')
        user = current_user.nome

        RegistrarLog(f"Visualizando Histórico - Id: {reg_id} Fonte: {reg_fonte} User: {user}", "HTTP")

        svc = AjustesManuaisRazaoService(session_db)
        historico = svc.ObterHistorico(reg_id, reg_fonte)

        return api_success(data=historico, message="Histórico carregado.")
    except Exception as e:
        RegistrarLog("Erro API GetHistorico", "ERROR", e)
        return api_error(message="Não foi possível carregar o histórico.", details=str(e), status=500)
    finally:
        session_db.close()