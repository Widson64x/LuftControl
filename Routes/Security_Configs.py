from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

# Imports de Conexão
from Db.Connections import get_postgres_engine

# Imports dos Modelos e Helpers
from Models.POSTGRESS.Seguranca import SecUserExtension, SecRole, SecPermission
from Utils.Security import requires_permission

security_bp = Blueprint('SecurityConfig', __name__)

def get_pg_session():
    engine = get_postgres_engine()
    return sessionmaker(bind=engine)()

# ============================================================
# VIEWS (Páginas HTML)
# ============================================================

@security_bp.route('/Manager', methods=['GET'])
@login_required
@requires_permission('security.view')
def ViewSecurityManager():
    return render_template('CONFIGS/ConfigsPerms.html')

@security_bp.route('/Visualizador', methods=['GET'])
@login_required
@requires_permission('security.view')
def ViewSecurityMap():
    return render_template('COMPONENTS/SecurityMap.html')

# ============================================================
# API: DADOS DO GRAFO E USUÁRIOS
# ============================================================

@security_bp.route('/API/GetSecurityGraph', methods=['GET'])
@login_required
def GetSecurityGraph():
    pg_session = get_pg_session()
    try:
        nodes = []
        edges = []
        
        # A. Papéis (Roles)
        roles = pg_session.query(SecRole).all()
        for r in roles:
            role_node_id = f"role_{r.Id}"
            nodes.append({
                "id": role_node_id,
                "label": r.Nome,
                "group": "role",
                "title": f"Grupo: {r.Descricao}",
                "value": 25
            })
            
            # Aresta: Grupo -> Permissão
            for perm in r.permissions:
                perm_id = f"perm_{perm.Id}"
                _add_permission_node(nodes, perm)
                edges.append({
                    "from": role_node_id,
                    "to": perm_id,
                    "arrows": "to",
                    "color": {"color": "#6C5CE7", "opacity": 0.4}
                })

        # B. Usuários
        users = pg_session.query(SecUserExtension).all()
        for u in users:
            user_node_id = f"user_{u.Id}"
            nodes.append({
                "id": user_node_id,
                "label": u.Login_Usuario,
                "group": "user",
                "value": 15
            })
            
            if u.RoleId:
                edges.append({
                    "from": user_node_id,
                    "to": f"role_{u.RoleId}",
                    "length": 100,
                    "color": {"color": "#00B894"},
                    "width": 2
                })
            else:
                _add_no_access_node(nodes)
                edges.append({ "from": user_node_id, "to": "no_access", "dashes": [5,5], "color": "#ff7675" })

            # B2. Permissões Diretas
            for direct_perm in u.direct_permissions:
                perm_id = f"perm_{direct_perm.Id}"
                _add_permission_node(nodes, direct_perm)
                edges.append({
                    "from": user_node_id,
                    "to": perm_id,
                    "arrows": "to",
                    "color": {"color": "#fdcb6e"},
                    "dashes": [2, 2]
                })

        return jsonify({"nodes": nodes, "edges": edges}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        pg_session.close()

def _add_permission_node(nodes_list, perm_obj):
    pid = f"perm_{perm_obj.Id}"
    if not any(n['id'] == pid for n in nodes_list):
        nodes_list.append({
            "id": pid,
            "label": perm_obj.Slug,
            "group": "permission",
            "title": perm_obj.Descricao,
            "value": 8
        })

def _add_no_access_node(nodes_list):
    if not any(n['id'] == 'no_access' for n in nodes_list):
        nodes_list.append({ "id": "no_access", "label": "Sem Grupo", "group": "warning", "shape": "triangle", "value": 20 })

@security_bp.route('/API/GetActiveUsers', methods=['GET'])
@login_required
def GetActiveUsers():
    """Retorna apenas usuários que já existem na tabela SEC_Users"""
    pg_session = get_pg_session()
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
# API: GERENCIAMENTO (CRUD) - AS ROTAS QUE FALTAVAM
# ============================================================

@security_bp.route('/API/UpdateUserRole', methods=['POST'])
@login_required
@requires_permission('security.manage')
def UpdateUserRole():
    """Define o Papel (Role) de um usuário específico."""
    pg_session = get_pg_session()
    try:
        data = request.json
        login = data.get('login')
        role_id = data.get('role_id')
        
        user_ext = pg_session.query(SecUserExtension).filter_by(Login_Usuario=login).first()
        
        if not user_ext:
            # Cria se não existir (caso venha do modal visual)
            user_ext = SecUserExtension(Login_Usuario=login)
            pg_session.add(user_ext)
        
        user_ext.RoleId = int(role_id) if role_id else None
        
        pg_session.commit()
        return jsonify({"success": True, "msg": "Perfil atualizado!"}), 200
    except Exception as e:
        pg_session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        pg_session.close()

@security_bp.route('/API/GetRolesAndPermissions', methods=['GET'])
@login_required
def GetRolesAndPermissions():
    """Retorna lista de Roles e Permissões disponíveis"""
    pg_session = get_pg_session()
    try:
        all_perms = pg_session.query(SecPermission).all()
        perms_list = [{"id": p.Id, "slug": p.Slug, "desc": p.Descricao} for p in all_perms]
        
        roles = pg_session.query(SecRole).all()
        roles_data = []
        for r in roles:
            roles_data.append({
                "id": r.Id,
                "nome": r.Nome,
                "descricao": r.Descricao,
                "permissions": [p.Id for p in r.permissions]
            })
            
        return jsonify({"roles": roles_data, "all_permissions": perms_list}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        pg_session.close()

@security_bp.route('/API/SaveRole', methods=['POST'])
@login_required
@requires_permission('security.manage')
def SaveRole():
    """Cria ou Edita um Papel"""
    pg_session = get_pg_session()
    try:
        data = request.json
        role_id = data.get('id')
        nome = data.get('nome')
        descricao = data.get('descricao')
        perm_ids = data.get('permissions', [])
        
        if role_id:
            role = pg_session.query(SecRole).get(role_id)
        else:
            role = SecRole()
            pg_session.add(role)
            
        role.Nome = nome
        role.Descricao = descricao
        
        # Atualiza permissões
        role.permissions = []
        if perm_ids:
            perms = pg_session.query(SecPermission).filter(SecPermission.Id.in_(perm_ids)).all()
            role.permissions = perms
            
        pg_session.commit()
        return jsonify({"success": True, "msg": "Papel salvo!"}), 200
    except Exception as e:
        pg_session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        pg_session.close()

# No final de SecurityConfig.py, adicione/atualize estas rotas:

# --- NOVAS ROTAS DE CRIAÇÃO/EXCLUSÃO ---

@security_bp.route('/API/SavePermission', methods=['POST'])
@login_required
@requires_permission('security.manage')
def SavePermission():
    """Cria ou Edita uma Permissão Avulsa"""
    pg_session = get_pg_session()
    try:
        data = request.json
        slug = data.get('slug')
        descricao = data.get('descricao')
        
        # Verifica duplicidade de Slug na criação
        exists = pg_session.query(SecPermission).filter_by(Slug=slug).first()
        if exists:
            return jsonify({"error": "Já existe uma permissão com este Slug."}), 400

        new_perm = SecPermission(Slug=slug, Descricao=descricao)
        pg_session.add(new_perm)
        pg_session.commit()
        
        return jsonify({"success": True, "msg": "Permissão criada!"}), 200
    except Exception as e:
        pg_session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        pg_session.close()

@security_bp.route('/API/DeleteRole', methods=['POST'])
@login_required
@requires_permission('security.manage')
def DeleteRole():
    """Exclui um Grupo e remove a associação dos usuários"""
    pg_session = get_pg_session()
    try:
        role_id = request.json.get('id')
        role = pg_session.query(SecRole).get(role_id)
        
        if not role:
            return jsonify({"error": "Grupo não encontrado"}), 404
            
        # Opcional: Impedir exclusão se tiver usuários, ou apenas limpar (setar null)
        # O comportamento padrão do SQLAlchemy depende do cascade, 
        # mas aqui vamos forçar a desassociação manual para segurança.
        users = pg_session.query(SecUserExtension).filter_by(RoleId=role_id).all()
        for u in users:
            u.RoleId = None
            
        pg_session.delete(role)
        pg_session.commit()
        return jsonify({"success": True, "msg": "Grupo excluído."}), 200
    except Exception as e:
        pg_session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        pg_session.close()

@security_bp.route('/API/DeletePermission', methods=['POST'])
@login_required
@requires_permission('security.manage')
def DeletePermission():
    """Exclui uma Permissão (remove de todos os grupos e usuários)"""
    pg_session = get_pg_session()
    try:
        perm_id = request.json.get('id')
        perm = pg_session.query(SecPermission).get(perm_id)
        
        if not perm:
            return jsonify({"error": "Permissão não encontrada"}), 404

        # Remover associações diretas de usuários (tabela de associação many-to-many user_permissions)
        # SQLAlchemy gerencia a tabela de associação role_permissions automaticamente se configurado corretamente,
        # mas usuários diretos precisam de atenção se não houver CASCADE configurado no banco.
        
        pg_session.delete(perm)
        pg_session.commit()
        return jsonify({"success": True, "msg": "Permissão removida."}), 200
    except Exception as e:
        pg_session.rollback()
        return jsonify({"error": "Erro ao excluir (possivelmente em uso restrito): " + str(e)}), 500
    finally:
        pg_session.close()
        
@security_bp.route('/API/ToggleDirectPermission', methods=['POST'])
@login_required
@requires_permission('security.manage')
def ToggleDirectPermission():
    """Adiciona ou remove permissão direta de usuário"""
    pg_session = get_pg_session()
    try:
        data = request.json
        user_login = data.get('login') 
        perm_id = data.get('permission_id') 
        action = data.get('action')

        user = pg_session.query(SecUserExtension).filter_by(Login_Usuario=user_login).first()
        perm = pg_session.query(SecPermission).get(perm_id)

        if not user or not perm:
            return jsonify({"error": "Usuário ou Permissão não encontrados"}), 404

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