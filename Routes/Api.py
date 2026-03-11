# Routes/Api.py
from flask import Blueprint, jsonify
from sqlalchemy.orm import sessionmaker
from Db.Connections import GetPostgresEngine
from Services.SyncService import SyncService

api_bp = Blueprint('Api', __name__)

def GetSession():
    engine = GetPostgresEngine()
    return sessionmaker(bind=engine)()

# Mudamos aqui para não ficar /Api/api/...
@api_bp.route('/sincronizar-consolidado', methods=['POST'])
def SincronizarConsolidado():
    """
    Rota invisível para o utilizador, chamada em background a cada 10 segundos
    para manter os dados perfeitamente sincronizados.
    """
    session_db = GetSession()
    try:
        servico = SyncService(session_db)
        servico.SincronizarDados()
        return jsonify({'status': 'success', 'msg': 'Sincronização concluída com sucesso!'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500
    finally:
        session_db.close()