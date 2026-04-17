import os
from flask_login import UserMixin
from sqlalchemy.orm import sessionmaker
from ldap3 import Server, Connection, SIMPLE, core

# --- Imports de Banco de Dados ---
from Db.Connections import GetSqlServerEngine, GetPostgresEngine

# --- Imports dos Modelos ---
from Models.SqlServer.Usuario import Usuario, UsuarioGrupo, MenuAcesso, Menu
from Models.Postgress.CTL_Seguranca import CtlSegUsuario # ATUALIZADO

# --- Import do Logger ---
from Utils.Logger import RegistrarLog

# --- Import do Serviço de Permissões ---
from Modules.SISTEMA.Services.PermissaoService import PermissaoService

class UsuarioWrapper(UserMixin):
    def __init__(self, usuario_db, nome_grupo="", lista_menus=None):
        self.id = usuario_db.Codigo_Usuario
        self.nome = usuario_db.Login_Usuario
        self.nome_completo = usuario_db.Nome_Usuario
        self.email = usuario_db.Email_Usuario
        self.grupo_id = usuario_db.codigo_usuariogrupo
        
        self.nome_grupo = nome_grupo
        self.lista_menus = lista_menus if lista_menus is not None else []
        self.all_permissions = set()
        
        self._CarregarContextoSeguranca()

    def _ObterSessaoPostgres(self):
        engine_pg = GetPostgresEngine()
        return sessionmaker(bind=engine_pg)()

    def _CarregarContextoSeguranca(self):
        session_pg = self._ObterSessaoPostgres()
        try:
            # ATUALIZADO: SecUserExtension para CtlSegUsuario
            pg_user = session_pg.query(CtlSegUsuario).filter_by(Login_Usuario=self.nome).first()
            if pg_user:
                if pg_user.perfil: # <--- CORRIGIDO PARA 'perfil'
                    for perm in pg_user.perfil.permissions: # <--- CORRIGIDO PARA 'perfil'
                        self.all_permissions.add(perm.Slug)
                for perm in pg_user.direct_permissions:
                    self.all_permissions.add(perm.Slug)
        except Exception as e:
            RegistrarLog(f"Erro ao carregar contexto de segurança para {self.nome}", "ERROR", erro=e)
        finally:
            session_pg.close()

    def has_permission(self, slug):
        if 'admin.master' in self.all_permissions:
            return True
        return slug in self.all_permissions

class AutenticacaoService:
    def __init__(self):
        self.ldap_server = os.getenv("LDAP_SERVER", "luftfarma.com.br")
        self.ldap_domain = os.getenv("LDAP_DOMAIN", "luftfarma")

    def _ObterSessaoSqlServer(self):
        engine = GetSqlServerEngine()
        return sessionmaker(bind=engine)()

    def AutenticarNoAd(self, usuario, senha):
        if not senha: return False
        full_user = f'{self.ldap_domain}\\{usuario}'
        try:
            server = Server(self.ldap_server, port=389, use_ssl=False, get_info=None)
            conn = Connection(server, user=full_user, password=senha, authentication=SIMPLE, auto_bind=True)
            conn.unbind()
            return True
        except core.exceptions.LDAPBindError:
            return False
        except Exception as e:
            return False

    def ObterUsuarioPorLogin(self, login_usuario):
        session_db = self._ObterSessaoSqlServer()
        try:
            return session_db.query(Usuario).filter_by(Login_Usuario=login_usuario).first()
        finally:
            session_db.close()

    def CarregarUsuarioCompleto(self, user_id):
        session_db = self._ObterSessaoSqlServer()
        try:
            resultado = session_db.query(Usuario, UsuarioGrupo)\
                .outerjoin(UsuarioGrupo, Usuario.codigo_usuariogrupo == UsuarioGrupo.codigo_usuariogrupo)\
                .filter(Usuario.Codigo_Usuario == user_id)\
                .first()

            if resultado:
                usuario, grupo = resultado
                nome_grupo = grupo.Sigla_UsuarioGrupo if grupo else "Sem Grupo"
                menus_db = session_db.query(Menu.Nome_Menu)\
                    .join(MenuAcesso, Menu.Codigo_Menu == MenuAcesso.Codigo_Menu)\
                    .filter(MenuAcesso.Codigo_UsuarioGrupo == usuario.codigo_usuariogrupo)\
                    .order_by(Menu.Numero_Menu)\
                    .all()
                lista_menus = [m.Nome_Menu for m in menus_db]
                return UsuarioWrapper(usuario, nome_grupo, lista_menus)
            return None
        finally:
            session_db.close()

    def VerificarAcessoSistema(self, usuario_flask):
        """Verifica se o usuário tem ao menos a permissão HOME.VISUALIZAR no banco de dados."""
        return PermissaoService.VerificarPermissao(usuario_flask, 'HOME.VISUALIZAR')