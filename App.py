from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy 
from flask_migrate import Migrate        
from dotenv import load_dotenv
import os

# Importa as rotas
from Routes.Auth import auth_bp
from Routes.Main import main_bp
from Routes.Reports import reports_bp
from Routes.DreConfig import dre_config_bp
from Routes.DreOrdenamento import dre_ordem_bp
from Routes.Auth import carregar_usuario_flask
from Routes.SecurityConfig import security_bp

# --- IMPORTS PARA BANCO DE DADOS ---
# 1. Importa a string de conexão que já configuramos
from Db.Connections import PG_DATABASE_URL
# 2. Importa a Base dos modelos que queremos migrar (DreEstrutura)
# Isso faz o Python ler o arquivo e registrar as tabelas na memória
from Models.POSTGRESS.DreEstrutura import Base as DreBase

load_dotenv()

ROUTE_PREFIX = os.getenv("ROUTE_PREFIX", "")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_PASSPHRASE", "chave_dev_super_secreta")

# --- CONFIGURAÇÃO FLASK-SQLALCHEMY & MIGRATE ---
# Configura a URI do banco Postgres
app.config['SQLALCHEMY_DATABASE_URI'] = PG_DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializa o objeto DB (Necessário para o Flask-Migrate rodar)
db = SQLAlchemy(app)

# Inicializa o Migrate
# TRUQUE: Passamos 'metadata=DreBase.metadata' para ele olhar para os seus modelos
# Se você tiver mais arquivos de modelos com 'Base' diferentes, precisará unificá-los ou passar via env.py
migrate = Migrate(app, db, metadata=DreBase.metadata)

# --- Configuração do Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = "Por favor, faça login para acessar essa página."
login_manager.login_message_category = "warning"

@login_manager.user_loader
def load_user(user_id):
    return carregar_usuario_flask(user_id)

# --- Registro de Blueprints ---
app.register_blueprint(auth_bp, url_prefix=ROUTE_PREFIX + '/Auth')
app.register_blueprint(main_bp , url_prefix=ROUTE_PREFIX + '/')
app.register_blueprint(reports_bp, url_prefix=ROUTE_PREFIX + '/Reports')
app.register_blueprint(dre_config_bp, url_prefix=ROUTE_PREFIX + '/DreConfig')
app.register_blueprint(dre_ordem_bp, url_prefix=ROUTE_PREFIX + '/DreOrdenamento')
app.register_blueprint(security_bp, url_prefix=ROUTE_PREFIX + '/SecurityConfig')

@app.route('/')
def index():
    return redirect(url_for('main.dashboard'))

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)