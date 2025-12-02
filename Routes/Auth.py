import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, UserMixin
from sqlalchemy.orm import sessionmaker
from ldap3 import Server, Connection, SIMPLE, core

# Importações locais do seu projeto
from Db.Connections import get_sqlserver_engine
from Models.SQL_SERVER.Usuario import Usuario, UsuarioGrupo, MenuAcesso, Menu

auth_bp = Blueprint('auth', __name__)

# --- Configurações do AD (Carregadas do .env) ---
LDAP_SERVER = os.getenv("LDAP_SERVER", "luftfarma.com.br") # Coloque o IP padrão ou configure no .env
LDAP_DOMAIN = os.getenv("LDAP_DOMAIN", "luftfarma")         # Coloque o domínio padrão

# --- Configuração da Sessão do Banco (SQL Server) ---
engine = get_sqlserver_engine()
Session = sessionmaker(bind=engine)

# --- Classe Wrapper para o Flask-Login ---
# Necessária para adaptar o objeto do SQLAlchemy para o que o Flask-Login espera
class UserWrapper(UserMixin):
    def __init__(self, usuario_db, nome_grupo="", lista_menus=[]):
        self.id = usuario_db.Codigo_Usuario
        self.nome = usuario_db.Login_Usuario
        self.nome_completo = usuario_db.Nome_Usuario # Adicionado para exibição bonita
        self.email = usuario_db.Email_Usuario
        self.grupo_id = usuario_db.codigo_usuariogrupo
        
        # Novos campos
        self.nome_grupo = nome_grupo
        self.menus = lista_menus # Será uma lista de strings

# --- Função de Autenticação no AD ---
def autenticar_ad(usuario, senha):
    """
    Tenta autenticar o usuário no Active Directory via NTLM.
    Retorna True se sucesso, False se falha.
    """
    if not senha:
        return False

    # Monta o usuário no formato DOMINIO\usuario
    full_user = f'{LDAP_DOMAIN}\\{usuario}'

    try:
        server = Server(LDAP_SERVER, port=389, use_ssl=False, get_info=None)
        conn = Connection(
            server,
            user=full_user,
            password=senha,
            authentication=SIMPLE,
            auto_bind=True
        )
        # Se passou do auto_bind sem erro, a senha está correta
        print(f"✅ [AUTH AD] Usuário '{usuario}' autenticado com sucesso no AD!")
        conn.unbind()
        return True

    except core.exceptions.LDAPBindError as e:
        print(f"❌ [AUTH AD] Falha de login para '{usuario}': {e}")
        return False
    except Exception as e:
        print(f"❌ [AUTH AD] Erro de conexão LDAP: {e}")
        return False

# --- Callback do Flask-Login (User Loader) ---
def carregar_usuario_flask(user_id):
    session_db = Session()
    try:
        # Busca o Usuário e seu Grupo (Equivalente ao LEFT JOIN da sua query)
        resultado = session_db.query(Usuario, UsuarioGrupo)\
            .outerjoin(UsuarioGrupo, Usuario.codigo_usuariogrupo == UsuarioGrupo.codigo_usuariogrupo)\
            .filter(Usuario.Codigo_Usuario == user_id)\
            .first()

        if resultado:
            usuario, grupo = resultado
            
            # Define o nome do grupo (Sigla ou Descrição)
            nome_grupo = grupo.Sigla_UsuarioGrupo if grupo else "Sem Grupo"

            # Busca os Menus (Equivalente ao OUTER APPLY dos Menus na sua query)
            # Pega o Nome do Menu onde o Codigo_UsuarioGrupo bate com o do usuário
            menus_db = session_db.query(Menu.Nome_Menu)\
                .join(MenuAcesso, Menu.Codigo_Menu == MenuAcesso.Codigo_Menu)\
                .filter(MenuAcesso.Codigo_UsuarioGrupo == usuario.codigo_usuariogrupo)\
                .order_by(Menu.Numero_Menu)\
                .all()
            
            # Transforma a lista de tuplas em lista de strings simples
            lista_menus = [m.Nome_Menu for m in menus_db]

            return UserWrapper(usuario, nome_grupo, lista_menus)
            
    except Exception as e:
        print(f"Erro ao carregar usuário na sessão: {e}")
    finally:
        session_db.close()
    return None

# --- Rotas ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # 1. Autenticação via Active Directory
        if autenticar_ad(username, password):
            
            # 2. Verificação no Banco de Dados (SQL Server)
            # O usuário precisa existir na tabela 'Usuario' para ter permissão no sistema
            session_db = Session()
            try:
                user_db = session_db.query(Usuario).filter_by(Login_Usuario=username).first()
                
                if user_db:
                    # SUCESSO TOTAL: Validado no AD e Encontrado no Banco
                    usuario_flask = carregar_usuario_flask(user_db.Codigo_Usuario)
                    login_user(usuario_flask)
                    
                    flash(f'Bem-vindo(a), {user_db.Nome_Usuario}!', 'success')
                    
                    next_page = request.args.get('next')
                    return redirect(next_page or url_for('main.dashboard'))
                else:
                    # ERRO: Login correto no AD, mas não tem cadastro no sistema
                    flash('Login correto (AD), mas usuário não possui cadastro neste sistema.', 'warning')
            
            except Exception as e:
                flash(f'Erro ao validar usuário no banco de dados: {e}', 'danger')
            finally:
                session_db.close()
        
        else:
            # ERRO: Senha ou Usuário incorretos no AD
            flash('Usuário ou senha inválidos.', 'danger')
            
    return render_template('AUTH/Login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('auth.login'))