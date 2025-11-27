let globalTodasContas = [];
let contextNode = { id: null, type: null, text: null, ordem: null };
let clipboard = null;
let currentSelectedGroup = null;
let ordenamentoAtivo = false;

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Carrega as listas de contas (independente)
    loadContasList();
    
    // 2. PRIMEIRO verifica se o ordenamento está ativo
    // O await garante que o código pare aqui até o servidor responder
    await verificarOrdenamento(); 
    
    // 3. SÓ AGORA carrega a árvore, já sabendo o estado correto do ordenamento
    loadTree(); 
    
    // Event listeners globais
    document.addEventListener('click', () => document.getElementById('contextMenu').style.display = 'none');
    document.querySelectorAll('.dre-modal-overlay').forEach(o => o.addEventListener('click', e => { if(e.target === o) closeModals(); }));
    
    // Atalhos de teclado
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
    
    document.addEventListener('click', () => document.getElementById('contextMenu').style.display = 'none');
    document.querySelectorAll('.dre-modal-overlay').forEach(o => o.addEventListener('click', e => { if(e.target === o) closeModals(); }));
    
    // Atalhos de teclado para reordenação
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

// --- VERIFICAÇÃO E CONTROLE DE ORDENAMENTO ---
async function verificarOrdenamento() {
    const toolbar = document.getElementById('ordenamentoToolbar');
    const indicator = document.getElementById('ordenamentoIndicator');
    const statusText = document.getElementById('ordenamentoStatusText');
    const btnInit = document.getElementById('btnInicializarOrdem');
    const btnReset = document.getElementById('btnResetarOrdem');
    const btnNorm = document.getElementById('btnNormalizarOrdem');
    
    try {
        const r = await fetch('/Ordenamento/GetFilhosOrdenados', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ contexto_pai: 'root' })
        });
        
        if (r.ok) {
            const data = await r.json();
            ordenamentoAtivo = data.length > 0;
            
            if (ordenamentoAtivo) {
                toolbar.classList.remove('inactive');
                indicator.classList.add('active');
                indicator.classList.remove('inactive');
                statusText.innerHTML = '<strong class="text-success">Ordenamento Ativo</strong> - Arraste para reordenar';
                btnInit.style.display = 'none';
                btnReset.style.display = 'inline-block';
                btnNorm.style.display = 'inline-block';
            } else {
                toolbar.classList.add('inactive');
                indicator.classList.remove('active');
                indicator.classList.add('inactive');
                statusText.innerHTML = '<strong class="text-warning">Ordenamento Inativo</strong> - Clique para ativar';
                btnInit.style.display = 'inline-block';
                btnReset.style.display = 'none';
                btnNorm.style.display = 'none';
            }
        }
    } catch (e) {
        console.warn('Ordenamento não disponível:', e);
        toolbar.classList.add('inactive');
        statusText.innerHTML = '<span class="text-danger">API de ordenamento não encontrada</span>';
    }
}

async function inicializarOrdenamento() {
    if (!confirm('Isso irá criar a estrutura de ordenamento baseada na configuração atual. Continuar?')) return;
    
    try {
        showToast('Inicializando ordenamento...');
        const r = await fetch('/Ordenamento/Inicializar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ limpar: false })
        });
        
        const data = await r.json();
        if (r.ok) {
            showToast(data.msg || 'Ordenamento inicializado!');
            verificarOrdenamento();
            loadTree();
        } else {
            alert('Erro: ' + data.error);
        }
    } catch (e) {
        alert('Erro de conexão');
    }
}

async function resetarOrdenamento() {
    if (!confirm('ATENÇÃO: Isso irá RESETAR toda a ordem para o padrão. Continuar?')) return;
    
    try {
        const r = await fetch('/Ordenamento/Inicializar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ limpar: true })
        });
        
        if (r.ok) {
            showToast('Ordenamento resetado!');
            loadTree();
        }
    } catch (e) {
        alert('Erro');
    }
}

async function normalizarOrdenamento() {
    try {
        const r = await fetch('/Ordenamento/Normalizar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ contexto_pai: 'root' })
        });
        
        if (r.ok) {
            showToast('Ordem normalizada!');
        }
    } catch (e) {
        console.error(e);
    }
}

// --- FUNÇÕES DE MOVER (UP/DOWN) ---
async function moverParaCima() {
    if (!contextNode.id) return;
    await moverElemento(-1);
}

async function moverParaBaixo() {
    if (!contextNode.id) return;
    await moverElemento(1);
}

async function moverElemento(direcao) {
    // Pega o elemento visual atual
    const wrapper = document.querySelector(`.node-wrapper[data-id="${contextNode.id}"]`);
    if (!wrapper) return;
    
    const li = wrapper.closest('li');
    const ul = li.parentElement;
    const irmãos = Array.from(ul.querySelectorAll(':scope > li'));
    const indiceAtual = irmãos.indexOf(li);
    
    const novoIndice = indiceAtual + direcao;
    if (novoIndice < 0 || novoIndice >= irmãos.length) {
        showToast('Não é possível mover nesta direção');
        return;
    }
    
    // Move visualmente
    if (direcao < 0) {
        ul.insertBefore(li, irmãos[novoIndice]);
    } else {
        ul.insertBefore(li, irmãos[novoIndice].nextSibling);
    }
    
    // Animação
    wrapper.classList.add('just-reordered');
    setTimeout(() => wrapper.classList.remove('just-reordered'), 500);
    
    // Salva nova ordem
    await salvarOrdemContexto(ul);
    showToast('Posição atualizada!');
}

async function salvarOrdemContexto(ul) {
    const items = ul.querySelectorAll(':scope > li > .node-wrapper');
    const novaOrdem = [];
    
    items.forEach((item, index) => {
        const id = item.getAttribute('data-id');
        const tipo = getNodeTypeFromId(id);
        
        novaOrdem.push({
            tipo_no: tipo,
            id_referencia: extrairIdReferencia(id, tipo),
            ordem: (index + 1) * 10
        });
    });
    
    // Determina contexto pai
    const liPai = ul.parentElement;
    let contexto = 'root';
    
    if (liPai && liPai.tagName === 'LI') {
        const wrapperPai = liPai.querySelector(':scope > .node-wrapper');
        if (wrapperPai) {
            const idPai = wrapperPai.getAttribute('data-id');
            contexto = idPai;
        }
    }
    
    try {
        await fetch('/Ordenamento/ReordenarLote', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                contexto_pai: contexto,
                nova_ordem: novaOrdem
            })
        });
    } catch (e) {
        console.error('Erro ao salvar ordem:', e);
    }
}

function getNodeTypeFromId(id) {
    if (id.startsWith('tipo_')) return 'tipo_cc';
    if (id.startsWith('virt_')) return 'virtual';
    if (id.startsWith('cc_')) return 'cc';
    if (id.startsWith('sg_')) return 'subgrupo';
    if (id.startsWith('conta_')) return 'conta';
    if (id.startsWith('cd_')) return 'conta_detalhe';
    return 'unknown';
}

function extrairIdReferencia(nodeId, tipo) {
    if (tipo === 'tipo_cc') return nodeId.replace('tipo_', '');
    if (tipo === 'virtual') return nodeId.replace('virt_', '');
    if (tipo === 'cc') return nodeId.replace('cc_', '');
    if (tipo === 'subgrupo') return nodeId.replace('sg_', '');
    if (tipo === 'conta') return nodeId.replace('conta_', '');
    if (tipo === 'conta_detalhe') return nodeId.replace('cd_', '');
    return nodeId;
}

// --- RENDERIZAÇÃO DA ÁRVORE (COM SUPORTE A ORDENAMENTO) ---
async function loadTree() {
    const rootUl = document.getElementById('treeRoot');
    
    try {
        // Tenta usar a API ordenada primeiro
        let response;
        let useOrdenada = false;
        
        if (ordenamentoAtivo) {
            try {
                response = await fetch('/Ordenamento/GetArvoreOrdenada');
                if (response.ok) {
                    useOrdenada = true;
                }
            } catch (e) {
                console.warn('API ordenada não disponível, usando padrão');
            }
        }
        
        if (!useOrdenada) {
            response = await fetch('/Configuracao/GetDadosArvore');
        }
        
        const data = await response.json();
        rootUl.innerHTML = '';
        
        if (!data || data.length === 0) { 
            rootUl.innerHTML = '<li class="text-secondary p-4 text-center">Nenhuma estrutura encontrada.<br>Comece criando um Nó Virtual ou importe do ERP.</li>'; 
            return; 
        }
        
        data.forEach(item => rootUl.appendChild(createNodeHTML(item)));
        
        // Habilita drag-drop se ordenamento ativo
        if (ordenamentoAtivo && window.dreOrdenamento) {
            setTimeout(() => window.dreOrdenamento.habilitarDragDrop(), 200);
        }
        
    } catch (error) { 
        console.error(error); 
        rootUl.innerHTML = '<li class="text-danger p-4">Erro ao carregar dados.</li>'; 
    }
}

function createNodeHTML(node) {
    const li = document.createElement('li');
    const wrapper = document.createElement('div');
    
    let typeClass = 'node-std';
    let icon = 'fa-circle';
    
    if(node.type === 'root_tipo') { typeClass = 'node-folder'; icon = 'fa-folder'; }
    else if(node.type === 'root_cc') { typeClass = 'node-cc'; icon = 'fa-building'; }
    else if(node.type === 'root_virtual') { typeClass = 'node-virtual'; icon = 'fa-layer-group'; }
    else if(node.type === 'subgrupo') { typeClass = 'node-sg'; icon = 'fa-folder-open'; }
    else if(node.type.includes('conta')) { typeClass = 'node-conta'; icon = 'fa-file-invoice'; }

    wrapper.className = `node-wrapper ${typeClass}`;
    wrapper.setAttribute('data-id', node.id);
    if (node.ordem) wrapper.setAttribute('data-ordem', node.ordem);
    
    const hasChildren = node.children && node.children.length > 0;
    
    // Drag Handle (só aparece se ordenamento ativo)
    let dragHandleHtml = '';
    if (ordenamentoAtivo) {
        dragHandleHtml = '<i class="fas fa-grip-vertical drag-handle"></i>';
    }
    
    const toggle = document.createElement('div');
    toggle.className = `toggle-icon ${hasChildren ? '' : 'invisible'}`;
    toggle.innerHTML = '<i class="fas fa-chevron-right"></i>';
    
    if(hasChildren) {
        toggle.onclick = (e) => {
            e.stopPropagation();
            toggleNode(li, toggle);
        };
        wrapper.ondblclick = (e) => {
            e.stopPropagation();
            toggleNode(li, toggle);
        };
    }

    // Badge de ordem (debug/visual)
    let ordemBadge = '';
    if (node.ordem && ordenamentoAtivo) {
        ordemBadge = `<span class="ordem-badge" title="Ordem: ${node.ordem}">#${node.ordem}</span>`;
    }

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

    wrapper.appendChild(toggle);
    wrapper.appendChild(contentSpan);
    
    wrapper.onclick = () => selectNodeUI(wrapper);
    wrapper.oncontextmenu = (e) => handleRightClick(e, node, wrapper);

    li.appendChild(wrapper);

    if (hasChildren) {
        const ul = document.createElement('ul');
        
        // Expande automaticamente os tipos e virtuais na carga inicial

        if (node.type === 'root_tipo' || node.type === 'root_virtual') {
            ul.classList.add('expanded');
            toggle.classList.add('rotated');
        }

        // ------------------------------------

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
    const uls = document.querySelectorAll('#treeRoot ul');
    const toggles = document.querySelectorAll('.toggle-icon:not(.invisible)');
    
    uls.forEach(ul => expand ? ul.classList.add('expanded') : ul.classList.remove('expanded'));
    toggles.forEach(t => expand ? t.classList.add('rotated') : t.classList.remove('rotated'));
}

function selectNodeUI(element) {
    document.querySelectorAll('.node-wrapper').forEach(el => el.classList.remove('selected'));
    element.classList.add('selected');
}

// --- MENU DE CONTEXTO ---
function handleRightClick(e, node, element) {
    e.preventDefault();
    selectNodeUI(element);
    contextNode = node;
    
    const menu = document.getElementById('contextMenu');
    
    // Esconde tudo primeiro
    const els = ['ctxRename', /* ... seus outros IDs ... */]; 
    els.forEach(id => { 
        const el = document.getElementById(id); 
        if(el) el.style.display = 'none'; 
    });

    const show = (id) => { const el = document.getElementById(id); if(el) el.style.display = 'flex'; };

    // Lógica de exibição do Renomear
    if (node.type === 'root_virtual' || node.type === 'subgrupo' || node.type === 'conta_detalhe') {
        show('ctxRename');
    }
    const showDiv = (id) => { const el = document.getElementById(id); if(el) el.style.display = 'block'; };

    // Opções de ordenamento (sempre mostrar se ativo)
    if (ordenamentoAtivo) {
        show('ctxMoveUp');
        show('ctxMoveDown');
        showDiv('divOrdem');
    }

    if (node.type === 'root_tipo') {
        show('ctxMassManager'); 
        showDiv('divSystematic');
    }
    else if (node.type === 'root_cc') {
        show('ctxAddSub');
        show('ctxReplicar');
        if(clipboard) show('ctxPaste');
    } 
    else if (node.type === 'subgrupo') {
        show('ctxAddSub');
        show('ctxCopy');
        if(clipboard) show('ctxPaste');
        showDiv('divCopy');
        show('ctxLinkConta');
        show('ctxLinkDetalhe');
        showDiv('ctxDivider');
        show('ctxDelete');
    }
    else if (node.type === 'root_virtual') {
        show('ctxAddSub');
        if(clipboard) show('ctxPaste');
        show('ctxLinkDetalhe');
        showDiv('ctxDivider');
        show('ctxDelete');
    }
    else if (node.type.includes('conta')) {
        show('ctxDelete');
    }

    const clickX = e.clientX;
    const clickY = e.clientY;
    menu.style.left = `${e.clientX}px`;
    menu.style.top = `${e.clientY}px`;
    menu.style.display = 'block';
}

// 2. NOVA FUNÇÃO PARA EXECUTAR O RENOMEAR
async function renameNode() {
    // Usa um prompt simples do navegador (pode trocar por modal se quiser mais elegância)
    const novoNome = prompt("Novo nome para: " + contextNode.text, contextNode.text);
    
    if (!novoNome || novoNome === contextNode.text) return;

    let url = '';
    
    if (contextNode.type === 'root_virtual') url = '/Configuracao/RenameNoVirtual';
    else if (contextNode.type === 'subgrupo') url = '/Configuracao/RenameSubgrupo';
    else if (contextNode.type === 'conta_detalhe') url = '/Configuracao/RenameContaPersonalizada';
    
    if (!url) return alert('Este item não pode ser renomeado.');

    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ id: contextNode.id, novo_nome: novoNome })
        });
        
        if (r.ok) {
            showToast('Renomeado com sucesso!');
            loadTree(); // Recarrega a árvore para mostrar o novo nome
        } else {
            const d = await r.json();
            alert('Erro: ' + d.error);
        }
    } catch (e) {
        console.error(e);
        alert('Erro de conexão ao renomear.');
    }
    
    document.getElementById('contextMenu').style.display = 'none';
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
    fetchAPI('/Configuracao/ColarEstrutura', { origem_id: clipboard.id, destino_id: contextNode.id }, 'Estrutura colada!');
}

async function openReplicarModal() {
    openModal('modalReplicar');
    document.getElementById('lblOrigemReplicar').innerText = contextNode.text;
    const list = document.getElementById('listaDestinos');
    list.innerHTML = '<div class="text-center p-3">Carregando...</div>';
    
    try {
        const res = await fetch('/Configuracao/GetDadosArvore');
        const data = await res.json();
        let targets = [];
        
        data.forEach(root => {
            if(root.type === 'root_tipo' && root.id !== 'root_virtual_group') {
                if(root.children) {
                    root.children.forEach(cc => {
                        if(cc.id !== contextNode.id) {
                            targets.push({ id: cc.id.replace('cc_', ''), text: cc.text, group: root.text });
                        }
                    });
                }
            }
        });

        let html = '';
        let lastGroup = '';
        targets.forEach(t => {
            if(t.group !== lastGroup) {
                html += `<div class="text-xs font-bold text-primary mt-2 mb-1 border-bottom border-secondary p-1 sticky-top" style="background:#1e2736">${t.group}</div>`;
                lastGroup = t.group;
            }
            html += `
                <div class="d-flex align-items-center gap-2 py-1 px-2 hover-bg">
                    <input type="checkbox" class="chk-dest" value="${t.id}">
                    <span class="text-sm">${t.text}</span>
                </div>
            `;
        });
        list.innerHTML = html;
    } catch(e) { list.innerHTML = 'Erro ao carregar lista.'; }
}

function toggleAllDestinos() {
    const chks = document.querySelectorAll('.chk-dest');
    chks.forEach(c => c.checked = !c.checked);
    const count = document.querySelectorAll('.chk-dest:checked').length;
    document.getElementById('lblTotalSelecionados').innerText = `${count} selecionados`;
}

async function submitReplicar() {
    const ids = Array.from(document.querySelectorAll('.chk-dest:checked')).map(c => c.value);
    if(ids.length === 0) return alert("Selecione destinos.");
    if(!confirm(`Replicar para ${ids.length} locais?`)) return;
    fetchAPI('/Configuracao/ReplicarEstrutura', { origem_node_id: contextNode.id, destinos_ids: ids }, 'Replicação concluída!');
}

function openMassManager() {
    const tipoCC = contextNode.id.replace('tipo_', '');
    document.getElementById('lblMassType').innerText = tipoCC;
    loadMassGroupsList(tipoCC);
    document.getElementById('inputMassCreateName').value = '';
    document.getElementById('inputMassLinkConta').value = '';
    document.getElementById('inputMassUnlinkConta').value = '';
    openModal('modalMassManager');
    switchMassTab('tabCreateGroup', document.querySelector('.mass-nav-item')); 
}

function switchMassTab(tabId, navElement) {
    document.querySelectorAll('.mass-tab').forEach(t => t.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    document.querySelectorAll('.mass-nav-item').forEach(n => n.classList.remove('active'));
    if(navElement) navElement.classList.add('active');
}

async function loadMassGroupsList(tipoCC) {
    const listContainer = document.getElementById('listMassGroups');
    listContainer.innerHTML = '<div class="text-center p-3 text-secondary"><i class="fas fa-spinner fa-spin"></i></div>';
    
    document.getElementById('noGroupSelected').style.display = 'flex';
    document.getElementById('groupDetails').style.display = 'none';
    currentSelectedGroup = null;

    const selDel = document.getElementById('selectMassDeleteGroup');
    selDel.innerHTML = '<option>Carregando...</option>';

    try {
        const r = await fetch('/Configuracao/GetSubgruposPorTipo', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ tipo_cc: tipoCC })
        });
        const grupos = await r.json();

        let htmlList = '';
        let htmlSelect = '<option value="" disabled selected>Selecione...</option>';

        if(grupos.length > 0) {
            grupos.forEach(g => {
                htmlList += `
                    <div class="group-list-item" onclick="selectMassGroup('${g}', this)">
                        <span><i class="fas fa-folder text-warning me-2"></i> ${g}</span>
                        <i class="fas fa-chevron-right"></i>
                    </div>
                `;
                htmlSelect += `<option value="${g}">${g}</option>`;
            });
        } else {
            htmlList = '<div class="p-3 text-muted text-center text-sm">Nenhum grupo criado.</div>';
            htmlSelect = '<option disabled>Vazio</option>';
        }
        
        listContainer.innerHTML = htmlList;
        selDel.innerHTML = htmlSelect;

    } catch(e) { console.error(e); }
}

async function selectMassGroup(groupName, element) {
    currentSelectedGroup = groupName;
    const tipoCC = document.getElementById('lblMassType').innerText;

    document.querySelectorAll('.group-list-item').forEach(i => i.classList.remove('active'));
    element.classList.add('active');
    
    document.getElementById('noGroupSelected').style.display = 'none';
    document.getElementById('groupDetails').style.display = 'flex';
    document.getElementById('lblSelectedGroup').innerText = groupName;
    document.getElementById('inputMassLinkConta').value = ''; 

    const areaContas = document.getElementById('listLinkedAccounts');
    areaContas.innerHTML = '<div class="text-secondary w-100 text-center mt-4"><i class="fas fa-spinner fa-spin"></i></div>';

    try {
        const r = await fetch('/Configuracao/GetContasDoGrupoMassa', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ tipo_cc: tipoCC, nome_grupo: groupName })
        });
        const contasVinculadas = await r.json(); 
        
        document.getElementById('lblCountAccounts').innerText = `${contasVinculadas.length} contas`;
        updateMassDatalist(contasVinculadas);

        if(contasVinculadas.length === 0) {
            areaContas.innerHTML = '<div class="empty-state">Nenhuma conta vinculada ainda.</div>';
        } else {
            let tags = '';
            contasVinculadas.forEach(c => {
                const contaInfo = globalTodasContas.find(x => x.numero == c);
                const labelConta = contaInfo ? `${c} - ${contaInfo.nome.substring(0, 15)}...` : c;

                tags += `
                    <div class="account-tag">
                        ${labelConta}
                        <i class="fas fa-times remove-btn" onclick="removeAccountFromGroup('${c}')" title="Desvincular"></i>
                    </div>
                `;
            });
            areaContas.innerHTML = tags;
        }
    } catch(e) { 
        console.error(e);
        areaContas.innerHTML = '<div class="text-danger">Erro ao carregar.</div>'; 
    }
}

async function submitMassCreate() {
    const nome = document.getElementById('inputMassCreateName').value;
    const tipoCC = document.getElementById('lblMassType').innerText;
    if(!nome) return alert('Nome obrigatório.');
    fetchAPI('/Configuracao/AddSubgrupoSistematico', { nome: nome, tipo_cc: tipoCC });
}

async function submitMassDelete() {
    const nome = document.getElementById('selectMassDeleteGroup').value;
    const tipoCC = document.getElementById('lblMassType').innerText;
    if(!nome) return alert('Selecione um grupo.');
    if(!confirm(`ATENÇÃO: Isso excluirá o grupo "${nome}" de TODOS os CCs de ${tipoCC}. Continuar?`)) return;
    fetchAPI('/Configuracao/DeleteSubgrupoEmMassa', { nome_grupo: nome, tipo_cc: tipoCC });
}

async function submitMassUnlink() {
    const conta = document.getElementById('inputMassUnlinkConta').value;
    const tipoCC = document.getElementById('lblMassType').innerText;
    if(!conta) return alert('Digite a conta.');
    if(!confirm(`Remover o vínculo da conta ${conta} de todos os CCs?`)) return;
    fetchAPI('/Configuracao/DesvincularContaEmMassa', { tipo_cc: tipoCC, conta: conta });
}

async function addAccountToGroup() {
    if(!currentSelectedGroup) return;
    const conta = document.getElementById('inputMassLinkConta').value;
    const tipoCC = document.getElementById('lblMassType').innerText;
    if(!conta) return alert('Digite a conta.');

    try {
        const r = await fetch('/Configuracao/VincularContaEmMassa', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ tipo_cc: tipoCC, nome_subgrupo: currentSelectedGroup, conta: conta })
        });
        if(r.ok) {
            document.getElementById('inputMassLinkConta').value = '';
            const activeItem = document.querySelector('.group-list-item.active');
            if(activeItem) selectMassGroup(currentSelectedGroup, activeItem);
            showToast(`Conta ${conta} adicionada!`);
        } else {
            const d = await r.json(); alert('Erro: ' + d.error);
        }
    } catch(e) { alert('Erro de conexão'); }
}

async function removeAccountFromGroup(conta) {
    if(!currentSelectedGroup) return;
    const tipoCC = document.getElementById('lblMassType').innerText;
    if(!confirm(`Remover conta ${conta} deste grupo em TODOS os CCs?`)) return;

    try {
        const r = await fetch('/Configuracao/DesvincularContaEmMassa', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ tipo_cc: tipoCC, conta: conta })
        });
        if(r.ok) {
            const activeItem = document.querySelector('.group-list-item.active');
            if(activeItem) selectMassGroup(currentSelectedGroup, activeItem);
            showToast('Conta removida.');
        }
    } catch(e) { alert('Erro ao remover'); }
}

function openModal(id) {
    const m = document.getElementById(id);
    document.getElementById('contextMenu').style.display = 'none';
    m.classList.add('active'); m.style.setProperty('display', 'flex', 'important');
    
    if(id==='modalAddSub') { document.getElementById('lblParentName').innerText = contextNode.text; resetInput('inputSubName'); }
    if(id==='modalLinkDetalhe') { document.getElementById('lblDetailTarget').innerText = contextNode.text; resetInput('inputDetailConta'); document.getElementById('inputDetailName').value = ''; }
    if(id==='modalAddVirtual') resetInput('inputVirtualName');

    if(id==='modalLinkConta') { 
        document.getElementById('lblGroupTarget').innerText = contextNode.text; 
        document.getElementById('inputContaSearch').value = '';
        loadStdGroupAccounts(contextNode.id);
    }
}

function resetInput(id){ const e = document.getElementById(id); if(e){ e.value=''; setTimeout(()=>e.focus(),100); } }
function closeModals(){ document.querySelectorAll('.dre-modal-overlay').forEach(m=>{ m.classList.remove('active'); m.style.display='none'; }); }
function showToast(msg) { const t = document.getElementById("toast"); t.innerHTML = `<i class="fas fa-check"></i> ${msg}`; t.className = "show"; setTimeout(() => t.className = "", 3000); }

async function fetchAPI(url, body, successMsg='Sucesso!') {
    try {
        const r = await fetch(url, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
        const data = await r.json();

        if(r.ok) { 
            showToast(data.msg || successMsg); 
            closeModals(); 
            loadTree(); 
        } else { 
            alert("Erro: "+ data.error); 
        }
    } catch(e) { alert("Erro de conexão."); }
    document.getElementById('contextMenu').style.display = 'none';
}

async function submitAddVirtual() { const n=document.getElementById('inputVirtualName').value; if(!n)return alert('Nome?'); fetchAPI('/Configuracao/AddNoVirtual', {nome:n}); }
async function submitAddSub() { const n=document.getElementById('inputSubName').value; if(!n)return alert('Nome?'); fetchAPI('/Configuracao/AddSubgrupo', {nome:n, parent_id:contextNode.id}); }

async function submitLinkConta() { 
    const c = document.getElementById('inputContaSearch').value; 
    if(!c) return alert('Conta?'); 
    try {
        const r = await fetch('/Configuracao/VincularConta', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ conta: c, subgrupo_id: contextNode.id })
        });
        if(r.ok) {
            showToast('Conta vinculada!');
            document.getElementById('inputContaSearch').value = '';
            loadStdGroupAccounts(contextNode.id);
            loadTree();
        } else {
            const d = await r.json(); alert(d.error);
        }
    } catch(e) { alert("Erro de conexão"); }
}

async function submitLinkDetalhe() { const c=document.getElementById('inputDetailConta').value; const n=document.getElementById('inputDetailName').value; if(!c)return alert('Conta?'); fetchAPI('/Configuracao/VincularContaDetalhe', {conta:c, nome_personalizado:n, parent_id:contextNode.id}); }

async function deleteNode() {
    if(!confirm(`Remover "${contextNode.text}"?`)) return;
    let url = '';
    if(contextNode.type==='subgrupo') url='/Configuracao/DeleteSubgrupo';
    if(contextNode.type.includes('conta')) url='/Configuracao/DesvincularConta';
    if(contextNode.type==='root_virtual') url='/Configuracao/DeleteNoVirtual';
    if(!url) return;
    fetchAPI(url, {id:contextNode.id}, 'Item removido.');
}

async function loadContasList() {
    try {
        const r = await fetch('/Configuracao/GetContasDisponiveis');
        const d = await r.json();
        
        globalTodasContas = d; 

        const dl = document.getElementById('contasDataList'); 
        dl.innerHTML = '';
        d.forEach(c => { 
            const o = document.createElement('option'); 
            o.value = c.numero; 
            o.label = c.nome; 
            dl.appendChild(o); 
        });
    } catch(e){}
}

function updateMassDatalist(contasJaVinculadas) {
    const dlMass = document.getElementById('massContasDataList');
    dlMass.innerHTML = ''; 
    const contasFiltradas = globalTodasContas.filter(c => !contasJaVinculadas.includes(c.numero.toString()));
    contasFiltradas.forEach(c => {
        const o = document.createElement('option');
        o.value = c.numero;
        o.label = c.nome;
        dlMass.appendChild(o);
    });
}

async function loadStdGroupAccounts(nodeId) {
    const areaContas = document.getElementById('listStdLinkedAccounts');
    areaContas.innerHTML = '<div class="text-center text-secondary pt-4"><i class="fas fa-spinner fa-spin"></i></div>';
    
    const dbId = nodeId.replace('sg_', ''); 

    try {
        const r = await fetch('/Configuracao/GetContasDoSubgrupo', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ id: dbId })
        });
        
        const data = await r.json();

        if (!r.ok || !Array.isArray(data)) {
            console.error("Erro servidor:", data);
            areaContas.innerHTML = '<div class="text-danger text-center pt-4 text-sm">Erro ao buscar contas.</div>';
            document.getElementById('lblCountStd').innerText = "0";
            return;
        }

        const contasVinculadas = data;

        document.getElementById('lblCountStd').innerText = contasVinculadas.length;
        updateStdDatalist(contasVinculadas);

        if(contasVinculadas.length === 0) {
            areaContas.innerHTML = '<div class="text-center text-secondary pt-4 text-sm">Nenhuma conta vinculada.</div>';
        } else {
            let tags = '';
            contasVinculadas.forEach(c => {
                const contaInfo = globalTodasContas.find(x => x.numero == c);
                const labelConta = contaInfo ? `${c} - ${contaInfo.nome.substring(0, 15)}...` : c;

                tags += `
                    <div class="account-tag">
                        ${labelConta}
                        <i class="fas fa-times remove-btn" onclick="removeStdAccount('${c}')" title="Desvincular"></i>
                    </div>
                `;
            });
            areaContas.innerHTML = tags;
        }

    } catch(e) { 
        console.error(e);
        areaContas.innerHTML = '<div class="text-danger text-center pt-4">Erro de conexão.</div>';
    }
}

function updateStdDatalist(contasJaVinculadas) {
    const dl = document.getElementById('stdContasDataList');
    dl.innerHTML = ''; 
    const disponiveis = globalTodasContas.filter(c => !contasJaVinculadas.includes(c.numero.toString()));
    disponiveis.forEach(c => {
        const o = document.createElement('option');
        o.value = c.numero;
        o.label = c.nome;
        dl.appendChild(o);
    });
}

async function removeStdAccount(conta) {
    if(!confirm(`Desvincular a conta ${conta}?`)) return;
    try {
        const nodeFakeId = `conta_${conta}`;
        const r = await fetch('/Configuracao/DesvincularConta', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ id: nodeFakeId })
        });
        if(r.ok) {
            showToast('Desvinculado.');
            loadStdGroupAccounts(contextNode.id);
            loadTree();
        }
    } catch(e) { alert("Erro ao remover"); }
}

// ADICIONE NO FINAL DO SCRIPT
async function sincronizarOrdem() {
    const btn = event.currentTarget;
    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processando...';
    btn.disabled = true;

    try {
        // Chama a rota Inicializar com limpar=false (apenas adiciona novos)
        const r = await fetch('/Ordenamento/Inicializar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ limpar: false })
        });
        
        if (r.ok) {
            const data = await r.json();
            showToast(data.msg || 'Sincronização concluída!');
            loadTree(); // Recarrega a árvore para mostrar os novos itens
        } else {
            alert('Erro na sincronização');
        }
    } catch (e) {
        console.error(e);
        alert('Erro de conexão');
    } finally {
        btn.innerHTML = originalHtml;
        btn.disabled = false;
    }
}
