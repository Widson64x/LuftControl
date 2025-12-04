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
from Routes.Adjustments import ajustes_bp

# --- IMPORTS PARA BANCO DE DADOS ---
# 1. (ALTERADO) Importamos a URL e agora a função de CHECK
from Db.Connections import PG_DATABASE_URL, check_connections

# 2. Importa a Base dos modelos que queremos migrar (DreEstrutura)
from Models.POSTGRESS.DreEstrutura import Base as DreBase

load_dotenv()

ROUTE_PREFIX = os.getenv("ROUTE_PREFIX", "")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_PASSPHRASE", "chave_dev_super_secreta")

# --- CONFIGURAÇÃO FLASK-SQLALCHEMY & MIGRATE ---
app.config['SQLALCHEMY_DATABASE_URI'] = PG_DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Inicializa o Migrate
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
app.register_blueprint(ajustes_bp, url_prefix=ROUTE_PREFIX + '/Adjustments')
app.register_blueprint(security_bp, url_prefix=ROUTE_PREFIX + '/SecurityConfig')

@app.route('/')
def index():
    return redirect(url_for('main.dashboard'))

if __name__ == "__main__":
    # Chamamos sem parâmetros. Ele vai ler do .env (DB_CONNECT_LOGS)
    # Se quiser forçar ver o log independente do env, use check_connections(verbose=True)
    bancos_ok = check_connections() 

    if not bancos_ok:
        # Nota: Se os logs estiverem desligados (False), 
        # é importante ter um print aqui caso dê erro, senão o app morre em silêncio.
        print("⚠️  [AVISO CRÍTICO] Falha na conexão com Banco de Dados.")
        # exit(1)

    app.run(debug=True, host='0.0.0.0', port=5000)