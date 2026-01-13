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
let tipoDestinoIntegral = null; // Controle para replicação de Tipos

// DEFINIÇÃO DE PREFIXOS (Baseado nos seus logs)
const PREFIX_ORDEM = '/T-controllership/DreOrdenamento';
const PREFIX_CONFIG = '/T-controllership/DreConfig';

// MAPA VISUAL (Somente Visualização)
const MAPA_TIPOS_CC = {
    'Oper': 'CUSTOS',
    'Adm': 'ADMINISTRATIVO',
    'Coml': 'COMERCIAL'
};

function getLabelTipoCC(tipo) {
    return MAPA_TIPOS_CC[tipo] || tipo;
}

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
// 1. FUNÇÕES CENTRAIS DE API E SINCRONIZAÇÃO
// ==========================================================================

function getRoute(key, fallbackPath, type='config') {
    if (typeof API_ROUTES !== 'undefined' && API_ROUTES[key]) {
        return API_ROUTES[key];
    }
    const prefix = type === 'ordem' ? PREFIX_ORDEM : PREFIX_CONFIG;
    const cleanPath = fallbackPath.startsWith('/') ? fallbackPath : '/' + fallbackPath;
    return `${prefix}${cleanPath}`;
}

async function fetchAPI(url, body, successMsg='Sucesso!') {
    if (!url.startsWith('/')) {
        url = getRoute(null, url, 'config'); 
    }

    try {
        const r = await fetch(url, { 
            method: 'POST', 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify(body) 
        });
        
        if (!r.ok) {
            throw new Error(`Erro ${r.status}: ${r.statusText}`);
        }

        const data = await r.json();

        if(data.success || r.ok) { 
            if(successMsg) showToast(data.msg || successMsg); 
            closeModals(); 
            
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
    m.offsetHeight; 
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
    if(id === 'modalAddVirtual') {
        resetInput('inputVirtualName');
        // Reset da Cor
        document.getElementById('inputVirtualColor').value = '#34495e'; 
    }
    
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
    
    const COLOR_DARK   = 'color: var(--icon-structure);'; 
    const COLOR_GRAY   = 'color: var(--icon-secondary);'; 
    const COLOR_FOLDER = 'color: var(--icon-folder);'; 
    const COLOR_LIGHT  = 'color: var(--icon-account);';
    
    let typeClass = 'node-std';
    let icon = 'fa-circle';
    let styleIcon = ''; 
    
    // --- LÓGICA VISUAL EMPRESARIAL ---
    
    if(node.type === 'root_tipo') { 
        typeClass = 'node-folder'; 
        icon = 'fa-layer-group'; 
        styleIcon = COLOR_DARK;
        
        // CORREÇÃO VISUAL: Aplica o nome amigável (CUSTOS, etc)
        const rawType = node.id.replace('tipo_', '');
        node.text = getLabelTipoCC(rawType);
    }
    else if(node.type === 'root_cc') { 
        typeClass = 'node-cc'; 
        icon = 'fa-building'; 
        styleIcon = COLOR_GRAY;
    }
    else if(node.type === 'root_virtual') { 
        typeClass = 'node-virtual'; 
        icon = 'fa-cube'; 
        styleIcon = COLOR_DARK;
        
        // APLICAÇÃO DA COR CUSTOMIZADA
        if (node.estilo_css) {
            styleIcon = node.estilo_css; 
        }
    }
    else if(node.type === 'subgrupo') { 
        if (!node.parent || node.parent === 'root' || node.id_pai === null) {
            typeClass = 'node-sg-root'; 
            icon = 'fa-globe'; 
            styleIcon = COLOR_GRAY; 
        } else {
            typeClass = 'node-sg'; 
            icon = 'fa-folder'; 
            styleIcon = COLOR_FOLDER; 
        }
    }
    else if(node.type && node.type.includes('conta')) { 
        typeClass = 'node-conta'; 
        icon = 'fa-file-alt'; 
        styleIcon = COLOR_LIGHT;
    }
    if(node.type === 'conta_detalhe') { 
        typeClass = 'node-conta_detalhe'; 
        icon = 'fa-tag'; 
        styleIcon = COLOR_GRAY;
    }

    if (typeClass === 'node-sg-root') {
        wrapper.className = `node-wrapper node-sg ${typeClass}`;
    } else {
        wrapper.className = `node-wrapper ${typeClass}`;
    }
    
    wrapper.setAttribute('data-id', node.id);
    if (node.ordem) wrapper.setAttribute('data-ordem', node.ordem);
    
    const hasChildren = node.children && node.children.length > 0;
    
    let dragHandleHtml = ordenamentoAtivo ? '<i class="fas fa-grip-vertical drag-handle" style="color: #dfe6e9;"></i>' : '';
    
    const toggle = document.createElement('div');
    toggle.className = `toggle-icon ${hasChildren ? '' : 'invisible'}`;
    toggle.innerHTML = '<i class="fas fa-caret-right" style="color: #95a5a6;"></i>'; 
    
    if(hasChildren) {
        toggle.onclick = (e) => { e.stopPropagation(); toggleNode(li, toggle); };
        wrapper.ondblclick = (e) => { e.stopPropagation(); toggleNode(li, toggle); };
    }

    let ordemBadge = (node.ordem && ordenamentoAtivo) 
        ? `<span class="ordem-badge" style="color: var(--bi-row-root-text);">#${node.ordem}</span>` 
        : '';

    const contentHtml = `
        ${dragHandleHtml}
        <i class="fas ${icon} type-icon" style="${styleIcon} margin-right: 8px;"></i>
        <span class="node-text" style="color: var(--bi-row-root-text) !important; font-weight: 500;">${node.text}</span>
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
let currentEditingNodeId = null; // Controla se estamos editando ou criando

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

    // 1. Opções de Ordenamento
    if (ordenamentoAtivo) {
        show('ctxMoveUp'); show('ctxMoveDown'); showDiv('divOrdem');
    }

    // 2. Opção Renomear (Comum a vários tipos)
    if (node.type === 'root_virtual' || node.type === 'subgrupo' || node.type === 'conta_detalhe') {
        show('ctxRename');
    }

    // 3. Menus Específicos por Tipo
    if (isRoot) {
        show('ctxMassManager'); 
        show('ctxReplicarTipo');
    } 
    else if (isGroup) {
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
    } 
    else if (isVirtual) {
        // --- NOVA LÓGICA: Se for calculado, permite editar ---
        if (node.is_calculado) {
            show('ctxEditCalc');
        }

        show('ctxAddSub'); 
        show('ctxLinkDetalhe');
        show('ctxReplicar'); 
        if(clipboard) show('ctxPaste');
        
        showDiv('ctxDivider'); 
        show('ctxDelete');
    } 
    else if (isItem) {
        show('ctxDelete');
    }

    // 4. Posicionamento do Menu
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

async function editCalculado() {
    if (!contextNode.id.startsWith('virt_')) return;
    
    const dbId = contextNode.id.replace('virt_', '');
    currentEditingNodeId = dbId; // Marca que estamos editando

    // Carrega operandos se necessário
    if (!operandosDisponiveis) {
        try {
            const url = getRoute('GetOperandosDisponiveis', '/Configuracao/GetOperandosDisponiveis', 'config');
            const r = await fetch(url);
            operandosDisponiveis = await r.json();
        } catch(e) { return alert("Erro ao carregar dependências"); }
    }

    // Busca os dados completos deste nó (Fórmula, estilo, etc)
    try {
        const url = getRoute('GetNosCalculados', '/Configuracao/GetNosCalculados', 'config');
        const r = await fetch(url);
        const lista = await r.json();
        const dadosNo = lista.find(n => n.id == dbId);

        if (!dadosNo) return alert("Dados do nó não encontrados.");

        // Preenche o Modal
        document.getElementById('inputCalcNome').value = dadosNo.nome;
        document.getElementById('inputCalcOrdem').value = dadosNo.ordem || 50;
        document.getElementById('selectCalcTipoExibicao').value = dadosNo.tipo_exibicao || 'valor';
        
        // Carrega a Cor (Extrai do CSS)
        let corSalva = '#34495e';
        if (dadosNo.estilo_css && dadosNo.estilo_css.includes('background-color:')) {
            const match = dadosNo.estilo_css.match(/background-color:\s*(#[0-9a-fA-F]{6})/);
            if (match) corSalva = match[1];
        }
        document.getElementById('inputCalcColor').value = corSalva;
        
        // Reconstrói a fórmula
        if (dadosNo.formula) {
            document.getElementById('selectCalcOperacao').value = dadosNo.formula.operacao || 'soma';
            
            // Mapeia os operandos salvos de volta para o formato de edição
            operandosSelecionados = (dadosNo.formula.operandos || []).map(op => ({
                tipo: op.tipo,
                id: op.id,
                label: op.label || op.id // Fallback se label não vier
            }));
        } else {
            operandosSelecionados = [];
        }

        renderOperandos();
        atualizarPreviewFormula();
        
        // Ajusta título do modal (Visual)
        const modalTitle = document.querySelector('#modalAddCalculado .modal-header h3');
        if(modalTitle) modalTitle.innerText = "Editar Nó Calculado";

        openModal('modalAddCalculado');

    } catch (e) {
        console.error(e);
        alert("Erro ao carregar detalhes do cálculo.");
    }
}

async function renameNode() {
    const novoNome = prompt("Novo nome:", contextNode.text);
    if (!novoNome || novoNome === contextNode.text) return;

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
    const c = document.getElementById('inputVirtualColor').value; 

    if(!n) return alert('Nome?'); 
    
    fetchAPI(getRoute(null, '/Configuracao/AddNoVirtual', 'config'), {
        nome: n,
        cor: c // Envia a cor
    }, 'Nó Virtual criado!');
}

function submitAddSub() { 
    const n = document.getElementById('inputSubName').value; 
    if(!n) return alert('Nome?'); 
    if (!contextNode || !contextNode.id) return alert('Erro de contexto. Tente novamente.');

    fetchAPI(
        getRoute(null, '/Configuracao/AddSubgrupo', 'config'), 
        { nome: n, parent_id: contextNode.id }, 
        'Grupo criado!'
    );
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
            loadStdGroupAccounts(contextNode.id); 
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
    if (!contextNode.id.startsWith('tipo_')) {
        return;
    }
    
    const tipoCC = contextNode.id.replace('tipo_', '');
    const lbl = document.getElementById('lblMassType');
    
    // CORREÇÃO CRÍTICA: 
    // - data-code armazena o valor real ('Oper') para as APIs
    // - innerText exibe o valor amigável ('CUSTOS') para o usuário
    lbl.dataset.code = tipoCC;
    lbl.innerText = getLabelTipoCC(tipoCC);
    
    openModal('modalMassManager');
    
    const defaultBtn = document.querySelector('.nav-btn'); 
    switchMassTab('tabGroupManager', defaultBtn);
}

function switchMassTab(tabId, btn) {
    document.querySelectorAll('.tab-pane').forEach(p => {
        p.style.display = 'none';
        p.classList.remove('active');
    });
    
    const target = document.getElementById(tabId);
    if(target) {
        target.style.display = 'flex'; 
        setTimeout(() => target.classList.add('active'), 10);
    }

    if(btn) {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    }

    // CORREÇÃO: Lê do dataset.code (valor real 'Oper') em vez do texto visível
    const tipoCC = document.getElementById('lblMassType').dataset.code;
    
    if (tabId === 'tabGroupManager') {
        loadGroupManagerList(tipoCC);
    } else if (tabId === 'tabLinkAccount') {
        loadMassGroupsList(tipoCC);
    }
}

async function loadGroupManagerList(tipoCC) {
    const list = document.getElementById('listGroupManager');
    list.innerHTML = '<div class="text-center p-3"><i class="fas fa-spinner fa-spin"></i> Carregando...</div>';

    const url = getRoute(null, '/Configuracao/GetSubgruposPorTipo', 'config');

    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ tipo_cc: tipoCC })
        });
        
        const grupos = await r.json();
        list.innerHTML = '';

        if (grupos.length === 0) {
            list.innerHTML = '<div class="p-3 text-center text-muted">Nenhum grupo encontrado. Crie um acima.</div>';
            return;
        }

        grupos.forEach((nome) => {
            list.appendChild(createGroupManagerItem(nome));
        });

        initMassDragContainer(list);

    } catch(e) {
        console.error(e);
        list.innerHTML = '<div class="text-danger p-3">Erro ao carregar lista.</div>';
    }
}

function createGroupManagerItem(nome) {
    const li = document.createElement('li');
    li.className = 'reorder-item';
    li.setAttribute('draggable', 'true');
    li.setAttribute('data-name', nome);
    
    li.innerHTML = `
        <div class="drag-col"><i class="fas fa-grip-lines reorder-handle"></i></div>
        <div class="name-col"><span class="font-weight-500">${nome}</span></div>
        <div class="action-col text-end">
            <button class="delete-btn" title="Excluir Grupo e Conteúdo" onclick="submitMassDeleteFromList(this, '${nome}')">
                <i class="fas fa-trash-alt"></i>
            </button>
        </div>
    `;

    li.addEventListener('dragstart', () => li.classList.add('dragging'));
    li.addEventListener('dragend', () => li.classList.remove('dragging'));
    
    return li;
}

async function loadMassGroupsList(tipoCC) {
    const list = document.getElementById('listMassGroups');
    const select = document.getElementById('selectMassDeleteGroup'); // Se existir em legado
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
        if (grupos.length > 0) {
            grupos.forEach(g => {
                htmlList += `
                    <div class="group-list-item" onclick="selectMassGroup('${g}', this)">
                        <span><i class="fas fa-folder text-warning me-2"></i> ${g}</span>
                        <i class="fas fa-chevron-right"></i>
                    </div>`;
            });
        } else {
            htmlList = '<div class="p-3 text-center text-muted">Vazio</div>';
        }
        list.innerHTML = htmlList;
        
        if(select) {
            let htmlSelect = '<option value="" disabled selected>Selecione...</option>';
            grupos.forEach(g => htmlSelect += `<option value="${g}">${g}</option>`);
            select.innerHTML = htmlSelect;
        }
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
    
    // CORREÇÃO: Lê do dataset.code
    const tipoCC = document.getElementById('lblMassType').dataset.code;
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
    // CORREÇÃO: Lê do dataset.code
    const tipoCC = document.getElementById('lblMassType').dataset.code;
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
    // CORREÇÃO: Lê do dataset.code
    const tipoCC = document.getElementById('lblMassType').dataset.code;
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

async function submitMassCreate() {
    const input = document.getElementById('inputMassCreateName');
    const nome = input.value.trim();
    // CORREÇÃO: Lê do dataset.code
    const tipoCC = document.getElementById('lblMassType').dataset.code;
    
    if(!nome) return showToast('Digite um nome para o grupo.');
    
    const url = getRoute(null, '/Configuracao/AddSubgrupoSistematico', 'config');
    
    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({nome: nome, tipo_cc: tipoCC})
        });
        
        if (r.ok) {
            showToast('Grupo Criado!');
            input.value = ''; 
            await loadGroupManagerList(tipoCC);
            loadTree(); 
        } else {
            const d = await r.json();
            alert(d.error || 'Erro ao criar');
        }
    } catch(e) { alert('Erro de conexão'); }
}

async function submitMassDeleteFromList(btn, nome) {
    if(!confirm(`⚠️ ATENÇÃO: Isso excluirá o grupo "${nome}" de TODOS os Centros de Custo deste tipo, incluindo todas as contas vinculadas a ele.\n\nTem certeza absoluta?`)) return;

    // CORREÇÃO: Lê do dataset.code
    const tipoCC = document.getElementById('lblMassType').dataset.code;
    const url = getRoute(null, '/Configuracao/DeleteSubgrupoEmMassa', 'config');
    
    const originalIcon = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    btn.disabled = true;

    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({nome_grupo: nome, tipo_cc: tipoCC})
        });

        if (r.ok) {
            showToast('Grupo Excluído com sucesso.');
            const li = btn.closest('li');
            li.remove();
            loadTree();
        } else {
            const d = await r.json();
            alert(d.error || 'Erro ao excluir');
            btn.innerHTML = originalIcon;
            btn.disabled = false;
        }
    } catch(e) { 
        alert('Erro de conexão'); 
        btn.innerHTML = originalIcon;
        btn.disabled = false;
    }
}

function initMassDragContainer(container) {
    container.addEventListener('dragover', e => {
        e.preventDefault();
        const afterElement = getDragAfterElement(container, e.clientY);
        const draggable = document.querySelector('.reorder-list .dragging'); 
        if (!draggable) return;
        
        if (afterElement == null) {
            container.appendChild(draggable);
        } else {
            container.insertBefore(draggable, afterElement);
        }
    });
}

function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('.reorder-item:not(.dragging)')];

    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

async function submitMassReorder() {
    const list = document.getElementById('listGroupManager');
    const items = list.querySelectorAll('.reorder-item');
    // CORREÇÃO: Lê do dataset.code
    const tipoCC = document.getElementById('lblMassType').dataset.code;
    
    const novaOrdemNomes = Array.from(items).map(li => li.getAttribute('data-name'));
    
    if(novaOrdemNomes.length === 0) return;

    const btn = document.querySelector('#tabGroupManager .modal-footer-embedded button');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Salvando...';
    btn.disabled = true;

    const url = getRoute('reordenarEmMassa', '/Ordenamento/ReordenarEmMassa', 'ordem');

    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                tipo_cc: tipoCC,
                ordem_nomes: novaOrdemNomes
            })
        });

        if(r.ok) {
            const data = await r.json();
            showToast(data.msg || 'Ordem aplicada com sucesso!');
            await loadGroupManagerList(tipoCC); 
            await autoSync(); 
            await loadTree();
        } else {
            const err = await r.json();
            alert('Erro: ' + (err.error || 'Falha desconhecida'));
        }
    } catch(e) {
        console.error(e);
        alert('Erro de conexão ao salvar ordem.');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// --- REPLICAÇÃO INTEGRAL DE TIPO CC ---

let tipoDestinoSelecionado = null;

// ==========================================================================
// 9. REPLICAÇÃO INTEGRAL (TIPO -> TIPO)
// ==========================================================================

async function openReplicarTipoModal() {
    // Verifica se é um nó de tipo (ex: "tipo_Oper")
    if (!contextNode.id.startsWith('tipo_')) return;
    
    tipoDestinoIntegral = contextNode.id.replace('tipo_', '');
    const nomeDestino = getLabelTipoCC(tipoDestinoIntegral);
    
    const modal = document.getElementById('modalReplicar');
    const content = document.getElementById('listaDestinos');
    const btn = document.querySelector('#modalReplicar .btn-primary');
    const title = document.querySelector('#modalReplicar .modal-header h3');
    const headerInfo = document.querySelector('#modalReplicar .modal-body .mb-2') || document.querySelector('#lblOrigemReplicar').parentElement;

    // 1. Adapta o Modal (Reutiliza a estrutura visual)
    if(title) title.innerText = "Replicar Estrutura Completa";
    
    // Altera o cabeçalho para focar no DESTINO (que será apagado)
    if(headerInfo) {
        headerInfo.innerHTML = `
            <div style="background:#fff5f5; border-left:4px solid #e74c3c; padding:10px;">
                <h5 style="margin:0; color:#c0392b;">DESTINO: ${nomeDestino}</h5>
                <small style="color:#7f8c8d;">Todo o conteúdo deste tipo será APAGADO e substituído.</small>
            </div>
            <div style="margin-top:15px; font-weight:bold;">Selecione a ORIGEM (Modelo):</div>
        `;
    }

    // 2. Preenche lista de Tipos de Origem (excluindo o destino atual)
    const tiposDisponiveis = Object.keys(MAPA_TIPOS_CC).filter(t => t !== tipoDestinoIntegral);

    if (tiposDisponiveis.length === 0) {
        content.innerHTML = '<div class="alert alert-warning">Não há outros tipos cadastrados para usar como origem.</div>';
        btn.disabled = true;
    } else {
        let html = `<select id="selectTipoOrigemIntegral" class="form-select" style="width:100%; padding:10px; font-size:1.1em; margin-bottom:15px;">
            <option value="" selected disabled>-- Selecione o Tipo de Origem --</option>`;
        
        tiposDisponiveis.forEach(t => {
            html += `<option value="${t}">📂 ${getLabelTipoCC(t)}</option>`;
        });
        
        html += `</select>
        <div class="alert alert-info small">
            <i class="fas fa-info-circle"></i> 
            A estrutura de grupos e vínculos de contas da origem selecionada será copiada para <strong>todos</strong> os Centros de Custo de <em>${nomeDestino}</em>.
        </div>`;
        
        content.innerHTML = html;
        btn.disabled = false;
    }

    // 3. Configura o Botão de Ação
    btn.onclick = submitReplicarTipoAction; // Aponta para a nova função
    btn.innerHTML = '<i class="fas fa-exchange-alt"></i> Substituir Tudo';
    btn.classList.remove('btn-primary');
    btn.classList.add('btn-danger'); // Muda cor para indicar perigo (se CSS permitir)

    // Abre o modal
    openModal('modalReplicar');
}

async function submitReplicarTipoAction() {
    const select = document.getElementById('selectTipoOrigemIntegral');
    if(!select || !select.value) return showToast("Por favor, selecione uma origem.");
    
    const tipoOrigem = select.value;
    const nomeDestino = getLabelTipoCC(tipoDestinoIntegral);
    const nomeOrigem = getLabelTipoCC(tipoOrigem);

    // Logs de Debug do Cliente
    console.group("🚀 Debug: Replicar Tipo CC");
    console.log(`Origem Selecionada: ${tipoOrigem} (${nomeOrigem})`);
    console.log(`Destino Alvo: ${tipoDestinoIntegral} (${nomeDestino})`);
    console.log("Ação: Substituição Integral com Transformação de String");

    // Confirmação Dupla
    if (!confirm(`⚠️ ATENÇÃO: Iniciando clonagem de '${nomeOrigem}' para '${nomeDestino}'.\nIsso apagará TODO o conteúdo de '${nomeDestino}'.\n\nConfirma?`)) {
        console.log("Cancelado pelo usuário.");
        console.groupEnd();
        return;
    }

    // Prepara UI
    const btn = document.querySelector('#modalReplicar .btn-primary') || document.querySelector('#modalReplicar .btn-danger');
    const txtOriginal = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processando...';
    btn.disabled = true;

    const url = getRoute('replicarTipoIntegral', '/Configuracao/ReplicarTipoIntegral', 'config');

    try {
        console.log("Enviando requisição para API...");
        const r = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                tipo_origem: tipoOrigem,
                tipo_destino: tipoDestinoIntegral
            })
        });
        
        const data = await r.json();

        if (r.ok) {
            console.log("✅ Sucesso API:", data.msg);
            showToast("Replicação concluída com sucesso!");
            closeModals();
            
            // Restaura estilo do botão
            btn.classList.add('btn-primary');
            btn.classList.remove('btn-danger');
            
            console.log("Atualizando interface...");
            await autoSync(); 
            await loadTree(); 
        } else {
            console.error("❌ Erro API:", data.error);
            alert("Erro na replicação: " + (data.error || "Erro desconhecido"));
        }
    } catch (e) {
        console.error("❌ Erro de Rede/JS:", e);
        alert("Erro de comunicação: " + e.message);
    } finally {
        if(btn) {
            btn.innerHTML = txtOriginal;
            btn.disabled = false;
        }
        console.groupEnd();
    }
}

function submitMassDelete() {
    // CORREÇÃO: Lê do dataset.code
    const nome = document.getElementById('selectMassDeleteGroup').value;
    const tipoCC = document.getElementById('lblMassType').dataset.code;
    if(!nome) return;
    if(!confirm('Isso apagará o grupo e contas de TODOS os CCs. Continuar?')) return;
    const url = getRoute(null, '/Configuracao/DeleteSubgrupoEmMassa', 'config');
    fetchAPI(url, {nome_grupo:nome, tipo_cc:tipoCC}, 'Grupo Excluído!');
}

function submitMassUnlink() {
    // CORREÇÃO: Lê do dataset.code
    const c = document.getElementById('inputMassUnlinkConta').value;
    const tipoCC = document.getElementById('lblMassType').dataset.code;
    if(!c) return;
    const url = getRoute(null, '/Configuracao/DesvincularContaEmMassa', 'config');
    fetchAPI(url, {conta:c, tipo_cc:tipoCC}, 'Vínculo removido!');
}

// ==========================================================================
// 8. HELPERS
// ==========================================================================

function openAddRootGroup() {
    contextNode = { id: 'root', text: 'RAIZ DO RELATÓRIO', type: 'root' };
    openModal('modalAddSub');
    const lbl = document.getElementById('lblParentName');
    if (lbl) {
        lbl.innerText = contextNode.text;
        lbl.style.color = '#e74c3c'; 
        lbl.style.fontWeight = 'bold';
    }
    resetInput('inputSubName');
}

async function openReplicarModal() {
    openModal('modalReplicar');
    
    // RESET DE INTERFACE (Para evitar conflito com a Replicação de Tipo)
    const btn = document.querySelector('#modalReplicar .btn-primary');
    const title = document.querySelector('#modalReplicar .modal-header h3');
    const headerInfo = document.querySelector('#modalReplicar .modal-body .mb-2') || document.querySelector('#lblOrigemReplicar').parentElement;

    if(btn) {
        btn.onclick = submitReplicar; // Restaura função original
        btn.innerHTML = 'Replicar';
        btn.disabled = false;
    }
    if(title) title.innerText = "Replicar Estrutura (Subgrupo)";
    
    // Restaura o cabeçalho padrão
    if(headerInfo) {
        headerInfo.innerHTML = `Origem: <strong id="lblOrigemReplicar">${contextNode.text}</strong>`;
    }

    // Lógica original de carregar destinos
    const list = document.getElementById('listaDestinos');
    list.innerHTML = '<div class="text-center text-muted p-2"><i class="fas fa-spinner fa-spin"></i> Carregando destinos...</div>';
    
    try {
        const url = getRoute('getDadosArvore', '/Configuracao/GetDadosArvore', 'config');
        const r = await fetch(url);
        const data = await r.json();
        let html = '';
        data.forEach(root => {
            if(root.type === 'root_tipo') {
                html += `<div style="background:var(--bg-secondary); padding:5px; font-weight:bold; margin-top:8px; border-radius:4px;">${root.text}</div>`;
                root.children.forEach(cc => {
                    // Não mostra o próprio nó origem na lista de destinos
                    if(cc.id !== contextNode.id) {
                        html += `
                        <label style="display:block; padding:8px 5px; cursor:pointer; border-bottom:1px solid #eee;">
                            <input type="checkbox" class="chk-dest" value="${cc.id.replace('cc_','')}"> 
                            <span style="margin-left:8px;">${cc.text}</span>
                        </label>`;
                    }
                });
            }
        });
        list.innerHTML = html || '<div class="p-2">Nenhum destino disponível.</div>';
    } catch(e){ 
        list.innerHTML = `<div class="text-danger p-2">Erro: ${e.message}</div>`; 
    }
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
    // Reset de estado
    currentEditingNodeId = null;
    document.getElementById('inputCalcNome').value = '';
    document.getElementById('inputCalcOrdem').value = '50';
    document.getElementById('selectCalcOperacao').value = 'soma';
    
    // Reset da Cor
    document.getElementById('inputCalcColor').value = '#34495e';

    const modalTitle = document.querySelector('#modalAddCalculado .modal-header h3');
    if(modalTitle) modalTitle.innerText = "Novo Nó Calculado";

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
    
    const nosManuais = operandosDisponiveis.nos_virtuais.filter(n => !n.is_calculado);
    const nosCalculados = operandosDisponiveis.nos_virtuais.filter(n => n.is_calculado);
    const subgrupos = operandosDisponiveis.subgrupos_raiz || [];

    operandosSelecionados.forEach((op, idx) => {
        container.innerHTML += `
            <div class="operando-item" data-index="${idx}">
                <select class="form-select form-select-sm" onchange="updateOperando(${idx}, this)">
                    <option value="" disabled ${!op.id ? 'selected' : ''}>Selecione...</option>
                    
                    <optgroup label="Tipos de Centro de Custo">
                        ${operandosDisponiveis.tipos_cc.map(t => 
                            `<option value="tipo_cc:${t.id}" ${op.tipo === 'tipo_cc' && op.id === t.id ? 'selected' : ''}>
                                📂 ${getLabelTipoCC(t.nome)} </option>`
                        ).join('')}
                    </optgroup>

                    <optgroup label="Grupos Operacionais (Subgrupos)">
                        ${subgrupos.map(sg => 
                            `<option value="subgrupo:${sg.nome}" ${op.tipo === 'subgrupo' && op.id === sg.nome ? 'selected' : ''}>
                                📁 ${sg.nome}
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
    operandosSelecionados.push({ tipo: 'tipo_cc', id: 'Oper', label: 'CUSTOS' }); // Default visual
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
    
    // Captura e formata a cor
    const cor = document.getElementById('inputCalcColor').value;
    const estiloCss = `background-color: ${cor}; font-weight: bold; color: #000000;`;

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
    
    // DECISÃO: UPDATE ou CREATE
    if (currentEditingNodeId) {
        // Modo Edição
        const url = getRoute(null, '/Configuracao/UpdateNoCalculado', 'config');
        fetchAPI(url, {
            id: currentEditingNodeId,
            nome: nome,
            formula: formula,
            ordem: ordem,
            tipo_exibicao: tipoExibicao,
            estilo_css: estiloCss // Envia o CSS
        }, 'Cálculo atualizado com sucesso!');
    } else {
        // Modo Criação
        const url = getRoute(null, '/Configuracao/AddNoCalculado', 'config');
        fetchAPI(url, {
            nome: nome,
            formula: formula,
            ordem: ordem,
            tipo_exibicao: tipoExibicao,
            estilo_css: estiloCss // Envia o CSS
        }, 'Nó calculado criado!');
    }
}

document.getElementById('selectCalcOperacao')?.addEventListener('change', atualizarPreviewFormula);