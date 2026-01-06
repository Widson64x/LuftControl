import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, UserMixin
from sqlalchemy.orm import sessionmaker
# Biblioteca para comunicação com o Active Directory (LDAP)
from ldap3 import Server, Connection, SIMPLE, core

# Engines de conexão com SQL Server (Dados de Negócio) e Postgres (Dados de Segurança/Logs)
from Db.Connections import GetSqlServerEngine, GetPostgresEngine
# Modelos das tabelas do SQL Server
from Models.SQL_SERVER.Usuario import Usuario, UsuarioGrupo, MenuAcesso, Menu
# Modelo de segurança estendida (Permissões extras) no Postgres
from Models.POSTGRESS.Seguranca import SecUserExtension

# Definição do Blueprint 'Auth'. 
# Blueprints organizam o código, permitindo que todas as rotas de autenticação fiquem neste arquivo.
auth_bp = Blueprint('Auth', __name__)

# --- Configurações do Active Directory (AD) ---
# Busca as variáveis de ambiente. Se não encontrar, usa valores padrão (fallback).
LDAP_SERVER = os.getenv("LDAP_SERVER", "luftfarma.com.br")
LDAP_DOMAIN = os.getenv("LDAP_DOMAIN", "luftfarma")

# --- Configuração da Sessão Principal (SQL Server) ---
# Cria o motor de conexão e a fábrica de sessões para o banco principal da aplicação
engine = GetSqlServerEngine()
Session = sessionmaker(bind=engine)

def GetPgSession():
    """
    Fábrica de sessões específica para o PostgreSQL.
    Usada para buscar permissões granulares que não existem no SQL Server.
    """
    engine_pg = GetPostgresEngine()
    return sessionmaker(bind=engine_pg)()

# --- Classe Wrapper (Adaptador de Usuário) ---
class UserWrapper(UserMixin):
    """
    Classe intermediária que adapta o usuário do Banco de Dados para o formato 
    que o Flask-Login espera. Ela herda de UserMixin para ganhar métodos como is_authenticated.
    """
    def __init__(self, usuario_db, nome_grupo="", lista_menus=None):
        # Mapeia os dados do objeto do banco (SQL Server) para atributos da classe
        self.id = usuario_db.Codigo_Usuario
        self.nome = usuario_db.Login_Usuario
        self.nome_completo = usuario_db.Nome_Usuario
        self.email = usuario_db.Email_Usuario
        self.grupo_id = usuario_db.codigo_usuariogrupo
        
        # Armazena informações de contexto (Grupo e Menus)
        self.nome_grupo = nome_grupo
        # Garante que lista_menus seja uma lista válida, evitando erro com None
        self.lista_menus = lista_menus if lista_menus is not None else []
        
        # Conjunto (Set) para armazenar permissões únicas (evita duplicatas)
        self.all_permissions = set()
        
        # Ao instanciar o usuário, já carregamos suas permissões de segurança
        self._load_security_context()

    def _load_security_context(self):
        """
        Método interno que conecta no Postgres para buscar permissões 
        específicas (Roles e Permissions) do usuário.
        """
        session_pg = GetPgSession()
        try:
            # Busca o usuário na tabela de extensão de segurança pelo Login
            pg_user = session_pg.query(SecUserExtension).filter_by(Login_Usuario=self.nome).first()
            if pg_user:
                # 1. Se o usuário tem uma Role (papel), adiciona todas as permissões dessa Role
                if pg_user.role:
                    for perm in pg_user.role.permissions:
                        self.all_permissions.add(perm.Slug)
                
                # 2. Adiciona permissões atribuídas diretamente ao usuário (exceções)
                for perm in pg_user.direct_permissions:
                    self.all_permissions.add(perm.Slug)
        except Exception as e:
            # Loga o erro mas não trava o login do usuário
            print(f"⚠️ Erro ao carregar contexto de segurança: {e}")
        finally:
            # Garante o fechamento da conexão com o Postgres
            session_pg.close()

    def has_permission(self, slug):
        """
        Verifica se o usuário possui uma permissão específica.
        Retorna True se tiver a permissão ou se for 'admin.master'.
        """
        if 'admin.master' in self.all_permissions:
            return True
        return slug in self.all_permissions

# --- Funções Auxiliares (Lógica de Negócio) ---

def AutenticarAd(usuario, senha):
    """
    Realiza a tentativa de login no servidor LDAP (Active Directory).
    Retorna True se a senha estiver correta, False caso contrário.
    """
    if not senha:
        return False
        
    # Formata o usuário como 'DOMINIO\usuario' para autenticação NTLM/Simple
    full_user = f'{LDAP_DOMAIN}\\{usuario}'
    
    try:
        # Tenta conectar ao servidor LDAP
        server = Server(LDAP_SERVER, port=389, use_ssl=False, get_info=None)
        # O parâmetro auto_bind=True tenta logar imediatamente. Se falhar, gera exceção.
        conn = Connection(server, user=full_user, password=senha, authentication=SIMPLE, auto_bind=True)
        
        print(f"✅ [AUTH AD] Usuário '{usuario}' autenticado com sucesso!")
        conn.unbind() # Fecha a conexão LDAP
        return True
        
    except core.exceptions.LDAPBindError as e:
        # Erro específico de credenciais inválidas
        print(f"❌ [AUTH AD] Falha de login para '{usuario}': {e}")
        return False
    except Exception as e:
        # Erros gerais de conexão (Servidor fora do ar, rede, etc)
        print(f"❌ [AUTH AD] Erro LDAP: {e}")
        return False

def CarregarUsuarioFlask(user_id):
    """
    Função vital para o Flask-Login. É chamada a cada requisição (request)
    para recarregar o usuário logado a partir do ID na sessão.
    """
    session_db = Session()
    try:
        # Faz uma consulta unindo Usuario e UsuarioGrupo (Outer Join)
        resultado = session_db.query(Usuario, UsuarioGrupo)\
            .outerjoin(UsuarioGrupo, Usuario.codigo_usuariogrupo == UsuarioGrupo.codigo_usuariogrupo)\
            .filter(Usuario.Codigo_Usuario == user_id)\
            .first()

        if resultado:
            usuario, grupo = resultado
            # Define um nome padrão caso o usuário não tenha grupo
            nome_grupo = grupo.Sigla_UsuarioGrupo if grupo else "Sem Grupo"
            
            # Busca quais menus esse grupo pode acessar
            menus_db = session_db.query(Menu.Nome_Menu)\
                .join(MenuAcesso, Menu.Codigo_Menu == MenuAcesso.Codigo_Menu)\
                .filter(MenuAcesso.Codigo_UsuarioGrupo == usuario.codigo_usuariogrupo)\
                .order_by(Menu.Numero_Menu)\
                .all()
            
            # Transforma o resultado do banco em uma lista simples de strings
            lista_menus = [m.Nome_Menu for m in menus_db]
            
            # Retorna o objeto Wrapper populado
            return UserWrapper(usuario, nome_grupo, lista_menus)
            
    except Exception as e:
        print(f"⚠️ Erro ao recarregar usuário: {e}")
    finally:
        session_db.close()
    
    return None

# --- Rotas de Autenticação ---

@auth_bp.route('/login', methods=['GET', 'POST'])
def Login(): 
    """
    Rota responsável por exibir o formulário (GET) e processar o login (POST).
    """
    if request.method == 'POST':
        # Captura dados do formulário HTML
        username = request.form.get('username')
        password = request.form.get('password')
        
        # --- ETAPA 1: Validação de Credenciais no AD ---
        if AutenticarAd(username, password):
            
            session_db = Session()
            try:
                # --- ETAPA 2: Validação Cadastral no SQL Server ---
                # O usuário precisa existir no banco local da aplicação
                user_db = session_db.query(Usuario).filter_by(Login_Usuario=username).first()
                
                if user_db:
                    # Carrega o objeto completo do usuário
                    usuario_flask = CarregarUsuarioFlask(user_db.Codigo_Usuario)
                    
                    # Loga o usuário no Flask (Cria o cookie de sessão)
                    login_user(usuario_flask)
                    
                    # --- ETAPA 3: Validação de Grupo (Whitelist) ---
                    # Apenas usuários destes grupos específicos podem entrar
                    grupos_permitidos = ['CONTROLADORIA ADMIN', 'CONTROLADORIA BÁSICO', 'GRUPO ADMIN', 'GRUPO TI']
                    
                    if usuario_flask.nome_grupo not in grupos_permitidos:
                        # Se não for do grupo permitido, desloga imediatamente e avisa
                        logout_user()
                        flash('Usuário não possui permissão para acessar o sistema.', 'danger')
                        return redirect(url_for('Auth.Login'))
                    
                    # Sucesso Total
                    flash(f'Bem-vindo(a), {user_db.Nome_Usuario}!', 'success')
                    
                    # Verifica se havia uma página 'next' na URL (usuário tentou acessar pag restrita antes de logar)
                    next_page = request.args.get('next')
                    return redirect(next_page or url_for('Main.Dashboard'))
                    
                else:
                    # Caso: Senha correta (AD), mas não tem cadastro no sistema
                    flash('Login correto (AD), mas usuário não possui cadastro neste sistema.', 'warning')
            
            except Exception as e:
                flash(f'Erro ao validar usuário no banco: {e}', 'danger')
            finally:
                # Sempre fecha a sessão do banco
                session_db.close()
        else:
            # Caso: Senha ou usuário incorretos no AD
            flash('Usuário ou senha inválidos.', 'danger')
            
    # Se for GET, apenas renderiza o template de login
    return render_template('AUTH/Login.html')

@auth_bp.route('/logout')
@login_required # Garante que apenas usuários logados acessem essa rota
def Logout():
    """
    Rota para encerrar a sessão do usuário.
    """
    logout_user() # Limpa o cookie de sessão do Flask
    flash('Você saiu do sistema.', 'info')
    
    # Redireciona para a tela de login (usando o nome do Blueprint 'Auth' e função 'Login')
    return redirect(url_for('Auth.Login'))