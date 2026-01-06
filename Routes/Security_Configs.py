from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

# --- Imports de Conexão ---
from Db.Connections import GetPostgresEngine

# --- Imports dos Modelos e Helpers ---
from Models.POSTGRESS.Seguranca import SecUserExtension, SecRole, SecPermission
# Importa o nosso novo decorator em PascalCase
from Utils.Security import RequiresPermission

# Define o Blueprint com nome elegante
security_bp = Blueprint('SecurityConfig', __name__)

def GetPgSession():
    """Cria uma sessão isolada para transações de segurança no Postgres."""
    engine = GetPostgresEngine()
    return sessionmaker(bind=engine)()

# ============================================================
# VIEWS (Páginas HTML para o Usuário Final)
# ============================================================

@security_bp.route('/manager', methods=['GET'])
@login_required
@RequiresPermission('security.view')
def ViewSecurityManager():
    """Tela Principal de Gestão de Permissões (Matriz)"""
    return render_template('CONFIGS/ConfigsPerms.html')

@security_bp.route('/visualizador', methods=['GET'])
@login_required
@RequiresPermission('security.view')
def ViewSecurityMap():
    """Tela Visual do Grafo de Segurança (Nodes e Edges)"""
    return render_template('COMPONENTS/SecurityMap.html')

# ============================================================
# API: DADOS DO GRAFO E USUÁRIOS (Leitura)
# ============================================================

@security_bp.route('/api/get-security-graph', methods=['GET'])
@login_required
def GetSecurityGraph():
    """
    Retorna a estrutura de nós e arestas para desenhar o grafo visual.
    Mostra quem é quem e quem pode o quê.
    """
    pg_session = GetPgSession()
    try:
        nodes = []
        edges = []
        
        # A. Processa Papéis (Roles) - Os grupos de permissão
        roles = pg_session.query(SecRole).all()
        for r in roles:
            role_node_id = f"role_{r.Id}"
            nodes.append({
                "id": role_node_id,
                "label": r.Nome,
                "group": "role",
                "title": f"Grupo: {r.Descricao}",
                "value": 25 # Tamanho visual do nó
            })
            
            # Cria linhas conectando Grupo -> Permissão
            for perm in r.permissions:
                perm_id = f"perm_{perm.Id}"
                _AddPermissionNode(nodes, perm) # Garante que o nó da permissão existe
                edges.append({
                    "from": role_node_id,
                    "to": perm_id,
                    "arrows": "to",
                    "color": {"color": "#6C5CE7", "opacity": 0.4}
                })

        # B. Processa Usuários
        users = pg_session.query(SecUserExtension).all()
        for u in users:
            user_node_id = f"user_{u.Id}"
            nodes.append({
                "id": user_node_id,
                "label": u.Login_Usuario,
                "group": "user",
                "value": 15
            })
            
            # Conecta Usuário -> Grupo (Role)
            if u.RoleId:
                edges.append({
                    "from": user_node_id,
                    "to": f"role_{u.RoleId}",
                    "length": 100,
                    "color": {"color": "#00B894"},
                    "width": 2
                })
            else:
                # Se não tem grupo, conecta num nó de alerta "Sem Acesso"
                _AddNoAccessNode(nodes)
                edges.append({ "from": user_node_id, "to": "no_access", "dashes": [5,5], "color": "#ff7675" })

            # B2. Conecta Usuário -> Permissões Diretas (Exceções)
            for direct_perm in u.direct_permissions:
                perm_id = f"perm_{direct_perm.Id}"
                _AddPermissionNode(nodes, direct_perm)
                edges.append({
                    "from": user_node_id,
                    "to": perm_id,
                    "arrows": "to",
                    "color": {"color": "#fdcb6e"}, # Cor diferente para destacar que é direto
                    "dashes": [2, 2] # Linha tracejada
                })

        return jsonify({"nodes": nodes, "edges": edges}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        pg_session.close()

# --- Funções Auxiliares Privadas (para montar o grafo) ---

def _AddPermissionNode(nodes_list, perm_obj):
    """Adiciona um nó de permissão à lista se ele ainda não existir."""
    pid = f"perm_{perm_obj.Id}"
    if not any(n['id'] == pid for n in nodes_list):
        nodes_list.append({
            "id": pid,
            "label": perm_obj.Slug,
            "group": "permission",
            "title": perm_obj.Descricao,
            "value": 8
        })

def _AddNoAccessNode(nodes_list):
    """Adiciona o nó triangular de alerta 'Sem Grupo'."""
    if not any(n['id'] == 'no_access' for n in nodes_list):
        nodes_list.append({ "id": "no_access", "label": "Sem Grupo", "group": "warning", "shape": "triangle", "value": 20 })

@security_bp.route('/api/get-active-users', methods=['GET'])
@login_required
def GetActiveUsers():
    """Lista usuários cadastrados na tabela de extensão de segurança."""
    pg_session = GetPgSession()
    try:
        users = pg_session.query(SecUserExtension).all()
        result = []
        for u in users:
            perms_diretas = [p.Id for p in u.direct_permissions]
            result.append({
                "id": u.Id,
                "login": u.Login_Usuario,
                "role_id": u.RoleId,
                "role_name": u.role.Nome if u.role else "Sem Grupo",
                "direct_permissions": perms_diretas
            })
        return jsonify(result), 200
    finally:
        pg_session.close()

# ============================================================
# API: GERENCIAMENTO (CRUD - Escrita)
# ============================================================

@security_bp.route('/api/update-user-role', methods=['POST'])
@login_required
@RequiresPermission('security.manage')
def UpdateUserRole():
    """Define ou altera o Papel (Role) de um usuário."""
    pg_session = GetPgSession()
    try:
        data = request.json
        login = data.get('login')
        role_id = data.get('role_id')
        
        user_ext = pg_session.query(SecUserExtension).filter_by(Login_Usuario=login).first()
        
        if not user_ext:
            # Se o usuário não existia na tabela de segurança, cria agora.
            user_ext = SecUserExtension(Login_Usuario=login)
            pg_session.add(user_ext)
        
        # Converte para int se existir valor, senão fica None (sem grupo)
        user_ext.RoleId = int(role_id) if role_id else None
        
        pg_session.commit()
        return jsonify({"success": True, "msg": "Perfil atualizado com sucesso!"}), 200
    except Exception as e:
        pg_session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        pg_session.close()

@security_bp.route('/api/get-roles-and-permissions', methods=['GET'])
@login_required
def GetRolesAndPermissions():
    """
    Retorna todos os Grupos e todas as Permissões do sistema.
    Usado para preencher os selects e modais do frontend.
    """
    pg_session = GetPgSession()
    try:
        # Busca todas as permissões
        all_perms = pg_session.query(SecPermission).all()
        perms_list = [{"id": p.Id, "slug": p.Slug, "desc": p.Descricao} for p in all_perms]
        
        # Busca todos os grupos
        roles = pg_session.query(SecRole).all()
        roles_data = []
        for r in roles:
            roles_data.append({
                "id": r.Id,
                "nome": r.Nome,
                "descricao": r.Descricao,
                "permissions": [p.Id for p in r.permissions] # Lista de IDs para facilitar o check no front
            })
            
        return jsonify({"roles": roles_data, "all_permissions": perms_list}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        pg_session.close()

@security_bp.route('/api/save-role', methods=['POST'])
@login_required
@RequiresPermission('security.manage')
def SaveRole():
    """Cria um novo Grupo ou edita um existente."""
    pg_session = GetPgSession()
    try:
        data = request.json
        role_id = data.get('id')
        nome = data.get('nome')
        descricao = data.get('descricao')
        perm_ids = data.get('permissions', [])
        
        if role_id:
            # Edição
            role = pg_session.query(SecRole).get(role_id)
        else:
            # Criação
            role = SecRole()
            pg_session.add(role)
            
        role.Nome = nome
        role.Descricao = descricao
        
        # Atualiza a lista de permissões do grupo
        # Primeiro limpa, depois adiciona as selecionadas
        role.permissions = []
        if perm_ids:
            perms = pg_session.query(SecPermission).filter(SecPermission.Id.in_(perm_ids)).all()
            role.permissions = perms
            
        pg_session.commit()
        return jsonify({"success": True, "msg": "Grupo salvo com sucesso!"}), 200
    except Exception as e:
        pg_session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        pg_session.close()

@security_bp.route('/api/save-permission', methods=['POST'])
@login_required
@RequiresPermission('security.manage')
def SavePermission():
    """Cria uma nova Permissão no sistema (ex: 'relatorios.exportar')."""
    pg_session = GetPgSession()
    try:
        data = request.json
        slug = data.get('slug')
        descricao = data.get('descricao')
        
        # Verifica se já não existe uma com o mesmo nome técnico (Slug)
        exists = pg_session.query(SecPermission).filter_by(Slug=slug).first()
        if exists:
            return jsonify({"error": "Ops! Já existe uma permissão com este Slug."}), 400

        new_perm = SecPermission(Slug=slug, Descricao=descricao)
        pg_session.add(new_perm)
        pg_session.commit()
        
        return jsonify({"success": True, "msg": "Permissão criada com sucesso!"}), 200
    except Exception as e:
        pg_session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        pg_session.close()

@security_bp.route('/api/delete-role', methods=['POST'])
@login_required
@RequiresPermission('security.manage')
def DeleteRole():
    """Exclui um Grupo e solta os usuários que estavam nele (ficam sem grupo)."""
    pg_session = GetPgSession()
    try:
        role_id = request.json.get('id')
        role = pg_session.query(SecRole).get(role_id)
        
        if not role:
            return jsonify({"error": "Grupo não encontrado."}), 404
            
        # Remove a associação dos usuários antes de deletar o grupo
        users = pg_session.query(SecUserExtension).filter_by(RoleId=role_id).all()
        for u in users:
            u.RoleId = None
            
        pg_session.delete(role)
        pg_session.commit()
        return jsonify({"success": True, "msg": "Grupo excluído permanentemente."}), 200
    except Exception as e:
        pg_session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        pg_session.close()

@security_bp.route('/api/delete-permission', methods=['POST'])
@login_required
@RequiresPermission('security.manage')
def DeletePermission():
    """Exclui uma Permissão do sistema (remove de todos os grupos e usuários)."""
    pg_session = GetPgSession()
    try:
        perm_id = request.json.get('id')
        perm = pg_session.query(SecPermission).get(perm_id)
        
        if not perm:
            return jsonify({"error": "Permissão não encontrada."}), 404

        # O SQLAlchemy cuida da tabela de associação Many-to-Many se estiver bem configurado.
        # Caso contrário, seria necessário limpar manualmente as tabelas de ligação.
        pg_session.delete(perm)
        pg_session.commit()
        return jsonify({"success": True, "msg": "Permissão removida do sistema."}), 200
    except Exception as e:
        pg_session.rollback()
        return jsonify({"error": "Erro ao excluir (Pode estar em uso): " + str(e)}), 500
    finally:
        pg_session.close()
        
@security_bp.route('/api/toggle-direct-permission', methods=['POST'])
@login_required
@RequiresPermission('security.manage')
def ToggleDirectPermission():
    """
    Adiciona ou remove uma permissão direta de um usuário específico.
    Isso cria exceções (o usuário pode algo que o grupo dele não pode).
    """
    pg_session = GetPgSession()
    try:
        data = request.json
        user_login = data.get('login') 
        perm_id = data.get('permission_id') 
        action = data.get('action') # 'add' ou 'remove'

        user = pg_session.query(SecUserExtension).filter_by(Login_Usuario=user_login).first()
        perm = pg_session.query(SecPermission).get(perm_id)

        if not user or not perm:
            return jsonify({"error": "Usuário ou Permissão não encontrados."}), 404

        if action == 'add':
            if perm not in user.direct_permissions:
                user.direct_permissions.append(perm)
        elif action == 'remove':
            if perm in user.direct_permissions:
                user.direct_permissions.remove(perm)

        pg_session.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        pg_session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        pg_session.close()