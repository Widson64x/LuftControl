# Helpers/Security.py
from functools import wraps
from flask import abort, jsonify, request, render_template, redirect, url_for
from flask_login import current_user

def RequiresPermission(permission_slug):
    """
    O Guarda-Costas das Rotas:
    Este decorator verifica se o usuário tem o crachá certo (permissão) para entrar.
    
    Como usar:
        @app.route('/area-secreta')
        @RequiresPermission('area.secreta.acesso')
        def AreaSecreta():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Primeira barreira: Autenticação
            # Se não estiver logado, nem adianta mostrar o crachá.
            if not current_user.is_authenticated:
                # Retorna 401 (Não Autorizado) com um JSON amigável
                return jsonify({"error": "Usuário não autenticado."}), 401
            
            # 2. Segunda barreira: Permissão Específica
            # Chama o método 'has_permission' que criamos lá no UserWrapper (Auth.py)
            if not current_user.has_permission(permission_slug):
                # Se não tiver permissão, exibe a página de "Proibido Entrar" (403 Forbidden)
                # Você pode retornar um JSON também se for uma API pura.
                # Aqui assumimos que pode ser tanto tela quanto API, mas o render é mais comum em views.
                if request.is_json:
                    return jsonify({"error": f"Acesso negado. Requer permissão: {permission_slug}"}), 403
                return render_template('COMPONENTS/NoPermission.html'), 403
            
            # Se passou por tudo, executa a função original da rota
            return f(*args, **kwargs)
        return decorated_function
    return decorator