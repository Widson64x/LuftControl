// ============================================================================
// Luft Control - ORQUESTRADOR DE RELATÓRIOS
// Arquivo: Static/JS/Reports/Relatorios.js
// Design System: LuftCore
// ============================================================================

if (typeof window.relatorioSystemInitialized === 'undefined') {
    window.relatorioSystemInitialized = true;

    // ========================================================================
    // 1. ADAPTADOR DO MODAL LUFTCORE
    // Substitui a antiga "ModalSystem" para interagir corretamente com o novo framework
    // ========================================================================
    class LuftModalWrapper {
        constructor(modalId) {
            this.id = modalId;
            this.modalEl = document.getElementById(modalId);
            this.titleEl = this.modalEl ? this.modalEl.querySelector('.luft-modal-title') : null;
            this.bodyEl = this.modalEl ? this.modalEl.querySelector('.luft-modal-body') : null;
        }

        open(titleHtml, subtitleHtml = '') {
            // Atualiza o título do modal no novo padrão
            if (this.titleEl && titleHtml) {
                this.titleEl.innerHTML = titleHtml + (subtitleHtml ? ` <span class="text-sm text-muted ms-2">${subtitleHtml}</span>` : '');
            }
            
            // Chama a função nativa do framework que você mandou (base.js)
            if (typeof LuftCore !== 'undefined') {
                LuftCore.abrirModal(this.id);
            } else {
                console.error("Framework LuftCore não encontrado na página!");
            }
        }

        close() {
            if (typeof LuftCore !== 'undefined') {
                LuftCore.fecharModal(this.id);
            }
        }

        setContent(html) {
            if (this.bodyEl) {
                this.bodyEl.innerHTML = html;
            }
        }

        showLoading(msg = 'Aguardando comando do servidor...') {
            this.setContent(`
                <div class="luft-modal-content-wrapper" style="height: 100%; display: flex; flex-direction: column;">
                    <div class="luft-hub-loading d-flex flex-column align-items-center justify-content-center h-100" style="min-height: 400px; background: var(--luft-bg-app);">
                        <div class="luft-spinner" style="width: 40px; height: 40px; border: 3px solid var(--luft-border); border-top-color: var(--luft-primary-500); border-radius: 50%; animation: spin 1s linear infinite;"></div>
                        <div class="luft-loading-text mt-4 text-muted font-medium">${msg}</div>
                    </div>
                </div>
            `);
        }

        showError(msg) {
            this.setContent(`
                <div class="luft-modal-content-wrapper p-5" style="height: 100%; background: var(--luft-bg-app);">
                    <div style="background: var(--luft-danger-50); border: 1px solid var(--luft-danger-200); color: var(--luft-danger-700); padding: 20px; border-radius: var(--luft-radius-lg);">
                        <i class="fas fa-exclamation-triangle me-2"></i> ${msg}
                    </div>
                </div>
            `);
        }
    }

    // ========================================================================
    // 2. ORQUESTRADOR DO SISTEMA
    // ========================================================================
    class RelatorioSystem {
        constructor() {
            this.modal = null;
            this.razao = null;
            this.dre = null;
            this.dreConsolidado = null;
            
            this.init();
        }

        init() {
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => this.setupSystem());
            } else {
                this.setupSystem();
            }
        }

        setupSystem() {
            const modalElement = document.getElementById('modalRelatorio');
            
            // Aqui é o grande truque: Usamos o novo adaptador no lugar do ModalSystem antigo
            if (modalElement) {
                this.modal = new LuftModalWrapper('modalRelatorio');
            } else {
                console.warn("Elemento HTML 'modalRelatorio' não foi encontrado na tela.");
            }

            // Instancia os submódulos passando o modal formatado para eles
            if (typeof RelatorioRazao !== 'undefined') {
                this.razao = new RelatorioRazao(this.modal);
            }
            if (typeof RelatorioDRE !== 'undefined') {
                this.dre = new RelatorioDRE(this.modal);
            }
            if (typeof RelatorioDreConsolidado !== 'undefined') {
                this.dreConsolidado = new RelatorioDreConsolidado(this.modal);
            }
        }

        // Métodos de chamada a partir do HTML
        loadRazaoReport(page = 1) {
            if (this.razao) this.razao.loadReport(page);
        }

        toggleRazaoView(isChecked) {
            if (this.razao) this.razao.toggleView(isChecked);
        }

        loadRentabilidadeReport(origem = null) {
            if (this.dre) this.dre.loadReport(origem);
        }

        loadDreConsolidadoReport() {
            if (this.dreConsolidado) this.dreConsolidado.loadReport();
        }
    }

    // Instanciação Global
    window.relatorioSystem = new RelatorioSystem();
    
    // Utilitário global para o botão de "X" fechar o modal
    window.fecharModal = function() { 
        if (window.relatorioSystem && window.relatorioSystem.modal) {
            window.relatorioSystem.modal.close(); 
        }
    };
}