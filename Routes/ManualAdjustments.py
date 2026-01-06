from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user
from sqlalchemy.orm import sessionmaker
from Db.Connections import GetPostgresEngine
from Services.AdjustmentsService import AdjustmentService
from Utils.Logger import RegistrarLog

# Definindo a Blueprint (nossa área vip de rotas)
ajustes_bp = Blueprint('Ajustes', __name__)

def GetSession():
    """
    Abre uma sessão novinha com o Postgres.
    Lembre-se de fechar depois, hein!
    """
    engine = GetPostgresEngine()
    return sessionmaker(bind=engine)()

@ajustes_bp.route('/ajustes-razao', methods=['GET'])
def Index():
    """
    Rota principal que entrega a página HTML.
    Simples e direta.
    """
    user = current_user.nome if current_user.is_authenticated else 'Anonimo'
    RegistrarLog(f"Acesso à página de Ajustes. User: {user}", "HTTP")
    return render_template('PAGES/AjustesRazao.html')

@ajustes_bp.route('/api/gerar-intergrupo', methods=['POST'])
def GerarAjusteIntergrupo():
    """
    Essa aqui faz a mágica dos ajustes intergrupo.
    Pega o ano, chama o serviço e reza pra dar tudo certo.
    """
    session_db = GetSession()
    try:
        data = request.get_json()
        ano = int(data.get('ano'))
        
        RegistrarLog(f"Rota API: Gerar Intergrupo. Ano: {ano}", "HTTP")
        
        svc = AdjustmentService(session_db)
        
        # Manda bala na geração
        logs = svc.GerarIntergrupo(ano)
        
        return jsonify({'status': 'completed', 'logs': logs})
    except Exception as e:
        RegistrarLog("Erro API Gerar Intergrupo", "ERROR", e)
        # Deu ruim? Desfaz tudo!
        session_db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        # Fecha a porta ao sair
        session_db.close()

@ajustes_bp.route('/api/ajustes-razao/dados', methods=['GET'])
def GetDados():
    """
    Busca os dados para popular o grid.
    Mistura o que vem do ERP com os ajustes manuais.
    """
    session_db = GetSession()
    try:
        RegistrarLog("Rota API: GetDados (Grid)", "HTTP")
        svc = AdjustmentService(session_db)
        dados = svc.ObterDadosGrid()
        return jsonify(dados)
    except Exception as e:
        RegistrarLog("Erro API GetDados", "ERROR", e)
        import traceback
        traceback.print_exc() # Printando pra saber onde o bicho pegou
        return jsonify({'error': str(e)}), 500
    finally:
        session_db.close()

@ajustes_bp.route('/api/ajustes-razao/salvar', methods=['POST'])
def Salvar():
    """
    Salva ou edita um ajuste.
    Se o usuário não estiver logado, culpa o 'System'.
    """
    session_db = GetSession()
    try:
        user = current_user.nome if current_user.is_authenticated else 'System'
        RegistrarLog(f"Rota API: Salvar. User: {user}", "HTTP")
        
        svc = AdjustmentService(session_db)
        
        # Chama o serviço pra persistir a alteração
        novo_id = svc.SalvarAjuste(request.json, user)
        
        return jsonify({'msg': 'Salvo', 'id': novo_id})
    except Exception as e:
        RegistrarLog("Erro API Salvar", "ERROR", e)
        session_db.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session_db.close()

@ajustes_bp.route('/api/ajustes-razao/aprovar', methods=['POST'])
def Aprovar():
    """
    Aprova ou Reprova um ajuste.
    O destino do lançamento está nestas mãos.
    """
    session_db = GetSession()
    try:
        dt = request.json
        user = current_user.nome if current_user.is_authenticated else 'System'
        RegistrarLog(f"Rota API: Aprovar. User: {user}, ID: {dt.get('Ajuste_ID')}", "HTTP")
        
        svc = AdjustmentService(session_db)
        
        svc.AprovarAjuste(dt.get('Ajuste_ID'), dt.get('Acao'), user)
        
        return jsonify({'msg': 'OK'})
    except Exception as e:
        RegistrarLog("Erro API Aprovar", "ERROR", e)
        return jsonify({'error': str(e)}), 500
    finally:
        session_db.close()

@ajustes_bp.route('/api/ajustes-razao/status-invalido', methods=['POST'])
def AlterarStatusInvalido():
    """
    Alterna o status de 'Inválido'.
    Basicamente um soft-delete ou soft-undelete.
    """
    session_db = GetSession()
    try:
        dt = request.json
        user = current_user.nome if current_user.is_authenticated else 'System'
        RegistrarLog(f"Rota API: Status Invalido. User: {user}, ID: {dt.get('Ajuste_ID')}", "HTTP")
        
        svc = AdjustmentService(session_db)
        
        svc.ToggleInvalido(dt.get('Ajuste_ID'), dt.get('Acao'), user)
        
        return jsonify({'msg': 'Status atualizado com sucesso'})
    except Exception as e:
        RegistrarLog("Erro API Status Invalido", "ERROR", e)
        session_db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session_db.close()

@ajustes_bp.route('/api/ajustes-razao/historico/<int:id_ajuste>', methods=['GET'])
def GetHistorico(id_ajuste):
    """
    Fofoca completa: mostra tudo o que aconteceu com aquele ajuste.
    Quem mudou, quando e o quê.
    """
    session_db = GetSession()
    try:
        RegistrarLog(f"Rota API: Historico. ID: {id_ajuste}", "HTTP")
        svc = AdjustmentService(session_db)
        historico = svc.ObterHistorico(id_ajuste)
        return jsonify(historico)
    except Exception as e:
        RegistrarLog("Erro API Historico", "ERROR", e)
        return jsonify({'error': str(e)}), 500
    finally:
        session_db.close()