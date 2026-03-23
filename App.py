from flask import Flask, redirect, url_for
from flask_login import LoginManager, current_user
from flask_sqlalchemy import SQLAlchemy 
from flask_migrate import Migrate        
from dotenv import load_dotenv
import os
from luftcore.extensions.flask_extension import LuftCorePackages, LuftUser

# --- Imports das Rotas ---
# Importando a função auxiliar que também foi renomeada
from Modules.DRE.Routes.Autenticacao import auth_bp, CarregarUsuarioFlask
from Modules.DRE.Routes.MenuPrincipal import main_bp
from Modules.DRE.Routes.Relatorios import reports_bp
from Modules.DRE.Routes.ConfiguracaoDre import configuracao_dre_bp
from Modules.DRE.Routes.OrdenamentoDre import dre_ordem_bp
from Modules.DRE.Routes.ConfiguracaoSeguranca import security_bp
from Modules.DRE.Routes.AjustesManuais import ajustes_bp
from Modules.DRE.Routes.ImportacaoDados import import_bp
from Modules.DRE.Routes.Api import api_bp

# --- Imports Banco de Dados ---
from Db.Connections import PG_DATABASE_URL, CheckConnections
from Models.Postgress.CTL_Dre_Estrutura import Base as DreBase
from werkzeug.middleware.proxy_fix import ProxyFix
from Utils.Logger import ConfigurarLogger, RegistrarLog

load_dotenv()

ROUTE_PREFIX = os.getenv("ROUTE_PREFIX", "")

app = Flask(__name__,
            static_url_path=f'{ROUTE_PREFIX}/Static', 
            static_folder='Static')

# === ADICIONE ESTA LINHA AQUI ===
# Diz ao Flask para confiar no cabeçalho X-Forwarded-For (1 nível de proxy)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.secret_key = os.getenv("SECRET_PASSPHRASE", "40028922") # Chave secreta padrão para desenvolvimento

# --- Configuração SQLAlchemy ---
app.config['SQLALCHEMY_DATABASE_URI'] = PG_DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db, metadata=DreBase.metadata)

# --- Configuração Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)

login_manager.login_view = 'Autenticacao.Login' 
login_manager.login_message = "Por favor, faça login para acessar essa página."
login_manager.login_message_category = "warning"

@login_manager.user_loader
def LoadUser(user_id):
    """Callback do Flask-Login em PascalCase."""
    return CarregarUsuarioFlask(user_id)

# ==========================================
# --- INICIALIZAÇÃO DO LUFTCORE ---
# ==========================================

# 1. Mapeamento do Usuário
# O framework vai extrair esses dados do current_user do Flask-Login em cada requisição
gerenciador_usuario = LuftUser(
    callback_usuario=lambda: current_user,
    attr_nome='nome',          # Atributo obrigatório
    email='email',             # Atributos extras mapeados para o front
    cargo='nome_grupo',        # Exemplo: usando o grupo de permissão como 'cargo' no front
    nome_completo='nome_completo'
)

# 2. Injeção do Framework na Aplicação
luftcore_app = LuftCorePackages(
    app=app,
    app_name="Luft Control",
    gerenciador_usuario=gerenciador_usuario,
    inject_theme=True,         # Injeta CSS de temas
    inject_global=True,        # Injeta CSS global estrutural
    inject_animations=True,    # Injeta animações CSS
    inject_js=True,             # Injeta o base.js do LuftCore

    show_topbar=True,         # Se meteres False, a barra de cima desaparece toda
    show_search=False,        # Oculta a barra de pesquisa
    show_notifications=False, # Oculta o botão do sininho
    show_breadcrumb=True      # Mantém os breadcrumbs automáticos ativados
)

# --- Registro de Blueprints ---
app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(api_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(configuracao_dre_bp)
app.register_blueprint(dre_ordem_bp)
app.register_blueprint(ajustes_bp)
app.register_blueprint(security_bp)
app.register_blueprint(import_bp)

@app.route('/')
def Index(): # Até o index merece um PascalCase
    return redirect(url_for('Principal.MenuPrincipal'))

if __name__ == "__main__":
    ConfigurarLogger()
    
    RegistrarLog("Verificando conexões...", "System")
    
    bancos_ok = CheckConnections()
    
    if not bancos_ok:
        RegistrarLog("Falha ao conectar nos bancos.", "Critical")
    else:
        RegistrarLog("Bancos conectados.", "Database")
        
    app.run(debug=True, host='0.0.0.0', port=5000)