// ==========================================================================
// T-CONTROLLERSHIP - TREE VIEW MANAGER
// Arquivo: Static/JS/DreTreeView.js
// Descrição: Gerencia a árvore, modais, menu de contexto e sincronização.
// ==========================================================================

let globalTodasContas = [];
let contextNode = { id: null, type: null, text: null, ordem: null };
let clipboard = null;
let currentSelectedGroup = null;
let ordenamentoAtivo = false;

// DEFINIÇÃO DE PREFIXOS (Baseado nos seus logs)
// Se API_ROUTES falhar, usaremos estes caminhos como fallback
const PREFIX_ORDEM = '/T-controllership/DreOrdenamento';
const PREFIX_CONFIG = '/T-controllership/DreConfig';

// --- INICIALIZAÇÃO ---
document.addEventListener('DOMContentLoaded', async () => {
    // 1. Carrega listas auxiliares
    await loadContasList();
    
    // 2. Verifica status do ordenamento
    await verificarOrdenamento(); 
    
    // 3. Carrega a árvore
    await loadTree(); 
    
    // Event listeners globais
    document.addEventListener('click', () => {
        const menu = document.getElementById('contextMenu');
        if(menu) menu.style.display = 'none';
    });

    // Fechar modais ao clicar fora
    document.querySelectorAll('.modal-backdrop').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeModals();
        });
    });
    
    // Atalhos de teclado (Alt + Setas)
    document.addEventListener('keydown', (e) => {
        if (!contextNode.id) return;
        if (e.altKey && e.key === 'ArrowUp') {
            e.preventDefault();
            moverParaCima();
        } else if (e.altKey && e.key === 'ArrowDown') {
            e.preventDefault();
            moverParaBaixo();
        }
    });
});

// ==========================================================================
// 1. FUNÇÕES CENTRAIS DE API E SINCRONIZAÇÃO (CORRIGIDO)
// ==========================================================================

/**
 * Helper para resolver rotas.
 * Tenta usar API_ROUTES (injetado pelo HTML), senão usa o fallback com prefixo.
 */
function getRoute(key, fallbackPath, type='config') {
    if (typeof API_ROUTES !== 'undefined' && API_ROUTES[key]) {
        return API_ROUTES[key];
    }
    // Determina o prefixo baseado no tipo de rota
    const prefix = type === 'ordem' ? PREFIX_ORDEM : PREFIX_CONFIG;
    // Garante que não duplique barras
    const cleanPath = fallbackPath.startsWith('/') ? fallbackPath : '/' + fallbackPath;
    return `${prefix}${cleanPath}`;
}

/**
 * Função central para chamadas de API que alteram a estrutura.
 */
async function fetchAPI(url, body, successMsg='Sucesso!') {
    // Se a URL não começar com /, provavelmente é uma rota relativa que precisa de prefixo
    if (!url.startsWith('/')) {
        // Assume config por padrão se passar caminho curto
        url = getRoute(null, url, 'config'); 
    }

    try {
        const r = await fetch(url, { 
            method: 'POST', 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify(body) 
        });
        
        // CORREÇÃO: Verifica se é OK antes de tentar ler JSON
        if (!r.ok) {
            throw new Error(`Erro ${r.status}: ${r.statusText}`);
        }

        const data = await r.json();

        if(data.success || r.ok) { // Aceita tanto flag success quanto status 200
            if(successMsg) showToast(data.msg || successMsg); 
            closeModals(); 
            
            // Força sincronização e reload
            await autoSync(); 
            await loadTree(); 
        } else { 
            alert("Erro: "+ (data.error || "Erro desconhecido")); 
        }
    } catch(e) { 
        console.error("Fetch Error:", e);
        alert("Erro de comunicação: " + e.message); 
    }
    const menu = document.getElementById('contextMenu');
    if(menu) menu.style.display = 'none';
}

/**
 * Sincroniza a tabela de ordenamento silenciosamente.
 */
async function autoSync() {
    if(!ordenamentoAtivo) return;
    
    const statusText = document.getElementById('ordenamentoStatusText');
    if(statusText) statusText.innerText = "Sincronizando...";

    const url = getRoute('inicializarOrdenamento', '/Ordenamento/Inicializar', 'ordem');

    try {
        await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ limpar: false }) 
        });
        if(statusText) statusText.innerText = "Atualizado";
    } catch(e) {
        console.warn("Falha no auto-sync", e);
    }
}

// ==========================================================================
// 2. MODAIS E UI
// ==========================================================================

function closeModals() {
    document.querySelectorAll('.modal-backdrop').forEach(m => {
        m.classList.remove('active');
        setTimeout(() => {
            if (!m.classList.contains('active')) m.style.display = 'none';
        }, 200); 
    });
}

function openModal(id) {
    const m = document.getElementById(id);
    if (!m) return;
    
    const menu = document.getElementById('contextMenu');
    if(menu) menu.style.display = 'none';
    
    m.style.display = 'flex';
    m.offsetHeight; // Force reflow
    m.classList.add('active');

    if(id === 'modalAddSub') { 
        document.getElementById('lblParentName').innerText = contextNode.text || '...'; 
        resetInput('inputSubName'); 
    }
    if(id === 'modalLinkDetalhe') { 
        document.getElementById('lblDetailTarget').innerText = contextNode.text || '...'; 
        resetInput('inputDetailConta'); 
        document.getElementById('inputDetailName').value = ''; 
    }
    if(id === 'modalAddVirtual') resetInput('inputVirtualName');
    
    if(id === 'modalLinkConta') { 
        document.getElementById('lblGroupTarget').innerText = contextNode.text || '...'; 
        document.getElementById('inputContaSearch').value = '';
        loadStdGroupAccounts(contextNode.id);
    }
}

function resetInput(id){ 
    const e = document.getElementById(id); 
    if(e){ e.value=''; setTimeout(()=>e.focus(), 100); } 
}

function showToast(msg) { 
    const t = document.getElementById("toast"); 
    if(!t) return;
    t.innerHTML = `<i class="fas fa-check"></i> ${msg}`; 
    t.classList.add("show"); 
    setTimeout(() => t.classList.remove("show"), 3000); 
}

// ==========================================================================
// 3. ÁRVORE (RENDERIZAÇÃO)
// ==========================================================================

async function loadTree() {
    const rootUl = document.getElementById('treeRoot');
    rootUl.innerHTML = '<li class="loading-state"><div class="spinner"></div><span>Atualizando estrutura...</span></li>';
    
    try {
        let url;
        
        if (ordenamentoAtivo) {
            url = getRoute('getArvoreOrdenada', '/Ordenamento/GetArvoreOrdenada', 'ordem');
        } else {
            url = getRoute('getDadosArvore', '/Configuracao/GetDadosArvore', 'config');
        }
        
        console.log("LoadTree URL:", url);

        const response = await fetch(url);
        
        if (!response.ok) {
            // Tenta ler o erro JSON se possível, senão lança status
            try {
                const errData = await response.json();
                throw new Error(errData.msg || errData.error || response.statusText);
            } catch (jsonError) {
                throw new Error(`Erro HTTP ${response.status}`);
            }
        }
        
        const data = await response.json();
        rootUl.innerHTML = '';

        if (data.error) throw new Error(data.msg || data.error);
        
        if (!data || data.length === 0) { 
            rootUl.innerHTML = '<li class="loading-state text-secondary">Nenhuma estrutura encontrada.<br>Crie um Nó Virtual para começar.</li>'; 
            return; 
        }
        
        data.forEach(item => rootUl.appendChild(createNodeHTML(item)));
        
        if (ordenamentoAtivo && window.dreOrdenamento) {
            setTimeout(() => window.dreOrdenamento.habilitarDragDrop(), 200);
        }
        
    } catch (error) { 
        console.error("Erro no loadTree:", error); 
        rootUl.innerHTML = `<li class="loading-state text-danger">
            Erro ao carregar dados.<br>
            <small>${error.message}</small>
        </li>`; 
    }
}

function createNodeHTML(node) {
    const li = document.createElement('li');
    const wrapper = document.createElement('div');
    
    let typeClass = 'node-std';
    let icon = 'fa-circle';
    
    if(node.type === 'root_tipo') { typeClass = 'node-folder'; icon = 'fa-folder'; }
    else if(node.type === 'root_cc') { typeClass = 'node-cc'; icon = 'fa-building'; }
    else if(node.type === 'root_virtual') { typeClass = 'node-virtual'; icon = 'fa-cube'; }
    else if(node.type === 'subgrupo') { typeClass = 'node-sg'; icon = 'fa-folder-open'; }
    else if(node.type && node.type.includes('conta')) { typeClass = 'node-conta'; icon = 'fa-file-invoice'; }
    if(node.type === 'conta_detalhe') { typeClass = 'node-conta_detalhe'; icon = 'fa-tag'; }

    wrapper.className = `node-wrapper ${typeClass}`;
    wrapper.setAttribute('data-id', node.id);
    if (node.ordem) wrapper.setAttribute('data-ordem', node.ordem);
    
    const hasChildren = node.children && node.children.length > 0;
    
    let dragHandleHtml = ordenamentoAtivo ? '<i class="fas fa-grip-vertical drag-handle"></i>' : '';
    
    const toggle = document.createElement('div');
    toggle.className = `toggle-icon ${hasChildren ? '' : 'invisible'}`;
    toggle.innerHTML = '<i class="fas fa-chevron-right"></i>';
    
    if(hasChildren) {
        toggle.onclick = (e) => { e.stopPropagation(); toggleNode(li, toggle); };
        wrapper.ondblclick = (e) => { e.stopPropagation(); toggleNode(li, toggle); };
    }

    let ordemBadge = (node.ordem && ordenamentoAtivo) 
        ? `<span class="ordem-badge">#${node.ordem}</span>` 
        : '';

    const contentHtml = `
        ${dragHandleHtml}
        <i class="fas ${icon} type-icon"></i>
        <span class="node-text">${node.text}</span>
        ${ordemBadge}
    `;
    
    const contentSpan = document.createElement('span');
    contentSpan.innerHTML = contentHtml;
    contentSpan.style.display = 'flex';
    contentSpan.style.alignItems = 'center';
    contentSpan.style.flex = '1';
    contentSpan.style.overflow = 'hidden';

    wrapper.appendChild(toggle);
    wrapper.appendChild(contentSpan);
    
    wrapper.onclick = () => selectNodeUI(wrapper);
    wrapper.oncontextmenu = (e) => handleRightClick(e, node, wrapper);

    li.appendChild(wrapper);

    if (hasChildren) {
        const ul = document.createElement('ul');
        if (node.type === 'root_tipo' || node.type === 'root_virtual') {
            ul.classList.add('expanded');
            toggle.classList.add('rotated');
        }
        node.children.forEach(child => ul.appendChild(createNodeHTML(child)));
        li.appendChild(ul);
    }

    return li;
}

function toggleNode(li, toggleIcon) {
    const ul = li.querySelector('ul');
    if (ul) {
        ul.classList.toggle('expanded');
        toggleIcon.classList.toggle('rotated');
    }
}

function toggleAllTree(expand) {
    document.querySelectorAll('#treeRoot ul').forEach(ul => 
        expand ? ul.classList.add('expanded') : ul.classList.remove('expanded'));
    document.querySelectorAll('.toggle-icon:not(.invisible)').forEach(t => 
        expand ? t.classList.add('rotated') : t.classList.remove('rotated'));
}

function selectNodeUI(element) {
    document.querySelectorAll('.node-wrapper').forEach(el => el.classList.remove('selected'));
    element.classList.add('selected');
}

// ==========================================================================
// 4. MENU DE CONTEXTO & AÇÕES
// ==========================================================================

function handleRightClick(e, node, element) {
    e.preventDefault();
    selectNodeUI(element);
    contextNode = node;
    
    const menu = document.getElementById('contextMenu');
    
    const show = (id) => { const el = document.getElementById(id); if(el) el.style.display = 'flex'; };
    const hideAll = () => { document.querySelectorAll('.ctx-item, .ctx-separator').forEach(el => el.style.display = 'none'); };
    const showDiv = (id) => { const el = document.getElementById(id); if(el) el.style.display = 'block'; };

    hideAll();

    const isRoot = node.type === 'root_tipo';
    const isVirtual = node.type === 'root_virtual';
    const isGroup = node.type === 'subgrupo' || node.type === 'root_cc';
    const isItem = node.type && node.type.includes('conta');

    if (ordenamentoAtivo) {
        show('ctxMoveUp'); show('ctxMoveDown'); showDiv('divOrdem');
    }

    if (node.type === 'root_virtual' || node.type === 'subgrupo' || node.type === 'conta_detalhe') {
        show('ctxRename');
    }

    if (isRoot) {
        show('ctxMassManager'); 
    } else if (isGroup) {
        show('ctxAddSub'); showDiv('divCopy');
        show('ctxReplicar');
        if(node.type === 'subgrupo') {
            show('ctxCopy');
            if(clipboard) show('ctxPaste');
            show('ctxLinkConta'); show('ctxLinkDetalhe');
            showDiv('ctxDivider'); show('ctxDelete');
        } else {
            if(clipboard) show('ctxPaste');
        }
    } else if (isVirtual) {
        show('ctxAddSub'); show('ctxLinkDetalhe');
        show('ctxReplicar'); if(clipboard) show('ctxPaste');
        showDiv('ctxDivider'); show('ctxDelete');
    } else if (isItem) {
        show('ctxDelete');
    }

    const menuWidth = 220;
    const menuHeight = 300;
    let x = e.clientX;
    let y = e.clientY;

    if (x + menuWidth > window.innerWidth) x -= menuWidth;
    if (y + menuHeight > window.innerHeight) y -= menuHeight;

    menu.style.left = `${x}px`;
    menu.style.top = `${y}px`;
    menu.style.display = 'block';
}

// Ações do Menu
async function renameNode() {
    const novoNome = prompt("Novo nome:", contextNode.text);
    if (!novoNome || novoNome === contextNode.text) return;

    // Constrói URL correta usando o prefixo CONFIG
    let endpoint = '';
    if (contextNode.type === 'root_virtual') endpoint = '/Configuracao/RenameNoVirtual';
    else if (contextNode.type === 'subgrupo') endpoint = '/Configuracao/RenameSubgrupo';
    else if (contextNode.type === 'conta_detalhe') endpoint = '/Configuracao/RenameContaPersonalizada';
    
    if (endpoint) {
        fetchAPI(getRoute(null, endpoint, 'config'), { id: contextNode.id, novo_nome: novoNome }, 'Renomeado!');
    }
}

function copyNode() {
    if (!contextNode.id.startsWith('sg_')) return alert('Apenas subgrupos podem ser copiados.');
    clipboard = { id: contextNode.id, text: contextNode.text };
    showToast(`Copiado: ${contextNode.text}`);
    document.getElementById('contextMenu').style.display = 'none';
}

async function pasteNode() {
    if (!clipboard) return;
    if (!confirm(`Colar "${clipboard.text}" dentro de "${contextNode.text}"?`)) return;
    const url = getRoute(null, '/Configuracao/ColarEstrutura', 'config');
    fetchAPI(url, { origem_id: clipboard.id, destino_id: contextNode.id }, 'Estrutura colada!');
}

async function deleteNode() {
    if(!confirm(`Remover "${contextNode.text}" permanentemente?`)) return;
    let endpoint = '';
    if(contextNode.type==='subgrupo') endpoint='/Configuracao/DeleteSubgrupo';
    if(contextNode.type && contextNode.type.includes('conta')) endpoint='/Configuracao/DesvincularConta';
    if(contextNode.type==='root_virtual') endpoint='/Configuracao/DeleteNoVirtual';
    
    if(endpoint) {
        fetchAPI(getRoute(null, endpoint, 'config'), {id:contextNode.id}, 'Item removido.');
    }
}

// ==========================================================================
// 5. ORDENAMENTO
// ==========================================================================

async function verificarOrdenamento() {
    const indicator = document.getElementById('ordenamentoIndicator');
    const statusText = document.getElementById('ordenamentoStatusText');
    const toolbar = document.getElementById('ordenamentoToolbar');
    
    // Botões
    const btnInit = document.getElementById('btnInicializarOrdem');
    const btnReset = document.getElementById('btnResetarOrdem');
    const btnNorm = document.getElementById('btnNormalizarOrdem');
    
    try {
        const url = getRoute('getFilhosOrdenados', '/Ordenamento/GetFilhosOrdenados', 'ordem');

        const r = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ contexto_pai: 'root' })
        });
        
        if (r.ok) {
            const data = await r.json();
            ordenamentoAtivo = data.length > 0;
            
            if (ordenamentoAtivo) {
                if(toolbar) toolbar.classList.remove('inactive');
                if(indicator) { indicator.classList.add('active'); indicator.classList.remove('inactive'); }
                if(statusText) statusText.innerHTML = 'Ordenamento <strong>Ativo</strong>';
                
                if(btnInit) btnInit.style.display = 'none';
                if(btnReset) btnReset.style.display = 'inline-block';
                if(btnNorm) btnNorm.style.display = 'inline-block';
            } else {
                if(toolbar) toolbar.classList.add('inactive');
                if(indicator) { indicator.classList.remove('active'); indicator.classList.add('inactive'); }
                if(statusText) statusText.innerHTML = 'Ordenamento <strong>Inativo</strong>';
                
                if(btnInit) btnInit.style.display = 'inline-block';
                if(btnReset) btnReset.style.display = 'none';
                if(btnNorm) btnNorm.style.display = 'none';
            }
        }
    } catch (e) { 
        console.warn("Falha na verificação de ordenamento:", e); 
    }
}

async function inicializarOrdenamento() {
    if (!confirm('Inicializar estrutura de ordenamento?')) return;
    showToast('Inicializando...');
    const url = getRoute('inicializarOrdenamento', '/Ordenamento/Inicializar', 'ordem');
    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ limpar: false })
        });
        if(r.ok) { showToast('Ordenamento Ativado!'); window.location.reload(); }
    } catch(e) { alert('Erro: ' + e); }
}

async function resetarOrdenamento() {
    if (!confirm('RESETAR toda a ordem para o padrão alfabético/código?')) return;
    const url = getRoute('inicializarOrdenamento', '/Ordenamento/Inicializar', 'ordem');
    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ limpar: true })
        });
        if(r.ok) { showToast('Resetado!'); loadTree(); }
    } catch(e) { alert('Erro: ' + e); }
}

async function normalizarOrdenamento() {
    const url = getRoute(null, '/Ordenamento/Normalizar', 'ordem');
    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ contexto_pai: 'root' })
        });
        if(r.ok) showToast('Normalizado!');
    } catch(e) {}
}

async function sincronizarOrdem() {
    showToast('Sincronizando...');
    await autoSync();
    await loadTree();
    showToast('Sincronizado!');
}

async function moverParaCima() { if (!contextNode.id) return; await moverElemento(-1); }
async function moverParaBaixo() { if (!contextNode.id) return; await moverElemento(1); }

async function moverElemento(direcao) {
    const wrapper = document.querySelector(`.node-wrapper[data-id="${contextNode.id}"]`);
    if (!wrapper) return;
    const li = wrapper.closest('li');
    const ul = li.parentElement;
    const items = Array.from(ul.querySelectorAll(':scope > li'));
    const index = items.indexOf(li);
    const newIndex = index + direcao;
    
    if (newIndex >= 0 && newIndex < items.length) {
        if (direcao < 0) ul.insertBefore(li, items[newIndex]);
        else ul.insertBefore(li, items[newIndex].nextSibling);
        
        // Salva ordem via DragManager (reutiliza lógica)
        if (window.dreOrdenamento) {
            await window.dreOrdenamento.salvarNovaPosicao(ul);
        }
    }
}

// ==========================================================================
// 6. FORM SUBMISSIONS
// ==========================================================================

function submitAddVirtual() { 
    const n = document.getElementById('inputVirtualName').value; 
    if(!n) return alert('Nome?'); 
    fetchAPI(getRoute(null, '/Configuracao/AddNoVirtual', 'config'), {nome:n}, 'Nó Virtual criado!');
}

function submitAddSub() { 
    const n = document.getElementById('inputSubName').value; 
    if(!n) return alert('Nome?'); 
    fetchAPI(getRoute(null, '/Configuracao/AddSubgrupo', 'config'), {nome:n, parent_id:contextNode.id}, 'Grupo criado!');
}

async function submitLinkConta() {
    const c = document.getElementById('inputContaSearch').value;
    if(!c) return alert('Conta?');
    const url = getRoute(null, '/Configuracao/VincularConta', 'config');
    
    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ conta: c, subgrupo_id: contextNode.id })
        });
        if(r.ok) {
            showToast('Vinculado!');
            document.getElementById('inputContaSearch').value = '';
            loadStdGroupAccounts(contextNode.id); // Atualiza modal
            await autoSync(); 
            loadTree(); 
        } else {
            const d = await r.json(); alert(d.error);
        }
    } catch(e) { alert("Erro de conexão"); }
}

function submitLinkDetalhe() { 
    const c = document.getElementById('inputDetailConta').value; 
    const n = document.getElementById('inputDetailName').value; 
    if(!c) return alert('Conta?'); 
    fetchAPI(
        getRoute(null, '/Configuracao/VincularContaDetalhe', 'config'), 
        {conta:c, nome_personalizado:n, parent_id:contextNode.id}, 
        'Vinculado!'
    );
}

// ==========================================================================
// 7. GERENCIADOR EM MASSA
// ==========================================================================

function openMassManager() {
    const tipoCC = contextNode.id.replace('tipo_', '');
    document.getElementById('lblMassType').innerText = tipoCC;
    loadMassGroupsList(tipoCC);
    openModal('modalMassManager');
    switchMassTab('tabCreateGroup', document.querySelector('.nav-btn.active'));
}

function switchMassTab(tabId, btn) {
    document.querySelectorAll('.tab-pane').forEach(p => {
        p.style.display = 'none';
        p.classList.remove('active');
    });
    document.getElementById(tabId).style.display = 'flex';
    setTimeout(() => document.getElementById(tabId).classList.add('active'), 10);

    if(btn) {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    }
}

async function loadMassGroupsList(tipoCC) {
    const list = document.getElementById('listMassGroups');
    const select = document.getElementById('selectMassDeleteGroup');
    list.innerHTML = '<div class="text-center p-3 text-secondary"><i class="fas fa-spinner fa-spin"></i></div>';
    
    const url = getRoute(null, '/Configuracao/GetSubgruposPorTipo', 'config');

    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ tipo_cc: tipoCC })
        });
        const grupos = await r.json();
        
        let htmlList = '';
        let htmlSelect = '<option value="" disabled selected>Selecione...</option>';
        
        if (grupos.length > 0) {
            grupos.forEach(g => {
                htmlList += `
                    <div class="group-list-item" onclick="selectMassGroup('${g}', this)">
                        <span><i class="fas fa-folder text-warning me-2"></i> ${g}</span>
                        <i class="fas fa-chevron-right"></i>
                    </div>`;
                htmlSelect += `<option value="${g}">${g}</option>`;
            });
        } else {
            htmlList = '<div class="p-3 text-center text-muted">Vazio</div>';
        }
        
        list.innerHTML = htmlList;
        select.innerHTML = htmlSelect;
    } catch(e) { console.error(e); }
}

async function selectMassGroup(groupName, el) {
    currentSelectedGroup = groupName;
    document.querySelectorAll('.group-list-item').forEach(i => i.classList.remove('active'));
    el.classList.add('active');
    
    document.getElementById('noGroupSelected').style.display = 'none';
    document.getElementById('groupDetails').style.display = 'flex';
    document.getElementById('lblSelectedGroup').innerText = groupName;
    
    const container = document.getElementById('listLinkedAccounts');
    container.innerHTML = '<div class="text-center p-3"><i class="fas fa-spinner fa-spin"></i></div>';
    
    const tipoCC = document.getElementById('lblMassType').innerText;
    const url = getRoute(null, '/Configuracao/GetContasDoGrupoMassa', 'config');
    
    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ tipo_cc: tipoCC, nome_grupo: groupName })
        });
        const contas = await r.json();
        
        document.getElementById('lblCountAccounts').innerText = `${contas.length} contas`;
        
        const dl = document.getElementById('massContasDataList');
        dl.innerHTML = '';
        const numerosVinculados = contas.map(c => c.conta);
        globalTodasContas.filter(x => !numerosVinculados.includes(x.numero)).forEach(c => {
            const o = document.createElement('option');
            o.value = c.numero; o.label = c.nome;
            dl.appendChild(o);
        });

        if (contas.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>Nenhuma conta vinculada.</p></div>';
        } else {
            let html = '';
            contas.forEach(item => {
                const isPers = (item.tipo === 'personalizada');
                const contaInfo = globalTodasContas.find(x => x.numero == item.conta);
                const nomeBase = contaInfo ? contaInfo.nome.substring(0,15)+'...' : 'S/ Nome';
                const label = isPers 
                    ? `<strong>${item.conta}</strong> <small>(${item.nome_personalizado || nomeBase})</small>`
                    : `${item.conta} - ${nomeBase}`;
                
                html += `
                    <div class="account-tag ${isPers ? 'pers' : ''}">
                        ${isPers ? '<i class="fas fa-pen-fancy fa-xs me-1"></i>' : ''}
                        ${label}
                        <i class="fas fa-times remove-btn" onclick="removeAccountFromGroup('${item.conta}', ${isPers})"></i>
                    </div>`;
            });
            container.innerHTML = html;
        }
    } catch(e) { console.error(e); }
}

function toggleMassCustomInput() {
    const chk = document.getElementById('chkMassPersonalizada');
    const div = document.getElementById('divMassCustomName');
    div.style.display = chk.checked ? 'block' : 'none';
    if(chk.checked) document.getElementById('inputMassCustomName').focus();
}

async function addAccountToGroup() {
    if(!currentSelectedGroup) return;
    const conta = document.getElementById('inputMassLinkConta').value;
    const tipoCC = document.getElementById('lblMassType').innerText;
    const isPers = document.getElementById('chkMassPersonalizada').checked;
    const nomePers = document.getElementById('inputMassCustomName').value;
    
    if(!conta) return alert('Conta?');
    
    const url = getRoute(null, '/Configuracao/VincularContaEmMassa', 'config');

    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                tipo_cc: tipoCC,
                nome_subgrupo: currentSelectedGroup,
                conta: conta,
                is_personalizada: isPers,
                nome_personalizado_conta: nomePers
            })
        });
        const data = await r.json();
        if(r.ok) {
            showToast(data.msg);
            document.getElementById('inputMassLinkConta').value = '';
            const activeItem = document.querySelector('.group-list-item.active');
            if(activeItem) selectMassGroup(currentSelectedGroup, activeItem);
            
            await autoSync();
            loadTree();
        } else {
            alert(data.error);
        }
    } catch(e) { alert('Erro'); }
}

async function removeAccountFromGroup(conta, isPers) {
    const tipoCC = document.getElementById('lblMassType').innerText;
    if(!confirm('Remover vínculo?')) return;
    
    const url = getRoute(null, '/Configuracao/DesvincularContaEmMassa', 'config');

    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ tipo_cc: tipoCC, conta: conta, is_personalizada: isPers })
        });
        if(r.ok) {
            showToast('Removido');
            const activeItem = document.querySelector('.group-list-item.active');
            if(activeItem) selectMassGroup(currentSelectedGroup, activeItem);
            await autoSync();
            loadTree();
        }
    } catch(e) { alert('Erro'); }
}

function submitMassCreate() {
    const nome = document.getElementById('inputMassCreateName').value;
    const tipoCC = document.getElementById('lblMassType').innerText;
    if(!nome) return;
    const url = getRoute(null, '/Configuracao/AddSubgrupoSistematico', 'config');
    fetchAPI(url, {nome:nome, tipo_cc:tipoCC}, 'Grupo Criado!');
}

function submitMassDelete() {
    const nome = document.getElementById('selectMassDeleteGroup').value;
    const tipoCC = document.getElementById('lblMassType').innerText;
    if(!nome) return;
    if(!confirm('Isso apagará o grupo e contas de TODOS os CCs. Continuar?')) return;
    const url = getRoute(null, '/Configuracao/DeleteSubgrupoEmMassa', 'config');
    fetchAPI(url, {nome_grupo:nome, tipo_cc:tipoCC}, 'Grupo Excluído!');
}

function submitMassUnlink() {
    const c = document.getElementById('inputMassUnlinkConta').value;
    const tipoCC = document.getElementById('lblMassType').innerText;
    if(!c) return;
    const url = getRoute(null, '/Configuracao/DesvincularContaEmMassa', 'config');
    fetchAPI(url, {conta:c, tipo_cc:tipoCC}, 'Vínculo removido!');
}

// ==========================================================================
// 8. HELPERS
// ==========================================================================

async function openReplicarModal() {
    openModal('modalReplicar');
    document.getElementById('lblOrigemReplicar').innerText = contextNode.text;
    const list = document.getElementById('listaDestinos');
    list.innerHTML = 'Carregando...';
    
    try {
        const url = getRoute('getDadosArvore', '/Configuracao/GetDadosArvore', 'config');
        const r = await fetch(url);
        const data = await r.json();
        let html = '';
        data.forEach(root => {
            if(root.type === 'root_tipo') {
                html += `<div style="background:rgba(0,0,0,0.2);padding:5px;font-weight:bold;margin-top:5px;">${root.text}</div>`;
                root.children.forEach(cc => {
                    if(cc.id !== contextNode.id) {
                        html += `<label style="display:block;padding:5px;cursor:pointer;"><input type="checkbox" class="chk-dest" value="${cc.id.replace('cc_','')}"> ${cc.text}</label>`;
                    }
                });
            }
        });
        list.innerHTML = html;
    } catch(e){ list.innerHTML = 'Erro: ' + e.message; }
}

function toggleAllDestinos() {
    document.querySelectorAll('.chk-dest').forEach(c => c.checked = !c.checked);
    document.getElementById('lblTotalSelecionados').innerText = document.querySelectorAll('.chk-dest:checked').length + ' selecionados';
}

async function submitReplicar() {
    const ids = Array.from(document.querySelectorAll('.chk-dest:checked')).map(c => c.value);
    if(ids.length === 0) return alert('Selecione destinos');
    const url = getRoute(null, '/Configuracao/ReplicarEstrutura', 'config');
    fetchAPI(url, {origem_node_id: contextNode.id, destinos_ids: ids}, 'Replicado!');
}

async function loadContasList() {
    try {
        const url = getRoute('GetContasDisponiveis', '/Configuracao/GetContasDisponiveis', 'config');
        const r = await fetch(url);
        if(!r.ok) throw new Error("Falha ao carregar contas");
        const d = await r.json();
        globalTodasContas = d;
        const dl = document.getElementById('contasDataList');
        const dlStd = document.getElementById('stdContasDataList');
        if(dl) dl.innerHTML = '';
        if(dlStd) dlStd.innerHTML = '';
        
        d.forEach(c => {
            const o = document.createElement('option');
            o.value = c.numero; o.label = c.nome;
            if(dl) dl.appendChild(o.cloneNode(true));
            if(dlStd) dlStd.appendChild(o);
        });
    } catch(e){ console.error(e); }
}

async function loadStdGroupAccounts(nodeId) {
    const list = document.getElementById('listStdLinkedAccounts');
    list.innerHTML = 'Carregando...';
    const dbId = nodeId.replace('sg_', '');
    const url = getRoute(null, '/Configuracao/GetContasDoSubgrupo', 'config');

    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({id: dbId})
        });
        const d = await r.json();
        document.getElementById('lblCountStd').innerText = d.length;
        
        if(d.length === 0) list.innerHTML = '<div class="text-muted text-center p-3">Vazio</div>';
        else {
            let html = '';
            d.forEach(c => {
                const info = globalTodasContas.find(x=>x.numero==c);
                html += `
                    <div class="account-tag" style="margin:5px;">
                        ${c} - ${info ? info.nome.substring(0,15) : '...'}
                        <i class="fas fa-times remove-btn" onclick="removeStdAccount('${c}')"></i>
                    </div>`;
            });
            list.innerHTML = `<div style="display:flex;flex-wrap:wrap;">${html}</div>`;
        }
    } catch(e){ list.innerHTML = 'Erro'; }
}

async function removeStdAccount(c) {
    if(!confirm('Desvincular?')) return;
    const url = getRoute(null, '/Configuracao/DesvincularConta', 'config');
    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({id: `conta_${c}`})
        });
        if(r.ok) {
            showToast('Removido');
            loadStdGroupAccounts(contextNode.id);
            await autoSync();
            loadTree();
        }
    } catch(e){ alert('Erro'); }
}

// ---------------------------
// GESTÃO DE NÓS CALCULADOS
// ---------------------------
let operandosDisponiveis = null;
let operandosSelecionados = [];

async function openModalCalculado() {
    // Carrega operandos disponíveis se ainda não existirem
    if (!operandosDisponiveis) {
        try {
            const url = getRoute('GetOperandosDisponiveis', '/Configuracao/GetOperandosDisponiveis', 'config');
            const r = await fetch(url);
            
            if (!r.ok) {
                const err = await r.json();
                throw new Error(err.error || "Erro ao carregar dados do servidor");
            }
            operandosDisponiveis = await r.json();
        } catch (e) {
            console.error(e);
            alert("Erro ao carregar operandos: " + e.message);
            return;
        }
    }
    
    operandosSelecionados = [];
    renderOperandos();
    openModal('modalAddCalculado');
    atualizarPreviewFormula();
}

function renderOperandos() {
    const container = document.getElementById('containerOperandos');
    
    if (!operandosDisponiveis || !operandosDisponiveis.tipos_cc) {
        container.innerHTML = '<div class="text-danger p-2">Erro: Dados não carregados.</div>';
        return;
    }

    container.innerHTML = '';
    
    // Separa os nós virtuais em Manuais (Inputs) e Calculados (Fórmulas)
    const nosManuais = operandosDisponiveis.nos_virtuais.filter(n => !n.is_calculado);
    const nosCalculados = operandosDisponiveis.nos_virtuais.filter(n => n.is_calculado);

    operandosSelecionados.forEach((op, idx) => {
        container.innerHTML += `
            <div class="operando-item" data-index="${idx}">
                <select class="form-select form-select-sm" onchange="updateOperando(${idx}, this)">
                    <option value="" disabled ${!op.id ? 'selected' : ''}>Selecione...</option>
                    
                    <optgroup label="Tipos de Centro de Custo">
                        ${operandosDisponiveis.tipos_cc.map(t => 
                            `<option value="tipo_cc:${t.id}" ${op.tipo === 'tipo_cc' && op.id === t.id ? 'selected' : ''}>
                                📂 ${t.nome}
                            </option>`
                        ).join('')}
                    </optgroup>

                    <optgroup label="Nós Virtuais (Input Manual)">
                        ${nosManuais.map(n => 
                            `<option value="no_virtual:${n.id}" ${op.tipo === 'no_virtual' && op.id == n.id ? 'selected' : ''}>
                                📝 ${n.nome}
                            </option>`
                        ).join('')}
                    </optgroup>

                    <optgroup label="Nós Calculados (Resultados)">
                        ${nosCalculados.map(n => 
                            `<option value="no_virtual:${n.id}" ${op.tipo === 'no_virtual' && op.id == n.id ? 'selected' : ''}>
                                📊 ${n.nome}
                            </option>`
                        ).join('')}
                    </optgroup>

                </select>
                <button class="btn btn-xs btn-ghost text-danger" onclick="removeOperando(${idx})">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
    });
}

function addOperando() {
    operandosSelecionados.push({ tipo: 'tipo_cc', id: 'Oper', label: 'Operacional' });
    renderOperandos();
    atualizarPreviewFormula();
}

function removeOperando(idx) {
    operandosSelecionados.splice(idx, 1);
    renderOperandos();
    atualizarPreviewFormula();
}

function updateOperando(idx, select) {
    const [tipo, id] = select.value.split(':');
    const label = select.options[select.selectedIndex].text;
    operandosSelecionados[idx] = { tipo, id, label };
    atualizarPreviewFormula();
}

function atualizarPreviewFormula() {
    const op = document.getElementById('selectCalcOperacao').value;
    const simbolos = { soma: '+', subtracao: '-', multiplicacao: '×', divisao: '÷' };
    
    const labels = operandosSelecionados.map(o => o.label || o.id);
    const preview = labels.join(` ${simbolos[op]} `) || 'Selecione operandos...';
    
    document.getElementById('previewFormula').textContent = preview;
}

async function submitNoCalculado() {
    const nome = document.getElementById('inputCalcNome').value;
    const operacao = document.getElementById('selectCalcOperacao').value;
    const ordem = parseInt(document.getElementById('inputCalcOrdem').value) || 50;
    const tipoExibicao = document.getElementById('selectCalcTipoExibicao').value;
    
    if (!nome) return alert('Informe o nome do nó');
    if (operandosSelecionados.length < 2) return alert('Adicione pelo menos 2 operandos');
    
    const formula = {
        operacao: operacao,
        operandos: operandosSelecionados.map(o => ({
            tipo: o.tipo,
            id: o.tipo === 'no_virtual' ? parseInt(o.id) : o.id,
            label: o.label
        }))
    };
    
    const url = getRoute(null, '/Configuracao/AddNoCalculado', 'config');
    fetchAPI(url, {
        nome: nome,
        formula: formula,
        ordem: ordem,
        tipo_exibicao: tipoExibicao
    }, 'Nó calculado criado!');
}

document.getElementById('selectCalcOperacao')?.addEventListener('change', atualizarPreviewFormula);