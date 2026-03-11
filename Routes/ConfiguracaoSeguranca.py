from flask import Blueprint, request, render_template
from flask_login import login_required

# --- Imports dos Serviços ---
from Services.ConfiguracaoSegurancaService import ConfiguracaoSegurancaService

# --- Imports do LuftCore (O Poder do Framework) ---
from luftcore.extensions.flask_extension import (
    require_permission, 
    require_ajax, 
    api_success, 
    api_error
)

# Define o Blueprint
security_bp = Blueprint('Seguranca', __name__)

# ============================================================
# VIEWS (Páginas HTML)
# ============================================================

@security_bp.route('/gerenciador', methods=['GET'])
@login_required
@require_permission('security.view')
def VisualizarGerenciador():
    """Tela Principal de Gestão de Permissões."""
    return render_template('Pages/Configs/PermissionConfigs.html')

@security_bp.route('/visualizador', methods=['GET'])    
@login_required
@require_permission('security.view')
def VisualizarMapa():
    """Tela Visual do Grafo de Segurança."""
    return render_template('Components/SecurityMap.html')

# ============================================================
# API: LEITURA (Protegido por @require_ajax para impedir acesso via URL)
# ============================================================

@security_bp.route('/api/obter-grafo', methods=['GET'])
@login_required
@require_ajax
def ObterGrafo():
    try:
        dados = ConfiguracaoSegurancaService.ObterGrafoDeSeguranca()
        return api_success(data=dados, message="Grafo carregado com sucesso.")
    except Exception as e:
        return api_error(message="Falha ao carregar o grafo de segurança.", details=str(e), status=500)

@security_bp.route('/api/obter-usuarios', methods=['GET'])
@login_required
@require_ajax
def ObterUsuariosAtivos():
    try:
        users = ConfiguracaoSegurancaService.ObterUsuariosAtivos()
        return api_success(data=users, message="Usuários carregados com sucesso.")
    except Exception as e:
        return api_error(message="Falha ao listar usuários ativos.", details=str(e), status=500)

@security_bp.route('/api/obter-papeis', methods=['GET'])
@login_required
@require_ajax
def ObterPapeisEPermissoes():
    try:
        dados = ConfiguracaoSegurancaService.ObterPapeisEPermissoes()
        return api_success(data=dados, message="Papéis e permissões carregados.")
    except Exception as e:
        return api_error(message="Falha ao obter papéis e permissões.", details=str(e), status=500)

# ============================================================
# API: ESCRITA (Gerenciamento)
# ============================================================

@security_bp.route('/api/atualizar-papel', methods=['POST'])
@login_required
@require_permission('security.manage')
@require_ajax
def AtualizarPapelUsuario():
    try:
        data = request.json
        ConfiguracaoSegurancaService.AtualizarPapelUsuario(
            login=data.get('login'),
            role_id=data.get('role_id')
        )
        return api_success(message="Perfil atualizado com sucesso!")
    except Exception as e:
        return api_error(message="Erro ao atualizar perfil de usuário.", details=str(e), status=500)

@security_bp.route('/api/salvar-papel', methods=['POST'])
@login_required
@require_permission('security.manage')
@require_ajax
def SalvarPapel():
    try:
        data = request.json
        ConfiguracaoSegurancaService.SalvarPapel(
            role_id=data.get('id'),
            nome=data.get('nome'),
            descricao=data.get('descricao'),
            ids_permissoes=data.get('permissions', [])
        )
        return api_success(message="Grupo salvo com sucesso!")
    except Exception as e:
        return api_error(message="Erro ao salvar grupo de permissões.", details=str(e), status=500)

@security_bp.route('/api/salvar-permissao', methods=['POST'])
@login_required
@require_permission('security.manage')
@require_ajax
def SalvarPermissao():
    try:
        data = request.json
        ConfiguracaoSegurancaService.SalvarPermissao(
            slug=data.get('slug'),
            descricao=data.get('descricao')
        )
        return api_success(message="Permissão criada com sucesso!")
    except ValueError as ve:
        return api_error(message="Dados inválidos.", details=str(ve), status=400)
    except Exception as e:
        return api_error(message="Erro ao criar permissão.", details=str(e), status=500)

@security_bp.route('/api/excluir-papel', methods=['POST'])
@login_required
@require_permission('security.manage')
@require_ajax
def ExcluirPapel():
    try:
        role_id = request.json.get('id')
        ConfiguracaoSegurancaService.ExcluirPapel(role_id)
        return api_success(message="Grupo excluído permanentemente.")
    except ValueError as ve:
        return api_error(message="Grupo não encontrado ou protegido.", details=str(ve), status=404)
    except Exception as e:
        return api_error(message="Erro ao excluir grupo.", details=str(e), status=500)

@security_bp.route('/api/excluir-permissao', methods=['POST'])
@login_required
@require_permission('security.manage')
@require_ajax
def ExcluirPermissao():
    try:
        perm_id = request.json.get('id')
        ConfiguracaoSegurancaService.ExcluirPermissao(perm_id)
        return api_success(message="Permissão removida do sistema.")
    except ValueError as ve:
        return api_error(message="Permissão não encontrada ou protegida.", details=str(ve), status=404)
    except Exception as e:
        return api_error(message="Erro ao excluir. Pode estar em uso.", details=str(e), status=500)

@security_bp.route('/api/alternar-permissao', methods=['POST'])
@login_required
@require_permission('security.manage')
@require_ajax
def AlternarPermissaoDireta():
    try:
        data = request.json
        ConfiguracaoSegurancaService.AlternarPermissaoDireta(
            login=data.get('login'),
            perm_id=data.get('permission_id'),
            acao=data.get('action')
        )
        return api_success(message="Permissão direta alterada com sucesso!")
    except ValueError as ve:
        return api_error(message="Usuário ou permissão inválidos.", details=str(ve), status=404)
    except Exception as e:
        return api_error(message="Erro ao alternar permissão.", details=str(e), status=500)