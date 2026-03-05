// ============================================================================
// Luft Control - MÓDULO: RAZÃO CONTÁBIL
// Arquivo: Static/JS/Reports/RelatorioRazao.js
// Design System: LuftCore
// ============================================================================

class RelatorioRazao {
    constructor(modalSystem) {
        this.modal = modalSystem;
        this.data = null;
        this.summary = null; 
        this.page = 1;
        this.totalPages = 1;
        this.search = '';
        this.searchTimer = null;
        this.viewType = 'original'; 
        this.table = null;
    }

    async loadReport(page = 1) {
        // Usa o wrapper novo que criamos no orquestrador
        if (!this.modal) this.modal = new LuftModalWrapper('modalRelatorio');         
        this.page = page;
        
        const titleSuffix = this.viewType === 'adjusted' ? 'Visão Ajustada' : 'Original';
        const modalTitle = `<i class="fas fa-database text-primary"></i> Relatório de Razão Contábil`;
        const modalSubtitle = this.search ? `${titleSuffix} | Busca: "${this.search}"` : titleSuffix;

        if (page === 1 && !document.querySelector('#razaoTableContainer')) {
            this.modal.open(modalTitle, modalSubtitle);
            this.modal.showLoading('Carregando lançamentos contábeis...');
        }

        try {
            const urlData = (typeof API_ROUTES !== 'undefined' && API_ROUTES.getRazaoData) ? API_ROUTES.getRazaoData : '/Reports/RelatorioRazao/Dados'; 
            const urlSummary = (typeof API_ROUTES !== 'undefined' && API_ROUTES.getRazaoResumo) ? API_ROUTES.getRazaoResumo : '/Reports/RelatorioRazao/Resumo';

            const term = encodeURIComponent(this.search);
            const viewType = this.viewType;
            
            const [respData, respSummary] = await Promise.all([
                APIUtils.get(`${urlData}?page=${page}&search=${term}&view_type=${viewType}`),
                APIUtils.get(`${urlSummary}?view_type=${viewType}`)
            ]);

            this.data = respData.dados || [];
            this.totalPages = respData.total_paginas || 1;
            this.summary = respSummary;

            this.renderView(respData, respSummary);
        } catch (error) {
            console.error(error);
            // Repassa o objeto de erro inteiro para o Modal analisar
            this.modal.showError(error);
        }
    }

    toggleView(isChecked) {
        this.viewType = isChecked ? 'adjusted' : 'original';
        this.loadReport(1);
    }

    renderView(metaData, summaryData) {
        // Novo card de resumo LuftCore
        const summaryHtml = `
            <div class="luft-summary-grid">
                <div class="luft-summary-card">
                    <div class="luft-summary-label">Total de Registros</div>
                    <div class="luft-summary-value text-primary">${FormatUtils.formatNumber(summaryData.total_registros)}</div>
                </div>
            </div>`;

        // Toolbar premium (aproveitando classes do DRE para consistência)
        const controlsHtml = `
            <div class="luft-dre-toolbar mb-4 rounded-lg" style="border-top: 1px solid var(--luft-border-dark); margin-top: 0;">
                <div class="d-flex align-items-center gap-4 flex-wrap" style="flex: 1;">
                    
                    <div class="luft-hub-search" style="max-width: 350px;">
                        <i class="fas fa-search luft-hub-search-icon"></i>
                        <input type="text" id="razaoSearchInput" class="luft-hub-search-input" 
                            style="padding-top: 8px; padding-bottom: 8px;"
                            placeholder="Busca Global (Server-side)..." value="${this.search}">
                    </div>
                    
                    <div class="luft-separator-vertical"></div>

                    <label class="luft-switch-container">
                        <input type="checkbox" class="luft-switch-input" id="chkViewTypeRazao" 
                            ${this.viewType === 'adjusted' ? 'checked' : ''}
                            onchange="relatorioSystem.razao.toggleView(this.checked)">
                        <div class="luft-switch-track"><div class="luft-switch-thumb"></div></div>
                        <span class="luft-switch-label">Modo Ajustado <small class="text-muted font-normal">(Inclusões/Edições)</small></span>
                    </label>

                </div>

                <div class="d-flex align-items-center gap-3">
                    <button class="luft-dre-btn" onclick="relatorioSystem.razao.downloadFull()" title="Exportar para Excel">
                        <i id="iconDownload" class="fas fa-file-excel text-success" style="margin-right: 8px;"></i> Exportar Base
                    </button>
                    
                    <div class="luft-separator-vertical"></div>
                    
                    <span class="text-sm text-muted" style="font-weight: 600;">Página ${this.page} de ${this.totalPages}</span>
                    
                    <div class="d-flex gap-1">
                        <button class="luft-dre-btn" style="padding: 8px 12px;" onclick="relatorioSystem.razao.loadReport(${this.page - 1})" ${this.page <= 1 ? 'disabled' : ''}><i class="fas fa-chevron-left m-0"></i></button>
                        <button class="luft-dre-btn" style="padding: 8px 12px;" onclick="relatorioSystem.razao.loadReport(${this.page + 1})" ${this.page >= this.totalPages ? 'disabled' : ''}><i class="fas fa-chevron-right m-0"></i></button>
                    </div>
                </div>
            </div>
            
            <div id="razaoTabulator" style="flex: 1; min-height: 400px; width: 100%;"></div>
            <div class="text-end mt-2"><small class="text-muted text-xs font-medium"><i class="fas fa-info-circle me-1"></i> Filtros aplicados nas colunas abaixo afetam apenas a visualização da página atual.</small></div>
        `;

        this.modal.setContent(`<div id="razaoTableContainer" style="padding: 1.5rem; height: 100%; display: flex; flex-direction: column;">${summaryHtml}${controlsHtml}</div>`);

        const input = document.getElementById('razaoSearchInput');
        if (input) {
            input.focus();
            const val = input.value;
            input.value = '';
            input.value = val;
            
            input.addEventListener('input', (e) => {
                clearTimeout(this.searchTimer);
                this.searchTimer = setTimeout(() => {
                    this.search = e.target.value;
                    this.loadReport(1);
                }, 600);
            });
        }

        this.initTabulator();
    }

    initTabulator() {
        const moneyFormatter = (cell) => {
            const val = cell.getValue();
            // Cores do framework: text-danger, text-success ou text-muted
            const color = val < 0 ? "color: var(--luft-danger-600)" : (val > 0 ? "color: var(--luft-success-600)" : "color: var(--luft-text-muted)");
            return `<span style="${color}; font-family: monospace; font-weight: 600; font-size: 13px;">${FormatUtils.formatCurrency(val)}</span>`;
        };

        const origemFormatter = (cell) => {
            const val = cell.getValue();
            const row = cell.getRow().getData();
            if (row.is_ajustado) {
                const isNew = val.includes('(NOVO)');
                const icon = isNew ? 'fa-plus' : 'fa-pen';
                // Usando as variáveis de alerta do sistema (Bg + Texto da mesma família)
                const bgVar = isNew ? 'var(--luft-success-100)' : 'var(--luft-warning-100)';
                const txtVar = isNew ? 'var(--luft-success-700)' : 'var(--luft-warning-700)';
                const borderVar = isNew ? 'var(--luft-success-300)' : 'var(--luft-warning-300)';
                
                return `<span style="background: ${bgVar}; color: ${txtVar}; border: 1px solid ${borderVar}; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 700; white-space: nowrap;"><i class="fas ${icon} me-1"></i> ${val}</span>`;
            }
            // Badge genérico
            return `<span style="background: var(--luft-bg-app); border: 1px solid var(--luft-border-dark); color: var(--luft-text-muted); padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 700; white-space: nowrap;">${val}</span>`;
        };

        this.table = new Tabulator("#razaoTabulator", {
            data: this.data,
            layout: "fitColumns",
            height: "100%",
            placeholder: "Nenhum lançamento contábil encontrado.",
            movableColumns: true,
            columns: [
                {title:"Origem", field:"origem", width: 140, formatter: origemFormatter, headerFilter:"input"},
                {title:"Conta", field:"conta", width: 130, headerFilter:"input"},
                {title:"Título", field:"titulo_conta", minWidth: 200, headerFilter:"input"},
                {title:"Data", field:"data", width: 110, headerFilter:"input", formatter: (cell) => FormatUtils.formatDate(cell.getValue())},
                {title:"Doc", field:"numero", width: 100, headerFilter:"input"},
                {title:"Histórico", field:"descricao", minWidth: 250, headerFilter:"input"},
                {title:"CC", field:"centro_custo", width: 100, headerFilter:"input"},
                {title:"Filial", field:"filial", width: 80, headerFilter:"input"},
                {title:"Item", field:"item", width: 80, headerFilter:"input"},
                {title:"Débito", field:"debito", width: 120, hozAlign:"right", formatter: moneyFormatter, bottomCalc:"sum", bottomCalcFormatter: moneyFormatter},
                {title:"Crédito", field:"credito", width: 120, hozAlign:"right", formatter: moneyFormatter, bottomCalc:"sum", bottomCalcFormatter: moneyFormatter},
                {title:"Saldo", field:"saldo", width: 120, hozAlign:"right", formatter: moneyFormatter, bottomCalc:"sum", bottomCalcFormatter: moneyFormatter},
            ],
            rowFormatter: function(row){
                const data = row.getData();
                if(data.is_ajustado){
                    const origem = data.origem || "";
                    if (origem.includes("(NOVO)")) {
                         row.getElement().style.backgroundColor = "var(--luft-success-50)"; 
                         row.getElement().style.color = "var(--luft-success-900)"; 
                    } else {
                         row.getElement().style.backgroundColor = "var(--luft-warning-50)"; 
                         row.getElement().style.color = "var(--luft-warning-900)"; 
                    }
                }
            },
        });
    }

    downloadFull() {
        const searchTerm = encodeURIComponent(this.search || '');
        const viewType = this.viewType; 
        const baseUrl = API_ROUTES.getRazaoDownload;
        if (!baseUrl) { alert("Erro de configuração: Rota de download não encontrada."); return; }
        const finalUrl = `${baseUrl}?search=${searchTerm}&view_type=${viewType}`;
        const btnIcon = document.getElementById('iconDownload');
        if(btnIcon) btnIcon.className = "fas fa-spinner fa-spin text-success";
        window.location.href = finalUrl;
        setTimeout(() => { if(btnIcon) btnIcon.className = "fas fa-file-excel text-success"; }, 3000);
    }
}