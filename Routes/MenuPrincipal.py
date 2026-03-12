from flask import Blueprint, render_template
from flask_login import login_required, current_user
from Services.PermissaoService import RequerPermissao

main_bp = Blueprint('Principal', __name__)

@main_bp.route('/')
@login_required
@RequerPermissao('HOME.VISUALIZAR')
def MenuPrincipal():
    return render_template('Pages/HomeDashboard.html', user=current_user)

# --- NOVA ROTA: HUB DE CONFIGURAÇÕES ---
@main_bp.route('/configuracoes')
@login_required
@RequerPermissao('CONFIGURACOES.VISUALIZAR')
def MenuConfiguracoes():
    """
    Página centralizadora de configurações do sistema.
    Aqui o usuário escolhe se quer configurar DRE, Usuários, etc.
    """
    return render_template('Pages/Configs/SystemConfigs.html')