// ============================================================================
// T-Controllership - SISTEMA DE RELATÓRIOS FINANCEIROS & BI NATIVO
// Arquivo: Static/JS/Relatorios.js
// Descrição: Gerencia Relatório de Razão e o Motor de BI (Rentabilidade)
// ============================================================================

if (typeof window.relatorioSystemInitialized === 'undefined') {
    window.relatorioSystemInitialized = true;

    class RelatorioSystem {
        constructor() {
            this.modal = null;
            
            // --- ESTADO: RELATÓRIO DE RAZÃO ---
            this.razaoData = null;
            this.razaoPage = 1;
            this.razaoTotalPages = 1;
            this.razaoSearch = '';
            this.razaoSearchTimer = null;

            // --- ESTADO: BI RENTABILIDADE ---
            this.biRawData = [];      // Dados originais do banco
            this.biTreeData = [];     // Dados estruturados em árvore
            this.biState = {
                expanded: new Set(['root']), // IDs dos nós expandidos
                hiddenCols: new Set(),       // Colunas ocultas
                filters: {},                 // Filtros por coluna { coluna: valor }
                globalSearch: '',            // Busca global
                sort: { col: null, dir: 'asc' }, // Ordenação
                columnsOrder: [],            // Ordem das colunas (meses)
                origemFilter: 'Consolidado'  // Filtro de origem (FARMA, FARMADIST, Consolidado)
            };
            this.biDebounceTimer = null;
            this.biIsLoading = false;        // Flag de loading

            // Cache de nós calculados
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
            this.modal = new ModalSystem('modalRelatorio');
            console.log('✅ RelatorioSystem Nativo Inicializado');
        }

        // =========================================================================
        // MÓDULO 1: RELATÓRIO DE RAZÃO (Paginado Server-Side)
        // =========================================================================

        async loadRazaoReport(page = 1) {
            if (!this.modal) this.modal = new ModalSystem('modalRelatorio');
            
            this.razaoPage = page;
            const title = this.razaoSearch 
                ? `📈 Razão Contábil - Buscando: "${this.razaoSearch}"` 
                : '📈 Relatório de Razão (Base Completa)';

            // Se for a primeira carga ou busca, abre o modal e mostra loading
            if (page === 1 && !document.querySelector('#razaoTableContainer')) {
                this.modal.open(title);
                this.modal.showLoading('Carregando lançamentos contábeis...');
            }

            try {
                let urlBase = '/Reports/RelatorioRazao/Dados'; 
                if (typeof API_ROUTES !== 'undefined' && API_ROUTES.getRazaoData) {
                    urlBase = API_ROUTES.getRazaoData;
                }

                const term = encodeURIComponent(this.razaoSearch);
                const fullUrl = `${urlBase}?page=${page}&search=${term}`;

                const response = await APIUtils.get(fullUrl);
                
                this.razaoData = response.dados || [];
                this.razaoTotalPages = response.total_paginas || 1;

                this.renderRazaoView(response);
            } catch (error) {
                console.error(error);
                this.modal.showError(`Erro ao carregar Razão: ${error.message}`);
            }
        }

        renderRazaoView(metaData) {
            const totals = this.razaoData.reduce((acc, item) => ({
                deb: acc.deb + (item.debito || 0),
                cred: acc.cred + (item.credito || 0),
                saldo: acc.saldo + (item.saldo || 0)
            }), { deb: 0, cred: 0, saldo: 0 });

            const summaryHtml = `
                <div class="summary-grid mb-3">
                    <div class="summary-card">
                        <div class="summary-label">Total Registros</div>
                        <div class="summary-value">${FormatUtils.formatNumber(metaData.total_registros)}</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-label">Débito (Página)</div>
                        <div class="summary-value text-danger">${FormatUtils.formatCurrency(totals.deb)}</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-label">Crédito (Página)</div>
                        <div class="summary-value text-success">${FormatUtils.formatCurrency(totals.cred)}</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-label">Saldo (Página)</div>
                        <div class="summary-value ${totals.saldo >= 0 ? 'text-success' : 'text-danger'} font-bold">
                            ${FormatUtils.formatCurrency(totals.saldo)}
                        </div>
                    </div>
                </div>`;

            const controlsHtml = `
                <div class="d-flex justify-content-between align-items-center mb-3 p-2 bg-tertiary rounded">
                    <div class="input-group" style="max-width: 400px;">
                        <i class="input-group-icon fas fa-search"></i>
                        <input type="text" id="razaoSearchInput" class="form-control" 
                               placeholder="Filtrar por conta, histórico, valor..." 
                               value="${this.razaoSearch}" autofocus>
                    </div>
                    <div class="d-flex align-items-center gap-2">
                        <small class="text-secondary me-2">Página ${this.razaoPage} de ${this.razaoTotalPages}</small>
                        <div class="btn-group">
                            <button class="btn btn-sm btn-secondary" 
                                    onclick="relatorioSystem.loadRazaoReport(${this.razaoPage - 1})" 
                                    ${this.razaoPage <= 1 ? 'disabled' : ''}>
                                <i class="fas fa-chevron-left"></i>
                            </button>
                            <button class="btn btn-sm btn-secondary" 
                                    onclick="relatorioSystem.loadRazaoReport(${this.razaoPage + 1})" 
                                    ${this.razaoPage >= this.razaoTotalPages ? 'disabled' : ''}>
                                <i class="fas fa-chevron-right"></i>
                            </button>
                        </div>
                    </div>
                </div>`;

            const rows = this.razaoData.map(r => `
                <tr>
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
                    <td><span class="badge badge-secondary">${r.origem}</span></td>
                </tr>
            `).join('');

            const tableHtml = `
                <div id="razaoTableContainer" class="table-fixed-container" style="height: 55vh;">
                    <table class="table-modern table-hover">
                        <thead style="position: sticky; top: 0; z-index: 10;">
                            <tr>
                                <th>Conta</th><th>Título</th><th>Data</th><th>Doc</th><th>Histórico</th>
                                <th class="text-end">Débito</th><th class="text-end">Crédito</th><th class="text-end">Saldo</th>
                                <th>Origem</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rows || '<tr><td colspan="9" class="text-center p-4">Nenhum registro encontrado.</td></tr>'}
                        </tbody>
                    </table>
                </div>`;

            this.modal.setContent(`<div style="padding: 1.5rem;">${summaryHtml}${controlsHtml}${tableHtml}</div>`);

            const input = document.getElementById('razaoSearchInput');
            if (input) {
                input.selectionStart = input.selectionEnd = input.value.length; 
                input.addEventListener('input', (e) => {
                    clearTimeout(this.razaoSearchTimer);
                    this.razaoSearchTimer = setTimeout(() => {
                        this.razaoSearch = e.target.value;
                        this.loadRazaoReport(1);
                    }, 600);
                });
            }
        }

        // =========================================================================
        // MÓDULO 2: MOTOR BI RENTABILIDADE (Árvore, Filtros, Colunas)
        // =========================================================================

        async loadRentabilidadeReport(origem = null) {
            if (!this.modal) this.modal = new ModalSystem('modalRelatorio');
            
            if (origem !== null) {
                this.biState.origemFilter = origem;
            }
            
            if (origem === null) {
                this.biState.filters = {};
                this.biState.globalSearch = '';
            }
            
            this.modal.open('<i class="fas fa-cubes"></i> Análise Gerencial (BI DRE)', '');
            this.modal.showLoading('Construindo cubo de dados...');

            try {
                let urlBase = '/Reports/RelatorioRazao/Rentabilidade';
                if (typeof API_ROUTES !== 'undefined' && API_ROUTES.getRentabilidadeData) {
                    urlBase = API_ROUTES.getRentabilidadeData;
                }

                const origemParam = encodeURIComponent(this.biState.origemFilter);
                const rawData = await APIUtils.get(`${urlBase}?origem=${origemParam}`);
                
                if (!rawData || rawData.length === 0) {
                    this.renderBiEmptyState();
                    return;
                }

                this.biRawData = rawData;
                this.biState.columnsOrder = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez', 'Total_Ano'];

                await this.processBiTreeWithCalculated();
                this.renderBiInterface();

            } catch (error) {
                console.error(error);
                this.modal.showError(`Erro no BI: ${error.message}`);
            }
        }

        renderBiEmptyState() {
            const emptyHtml = `
                <div class="bi-toolbar d-flex justify-content-between align-items-center p-3 border-bottom border-primary bg-tertiary">
                    <div class="d-flex gap-2 align-items-center">
                        ${this.renderOrigemFilter()}
                    </div>
                </div>
                <div class="p-4 text-center" style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;">
                    <i class="fas fa-database fa-3x text-muted mb-3"></i>
                    <h4 class="text-secondary">Sem dados disponíveis</h4>
                    <p class="text-muted">Não há registros para a origem "${this.biState.origemFilter}".</p>
                    <p class="text-muted text-sm">Tente selecionar outra origem no filtro acima.</p>
                </div>
            `;
            this.modal.setContent(`<div style="display: flex; flex-direction: column; height: 100%;">${emptyHtml}</div>`);
            this.setupOrigemFilterEvents();
        }

        async reloadBiDataAsync(novaOrigem) {
            if (this.biIsLoading) return;
            
            this.biIsLoading = true;
            this.biState.origemFilter = novaOrigem;
            
            const container = document.getElementById('biGridContainer');
            if (container) {
                container.innerHTML = `
                    <div class="loading-container" style="height: 100%;">
                        <div class="loading-spinner"></div>
                        <div class="loading-text">Recarregando dados para "${novaOrigem}"...</div>
                    </div>
                `;
            }

            try {
                let urlBase = '/Reports/RelatorioRazao/Rentabilidade';
                if (typeof API_ROUTES !== 'undefined' && API_ROUTES.getRentabilidadeData) {
                    urlBase = API_ROUTES.getRentabilidadeData;
                }

                const origemParam = encodeURIComponent(novaOrigem);
                const rawData = await APIUtils.get(`${urlBase}?origem=${origemParam}`);
                
                if (!rawData || rawData.length === 0) {
                    this.biRawData = [];
                    this.biTreeData = [];
                    if (container) {
                        container.innerHTML = `
                            <div class="p-4 text-center" style="height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center;">
                                <i class="fas fa-inbox fa-2x text-muted mb-2"></i>
                                <p class="text-muted">Nenhum dado encontrado para "${novaOrigem}".</p>
                            </div>
                        `;
                    }
                } else {
                    this.biRawData = rawData;
                    await this.processBiTreeWithCalculated();
                    this.renderBiTable();
                }
                
                this.updateOrigemBadge();
                
            } catch (error) {
                console.error('Erro ao recarregar BI:', error);
                if (container) {
                    container.innerHTML = `
                        <div class="p-4 text-center text-danger">
                            <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                            <p>Erro ao carregar dados: ${error.message}</p>
                        </div>
                    `;
                }
            } finally {
                this.biIsLoading = false;
            }
        }

        updateOrigemBadge() {
            const badge = document.getElementById('biOrigemBadge');
            if (badge) {
                badge.textContent = `${this.biRawData.length} registros`;
            }
        }

        renderOrigemFilter() {
            const opcoes = ['Consolidado', 'FARMA', 'FARMADIST'];
            return `
                <div class="origem-filter-group d-flex align-items-center gap-2">
                    <label class="text-secondary text-sm me-1">
                        <i class="fas fa-filter"></i> Origem:
                    </label>
                    <div class="btn-group origem-toggle-group" role="group">
                        ${opcoes.map(op => `
                            <button type="button" 
                                    class="btn btn-sm origem-toggle-btn ${this.biState.origemFilter === op ? 'active' : ''}" 
                                    data-origem="${op}"
                                    onclick="relatorioSystem.handleOrigemChange('${op}')">
                                ${this.getOrigemIcon(op)} ${op}
                            </button>
                        `).join('')}
                    </div>
                    <span id="biOrigemBadge" class="badge badge-secondary ms-2">
                        ${this.biRawData.length} registros
                    </span>
                </div>
            `;
        }

        getOrigemIcon(origem) {
            const icons = {
                'Consolidado': '<i class="fas fa-layer-group"></i>',
                'FARMA': '<i class="fas fa-pills"></i>',
                'FARMADIST': '<i class="fas fa-truck"></i>'
            };
            return icons[origem] || '';
        }

        handleOrigemChange(novaOrigem) {
            if (novaOrigem === this.biState.origemFilter || this.biIsLoading) return;
            document.querySelectorAll('.origem-toggle-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.origem === novaOrigem);
            });
            this.reloadBiDataAsync(novaOrigem);
        }

        setupOrigemFilterEvents() {}

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
                // CORREÇÃO: Garante que 0 não seja tratado como false
                const ordemVal = (row.ordem_prioridade !== null && row.ordem_prioridade !== undefined) 
                    ? row.ordem_prioridade 
                    : (row.Ordem || row.ordem || (index * 10) + 1000);

                const tipoId = `T_${row.Tipo_CC}`;
                const tipoNode = getOrCreateNode(tipoId, row.Tipo_CC, 'root', root, ordemVal);
                
                // CORREÇÃO: Atualiza a ordem do nó existente se a linha atual tiver uma ordem válida e menor
                // Isso corrige o bug onde a primeira linha pode não ter ordem, mas a segunda sim
                if ((row.ordem_prioridade !== null || row.Ordem) && tipoNode.ordem >= 1000) {
                    tipoNode.ordem = (row.ordem_prioridade !== null) ? row.ordem_prioridade : row.Ordem;
                }
                
                sumValues(tipoNode, row);

                let currentNode = tipoNode;
                let currentId = tipoId;

                if (row.Caminho_Subgrupos && row.Caminho_Subgrupos !== 'Não Classificado' && row.Caminho_Subgrupos !== 'Direto') {
                    const groups = row.Caminho_Subgrupos.split('||');
                    groups.forEach((gName, idx) => {
                        currentId += `_G${idx}_${gName}`; 
                        const groupNode = getOrCreateNode(currentId, gName, 'group', currentNode.children);
                        sumValues(groupNode, row);
                        currentNode = groupNode;
                    });
                }

                const contaId = `C_${row.Conta}`;
                const contaNode = {
                    id: contaId + currentId,
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
            const toolbar = `
                <div class="bi-toolbar d-flex justify-content-between align-items-center p-3 border-bottom border-primary bg-tertiary">
                    <div class="d-flex gap-2 align-items-center flex-wrap">
                        ${this.renderOrigemFilter()}
                        <div class="separator-vertical mx-2" style="height: 20px; border-left: 1px solid var(--border-secondary);"></div>
                        <div class="input-group input-group-sm" style="width: 200px;">
                            <i class="input-group-icon fas fa-search"></i>
                            <input type="text" id="biGlobalSearch" class="form-control" 
                                   placeholder="Filtrar estrutura..." value="${this.biState.globalSearch}"
                                   oninput="relatorioSystem.handleBiGlobalSearch(this.value)">
                        </div>
                    </div>
                    <div class="d-flex gap-2 align-items-center">
                        <button class="btn btn-sm btn-outline" onclick="relatorioSystem.toggleAllNodes(true)" title="Expandir Tudo">
                            <i class="fas fa-expand-arrows-alt"></i>
                        </button>
                        <button class="btn btn-sm btn-outline" onclick="relatorioSystem.toggleAllNodes(false)" title="Recolher Tudo">
                            <i class="fas fa-compress-arrows-alt"></i>
                        </button>
                        <button class="btn btn-sm btn-outline" onclick="relatorioSystem.openColumnManager()" title="Gerenciar Colunas">
                            <i class="fas fa-columns"></i>
                        </button>
                        <div class="separator-vertical mx-1" style="height: 20px; border-left: 1px solid var(--border-secondary);"></div>
                        <button class="btn btn-sm btn-success" onclick="relatorioSystem.exportBiToCsv()">
                            <i class="fas fa-file-csv"></i> Exportar
                        </button>
                    </div>
                </div>`;

            const gridContainer = `
                <div id="biGridContainer" class="table-fixed-container" style="flex: 1; overflow: auto; background: var(--bg-secondary);">
                </div>`;

            const footer = `
                <div class="bi-footer p-2 bg-tertiary border-top border-primary d-flex justify-content-between align-items-center">
                    <span class="text-secondary text-xs">
                        <i class="fas fa-info-circle"></i> 
                        Fonte: <strong>${this.biState.origemFilter}</strong> | 
                        Valores consolidados por estrutura DRE
                    </span>
                    <span class="text-muted text-xs">
                        Última atualização: ${new Date().toLocaleTimeString('pt-BR')}
                    </span>
                </div>`;

            this.modal.setContent(`<div style="display: flex; flex-direction: column; height: 100%;">${toolbar}${gridContainer}${footer}</div>`);
            
            this.renderBiTable();
            this.setupOrigemFilterEvents();
        }

        renderBiTable() {
            const container = document.getElementById('biGridContainer');
            if (!container) return;

            const cols = this.biState.columnsOrder.filter(c => !this.biState.hiddenCols.has(c));
            
            let headerHtml = `
                <thead style="position: sticky; top: 0; z-index: 20;">
                    <tr>
                        <th style="min-width: 350px; left: 0; position: sticky; z-index: 30;" class="bg-tertiary border-end border-secondary">
                            Estrutura DRE
                        </th>
                        ${cols.map(c => `
                            <th class="text-end bg-tertiary border-end border-secondary" style="min-width: 110px;">
                                <div class="d-flex flex-column">
                                    <span class="mb-1 cursor-pointer" onclick="relatorioSystem.sortBiBy('${c}')">${c} <i class="fas fa-sort text-muted text-xs"></i></span>
                                    <input type="text" class="form-control form-control-sm p-1 text-end text-xs bg-dark border-secondary" 
                                           placeholder="Filtro..." 
                                           value="${this.biState.filters[c] || ''}"
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
                
                // Ícone
                let icon = '';
                if (isGroup) {
                    icon = `<i class="fas fa-chevron-${isExpanded ? 'down' : 'right'} me-2 toggle-icon" 
                            onclick="event.stopPropagation(); relatorioSystem.toggleNode('${node.id}')"></i>`;
                } else {
                    // Diferencia ícone para nó calculado
                    if (node.type === 'calculated') {
                         // ADICIONADO: title="${node.formulaDescricao || ''}"
                         icon = `<i class="fas fa-calculator me-2 text-info" 
                                    style="margin-left: 4px; cursor: help;" 
                                    title="${node.formulaDescricao || 'Nó Calculado'}"></i>`;
                    } else {
                         icon = `<i class="far fa-file-alt me-2 opacity-50" style="margin-left: 4px;"></i>`;
                    }
                }

                let rowClass = '';
                if (node.type === 'root') rowClass = 'bi-row-root'; 
                else if (node.type === 'group') rowClass = 'bi-row-group'; 
                else if (node.type === 'calculated') rowClass = 'bi-row-calculated';
                else rowClass = 'bi-row-account'; 

                const customStyle = node.estiloCss ? `style="${node.estiloCss}"` : '';

                const cellsHtml = cols.map(c => {
                    const val = node.values[c];
                    let colorClass = 'text-muted';
                    
                    if (val < 0) colorClass = 'text-danger fw-bold';
                    else if (val > 0) colorClass = 'text-success fw-bold';
                    
                    let displayVal = val !== 0 ? FormatUtils.formatNumber(val) : '-';
                    if (node.tipoExibicao === 'percentual' && val !== 0) {
                        displayVal = val.toFixed(2) + '%';
                    }

                    return `<td class="text-end font-mono ${colorClass}">
                                ${displayVal}
                            </td>`;
                }).join('');

                bodyRows += `
                    <tr class="${rowClass}" ${customStyle}>
                        <td style="padding-left: ${padding}px;">
                            <div class="d-flex align-items-center cell-label">
                                ${icon}
                                <span class="text-truncate" title="${node.formulaDescricao || ''}">${node.label}</span>
                            </div>
                        </td>
                        ${cellsHtml}
                    </tr>
                `;

                if (isGroup && isExpanded) {
                    node.children.forEach(child => renderNode(child, level + 1));
                }
            };

            this.biTreeData.forEach(node => renderNode(node, 0));

            container.innerHTML = `<table class="table-modern w-100" style="border-collapse: separate; border-spacing: 0;">${headerHtml}<tbody>${bodyRows}</tbody></table>`;
        }

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
                if (node.children && node.children.length > 0) {
                    node.children.forEach(child => {
                        if (checkVisibility(child)) hasVisibleChildren = true;
                    });
                }

                const isVisible = (matchesGlobal && matchesCols) || hasVisibleChildren;
                node.isVisible = isVisible;

                if (isVisible && (globalTerm || hasColFilters)) {
                    this.biState.expanded.add(node.id); 
                }

                return isVisible;
            };

            this.biTreeData.forEach(node => checkVisibility(node));
        }

        handleBiGlobalSearch(val) {
            this.biState.globalSearch = val;
            this.debounceRender();
        }

        handleBiColFilter(col, val) {
            if (!val) delete this.biState.filters[col];
            else this.biState.filters[col] = val;
            this.debounceRender();
        }

        debounceRender() {
            clearTimeout(this.biDebounceTimer);
            this.biDebounceTimer = setTimeout(() => {
                this.applyBiFilters();
                this.renderBiTable();
            }, 400);
        }

        toggleNode(id) {
            if (this.biState.expanded.has(id)) this.biState.expanded.delete(id);
            else this.biState.expanded.add(id);
            this.renderBiTable();
        }

        toggleAllNodes(expand) {
            const recurse = (nodes) => {
                nodes.forEach(n => {
                    if (expand) this.biState.expanded.add(n.id);
                    else this.biState.expanded.delete(n.id);
                    if (n.children) recurse(n.children);
                });
            };
            recurse(this.biTreeData);
            this.renderBiTable();
        }

        openColumnManager() {
            const allCols = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez', 'Total_Ano'];
            
            const checksHtml = allCols.map(c => `
                <div class="col-6 mb-2">
                    <label class="d-flex align-items-center cursor-pointer">
                        <input type="checkbox" 
                               ${!this.biState.hiddenCols.has(c) ? 'checked' : ''} 
                               onchange="relatorioSystem.toggleBiColumn('${c}')">
                        <span class="ms-2 text-white">${c}</span>
                    </label>
                </div>
            `).join('');

            const modalHtml = `
                <div class="p-3">
                    <h5>Gerenciar Colunas Visíveis</h5>
                    <div class="row mt-3">${checksHtml}</div>
                    <div class="mt-3 text-end">
                        <button class="btn btn-sm btn-primary" onclick="this.closest('.modal-backdrop').remove(); relatorioSystem.renderBiTable()">Aplicar</button>
                    </div>
                </div>
            `;
            
            const colModal = document.createElement('div');
            colModal.className = 'modal-backdrop active';
            colModal.innerHTML = `<div class="modal-window modal-sm"><div class="modal-body">${modalHtml}</div></div>`;
            colModal.onclick = (e) => { if(e.target === colModal) colModal.remove(); };
            document.body.appendChild(colModal);
        }

        toggleBiColumn(col) {
            if (this.biState.hiddenCols.has(col)) this.biState.hiddenCols.delete(col);
            else this.biState.hiddenCols.add(col);
        }
        
        sortBiBy(col) {
            if (this.biState.sort.col === col) {
                this.biState.sort.dir = this.biState.sort.dir === 'asc' ? 'desc' : 'asc';
            } else {
                this.biState.sort.col = col;
                this.biState.sort.dir = 'desc'; 
            }
            
            const sortNodes = (nodes) => {
                nodes.sort((a, b) => {
                    const valA = a.values[col] || 0;
                    const valB = b.values[col] || 0;
                    return this.biState.sort.dir === 'asc' ? valA - valB : valB - valA;
                });
                nodes.forEach(n => {
                    if (n.children && n.children.length > 0) {
                        sortNodes(n.children);
                    }
                });
            };
            
            sortNodes(this.biTreeData);
            this.renderBiTable();
        }

        exportBiToCsv() {
            let csvContent = "data:text/csv;charset=utf-8,";
            const visibleCols = this.biState.columnsOrder.filter(c => !this.biState.hiddenCols.has(c));
            
            csvContent += `# Análise Gerencial - Origem: ${this.biState.origemFilter}\r\n`;
            csvContent += `# Exportado em: ${new Date().toLocaleString('pt-BR')}\r\n`;
            csvContent += "\r\n";
            
            csvContent += "Estrutura;" + visibleCols.join(";") + "\r\n";

            const processRow = (node, prefix = "") => {
                if (!node.isVisible) return;
                const rowStr = [`"${prefix}${node.label}"`, ...visibleCols.map(c => (node.values[c] || 0).toFixed(2).replace('.', ','))].join(";");
                csvContent += rowStr + "\r\n";
                
                if (node.children) {
                    node.children.forEach(child => processRow(child, prefix + "  "));
                }
            };

            this.biTreeData.forEach(n => processRow(n));

            const encodedUri = encodeURI(csvContent);
            const link = document.createElement("a");
            link.setAttribute("href", encodedUri);
            link.setAttribute("download", `analise_dre_${this.biState.origemFilter.toLowerCase()}_${new Date().toISOString().slice(0,10)}.csv`);
            document.body.appendChild(link);
            link.click();
            link.remove();
        }

        async loadNosCalculados() {
            try {
                let url = '/Configuracao/GetNosCalculados';
                if (typeof API_ROUTES !== 'undefined' && API_ROUTES.getNosCalculados) {
                    url = API_ROUTES.getNosCalculados;
                }
                const response = await APIUtils.get(url);
                this.nosCalculados = response || [];
                return this.nosCalculados;
            } catch (e) {
                console.warn('Erro ao carregar nós calculados:', e);
                return [];
            }
        }

        calcularValorNo(formula, mes, valoresAgregados) {
            if (!formula || !formula.operandos) return 0;
            
            const operacao = formula.operacao || 'soma';
            const operandos = formula.operandos;
            
            const valores = operandos.map(op => {
                const chave = `${op.tipo}_${op.id}`;
                return valoresAgregados[chave]?.[mes] || 0;
            });
            
            let resultado = 0;
            
            switch (operacao) {
                case 'soma':
                    resultado = valores.reduce((a, b) => a + b, 0);
                    break;
                case 'subtracao':
                    resultado = valores[0] - valores.slice(1).reduce((a, b) => a + b, 0);
                    break;
                case 'multiplicacao':
                    resultado = valores.reduce((a, b) => a * b, 1);
                    break;
                case 'divisao':
                    resultado = valores[1] !== 0 ? valores[0] / valores[1] : 0;
                    break;
            }
            
            if (formula.multiplicador) {
                resultado *= formula.multiplicador;
            }
            
            return resultado;
        }

        async processBiTreeWithCalculated() {
            // 1. Processa árvore normal (Dados do Banco)
            this.processBiTree();
            
            // 2. Carrega nós calculados (Configuração)
            const nosCalc = await this.loadNosCalculados();
            
            if (nosCalc.length > 0) {
                // 3. Agrega valores
                const valoresAgregados = this.agregarValoresPorTipo();
                const meses = this.biState.columnsOrder;
                
                // 4. Cria e adiciona nós calculados na lista principal
                nosCalc.forEach(noCalc => {
                    if (!noCalc.formula) return;
                    
                    const valores = {};
                    meses.forEach(mes => {
                        valores[mes] = this.calcularValorNo(noCalc.formula, mes, valoresAgregados);
                    });

                    // --- INÍCIO DA ADIÇÃO: GERA DESCRIÇÃO AUTOMÁTICA ---
                    let textoTooltip = noCalc.formula_descricao;
                    
                    if (!textoTooltip && noCalc.formula) {
                        const ops = noCalc.formula.operandos || [];
                        const nomesOps = ops.map(o => o.label || o.id).join(', '); // Pega o nome amigável ou o ID
                        const opMap = {
                            'soma': 'Soma (+)',
                            'subtracao': 'Subtração (-)',
                            'multiplicacao': 'Multiplicação (×)',
                            'divisao': 'Divisão (÷)'
                        };
                        const opNome = opMap[noCalc.formula.operacao] || noCalc.formula.operacao;
                        
                        textoTooltip = `Fórmula: ${opNome}\nEnvolvendo: ${nomesOps}`;
                        if(noCalc.formula.multiplicador) textoTooltip += `\nMultiplicador: ${noCalc.formula.multiplicador}x`;
                    }
                    // --- FIM DA ADIÇÃO ---

                    // ... Lógica de ordem original ...
                    const rowBackend = this.biRawData.find(r => 
                        (r.Root_Virtual_Id == noCalc.id) || 
                        (r.Titulo_Conta === noCalc.nome)
                    );
                    
                    let ordemCorreta = 50;
                    if (rowBackend && rowBackend.ordem_prioridade !== null) {
                        ordemCorreta = rowBackend.ordem_prioridade;
                    } else if (noCalc.ordem !== null && noCalc.ordem !== undefined) {
                        ordemCorreta = noCalc.ordem;
                    }
                    
                    const nodeCalc = {
                        id: `calc_${noCalc.id}`,
                        label: `📊 ${noCalc.nome}`, 
                        rawLabel: noCalc.nome,     
                        type: 'calculated',
                        children: [],
                        values: valores,
                        isVisible: true,
                        isExpanded: false,
                        formulaDescricao: textoTooltip, // <--- AQUI USA A VARIÁVEL NOVA
                        estiloCss: noCalc.estilo_css,
                        tipoExibicao: noCalc.tipo_exibicao,
                        ordem: ordemCorreta
                    };
                    
                    this.biTreeData.push(nodeCalc);
                });
            }

            // 5. DEDUPLICAÇÃO (Prioriza Calculado sobre Standard)
            const nomesCalculados = new Set(
                this.biTreeData
                    .filter(n => n.type === 'calculated')
                    .map(n => (n.rawLabel || n.label.replace('📊 ', '')).toUpperCase().trim())
            );

            this.biTreeData = this.biTreeData.filter(node => {
                if (node.type === 'root') {
                    const labelPadrao = node.label.toUpperCase().trim();
                    if (nomesCalculados.has(labelPadrao)) {
                        return false; 
                    }
                }
                return true;
            });

            // 6. ORDENAÇÃO GLOBAL
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
                const tipoId = rootNode.id.replace('T_', '');
                const chave = `tipo_cc_${tipoId}`;
                
                if (!agregados[chave]) {
                    agregados[chave] = {};
                    meses.forEach(m => agregados[chave][m] = 0);
                }
                
                meses.forEach(m => {
                    agregados[chave][m] += rootNode.values[m] || 0;
                });
            });
            
            return agregados;
        }

        inserirNoCalculadoNaArvore(nodeCalc, ordem) {
            let posicao = this.biTreeData.findIndex(n => {
                const ordemExistente = n.ordem || 9999; 
                return ordemExistente > ordem;
            });
            
            if (posicao === -1) {
                this.biTreeData.push(nodeCalc);
            } else {
                this.biTreeData.splice(posicao, 0, nodeCalc);
            }
        }
    }

    window.relatorioSystem = new RelatorioSystem();

    window.fecharModal = function() {
        if (window.relatorioSystem && window.relatorioSystem.modal) {
            window.relatorioSystem.modal.close();
        }
    };
}