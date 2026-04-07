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

        showError(errorObj) {
            // Extrai a mensagem de forma segura
            const msg = typeof errorObj === 'string' ? errorObj : (errorObj.message || String(errorObj));
            
            // Detecta automaticamente se é um erro de Permissão/Autenticação
            const isAuthError = msg.includes('403') || msg.toLowerCase().includes('acesso negado') || msg.toLowerCase().includes('permissão');
            
            // Limpa a mensagem técnica feia para exibição ao usuário
            let cleanMsg = msg.replace('Error: HTTP Error: 403', '').replace('403 FORBIDDEN', '').replace('Error: ', '').trim();
            
            if (isAuthError && cleanMsg.length < 5) {
                cleanMsg = "Seu grupo de usuário não possui as permissões necessárias para visualizar este módulo.";
            }

            if (isAuthError) {
                // Tela de Acesso Restrito embutida no Modal (Padrão LuftCore)
                this.setContent(`
                    <div class="luft-modal-content-wrapper d-flex flex-column align-items-center justify-content-center animate-slide-up" style="height: 100%; min-height: 350px; background: var(--luft-bg-app);">
                        <div class="luft-error-icon-box text-warning bg-warning-light mb-4 shadow-sm" style="width: 90px; height: 90px; border-radius: 50%; display: flex; align-items: center; justify-content: center;">
                            <i class="fas fa-lock" style="font-size: 3.5rem;"></i>
                        </div>
                        <h3 class="font-black text-2xl text-main m-0">Acesso Restrito</h3>
                        
                        <p class="text-muted mt-3 max-w-md text-center text-sm font-medium">
                            Você não possui permissão para acessar este relatório.
                            <br>
                            <span class="text-xs opacity-75 font-normal mt-1 d-block">${cleanMsg}</span>
                        </p>
                        <br>
                        <button class="btn btn-outline mt-5" onclick="window.fecharModal()">
                            <i class="fas fa-times"></i> Fechar Relatório
                        </button>
                    </div>
                `);
            } else {
                // Tela de Erro Genérico/500
                this.setContent(`
                    <div class="luft-modal-content-wrapper d-flex flex-column align-items-center justify-content-center animate-slide-up" style="height: 100%; min-height: 350px; background: var(--luft-bg-app);">
                        <div class="luft-error-icon-box text-danger bg-danger-light mb-4 shadow-sm" style="width: 80px; height: 80px; border-radius: 50%; display: flex; align-items: center; justify-content: center;">
                            <i class="fas fa-exclamation-triangle" style="font-size: 3rem;"></i>
                        </div>
                        <h3 class="font-black text-xl text-main m-0">Falha no Processamento</h3>
                        <div class="bg-panel border rounded-lg p-3 mt-4 text-xs text-danger text-center max-w-lg w-full" style="word-break: break-word;">
                            ${cleanMsg || "O servidor não conseguiu processar a requisição."}
                        </div>
                        <button class="btn btn-outline mt-4" onclick="window.fecharModal()">
                            <i class="fas fa-times"></i> Fechar
                        </button>
                    </div>
                `);
            }
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
            this.relatorioBudget = null;
            
            // 1. ADICIONA AQUI A VARIÁVEL DO NOVO RELATÓRIO
            this.dreOperacao = null; 
            
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
            if (typeof DreConsolidado !== 'undefined') {
                this.dreConsolidado = new DreConsolidado(this.modal);
            }
            
            if (typeof DreOperacao !== 'undefined') {
                this.dreOperacao = new DreOperacao(this.modal);
            }

            if (typeof RelatorioBudget !== 'undefined') {
                this.relatorioBudget = new RelatorioBudget(this.modal);
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

        loadDreOperacaoReport() {
            if (this.dreOperacao) this.dreOperacao.loadReport();
        }

        loadBudgetReport(urlAlvo) {
            if (urlAlvo && typeof urlAlvo === 'string') {
                window.location.href = urlAlvo;
            } else if (this.relatorioBudget) {
                this.relatorioBudget.carregarRelatorio();
            } else {
                console.warn("Nenhuma URL de destino ou classe RelatorioBudget fornecida.");
            }
        }

        loadBudgetAnaliticoReport(urlAlvo) {
            if (urlAlvo && typeof urlAlvo === 'string') {
                window.location.href = urlAlvo;
            } else {
                console.warn("Nenhuma URL de destino fornecida para o Budget Analítico.");
            }
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