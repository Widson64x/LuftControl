from flask import Blueprint, request, render_template, send_file
from flask_login import login_required, current_user 
from datetime import datetime

# --- Imports do LuftCore (Segurança e Padronização de API) ---
from luftcore.extensions.flask_extension import (
    require_ajax, 
    api_success, 
    api_error
)

# Importa o Serviço (Único ponto de contato com a lógica)
from Modules.DRE.Services.RelatoriosService import RelatoriosService
from Modules.DRE.Services.PermissaoService import RequerPermissao
# Import do Logger
from Utils.Logger import RegistrarLog

# Definição do Blueprint
reports_bp = Blueprint('Relatorios', __name__) 

# ============================================================
# VIEWS (Páginas HTML)
# ============================================================

@reports_bp.route('/relatorios', methods=['GET']) 
@login_required 
@RequerPermissao('RELATORIOS.VISUALIZAR')
def PaginaRelatorios():
    """Renderiza a página HTML principal de relatórios."""
    return render_template('Pages/Reports/ReportsDashboard.html')

# ============================================================
# APIs DE DADOS (AJAX)
# ============================================================

@reports_bp.route('/razao/dados', methods=['GET']) 
@login_required 
@RequerPermissao('RELATORIOS.RAZAO.VISUALIZAR') 
@require_ajax
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
        
        return api_success(data=dados, message="Dados do Razão carregados.")
    except Exception as e: 
        RegistrarLog("Erro na rota ObterDadosRazao", "ERROR", e)
        return api_error(message="Falha ao carregar os dados do Razão.", details=str(e), status=500)

@reports_bp.route('/razao/resumo', methods=['GET']) 
@login_required 
@RequerPermissao('RELATORIOS.RAZAO.VISUALIZAR')
@require_ajax
def ObterResumoRazao():
    """API: Retorna os totais do rodapé do Razão."""
    try: 
        tipo_visualizacao = request.args.get('view_type', 'original')
        svc = RelatoriosService()
        resumo = svc.ObterResumoRazao(tipo_visualizacao)
        
        return api_success(data=resumo)
    except Exception as e: 
        return api_error(message="Falha ao calcular os totais do Razão.", details=str(e), status=500)

@reports_bp.route('/razao/centros-custo', methods=['GET'])
@login_required
@RequerPermissao('RELATORIOS.VISUALIZAR') 
@require_ajax
def ListarCentrosCusto():
    """API: Dropdown de Centros de Custo."""
    try:
        svc = RelatoriosService()
        lista = svc.ListarCentrosCusto()
        return api_success(data=lista)
    except Exception as e:
        # Se falhar, devolvemos a lista vazia dentro do padrão api_success
        # para não quebrar a tela do usuário, como era a sua lógica original.
        RegistrarLog("Aviso ao carregar centros de custo", "WARNING", e)
        return api_success(data=[]) 

@reports_bp.route('/dre/rentabilidade', methods=['GET'])
@login_required
@RequerPermissao('RELATORIOS.DRE.VISUALIZAR') 
@require_ajax
def RelatorioRentabilidade():
    """API: Gera o relatório de DRE Gerencial."""
    try:
        origem = request.args.get('origem', "FARMA,FARMADIST,INTEC")
        modo_escala = request.args.get('scale_mode', 'dre')
        filtro_cc = request.args.get('centro_custo', 'Todos')
        
        ano_atual = datetime.now().year
        ano = request.args.get('ano', ano_atual)
        
        usuario_id = current_user.get_id() if current_user else "Anonimo"
        RegistrarLog(f"Relatório DRE solicitado por {usuario_id}. Ano: {ano}", "WEB_REPORT")
        
        svc = RelatoriosService()
        dados = svc.GerarDreRentabilidade(origem, filtro_cc, modo_escala, ano)
        
        return api_success(data=dados, message="DRE Gerencial processado.")
    except Exception as e:
        RegistrarLog("Erro Crítico no Relatório DRE", "ERROR", e)
        return api_error(message="Falha ao gerar o relatório DRE.", details=str(e), status=500)

@reports_bp.route('/dre/consolidado', methods=['GET'])
@login_required
@RequerPermissao('RELATORIOS.DRE_CONSOLIDADO.VISUALIZAR') 
@require_ajax
def GerarDreConsolidado():
    """API: Gera o relatório DRE Consolidado (Visão por Unidade)."""
    try:
        modo_escala = request.args.get('scale_mode', 'dre')
        ano = request.args.get('ano', datetime.now().year)
        
        usuario_id = current_user.get_id() if current_user else "Anonimo"
        RegistrarLog(f"Relatório DRE Consolidado solicitado por {usuario_id}. Ano: {ano}", "WEB_REPORT")
        
        svc = RelatoriosService()
        dados = svc.GerarDreConsolidado(modo_escala, ano)
        
        return api_success(data=dados, message="DRE Consolidado processado.")
    except Exception as e:
        RegistrarLog("Erro Crítico no Relatório DRE Consolidado", "ERROR", e)
        return api_error(message="Falha ao gerar o DRE Consolidado.", details=str(e), status=500)

@reports_bp.route('/dre/operacao', methods=['GET'])
@login_required
@RequerPermissao('RELATORIOS.DRE_OPERACAO.VISUALIZAR')
@require_ajax
def GerarDreOperacao():
    """API: Gera o relatório DRE por Operação."""
    try:
        modo_escala = request.args.get('scale_mode', 'dre')
        ano = request.args.get('ano', datetime.now().year)
        
        usuario_id = current_user.get_id() if current_user else "Anonimo"
        RegistrarLog(f"Relatório DRE Operação solicitado por {usuario_id}. Ano: {ano}", "WEB_REPORT")
        
        svc = RelatoriosService()
        dados = svc.GerarDreOperacao(modo_escala, ano)
        
        return api_success(data=dados, message="DRE Operação processado.")
    except Exception as e:
        RegistrarLog("Erro Crítico no Relatório DRE Operação", "ERROR", e)
        return api_error(message="Falha ao gerar o DRE Operação.", details=str(e), status=500)
    
# ============================================================
# ARQUIVOS E EXPORTAÇÕES (NÃO USA @require_ajax)
# ============================================================

@reports_bp.route('/razao/download', methods=['GET'])
@login_required
@RequerPermissao('RELATORIOS.RAZAO.EXPORTAR') 
# Sem require_ajax pois é download/attachment
def BaixarRazaoExcel():
    """Gera e baixa o Excel completo do Razão."""
    
    # ATENÇÃO: NÃO usamos @require_ajax aqui, pois o navegador faz o 
    # download do arquivo usando uma requisição GET padrão (window.location ou <a href>),
    # o que faria o @require_ajax bloquear a chamada.
    
    try:
        tipo_visualizacao = request.args.get('view_type', 'original')
        termo_busca = request.args.get('search', '').strip()
        usuario_id = current_user.get_id() if current_user else "Anonimo"

        RegistrarLog(f"Download Excel Razão iniciado por {usuario_id}", "WEB_EXPORT")
        
        svc = RelatoriosService()
        arquivo_binario = svc.GerarExcelRazao(termo_busca, tipo_visualizacao)
        
        if not arquivo_binario:
            # Caso chamem via fetch Blob, o api_error responde em json formatado.
            return api_error(message="Sem dados para exportar.", status=404)

        nome_arquivo = f"Razao_Analitico_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        return send_file(
            arquivo_binario, 
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
            as_attachment=True, 
            download_name=nome_arquivo
        )

    except Exception as e:
        RegistrarLog("Erro no Download Excel", "ERROR", e)
        return api_error(message="Falha na exportação do Excel.", details=str(e), status=500)

# ============================================================
# ROTAS DE ADMIN/DEBUG
# ============================================================

@reports_bp.route('Relatorios.DepurarOrdenamento', methods=['GET'])
@login_required
@RequerPermissao('SISTEMA.ADMIN.DEPURAR') 
@require_ajax
def DepurarOrdenamento():
    """Rota auxiliar de debug do Sistema."""
    try:
        svc = RelatoriosService()
        dados_debug = svc.DepurarOrdenamentoDre()
        return api_success(data=dados_debug, message="Dados de debug extraídos.")
    except Exception as e:
        return api_error(message="Erro ao executar rotina de debug.", details=str(e), status=500)