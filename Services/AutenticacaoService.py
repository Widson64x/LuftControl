import os
from flask_login import UserMixin
from sqlalchemy.orm import sessionmaker
from ldap3 import Server, Connection, SIMPLE, core

# --- Imports de Banco de Dados ---
from Db.Connections import GetSqlServerEngine, GetPostgresEngine

# --- Imports dos Modelos ---
from Models.SQL_SERVER.Usuario import Usuario, UsuarioGrupo, MenuAcesso, Menu
from Models.POSTGRESS.Seguranca import SecUserExtension

# --- Import do Logger ---
from Utils.Logger import RegistrarLog

class UsuarioWrapper(UserMixin):
    """
    Classe intermediária que adapta o usuário do Banco de Dados para o formato 
    que o Flask-Login espera. Herda de UserMixin.
    """
    def __init__(self, usuario_db, nome_grupo="", lista_menus=None):
        # Mapeia os dados do objeto do banco (SQL Server)
        self.id = usuario_db.Codigo_Usuario
        self.nome = usuario_db.Login_Usuario
        self.nome_completo = usuario_db.Nome_Usuario
        self.email = usuario_db.Email_Usuario
        self.grupo_id = usuario_db.codigo_usuariogrupo
        
        # Armazena informações de contexto
        self.nome_grupo = nome_grupo
        self.lista_menus = lista_menus if lista_menus is not None else []
        
        # Conjunto para armazenar permissões únicas
        self.all_permissions = set()
        
        # Carrega permissões estendidas do Postgres
        self._CarregarContextoSeguranca()

    def _ObterSessaoPostgres(self):
        """Cria uma sessão isolada para o Postgres."""
        engine_pg = GetPostgresEngine()
        return sessionmaker(bind=engine_pg)()

    def _CarregarContextoSeguranca(self):
        """
        Conecta no Postgres para buscar Roles e Permissions do usuário.
        """
        session_pg = self._ObterSessaoPostgres()
        try:
            # Busca o usuário na tabela de extensão de segurança pelo Login
            pg_user = session_pg.query(SecUserExtension).filter_by(Login_Usuario=self.nome).first()
            if pg_user:
                # 1. Adiciona permissões do Grupo (Role)
                if pg_user.role:
                    for perm in pg_user.role.permissions:
                        self.all_permissions.add(perm.Slug)
                
                # 2. Adiciona permissões diretas (Exceções)
                for perm in pg_user.direct_permissions:
                    self.all_permissions.add(perm.Slug)
        except Exception as e:
            RegistrarLog(f"Erro ao carregar contexto de segurança para {self.nome}", "ERROR", erro=e)
        finally:
            session_pg.close()

    def has_permission(self, slug):
        """
        Verifica se o usuário possui uma permissão específica.
        Admin Master tem acesso irrestrito.
        """
        if 'admin.master' in self.all_permissions:
            return True
        return slug in self.all_permissions


class AutenticacaoService:
    """
    Serviço responsável por toda a lógica de autenticação (LDAP e DB).
    """
    
    def __init__(self):
        # Configurações do AD via variáveis de ambiente
        self.ldap_server = os.getenv("LDAP_SERVER", "luftfarma.com.br")
        self.ldap_domain = os.getenv("LDAP_DOMAIN", "luftfarma")
        
        # Whitelist de grupos permitidos
        self.grupos_permitidos = [
            'CONTROLADORIA ADMIN', 
            'CONTROLADORIA BÁSICO', 
            'GRUPO ADMIN', 
            'GRUPO TI'
        ]

    def _ObterSessaoSqlServer(self):
        """Cria uma sessão para o SQL Server (Dados de Negócio)."""
        engine = GetSqlServerEngine()
        return sessionmaker(bind=engine)()

    def AutenticarNoAd(self, usuario, senha):
        """
        Valida as credenciais no Active Directory.
        Retorna True se sucesso, False caso contrário.
        """
        if not senha:
            return False
            
        full_user = f'{self.ldap_domain}\\{usuario}'
        
        try:
            server = Server(self.ldap_server, port=389, use_ssl=False, get_info=None)
            # auto_bind=True tenta logar imediatamente
            conn = Connection(server, user=full_user, password=senha, authentication=SIMPLE, auto_bind=True)
            
            # Se chegou aqui, logou com sucesso
            conn.unbind()
            return True
            
        except core.exceptions.LDAPBindError:
            RegistrarLog(f"Falha de login no AD para '{usuario}' (Credenciais Inválidas)", "AUTH_FAIL")
            return False
        except Exception as e:
            RegistrarLog(f"Erro de conexão LDAP no servidor {self.ldap_server}", "ERROR", erro=e)
            return False

    def ObterUsuarioPorLogin(self, login_usuario):
        """
        Busca um usuário no banco SQL Server pelo login (string).
        Usado durante o processo de Login.
        """
        session_db = self._ObterSessaoSqlServer()
        try:
            user_db = session_db.query(Usuario).filter_by(Login_Usuario=login_usuario).first()
            return user_db
        except Exception as e:
            RegistrarLog(f"Erro ao buscar usuário por login: {login_usuario}", "ERROR", erro=e)
            raise e
        finally:
            session_db.close()

    def CarregarUsuarioCompleto(self, user_id):
        """
        Carrega o usuário, seu grupo e menus a partir do ID.
        Retorna uma instância de UsuarioWrapper.
        """
        session_db = self._ObterSessaoSqlServer()
        try:
            # Consulta com Outer Join para pegar o Grupo
            resultado = session_db.query(Usuario, UsuarioGrupo)\
                .outerjoin(UsuarioGrupo, Usuario.codigo_usuariogrupo == UsuarioGrupo.codigo_usuariogrupo)\
                .filter(Usuario.Codigo_Usuario == user_id)\
                .first()

            if resultado:
                usuario, grupo = resultado
                nome_grupo = grupo.Sigla_UsuarioGrupo if grupo else "Sem Grupo"
                
                # Busca menus permitidos para este grupo
                menus_db = session_db.query(Menu.Nome_Menu)\
                    .join(MenuAcesso, Menu.Codigo_Menu == MenuAcesso.Codigo_Menu)\
                    .filter(MenuAcesso.Codigo_UsuarioGrupo == usuario.codigo_usuariogrupo)\
                    .order_by(Menu.Numero_Menu)\
                    .all()
                
                lista_menus = [m.Nome_Menu for m in menus_db]
                
                # Retorna o Wrapper pronto para o Flask-Login
                return UsuarioWrapper(usuario, nome_grupo, lista_menus)
                
            return None

        except Exception as e:
            RegistrarLog(f"Erro ao carregar sessão do usuário ID {user_id}", "ERROR", erro=e)
            return None
        finally:
            session_db.close()

    def VerificarPermissaoGrupo(self, nome_grupo):
        """Verifica se o grupo do usuário está na lista de permitidos."""
        return nome_grupo in self.grupos_permitidos