# Helpers/Security.py
from functools import wraps
from flask import abort, jsonify, request, render_template, redirect, url_for
from flask_login import current_user

def requires_permission(permission_slug):
    """
    Decorator para proteger rotas baseado em permissões.
    Uso: @requires_permission('dre.visualizar')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Verifica login
            if not current_user.is_authenticated:
                return jsonify({"error": "Não autenticado"}), 401
            
            # 2. Verifica permissão (Método que criaremos no UserWrapper)
            if not current_user.has_permission(permission_slug):
                # Renderiza página de acesso negado
                return render_template('COMPONENTS/NoPermission.html'), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator