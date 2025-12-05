"""
Routes/Reports.py
Rotas para Relatórios de Rentabilidade e Razão Contábil
VERSÃO CORRIGIDA - Consulta SQL dinâmica para evitar problemas de mapeamento ORM
"""

from flask import Blueprint, jsonify, request, current_app, abort, render_template
from flask_login import login_required 
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func, or_, String, text
import json


from Db.Connections import get_postgres_engine
from Helpers.Security import requires_permission
from Services.DreService import DreService

reports_bp = Blueprint('Reports', __name__) 


def get_pg_session():
    """Cria e retorna uma sessão do PostgreSQL"""
    engine = get_postgres_engine()
    Session = sessionmaker(bind=engine)
    return Session()


@reports_bp.route('/', methods=['GET']) 
@login_required 
def PaginaRelatorios():
    """Renderiza a página principal de relatórios"""
    return render_template('MENUS/Relatórios.html')


@reports_bp.route('/RelatorioRazao/Dados', methods=['GET']) 
@login_required 
def RelatorioRazaoDados():
    session = None
    try: 
        session = get_pg_session()
        service = DreService(session)
        
        # Parâmetros
        page = int(request.args.get('page', 1))
        search_term = request.args.get('search', '').strip()
        view_type = request.args.get('view_type', 'original') # Novo parâmetro
        per_page = 1000
        
        # Chama Serviço
        dados = service.get_razao_dados(page, per_page, search_term, view_type)
        
        return jsonify(dados), 200
        
    except Exception as e: 
        current_app.logger.error(f"Erro no RelatorioRazaoDados: {e}")
        abort(500, description=f"Erro: {str(e)}")
    finally:
        if session: session.close()

@reports_bp.route('/RelatorioRazao/Resumo', methods=['GET']) 
@login_required 
def RelatorioRazaoResumo():
    session = None
    try: 
        session = get_pg_session()
        service = DreService(session)
        view_type = request.args.get('view_type', 'original')
        
        resumo = service.get_razao_resumo(view_type)
        
        return jsonify(resumo), 200
        
    except Exception as e: 
        abort(500, description=str(e))
    finally:
        if session: session.close()

@reports_bp.route('/RelatorioRazao/Rentabilidade', methods=['GET'])
@login_required
def RelatorioRentabilidade():
    session = None
    try:
        session = get_pg_session()
        service = DreService(session)
        
        filtro_origem = request.args.get('origem', 'Consolidado')
        scale_mode = request.args.get('scale_mode', 'dre') # Padrão é 'dre'
        
        # 1. Processar Base
        data = service.processar_relatorio(filtro_origem=filtro_origem, agrupar_por_cc=False)
        
        # 2. Calcular Fórmulas
        final_data = service.calcular_nos_virtuais(data)
        
        # 3. Aplicar Escala DRE (Divisão por 1000) se solicitado
        if scale_mode == 'dre':
            final_data = service.aplicar_escala_milhares(final_data)
        
        return jsonify(final_data), 200

    except Exception as e:
        current_app.logger.error(f"Erro DreService Rentabilidade: {e}")
        abort(500, description=f"Erro interno: {str(e)}")
    finally:
        if session: session.close()

@reports_bp.route('/RelatorioRazao/RentabilidadePorCC', methods=['GET'])
@login_required
def RelatorioRentabilidadePorCC():
    session = None
    try:
        session = get_pg_session()
        service = DreService(session)
        
        filtro_origem = request.args.get('origem', 'Consolidado')
        scale_mode = request.args.get('scale_mode', 'dre') # Padrão é 'dre'
        
        # Processa
        data = service.processar_relatorio(filtro_origem=filtro_origem, agrupar_por_cc=True)
        
        # Se houver fórmulas calculadas no futuro para CC, insira aqui
        # service.calcular_nos_virtuais(data) 
        
        # Aplicar Escala
        if scale_mode == 'dre':
            data = service.aplicar_escala_milhares(data)
        
        return jsonify(data), 200

    except Exception as e:
        current_app.logger.error(f"Erro DreService RentabilidadeCC: {e}")
        abort(500, description=f"Erro interno: {str(e)}")
    finally:
        if session: session.close()