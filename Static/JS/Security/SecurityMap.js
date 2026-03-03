/**
 * SecurityMap.js
 * Gerenciamento Avançado do Mapa de Segurança com Vis.js e CRUD integrado.
 */

class SecurityNetwork {
    constructor() {
        this.container = document.getElementById('securityNetwork');
        if (!this.container) return;

        this.network = null;
        // Datasets do Vis.js permitem manipulação dinâmica sem recarregar tudo
        this.nodes = new vis.DataSet([]);
        this.edges = new vis.DataSet([]);
        
        this.rolesCache = [];
        this.permsCache = [];

        // Opções Visuais "Dark Theme Tech"
        this.options = {
            nodes: {
                shape: 'dot',
                font: { size: 14, color: '#ffffff', face: 'Inter, sans-serif', strokeWidth: 3, strokeColor: '#1e1e24' },
                borderWidth: 2,
                shadow: { enabled: true, color: 'rgba(0,0,0,0.5)', size: 10, x: 5, y: 5 }
            },
            edges: {
                width: 1.5,
                color: { color: '#4b5563', highlight: '#6C5CE7', opacity: 0.4 },
                smooth: { type: 'continuous', forceDirection: 'none', roundness: 0.5 }
            },
            physics: {
                stabilization: false,
                barnesHut: {
                    gravitationalConstant: -3000,
                    centralGravity: 0.1,
                    springLength: 150,
                    springConstant: 0.03,
                    damping: 0.09,
                    avoidOverlap: 0.2
                }
            },
            interaction: { 
                hover: true, 
                tooltipDelay: 200,
                hideEdgesOnDrag: true,
                multiselect: false
            }
        };

        this.init();
    }

    async init() {
        await this.loadMetadata(); // Carrega Roles e Perms para os Modais
        await this.loadGraphData();
        
        // Listener global para fechar menu de contexto ao clicar fora
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.ctx-menu')) this.hideContextMenu();
        });
    }

    // --- CARREGAMENTO DE DADOS ---

    async loadMetadata() {
        try {
            const res = await fetch(API.getRoles);
            const json = await res.json();
            this.rolesCache = json.roles;
            this.permsCache = json.all_permissions;
        } catch(e) { console.error("Erro metadata:", e); }
    }

    async loadGraphData() {
        const loader = document.getElementById('loader');
        if(loader) loader.style.opacity = '1';

        try {
            const res = await fetch(API.getData);
            const json = await res.json();

            // Pré-processamento visual dos nós
            const styledNodes = json.nodes.map(n => this.styleNode(n));

            this.nodes.clear();
            this.edges.clear();
            this.nodes.add(styledNodes);
            this.edges.add(json.edges);

            if (!this.network) {
                this.createNetwork();
            } else {
                // Se já existe, apenas estabiliza
                this.network.fit({ animation: true });
            }

        } catch (e) {
            console.error("Erro grafo:", e);
            alert("Falha ao carregar dados visuais.");
        } finally {
            if(loader) {
                loader.style.opacity = '0';
                setTimeout(() => loader.style.display = 'none', 500);
            }
        }
    }

    styleNode(node) {
        // Aplica estilos específicos baseados no grupo
        switch(node.group) {
            case 'role':
                return { 
                    ...node, 
                    color: { background: '#6C5CE7', border: '#a29bfe', highlight: '#81ecec' }, 
                    size: 35, 
                    font: { size: 16, background: 'rgba(0,0,0,0.6)' } 
                };
            case 'user':
                // Usuário com permissão direta (exceção) ganha cor diferente no backend ou aqui?
                // Vamos assumir padrão verde, mas se tiver 'direct' na label ou props, mudamos.
                return { 
                    ...node, 
                    color: { background: '#00B894', border: '#55efc4' }, 
                    size: 20 
                };
            case 'permission':
                return { 
                    ...node, 
                    color: { background: '#2d3436', border: '#FD79A8' }, 
                    shape: 'diamond', 
                    size: 10, 
                    font: { size: 10, color: '#b2bec3' } 
                };
            case 'warning': // Sem acesso
                return { 
                    ...node, 
                    color: { background: '#d63031', border: '#ff7675' }, 
                    shape: 'triangle', 
                    size: 25 
                };
            default: return node;
        }
    }

    createNetwork() {
        const data = { nodes: this.nodes, edges: this.edges };
        this.network = new vis.Network(this.container, data, this.options);

        // Eventos
        this.network.on("oncontext", (params) => this.handleRightClick(params));
        this.network.on("click", () => this.hideContextMenu());
        this.network.on("dragStart", () => this.hideContextMenu());
    }

    // --- INTERAÇÃO E MENUS ---

    handleRightClick(params) {
        params.event.preventDefault();
        const nodeId = this.network.getNodeAt(params.pointer.DOM);
        
        if (nodeId) {
            // Seleciona o nó visualmente
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

        // Posiciona Menu (ajuste de offset para não sair da tela poderia ser adicionado aqui)
        const rect = this.container.getBoundingClientRect();
        menu.style.left = (rect.left + x + 15) + 'px';
        menu.style.top = (rect.top + y + 15) + 'px';

        let html = '';

        if (node.group === 'user' || node.group === 'warning') {
            header.innerText = node.label;
            html = `
                <div class="ctx-item" onclick="networkManager.prepareChangeRole('${node.id}', '${node.label}')">
                    <i class="fas fa-id-badge text-primary"></i> Alterar Grupo
                </div>
                <div class="ctx-item" onclick="networkManager.prepareDirectPerms('${node.id}', '${node.label}')">
                    <i class="fas fa-key text-warning"></i> Permissões Diretas
                </div>
            `;
        } else if (node.group === 'role') {
            header.innerText = node.label;
            html = `
                <div class="ctx-item" onclick="networkManager.prepareEditRole('${node.id}')">
                    <i class="fas fa-edit text-info"></i> Editar Grupo
                </div>
                <div class="ctx-item danger" onclick="networkManager.prepareDeleteRole('${node.id}')">
                    <i class="fas fa-trash text-danger"></i> Excluir Grupo
                </div>
            `;
        } else {
            // Permissão: Apenas visual por enquanto ou remover
            header.innerText = node.label;
            html = `<div class="ctx-item text-secondary"><i class="fas fa-info-circle"></i> Item do Sistema</div>`;
        }

        content.innerHTML = html;
        menu.style.display = 'block';
    }

    hideContextMenu() {
        document.getElementById('contextMenuNetwork').style.display = 'none';
    }

    // --- AÇÕES: USUÁRIOS ---

    prepareChangeRole(nodeId, userName) {
        this.hideContextMenu();
        document.getElementById('targetUserLogin').value = userName;
        document.getElementById('lblTargetUser').innerText = userName;

        const select = document.getElementById('selectNewRole');
        select.innerHTML = '<option value="">-- Sem Acesso (Remover) --</option>';
        
        // Popula Select
        this.rolesCache.forEach(r => {
            select.innerHTML += `<option value="${r.id}">${r.nome}</option>`;
        });

        // Tenta descobrir o Role atual pelas arestas
        const edges = this.edges.get({ filter: e => e.from === nodeId });
        const roleEdge = edges.find(e => e.to.startsWith('role_'));
        if(roleEdge) {
            select.value = roleEdge.to.replace('role_', '');
        }

        openModal('modalChangeRole');
    }

    async saveUserRole() {
        const login = document.getElementById('targetUserLogin').value;
        const roleId = document.getElementById('selectNewRole').value;

        try {
            const res = await fetch(API.updateUserRole, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ login, role_id: roleId })
            });
            if(res.ok) {
                closeModal('modalChangeRole');
                this.reload();
                this.toast("Grupo do usuário atualizado!");
            }
        } catch(e) { alert("Erro de comunicação."); }
    }

    prepareDirectPerms(nodeId, userName) {
        this.hideContextMenu();
        document.getElementById('directUserLogin').value = userName;
        document.getElementById('lblDirectUser').innerText = userName;

        // Popula Select de Permissões Disponíveis
        const select = document.getElementById('selectDirectPerm');
        select.innerHTML = '<option value="">Selecione para adicionar...</option>';
        // Ordena por slug
        [...this.permsCache].sort((a,b) => a.slug.localeCompare(b.slug)).forEach(p => {
            select.innerHTML += `<option value="${p.id}">${p.slug} - ${p.desc}</option>`;
        });

        // Lista as Permissões Atuais (descobrindo pelas arestas pontilhadas)
        const list = document.getElementById('listDirectPerms');
        list.innerHTML = '';
        
        const edges = this.edges.get({ filter: e => e.from === nodeId });
        let found = false;

        edges.forEach(edge => {
            // Arestas de permissão direta (usualmente definimos dashes no backend ou aqui)
            // No backend definimos dashes: [2,2] para diretas.
            if(edge.to.startsWith('perm_') && edge.dashes) {
                found = true;
                const permId = edge.to.replace('perm_', '');
                const permInfo = this.permsCache.find(p => p.id == permId);
                
                if(permInfo) {
                    list.innerHTML += `
                    <div class="d-flex justify-between align-center bg-dark p-2 rounded border border-secondary">
                        <span class="text-xs font-mono text-warning">${permInfo.slug}</span>
                        <button class="btn btn-xs btn-ghost text-danger" onclick="networkManager.removeDirectPermission('${userName}', ${permId})">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>`;
                }
            }
        });

        if(!found) list.innerHTML = '<div class="text-secondary text-xs text-center p-2">Nenhuma permissão direta atribuída.</div>';

        openModal('modalDirectPerms');
    }

    async addDirectPermission() {
        const login = document.getElementById('directUserLogin').value;
        const permId = document.getElementById('selectDirectPerm').value;
        if(!permId) return;
        
        await this.togglePermissionAPI(login, permId, 'add');
    }

    async removeDirectPermission(login, permId) {
        await this.togglePermissionAPI(login, permId, 'remove');
    }

    async togglePermissionAPI(login, permId, action) {
        try {
            const res = await fetch(API.toggleDirect, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ login, permission_id: permId, action })
            });
            if(res.ok) {
                // Recarrega grafo E reabre modal para ver atualização
                await this.loadGraphData();
                const userNode = this.nodes.get({filter: n => n.label === login})[0];
                if(userNode) this.prepareDirectPerms(userNode.id, login);
                this.toast(action === 'add' ? "Permissão concedida" : "Permissão revogada");
            }
        } catch(e) { alert("Erro ao alterar permissão."); }
    }

    // --- AÇÕES: GRUPOS (ROLES) ---

    prepareEditRole(nodeId) {
        this.hideContextMenu();
        const roleId = nodeId.replace('role_', '');
        const role = this.rolesCache.find(r => r.id == roleId);
        if(!role) return;

        document.getElementById('editRoleId').value = role.id;
        document.getElementById('editRoleName').value = role.nome;
        document.getElementById('editRoleDesc').value = role.descricao;

        // Renderiza Checkboxes
        const container = document.getElementById('editRolePermsContainer');
        let html = '';
        const sortedPerms = [...this.permsCache].sort((a,b) => a.slug.localeCompare(b.slug));

        sortedPerms.forEach(p => {
            const isChecked = role.permissions.includes(p.id) ? 'checked' : '';
            html += `
            <label class="d-flex gap-2 align-start p-2 bg-secondary rounded perm-check-item" data-search="${p.slug}">
                <input type="checkbox" value="${p.id}" ${isChecked} class="role-perm-check mt-1">
                <div style="line-height:1.2">
                    <div class="text-xs font-bold text-white">${p.slug}</div>
                    <div class="text-xs text-muted" style="font-size:0.65rem">${p.desc}</div>
                </div>
            </label>`;
        });
        container.innerHTML = html;

        openModal('modalEditRole');
    }

    filterPermChecks(term) {
        term = term.toLowerCase();
        document.querySelectorAll('.perm-check-item').forEach(el => {
            el.style.display = el.dataset.search.toLowerCase().includes(term) ? 'flex' : 'none';
        });
    }

    async saveRole() {
        const id = document.getElementById('editRoleId').value;
        const nome = document.getElementById('editRoleName').value;
        const descricao = document.getElementById('editRoleDesc').value;
        
        const checkboxes = document.querySelectorAll('.role-perm-check:checked');
        const permissions = Array.from(checkboxes).map(c => parseInt(c.value));

        if(!nome) return alert("Nome é obrigatório");

        try {
            const res = await fetch(API.saveRole, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ id, nome, descricao, permissions })
            });
            if(res.ok) {
                closeModal('modalEditRole');
                this.reload(); // Recarrega tudo (metadados e grafo)
                this.toast("Grupo salvo com sucesso!");
            }
        } catch(e) { console.error(e); }
    }

    prepareDeleteRole(nodeId) {
        this.hideContextMenu();
        if(!confirm("ATENÇÃO: Excluir este grupo removerá o acesso de todos os usuários vinculados. Continuar?")) return;

        const roleId = nodeId.replace('role_', '');
        this.deleteRoleAPI(roleId);
    }

    async deleteRoleAPI(id) {
        // Se chamado de dentro do modal, id pode vir undefined, pegar do input hidden
        if(!id) id = document.getElementById('editRoleId').value;

        try {
            const res = await fetch(API.deleteRole, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ id })
            });
            if(res.ok) {
                closeModal('modalEditRole');
                this.reload();
                this.toast("Grupo excluído.");
            } else {
                alert("Erro ao excluir.");
            }
        } catch(e) { console.error(e); }
    }

    // --- UTILITÁRIOS ---

    async reload() {
        await this.loadMetadata(); // Recarrega roles atualizadas
        await this.loadGraphData(); // Redesenha grafo
    }

    fit() {
        if(this.network) this.network.fit({ animation: true });
    }

    toast(msg) {
        // Fallback simples se não houver sistema de toast global
        if(window.NotificationSystem) window.NotificationSystem.show(msg, 'success');
        else {
            const el = document.createElement('div');
            el.style.cssText = "position:fixed; bottom:20px; left:50%; transform:translateX(-50%); background:#00B894; color:white; padding:10px 20px; border-radius:30px; z-index:9999; font-weight:bold; box-shadow:0 5px 15px rgba(0,0,0,0.3); animation: fadeIn 0.3s forwards";
            el.innerText = msg;
            document.body.appendChild(el);
            setTimeout(() => { el.style.opacity='0'; setTimeout(()=>el.remove(),300); }, 3000);
        }
    }
}

// Inicializa
document.addEventListener('DOMContentLoaded', () => {
    window.networkManager = new SecurityNetwork();
});