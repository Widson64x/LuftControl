# Routes/Reports.py
from flask import Blueprint, jsonify, request, current_app, abort, render_template, send_file
from flask_login import login_required, current_user 
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import io
import pandas as pd
import xlsxwriter
from datetime import datetime

# Importações Locais
from Db.Connections import GetPostgresEngine
from Reports.AnaliseDRE import AnaliseDREReport
from Reports.Razao import RazaoReport

# --- Import do Logger ---
from Utils.Logger import RegistrarLog

# Definição do Blueprint com Nome PascalCase
reports_bp = Blueprint('Reports', __name__) 

def GetPgSession():
    """Fabrica de sessão PostgreSQL para os relatórios."""
    engine = GetPostgresEngine()
    Session = sessionmaker(bind=engine)
    return Session()

@reports_bp.route('/', methods=['GET']) 
@login_required 
def PaginaRelatorios():
    """Renderiza a página HTML principal de relatórios."""
    return render_template('PAGES/Relatórios.html')

@reports_bp.route('/relatoriorazao/dados', methods=['GET']) 
@login_required 
def RelatorioRazaoDados():
    """API: Retorna JSON com os dados paginados do Razão."""
    session = None
    try: 
        session = GetPgSession()
        report = RazaoReport(session)
        
        page = int(request.args.get('page', 1))
        search_term = request.args.get('search', '').strip()
        view_type = request.args.get('view_type', 'original')
        per_page = 1000 # Limite alto para performance no grid
        
        user_id = current_user.get_id() if current_user else "Anonimo"
        # Loga apenas a primeira página para não floodar na paginação
        if page == 1:
            RegistrarLog(f"Relatório Razão solicitado por {user_id}. Filtro: '{search_term}'", "WEB_REPORT")

        # Chama o método refatorado em PascalCase
        dados = report.GetDados(page, per_page, search_term, view_type)
        return jsonify(dados), 200
    except Exception as e: 
        RegistrarLog("Erro na rota RelatorioRazaoDados", "ERROR", e)
        current_app.logger.error(f"Erro no RelatorioRazaoDados: {e}")
        abort(500, description=f"Erro: {str(e)}")
    finally:
        if session: session.close()

@reports_bp.route('/relatoriorazao/resumo', methods=['GET']) 
@login_required 
def RelatorioRazaoResumo():
    """API: Retorna os totais do rodapé do Razão."""
    session = None
    try: 
        session = GetPgSession()
        report = RazaoReport(session)
        view_type = request.args.get('view_type', 'original')
        
        resumo = report.GetResumo(view_type)
        return jsonify(resumo), 200
    except Exception as e: 
        RegistrarLog("Erro no resumo do Razão", "ERROR", e)
        abort(500, description=str(e))
    finally:
        if session: session.close()

@reports_bp.route('/relatoriorazao/listacentroscusto', methods=['GET'])
@login_required
def ListaCentrosCusto():
    """
    API: Retorna lista de centros de custo para preencher o Dropdown de filtros.
    Trata duplicidades de nomes adicionando o código entre parênteses.
    """
    session = None
    try:
        session = GetPgSession()
        
        sql = text("""
            SELECT DISTINCT ccc."Codigo", ccc."Nome" 
            FROM "Dre_Schema"."Razao_Dados_Consolidado" rdc 
            JOIN "Dre_Schema"."Classificacao_Centro_Custo" ccc ON rdc."Centro de Custo" = ccc."Codigo" 
            WHERE ccc."Nome" IS NOT NULL 
            ORDER BY ccc."Nome"
        """)
        
        rows = session.execute(sql).fetchall()
        
        # Contagem para identificar duplicatas
        nome_counts = {}
        for row in rows:
            nome_counts[row.Nome] = nome_counts.get(row.Nome, 0) + 1

        lista_ccs = []
        for row in rows:
            nome_base = row.Nome
            codigo = str(row.Codigo)

            nome_exibicao = nome_base
            if nome_counts[nome_base] > 1:
                nome_exibicao = f"{nome_base} ({codigo})"
            
            lista_ccs.append({'codigo': codigo, 'nome': nome_exibicao})
        
        return jsonify(lista_ccs), 200
        
    except Exception as e:
        RegistrarLog("Erro ao listar Centros de Custo", "ERROR", e)
        current_app.logger.error(f"Erro ao listar Centros de Custo: {e}")
        return jsonify([]), 200 
    finally:
        if session: session.close()
        
@reports_bp.route('/relatoriorazao/rentabilidade', methods=['GET'])
@login_required
def RelatorioRentabilidade():
    """
    API: Gera o relatório de DRE Gerencial (Rentabilidade).
    Envolve processamento pesado de hierarquia e fórmulas.
    """
    session = None
    try:
        session = GetPgSession()
        report = AnaliseDREReport(session)
        
        filtro_origem_raw = request.args.get('origem', '')
        if not filtro_origem_raw:
             filtro_origem_raw = "FARMA,FARMADIST,INTEC" 

        scale_mode = request.args.get('scale_mode', 'dre')
        filtro_cc = request.args.get('centro_custo', 'Todos')
        
        user_id = current_user.get_id() if current_user else "Anonimo"
        RegistrarLog(f"Relatório Rentabilidade (DRE) solicitado por {user_id}", "WEB_REPORT")
        
        # print(f"\n[ROTA DEBUG] Chamando ProcessarRelatorio...") 
        # Removido print, o log interno do Service já captura isso
        
        # 1. Busca Dados Base e Aplica Hierarquia
        data = report.ProcessarRelatorio(
            filtro_origem=filtro_origem_raw, 
            agrupar_por_cc=False, 
            filtro_cc=filtro_cc 
        )
        
        # 2. Executa Fórmulas (Margens, EBITDA, etc)
        final_data = report.CalcularNosVirtuais(data)
        
        # 3. Formatação
        if scale_mode == 'dre':
            final_data = report.AplicarMilhares(final_data)

        RegistrarLog(f"DRE Finalizado. Retornando {len(final_data)} linhas.", "WEB_SUCCESS")
        return jsonify(final_data), 200
    except Exception as e:
        RegistrarLog("Erro Crítico no Relatório de Rentabilidade", "ERROR", e)
        current_app.logger.error(f"Erro AnaliseDREReport: {e}")
        abort(500, description=f"Erro interno: {str(e)}")
    finally:
        if session: session.close()
    
@reports_bp.route('/relatoriorazao/downloadfull', methods=['GET'])
@login_required
def DownloadRazaoFull():
    """Gera e baixa o Excel completo do Razão."""
    session = None
    try:
        view_type = request.args.get('view_type', 'original')
        search_term = request.args.get('search', '').strip()
        user_id = current_user.get_id() if current_user else "Anonimo"

        RegistrarLog(f"Download Excel Razão iniciado por {user_id}", "WEB_EXPORT")
        
        session = GetPgSession()
        report = RazaoReport(session)
        
        data_rows = report.ExportFull(search_term, view_type)
        if not data_rows: 
            RegistrarLog("Download cancelado: Sem dados.", "WARNING")
            return jsonify({'message': 'Sem dados para exportar'}), 404

        df = pd.DataFrame(data_rows)
        if 'Data' in df.columns:
            df['Data'] = pd.to_datetime(df['Data']).dt.strftime('%d/%m/%Y')

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Razão Full')
            worksheet = writer.sheets['Razão Full']
            for idx, col in enumerate(df.columns):
                # Ajuste automático de largura de coluna
                max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(idx, idx, min(max_len, 60))

        output.seek(0)
        filename = f"Razao_Full_{view_type}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        RegistrarLog(f"Arquivo Excel gerado com sucesso: {filename}", "WEB_SUCCESS")
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=filename)

    except Exception as e:
        RegistrarLog("Erro ao gerar Download Excel", "ERROR", e)
        current_app.logger.error(f"Erro Download: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if session: session.close()
        
@reports_bp.route('/relatoriorazao/debugordenamento', methods=['GET'])
@login_required
def DebugOrdenamento():
    """Rota auxiliar para verificar por que uma conta está fora de ordem."""
    session = None
    try:
        session = GetPgSession()
        report = AnaliseDREReport(session)
        
        dados_debug = report.DebugStructureAndOrder()
        
        return jsonify(dados_debug), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if session: session.close()