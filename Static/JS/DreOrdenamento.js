// Static/JS/DreOrdenamento.js
/**
 * Sistema de Ordenamento Drag-and-Drop Visual para Árvore DRE
 * 
 * Características:
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
            const r = await fetch('/Ordenamento/GetFilhosOrdenados', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ contexto_pai: 'root' })
            });
            
            if (r.ok) {
                const data = await r.json();
                this.ordenamentoAtivo = data.length > 0;
                
                if (this.ordenamentoAtivo) {
                    setTimeout(() => this.habilitarDragDrop(), 500);
                    console.log('✅ Ordenamento ativo - Drag & Drop habilitado');
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
     */
    habilitarDragDrop() {
        // Adiciona handles de arraste
        const wrappers = document.querySelectorAll('.node-wrapper');
        
        wrappers.forEach(wrapper => {
            const li = wrapper.closest('li');
            if (!li) return;
            
            // Verifica se pode ser arrastado
            const nodeType = this.getNodeType(wrapper);
            if (!this.podeSerArrastado(nodeType)) return;
            
            // Adiciona handle se não existir
            if (!wrapper.querySelector('.drag-handle')) {
                const handle = document.createElement('span');
                handle.className = 'drag-handle';
                handle.innerHTML = '<i class="fas fa-grip-vertical"></i>';
                wrapper.insertBefore(handle, wrapper.firstChild);
            }
            
            // Evento de mousedown no handle
            const handle = wrapper.querySelector('.drag-handle');
            handle.removeEventListener('mousedown', this.onMouseDown); // Remove duplicados
            handle.addEventListener('mousedown', (e) => this.onMouseDown(e, li, wrapper));
        });
        
        // Eventos globais (apenas uma vez)
        document.removeEventListener('mousemove', this.onMouseMove);
        document.removeEventListener('mouseup', this.onMouseUp);
        document.addEventListener('mousemove', this.onMouseMove);
        document.addEventListener('mouseup', this.onMouseUp);
    }

    /**
     * Reabilita após recarregar árvore
     */
    reabilitar() {
        if (this.ordenamentoAtivo) {
            setTimeout(() => this.habilitarDragDrop(), 300);
        }
    }

    // ========================================
    // EVENTOS DE MOUSE
    // ========================================

    onMouseDown(e, li, wrapper) {
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
        
        // Dimensões originais
        const rect = li.getBoundingClientRect();
        this.dragOffset = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };
        
        // Cria clone visual
        this.criarClone(li, e);
        
        // Cria placeholder
        this.criarPlaceholder(li);
        
        // Esconde original
        li.style.opacity = '0';
        li.style.height = '0';
        li.style.overflow = 'hidden';
        li.style.margin = '0';
        li.style.padding = '0';
        
        document.body.classList.add('dragging-active');
        
        console.log('🎯 Drag iniciado:', this.draggedNodeData.text);
    }

    onMouseMove(e) {
        if (!this.isDragging || !this.draggedClone) return;
        
        // Move o clone
        this.draggedClone.style.left = `${e.clientX - this.dragOffset.x}px`;
        this.draggedClone.style.top = `${e.clientY - this.dragOffset.y}px`;
        
        // Auto-scroll
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
        
        // Move o elemento real para onde o placeholder está
        if (this.placeholder && this.placeholder.parentElement && this.draggedLi) {
            const newParent = this.placeholder.parentElement;
            
            // Restaura visual do item
            this.draggedLi.style.opacity = '';
            this.draggedLi.style.height = '';
            this.draggedLi.style.overflow = '';
            this.draggedLi.style.margin = '';
            this.draggedLi.style.padding = '';
            
            // Insere na nova posição
            newParent.insertBefore(this.draggedLi, this.placeholder);
            
            // Remove placeholder
            this.placeholder.remove();
            
            // Animação de destaque
            const wrapper = this.draggedLi.querySelector('.node-wrapper');
            if (wrapper) {
                wrapper.classList.add('just-dropped');
                setTimeout(() => wrapper.classList.remove('just-dropped'), 500);
            }
            
            // Salva no backend
            this.salvarNovaPosicao(newParent);
        } else {
            // Restaura posição original
            if (this.draggedLi) {
                this.draggedLi.style.opacity = '';
                this.draggedLi.style.height = '';
                this.draggedLi.style.overflow = '';
                this.draggedLi.style.margin = '';
                this.draggedLi.style.padding = '';
            }
            
            if (this.placeholder) {
                this.placeholder.remove();
            }
        }
        
        document.body.classList.remove('dragging-active');
        
        this.draggedLi = null;
        this.placeholder = null;
        this.originalParent = null;
        this.draggedNodeData = null;
        
        console.log('✅ Drag finalizado');
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
        
        // Estilos do clone
        Object.assign(this.draggedClone.style, {
            position: 'fixed',
            left: `${e.clientX - this.dragOffset.x}px`,
            top: `${e.clientY - this.dragOffset.y}px`,
            width: `${rect.width}px`,
            zIndex: '10000',
            pointerEvents: 'none',
            opacity: '0.9',
            transform: 'rotate(2deg) scale(1.02)',
            boxShadow: '0 8px 25px rgba(0,0,0,0.3), 0 0 0 2px #3498db',
            background: '#1e2736',
            borderRadius: '8px',
            padding: '8px 12px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            color: '#fff',
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
        
        // Insere após o item original
        li.parentElement.insertBefore(this.placeholder, li.nextSibling);
    }

    // ========================================
    // LÓGICA DE POSICIONAMENTO
    // ========================================

    atualizarPosicaoDrop(e) {
        const mouseY = e.clientY;
        const mouseX = e.clientX;
        
        // Remove highlight anterior
        document.querySelectorAll('.drop-highlight').forEach(el => {
            el.classList.remove('drop-highlight', 'drop-above', 'drop-below', 'drop-inside');
        });
        
        // Encontra todos os LIs visíveis que podem receber
        const allLis = document.querySelectorAll('#treeRoot li');
        let closestLi = null;
        let closestDistance = Infinity;
        let dropPosition = 'below'; // 'above', 'below', 'inside'
        
        allLis.forEach(li => {
            if (li === this.draggedLi || li === this.placeholder) return;
            if (li.closest('.drag-placeholder')) return;
            
            const wrapper = li.querySelector(':scope > .node-wrapper');
            if (!wrapper) return;
            
            const rect = wrapper.getBoundingClientRect();
            
            // Verifica se o mouse está na área horizontal do item
            if (mouseX < rect.left - 50 || mouseX > rect.right + 50) return;
            
            // Calcula distância vertical
            const centerY = rect.top + rect.height / 2;
            const distance = Math.abs(mouseY - centerY);
            
            if (distance < closestDistance && distance < 80) {
                closestDistance = distance;
                closestLi = li;
                
                // Determina posição (acima, abaixo ou dentro)
                const relativeY = (mouseY - rect.top) / rect.height;
                
                if (relativeY < 0.25) {
                    dropPosition = 'above';
                } else if (relativeY > 0.75) {
                    dropPosition = 'below';
                } else {
                    // Só permite "dentro" se o alvo puder receber filhos
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
            
            // Verifica se pode dropar neste contexto
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
            // Encontra ou cria UL filho
            let childUl = targetLi.querySelector(':scope > ul');
            if (!childUl) {
                childUl = document.createElement('ul');
                childUl.className = 'tree expanded';
                targetLi.appendChild(childUl);
            }
            childUl.classList.add('expanded');
            childUl.insertBefore(this.placeholder, childUl.firstChild);
        }
        
        // Atualiza visual do placeholder
        this.placeholder.className = `drag-placeholder position-${position}`;
    }

    // ========================================
    // VALIDAÇÃO DE HIERARQUIA
    // ========================================

    getNodeType(element) {
        const id = element.getAttribute('data-id') || '';
        
        if (id.startsWith('tipo_')) return 'tipo_cc';
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
        // Se está dropando "dentro", verifica se o alvo pode receber
        if (posicao === 'inside') {
            return this.podeReceberFilhos(tipoAlvo, tipoOrigem);
        }
        
        // Se está dropando acima/abaixo, verifica se é o mesmo nível
        // (mesmo tipo de pai)
        const regrasContexto = {
            'tipo_cc': ['root'],
            'virtual': ['root'],
            'cc': ['tipo_cc'],
            'subgrupo': ['cc', 'virtual', 'subgrupo'],
            'conta': ['subgrupo'],
            'conta_detalhe': ['subgrupo', 'virtual']
        };
        
        const permitidos = regrasContexto[tipoOrigem] || [];
        
        // Verifica pelo contexto
        if (contexto === 'root') return permitidos.includes('root');
        if (contexto.startsWith('tipo_')) return permitidos.includes('tipo_cc');
        if (contexto.startsWith('cc_')) return permitidos.includes('cc');
        if (contexto.startsWith('virt_')) return permitidos.includes('virtual');
        if (contexto.startsWith('sg_')) return permitidos.includes('subgrupo');
        
        return false;
    }

    determinarContexto(ul) {
        // Se é o root
        if (ul.id === 'treeRoot') return 'root';
        
        // Pega o LI pai
        const liPai = ul.parentElement;
        if (!liPai || liPai.tagName !== 'LI') return 'root';
        
        const wrapperPai = liPai.querySelector(':scope > .node-wrapper');
        if (!wrapperPai) return 'root';
        
        return wrapperPai.getAttribute('data-id') || 'root';
    }

    // ========================================
    // AUTO-SCROLL
    // ========================================

    handleAutoScroll(e) {
        const container = document.querySelector('.tree-panel') || document.querySelector('#treeRoot')?.parentElement;
        if (!container) return;
        
        const rect = container.getBoundingClientRect();
        const mouseY = e.clientY;
        
        this.pararAutoScroll();
        
        if (mouseY < rect.top + this.config.scrollZone) {
            // Scroll para cima
            this.scrollInterval = setInterval(() => {
                container.scrollTop -= this.config.scrollSpeed;
            }, 16);
        } else if (mouseY > rect.bottom - this.config.scrollZone) {
            // Scroll para baixo
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
    // PERSISTÊNCIA
    // ========================================

    async salvarNovaPosicao(parentUl) {
        const contexto = this.determinarContexto(parentUl);
        const items = parentUl.querySelectorAll(':scope > li:not(.drag-placeholder) > .node-wrapper');
        
        const novaOrdem = [];
        
        items.forEach((item, index) => {
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
            const r = await fetch('/Ordenamento/ReordenarLote', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    contexto_pai: contexto,
                    nova_ordem: novaOrdem
                })
            });
            
            if (r.ok) {
                this.showToast('Ordem salva!');
            } else {
                console.error('Erro ao salvar');
                this.showToast('Erro ao salvar ordem', 'error');
            }
        } catch (e) {
            console.error('Erro:', e);
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
        // Usa toast global se existir
        if (typeof showToast === 'function') {
            showToast(msg);
            return;
        }
        
        // Toast próprio
        let toast = document.getElementById('dre-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'dre-toast';
            document.body.appendChild(toast);
        }
        
        toast.textContent = msg;
        toast.className = `dre-toast show ${type}`;
        
        setTimeout(() => {
            toast.classList.remove('show');
        }, 2000);
    }

    // ========================================
    // ESTILOS CSS
    // ========================================

    injetarEstilos() {
        const styles = `
<style id="dre-ordenamento-styles">
/* ========================================
   DRAG & DROP VISUAL STYLES
   ======================================== */

/* Estado global durante drag */
body.dragging-active {
    cursor: grabbing !important;
    user-select: none !important;
}

body.dragging-active * {
    cursor: grabbing !important;
}

/* Handle de arraste */
.drag-handle {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    margin-right: 6px;
    color: #5a6a7a;
    cursor: grab;
    opacity: 0;
    transition: all 0.2s ease;
    border-radius: 4px;
    flex-shrink: 0;
}

.node-wrapper:hover .drag-handle {
    opacity: 0.7;
}

.drag-handle:hover {
    opacity: 1 !important;
    background: rgba(52, 152, 219, 0.2);
    color: #3498db;
}

.drag-handle:active {
    cursor: grabbing;
    transform: scale(0.95);
}

/* Clone que segue o mouse */
.drag-clone {
    font-family: inherit;
    animation: cloneAppear 0.15s ease-out;
}

@keyframes cloneAppear {
    from {
        opacity: 0;
        transform: rotate(0) scale(0.8);
    }
    to {
        opacity: 0.9;
        transform: rotate(2deg) scale(1.02);
    }
}

/* Placeholder - onde o item vai cair */
.drag-placeholder {
    list-style: none;
    margin: 4px 0;
    transition: all 0.2s ease;
}

.drag-placeholder .placeholder-inner {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 15px;
    background: linear-gradient(135deg, rgba(46, 204, 113, 0.15), rgba(52, 152, 219, 0.15));
    border: 2px dashed #2ecc71;
    border-radius: 8px;
    color: #2ecc71;
    font-size: 0.85rem;
    font-weight: 500;
    animation: placeholderPulse 1s ease-in-out infinite;
}

@keyframes placeholderPulse {
    0%, 100% {
        border-color: #2ecc71;
        background: linear-gradient(135deg, rgba(46, 204, 113, 0.15), rgba(52, 152, 219, 0.15));
    }
    50% {
        border-color: #3498db;
        background: linear-gradient(135deg, rgba(52, 152, 219, 0.2), rgba(46, 204, 113, 0.2));
    }
}

.drag-placeholder.position-inside .placeholder-inner {
    margin-left: 20px;
    background: linear-gradient(135deg, rgba(155, 89, 182, 0.15), rgba(52, 152, 219, 0.15));
    border-color: #9b59b6;
    color: #9b59b6;
}

/* Highlight no elemento alvo */
.node-wrapper.drop-highlight {
    position: relative;
    transition: all 0.15s ease;
}

.node-wrapper.drop-highlight.drop-above::before {
    content: '';
    position: absolute;
    top: -3px;
    left: 0;
    right: 0;
    height: 4px;
    background: linear-gradient(90deg, #2ecc71, #3498db);
    border-radius: 2px;
    animation: lineGlow 0.8s ease-in-out infinite;
}

.node-wrapper.drop-highlight.drop-below::after {
    content: '';
    position: absolute;
    bottom: -3px;
    left: 0;
    right: 0;
    height: 4px;
    background: linear-gradient(90deg, #3498db, #2ecc71);
    border-radius: 2px;
    animation: lineGlow 0.8s ease-in-out infinite;
}

.node-wrapper.drop-highlight.drop-inside {
    background: rgba(155, 89, 182, 0.2) !important;
    border: 2px solid #9b59b6 !important;
    box-shadow: 0 0 15px rgba(155, 89, 182, 0.3);
}

@keyframes lineGlow {
    0%, 100% {
        opacity: 1;
        box-shadow: 0 0 8px rgba(46, 204, 113, 0.6);
    }
    50% {
        opacity: 0.7;
        box-shadow: 0 0 15px rgba(52, 152, 219, 0.8);
    }
}

/* Animação quando o item é solto */
.node-wrapper.just-dropped {
    animation: dropLand 0.4s ease-out;
}

@keyframes dropLand {
    0% {
        transform: scale(1.05);
        background: rgba(46, 204, 113, 0.3);
        box-shadow: 0 0 20px rgba(46, 204, 113, 0.5);
    }
    50% {
        transform: scale(0.98);
    }
    100% {
        transform: scale(1);
        background: transparent;
        box-shadow: none;
    }
}

/* Item original escondido durante drag */
li.dragging-original {
    opacity: 0 !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
}

/* Toast de feedback */
.dre-toast {
    position: fixed;
    bottom: 30px;
    left: 50%;
    transform: translateX(-50%) translateY(100px);
    background: #2ecc71;
    color: white;
    padding: 12px 24px;
    border-radius: 30px;
    font-weight: 600;
    box-shadow: 0 5px 20px rgba(46, 204, 113, 0.4);
    z-index: 10001;
    transition: transform 0.3s ease;
    opacity: 0;
}

.dre-toast.show {
    transform: translateX(-50%) translateY(0);
    opacity: 1;
}

.dre-toast.error {
    background: #e74c3c;
    box-shadow: 0 5px 20px rgba(231, 76, 60, 0.4);
}

/* Cursor grab para itens arrastáveis */
.node-wrapper:has(.drag-handle) {
    cursor: default;
}

/* Melhorias visuais na árvore durante drag */
body.dragging-active .node-wrapper {
    transition: background 0.15s ease, border 0.15s ease, box-shadow 0.15s ease;
}

body.dragging-active .node-wrapper:not(.drop-highlight) {
    opacity: 0.7;
}

/* Expande automaticamente subgrupos durante hover no drag */
body.dragging-active li:hover > ul {
    display: block !important;
}
</style>
`;
        
        // Remove estilos antigos se existir
        const oldStyles = document.getElementById('dre-ordenamento-styles');
        if (oldStyles) oldStyles.remove();
        
        document.head.insertAdjacentHTML('beforeend', styles);
    }
}

// ========================================
// INSTÂNCIA GLOBAL
// ========================================
let dreOrdenamento = null;

document.addEventListener('DOMContentLoaded', () => {
    dreOrdenamento = new DreOrdenamentoManager();
    dreOrdenamento.init();
});

// Exporta para uso global
window.dreOrdenamento = dreOrdenamento;
window.DreOrdenamentoManager = DreOrdenamentoManager;

// Hook para quando a árvore for recarregada
const originalLoadTree = window.loadTree;
if (typeof originalLoadTree === 'function') {
    window.loadTree = async function() {
        await originalLoadTree.apply(this, arguments);
        if (dreOrdenamento) {
            dreOrdenamento.reabilitar();
        }
    };
}