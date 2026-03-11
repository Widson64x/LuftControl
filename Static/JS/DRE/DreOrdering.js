// Static/JS/DreOrdenamento.js
/**
 * Sistema de Ordenamento Drag-and-Drop Visual para Árvore DRE
 * * Características:
 * - Item segue o mouse durante o arraste
 * - Indicador visual de "encaixe" entre elementos
 * - Animações suaves de reposicionamento
 * - Validação de hierarquia em tempo real
 */

class DreOrdenamentoManager {
    constructor() {
        // Estado do drag
        this.isDragging = false;
        this.draggedLi = null;          // O <li> sendo arrastado
        this.draggedClone = null;       // Clone visual que segue o mouse
        this.placeholder = null;        // Espaço reservado onde o item vai cair
        this.originalParent = null;     // UL original
        this.originalIndex = null;      // Índice original
        
        // Dados do nó
        this.draggedNodeData = null;
        
        // Offset do mouse
        this.dragOffset = { x: 0, y: 0 };
        
        // Configurações
        this.config = {
            intervalo: 10,
            scrollSpeed: 15,
            scrollZone: 50,
            animationDuration: 200
        };
        
        // Estado
        this.ordenamentoAtivo = false;
        this.scrollInterval = null;
        
        // Bind dos métodos
        this.onMouseDown = this.onMouseDown.bind(this);
        this.onMouseMove = this.onMouseMove.bind(this);
        this.onMouseUp = this.onMouseUp.bind(this);
    }

    /**
     * Inicializa o sistema
     */
    init() {
        this.injetarEstilos();
        this.verificarOrdenamentoAtivo();
        console.log('📊 DreOrdenamentoManager inicializado');
    }

    /**
     * Verifica se ordenamento está ativo
     */
    async verificarOrdenamentoAtivo() {
        try {
            let url;
            // Usa as rotas injetadas no HTML ou fallback
            if (typeof API_ROUTES !== 'undefined' && API_ROUTES.getFilhosOrdenados) {
                url = API_ROUTES.getFilhosOrdenados;
            } else {
                url = '/LuftControl/DreOrdenamento/ordenamento/obter-filhos'; 
            }

            const r = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ contexto_pai: 'root' })
            });
            
            if (r.ok) {
                const data = await r.json();
                this.ordenamentoAtivo = data.length > 0;
                
                if (this.ordenamentoAtivo) {
                    // Timeout aumentado para garantir que a árvore renderizou
                    setTimeout(() => this.habilitarDragDrop(), 500);
                } else {
                    console.log('⚠️ Ordenamento não inicializado');
                }
            }
        } catch (e) {
            console.warn('Ordenamento não disponível:', e);
        }
    }

    /**
     * Habilita drag-drop nos elementos
     * Chamado pelo DreTreeView após renderizar a árvore
     */
    habilitarDragDrop() {
        if (!this.ordenamentoAtivo) return;

        console.log("🔄 Reaplicando eventos de Drag & Drop...");
        
        // Seleciona todos os wrappers
        const wrappers = document.querySelectorAll('.node-wrapper');
        
        wrappers.forEach(wrapper => {
            const li = wrapper.closest('li');
            if (!li) return;
            
            // Verifica se pode ser arrastado
            const nodeType = this.getNodeType(wrapper);
            if (!this.podeSerArrastado(nodeType)) return;
            
            // Garante que o handle existe (DreTreeView já deve ter criado, mas garantimos aqui)
            let handle = wrapper.querySelector('.drag-handle');
            if (!handle) {
                handle = document.createElement('span');
                handle.className = 'drag-handle';
                handle.innerHTML = '<i class="fas fa-grip-vertical"></i>';
                wrapper.insertBefore(handle, wrapper.firstChild);
            }
            
            // CLONE E REPLACE para remover event listeners antigos e evitar duplicação
            const newHandle = handle.cloneNode(true);
            handle.parentNode.replaceChild(newHandle, handle);
            
            // Adiciona o listener
            newHandle.addEventListener('mousedown', (e) => this.onMouseDown(e, li, wrapper));
            // Previne clique duplo no handle de disparar toggle
            newHandle.addEventListener('click', (e) => e.stopPropagation());
        });
        
        // Eventos globais (apenas uma vez)
        document.removeEventListener('mousemove', this.onMouseMove);
        document.removeEventListener('mouseup', this.onMouseUp);
        document.addEventListener('mousemove', this.onMouseMove);
        document.addEventListener('mouseup', this.onMouseUp);
    }

    /**
     * Reabilita após recarregar árvore (Atalho)
     */
    reabilitar() {
        this.habilitarDragDrop();
    }

    // ========================================
    // EVENTOS DE MOUSE
    // ========================================

    onMouseDown(e, li, wrapper) {
        if (e.button !== 0) return; // Apenas botão esquerdo

        e.preventDefault();
        e.stopPropagation();
        
        this.isDragging = true;
        this.draggedLi = li;
        this.originalParent = li.parentElement;
        this.originalIndex = Array.from(this.originalParent.children).indexOf(li);
        
        // Dados do nó
        this.draggedNodeData = {
            id: wrapper.getAttribute('data-id'),
            type: this.getNodeType(wrapper),
            text: wrapper.querySelector('.node-text')?.textContent || ''
        };
        
        // Dimensões originais para calcular offset
        const rect = li.getBoundingClientRect();
        this.dragOffset = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };
        
        // Cria clone visual
        this.criarClone(li, e);
        
        // Cria placeholder
        this.criarPlaceholder(li);
        
        // Marca original como arrastando (CSS tratará opacidade)
        li.classList.add('dragging-original');
        document.body.classList.add('dragging-active');
    }

    onMouseMove(e) {
        if (!this.isDragging || !this.draggedClone) return;
        
        // Move o clone
        this.draggedClone.style.left = `${e.clientX - this.dragOffset.x}px`;
        this.draggedClone.style.top = `${e.clientY - this.dragOffset.y}px`;
        
        // Auto-scroll da árvore se chegar nas bordas
        this.handleAutoScroll(e);
        
        // Encontra posição de drop
        this.atualizarPosicaoDrop(e);
    }

    onMouseUp(e) {
        if (!this.isDragging) return;
        
        this.isDragging = false;
        this.pararAutoScroll();
        
        // Remove clone
        if (this.draggedClone) {
            this.draggedClone.remove();
            this.draggedClone = null;
        }
        
        // Remove highlights
        document.querySelectorAll('.drop-highlight').forEach(el => {
            el.classList.remove('drop-highlight', 'drop-above', 'drop-below', 'drop-inside');
        });
        
        // Se temos um placeholder válido inserido no DOM
        if (this.placeholder && this.placeholder.parentElement && this.draggedLi) {
            const newParent = this.placeholder.parentElement;
            
            // Restaura visual do item
            this.draggedLi.classList.remove('dragging-original');
            
            // Move o item real para a posição do placeholder
            newParent.insertBefore(this.draggedLi, this.placeholder);
            
            // Remove placeholder
            this.placeholder.remove();
            
            // Animação de sucesso
            const wrapper = this.draggedLi.querySelector('.node-wrapper');
            if (wrapper) {
                wrapper.classList.add('just-dropped');
                setTimeout(() => wrapper.classList.remove('just-dropped'), 500);
            }
            
            // Salva no backend
            this.salvarNovaPosicao(newParent);
        } else {
            // Cancelado
            if (this.draggedLi) this.draggedLi.classList.remove('dragging-original');
            if (this.placeholder) this.placeholder.remove();
        }
        
        document.body.classList.remove('dragging-active');
        
        this.draggedLi = null;
        this.placeholder = null;
        this.originalParent = null;
        this.draggedNodeData = null;
    }

    // ========================================
    // CRIAÇÃO DE ELEMENTOS VISUAIS
    // ========================================

    criarClone(li, e) {
        const rect = li.getBoundingClientRect();
        const wrapper = li.querySelector('.node-wrapper');
        
        this.draggedClone = document.createElement('div');
        this.draggedClone.className = 'drag-clone';
        this.draggedClone.innerHTML = wrapper.innerHTML;
        
        // Estilos do clone adaptados para o LuftCore
        Object.assign(this.draggedClone.style, {
            position: 'fixed',
            left: `${e.clientX - this.dragOffset.x}px`,
            top: `${e.clientY - this.dragOffset.y}px`,
            width: `${rect.width}px`,
            zIndex: 'var(--luft-z-tooltip)',
            pointerEvents: 'none',
            opacity: '0.95',
            transform: 'rotate(2deg) scale(1.02)',
            boxShadow: 'var(--luft-shadow-2xl)',
            background: 'var(--luft-bg-panel)',
            border: '2px solid var(--luft-primary-500)',
            borderRadius: 'var(--luft-radius-md)',
            padding: '8px 12px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            color: 'var(--luft-text-main)',
            fontSize: '0.9rem'
        });
        
        document.body.appendChild(this.draggedClone);
    }

    criarPlaceholder(li) {
        this.placeholder = document.createElement('li');
        this.placeholder.className = 'drag-placeholder';
        this.placeholder.innerHTML = `
            <div class="placeholder-inner">
                <i class="fas fa-arrow-right"></i>
                <span>Soltar aqui</span>
            </div>
        `;
        // Insere placeholder logo após o item (posição inicial)
        li.parentElement.insertBefore(this.placeholder, li.nextSibling);
    }

    // ========================================
    // LÓGICA DE POSICIONAMENTO E VALIDAÇÃO
    // ========================================

    atualizarPosicaoDrop(e) {
        const mouseY = e.clientY;
        const mouseX = e.clientX;
        
        // Remove highlight anterior
        document.querySelectorAll('.drop-highlight').forEach(el => {
            el.classList.remove('drop-highlight', 'drop-above', 'drop-below', 'drop-inside');
        });
        
        const allLis = document.querySelectorAll('#treeRoot li');
        let closestLi = null;
        let closestDistance = Infinity;
        let dropPosition = 'below'; 
        
        allLis.forEach(li => {
            if (li === this.draggedLi || li === this.placeholder) return;
            if (li.closest('.drag-placeholder')) return; // Não detecta o próprio placeholder
            
            const wrapper = li.querySelector(':scope > .node-wrapper');
            if (!wrapper) return;
            
            const rect = wrapper.getBoundingClientRect();
            
            // Tolerância horizontal para não soltar muito longe
            if (mouseX < rect.left - 50 || mouseX > rect.right + 50) return;
            
            const centerY = rect.top + rect.height / 2;
            const distance = Math.abs(mouseY - centerY);
            
            // Só considera se estiver perto o suficiente (80px)
            if (distance < closestDistance && distance < 80) {
                closestDistance = distance;
                closestLi = li;
                
                const relativeY = (mouseY - rect.top) / rect.height;
                
                if (relativeY < 0.25) {
                    dropPosition = 'above';
                } else if (relativeY > 0.75) {
                    dropPosition = 'below';
                } else {
                    const targetType = this.getNodeType(wrapper);
                    if (this.podeReceberFilhos(targetType, this.draggedNodeData.type)) {
                        dropPosition = 'inside';
                    } else {
                        dropPosition = relativeY < 0.5 ? 'above' : 'below';
                    }
                }
            }
        });
        
        if (closestLi) {
            const wrapper = closestLi.querySelector(':scope > .node-wrapper');
            const targetType = this.getNodeType(wrapper);
            const parentUl = closestLi.parentElement;
            const contexto = this.determinarContexto(parentUl);
            
            const podeDropar = this.validarDrop(this.draggedNodeData.type, targetType, contexto, dropPosition);
            
            if (podeDropar) {
                wrapper.classList.add('drop-highlight', `drop-${dropPosition}`);
                this.moverPlaceholder(closestLi, dropPosition);
            }
        }
    }

    moverPlaceholder(targetLi, position) {
        if (!this.placeholder) return;
        
        const targetUl = targetLi.parentElement;
        
        if (position === 'above') {
            targetUl.insertBefore(this.placeholder, targetLi);
        } else if (position === 'below') {
            targetUl.insertBefore(this.placeholder, targetLi.nextSibling);
        } else if (position === 'inside') {
            let childUl = targetLi.querySelector(':scope > ul');
            if (!childUl) {
                childUl = document.createElement('ul');
                childUl.className = 'tree expanded';
                targetLi.appendChild(childUl);
            }
            childUl.classList.add('expanded');
            // Abre o nó visualmente
            const toggle = targetLi.querySelector('.toggle-icon');
            if (toggle) {
                toggle.classList.remove('invisible');
                toggle.classList.add('rotated');
            }
            childUl.insertBefore(this.placeholder, childUl.firstChild);
        }
        
        this.placeholder.className = `drag-placeholder position-${position}`;
    }

    // ========================================
    // REGRAS DE HIERARQUIA 
    // ========================================

    getNodeType(element) {
        const id = element.getAttribute('data-id') || '';
        
        if (id.startsWith('tipo_')) return 'tipo_cc';
        // 'virt_' engloba nós virtuais manuais e calculados
        if (id.startsWith('virt_')) return 'virtual'; 
        if (id.startsWith('cc_')) return 'cc';
        if (id.startsWith('sg_')) return 'subgrupo';
        if (id.startsWith('conta_')) return 'conta';
        if (id.startsWith('cd_')) return 'conta_detalhe';
        
        return 'unknown';
    }

    podeSerArrastado(tipo) {
        return ['tipo_cc', 'virtual', 'cc', 'subgrupo', 'conta', 'conta_detalhe'].includes(tipo);
    }

    podeReceberFilhos(tipoContainer, tipoItem) {
        const regras = {
            'tipo_cc': ['cc'],
            'virtual': ['subgrupo', 'conta_detalhe'], 
            'cc': ['subgrupo'],
            'subgrupo': ['subgrupo', 'conta', 'conta_detalhe'] 
        };
        const permitidos = regras[tipoContainer] || [];
        return permitidos.includes(tipoItem);
    }

    validarDrop(tipoOrigem, tipoAlvo, contexto, posicao) {
        if (posicao === 'inside') {
            return this.podeReceberFilhos(tipoAlvo, tipoOrigem);
        }
        
        const regrasContexto = {
            'tipo_cc': ['root'],
            'virtual': ['root'],
            'cc': ['tipo_cc'],
            'subgrupo': ['cc', 'virtual', 'subgrupo', 'root'],
            'conta': ['subgrupo'],
            'conta_detalhe': ['subgrupo', 'virtual']
        };
        
        const permitidos = regrasContexto[tipoOrigem] || [];
        
        if (contexto === 'root') return permitidos.includes('root');
        if (contexto.startsWith('tipo_')) return permitidos.includes('tipo_cc');
        if (contexto.startsWith('cc_')) return permitidos.includes('cc');
        if (contexto.startsWith('virt_')) return permitidos.includes('virtual');
        if (contexto.startsWith('sg_')) return permitidos.includes('subgrupo');
        
        return false;
    }

    determinarContexto(ul) {
        if (ul.id === 'treeRoot') return 'root';
        const liPai = ul.parentElement;
        if (!liPai || liPai.tagName !== 'LI') return 'root';
        const wrapperPai = liPai.querySelector(':scope > .node-wrapper');
        return wrapperPai ? (wrapperPai.getAttribute('data-id') || 'root') : 'root';
    }

    // ========================================
    // AUTO-SCROLL
    // ========================================

    handleAutoScroll(e) {
        const container = document.getElementById('treeContainer'); // ID fixo definido no HTML
        if (!container) return;
        
        const rect = container.getBoundingClientRect();
        const mouseY = e.clientY;
        
        this.pararAutoScroll();
        
        if (mouseY < rect.top + this.config.scrollZone) {
            this.scrollInterval = setInterval(() => {
                container.scrollTop -= this.config.scrollSpeed;
            }, 16);
        } else if (mouseY > rect.bottom - this.config.scrollZone) {
            this.scrollInterval = setInterval(() => {
                container.scrollTop += this.config.scrollSpeed;
            }, 16);
        }
    }

    pararAutoScroll() {
        if (this.scrollInterval) {
            clearInterval(this.scrollInterval);
            this.scrollInterval = null;
        }
    }

    // ========================================
    // PERSISTÊNCIA (SALVAR NO BANCO)
    // ========================================

    async salvarNovaPosicao(parentUl) {
        const contexto = this.determinarContexto(parentUl);
        // Filtra apenas LIs reais
        const items = Array.from(parentUl.children).filter(li => 
            li.tagName === 'LI' && 
            !li.classList.contains('drag-placeholder') &&
            li.querySelector(':scope > .node-wrapper')
        );
        
        const novaOrdem = [];
        
        items.forEach((li, index) => {
            const item = li.querySelector(':scope > .node-wrapper');
            const id = item.getAttribute('data-id');
            if (!id) return;
            
            const tipo = this.getNodeType(item);
            
            novaOrdem.push({
                tipo_no: tipo,
                id_referencia: this.extrairIdReferencia(id, tipo),
                ordem: (index + 1) * this.config.intervalo
            });
        });
        
        console.log('💾 Salvando ordem:', contexto, novaOrdem);
        
        try {
            // Rota dinâmica
            let url;
            if (typeof API_ROUTES !== 'undefined' && API_ROUTES.reordenarLote) {
                url = API_ROUTES.reordenarLote;
            } else {
                url = '/LuftControl/DreOrdenamento/ordenamento/reordenar-lote';
            }
            
            const r = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    contexto_pai: contexto,
                    nova_ordem: novaOrdem
                })
            });
            
            const responseData = await r.json();
            
            if (r.ok) {
                this.showToast('Ordem salva!');
            } else {
                console.error('❌ Erro ao salvar:', responseData);
                this.showToast('Erro ao salvar: ' + (responseData.error || responseData.msg), 'error');
            }
        } catch (e) {
            console.error('❌ Erro de conexão:', e);
            this.showToast('Erro de conexão ao salvar', 'error');
        }
    }

    extrairIdReferencia(nodeId, tipo) {
        const prefixos = {
            'tipo_cc': 'tipo_',
            'virtual': 'virt_',
            'cc': 'cc_',
            'subgrupo': 'sg_',
            'conta': 'conta_',
            'conta_detalhe': 'cd_'
        };
        const prefixo = prefixos[tipo] || '';
        return nodeId.replace(prefixo, '');
    }

    showToast(msg, type = 'success') {
        // Tenta usar o global do sistema primeiro
        if (typeof window.showToast === 'function') {
            window.showToast(msg);
            return;
        }
        
        let toast = document.getElementById('dre-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'dre-toast';
            document.body.appendChild(toast);
        }
        toast.textContent = msg;
        toast.className = `dre-toast show ${type}`;
        setTimeout(() => toast.classList.remove('show'), 2000);
    }

    // ========================================
    // ESTILOS CSS (Ajustados para o LuftCore)
    // ========================================

    injetarEstilos() {
        const styles = `
<style id="dre-ordenamento-styles">
body.dragging-active { cursor: grabbing !important; user-select: none !important; }
body.dragging-active * { cursor: grabbing !important; }
.drag-handle {
    display: flex; align-items: center; justify-content: center;
    width: 20px; height: 20px; margin-right: 6px;
    color: var(--luft-text-light); cursor: grab; opacity: 0;
    transition: all 0.2s ease; border-radius: var(--luft-radius-sm); flex-shrink: 0;
}
.node-wrapper:hover .drag-handle { opacity: 0.7; }
.drag-handle:hover { opacity: 1 !important; background: var(--luft-primary-100); color: var(--luft-primary-600); }
.drag-handle:active { cursor: grabbing; transform: scale(0.95); }

/* Os estilos do clone agora são definidos via JS para garantir compatibilidade */

.drag-placeholder { margin: 4px 0; list-style: none; }
.drag-placeholder .placeholder-inner {
    display: flex; align-items: center; gap: 10px; padding: 10px 15px;
    background: var(--luft-primary-50);
    border: 2px dashed var(--luft-primary-500); border-radius: var(--luft-radius-md); 
    color: var(--luft-primary-600);
    font-size: 0.85rem; font-weight: 600;
}
.node-wrapper.drop-highlight.drop-above { border-top: 2px solid var(--luft-primary-500); }
.node-wrapper.drop-highlight.drop-below { border-bottom: 2px solid var(--luft-primary-500); }
.node-wrapper.drop-highlight.drop-inside { background: var(--luft-primary-50); border: 2px solid var(--luft-primary-600); }
li.dragging-original { opacity: 0.1 !important; height: 0 !important; overflow: hidden !important; margin: 0 !important; }
</style>`;
        const old = document.getElementById('dre-ordenamento-styles');
        if (old) old.remove();
        document.head.insertAdjacentHTML('beforeend', styles);
    }
}

// INICIALIZAÇÃO 
document.addEventListener('DOMContentLoaded', () => {
    window.dreOrdenamento = new DreOrdenamentoManager();
    window.dreOrdenamento.init();
});