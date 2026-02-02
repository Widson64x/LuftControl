from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy 
from flask_migrate import Migrate        
from dotenv import load_dotenv
import os

# --- Imports das Rotas ---
# Importando a função auxiliar que também foi renomeada
from Routes.Autenticacao import auth_bp, CarregarUsuarioFlask
from Routes.MenuPrincipal import main_bp
from Routes.Relatorios import reports_bp
from Routes.ConfiguracaoDre import dre_config_bp
from Routes.OrdenamentoDre import dre_ordem_bp
from Routes.ConfiguracaoSeguranca import security_bp
from Routes.AjustesManuais import ajustes_bp
from Routes.ImportacaoDados import import_bp

# --- Imports Banco de Dados ---
from Db.Connections import PG_DATABASE_URL, CheckConnections
from Models.POSTGRESS.DreEstrutura import Base as DreBase

from Utils.Logger import ConfigurarLogger, RegistrarLog

load_dotenv()

ROUTE_PREFIX = os.getenv("ROUTE_PREFIX", "")

app = Flask(__name__,
            static_url_path=f'{ROUTE_PREFIX}/Static', 
            static_folder='Static')

app.secret_key = os.getenv("SECRET_PASSPHRASE", "40028922") # Chave secreta padrão para desenvolvimento

# --- Configuração SQLAlchemy ---
app.config['SQLALCHEMY_DATABASE_URI'] = PG_DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db, metadata=DreBase.metadata)

# --- Configuração Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)

# ATENÇÃO: Como renomeamos o blueprint para 'Auth' e a função para 'Login', 
# o endpoint mudou de 'auth.login' para 'Auth.Login'.
login_manager.login_view = 'Auth.Login' 
login_manager.login_message = "Por favor, faça login para acessar essa página."
login_manager.login_message_category = "warning"

@login_manager.user_loader
def LoadUser(user_id):
    """Callback do Flask-Login em PascalCase."""
    return CarregarUsuarioFlask(user_id)

# --- Registro de Blueprints ---
app.register_blueprint(auth_bp,        url_prefix=ROUTE_PREFIX + '/Auth')
app.register_blueprint(main_bp,        url_prefix=ROUTE_PREFIX + '/')
app.register_blueprint(reports_bp,     url_prefix=ROUTE_PREFIX + '/Reports')
app.register_blueprint(dre_config_bp,  url_prefix=ROUTE_PREFIX + '/DreConfig')
app.register_blueprint(dre_ordem_bp,   url_prefix=ROUTE_PREFIX + '/DreOrdenamento')
app.register_blueprint(ajustes_bp,     url_prefix=ROUTE_PREFIX + '/Adjustments')
app.register_blueprint(security_bp,    url_prefix=ROUTE_PREFIX + '/SecurityConfig')
app.register_blueprint(import_bp,      url_prefix=ROUTE_PREFIX + '/Import')

@app.route('/')
def Index(): # Até o index merece um PascalCase
    return redirect(url_for('Main.MenuPrincipal'))

if __name__ == "__main__":
    ConfigurarLogger()
    
    RegistrarLog("Verificando conexões...", "System")
    
    bancos_ok = CheckConnections()
    
    if not bancos_ok:
        RegistrarLog("Falha ao conectar nos bancos.", "Critical")
    else:
        RegistrarLog("Bancos conectados.", "Database")
        
    app.run(debug=True, host='0.0.0.0', port=5000)