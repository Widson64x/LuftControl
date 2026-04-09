# Routes/Api.py
from flask import Blueprint, jsonify
from sqlalchemy.orm import sessionmaker
from Db.Connections import GetPostgresEngine
from Modules.DRE.Services.SyncService import SyncService
from flask_login import login_required
from Modules.DRE.Services.PermissaoService import RequerPermissao
from luftcore.extensions.flask_extension import require_ajax

api_bp = Blueprint('Api', __name__)

def GetSession():
    engine = GetPostgresEngine()
    return sessionmaker(bind=engine)()

@api_bp.route('/sincronizar-consolidado', methods=['POST'])
@login_required
#@RequerPermissao('API.CONSOLIDAR.SINCRONIZAR')
# Enquanto eu não descobrir uma forma de não gerar LOG para esta rota, vou deixar a permissão comentada, 
# para evitar que o LOG fique poluído com mensagens de sincronização.
@require_ajax
def SincronizarConsolidado():
    """
    Rota invisível para o utilizador, chamada em background a cada 10 segundos
    para manter os dados perfeitamente sincronizados.
    """
    session_db = GetSession()
    try:
        servico = SyncService(session_db)
        servico.sincronizarDados()
        return jsonify({'status': 'success', 'msg': 'Sincronização concluída com sucesso!'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500
    finally:
        session_db.close()