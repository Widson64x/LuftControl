from flask import Flask, redirect, url_for
from flask_login import LoginManager
from dotenv import load_dotenv
import os

# Importa as rotas (Blueprints)
from Routes.Auth import auth_bp
from Routes.Main import main_bp
from Routes.Reports import reports_bp

# Carrega variáveis de ambiente
load_dotenv()

app = Flask(__name__)

# Configuração de Segredo (Necessário para Sessões e Flash Messages)
# Se não tiver no .env, usa uma chave padrão insegura para dev
app.secret_key = os.getenv("SECRET_PASSPHRASE", "chave_dev_super_secreta")

# --- Configuração do Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login' # Nome da função da rota de login
login_manager.login_message = "Por favor, faça login para acessar essa página."
login_manager.login_message_category = "warning"

# Função para carregar o usuário (callback do Flask-Login)
# Importamos aqui para evitar ciclo de importação no topo
from Routes.Auth import carregar_usuario_flask
@login_manager.user_loader
def load_user(user_id):
    return carregar_usuario_flask(user_id)

# --- Registro de Blueprints (Rotas) ---
app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(reports_bp, url_prefix='/Reports')

# Rota raiz redireciona para o dashboard (que vai pedir login se não tiver)
@app.route('/')
def index():
    return redirect(url_for('main.dashboard'))

if __name__ == "__main__":
    # Rodar em modo debug
    app.run(debug=True, host='0.0.0.0', port=5000)