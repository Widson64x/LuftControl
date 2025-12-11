# Routes/Reports.py
from flask import Blueprint, jsonify, request, current_app, abort, render_template, send_file
from flask_login import login_required 
from sqlalchemy.orm import sessionmaker
import io
import pandas as pd
import xlsxwriter
from datetime import datetime

from Db.Connections import get_postgres_engine
from Reports.AnaliseDRE import AnaliseDREReport
from Reports.Razao import RazaoReport

reports_bp = Blueprint('Reports', __name__) 

def get_pg_session():
    engine = get_postgres_engine()
    Session = sessionmaker(bind=engine)
    return Session()

@reports_bp.route('/', methods=['GET']) 
@login_required 
def PaginaRelatorios():
    return render_template('MENUS/Relatórios.html')

@reports_bp.route('/RelatorioRazao/Dados', methods=['GET']) 
@login_required 
def RelatorioRazaoDados():
    session = None
    try: 
        session = get_pg_session()
        # INSTANCIA O REPORT ESPECÍFICO
        report = RazaoReport(session)
        
        page = int(request.args.get('page', 1))
        search_term = request.args.get('search', '').strip()
        view_type = request.args.get('view_type', 'original')
        per_page = 1000
        
        dados = report.get_dados(page, per_page, search_term, view_type)
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
        report = RazaoReport(session)
        view_type = request.args.get('view_type', 'original')
        resumo = report.get_resumo(view_type)
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
        # INSTANCIA O REPORT DE DRE
        report = AnaliseDREReport(session)
        
        filtro_origem = request.args.get('origem', 'Consolidado')
        scale_mode = request.args.get('scale_mode', 'dre') 
        
        data = report.processar_relatorio(filtro_origem=filtro_origem, agrupar_por_cc=False)
        final_data = report.calcular_nos_virtuais(data)
        
        if scale_mode == 'dre':
            final_data = report.aplicar_milhares(final_data)
        
        return jsonify(final_data), 200
    except Exception as e:
        current_app.logger.error(f"Erro AnaliseDREReport: {e}")
        abort(500, description=f"Erro interno: {str(e)}")
    finally:
        if session: session.close()

@reports_bp.route('/RelatorioRazao/RentabilidadePorCC', methods=['GET'])
@login_required
def RelatorioRentabilidadePorCC():
    session = None
    try:
        session = get_pg_session()
        report = AnaliseDREReport(session)
        
        filtro_origem = request.args.get('origem', 'Consolidado')
        scale_mode = request.args.get('scale_mode', 'dre') 
        
        data = report.processar_relatorio(filtro_origem=filtro_origem, agrupar_por_cc=True)
        # Se quiser aplicar fórmulas aqui no futuro:
        # data = report.calcular_nos_virtuais(data) 
        
        if scale_mode == 'dre':
            data = report.aplicar_milhares(data)
        
        return jsonify(data), 200
    except Exception as e:
        current_app.logger.error(f"Erro AnaliseDREReport CC: {e}")
        abort(500, description=f"Erro interno: {str(e)}")
    finally:
        if session: session.close()
    
@reports_bp.route('/RelatorioRazao/DownloadFull', methods=['GET'])
@login_required
def download_razao_full():
    session = None
    try:
        view_type = request.args.get('view_type', 'original')
        search_term = request.args.get('search', '').strip()
        
        session = get_pg_session()
        report = RazaoReport(session)
        
        data_rows = report.export_full(search_term, view_type)
        if not data_rows: return jsonify({'message': 'Sem dados para exportar'}), 404

        df = pd.DataFrame(data_rows)
        if 'Data' in df.columns:
            df['Data'] = pd.to_datetime(df['Data']).dt.strftime('%d/%m/%Y')

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Razão Full')
            worksheet = writer.sheets['Razão Full']
            for idx, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(idx, idx, min(max_len, 60))

        output.seek(0)
        filename = f"Razao_Full_{view_type}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=filename)

    except Exception as e:
        current_app.logger.error(f"Erro Download: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if session: session.close()