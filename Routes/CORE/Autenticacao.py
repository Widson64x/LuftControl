from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

# Importa o Serviço de Autenticação
from Modules.CORE.Services.AutenticacaoService import AutenticacaoService

# Import do Logger
from Utils.Logger import RegistrarLog

# Definição do Blueprint
auth_bp = Blueprint('Autenticacao', __name__)

# Instância do serviço
auth_service = AutenticacaoService()


def CarregarUsuarioFlask(user_id):
    """
    Função auxiliar usada pelo LoginManager no App.py.
    Delega a busca para o serviço.
    """
    return auth_service.CarregarUsuarioCompleto(user_id)


@auth_bp.route('/login', methods=['GET', 'POST'])
def Login():
    """
    Rota responsável por exibir o formulário (GET) e processar o login (POST).
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # 1. Captura o valor do checkbox (retorna 'on' se marcado, None se não marcado)
        lembrar_mim = request.form.get('remember') is not None

        RegistrarLog(f"Iniciando tentativa de login: Usuário '{username}'", 'AUTH')

        # Validação no AD (LDAP)
        if auth_service.AutenticarNoAd(username, password):
            try:
                # Busca usuário no Banco de Dados
                user_db = auth_service.ObterUsuarioPorLogin(username)

                if user_db:
                    # Carrega objeto completo (Wrapper)
                    usuario_flask = auth_service.CarregarUsuarioCompleto(user_db.Codigo_Usuario)

                    if usuario_flask:
                        # Validação de Grupo (Whitelist)
                        if not auth_service.VerificarPermissaoGrupo(usuario_flask.nome_grupo):
                            RegistrarLog(f"Acesso negado. Grupo '{usuario_flask.nome_grupo}' não autorizado. Usuário: {username}", 'WARNING')
                            flash('Usuário não possui permissão para acessar o sistema.', 'danger')
                            logout_user()
                            return redirect(url_for('Autenticacao.Login'))

                        # 2. Login com Sucesso: PASSAR O PARÂMETRO 'remember'
                        login_user(usuario_flask, remember=lembrar_mim)

                        RegistrarLog(f"Login efetuado com sucesso: {user_db.Nome_Usuario} (Grupo: {usuario_flask.nome_grupo})", 'AUTH')

                        flash(f'Bem-vindo(a), {user_db.Nome_Usuario}!', 'success')

                        # Redirecionamento (Página anterior ou Dashboard)
                        next_page = request.args.get('next')
                        return redirect(next_page or url_for('Principal.MenuPrincipal'))
                    else:
                        RegistrarLog(f"Erro ao instanciar wrapper do usuário: {username}", 'ERROR')
                        flash('Erro interno ao carregar perfil do usuário.', 'danger')
                else:
                    # Login correto no AD, mas sem cadastro no sistema
                    RegistrarLog(f"Usuário autenticado no AD mas sem cadastro no sistema: {username}", 'WARNING')
                    flash('Login correto (AD), mas usuário não possui cadastro neste sistema.', 'warning')

            except Exception as e:
                RegistrarLog('Erro técnico no fluxo de login', 'ERROR', erro=e)
                flash('Erro ao validar usuário no banco de dados.', 'danger')
        else:
            # Falha no AD
            flash('Usuário ou senha inválidos.', 'danger')

    return render_template('AUTH/Login.html')


@auth_bp.route('/sair')
@login_required
def Logout():
    """
    Rota para encerrar a sessão do usuário.
    """
    nome_usuario = 'Desconhecido'
    if current_user and current_user.is_authenticated:
        nome_usuario = getattr(current_user, 'nome_completo', getattr(current_user, 'nome', 'Usuário'))

    logout_user()

    RegistrarLog(f"Logout efetuado pelo usuário: {nome_usuario}", 'AUTH')

    # Mensagem exibida na tela de login após sair
    flash('Você saiu do sistema de forma segura.', 'info')

    return redirect(url_for('Autenticacao.Login'))