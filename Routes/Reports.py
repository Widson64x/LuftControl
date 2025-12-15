# Routes/Reports.py
from flask import Blueprint, jsonify, request, current_app, abort, render_template, send_file
from flask_login import login_required 
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
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

@reports_bp.route('/RelatorioRazao/ListaCentrosCusto', methods=['GET'])
@login_required
def ListaCentrosCusto():
    """
    Rota para popular o dropdown de Centros de Custo.
    Retorna objeto {codigo, nome_exibicao} para o frontend.
    """
    session = None
    try:
        session = get_pg_session()
        
        # Selecionamos o CODIGO (para o value) e o NOME (para o display)
        sql = text("""
            SELECT DISTINCT ccc."Codigo", ccc."Nome" 
            FROM "Dre_Schema"."Razao_Dados_Consolidado" rdc 
            JOIN "Dre_Schema"."Classificacao_Centro_Custo" ccc ON rdc."Centro de Custo" = ccc."Codigo" 
            WHERE ccc."Nome" IS NOT NULL 
            ORDER BY ccc."Nome"
        """)
        
        rows = session.execute(sql).fetchall()
        
        # 1. Identificar nomes duplicados
        nome_counts = {}
        for row in rows:
            nome_counts[row.Nome] = nome_counts.get(row.Nome, 0) + 1

        lista_ccs = []
        for row in rows:
            nome_base = row.Nome
            codigo = str(row.Codigo)

            # 2. Desambiguação: Se o nome for duplicado, adiciona o código ao nome
            nome_exibicao = nome_base
            if nome_counts[nome_base] > 1:
                nome_exibicao = f"{nome_base} ({codigo})"
            
            # Monta a lista de objetos, incluindo o código limpo para o 'value'
            lista_ccs.append({'codigo': codigo, 'nome': nome_exibicao})
        
        return jsonify(lista_ccs), 200
        
    except Exception as e:
        current_app.logger.error(f"Erro ao listar Centros de Custo: {e}")
        return jsonify([]), 200 
    finally:
        if session: session.close()
        
@reports_bp.route('/RelatorioRazao/Rentabilidade', methods=['GET'])
@login_required
def RelatorioRentabilidade():
    session = None
    try:
        session = get_pg_session()
        report = AnaliseDREReport(session)
        
        # Parâmetros da URL
        # Agora 'origem' pode ser "FARMA,INTEC" ou vazio
        filtro_origem_raw = request.args.get('origem', '')
        
        # Se vier vazio, definimos um padrão ou enviamos vazio (o processador lidará)
        if not filtro_origem_raw:
             # Opcional: Se quiser forçar todas caso nada seja enviado
             filtro_origem_raw = "FARMA,FARMADIST,INTEC" 

        scale_mode = request.args.get('scale_mode', 'dre')
        # AJUSTE: Mudar para receber múltiplos CCs (string separada por vírgula)
        filtro_cc = request.args.get('centro_custo', 'Todos')
        
        # Processamento
        # Passamos a string bruta separada por vírgula
        data = report.processar_relatorio(
            filtro_origem=filtro_origem_raw, 
            agrupar_por_cc=False, 
            filtro_cc=filtro_cc # CC é passado como string "cc1,cc2" ou "Todos"
        )
        
        # Cálculos de nós virtuais (fórmulas)
        final_data = report.calcular_nos_virtuais(data)
        
        # Aplicação da escala
        if scale_mode == 'dre':
            final_data = report.aplicar_milhares(final_data)
        
        return jsonify(final_data), 200
    except Exception as e:
        current_app.logger.error(f"Erro AnaliseDREReport: {e}")
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
        
@reports_bp.route('/RelatorioRazao/DebugOrdenamento', methods=['GET'])
@login_required
def DebugOrdenamento():
    session = None
    try:
        session = get_pg_session()
        report = AnaliseDREReport(session)
        
        # Chama a função nova de debug
        dados_debug = report.debug_structure_and_order()
        
        return jsonify(dados_debug), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if session: session.close()