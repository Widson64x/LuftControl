from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user
from sqlalchemy.orm import sessionmaker
from Db.Connections import get_postgres_engine
from Modules.AjustesManuais.Service import AdjustmentService

ajustes_bp = Blueprint('Ajustes', __name__)

def get_session():
    engine = get_postgres_engine()
    return sessionmaker(bind=engine)()

@ajustes_bp.route('/ajustes-razao', methods=['GET'])
def index():
    return render_template('MENUS/AjustesRazao.html')

@ajustes_bp.route('/api/gerar-intergrupo', methods=['POST'])
def gerar_ajuste_intergrupo():
    session_db = get_session()
    try:
        svc = AdjustmentService(session_db)
        data = request.get_json()
        ano = int(data.get('ano'))
        
        logs = svc.gerar_intergrupo(ano)
        
        return jsonify({'status': 'completed', 'logs': logs})
    except Exception as e:
        session_db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session_db.close()

@ajustes_bp.route('/api/ajustes-razao/dados', methods=['GET'])
def get_dados():
    session_db = get_session()
    try:
        svc = AdjustmentService(session_db)
        dados = svc.obter_dados_grid()
        return jsonify(dados)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session_db.close()

@ajustes_bp.route('/api/ajustes-razao/salvar', methods=['POST'])
def salvar():
    session_db = get_session()
    try:
        svc = AdjustmentService(session_db)
        user = current_user.nome if current_user.is_authenticated else 'System'
        
        novo_id = svc.salvar_ajuste(request.json, user)
        
        return jsonify({'msg': 'Salvo', 'id': novo_id})
    except Exception as e:
        session_db.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session_db.close()

@ajustes_bp.route('/api/ajustes-razao/aprovar', methods=['POST'])
def aprovar():
    session_db = get_session()
    try:
        svc = AdjustmentService(session_db)
        dt = request.json
        user = current_user.nome if current_user.is_authenticated else 'System'
        
        svc.aprovar_ajuste(dt.get('Ajuste_ID'), dt.get('Acao'), user)
        
        return jsonify({'msg': 'OK'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session_db.close()

@ajustes_bp.route('/api/ajustes-razao/status-invalido', methods=['POST'])
def alterar_status_invalido():
    session_db = get_session()
    try:
        svc = AdjustmentService(session_db)
        dt = request.json
        user = current_user.nome if current_user.is_authenticated else 'System'
        
        svc.toggle_invalido(dt.get('Ajuste_ID'), dt.get('Acao'), user)
        
        return jsonify({'msg': 'Status atualizado com sucesso'})
    except Exception as e:
        session_db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session_db.close()

@ajustes_bp.route('/api/ajustes-razao/historico/<int:id_ajuste>', methods=['GET'])
def get_historico(id_ajuste):
    session_db = get_session()
    try:
        svc = AdjustmentService(session_db)
        historico = svc.obter_historico(id_ajuste)
        return jsonify(historico)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session_db.close()