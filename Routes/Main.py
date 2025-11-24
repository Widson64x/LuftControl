from flask import Blueprint, render_template
from flask_login import login_required, current_user

main_bp = Blueprint('main', __name__)

@main_bp.route('/dashboard')
@login_required
def dashboard():
    # Renderiza o dashboard passando dados do usuário logado
    return render_template('Main.html', user=current_user)