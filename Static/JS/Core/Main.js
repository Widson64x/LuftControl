// ============================================
// Luft Control - MAIN JAVASCRIPT
// Arquivo: Static/JS/Core/Main.js
// ============================================

// ============================================
// 1. INTERCEPTADOR GLOBAL DE FETCH
// Injeta automaticamente o cabeçalho X-Requested-With 
// em TODAS as requisições do sistema para passar no @require_ajax
// ============================================
const originalFetch = window.fetch;
window.fetch = async function(resource, config) {
    // Garante que o config e o config.headers existam
    config = config || {};
    config.headers = config.headers || {};
    
    // Injeta o cabeçalho dependendo de como os headers foram instanciados
    if (config.headers instanceof Headers) {
        if (!config.headers.has('X-Requested-With')) {
            config.headers.append('X-Requested-With', 'XMLHttpRequest');
        }
    } else {
        config.headers['X-Requested-With'] = 'XMLHttpRequest';
    }
    
    // Repassa para o fetch nativo do navegador
    return originalFetch(resource, config);
};


/**
 * Sistema Principal do Luft Control
 * Gerencia funcionalidades globais do sistema
 */
class LuftControl {
    constructor() {
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupAnimations();
        this.setupKeyboardShortcuts();
        console.log('✅ Luft Control inicializado');
    }

    /**
     * Configura event listeners globais
     */
    setupEventListeners() {
        // Fechar modals com ESC
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeAllModals();
            }
        });

        // Fechar modal ao clicar no overlay
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-overlay')) {
                this.closeAllModals();
            }
        });

        // Smooth scroll para links internos
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', (e) => {
                e.preventDefault();
                const target = document.querySelector(anchor.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });
    }

    /**
     * Configura animações ao scroll
     */
    setupAnimations() {
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('fade-in');
                    }
                });
            },
            {
                threshold: 0.1,
                rootMargin: '0px 0px -50px 0px'
            }
        );

        // Observar elementos que devem animar
        document.querySelectorAll('.card, .summary-card').forEach(el => {
            observer.observe(el);
        });
    }

    /**
     * Configura atalhos de teclado
     */
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + K - Busca rápida
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                this.focusSearch();
            }
        });
    }

    /**
     * Foca no campo de busca se existir
     */
    focusSearch() {
        const searchInput = document.querySelector('#searchTable, [type="search"]');
        if (searchInput) {
            searchInput.focus();
        }
    }

    /**
     * Fecha todos os modals abertos
     */
    closeAllModals() {
        document.querySelectorAll('.modal-overlay').forEach(modal => {
            modal.classList.remove('active');
        });
        document.body.style.overflow = '';
    }
}

/**
 * Sistema de Modal
 * Gerencia abertura, fechamento e estados do modal
 */
class ModalSystem {
    constructor(modalId) {
        this.modal = document.getElementById(modalId);
        if (!this.modal) {
            console.warn(`Modal ${modalId} não encontrado`);
            return;
        }
        this.modalTitle = this.modal.querySelector('.modal-title');
        this.modalBody = this.modal.querySelector('.modal-body');
        this.setupCloseButton();
    }

    setupCloseButton() {
        const closeBtn = this.modal.querySelector('.modal-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.close());
        }
    }

    open(title = '', content = '') {
        if (!this.modal) return;

        if (title && this.modalTitle) {
            this.modalTitle.innerHTML = title;
        }

        if (content && this.modalBody) {
            this.modalBody.innerHTML = content;
        }

        this.modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    close() {
        if (!this.modal) return;
        
        this.modal.classList.remove('active');
        document.body.style.overflow = '';
    }

    showLoading(message = 'Carregando...') {
        if (!this.modalBody) return;
        
        this.modalBody.innerHTML = `
            <div class="loading-container">
                <div class="loading-spinner"></div>
                <div class="loading-text">${message}</div>
            </div>
        `;
    }

    showError(message) {
        if (!this.modalBody) return;
        
        this.modalBody.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle"></i>
                <div>
                    <strong>Erro</strong><br>
                    ${message}
                </div>
            </div>
        `;
    }

    showEmpty(message = 'Nenhum dado encontrado') {
        if (!this.modalBody) return;
        
        this.modalBody.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-inbox"></i>
                <p>${message}</p>
            </div>
        `;
    }

    setContent(html) {
        if (!this.modalBody) return;
        this.modalBody.innerHTML = html;
    }

    setTitle(title) {
        if (!this.modalTitle) return;
        this.modalTitle.innerHTML = title;
    }
}

/**
 * Sistema de Notificações
 */
class NotificationSystem {
    static container = null;

    static init() {
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'notification-container';
            this.container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
                display: flex;
                flex-direction: column;
                gap: 10px;
            `;
            document.body.appendChild(this.container);
        }
    }

    static show(message, type = 'info', duration = 3000) {
        this.init();

        const notification = document.createElement('div');
        notification.className = `alert alert-${type} slide-in-down`;
        notification.style.cssText = `
            min-width: 300px;
            animation: slideInRight 0.3s ease;
        `;
        
        notification.innerHTML = `
            <i class="fas fa-${this.getIcon(type)}"></i>
            <span>${message}</span>
        `;

        this.container.appendChild(notification);

        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(100px)';
            setTimeout(() => notification.remove(), 300);
        }, duration);
    }

    static getIcon(type) {
        const icons = {
            success: 'check-circle',
            danger: 'exclamation-circle',
            warning: 'exclamation-triangle',
            info: 'info-circle'
        };
        return icons[type] || 'info-circle';
    }
}

/**
 * Utilitários de Formatação
 */
class FormatUtils {
    static formatCurrency(value) {
        return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value || 0);
    }
    static formatNumber(value) {
        return new Intl.NumberFormat('pt-BR').format(value || 0);
    }
    static formatDate(dateString) {
        if (!dateString) return '-';
        return new Intl.DateTimeFormat('pt-BR').format(new Date(dateString));
    }
    static formatDateTime(dateString) {
        if (!dateString) return '-';
        return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(dateString));
    }
    static formatPercent(value) {
        return new Intl.NumberFormat('pt-BR', { style: 'percent', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value || 0);
    }
}

/**
 * Utilitários de Tabela
 */
class TableUtils {
    static addSearch(tableId, searchInputId) {
        const table = document.getElementById(tableId);
        const searchInput = document.getElementById(searchInputId);
        if (!table || !searchInput) return;
        searchInput.addEventListener('input', (e) => {
            this.filterTable(table, e.target.value);
        });
    }

    static filterTable(table, searchTerm) {
        const rows = table.querySelectorAll('tbody tr');
        const term = searchTerm.toLowerCase();
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(term) ? '' : 'none';
        });
    }

    static sortTable(table, columnIndex, ascending = true) {
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        rows.sort((a, b) => {
            const aValue = a.cells[columnIndex].textContent;
            const bValue = b.cells[columnIndex].textContent;
            return ascending 
                ? aValue.localeCompare(bValue, 'pt-BR', { numeric: true })
                : bValue.localeCompare(aValue, 'pt-BR', { numeric: true });
        });
        rows.forEach(row => tbody.appendChild(row));
    }
}

/**
 * Utilitários de API (Agora mais limpos graças ao Interceptor)
 */
class APIUtils {
    static async get(url) {
        const res = await fetch(url, {
            headers: { 'Accept': 'application/json' }
        });
        
        if (!res.ok && res.status !== 403 && res.status !== 400) {
            throw new Error(`HTTP Error: ${res.status}`);
        }
        
        const json = await res.json();
        
        if (json.status === 'error' || res.status === 403) {
            throw new Error(json.message || json.error || `Acesso Negado ou Erro (${res.status})`);
        }
        
        return json.status === 'success' ? (json.data !== undefined ? json.data : json) : json;
    }
    
    static async post(url, data) {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        if (!res.ok && res.status !== 403 && res.status !== 400) {
            throw new Error(`HTTP Error: ${res.status}`);
        }
        
        const json = await res.json();
        
        if (json.status === 'error' || res.status === 403) {
            throw new Error(json.message || json.error || `Acesso Negado ou Erro (${res.status})`);
        }
        
        return json.status === 'success' ? (json.data !== undefined ? json.data : json) : json;
    }
}

// ============================================
// INICIALIZAÇÃO
// ============================================

let luftControl;

document.addEventListener('DOMContentLoaded', () => {
    luftControl = new LuftControl();
});

// Exportar para uso global
window.LuftControl = LuftControl;
window.ModalSystem = ModalSystem;
window.NotificationSystem = NotificationSystem;
window.FormatUtils = FormatUtils;
window.TableUtils = TableUtils;
window.APIUtils = APIUtils;