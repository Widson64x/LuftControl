// ============================================================================
// Luft Control - ORQUESTRADOR DE RELATÓRIOS
// Arquivo: Static/JS/Reports/Relatorios.js
// ============================================================================

if (typeof window.relatorioSystemInitialized === 'undefined') {
    window.relatorioSystemInitialized = true;

    class RelatorioSystem {
        constructor() {
            this.modal = null;
            this.razao = null;
            this.dre = null;
            
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
            if (modalElement && typeof ModalSystem !== 'undefined') {
                this.modal = new ModalSystem('modalRelatorio');
            }

            // Instancia os submódulos e passa o modal global para eles
            this.razao = new RelatorioRazao(this.modal);
            this.dre = new RelatorioDRE(this.modal);

            if (typeof RelatorioDreConsolidado !== 'undefined') {
                this.dreConsolidado = new RelatorioDreConsolidado(this.modal);
            }
        }

        // ====================================================================
        // MÉTODOS PROXY (Garante compatibilidade caso existam chamadas de fora)
        // ====================================================================

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
    
    // Utilitário para Fechar o Modal globalmente
    window.fecharModal = function() { 
        if (window.relatorioSystem && window.relatorioSystem.modal) {
            window.relatorioSystem.modal.close(); 
        }
    };
}