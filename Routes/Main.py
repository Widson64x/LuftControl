from flask import Blueprint, render_template
from flask_login import login_required, current_user

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def dashboard():
    return render_template('Main.html', user=current_user)

# --- NOVA ROTA: HUB DE CONFIGURAÇÕES ---
@main_bp.route('/Settings')
@login_required
def settings_hub():
    """
    Página centralizadora de configurações do sistema.
    Aqui o usuário escolhe se quer configurar DRE, Usuários, etc.
    """
    return render_template('CONFIGS/ConfigsSystem.html')