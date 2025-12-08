"""
Routes/Reports.py
Rotas para Relatórios de Rentabilidade e Razão Contábil
VERSÃO CORRIGIDA - Consulta SQL dinâmica para evitar problemas de mapeamento ORM
"""

from flask import Blueprint, jsonify, request, current_app, abort, render_template, send_file
from flask_login import login_required 
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func, or_, String, text
import io
import pandas as pd
import xlsxwriter
from datetime import datetime


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
    
@reports_bp.route('/RelatorioRazao/DownloadFull', methods=['GET'])
@login_required
def download_razao_full():
    session = None
    try:
        # 1. Recupera filtros do Frontend
        view_type = request.args.get('view_type', 'original') # 'original' ou 'adjusted'
        search_term = request.args.get('search', '').strip()
        
        session = get_pg_session()
        service = DreService(session)
        
        # 2. Busca os dados brutos (Método que criaremos abaixo)
        data_rows = service.export_razao_full(search_term, view_type)
        
        if not data_rows:
            return jsonify({'message': 'Sem dados para exportar'}), 404

        # 3. Gera o DataFrame com as colunas na ordem correta
        df = pd.DataFrame(data_rows)
        
        # Formata datas para o Excel não se perder
        if 'Data' in df.columns:
            df['Data'] = pd.to_datetime(df['Data']).dt.strftime('%d/%m/%Y')

        # 4. Cria o arquivo em memória
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Razão Full')
            
            # Ajuste de largura das colunas (Opcional)
            worksheet = writer.sheets['Razão Full']
            for idx, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(idx, idx, min(max_len, 60))

        output.seek(0)
        
        filename = f"Razao_Full_{view_type}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        current_app.logger.error(f"Erro Download: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if session: session.close()