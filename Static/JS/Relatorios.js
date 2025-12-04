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
            this.razaoSummary = null; // Armazena totais globais
            this.razaoPage = 1;
            this.razaoTotalPages = 1;
            this.razaoSearch = '';
            this.razaoSearchTimer = null;
            this.razaoViewType = 'original'; // 'original' ou 'adjusted'

            // Estado do BI (DRE)
            this.biRawData = [];      
            this.biTreeData = [];     
            this.biState = {
                expanded: new Set(['root']), 
                hiddenCols: new Set(),       
                filters: {},                 
                globalSearch: '',            
                sort: { col: null, dir: 'asc' }, 
                columnsOrder: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez', 'Total_Ano'],            
                origemFilter: 'Consolidado',  
                viewMode: 'TIPO' // 'TIPO' ou 'CC'
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

            // Abre modal apenas se for primeira carga
            if (page === 1 && !document.querySelector('#razaoTableContainer')) {
                this.modal.open(title);
                this.modal.showLoading('Carregando lançamentos contábeis...');
            }

            try {
                const urlData = (API_ROUTES?.getRazaoData) || '/Reports/RelatorioRazao/Dados'; 
                const urlSummary = (API_ROUTES?.getRazaoResumo) || '/Reports/RelatorioRazao/Resumo';

                const term = encodeURIComponent(this.razaoSearch);
                const viewType = this.razaoViewType;
                
                // Busca Dados da Tabela + Resumo Global em paralelo
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
            // Cards de Resumo (Dados vindos do Backend agora)
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

            // Linhas da Tabela
            const rows = this.razaoData.map(r => {
                // Se for ajustado, aplica estilo de destaque
                const styleClass = r.is_ajustado ? 'background-color: #fff8e1;' : '';
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

            // Toolbar com Toggle Switch
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
            
            // Reatacha listeners
            const input = document.getElementById('razaoSearchInput');
            if (input) {
                input.focus();
                // input.setSelectionRange(input.value.length, input.value.length); // Mantém cursor no final
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
            // Recarrega na página 1 ao mudar o modo de visualização
            this.loadRazaoReport(1);
        }

        // ====================================================================
        // --- MÓDULO 2: RENTABILIDADE (BI) ---
        // ====================================================================

        async loadRentabilidadeReport(origem = null) {
            if (!this.modal) this.modal = new ModalSystem('modalRelatorio');
            
            if (origem !== null) this.biState.origemFilter = origem;
            else { // Reset completo se chamado sem params
                this.biState.filters = {};
                this.biState.globalSearch = '';
                this.biState.viewMode = 'TIPO'; 
            }
            
            const viewTitle = this.biState.viewMode === 'CC' ? 'por Centro de Custo' : 'por Tipo';
            this.modal.open(`<i class="fas fa-cubes"></i> Análise Gerencial (${viewTitle})`, '');
            this.modal.showLoading('Construindo cubo de dados...');

            try {
                // Roteamento inteligente
                let urlBase;
                if (this.biState.viewMode === 'CC') {
                    urlBase = (API_ROUTES?.getRentabilidadeDataCC) || '/Reports/RelatorioRazao/RentabilidadePorCC';
                } else {
                    urlBase = (API_ROUTES?.getRentabilidadeData) || '/Reports/RelatorioRazao/Rentabilidade';
                }

                const origemParam = encodeURIComponent(this.biState.origemFilter);
                const rawData = await APIUtils.get(`${urlBase}?origem=${origemParam}`);
                
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
                const rawData = await APIUtils.get(`${urlBase}?origem=${origemParam}`);
                
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
                console.error(error);
                if(container) container.innerHTML = `<div class="p-3 text-danger">Erro: ${error.message}</div>`;
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

        // --- CONSTRUÇÃO DA ÁRVORE (CORE) ---
        processBiTree() {
            const root = [];
            const map = {}; 
            const meses = this.biState.columnsOrder;

            // Função helper para criar nós
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

                // --- 1. RAIZ: TIPO DE CC (Sempre existe) ---
                const tipoId = `T_${row.Tipo_CC}`;
                const tipoNode = getOrCreateNode(tipoId, row.Tipo_CC, 'root', root, ordemVal);
                if (row.Root_Virtual_Id) tipoNode.virtualId = row.Root_Virtual_Id;
                
                if ((row.ordem_prioridade !== null || row.Ordem) && tipoNode.ordem >= 1000) {
                    tipoNode.ordem = (row.ordem_prioridade !== null) ? row.ordem_prioridade : row.Ordem;
                }
                sumValues(tipoNode, row);

                let currentNode = tipoNode;
                let currentId = tipoId;

                // --- 2. NÍVEL CENTRO DE CUSTO (Apenas se viewMode == 'CC') ---
                if (this.biState.viewMode === 'CC' && row.Nome_CC) {
                    // Cria ID seguro para o CC
                    const safeCCName = String(row.Nome_CC).replace(/[^a-zA-Z0-9]/g, '');
                    currentId += `_CC_${safeCCName}`;
                    
                    // O nó do CC é criado como filho do Tipo
                    const ccNode = getOrCreateNode(currentId, row.Nome_CC, 'group', currentNode.children);
                    sumValues(ccNode, row);
                    currentNode = ccNode;
                }

                // --- 3. SUBGRUPOS (Hierarquia Padrão) ---
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

                // --- 4. CONTA (Folha) ---
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

            const toolbar = `
                <div class="bi-toolbar d-flex justify-content-between align-items-center p-3 border-bottom border-primary bg-tertiary">
                    <div class="d-flex gap-2 align-items-center flex-wrap">
                        ${this.renderOrigemFilter()}
                        
                        <button class="btn btn-sm ${btnClass}" onclick="relatorioSystem.toggleViewMode()" title="Alternar Agrupamento">
                            <i class="fas ${btnIcon}"></i> ${btnText}
                        </button>

                        <div class="separator-vertical mx-2" style="height: 20px; border-left: 1px solid var(--border-secondary);"></div>
                        <div class="input-group input-group-sm" style="width: 200px;">
                            <i class="input-group-icon fas fa-search"></i>
                            <input type="text" id="biGlobalSearch" class="form-control" 
                                   placeholder="Filtrar estrutura..." value="${this.biState.globalSearch}"
                                   oninput="relatorioSystem.handleBiGlobalSearch(this.value)">
                        </div>
                    </div>
                    <div class="d-flex gap-2 align-items-center">
                        <button class="btn btn-sm btn-outline" onclick="relatorioSystem.toggleAllNodes(true)" title="Expandir Tudo"><i class="fas fa-expand-arrows-alt"></i></button>
                        <button class="btn btn-sm btn-outline" onclick="relatorioSystem.toggleAllNodes(false)" title="Recolher Tudo"><i class="fas fa-compress-arrows-alt"></i></button>
                        <button class="btn btn-sm btn-outline" onclick="relatorioSystem.openColumnManager()" title="Colunas"><i class="fas fa-columns"></i></button>
                        <div class="separator-vertical mx-1" style="height: 20px; border-left: 1px solid var(--border-secondary);"></div>
                        <button class="btn btn-sm btn-success" onclick="relatorioSystem.exportBiToCsv()"><i class="fas fa-file-csv"></i> Exportar</button>
                    </div>
                </div>`;

            const gridContainer = `<div id="biGridContainer" class="table-fixed-container" style="flex: 1; overflow: auto; background: var(--bg-secondary);"></div>`;
            const footer = `
                <div class="bi-footer p-2 bg-tertiary border-top border-primary d-flex justify-content-between align-items-center">
                    <span class="text-secondary text-xs">Fonte: <strong>${this.biState.origemFilter}</strong> | Modo: <strong>${this.biState.viewMode}</strong></span>
                    <span class="text-muted text-xs">Atualizado: ${new Date().toLocaleTimeString('pt-BR')}</span>
                </div>`;

            this.modal.setContent(`<div style="display: flex; flex-direction: column; height: 100%;">${toolbar}${gridContainer}${footer}</div>`);
            this.renderBiTable();
        }

        renderBiTable() {
            const container = document.getElementById('biGridContainer');
            if (!container) return;

            const cols = this.biState.columnsOrder.filter(c => !this.biState.hiddenCols.has(c));
            const rootHeaderName = this.biState.viewMode === 'CC' ? 'Tipo / Centro de Custo / Estrutura' : 'Tipo / Estrutura DRE';

            let headerHtml = `
                <thead style="position: sticky; top: 0; z-index: 20;">
                    <tr>
                        <th style="min-width: 350px; left: 0; position: sticky; z-index: 30;" class="bg-tertiary border-end border-secondary">
                            ${rootHeaderName}
                        </th>
                        ${cols.map(c => `
                            <th class="text-end bg-tertiary border-end border-secondary" style="min-width: 110px;">
                                <div class="d-flex flex-column">
                                    <span class="mb-1 cursor-pointer" onclick="relatorioSystem.sortBiBy('${c}')">${c} <i class="fas fa-sort text-muted text-xs"></i></span>
                                    <input type="text" class="form-control form-control-sm p-1 text-end text-xs bg-dark border-secondary" 
                                           placeholder="Filtro..." value="${this.biState.filters[c] || ''}"
                                           oninput="relatorioSystem.handleBiColFilter('${c}', this.value)">
                                </div>
                            </th>
                        `).join('')}
                    </tr>
                </thead>`;

            let bodyRows = '';
            
            const renderNode = (node, level) => {
                if (!node.isVisible) return;
                const padding = level * 20 + 10;
                const isGroup = node.children && node.children.length > 0;
                const isExpanded = this.biState.expanded.has(node.id);
                
                let icon = '';
                if (isGroup) {
                    icon = `<i class="fas fa-chevron-${isExpanded ? 'down' : 'right'} me-2 toggle-icon" onclick="event.stopPropagation(); relatorioSystem.toggleNode('${node.id}')"></i>`;
                } else {
                    icon = (node.type === 'calculated') 
                        ? `<i class="fas fa-calculator me-2 text-info" style="margin-left: 4px; cursor: help;" title="${node.formulaDescricao || ''}"></i>`
                        : `<i class="far fa-file-alt me-2 opacity-50" style="margin-left: 4px;"></i>`;
                }

                let rowClass = 'bi-row-account';
                if (node.type === 'root') rowClass = 'bi-row-root'; 
                else if (node.type === 'group') rowClass = 'bi-row-group'; 
                else if (node.type === 'calculated') rowClass = 'bi-row-calculated';

                const customStyle = node.estiloCss ? `style="${node.estiloCss}"` : '';
                const cellsHtml = cols.map(c => {
                    const val = node.values[c];
                    let colorClass = val < 0 ? 'text-danger fw-bold' : (val > 0 ? 'text-success fw-bold' : 'text-muted');
                    let displayVal = val !== 0 ? FormatUtils.formatNumber(val) : '-';
                    if (node.tipoExibicao === 'percentual' && val !== 0) displayVal = val.toFixed(2) + '%';
                    return `<td class="text-end font-mono ${colorClass}">${displayVal}</td>`;
                }).join('');

                bodyRows += `<tr class="${rowClass}" ${customStyle}>
                        <td style="padding-left: ${padding}px;">
                            <div class="d-flex align-items-center cell-label">
                                ${icon}<span class="text-truncate" title="${node.formulaDescricao || ''}">${node.label}</span>
                            </div>
                        </td>${cellsHtml}</tr>`;

                if (isGroup && isExpanded) node.children.forEach(child => renderNode(child, level + 1));
            };

            this.biTreeData.forEach(node => renderNode(node, 0));
            container.innerHTML = `<table class="table-modern w-100" style="border-collapse: separate; border-spacing: 0;">${headerHtml}<tbody>${bodyRows}</tbody></table>`;
        }

        // --- MÉTODOS AUXILIARES ---
        applyBiFilters() {
            const globalTerm = this.biState.globalSearch.toLowerCase();
            const colFilters = this.biState.filters;
            const hasColFilters = Object.keys(colFilters).length > 0;

            const checkVisibility = (node) => {
                let matchesGlobal = !globalTerm || node.label.toLowerCase().includes(globalTerm);
                let matchesCols = true;
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
                const isVisible = (matchesGlobal && matchesCols) || hasVisibleChildren;
                node.isVisible = isVisible;
                if (isVisible && (globalTerm || hasColFilters)) this.biState.expanded.add(node.id); 
                return isVisible;
            };
            this.biTreeData.forEach(node => checkVisibility(node));
        }

        handleBiGlobalSearch(val) { this.biState.globalSearch = val; this.debounceRender(); }
        handleBiColFilter(col, val) { if (!val) delete this.biState.filters[col]; else this.biState.filters[col] = val; this.debounceRender(); }
        debounceRender() { clearTimeout(this.biDebounceTimer); this.biDebounceTimer = setTimeout(() => { this.applyBiFilters(); this.renderBiTable(); }, 400); }
        toggleNode(id) { if (this.biState.expanded.has(id)) this.biState.expanded.delete(id); else this.biState.expanded.add(id); this.renderBiTable(); }
        toggleAllNodes(expand) { const recurse = (nodes) => { nodes.forEach(n => { if (expand) this.biState.expanded.add(n.id); else this.biState.expanded.delete(n.id); if (n.children) recurse(n.children); }); }; recurse(this.biTreeData); this.renderBiTable(); }
        openColumnManager() { 
            const allCols = this.biState.columnsOrder;
            const checksHtml = allCols.map(c => `<div class="col-6 mb-2"><label class="d-flex align-items-center cursor-pointer"><input type="checkbox" ${!this.biState.hiddenCols.has(c) ? 'checked' : ''} onchange="relatorioSystem.toggleBiColumn('${c}')"><span class="ms-2 text-white">${c}</span></label></div>`).join('');
            const modalHtml = `<div class="p-3"><h5>Gerenciar Colunas Visíveis</h5><div class="row mt-3">${checksHtml}</div><div class="mt-3 text-end"><button class="btn btn-sm btn-primary" onclick="this.closest('.modal-backdrop').remove(); relatorioSystem.renderBiTable()">Aplicar</button></div></div>`;
            const colModal = document.createElement('div'); colModal.className = 'modal-backdrop active'; colModal.innerHTML = `<div class="modal-window modal-sm"><div class="modal-body">${modalHtml}</div></div>`;
            colModal.onclick = (e) => { if(e.target === colModal) colModal.remove(); }; document.body.appendChild(colModal);
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
        
        // --- CÁLCULO DE NÓS (Mantido igual) ---
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

                    // Correção Cascata
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
                        label: `📊 ${noCalc.nome}`, 
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
    }

    window.relatorioSystem = new RelatorioSystem();
    window.fecharModal = function() { if (window.relatorioSystem && window.relatorioSystem.modal) window.relatorioSystem.modal.close(); };
}