// ============================================================================
// T-Controllership - SISTEMA DE RELATÓRIOS FINANCEIROS & BI NATIVO
// Arquivo: Static/JS/Relatorios.js
// ============================================================================

if (typeof window.relatorioSystemInitialized === 'undefined') {
    window.relatorioSystemInitialized = true;

    class RelatorioSystem {
        constructor() {
            this.modal = null;
            
            // Estado do Razão
            this.razaoData = null;
            this.razaoSummary = null; 
            this.razaoPage = 1;
            this.razaoTotalPages = 1;
            this.razaoSearch = '';
            this.razaoSearchTimer = null;
            this.razaoViewType = 'original'; 

            // Estado do BI (DRE)
            this.biRawData = [];      
            this.biTreeData = [];     
            this.biState = {
                    expanded: new Set(['root']), 
                    hiddenCols: new Set(),       
                    filters: {},                 
                    globalSearch: '',
                    // NOVOS ESTADOS PARA A BUSCA
                    searchMatches: [],      // Array com IDs dos nós encontrados
                    searchCurrentIndex: -1, // Índice atual da navegação            
                    sort: { col: null, dir: 'asc' }, 
                    columnsOrder: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez', 'Total_Ano'],            
                    origemFilter: 'Consolidado',  
                    viewMode: 'TIPO',
                    scaleMode: 'dre' // PADRÃO: DRE (dividido por 1000)
                };
            this.biDebounceTimer = null;
            this.biIsLoading = false;        
            this.nosCalculados = [];

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
                this.modal = new ModalSystem('modalRelatorio');
            }
        }

        // ====================================================================
        // --- MÓDULO 1: RAZÃO CONTÁBIL ---
        // ====================================================================

        async loadRazaoReport(page = 1) {
            if (!this.modal) this.modal = new ModalSystem('modalRelatorio');         
            this.razaoPage = page;
            
            const titleSuffix = this.razaoViewType === 'adjusted' ? '(VISÃO AJUSTADA)' : '(ORIGINAL)';
            const title = this.razaoSearch 
                ? `📈 Razão Contábil ${titleSuffix} - Buscando: "${this.razaoSearch}"` 
                : `📈 Relatório de Razão ${titleSuffix}`;

            if (page === 1 && !document.querySelector('#razaoTableContainer')) {
                this.modal.open(title);
                this.modal.showLoading('Carregando lançamentos contábeis...');
            }

            try {
                const urlData = (API_ROUTES?.getRazaoData) || '/Reports/RelatorioRazao/Dados'; 
                const urlSummary = (API_ROUTES?.getRazaoResumo) || '/Reports/RelatorioRazao/Resumo';

                const term = encodeURIComponent(this.razaoSearch);
                const viewType = this.razaoViewType;
                
                const [respData, respSummary] = await Promise.all([
                    APIUtils.get(`${urlData}?page=${page}&search=${term}&view_type=${viewType}`),
                    APIUtils.get(`${urlSummary}?view_type=${viewType}`)
                ]);

                this.razaoData = respData.dados || [];
                this.razaoTotalPages = respData.total_paginas || 1;
                this.razaoSummary = respSummary;

                this.renderRazaoView(respData, respSummary);
            } catch (error) {
                console.error(error);
                this.modal.showError(`Erro ao carregar Razão: ${error.message}`);
            }
        }

        renderRazaoView(metaData, summaryData) {
            const summaryHtml = `
                <div class="summary-grid mb-3">
                    <div class="summary-card">
                        <div class="summary-label">Total Registros</div>
                        <div class="summary-value">${FormatUtils.formatNumber(summaryData.total_registros)}</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-label">Total Débito</div>
                        <div class="summary-value text-danger font-bold">
                            ${FormatUtils.formatCurrency(summaryData.total_debito)}
                        </div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-label">Total Crédito</div>
                        <div class="summary-value text-success font-bold">
                            ${FormatUtils.formatCurrency(summaryData.total_credito)}
                        </div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-label">Saldo Total</div>
                        <div class="summary-value ${summaryData.saldo_total >= 0 ? 'text-success' : 'text-danger'} font-bold">
                            ${FormatUtils.formatCurrency(summaryData.saldo_total)}
                        </div>
                    </div>
                </div>`;

            const rows = this.razaoData.map(r => {
                const styleClass = r.is_ajustado ? 'background-color: rgba(255, 248, 225, 0.1);' : '';
                const badgeOrigem = r.is_ajustado 
                    ? `<span class="badge badge-warning" title="Lançamento Ajustado"><i class="fas fa-pen"></i> ${r.origem}</span>`
                    : `<span class="badge badge-secondary">${r.origem}</span>`;

                return `
                <tr style="${styleClass}">
                    <td class="font-mono text-xs">${r.conta}</td>
                    <td>${r.titulo_conta || '-'}</td>
                    <td>${FormatUtils.formatDate(r.data)}</td>
                    <td>${r.numero || ''}</td>
                    <td><small class="text-secondary">${r.descricao || ''}</small></td>
                    <td class="text-end text-danger">${FormatUtils.formatNumber(r.debito)}</td>
                    <td class="text-end text-success">${FormatUtils.formatNumber(r.credito)}</td>
                    <td class="text-end font-bold ${r.saldo >= 0 ? 'text-success' : 'text-danger'}">
                        ${FormatUtils.formatNumber(r.saldo)}
                    </td>
                    <td>${badgeOrigem}</td>
                </tr>
            `}).join('');

            const tableHtml = `
                <div class="d-flex justify-content-between align-items-center mb-3 p-2 bg-tertiary rounded flex-wrap gap-2">
                    <div class="d-flex align-items-center gap-3" style="flex: 1;">
                        <div class="input-group" style="max-width: 350px;">
                            <i class="input-group-icon fas fa-search"></i>
                            <input type="text" id="razaoSearchInput" class="form-control" 
                                   placeholder="Filtrar por conta, histórico..." value="${this.razaoSearch}">
                        </div>
                        
                        <div class="form-check form-switch d-flex align-items-center gap-2 m-0 cursor-pointer">
                            <input class="form-check-input cursor-pointer" type="checkbox" role="switch" id="chkViewTypeRazao" 
                                   ${this.razaoViewType === 'adjusted' ? 'checked' : ''}
                                   onchange="relatorioSystem.toggleRazaoView(this.checked)">
                            <label class="form-check-label text-white cursor-pointer select-none" for="chkViewTypeRazao">
                                Visualizar Ajustes
                            </label>
                        </div>
                    </div>

                    <div class="d-flex align-items-center gap-2">
                        <button class="btn btn-sm btn-success" onclick="relatorioSystem.downloadRazaoFull()" title="Baixar Relatório Completo em Excel">
                            <i id="iconDownload" class="fas fa-file-excel"></i> Exportar Full
                        </button>
                        
                        <div class="separator-vertical mx-2" style="height: 20px; border-left: 1px solid var(--border-secondary);"></div>
                        <small class="text-secondary me-2">Pag ${this.razaoPage}/${this.razaoTotalPages}</small>
                        <div class="btn-group">
                            <button class="btn btn-sm btn-secondary" onclick="relatorioSystem.loadRazaoReport(${this.razaoPage - 1})" ${this.razaoPage <= 1 ? 'disabled' : ''}><i class="fas fa-chevron-left"></i></button>
                            <button class="btn btn-sm btn-secondary" onclick="relatorioSystem.loadRazaoReport(${this.razaoPage + 1})" ${this.razaoPage >= this.razaoTotalPages ? 'disabled' : ''}><i class="fas fa-chevron-right"></i></button>
                        </div>
                    </div>
                </div>
                <div id="razaoTableContainer" class="table-fixed-container" style="height: 55vh;">
                    <table class="table-modern table-hover">
                        <thead style="position: sticky; top: 0; z-index: 10;">
                            <tr><th>Conta</th><th>Título</th><th>Data</th><th>Doc</th><th>Histórico</th><th class="text-end">Débito</th><th class="text-end">Crédito</th><th class="text-end">Saldo</th><th>Origem</th></tr>
                        </thead>
                        <tbody>${rows || '<tr><td colspan="9" class="text-center p-4">Vazio.</td></tr>'}</tbody>
                    </table>
                </div>`;

            this.modal.setContent(`<div style="padding: 1.5rem;">${summaryHtml}${tableHtml}</div>`);
            
            const input = document.getElementById('razaoSearchInput');
            if (input) {
                input.focus();
                input.addEventListener('input', (e) => {
                    clearTimeout(this.razaoSearchTimer);
                    this.razaoSearchTimer = setTimeout(() => {
                        this.razaoSearch = e.target.value;
                        this.loadRazaoReport(1);
                    }, 600);
                });
            }
        }

        toggleRazaoView(isChecked) {
            this.razaoViewType = isChecked ? 'adjusted' : 'original';
            this.loadRazaoReport(1);
        }

        // ====================================================================
        // --- MÓDULO 2: RENTABILIDADE (BI) ---
        // ====================================================================

        // --- NOVA FUNÇÃO PARA ALTERNAR O MODO ---
        toggleScaleMode() {
            if (this.biIsLoading) return;
            // Alterna entre 'dre' e 'normal'
            this.biState.scaleMode = (this.biState.scaleMode === 'dre') ? 'normal' : 'dre';
            // Recarrega os dados do backend (pois o cálculo é feito lá)
            this.loadRentabilidadeReport(this.biState.origemFilter);
        }

        // --- NOVA FUNÇÃO AUXILIAR DE FORMATAÇÃO VISUAL ---
        formatDREValue(value) {
            if (value === 0 || value === null) return '-';
            
            // Se for negativo, remove o sinal e coloca parênteses
            const isNegative = value < 0;
            const absValue = Math.abs(value);
            
            // Formata o número (0 casas decimais para DRE geralmente fica mais limpo, 
            // mas se quiser decimais mude para minimumFractionDigits: 2)
            const formatted = absValue.toLocaleString('pt-BR', { 
                minimumFractionDigits: 0, 
                maximumFractionDigits: 0 
            });

            return isNegative ? `(${formatted})` : formatted;
        }

        // --- ATUALIZAÇÃO DO loadRentabilidadeReport PARA ENVIAR O PARÂMETRO ---
        async loadRentabilidadeReport(origem = null) {
            if (!this.modal) this.modal = new ModalSystem('modalRelatorio');
            
            if (origem !== null) this.biState.origemFilter = origem;
            
            // Título dinâmico
            const viewTitle = this.biState.viewMode === 'CC' ? 'por Centro de Custo' : 'por Tipo';
            const scaleTitle = this.biState.scaleMode === 'dre' ? '(Em Milhares)' : '(Valor Integral)';
            
            this.modal.open(`<i class="fas fa-cubes"></i> Análise Gerencial ${viewTitle} <small class="modal-title">${scaleTitle}</small>`, '');
            this.modal.showLoading('Construindo cubo de dados...');

            try {
                let urlBase;
                if (this.biState.viewMode === 'CC') {
                    urlBase = (API_ROUTES?.getRentabilidadeDataCC) || '/Reports/RelatorioRazao/RentabilidadePorCC';
                } else {
                    urlBase = (API_ROUTES?.getRentabilidadeData) || '/Reports/RelatorioRazao/Rentabilidade';
                }

                const origemParam = encodeURIComponent(this.biState.origemFilter);
                // ADICIONADO: scale_mode
                const scaleParam = this.biState.scaleMode; 
                
                const rawData = await APIUtils.get(`${urlBase}?origem=${origemParam}&scale_mode=${scaleParam}`);
                
                if (!rawData || rawData.length === 0) {
                    this.renderBiEmptyState();
                    return;
                }

                this.biRawData = rawData;
                await this.processBiTreeWithCalculated();
                this.renderBiInterface();

            } catch (error) {
                console.error(error);
                this.modal.showError(`Erro no BI: ${error.message}`);
            }
        }

        toggleViewMode() {
            if (this.biIsLoading) return;
            this.biState.viewMode = (this.biState.viewMode === 'TIPO') ? 'CC' : 'TIPO';
            this.loadRentabilidadeReport(this.biState.origemFilter);
        }

        renderBiEmptyState() {
            const emptyHtml = `
                <div class="bi-toolbar d-flex justify-content-between align-items-center p-3 border-bottom border-primary bg-tertiary">
                    <div class="d-flex gap-2 align-items-center">${this.renderOrigemFilter()}</div>
                </div>
                <div class="p-4 text-center" style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;">
                    <i class="fas fa-database fa-3x text-muted mb-3"></i>
                    <h4 class="text-secondary">Sem dados</h4>
                    <p class="text-muted">Nenhum registro encontrado para "${this.biState.origemFilter}".</p>
                </div>`;
            this.modal.setContent(`<div style="display: flex; flex-direction: column; height: 100%;">${emptyHtml}</div>`);
        }

        async reloadBiDataAsync(novaOrigem) {
            if (this.biIsLoading) return;
            this.biIsLoading = true;
            this.biState.origemFilter = novaOrigem;
            
            const container = document.getElementById('biGridContainer');
            if (container) container.innerHTML = `<div class="loading-container" style="height: 100%;"><div class="loading-spinner"></div></div>`;

            try {
                let urlBase = (this.biState.viewMode === 'CC') 
                    ? (API_ROUTES?.getRentabilidadeDataCC || '/Reports/RelatorioRazao/RentabilidadePorCC')
                    : (API_ROUTES?.getRentabilidadeData || '/Reports/RelatorioRazao/Rentabilidade');

                const origemParam = encodeURIComponent(novaOrigem);
                const scaleParam = this.biState.scaleMode;

                const rawData = await APIUtils.get(`${urlBase}?origem=${origemParam}&scale_mode=${scaleParam}`);
                
                // ... restante da função igual ...
                if (!rawData || rawData.length === 0) {
                    this.biRawData = [];
                    this.biTreeData = [];
                    if (container) container.innerHTML = '<div class="p-4 text-center text-muted">Vazio</div>';
                } else {
                    this.biRawData = rawData;
                    await this.processBiTreeWithCalculated();
                    this.renderBiTable();
                }
                this.updateOrigemBadge();
            } catch (error) {
            // ... erro ...
            } finally {
                this.biIsLoading = false;
            }
        }

        updateOrigemBadge() {
            const badge = document.getElementById('biOrigemBadge');
            if (badge) badge.textContent = `${this.biRawData.length} registros`;
        }

        renderOrigemFilter() {
            const opcoes = ['Consolidado', 'FARMA', 'FARMADIST'];
            return `
                <div class="origem-filter-group d-flex align-items-center gap-2">
                    <div class="btn-group origem-toggle-group" role="group">
                        ${opcoes.map(op => `
                            <button type="button" class="btn btn-sm origem-toggle-btn ${this.biState.origemFilter === op ? 'active' : ''}" 
                                    data-origem="${op}" onclick="relatorioSystem.handleOrigemChange('${op}')">
                                ${this.getOrigemIcon(op)} ${op}
                            </button>
                        `).join('')}
                    </div>
                    <span id="biOrigemBadge" class="badge badge-secondary ms-2">${this.biRawData.length}</span>
                </div>`;
        }

        getOrigemIcon(origem) {
            const icons = {'Consolidado': '<i class="fas fa-layer-group"></i>', 'FARMA': '<i class="fas fa-pills"></i>', 'FARMADIST': '<i class="fas fa-truck"></i>'};
            return icons[origem] || '';
        }

        handleOrigemChange(novaOrigem) {
            if (novaOrigem === this.biState.origemFilter || this.biIsLoading) return;
            document.querySelectorAll('.origem-toggle-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.origem === novaOrigem);
            });
            this.reloadBiDataAsync(novaOrigem);
        }

        processBiTree() {
            const root = [];
            const map = {}; 
            const meses = this.biState.columnsOrder;

            const getOrCreateNode = (id, label, type, parentList, defaultOrder = 9999) => {
                if (!map[id]) {
                    const node = { 
                        id: id, 
                        label: label, 
                        type: type, 
                        children: [], 
                        values: {},
                        isVisible: true,
                        isExpanded: this.biState.expanded.has(id),
                        ordem: defaultOrder 
                    };
                    meses.forEach(m => node.values[m] = 0);
                    map[id] = node;
                    parentList.push(node);
                }
                return map[id];
            };

            const sumValues = (node, row) => {
                meses.forEach(m => node.values[m] += (parseFloat(row[m]) || 0));
            };

            this.biRawData.forEach((row, index) => {
                const ordemVal = (row.ordem_prioridade !== null && row.ordem_prioridade !== undefined) 
                    ? row.ordem_prioridade 
                    : (row.Ordem || row.ordem || (index * 10) + 1000);

                const tipoId = `T_${row.Tipo_CC}`;
                const tipoNode = getOrCreateNode(tipoId, row.Tipo_CC, 'root', root, ordemVal);
                if (row.Root_Virtual_Id) tipoNode.virtualId = row.Root_Virtual_Id;
                
                if ((row.ordem_prioridade !== null || row.Ordem) && tipoNode.ordem >= 1000) {
                    tipoNode.ordem = (row.ordem_prioridade !== null) ? row.ordem_prioridade : row.Ordem;
                }
                sumValues(tipoNode, row);

                let currentNode = tipoNode;
                let currentId = tipoId;

                if (this.biState.viewMode === 'CC' && row.Nome_CC) {
                    const safeCCName = String(row.Nome_CC).replace(/[^a-zA-Z0-9]/g, '');
                    currentId += `_CC_${safeCCName}`;
                    const ccNode = getOrCreateNode(currentId, row.Nome_CC, 'group', currentNode.children);
                    sumValues(ccNode, row);
                    currentNode = ccNode;
                }

                if (row.Caminho_Subgrupos && row.Caminho_Subgrupos !== 'Não Classificado' && row.Caminho_Subgrupos !== 'Direto' && row.Caminho_Subgrupos !== 'Calculado') {
                    const groups = row.Caminho_Subgrupos.split('||');
                    groups.forEach((gName, idx) => {
                        const safeGName = gName.replace(/[^a-zA-Z0-9]/g, '');
                        currentId += `_G${idx}_${safeGName}`; 
                        const groupNode = getOrCreateNode(currentId, gName, 'group', currentNode.children);
                        sumValues(groupNode, row);
                        currentNode = groupNode;
                    });
                }

                const contaId = `C_${row.Conta}_${currentId}`; 
                const contaNode = {
                    id: contaId,
                    label: `📄 ${row.Conta} - ${row.Titulo_Conta}`,
                    type: 'account',
                    children: [],
                    values: {},
                    isVisible: true,
                    ordem: 0 
                };
                meses.forEach(m => contaNode.values[m] = parseFloat(row[m]) || 0);
                currentNode.children.push(contaNode);
            });

            this.biTreeData = root;
            this.applyBiFilters();
        }

        renderBiInterface() {
            const isCC = this.biState.viewMode === 'CC';
            const btnClass = isCC ? 'btn-warning' : 'btn-primary';
            const btnIcon = isCC ? 'fa-building' : 'fa-sitemap';
            const btnText = isCC ? 'Visão: Centro de Custo' : 'Visão: Tipo';

            // Lógica do botão de Escala
            const isDreMode = this.biState.scaleMode === 'dre';
            const btnScaleClass = isDreMode ? 'btn-info' : 'btn-secondary';
            const btnScaleIcon = isDreMode ? 'fa-divide' : 'fa-dollar-sign';
            const btnScaleText = isDreMode ? 'Escala: Milhares (DRE)' : 'Escala: Reais';

            const toolbar = `
                <div class="bi-toolbar d-flex justify-content-between align-items-center p-3 border-bottom border-primary bg-tertiary">
                    <div class="d-flex gap-2 align-items-center flex-wrap">
                        ${this.renderOrigemFilter()}
                        
                        <button class="btn btn-sm ${btnClass}" onclick="relatorioSystem.toggleViewMode()" title="Alternar Agrupamento">
                            <i class="fas ${btnIcon}"></i> ${btnText}
                        </button>

                        <button class="btn btn-sm ${btnScaleClass}" onclick="relatorioSystem.toggleScaleMode()" title="Alternar Escala de Valores">
                            <i class="fas ${btnScaleIcon}"></i> ${btnScaleText}
                        </button>

                        <div class="separator-vertical mx-2" style="height: 20px; border-left: 1px solid var(--border-secondary);"></div>
                        <div class="input-group input-group-sm" style="width: 200px;">
                            <i class="input-group-icon fas fa-search"></i>
                            <input type="text" id="biGlobalSearch" class="form-control" 
                                placeholder="Buscar e navegar (Enter)..." value="${this.biState.globalSearch}"
                                oninput="relatorioSystem.handleBiGlobalSearch(this.value)"
                                onkeydown="if(event.key === 'Enter') { event.preventDefault(); relatorioSystem.navigateSearchNext(); }">
                        </div>
                    </div>
                    <div class="d-flex gap-2 align-items-center">
                        <button class="btn btn-sm btn-outline" onclick="relatorioSystem.toggleAllNodes(true)" title="Expandir Tudo"><i class="fas fa-expand-arrows-alt"></i></button>
                        <button class="btn btn-sm btn-outline" onclick="relatorioSystem.toggleAllNodes(false)" title="Recolher Tudo"><i class="fas fa-compress-arrows-alt"></i></button>
                        <button class="btn btn-sm btn-outline" onclick="relatorioSystem.openColumnManager()" title="Colunas"><i class="fas fa-columns"></i></button>
                        <div class="separator-vertical mx-1" style="height: 20px; border-left: 1px solid var(--border-secondary);"></div>
                        <!-- <button class="btn btn-sm btn-success" onclick="relatorioSystem.exportBiToCsv()"><i class="fas fa-file-csv"></i> Exportar</button>  DESATIVANDO BOTÃO DE EXPORTAR --!> 
                    </div>
                </div>`;
            
            const gridContainer = `<div id="biGridContainer" class="table-fixed-container" style="flex: 1; overflow: auto; background: var(--bg-secondary);"></div>`;
            const footer = `
                <div class="bi-footer p-2 bg-tertiary border-top border-primary d-flex justify-content-between align-items-center">
                    <span class="text-secondary text-xs">Fonte: <strong>${this.biState.origemFilter}</strong> | Modo: <strong>${this.biState.viewMode}</strong> | Escala: <strong>${this.biState.scaleMode.toUpperCase()}</strong></span>
                    <span class="text-muted text-xs">Atualizado: ${new Date().toLocaleTimeString('pt-BR')}</span>
                </div>`;

            this.modal.setContent(`<div style="display: flex; flex-direction: column; height: 100%;">${toolbar}${gridContainer}${footer}</div>`);
            this.renderBiTable();
        }

        renderBiTable() {
            const container = document.getElementById('biGridContainer');
            if (!container) return;

            const cols = this.biState.columnsOrder.filter(c => !this.biState.hiddenCols.has(c));
            const rootHeaderName = this.biState.viewMode === 'CC' ? 'Estrutura / Centro de Custo' : 'Estrutura DRE';

            // --- HEADER DA TABELA (SEM ESTILOS INLINE DE COR) ---
            let headerHtml = `
                <thead style="position: sticky; top: 0; z-index: 20;">
                    <tr>
                        <th style="min-width: 350px; left: 0; position: sticky; z-index: 30;">
                            ${rootHeaderName}
                        </th>
                        ${cols.map(c => `
                            <th class="text-end" style="min-width: 110px;">
                                <div class="d-flex flex-column">
                                    <span class="mb-1 cursor-pointer text-xs font-bold" onclick="relatorioSystem.sortBiBy('${c}')">${c}</span>
                                </div>
                            </th>
                        `).join('')}
                    </tr>
                </thead>`;

            let bodyRows = '';
            
            // --- VARIÁVEIS DE COR PARA ÍCONES (VEM DO CSS THEMES) ---
            const COLOR_DARK   = 'color: var(--icon-structure);'; 
            const COLOR_GRAY   = 'color: var(--icon-secondary);'; 
            const COLOR_FOLDER = 'color: var(--icon-folder);'; 
            const COLOR_LIGHT  = 'color: var(--icon-account);';

            const renderNode = (node, level) => {
                if (!node.isVisible) return;
                const padding = level * 20 + 10;
                const isGroup = node.children && node.children.length > 0;
                const isExpanded = this.biState.expanded.has(node.id);
                
                let iconClass = '';
                let iconStyle = '';

                if (node.type === 'calculated') {
                    iconClass = 'fa-calculator';
                    iconStyle = COLOR_DARK;
                } 
                else if (node.type === 'root') {
                    if (node.virtualId) {
                        iconClass = 'fa-cube';
                        iconStyle = COLOR_DARK;
                    } else {
                        iconClass = 'fa-layer-group';
                        iconStyle = COLOR_DARK;
                        
                        // Refinamento: Globo para Grupo Raiz (ordem baixa)
                        if (node.ordem < 1000 && !node.virtualId) {
                            iconClass = 'fa-globe';
                            iconStyle = COLOR_GRAY;
                        }
                    }
                }
                else if (node.type === 'group') {
                    iconClass = 'fa-folder';
                    iconStyle = COLOR_FOLDER;
                }
                else if (node.type === 'account') {
                    iconClass = 'fa-file-alt';
                    iconStyle = COLOR_LIGHT;
                }

                let iconHtml = '';
                if (isGroup) {
                    // Seta discreta
                    iconHtml = `<i class="fas fa-caret-${isExpanded ? 'down' : 'right'} me-2 toggle-icon" onclick="event.stopPropagation(); relatorioSystem.toggleNode('${node.id}')" style="width:10px; cursor: pointer; color: var(--text-tertiary);"></i>`;
                    iconHtml += `<i class="fas ${iconClass} me-2" style="${iconStyle}"></i>`;
                } else {
                    iconHtml = `<i class="fas ${iconClass} me-2" style="margin-left: 18px; ${iconStyle}"></i>`;
                }

                // Estilos de Fonte (Classes CSS, sem cor inline)
                let labelStyle = ''; 
                // As cores do texto são definidas no CSS pelas classes bi-row-*

                const customStyle = node.estiloCss ? `style="${node.estiloCss}"` : '';
                
                const cellsHtml = cols.map(c => {
                    const val = node.values[c];
                    
                    // Cores de valor (Bootstrap Standard)
                    let colorClass = '';
                    if (val < 0) colorClass = 'text-danger'; 
                    else if (val === 0) colorClass = 'text-muted';
                    
                    let displayVal = '-';
                    
                    if (val !== 0) {
                        if (this.biState.scaleMode === 'dre') {
                            // MODO DRE: Usa a formatação com parênteses
                            displayVal = this.formatDREValue(val);
                        } else {
                            // MODO NORMAL: Usa formatação padrão numérica
                            displayVal = FormatUtils.formatNumber(val);
                        }
                    }
                    
                    if (node.tipoExibicao === 'percentual' && val !== 0) displayVal = val.toFixed(2) + '%';
                    
                    const weight = (node.type === 'root' || node.type === 'calculated') ? 'font-weight: 600;' : '';
                    
                    return `<td class="text-end font-mono ${colorClass}" style="${weight}">${displayVal}</td>`;
                }).join('');

                const isMatch = this.biState.searchMatches.includes(node.id);
                const searchClass = isMatch ? 'search-match' : '';

                // GERAÇÃO DA LINHA (SEM STYLE BACKGROUND COLOR FIXO)
                bodyRows += `<tr id="row_${node.id}" class="bi-row-${node.type} ${searchClass}" ${customStyle}>
                        <td style="padding-left: ${padding}px;">
                            <div class="d-flex align-items-center cell-label" style="${labelStyle}">
                                ${iconHtml}<span class="text-truncate" title="${node.formulaDescricao || ''}">${node.label}</span>
                            </div>
                        </td>${cellsHtml}</tr>`;

                if (isGroup && isExpanded) node.children.forEach(child => renderNode(child, level + 1));
            };

            this.biTreeData.forEach(node => renderNode(node, 0));
            container.innerHTML = `<table class="table-modern w-100" style="border-collapse: separate; border-spacing: 0;">${headerHtml}<tbody>${bodyRows}</tbody></table>`;
        }

        // --- MÉTODOS AUXILIARES ---
        applyBiFilters() {
            const colFilters = this.biState.filters;
            const hasColFilters = Object.keys(colFilters).length > 0;

            const checkVisibility = (node) => {
                // A Busca Global NÃO afeta visibilidade (matchesGlobal é sempre true para renderizar)
                // Apenas expandimos os nós na função performSearchTraversal
                
                let matchesCols = true;
                
                // Filtros de Coluna (numéricos/valores) continuam escondendo linhas
                if (hasColFilters) {
                    for (const [col, filterVal] of Object.entries(colFilters)) {
                        if (!filterVal) continue;
                        const nodeVal = node.values[col];
                        let pass = false;
                        const cleanFilter = filterVal.replace(',', '.').trim();
                        if (cleanFilter.startsWith('>')) pass = nodeVal > parseFloat(cleanFilter.substring(1));
                        else if (cleanFilter.startsWith('<')) pass = nodeVal < parseFloat(cleanFilter.substring(1));
                        else pass = nodeVal.toString().includes(cleanFilter); 
                        if (!pass) { matchesCols = false; break; }
                    }
                }

                let hasVisibleChildren = false;
                if (node.children) node.children.forEach(child => { if (checkVisibility(child)) hasVisibleChildren = true; });
                
                // Visível se passar nos filtros de coluna OU tiver filhos visíveis
                const isVisible = matchesCols || hasVisibleChildren;
                node.isVisible = isVisible;
                
                // Se filtro de coluna estiver ativo e passar, expande para mostrar
                if (isVisible && hasColFilters) this.biState.expanded.add(node.id); 
                
                return isVisible;
            };
            this.biTreeData.forEach(node => checkVisibility(node));
        }
        handleBiGlobalSearch(val) { 
            this.biState.globalSearch = val; 
            
            // Se limpar, reseta tudo
            if (!val) {
                this.biState.searchMatches = [];
                this.biState.searchCurrentIndex = -1;
                this.renderBiTable(); // Renderiza limpo
                return;
            }

            clearTimeout(this.biDebounceTimer); 
            this.biDebounceTimer = setTimeout(() => { 
                this.performSearchTraversal(); 
            }, 400); 
        }

        performSearchTraversal() {
            const term = this.biState.globalSearch.toLowerCase();
            this.biState.searchMatches = []; // Reseta matches
            this.biState.searchCurrentIndex = -1;

            if (!term) return;

            // Função recursiva para encontrar matches e expandir pais
            const findAndExpand = (nodes, parentIds = []) => {
                nodes.forEach(node => {
                    const match = node.label.toLowerCase().includes(term);
                    
                    if (match) {
                        // Adiciona aos encontrados
                        this.biState.searchMatches.push(node.id);
                        // Expande todos os pais deste nó para garantir que ele esteja visível
                        parentIds.forEach(pid => this.biState.expanded.add(pid));
                    }

                    if (node.children && node.children.length > 0) {
                        findAndExpand(node.children, [...parentIds, node.id]);
                    }
                });
            };

            findAndExpand(this.biTreeData);

            // Se encontrou algo, prepara para ir ao primeiro
            if (this.biState.searchMatches.length > 0) {
                this.renderBiTable(); // Re-renderiza para aplicar classes e abrir pastas
                
                // Pequeno delay para garantir que o DOM existe antes de focar
                setTimeout(() => this.navigateSearchNext(), 100);
            } else {
                this.renderBiTable(); // Re-renderiza mesmo sem matches para limpar destaques anteriores
            }
        }

        navigateSearchNext() {
            if (this.biState.searchMatches.length === 0) return;

            // Incrementa índice (loop circular)
            this.biState.searchCurrentIndex++;
            if (this.biState.searchCurrentIndex >= this.biState.searchMatches.length) {
                this.biState.searchCurrentIndex = 0;
            }

            const nodeId = this.biState.searchMatches[this.biState.searchCurrentIndex];
            this.scrollToNode(nodeId);
            this.updateSearchHighlights();
        }

        scrollToNode(nodeId) {
            const row = document.getElementById(`row_${nodeId}`);
            if (row) {
                row.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }

        updateSearchHighlights() {
            // Remove destaque de foco anterior
            document.querySelectorAll('.search-current-match').forEach(el => el.classList.remove('search-current-match'));
            
            const currentId = this.biState.searchMatches[this.biState.searchCurrentIndex];
            const row = document.getElementById(`row_${currentId}`);
            if (row) {
                row.classList.add('search-current-match');
            }
        }

        handleBiColFilter(col, val) { if (!val) delete this.biState.filters[col]; else this.biState.filters[col] = val; this.debounceRender(); }
        debounceRender() { clearTimeout(this.biDebounceTimer); this.biDebounceTimer = setTimeout(() => { this.applyBiFilters(); this.renderBiTable(); }, 400); }
        toggleNode(id) { if (this.biState.expanded.has(id)) this.biState.expanded.delete(id); else this.biState.expanded.add(id); this.renderBiTable(); }
        toggleAllNodes(expand) { const recurse = (nodes) => { nodes.forEach(n => { if (expand) this.biState.expanded.add(n.id); else this.biState.expanded.delete(n.id); if (n.children) recurse(n.children); }); }; recurse(this.biTreeData); this.renderBiTable(); }
        openColumnManager() {
            const allCols = this.biState.columnsOrder;
            
            // Verifica se todos estão visíveis para marcar o "Selecionar Todos"
            const allVisible = allCols.every(c => !this.biState.hiddenCols.has(c));

            const modalHtml = `
                <div class="column-manager-container">
                    <div class="column-manager-header">
                        <h5 class="m-0"><i class="fas fa-columns text-primary"></i> Gerenciar Colunas</h5>
                        <button class="btn btn-sm btn-outline" onclick="relatorioSystem.toggleAllColumns(this)">
                            <i class="fas ${allVisible ? 'fa-check-square' : 'fa-square'}"></i> ${allVisible ? 'Desmarcar Todos' : 'Selecionar Todos'}
                        </button>
                    </div>
                    
                    <div class="column-grid">
                        ${allCols.map(c => {
                            const isVisible = !this.biState.hiddenCols.has(c);
                            return `
                            <label class="column-option ${isVisible ? 'selected' : ''}">
                                <input type="checkbox" class="column-checkbox" 
                                    value="${c}" 
                                    ${isVisible ? 'checked' : ''} 
                                    onchange="relatorioSystem.handleColumnToggle(this, '${c}')">
                                <span>${c}</span>
                            </label>
                            `;
                        }).join('')}
                    </div>

                    <div class="mt-4 text-end border-top border-primary pt-3">
                        <button class="btn btn-primary-custom" style="width: auto; padding: 8px 24px;" 
                                onclick="document.querySelector('.modal-backdrop').remove(); relatorioSystem.renderBiTable()">
                            <i class="fas fa-check"></i> Aplicar Alterações
                        </button>
                    </div>
                </div>`;

            // Cria o Modal Backdrop (mesma lógica anterior, mas com estilo melhor)
            const colModal = document.createElement('div'); 
            colModal.className = 'modal-backdrop active'; 
            colModal.innerHTML = `<div class="modal-window" style="max-width: 600px;">${modalHtml}</div>`;
            
            colModal.onclick = (e) => { 
                if(e.target === colModal) {
                    colModal.remove(); 
                    this.renderBiTable(); // Aplica ao fechar clicando fora também
                }
            }; 
            document.body.appendChild(colModal);
        }

        // Manipulador individual de checkbox (para atualizar estilo visual instantaneamente)
        handleColumnToggle(checkbox, col) {
            if (checkbox.checked) {
                this.biState.hiddenCols.delete(col);
                checkbox.closest('.column-option').classList.add('selected');
            } else {
                this.biState.hiddenCols.add(col);
                checkbox.closest('.column-option').classList.remove('selected');
            }
            // Atualiza botão "Selecionar Todos" dinamicamente
            this.updateSelectAllBtnState();
        }

        // Lógica "Selecionar Todos / Desmarcar Todos"
        toggleAllColumns(btn) {
            const allCols = this.biState.columnsOrder;
            const checkboxes = document.querySelectorAll('.column-grid input[type="checkbox"]');
            
            // Se o botão tem ícone de check, vamos desmarcar tudo. Se não, marcar tudo.
            const isCurrentlyAllChecked = btn.querySelector('i').classList.contains('fa-check-square');
            const newState = !isCurrentlyAllChecked;

            checkboxes.forEach(chk => {
                chk.checked = newState;
                const col = chk.value;
                const parent = chk.closest('.column-option');
                
                if (newState) {
                    this.biState.hiddenCols.delete(col);
                    parent.classList.add('selected');
                } else {
                    this.biState.hiddenCols.add(col);
                    parent.classList.remove('selected');
                }
            });

            this.updateSelectAllBtnState();
        }

        updateSelectAllBtnState() {
            const btn = document.querySelector('.column-manager-header button');
            if(!btn) return;
            
            const allCols = this.biState.columnsOrder;
            const allVisible = allCols.every(c => !this.biState.hiddenCols.has(c));
            
            if(allVisible) {
                btn.innerHTML = '<i class="fas fa-check-square"></i> Desmarcar Todos';
            } else {
                btn.innerHTML = '<i class="fas fa-square"></i> Selecionar Todos';
            }
        }

        toggleBiColumn(col) { if (this.biState.hiddenCols.has(col)) this.biState.hiddenCols.delete(col); else this.biState.hiddenCols.add(col); }
        sortBiBy(col) { 
            if (this.biState.sort.col === col) this.biState.sort.dir = this.biState.sort.dir === 'asc' ? 'desc' : 'asc';
            else { this.biState.sort.col = col; this.biState.sort.dir = 'desc'; }
            const sortNodes = (nodes) => {
                nodes.sort((a, b) => { const valA = a.values[col] || 0; const valB = b.values[col] || 0; return this.biState.sort.dir === 'asc' ? valA - valB : valB - valA; });
                nodes.forEach(n => { if (n.children) sortNodes(n.children); });
            };
            sortNodes(this.biTreeData); this.renderBiTable();
        }
        exportBiToCsv() { 
            let csv = "data:text/csv;charset=utf-8,";
            const visibleCols = this.biState.columnsOrder.filter(c => !this.biState.hiddenCols.has(c));
            csv += `# BI DRE - ${this.biState.origemFilter} - ${this.biState.viewMode}\r\nEstrutura;${visibleCols.join(";")}\r\n`;
            const processRow = (node, prefix = "") => {
                if (!node.isVisible) return;
                csv += `"${prefix}${node.label}";` + visibleCols.map(c => (node.values[c]||0).toFixed(2).replace('.',',')).join(";") + "\r\n";
                if(node.children) node.children.forEach(child => processRow(child, prefix + "  "));
            };
            this.biTreeData.forEach(n => processRow(n));
            const link = document.createElement("a"); link.href = encodeURI(csv); link.download = "bi_dre.csv"; document.body.appendChild(link); link.click(); link.remove();
        }
        async loadNosCalculados() { try { const r = await APIUtils.get((API_ROUTES?.getNosCalculados) || '/Configuracao/GetNosCalculados'); this.nosCalculados = r || []; return this.nosCalculados; } catch { return []; } }
        
        calcularValorNo(formula, mes, valoresAgregados) {
            if (!formula || !formula.operandos) return 0;
            const valores = formula.operandos.map(op => valoresAgregados[`${op.tipo}_${op.id}`]?.[mes] || 0);
            let res = 0;
            if (formula.operacao === 'soma') res = valores.reduce((a, b) => a + b, 0);
            else if (formula.operacao === 'subtracao') res = valores[0] - valores.slice(1).reduce((a, b) => a + b, 0);
            else if (formula.operacao === 'multiplicacao') res = valores.reduce((a, b) => a * b, 1);
            else if (formula.operacao === 'divisao') res = valores[1] !== 0 ? valores[0] / valores[1] : 0;
            if (formula.multiplicador) res *= formula.multiplicador;
            return res;
        }

        async processBiTreeWithCalculated() {
            this.processBiTree();
            const nosCalc = await this.loadNosCalculados();
            if (nosCalc.length > 0) {
                const valoresAgregados = this.agregarValoresPorTipo();
                const meses = this.biState.columnsOrder;
                nosCalc.forEach(noCalc => {
                    if (!noCalc.formula) return;
                    const valores = {};
                    meses.forEach(mes => {
                        valores[mes] = this.calcularValorNo(noCalc.formula, mes, valoresAgregados);
                    });

                    const chaveMemoria = `no_virtual_${noCalc.id}`;
                    if (!valoresAgregados[chaveMemoria]) valoresAgregados[chaveMemoria] = {};
                    meses.forEach(mes => valoresAgregados[chaveMemoria][mes] = valores[mes]);

                    let textoTooltip = noCalc.formula_descricao;
                    if (!textoTooltip && noCalc.formula) {
                        const ops = noCalc.formula.operandos || [];
                        const nomesOps = ops.map(o => o.label || o.id).join(', ');
                        const opMap = { 'soma': 'Soma (+)', 'subtracao': 'Subtração (-)', 'multiplicacao': 'Multiplicação (×)', 'divisao': 'Divisão (÷)' };
                        textoTooltip = `Fórmula: ${opMap[noCalc.formula.operacao] || noCalc.formula.operacao}\nEnvolvendo: ${nomesOps}`;
                    }

                    const rowBackend = this.biRawData.find(r => (r.Root_Virtual_Id == noCalc.id) || (r.Titulo_Conta === noCalc.nome));
                    let ordemCorreta = 50;
                    if (rowBackend && rowBackend.ordem_prioridade !== null) ordemCorreta = rowBackend.ordem_prioridade;
                    else if (noCalc.ordem !== null && noCalc.ordem !== undefined) ordemCorreta = noCalc.ordem;
                    
                    const nodeCalc = {
                        id: `calc_${noCalc.id}`,
                        label: `${noCalc.nome}`, 
                        rawLabel: noCalc.nome,     
                        type: 'calculated',
                        children: [],
                        values: valores,
                        isVisible: true,
                        isExpanded: false,
                        formulaDescricao: textoTooltip,
                        estiloCss: noCalc.estilo_css,
                        tipoExibicao: noCalc.tipo_exibicao,
                        ordem: ordemCorreta
                    };
                    this.biTreeData.push(nodeCalc);
                });
            }

            const nomesCalculados = new Set(this.biTreeData.filter(n => n.type === 'calculated').map(n => (n.rawLabel || n.label.replace('📊 ', '')).toUpperCase().trim()));
            this.biTreeData = this.biTreeData.filter(node => {
                if (node.type === 'root') {
                    const labelPadrao = node.label.toUpperCase().trim();
                    if (nomesCalculados.has(labelPadrao)) return false; 
                }
                return true;
            });
            this.biTreeData.sort((a, b) => {
                const ordA = (a.ordem !== undefined && a.ordem !== null) ? a.ordem : 9999;
                const ordB = (b.ordem !== undefined && b.ordem !== null) ? b.ordem : 9999;
                return ordA - ordB;
            });
        }

        agregarValoresPorTipo() {
            const agregados = {};
            const meses = this.biState.columnsOrder;
            this.biTreeData.forEach(rootNode => {
                const rawId = rootNode.id.replace('T_', '').replace('CC_', '');
                const chave = `tipo_cc_${rawId}`;
                if (!agregados[chave]) agregados[chave] = {};
                if (rootNode.virtualId) {
                    const chaveVirt = `no_virtual_${rootNode.virtualId}`;
                    if (!agregados[chaveVirt]) agregados[chaveVirt] = {};
                }
                meses.forEach(m => {
                    const val = rootNode.values[m] || 0;
                    if(agregados[chave]) agregados[chave][m] = (agregados[chave][m]||0) + val;
                    if (rootNode.virtualId) agregados[`no_virtual_${rootNode.virtualId}`][m] = (agregados[`no_virtual_${rootNode.virtualId}`][m]||0) + val;
                });
            });
            return agregados;
        }

        downloadRazaoFull() {
            // 1. Pega o estado atual da busca e do botão de ajustes
            const searchTerm = encodeURIComponent(this.razaoSearch || '');
            const viewType = this.razaoViewType; // Já alterna entre 'original' e 'adjusted' pelo switch
            
            // 2. Pega a rota segura do HTML
            const baseUrl = API_ROUTES.getRazaoDownload;

            if (!baseUrl) {
                alert("Erro de configuração: Rota de download não encontrada.");
                return;
            }

            // 3. Monta URL final
            const finalUrl = `${baseUrl}?search=${searchTerm}&view_type=${viewType}`;

            // 4. Feedback visual no botão (opcional)
            const btnIcon = document.getElementById('iconDownload');
            if(btnIcon) btnIcon.className = "fas fa-spinner fa-spin";

            // 5. Inicia Download
            window.location.href = finalUrl;

            // Remove spinner após 3s
            setTimeout(() => {
                if(btnIcon) btnIcon.className = "fas fa-file-excel";
            }, 3000);
        }

    }

    window.relatorioSystem = new RelatorioSystem();
    window.fecharModal = function() { if (window.relatorioSystem && window.relatorioSystem.modal) window.relatorioSystem.modal.close(); };
}