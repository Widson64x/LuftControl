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

        // --- CORREÇÃO: ADICIONADA A FUNÇÃO QUE FALTAVA ---
        toggleRazaoView(isChecked) {
            // Atualiza o estado
            this.razaoViewType = isChecked ? 'adjusted' : 'original';
            // Recarrega o relatório na página 1
            this.loadRazaoReport(1);
        }

        renderRazaoView(metaData, summaryData) {
            // 1. Resumo HTML (Cards superiores)
            const summaryHtml = `
                <div class="summary-grid mb-3">
                    <div class="summary-card">
                        <div class="summary-label">Total Registros</div>
                        <div class="summary-value">${FormatUtils.formatNumber(summaryData.total_registros)}</div>
                    </div>
                </div>`;

            // 2. Barra de Controle
            const controlsHtml = `
                <div class="d-flex justify-content-between align-items-center mb-2 p-2 bg-tertiary rounded flex-wrap gap-2">
                    <div class="d-flex align-items-center gap-3" style="flex: 1;">
                        <div class="input-group" style="max-width: 300px;">
                            <i class="input-group-icon fas fa-search"></i>
                            <input type="text" id="razaoSearchInput" class="form-control" 
                                placeholder="Busca Global (Server-side)..." value="${this.razaoSearch}">
                        </div>
                        
                        <div class="form-check form-switch d-flex align-items-center gap-2 m-0 cursor-pointer">
                            <input class="form-check-input cursor-pointer" type="checkbox" role="switch" id="chkViewTypeRazao" 
                                ${this.razaoViewType === 'adjusted' ? 'checked' : ''}
                                onchange="relatorioSystem.toggleRazaoView(this.checked)">
                            <label class="form-check-label text-white cursor-pointer select-none" for="chkViewTypeRazao">
                                Modo Ajustado (Inclusões/Edições)
                            </label>
                        </div>
                    </div>

                    <div class="d-flex align-items-center gap-2">
                        <button class="btn btn-sm btn-success" onclick="relatorioSystem.downloadRazaoFull()" title="Excel">
                            <i class="fas fa-file-excel"></i> Exportar
                        </button>
                        <div class="separator-vertical mx-2"></div>
                        <small class="text-secondary me-2">Página ${this.razaoPage} de ${this.razaoTotalPages}</small>
                        <div class="btn-group">
                            <button class="btn btn-sm btn-secondary" onclick="relatorioSystem.loadRazaoReport(${this.razaoPage - 1})" ${this.razaoPage <= 1 ? 'disabled' : ''}><i class="fas fa-chevron-left"></i></button>
                            <button class="btn btn-sm btn-secondary" onclick="relatorioSystem.loadRazaoReport(${this.razaoPage + 1})" ${this.razaoPage >= this.razaoTotalPages ? 'disabled' : ''}><i class="fas fa-chevron-right"></i></button>
                        </div>
                    </div>
                </div>
                
                <div id="razaoTabulator" style="height: 60vh; width: 100%; border-radius: 8px; overflow: hidden;"></div>
                <div class="text-end mt-1"><small class="text-muted text-xs">* Filtros nas colunas aplicam-se à página atual.</small></div>
            `;

            // 3. Renderiza o Layout Básico
            this.modal.setContent(`<div style="padding: 1.5rem; height: 100%; display: flex; flex-direction: column;">${summaryHtml}${controlsHtml}</div>`);

            // 4. Configuração do Evento de Busca Global
            const input = document.getElementById('razaoSearchInput');
            if (input) {
                input.focus();
                // Coloca o cursor no final do texto
                const val = input.value;
                input.value = '';
                input.value = val;
                
                input.addEventListener('input', (e) => {
                    clearTimeout(this.razaoSearchTimer);
                    this.razaoSearchTimer = setTimeout(() => {
                        this.razaoSearch = e.target.value;
                        this.loadRazaoReport(1);
                    }, 600);
                });
            }

            // 5. Inicialização do Tabulator
            this.initTabulator();
        }

        initTabulator() {
            // Definição de Formatadores
            const moneyFormatter = (cell) => {
                const val = cell.getValue();
                const color = val < 0 ? "text-danger" : (val > 0 ? "text-success" : "text-muted");
                return `<span class="${color}">${FormatUtils.formatCurrency(val)}</span>`;
            };

            const origemFormatter = (cell) => {
                const val = cell.getValue();
                const row = cell.getRow().getData();
                if (row.is_ajustado) {
                    // Verifica se é Inclusão ou Edição para dar dica visual
                    const isNew = val.includes('(NOVO)');
                    const icon = isNew ? 'fa-plus' : 'fa-pen';
                    const colorClass = isNew ? 'badge-success' : 'badge-warning';
                    return `<span class="badge ${colorClass} text-xs"><i class="fas ${icon}"></i> ${val}</span>`;
                }
                return `<span class="badge badge-secondary text-xs">${val}</span>`;
            };

            // Instancia Tabulator
            this.table = new Tabulator("#razaoTabulator", {
                data: this.razaoData,
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
                    
                    // Colunas Novas
                    {title:"CC", field:"centro_custo", width: 100, headerFilter:"input"},
                    {title:"Filial", field:"filial", width: 80, headerFilter:"input"},
                    {title:"Item", field:"item", width: 80, headerFilter:"input"},

                    // Valores
                    {title:"Débito", field:"debito", width: 120, hozAlign:"right", formatter: moneyFormatter, bottomCalc:"sum", bottomCalcFormatter: moneyFormatter},
                    {title:"Crédito", field:"credito", width: 120, hozAlign:"right", formatter: moneyFormatter, bottomCalc:"sum", bottomCalcFormatter: moneyFormatter},
                    {title:"Saldo", field:"saldo", width: 120, hozAlign:"right", formatter: moneyFormatter, bottomCalc:"sum", bottomCalcFormatter: moneyFormatter},
                ],
                rowFormatter: function(row){
                    const data = row.getData();
                    if(data.is_ajustado){
                        const origem = data.origem || "";
                        if (origem.includes("(NOVO)")) {
                             row.getElement().style.backgroundColor = "rgba(40, 167, 69, 0.1)"; // Verde suave para novos
                        } else {
                             row.getElement().style.backgroundColor = "rgba(255, 193, 7, 0.1)"; // Amarelo suave para edições
                        }
                    }
                },
            });
        }

        // ====================================================================
        // --- MÓDULO 2: RENTABILIDADE (BI) ---
        // ====================================================================

        toggleScaleMode() {
            if (this.biIsLoading) return;
            this.biState.scaleMode = (this.biState.scaleMode === 'dre') ? 'normal' : 'dre';
            this.loadRentabilidadeReport(this.biState.origemFilter);
        }

        formatDREValue(value) {
            if (value === 0 || value === null) return '-';
            const isNegative = value < 0;
            const absValue = Math.abs(value);
            const formatted = absValue.toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
            return isNegative ? `(${formatted})` : formatted;
        }

        async loadRentabilidadeReport(origem = null) {
            if (!this.modal) this.modal = new ModalSystem('modalRelatorio');
            if (origem !== null) this.biState.origemFilter = origem;
            
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
                    iconHtml = `<i class="fas fa-caret-${isExpanded ? 'down' : 'right'} me-2 toggle-icon" onclick="event.stopPropagation(); relatorioSystem.toggleNode('${node.id}')" style="width:10px; cursor: pointer; color: var(--text-tertiary);"></i>`;
                    iconHtml += `<i class="fas ${iconClass} me-2" style="${iconStyle}"></i>`;
                } else {
                    iconHtml = `<i class="fas ${iconClass} me-2" style="margin-left: 18px; ${iconStyle}"></i>`;
                }

                let labelStyle = ''; 
                const customStyle = node.estiloCss ? `style="${node.estiloCss}"` : '';
                
                const cellsHtml = cols.map(c => {
                    const val = node.values[c];
                    let colorClass = '';
                    if (val < 0) colorClass = 'text-danger'; 
                    else if (val === 0) colorClass = 'text-muted';
                    
                    let displayVal = '-';
                    if (val !== 0) {
                        if (this.biState.scaleMode === 'dre') displayVal = this.formatDREValue(val);
                        else displayVal = FormatUtils.formatNumber(val);
                    }
                    if (node.tipoExibicao === 'percentual' && val !== 0) displayVal = val.toFixed(2) + '%';
                    
                    const weight = (node.type === 'root' || node.type === 'calculated') ? 'font-weight: 600;' : '';
                    return `<td class="text-end font-mono ${colorClass}" style="${weight}">${displayVal}</td>`;
                }).join('');

                const isMatch = this.biState.searchMatches.includes(node.id);
                const searchClass = isMatch ? 'search-match' : '';

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
                
                const isVisible = matchesCols || hasVisibleChildren;
                node.isVisible = isVisible;
                if (isVisible && hasColFilters) this.biState.expanded.add(node.id); 
                return isVisible;
            };
            this.biTreeData.forEach(node => checkVisibility(node));
        }
        handleBiGlobalSearch(val) { 
            this.biState.globalSearch = val; 
            if (!val) {
                this.biState.searchMatches = [];
                this.biState.searchCurrentIndex = -1;
                this.renderBiTable();
                return;
            }
            clearTimeout(this.biDebounceTimer); 
            this.biDebounceTimer = setTimeout(() => { this.performSearchTraversal(); }, 400); 
        }

        performSearchTraversal() {
            const term = this.biState.globalSearch.toLowerCase();
            this.biState.searchMatches = [];
            this.biState.searchCurrentIndex = -1;
            if (!term) return;

            const findAndExpand = (nodes, parentIds = []) => {
                nodes.forEach(node => {
                    const match = node.label.toLowerCase().includes(term);
                    if (match) {
                        this.biState.searchMatches.push(node.id);
                        parentIds.forEach(pid => this.biState.expanded.add(pid));
                    }
                    if (node.children && node.children.length > 0) findAndExpand(node.children, [...parentIds, node.id]);
                });
            };
            findAndExpand(this.biTreeData);
            if (this.biState.searchMatches.length > 0) {
                this.renderBiTable();
                setTimeout(() => this.navigateSearchNext(), 100);
            } else {
                this.renderBiTable();
            }
        }

        navigateSearchNext() {
            if (this.biState.searchMatches.length === 0) return;
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
            if (row) row.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }

        updateSearchHighlights() {
            document.querySelectorAll('.search-current-match').forEach(el => el.classList.remove('search-current-match'));
            const currentId = this.biState.searchMatches[this.biState.searchCurrentIndex];
            const row = document.getElementById(`row_${currentId}`);
            if (row) row.classList.add('search-current-match');
        }

        handleBiColFilter(col, val) { if (!val) delete this.biState.filters[col]; else this.biState.filters[col] = val; this.debounceRender(); }
        debounceRender() { clearTimeout(this.biDebounceTimer); this.biDebounceTimer = setTimeout(() => { this.applyBiFilters(); this.renderBiTable(); }, 400); }
        toggleNode(id) { if (this.biState.expanded.has(id)) this.biState.expanded.delete(id); else this.biState.expanded.add(id); this.renderBiTable(); }
        toggleAllNodes(expand) { const recurse = (nodes) => { nodes.forEach(n => { if (expand) this.biState.expanded.add(n.id); else this.biState.expanded.delete(n.id); if (n.children) recurse(n.children); }); }; recurse(this.biTreeData); this.renderBiTable(); }
        openColumnManager() {
            const allCols = this.biState.columnsOrder;
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
                                <input type="checkbox" class="column-checkbox" value="${c}" ${isVisible ? 'checked' : ''} onchange="relatorioSystem.handleColumnToggle(this, '${c}')">
                                <span>${c}</span>
                            </label>`;
                        }).join('')}
                    </div>
                    <div class="mt-4 text-end border-top border-primary pt-3">
                        <button class="btn btn-primary-custom" style="width: auto; padding: 8px 24px;" onclick="document.querySelector('.modal-backdrop').remove(); relatorioSystem.renderBiTable()">
                            <i class="fas fa-check"></i> Aplicar Alterações
                        </button>
                    </div>
                </div>`;
            const colModal = document.createElement('div'); 
            colModal.className = 'modal-backdrop active'; 
            colModal.innerHTML = `<div class="modal-window" style="max-width: 600px;">${modalHtml}</div>`;
            colModal.onclick = (e) => { if(e.target === colModal) { colModal.remove(); this.renderBiTable(); } }; 
            document.body.appendChild(colModal);
        }

        handleColumnToggle(checkbox, col) {
            if (checkbox.checked) { this.biState.hiddenCols.delete(col); checkbox.closest('.column-option').classList.add('selected'); }
            else { this.biState.hiddenCols.add(col); checkbox.closest('.column-option').classList.remove('selected'); }
            this.updateSelectAllBtnState();
        }

        toggleAllColumns(btn) {
            const checkboxes = document.querySelectorAll('.column-grid input[type="checkbox"]');
            const isCurrentlyAllChecked = btn.querySelector('i').classList.contains('fa-check-square');
            const newState = !isCurrentlyAllChecked;
            checkboxes.forEach(chk => {
                chk.checked = newState;
                const col = chk.value;
                const parent = chk.closest('.column-option');
                if (newState) { this.biState.hiddenCols.delete(col); parent.classList.add('selected'); } 
                else { this.biState.hiddenCols.add(col); parent.classList.remove('selected'); }
            });
            this.updateSelectAllBtnState();
        }

        updateSelectAllBtnState() {
            const btn = document.querySelector('.column-manager-header button');
            if(!btn) return;
            const allCols = this.biState.columnsOrder;
            const allVisible = allCols.every(c => !this.biState.hiddenCols.has(c));
            if(allVisible) btn.innerHTML = '<i class="fas fa-check-square"></i> Desmarcar Todos';
            else btn.innerHTML = '<i class="fas fa-square"></i> Selecionar Todos';
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
            const searchTerm = encodeURIComponent(this.razaoSearch || '');
            const viewType = this.razaoViewType; 
            const baseUrl = API_ROUTES.getRazaoDownload;
            if (!baseUrl) { alert("Erro de configuração: Rota de download não encontrada."); return; }
            const finalUrl = `${baseUrl}?search=${searchTerm}&view_type=${viewType}`;
            const btnIcon = document.getElementById('iconDownload');
            if(btnIcon) btnIcon.className = "fas fa-spinner fa-spin";
            window.location.href = finalUrl;
            setTimeout(() => { if(btnIcon) btnIcon.className = "fas fa-file-excel"; }, 3000);
        }
    }

    window.relatorioSystem = new RelatorioSystem();
    window.fecharModal = function() { if (window.relatorioSystem && window.relatorioSystem.modal) window.relatorioSystem.modal.close(); };
}