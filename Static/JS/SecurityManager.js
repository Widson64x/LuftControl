/**
 * SecurityManager.js
 * Lógica de gerenciamento de segurança (Users, Roles, Permissions)
 */

const manager = {
    data: {
        users: [],
        roles: [],
        permissions: []
    },

    init() {
        this.loadData();
    },

    async loadData() {
        try {
            // Paraleliza as requisições para performance
            const [resRoles, resUsers] = await Promise.all([
                fetch(API.getRoles),
                fetch(API.getUsers)
            ]);

            const dataRoles = await resRoles.json();
            this.data.roles = dataRoles.roles;
            this.data.permissions = dataRoles.all_permissions; // Lista plana de perms
            this.data.users = await resUsers.json();

            this.renderUsers();
            this.renderRoles();
            this.renderPermissionsList();

        } catch (e) {
            console.error("Erro no load:", e);
            // Fallback para seu sistema de notificação
            if(window.NotificationSystem) NotificationSystem.show("Erro ao carregar dados.", "error");
        }
    },

    switchTab(tabId, btn) {
        document.querySelectorAll('.tab-pane').forEach(el => el.style.display = 'none');
        document.getElementById(tabId).style.display = 'block';
        document.getElementById(tabId).classList.add('fade-in');
        
        document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
        btn.classList.add('active');
    },

    // ==========================================
    // USUÁRIOS
    // ==========================================
    renderUsers() {
        const container = document.getElementById('usersListContainer');
        if (!this.data.users.length) {
            container.innerHTML = '<div class="text-center text-muted p-4">Nenhum usuário encontrado.</div>';
            return;
        }

        // Prepara options do select uma vez
        const roleOptions = this.data.roles.map(r => `<option value="${r.id}">${r.nome}</option>`).join('');
        const nullOption = `<option value="">-- Acesso Limitado (Sem Grupo) --</option>`;

        let html = '';
        this.data.users.forEach(u => {
            const hasDirect = u.direct_permissions && u.direct_permissions.length > 0;
            const directBadge = hasDirect ? 
                `<span class="badge badge-warning ms-2" title="Permissões manuais adicionadas"><i class="fas fa-exclamation-triangle"></i> Exceção</span>` : '';

            html += `
            <div class="user-card" data-search="${u.login.toLowerCase()}">
                <div class="user-avatar">${u.login.substring(0,2).toUpperCase()}</div>
                <div>
                    <h4 class="m-0 text-white">${u.login} ${directBadge}</h4>
                    <small class="text-secondary">ID: ${u.id}</small>
                </div>
                <div>
                    <select class="form-select form-select-sm" onchange="manager.updateUserRole('${u.login}', this.value)">
                        ${nullOption}
                        ${roleOptions.replace(`value="${u.role_id}"`, `value="${u.role_id}" selected`)}
                    </select>
                </div>
            </div>`;
        });
        container.innerHTML = html;
    },

    filterUsers() {
        const term = document.getElementById('searchUser').value.toLowerCase();
        document.querySelectorAll('.user-card').forEach(el => {
            el.style.display = el.dataset.search.includes(term) ? 'grid' : 'none';
        });
    },

    async updateUserRole(login, roleId) {
        try {
            const res = await fetch(API.updateUserRole, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ login, role_id: roleId })
            });
            if(res.ok) this.notify("Perfil de usuário atualizado!");
            else this.notify("Erro ao atualizar.", "error");
        } catch(e) { console.error(e); }
    },

    // ==========================================
    // GRUPOS (ROLES)
    // ==========================================
    renderRoles() {
        const container = document.getElementById('rolesListContainer');
        let html = '';
        this.data.roles.forEach(r => {
            html += `
            <div class="role-card">
                <div>
                    <div class="d-flex justify-between align-start mb-2">
                        <h3 class="h5 m-0 text-primary">${r.nome}</h3>
                        <span class="badge badge-secondary">${r.permissions.length} perms</span>
                    </div>
                    <p class="text-sm text-secondary line-clamp-2">${r.descricao || 'Sem descrição.'}</p>
                </div>
                <div class="role-actions">
                    <button class="btn btn-sm btn-ghost text-danger" onclick="manager.deleteRole(${r.id})">
                        <i class="fas fa-trash"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-primary" onclick='manager.editRole(${JSON.stringify(r)})'>
                        <i class="fas fa-edit me-1"></i> Editar
                    </button>
                </div>
            </div>`;
        });
        container.innerHTML = html;
    },

    openRoleModal() {
        document.getElementById('roleId').value = '';
        document.getElementById('roleName').value = '';
        document.getElementById('roleDesc').value = '';
        this.renderPermCheckboxes([]); // Renderiza limpo
        openModal('modalRole');
    },

    editRole(role) {
        document.getElementById('roleId').value = role.id;
        document.getElementById('roleName').value = role.nome;
        document.getElementById('roleDesc').value = role.descricao;
        this.renderPermCheckboxes(role.permissions);
        openModal('modalRole');
    },

    async deleteRole(id) {
        if(!confirm("Tem certeza? Usuários neste grupo perderão o acesso.")) return;
        
        try {
            const res = await fetch(API.deleteRole, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ id })
            });
            if(res.ok) {
                this.notify("Grupo excluído.");
                this.loadData();
            } else {
                const err = await res.json();
                alert(err.error);
            }
        } catch(e) { console.error(e); }
    },

    // Renderiza grid de checkboxes dentro do Modal de Role
    renderPermCheckboxes(activeIds) {
        const container = document.getElementById('permissionsCheckGrid');
        let html = '';
        // Ordena alfabeticamente pelo slug
        const sortedPerms = [...this.data.permissions].sort((a,b) => a.slug.localeCompare(b.slug));

        sortedPerms.forEach(p => {
            const isChecked = activeIds.includes(p.id) ? 'checked' : '';
            html += `
            <label class="perm-check-item" data-search="${p.slug.toLowerCase()} ${p.desc.toLowerCase()}">
                <input type="checkbox" value="${p.id}" ${isChecked} class="role-perm-checkbox">
                <div class="perm-check-content">
                    <span class="perm-slug text-primary">${p.slug}</span>
                    <span class="perm-desc">${p.desc}</span>
                </div>
            </label>`;
        });
        container.innerHTML = html;
    },

    filterPermChecks(term) {
        term = term.toLowerCase();
        document.querySelectorAll('.perm-check-item').forEach(el => {
            el.style.display = el.dataset.search.includes(term) ? 'block' : 'none';
        });
    },

    async saveRole() {
        const id = document.getElementById('roleId').value;
        const nome = document.getElementById('roleName').value;
        const descricao = document.getElementById('roleDesc').value;
        
        // Coleta IDs marcados
        const checkboxes = document.querySelectorAll('.role-perm-checkbox:checked');
        const permissions = Array.from(checkboxes).map(cb => parseInt(cb.value));

        if(!nome) return alert("Nome é obrigatório");

        try {
            const res = await fetch(API.saveRole, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ id, nome, descricao, permissions })
            });
            
            if(res.ok) {
                closeModals();
                this.notify("Grupo salvo com sucesso!");
                this.loadData();
            } else {
                alert("Erro ao salvar.");
            }
        } catch(e) { console.error(e); }
    },

    // ==========================================
    // PERMISSÕES
    // ==========================================
    renderPermissionsList() {
        const container = document.getElementById('permsListContainer');
        let html = '';
        // Ordena por slug
        this.data.permissions.sort((a,b) => a.slug.localeCompare(b.slug)).forEach(p => {
            html += `
            <div class="perm-row" data-search="${p.slug.toLowerCase()}">
                <div>
                    <div class="font-monospace text-primary fw-bold">${p.slug}</div>
                    <div class="text-sm text-secondary">${p.desc}</div>
                </div>
                <button class="btn btn-xs btn-ghost text-danger" onclick="manager.deletePermission(${p.id})">
                    <i class="fas fa-trash"></i>
                </button>
            </div>`;
        });
        container.innerHTML = html;
    },

    filterPermList(term) {
        term = term.toLowerCase();
        document.querySelectorAll('.perm-row').forEach(row => {
            row.style.display = row.dataset.search.includes(term) ? 'flex' : 'none';
        });
    },

    openPermModal() {
        document.getElementById('newPermSlug').value = '';
        document.getElementById('newPermDesc').value = '';
        openModal('modalPerm');
    },

    async createPermission() {
        const slug = document.getElementById('newPermSlug').value;
        const descricao = document.getElementById('newPermDesc').value;
        
        if(!slug) return alert("Slug é obrigatório");

        try {
            const res = await fetch(API.savePerm, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ slug, descricao })
            });
            const json = await res.json();
            
            if(res.ok) {
                closeModals();
                this.notify("Permissão criada!");
                this.loadData();
            } else {
                alert(json.error || "Erro ao criar.");
            }
        } catch(e) { console.error(e); }
    },

    async deletePermission(id) {
        if(!confirm("ATENÇÃO: Isso removerá esta permissão de TODOS os grupos e usuários. Continuar?")) return;

        try {
            const res = await fetch(API.deletePerm, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ id })
            });
            if(res.ok) {
                this.notify("Permissão removida.");
                this.loadData();
            } else {
                alert("Erro ao remover.");
            }
        } catch(e) { console.error(e); }
    },

    // Helper simples de Toast/Notificação
    notify(msg, type='success') {
        if(window.NotificationSystem) window.NotificationSystem.show(msg, type);
        else alert(msg);
    }
};

// --- Globais de Modal ---
function openModal(id) {
    const el = document.getElementById(id);
    if(el) { el.style.display = 'flex'; setTimeout(() => el.classList.add('active'), 10); }
}
function closeModals() {
    document.querySelectorAll('.modal-overlay').forEach(el => {
        el.classList.remove('active');
        setTimeout(() => el.style.display = 'none', 300);
    });
}

document.addEventListener('DOMContentLoaded', () => manager.init());