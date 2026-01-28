from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required

# --- Imports dos Serviços e Helpers ---
from Services.ConfiguracaoSegurancaService import ConfiguracaoSegurancaService
from Utils.Security import RequiresPermission

# Define o Blueprint
security_bp = Blueprint('SecurityConfig', __name__)

# ============================================================
# VIEWS (Páginas HTML)
# ============================================================

@security_bp.route('/manager', methods=['GET'])
@login_required
@RequiresPermission('security.view')
def VisualizarGerenciadorSeguranca():
    """Tela Principal de Gestão de Permissões."""
    return render_template('CONFIGS/ConfigsPerms.html')

@security_bp.route('/visualizador', methods=['GET'])
@login_required
@RequiresPermission('security.view')
def VisualizarMapaSeguranca():
    """Tela Visual do Grafo de Segurança."""
    return render_template('COMPONENTS/SecurityMap.html')

# ============================================================
# API: LEITURA
# ============================================================

@security_bp.route('/api/get-security-graph', methods=['GET'])
@login_required
def ObterGrafoSeguranca():
    try:
        dados = ConfiguracaoSegurancaService.ObterGrafoDeSeguranca()
        return jsonify(dados), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@security_bp.route('/api/get-active-users', methods=['GET'])
@login_required
def ObterUsuariosAtivos():
    try:
        users = ConfiguracaoSegurancaService.ObterUsuariosAtivos()
        return jsonify(users), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@security_bp.route('/api/get-roles-and-permissions', methods=['GET'])
@login_required
def ObterPapeisEPermissoes():
    try:
        dados = ConfiguracaoSegurancaService.ObterPapeisEPermissoes()
        return jsonify(dados), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# API: ESCRITA (Gerenciamento)
# ============================================================

@security_bp.route('/api/update-user-role', methods=['POST'])
@login_required
@RequiresPermission('security.manage')
def AtualizarPapelUsuario():
    try:
        data = request.json
        ConfiguracaoSegurancaService.AtualizarPapelUsuario(
            login=data.get('login'),
            role_id=data.get('role_id')
        )
        return jsonify({"success": True, "msg": "Perfil atualizado com sucesso!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@security_bp.route('/api/save-role', methods=['POST'])
@login_required
@RequiresPermission('security.manage')
def SalvarPapel():
    try:
        data = request.json
        ConfiguracaoSegurancaService.SalvarPapel(
            role_id=data.get('id'),
            nome=data.get('nome'),
            descricao=data.get('descricao'),
            ids_permissoes=data.get('permissions', [])
        )
        return jsonify({"success": True, "msg": "Grupo salvo com sucesso!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@security_bp.route('/api/save-permission', methods=['POST'])
@login_required
@RequiresPermission('security.manage')
def SalvarPermissao():
    try:
        data = request.json
        ConfiguracaoSegurancaService.SalvarPermissao(
            slug=data.get('slug'),
            descricao=data.get('descricao')
        )
        return jsonify({"success": True, "msg": "Permissão criada com sucesso!"}), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@security_bp.route('/api/delete-role', methods=['POST'])
@login_required
@RequiresPermission('security.manage')
def ExcluirPapel():
    try:
        role_id = request.json.get('id')
        ConfiguracaoSegurancaService.ExcluirPapel(role_id)
        return jsonify({"success": True, "msg": "Grupo excluído permanentemente."}), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@security_bp.route('/api/delete-permission', methods=['POST'])
@login_required
@RequiresPermission('security.manage')
def ExcluirPermissao():
    try:
        perm_id = request.json.get('id')
        ConfiguracaoSegurancaService.ExcluirPermissao(perm_id)
        return jsonify({"success": True, "msg": "Permissão removida do sistema."}), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        return jsonify({"error": "Erro ao excluir (Pode estar em uso): " + str(e)}), 500

@security_bp.route('/api/toggle-direct-permission', methods=['POST'])
@login_required
@RequiresPermission('security.manage')
def AlternarPermissaoDireta():
    try:
        data = request.json
        ConfiguracaoSegurancaService.AlternarPermissaoDireta(
            login=data.get('login'),
            perm_id=data.get('permission_id'),
            acao=data.get('action')
        )
        return jsonify({"success": True}), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500