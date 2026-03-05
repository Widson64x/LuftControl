/**
 * SecurityApp.js
 * Arquitetura OOP Completa Integrada com LuftCore e Backend Python.
 */

// ==========================================
// UTILS & API COMUNICATOR
// ==========================================
// ==========================================
// UTILS & API COMUNICATOR
// ==========================================
class SecurityAPI {
    static async get(url) {
        // Adicionamos os headers que servem de "Passaporte" para o @require_ajax
        const res = await fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest', 
                'Accept': 'application/json'
            }
        });
        
        if (!res.ok) throw new Error(`HTTP Error: ${res.status}`);
        
        const json = await res.json();
        
        // Desempacota o formato padrão do LuftCore (api_success)
        // Se a resposta tiver status 'success', devolvemos só o 'data' para o resto do app
        return json.status === 'success' ? json.data : json;
    }
    
    static async post(url, data) {
        // Adicionamos o "Passaporte" no POST também
        const res = await fetch(url, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest' 
            },
            body: JSON.stringify(data)
        });
        
        const json = await res.json();
        
        // Verifica se o LuftCore retornou um 'api_error'
        if (!res.ok || json.status === 'error') {
            throw new Error(json.message || json.error || `HTTP Error: ${res.status}`);
        }
        
        return json.status === 'success' ? (json.data || json) : json;
    }

    static notify(msg, type = 'success') {
        if (window.NotificationSystem) window.NotificationSystem.show(msg, type);
        else alert(`${type.toUpperCase()}: ${msg}`);
    }
}

// ==========================================
// TAB MANAGERS (Classes Especialistas)
// ==========================================

class UserManager {
    constructor(app) {
        this.app = app;
        this.setupListeners();
    }

    setupListeners() {
        document.getElementById('searchUser').addEventListener('input', (e) => this.filter(e.target.value));
    }

    render() {
        const container = document.getElementById('usersListContainer');
        const users = this.app.state.users;
        
        if (!users.length) {
            container.innerHTML = '<div class="text-center text-muted p-6 bg-app rounded-lg border">Nenhum usuário localizado no sistema.</div>';
            return;
        }

        const roleOptions = this.app.state.roles.map(r => `<option value="${r.id}">${r.nome}</option>`).join('');
        const nullOption = `<option value="">-- Acesso Restrito (Sem Grupo) --</option>`;

        let html = '';
        users.forEach(u => {
            const hasDirect = u.direct_permissions && u.direct_permissions.length > 0;
            const badge = hasDirect ? `<span class="luft-badge luft-badge-warning ml-2"><i class="fas fa-exclamation-triangle"></i> Exceção Ativa</span>` : '';

            html += `
            <div class="luft-card p-4 d-grid align-items-center gap-4 hover-lift user-row" style="grid-template-columns: 50px 2fr 1.5fr;" data-search="${u.login.toLowerCase()}">
                <div class="d-flex align-items-center justify-content-center rounded-full bg-primary text-white font-bold text-lg" style="width: 45px; height: 45px;">
                    ${u.login.substring(0,2).toUpperCase()}
                </div>
                <div>
                    <h4 class="text-lg font-bold text-main m-0 d-flex align-items-center">${u.login} ${badge}</h4>
                    <small class="text-muted">ID Sistema: ${u.id}</small>
                </div>
                <div>
                    <select class="form-control text-sm py-2 font-semibold bg-app" onchange="window.SecurityApp.users.changeRole('${u.login}', this.value)">
                        ${nullOption}
                        ${roleOptions.replace(`value="${u.role_id}"`, `value="${u.role_id}" selected`)}
                    </select>
                </div>
            </div>`;
        });
        container.innerHTML = html;
    }

    filter(term) {
        term = term.toLowerCase();
        document.querySelectorAll('.user-row').forEach(row => {
            row.style.display = row.dataset.search.includes(term) ? 'grid' : 'none';
        });
    }

    async changeRole(login, roleId) {
        try {
            await SecurityAPI.post(SECURITY_API_ROUTES.updateUserRole, { login, role_id: roleId });
            SecurityAPI.notify("Perfil de acesso atualizado com sucesso!");
            this.app.syncState(); // Recarrega grafo e dados
        } catch(e) { SecurityAPI.notify(e.message, 'error'); }
    }

    // --- Integração com os Modais vindos do Mapa ---
    
    prepareRoleChangeModal(login, currentRoleId) {
        document.getElementById('targetUserLogin').value = login;
        document.getElementById('lblTargetUser').innerText = login;
        const select = document.getElementById('selectNewRole');
        
        let opts = '<option value="">-- Acesso Restrito (Remover) --</option>';
        this.app.state.roles.forEach(r => opts += `<option value="${r.id}">${r.nome}</option>`);
        select.innerHTML = opts;
        if(currentRoleId) select.value = currentRoleId;

        LuftCore.abrirModal('modalChangeUserRole');
    }

    async saveRoleFromMap() {
        const login = document.getElementById('targetUserLogin').value;
        const roleId = document.getElementById('selectNewRole').value;
        await this.changeRole(login, roleId);
        LuftCore.fecharModal('modalChangeUserRole');
    }

    prepareDirectPermsModal(login, userDirectPermsIds) {
        document.getElementById('directUserLogin').value = login;
        document.getElementById('lblDirectUser').innerText = login;
        
        const select = document.getElementById('selectDirectPerm');
        let opts = '<option value="">Selecione uma permissão base...</option>';
        this.app.state.perms.forEach(p => opts += `<option value="${p.id}">${p.slug} - ${p.desc}</option>`);
        select.innerHTML = opts;

        const list = document.getElementById('listDirectPerms');
        list.innerHTML = '';
        
        if (!userDirectPermsIds || userDirectPermsIds.length === 0) {
            list.innerHTML = '<div class="text-muted text-sm text-center py-6 bg-app rounded-md border border-light">Nenhuma exceção configurada. O usuário segue as regras estritas do seu grupo.</div>';
        } else {
            userDirectPermsIds.forEach(pid => {
                const pInfo = this.app.state.perms.find(p => p.id == pid);
                if(pInfo) {
                    list.innerHTML += `
                    <div class="d-flex justify-content-between align-items-center bg-panel p-3 rounded-md border border-light shadow-sm">
                        <span class="text-sm font-mono text-warning font-bold">${pInfo.slug}</span>
                        <button class="btn btn-outline border-0 text-danger p-1" onclick="window.SecurityApp.users.removeDirectPermission('${login}', ${pid})">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>`;
                }
            });
        }
        LuftCore.abrirModal('modalDirectPerms');
    }

    async addDirectPermission() {
        const login = document.getElementById('directUserLogin').value;
        const permId = document.getElementById('selectDirectPerm').value;
        if(!permId) return;
        await this.toggleDirectPerm(login, permId, 'add');
    }

    async removeDirectPermission(login, permId) {
        await this.toggleDirectPerm(login, permId, 'remove');
    }

    async toggleDirectPerm(login, permId, action) {
        try {
            await SecurityAPI.post(SECURITY_API_ROUTES.toggleDirectPerm, { login, permission_id: permId, action });
            SecurityAPI.notify(action === 'add' ? "Exceção concedida com sucesso." : "Exceção revogada com sucesso.");
            await this.app.syncState();
            
            // Atualiza o modal na tela descobrindo os novos IDs via Grafo ou Estado
            const updatedUser = this.app.state.users.find(u => u.login === login);
            if(updatedUser) this.prepareDirectPermsModal(login, updatedUser.direct_permissions?.map(p=>p.id) || []);
            
        } catch(e) { SecurityAPI.notify(e.message, 'error'); }
    }
}

class RoleManager {
    constructor(app) {
        this.app = app;
        this.setupListeners();
    }

    setupListeners() {
        document.getElementById('filterRolePerms').addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase();
            document.querySelectorAll('.role-perm-item').forEach(el => {
                el.style.display = el.dataset.search.includes(term) ? 'block' : 'none';
            });
        });
    }

    render() {
        const container = document.getElementById('rolesListContainer');
        let html = '';
        this.app.state.roles.forEach(r => {
            html += `
            <div class="luft-card p-6 d-flex flex-col justify-content-between hover-lift border-t-4" style="border-top-color: var(--luft-primary-500)">
                <div>
                    <div class="d-flex justify-content-between align-items-start mb-3">
                        <h3 class="text-xl font-black text-main m-0">${r.nome}</h3>
                        <span class="luft-badge luft-badge-primary bg-primary-light text-primary">${r.permissions.length} perms</span>
                    </div>
                    <p class="text-sm text-muted line-clamp-2">${r.descricao || 'Sem descrição cadastrada.'}</p>
                </div>
                <div class="mt-5 pt-4 border-t border-light d-flex justify-content-end gap-2">
                    <button class="btn btn-outline text-danger border-0 hover-bg-danger-50" onclick="window.SecurityApp.roles.delete(${r.id})">
                        <i class="fas fa-trash"></i>
                    </button>
                    <button class="btn btn-outline text-primary border-primary bg-primary-light" onclick='window.SecurityApp.roles.openEditModal(${JSON.stringify(r)})'>
                        <i class="fas fa-sliders-h"></i> Configurar
                    </button>
                </div>
            </div>`;
        });
        container.innerHTML = html;
    }

    renderCheckboxes(activeIds = []) {
        const container = document.getElementById('rolePermsContainer');
        let html = '';
        const sorted = [...this.app.state.perms].sort((a,b) => a.slug.localeCompare(b.slug));
        
        sorted.forEach(p => {
            const isChecked = activeIds.includes(p.id) ? 'checked' : '';
            html += `
            <label class="luft-perm-check-item d-block role-perm-item" data-search="${p.slug.toLowerCase()} ${p.desc.toLowerCase()}">
                <input type="checkbox" value="${p.id}" ${isChecked} class="chk-role-perm">
                <div class="luft-perm-check-content">
                    <span class="font-mono font-bold text-sm text-main mb-1">${p.slug}</span>
                    <span class="text-xs text-muted leading-tight">${p.desc}</span>
                </div>
            </label>`;
        });
        container.innerHTML = html;
    }

    openCreateModal() {
        document.getElementById('editRoleId').value = '';
        document.getElementById('editRoleName').value = '';
        document.getElementById('editRoleDesc').value = '';
        this.renderCheckboxes([]);
        LuftCore.abrirModal('modalRoleEditor');
    }

    openEditModal(role) {
        document.getElementById('editRoleId').value = role.id;
        document.getElementById('editRoleName').value = role.nome;
        document.getElementById('editRoleDesc').value = role.descricao;
        this.renderCheckboxes(role.permissions);
        LuftCore.abrirModal('modalRoleEditor');
    }

    async save() {
        const id = document.getElementById('editRoleId').value;
        const nome = document.getElementById('editRoleName').value;
        const descricao = document.getElementById('editRoleDesc').value;
        const checkboxes = document.querySelectorAll('.chk-role-perm:checked');
        const permissions = Array.from(checkboxes).map(cb => parseInt(cb.value));

        if(!nome) return SecurityAPI.notify("O Nome do Grupo é obrigatório.", "error");

        try {
            await SecurityAPI.post(SECURITY_API_ROUTES.saveRole, { id, nome, descricao, permissions });
            LuftCore.fecharModal('modalRoleEditor');
            SecurityAPI.notify("Configurações do Grupo salvas com sucesso!");
            this.app.syncState();
        } catch(e) { SecurityAPI.notify(e.message, 'error'); }
    }

    async delete(id) {
        if(!confirm("OPERAÇÃO CRÍTICA: Excluir este grupo removerá o acesso de TODOS os usuários vinculados. Confirma?")) return;
        try {
            await SecurityAPI.post(SECURITY_API_ROUTES.deleteRole, { id });
            SecurityAPI.notify("Grupo excluído com sucesso.");
            this.app.syncState();
        } catch(e) { SecurityAPI.notify(e.message, 'error'); }
    }
}

class PermissionManager {
    constructor(app) {
        this.app = app;
        this.setupListeners();
    }

    setupListeners() {
        document.getElementById('searchPerm').addEventListener('input', (e) => this.filter(e.target.value));
    }

    render() {
        const container = document.getElementById('permsListContainer');
        let html = '';
        const sorted = [...this.app.state.perms].sort((a,b) => a.slug.localeCompare(b.slug));
        
        sorted.forEach(p => {
            html += `
            <div class="d-flex justify-content-between align-items-center p-4 border-b border-light bg-panel hover-lift perm-row" data-search="${p.slug.toLowerCase()}">
                <div class="d-flex align-items-center gap-4">
                    <div class="text-light"><i class="fas fa-cube text-xl"></i></div>
                    <div>
                        <div class="font-mono text-primary font-bold text-base mb-1">${p.slug}</div>
                        <div class="text-sm text-muted">${p.desc}</div>
                    </div>
                </div>
                <button class="btn btn-outline border-0 text-danger hover-bg-danger-50" onclick="window.SecurityApp.perms.delete(${p.id})">
                    <i class="fas fa-trash"></i>
                </button>
            </div>`;
        });
        container.innerHTML = html;
    }

    filter(term) {
        term = term.toLowerCase();
        document.querySelectorAll('.perm-row').forEach(row => {
            row.style.display = row.dataset.search.includes(term) ? 'flex' : 'none';
        });
    }

    openCreateModal() {
        document.getElementById('newPermSlug').value = '';
        document.getElementById('newPermDesc').value = '';
        LuftCore.abrirModal('modalPermEditor');
    }

    async create() {
        const slug = document.getElementById('newPermSlug').value;
        const descricao = document.getElementById('newPermDesc').value;
        if(!slug) return SecurityAPI.notify("O Slug é obrigatório.", "error");

        try {
            await SecurityAPI.post(SECURITY_API_ROUTES.savePerm, { slug, descricao });
            LuftCore.fecharModal('modalPermEditor');
            SecurityAPI.notify("Permissão base registrada com sucesso.");
            this.app.syncState();
        } catch(e) { SecurityAPI.notify(e.message, 'error'); }
    }

    async delete(id) {
        if(!confirm("Atenção Dev: Remover esta permissão vai apagar os vínculos dela em TODOS os grupos. Prosseguir?")) return;
        try {
            await SecurityAPI.post(SECURITY_API_ROUTES.deletePerm, { id });
            SecurityAPI.notify("Permissão excluída do catálogo.");
            this.app.syncState();
        } catch(e) { SecurityAPI.notify(e.message, 'error'); }
    }
}

class MapManager {
    constructor(app) {
        this.app = app;
        this.container = document.getElementById('securityNetwork');
        this.network = null;
        this.nodes = new vis.DataSet([]);
        this.edges = new vis.DataSet([]);
        
        this.options = {
            nodes: {
                shape: 'dot',
                font: { size: 13, color: '#1e293b', face: 'Inter, system-ui', strokeWidth: 3, strokeColor: '#ffffff' },
                borderWidth: 2,
                shadow: { enabled: true, color: 'rgba(0,0,0,0.08)', size: 10, x: 2, y: 4 }
            },
            edges: {
                width: 1.5,
                color: { color: '#cbd5e1', highlight: '#3b82f6', opacity: 0.8 },
                smooth: { type: 'continuous', forceDirection: 'none', roundness: 0.5 }
            },
            physics: {
                stabilization: false,
                barnesHut: { gravitationalConstant: -2500, centralGravity: 0.2, springLength: 120, springConstant: 0.04, damping: 0.09, avoidOverlap: 0.1 }
            },
            interaction: { hover: true, tooltipDelay: 200, hideEdgesOnDrag: true }
        };
    }

    styleNode(node) {
        // Cores LuftCore Estritas
        switch(node.group) {
            case 'role':
                return { ...node, color: { background: '#2563eb', border: '#1d4ed8', highlight: '#60a5fa' }, size: 30, font: { size: 16, color: '#ffffff', strokeWidth: 0 } };
            case 'user':
                return { ...node, color: { background: '#22c55e', border: '#16a34a', highlight: '#4ade80' }, size: 18 };
            case 'permission':
                return { ...node, color: { background: '#f8fafc', border: '#cbd5e1', highlight: '#e2e8f0' }, shape: 'diamond', size: 12, font: { size: 11, color: '#64748b', strokeWidth: 2, strokeColor: '#ffffff' } };
            case 'warning':
                return { ...node, color: { background: '#ef4444', border: '#dc2626', highlight: '#f87171' }, shape: 'triangle', size: 22 };
            default: return node;
        }
    }

    async reloadGraph() {
        const loader = document.getElementById('loaderMap');
        if(loader) loader.classList.remove('d-none');

        try {
            const data = await SecurityAPI.get(SECURITY_API_ROUTES.getGraph);
            const styledNodes = data.nodes.map(n => this.styleNode(n));
            
            this.nodes.clear();
            this.edges.clear();
            this.nodes.add(styledNodes);
            this.edges.add(data.edges);

            if (!this.network) {
                this.network = new vis.Network(this.container, { nodes: this.nodes, edges: this.edges }, this.options);
                this.network.on("oncontext", (p) => this.handleRightClick(p));
                this.network.on("click", () => this.hideContextMenu());
                this.network.on("dragStart", () => this.hideContextMenu());
            } else {
                this.network.fit({ animation: true });
            }
        } catch(e) {
            SecurityAPI.notify("Erro ao processar topologia visual.", "error");
        } finally {
            if(loader) loader.classList.add('d-none');
        }
    }

    handleRightClick(params) {
        params.event.preventDefault();
        const nodeId = this.network.getNodeAt(params.pointer.DOM);
        if (nodeId) {
            this.network.selectNodes([nodeId]);
            this.showContextMenu(nodeId, params.pointer.DOM.x, params.pointer.DOM.y);
        } else {
            this.hideContextMenu();
        }
    }

    showContextMenu(nodeId, x, y) {
        const menu = document.getElementById('contextMenuNetwork');
        const header = document.getElementById('ctxHeader');
        const content = document.getElementById('ctxItems');
        const node = this.nodes.get(nodeId);

        const rect = this.container.getBoundingClientRect();
        menu.style.left = `${x + 10}px`;
        menu.style.top = `${y + 10}px`;
        menu.classList.remove('d-none');
        menu.classList.add('d-block', 'fade-in');

        const btnClass = "btn btn-outline border-0 w-full justify-content-start text-left hover-lift bg-transparent text-main py-2";

        if (node.group === 'user' || node.group === 'warning') {
            header.innerText = `Conta: ${node.label}`;
            
            // Lógica para descobrir Grupo atual pelas arestas
            const edges = this.edges.get({ filter: e => e.from === nodeId });
            const roleEdge = edges.find(e => e.to.startsWith('role_'));
            const currentRoleId = roleEdge ? roleEdge.to.replace('role_', '') : null;
            
            // Lógica para descobrir exceções (arestas diretas com permissão marcadas com dashes no python)
            const directPermsIds = edges.filter(e => e.to.startsWith('perm_') && e.dashes).map(e => e.to.replace('perm_', ''));

            html = `
                <button class="${btnClass}" onclick="window.SecurityApp.users.prepareRoleChangeModal('${node.label}', '${currentRoleId || ''}')">
                    <i class="fas fa-id-badge text-primary" style="width:20px"></i> Modificar Grupo
                </button>
                <button class="${btnClass}" onclick="window.SecurityApp.users.prepareDirectPermsModal('${node.label}', ${JSON.stringify(directPermsIds)})">
                    <i class="fas fa-exclamation-triangle text-warning" style="width:20px"></i> Configurar Exceções
                </button>
            `;
        } else if (node.group === 'role') {
            header.innerText = `Grupo: ${node.label}`;
            const roleObj = this.app.state.roles.find(r => r.id == node.id.replace('role_', ''));
            
            html = `
                <button class="${btnClass}" onclick='window.SecurityApp.roles.openEditModal(${JSON.stringify(roleObj)})'>
                    <i class="fas fa-sliders-h text-info" style="width:20px"></i> Configurar Acessos
                </button>
                <div class="my-1 border-t border-light"></div>
                <button class="${btnClass} text-danger hover-bg-danger-50" onclick="window.SecurityApp.roles.delete(${roleObj.id})">
                    <i class="fas fa-trash text-danger" style="width:20px"></i> Destruir Grupo
                </button>
            `;
        } else {
            header.innerText = `Catálogo`;
            html = `<div class="p-2 text-muted text-sm text-center"><i class="fas fa-server mb-1 d-block text-xl"></i> Nó Base do Sistema</div>`;
        }

        content.innerHTML = html;
    }

    hideContextMenu() {
        const menu = document.getElementById('contextMenuNetwork');
        if(menu) {
            menu.classList.remove('d-block', 'fade-in');
            menu.classList.add('d-none');
        }
    }
}

// ==========================================
// CORE APP (Orquestrador)
// ==========================================
class AppController {
    constructor() {
        this.state = { users: [], roles: [], perms: [] };
        
        // Inicialização dos Managers
        this.users = new UserManager(this);
        this.roles = new RoleManager(this);
        this.perms = new PermissionManager(this);
        this.map = new MapManager(this);

        this.setupNavigation();
    }

    async init() {
        await this.syncState();
    }

    async syncState() {
        try {
            // Paraleliza os fetchs principais de dados em tela
            const [rolesData, usersData] = await Promise.all([
                SecurityAPI.get(SECURITY_API_ROUTES.getRolesPerms),
                SecurityAPI.get(SECURITY_API_ROUTES.getUsers)
            ]);

            this.state.roles = rolesData.roles;
            this.state.perms = rolesData.all_permissions;
            this.state.users = usersData;

            // Manda todos os painéis se re-renderizarem com os novos dados em memória
            this.users.render();
            this.roles.render();
            this.perms.render();
            
            // Se a aba do mapa estiver ativa ou já foi criada, atualiza silenciosamente
            if (document.getElementById('tabMap').classList.contains('d-block') || this.map.network) {
                await this.map.reloadGraph();
            }

        } catch(e) { console.error("Falha Crítica de Sincronização:", e); }
    }

    setupNavigation() {
        const navItems = document.querySelectorAll('.luft-nav-item');
        navItems.forEach(btn => {
            btn.addEventListener('click', (e) => {
                navItems.forEach(b => b.classList.remove('active'));
                const target = e.currentTarget;
                target.classList.add('active');
                
                const tabId = target.dataset.tab;
                document.querySelectorAll('.tab-pane').forEach(tab => {
                    tab.classList.add('d-none');
                    tab.classList.remove('d-block', 'fade-in');
                });
                
                const showTab = document.getElementById(tabId);
                showTab.classList.remove('d-none');
                showTab.classList.add('d-block', 'fade-in');

                // Se abriu o mapa pela primeira vez (ou quer forçar refit)
                if(tabId === 'tabMap') {
                    if(!this.map.network) this.map.reloadGraph();
                    else this.map.network.fit({ animation: true });
                }
            });
        });
    }
}

// Inicialização Global
document.addEventListener('DOMContentLoaded', () => {
    window.SecurityApp = new AppController();
    window.SecurityApp.init();
});