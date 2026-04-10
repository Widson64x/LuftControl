from flask import Blueprint, render_template
from flask_login import login_required, current_user

from Modules.SISTEMA.Services.PermissaoService import RequerPermissao

main_bp = Blueprint('Principal', __name__)


@main_bp.route('/')
@login_required
@RequerPermissao('HOME.VISUALIZAR')
def MenuPrincipal():
    return render_template('Pages/HomeDashboard.html', user=current_user)


@main_bp.route('/dre-hub')
@login_required
# @RequerPermissao('DRE.VISUALIZAR')  # Ajuste para a permissão correta do seu sistema
def HubDRE():
    """
    Painel central do Módulo DRE.
    Dá acesso a relatórios, ajustes, importação e configurações do DRE.
    """
    return render_template('Pages/DreHub.html')


@main_bp.route('/budget-hub')
@login_required
@RequerPermissao('RELATORIOS.BUDGET.VISUALIZAR')
def HubBudget():
    """
    Painel central do Módulo Budget.
    Concentra os processos e atalhos operacionais do orçamento.
    """
    return render_template('Pages/BudgetHub.html')


@main_bp.route('/configuracoes')
@login_required
@RequerPermissao('CONFIGURACOES.VISUALIZAR')
def MenuConfiguracoes():
    """
    Página centralizadora de configurações globais do sistema.
    Focada em Segurança, Parâmetros do App, etc.
    """
    return render_template('Pages/Configs/SystemConfigs.html')