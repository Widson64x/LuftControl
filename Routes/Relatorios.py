from flask import Blueprint, jsonify, request, abort, render_template, send_file
from flask_login import login_required, current_user 
from datetime import datetime

# Importa o Serviço (Único ponto de contato com a lógica)
from Services.RelatoriosService import RelatoriosService

# Import do Logger
from Utils.Logger import RegistrarLog

# Definição do Blueprint
reports_bp = Blueprint('Relatorios', __name__) 

@reports_bp.route('/', methods=['GET']) 
@login_required 
def PaginaRelatorios():
    """Renderiza a página HTML principal de relatórios."""
    return render_template('PAGES/Relatórios.html')

@reports_bp.route('/relatoriorazao/dados', methods=['GET']) 
@login_required 
def ObterDadosRazao():
    """API: Retorna JSON com os dados paginados do Razão."""
    try: 
        pagina = int(request.args.get('page', 1))
        termo_busca = request.args.get('search', '').strip()
        tipo_visualizacao = request.args.get('view_type', 'original')
        por_pagina = 1000 
        
        usuario_id = current_user.get_id() if current_user else "Anonimo"
        if pagina == 1:
            RegistrarLog(f"Relatório Razão solicitado por {usuario_id}. Filtro: '{termo_busca}'", "WEB_REPORT")

        svc = RelatoriosService()
        dados = svc.ObterDadosRazao(pagina, por_pagina, termo_busca, tipo_visualizacao)
        
        return jsonify(dados), 200
    except Exception as e: 
        RegistrarLog("Erro na rota ObterDadosRazao", "ERROR", e)
        return jsonify({"error": str(e)}), 500

@reports_bp.route('/relatoriorazao/resumo', methods=['GET']) 
@login_required 
def ObterResumoRazao():
    """API: Retorna os totais do rodapé do Razão."""
    try: 
        tipo_visualizacao = request.args.get('view_type', 'original')
        svc = RelatoriosService()
        resumo = svc.ObterResumoRazao(tipo_visualizacao)
        return jsonify(resumo), 200
    except Exception as e: 
        return jsonify({"error": str(e)}), 500

@reports_bp.route('/relatoriorazao/listacentroscusto', methods=['GET'])
@login_required
def ListarCentrosCusto():
    """API: Dropdown de Centros de Custo."""
    try:
        svc = RelatoriosService()
        lista = svc.ListarCentrosCusto()
        return jsonify(lista), 200
    except Exception as e:
        return jsonify([]), 200 

@reports_bp.route('/relatoriorazao/rentabilidade', methods=['GET'])
@login_required
def RelatorioRentabilidade():
    """API: Gera o relatório de DRE Gerencial."""
    try:
        origem = request.args.get('origem', "FARMA,FARMADIST,INTEC")
        modo_escala = request.args.get('scale_mode', 'dre')
        filtro_cc = request.args.get('centro_custo', 'Todos')
        
        usuario_id = current_user.get_id() if current_user else "Anonimo"
        RegistrarLog(f"Relatório DRE solicitado por {usuario_id}", "WEB_REPORT")
        
        svc = RelatoriosService()
        dados = svc.GerarDreRentabilidade(origem, filtro_cc, modo_escala)
        
        return jsonify(dados), 200
    except Exception as e:
        RegistrarLog("Erro Crítico no Relatório DRE", "ERROR", e)
        return jsonify({"error": str(e)}), 500
    
@reports_bp.route('/relatoriorazao/downloadfull', methods=['GET'])
@login_required
def DownloadRazaoExcel():
    """Gera e baixa o Excel completo do Razão."""
    try:
        tipo_visualizacao = request.args.get('view_type', 'original')
        termo_busca = request.args.get('search', '').strip()
        usuario_id = current_user.get_id() if current_user else "Anonimo"

        RegistrarLog(f"Download Excel Razão iniciado por {usuario_id}", "WEB_EXPORT")
        
        svc = RelatoriosService()
        arquivo_binario = svc.GerarExcelRazao(termo_busca, tipo_visualizacao)
        
        if not arquivo_binario:
            return jsonify({'message': 'Sem dados para exportar'}), 404

        nome_arquivo = f"Razao_Analitico_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        return send_file(
            arquivo_binario, 
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
            as_attachment=True, 
            download_name=nome_arquivo
        )

    except Exception as e:
        RegistrarLog("Erro no Download Excel", "ERROR", e)
        return jsonify({'error': str(e)}), 500
        
@reports_bp.route('/relatoriorazao/debugordenamento', methods=['GET'])
@login_required
def DepurarOrdenamento():
    """Rota auxiliar de debug."""
    try:
        svc = RelatoriosService()
        dados_debug = svc.DepurarOrdenamentoDre()
        return jsonify(dados_debug), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500