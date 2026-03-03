// ============================================================================
// Luft Control - MÓDULO: RAZÃO CONTÁBIL
// Arquivo: Static/JS/Reports/RelatorioRazao.js
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
        if (!this.modal) this.modal = new ModalSystem('modalRelatorio');         
        this.page = page;
        
        const titleSuffix = this.viewType === 'adjusted' ? '(VISÃO AJUSTADA)' : '(ORIGINAL)';
        const title = this.search 
            ? `📈 Razão Contábil ${titleSuffix} - Buscando: "${this.search}"` 
            : `📈 Relatório de Razão ${titleSuffix}`;

        if (page === 1 && !document.querySelector('#razaoTableContainer')) {
            this.modal.open(title);
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
            this.modal.showError(`Erro ao carregar Razão: ${error.message}`);
        }
    }

    toggleView(isChecked) {
        this.viewType = isChecked ? 'adjusted' : 'original';
        this.loadReport(1);
    }

    renderView(metaData, summaryData) {
        const summaryHtml = `
            <div class="summary-grid mb-3">
                <div class="summary-card">
                    <div class="summary-label">Total Registros</div>
                    <div class="summary-value">${FormatUtils.formatNumber(summaryData.total_registros)}</div>
                </div>
            </div>`;

        const controlsHtml = `
            <div class="d-flex justify-content-between align-items-center mb-2 p-2 bg-tertiary rounded flex-wrap gap-2">
                <div class="d-flex align-items-center gap-3" style="flex: 1;">
                    <div class="input-group" style="max-width: 300px;">
                        <i class="input-group-icon fas fa-search"></i>
                        <input type="text" id="razaoSearchInput" class="form-control" 
                            placeholder="Busca Global (Server-side)..." value="${this.search}">
                    </div>
                    
                    <div class="form-check form-switch d-flex align-items-center gap-2 m-0 cursor-pointer">
                        <input class="form-check-input cursor-pointer" type="checkbox" role="switch" id="chkViewTypeRazao" 
                            ${this.viewType === 'adjusted' ? 'checked' : ''}
                            onchange="relatorioSystem.razao.toggleView(this.checked)">
                        <label class="form-check-label text-white cursor-pointer select-none" for="chkViewTypeRazao">
                            Modo Ajustado (Inclusões/Edições)
                        </label>
                    </div>
                </div>

                <div class="d-flex align-items-center gap-2">
                    <button class="btn btn-sm btn-success" onclick="relatorioSystem.razao.downloadFull()" title="Excel">
                        <i class="fas fa-file-excel"></i> Exportar
                    </button>
                    <div class="separator-vertical mx-2"></div>
                    <small class="text-secondary me-2">Página ${this.page} de ${this.totalPages}</small>
                    <div class="btn-group">
                        <button class="btn btn-sm btn-secondary" onclick="relatorioSystem.razao.loadReport(${this.page - 1})" ${this.page <= 1 ? 'disabled' : ''}><i class="fas fa-chevron-left"></i></button>
                        <button class="btn btn-sm btn-secondary" onclick="relatorioSystem.razao.loadReport(${this.page + 1})" ${this.page >= this.totalPages ? 'disabled' : ''}><i class="fas fa-chevron-right"></i></button>
                    </div>
                </div>
            </div>
            
            <div id="razaoTabulator" style="height: 60vh; width: 100%; border-radius: 8px; overflow: hidden;"></div>
            <div class="text-end mt-1"><small class="text-muted text-xs">* Filtros nas colunas aplicam-se à página atual.</small></div>
        `;

        this.modal.setContent(`<div style="padding: 1.5rem; height: 100%; display: flex; flex-direction: column;">${summaryHtml}${controlsHtml}</div>`);

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
            const color = val < 0 ? "text-danger" : (val > 0 ? "text-success" : "text-muted");
            return `<span class="${color}">${FormatUtils.formatCurrency(val)}</span>`;
        };

        const origemFormatter = (cell) => {
            const val = cell.getValue();
            const row = cell.getRow().getData();
            if (row.is_ajustado) {
                const isNew = val.includes('(NOVO)');
                const icon = isNew ? 'fa-plus' : 'fa-pen';
                const colorClass = isNew ? 'badge-success' : 'badge-warning';
                return `<span class="badge ${colorClass} text-xs"><i class="fas ${icon}"></i> ${val}</span>`;
            }
            return `<span class="badge badge-secondary text-xs">${val}</span>`;
        };

        this.table = new Tabulator("#razaoTabulator", {
            data: this.data,
            layout: "fitColumns",
            height: "100%",
            placeholder: "Sem dados para exibir",
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
                         row.getElement().style.backgroundColor = "rgba(40, 167, 69, 0.1)"; 
                    } else {
                         row.getElement().style.backgroundColor = "rgba(255, 193, 7, 0.1)"; 
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
        if(btnIcon) btnIcon.className = "fas fa-spinner fa-spin";
        window.location.href = finalUrl;
        setTimeout(() => { if(btnIcon) btnIcon.className = "fas fa-file-excel"; }, 3000);
    }
}