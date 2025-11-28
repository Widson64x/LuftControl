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
                columnsOrder: []             // Ordem das colunas (meses)
            };
            this.biDebounceTimer = null;

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
                const term = encodeURIComponent(this.razaoSearch);
                const response = await APIUtils.get(`/Reports/RelatorioRazao/Dados?page=${page}&search=${term}`);
                
                this.razaoData = response.dados || [];
                this.razaoTotalPages = response.total_paginas || 1;

                this.renderRazaoView(response);
            } catch (error) {
                console.error(error);
                this.modal.showError(`Erro ao carregar Razão: ${error.message}`);
            }
        }

        renderRazaoView(metaData) {
            // 1. Calcular Totais da Página
            const totals = this.razaoData.reduce((acc, item) => ({
                deb: acc.deb + (item.debito || 0),
                cred: acc.cred + (item.credito || 0),
                saldo: acc.saldo + (item.saldo || 0)
            }), { deb: 0, cred: 0, saldo: 0 });

            // 2. HTML dos Cards de Resumo
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

            // 3. Barra de Controle (Busca e Paginação)
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

            // 4. Tabela de Dados
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

            // Event Listener para Busca com Debounce
            const input = document.getElementById('razaoSearchInput');
            if (input) {
                input.selectionStart = input.selectionEnd = input.value.length; // Cursor no final
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

        async loadRentabilidadeReport() {
            if (!this.modal) this.modal = new ModalSystem('modalRelatorio');
            
            // Reseta estado básico do BI se for recarga completa
            this.biState.filters = {};
            this.biState.globalSearch = '';
            
            this.modal.open('<i class="fas fa-cubes"></i> Análise Gerencial (BI DRE)', '');
            this.modal.showLoading('Construindo cubo de dados...');

            try {
                // 1. Busca dados do backend
                const rawData = await APIUtils.get('/Reports/RelatorioRazao/Rentabilidade');
                
                if (!rawData || rawData.length === 0) {
                    this.modal.setContent('<div class="p-4 alert alert-warning">Sem dados disponíveis para gerar o BI.</div>');
                    return;
                }

                this.biRawData = rawData;
                
                // 2. Define colunas iniciais (Meses)
                this.biState.columnsOrder = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez', 'Total_Ano'];

                // 3. Processa e Renderiza
                this.processBiTree();
                this.renderBiInterface();

            } catch (error) {
                console.error(error);
                this.modal.showError(`Erro no BI: ${error.message}`);
            }
        }

        /**
         * Transforma lista plana em árvore hierárquica e calcula somas
         */
        processBiTree() {
            const root = [];
            const map = {}; 
            const meses = this.biState.columnsOrder;

            // Helper para criar ou recuperar nó
            const getOrCreateNode = (id, label, type, parentList) => {
                if (!map[id]) {
                    const node = { 
                        id: id, 
                        label: label, 
                        type: type, // 'root', 'group', 'account'
                        children: [], 
                        values: {},
                        isVisible: true, // Controle de filtro
                        isExpanded: this.biState.expanded.has(id) // Persistência de expansão
                    };
                    meses.forEach(m => node.values[m] = 0);
                    map[id] = node;
                    parentList.push(node);
                }
                return map[id];
            };

            // Helper para somar valores no nó
            const sumValues = (node, row) => {
                meses.forEach(m => node.values[m] += (parseFloat(row[m]) || 0));
            };

            this.biRawData.forEach(row => {
                // 1. Nível 1: Tipo (Adm, Oper...)
                const tipoId = `T_${row.Tipo_CC}`;
                const tipoNode = getOrCreateNode(tipoId, row.Tipo_CC, 'root', root);
                sumValues(tipoNode, row);

                // 2. Níveis Dinâmicos (Subgrupos)
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

                // 3. Nível Folha (Conta)
                const contaId = `C_${row.Conta}`;
                // Conta única dentro do grupo
                const contaNode = {
                    id: contaId + currentId, // ID único composto
                    label: `📄 ${row.Conta} - ${row.Titulo_Conta}`,
                    type: 'account',
                    children: [],
                    values: {},
                    isVisible: true
                };
                meses.forEach(m => contaNode.values[m] = parseFloat(row[m]) || 0);
                
                currentNode.children.push(contaNode);
            });

            this.biTreeData = root;
            this.applyBiFilters(); // Aplica filtros iniciais (se houver)
        }

        /**
         * Renderiza a estrutura completa da interface do BI
         */
        renderBiInterface() {
            // Toolbar Superior
            const toolbar = `
                <div class="bi-toolbar d-flex justify-content-between align-items-center p-3 border-bottom border-primary bg-tertiary">
                    <div class="d-flex gap-2 align-items-center">
                        <div class="input-group input-group-sm me-2" style="width: 250px;">
                            <i class="input-group-icon fas fa-filter"></i>
                            <input type="text" id="biGlobalSearch" class="form-control" 
                                   placeholder="Filtrar estrutura..." value="${this.biState.globalSearch}"
                                   oninput="relatorioSystem.handleBiGlobalSearch(this.value)">
                        </div>
                        <div class="separator-vertical mx-2" style="height: 20px; border-left: 1px solid var(--border-secondary);"></div>
                        <button class="btn btn-sm btn-outline" onclick="relatorioSystem.toggleAllNodes(true)"><i class="fas fa-expand-arrows-alt"></i> Expandir</button>
                        <button class="btn btn-sm btn-outline" onclick="relatorioSystem.toggleAllNodes(false)"><i class="fas fa-compress-arrows-alt"></i> Recolher</button>
                        <button class="btn btn-sm btn-outline" onclick="relatorioSystem.openColumnManager()"><i class="fas fa-columns"></i> Colunas</button>
                    </div>
                    <div>
                        <button class="btn btn-sm btn-success" onclick="relatorioSystem.exportBiToCsv()"><i class="fas fa-file-csv"></i> Exportar CSV</button>
                    </div>
                </div>`;

            // Container da Tabela
            const gridContainer = `
                <div id="biGridContainer" class="table-fixed-container" style="flex: 1; overflow: auto; background: var(--bg-secondary);">
                    </div>`;

            // Footer
            const footer = `
                <div class="p-2 bg-tertiary border-top border-primary text-end text-secondary text-xs">
                    <i class="fas fa-info-circle"></i> Valores consolidados. Filtros ocultam linhas mas mantêm totais dos grupos.
                </div>`;

            this.modal.setContent(`<div style="display: flex; flex-direction: column; height: 100%;">${toolbar}${gridContainer}${footer}</div>`);
            
            // Renderiza a tabela em si
            this.renderBiTable();
        }

        /**
         * Gera o HTML da Tabela BI baseada no estado atual
         */
        renderBiTable() {
            const container = document.getElementById('biGridContainer');
            if (!container) return;

            const cols = this.biState.columnsOrder.filter(c => !this.biState.hiddenCols.has(c));
            
            // --- HEADER (Com Filtros) ---
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

            // --- BODY (Recursivo) ---
            let bodyRows = '';
            
            // Dentro de Static/JS/Relatorios.js -> renderBiTable -> renderNode

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
                    icon = `<i class="far fa-file-alt me-2 opacity-50" style="margin-left: 4px;"></i>`;
                }

                // --- CORREÇÃO AQUI: Classes Semânticas em vez de Cores Fixas ---
                let rowClass = '';
                
                if (node.type === 'root') { 
                    // Raiz (Ex: FATURAMENTO)
                    rowClass = 'bi-row-root'; 
                } 
                else if (node.type === 'group') { 
                    // Grupo (Ex: Despesas)
                    rowClass = 'bi-row-group'; 
                } 
                else { 
                    // Conta (Ex: Salários)
                    rowClass = 'bi-row-account'; 
                }

                // Células de Valor
                const cellsHtml = cols.map(c => {
                    const val = node.values[c];
                    let colorClass = 'text-muted'; // Cor padrão (cinza/apagado)
                    
                    // As cores de texto (danger/success) já usam variáveis no Themes.css, então funcionam
                    if (val < 0) colorClass = 'text-danger fw-bold';
                    else if (val > 0) colorClass = 'text-success fw-bold';
                    
                    return `<td class="text-end font-mono ${colorClass}">
                                ${val !== 0 ? FormatUtils.formatNumber(val) : '-'}
                            </td>`;
                }).join('');

                bodyRows += `
                    <tr class="${rowClass}">
                        <td style="padding-left: ${padding}px;">
                            <div class="d-flex align-items-center cell-label">
                                ${icon}
                                <span class="text-truncate">${node.label}</span>
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

            // Injeta na DOM
            container.innerHTML = `<table class="table-modern w-100" style="border-collapse: separate; border-spacing: 0;">${headerHtml}<tbody>${bodyRows}</tbody></table>`;
        }

        // --- LÓGICA DE FILTROS E ÁRVORE ---

        applyBiFilters() {
            const globalTerm = this.biState.globalSearch.toLowerCase();
            const colFilters = this.biState.filters;
            const hasColFilters = Object.keys(colFilters).length > 0;

            // Função recursiva para verificar visibilidade
            const checkVisibility = (node) => {
                let matchesGlobal = !globalTerm || node.label.toLowerCase().includes(globalTerm);
                let matchesCols = true;

                // Verifica filtros de coluna (ex: > 1000)
                if (hasColFilters) {
                    for (const [col, filterVal] of Object.entries(colFilters)) {
                        if (!filterVal) continue;
                        const nodeVal = node.values[col];
                        
                        // Suporte simples a operadores >, <, =
                        let pass = false;
                        const cleanFilter = filterVal.replace(',', '.').trim();
                        
                        if (cleanFilter.startsWith('>')) pass = nodeVal > parseFloat(cleanFilter.substring(1));
                        else if (cleanFilter.startsWith('<')) pass = nodeVal < parseFloat(cleanFilter.substring(1));
                        else pass = nodeVal.toString().includes(cleanFilter); // Busca texto exato

                        if (!pass) { matchesCols = false; break; }
                    }
                }

                // Lógica hierárquica: Se um filho é visível, o pai também deve ser
                let hasVisibleChildren = false;
                if (node.children && node.children.length > 0) {
                    node.children.forEach(child => {
                        if (checkVisibility(child)) hasVisibleChildren = true;
                    });
                }

                // O nó é visível se ele mesmo der match OU se tiver filhos visíveis
                // (Se tiver filtro ativo, expandimos automaticamente os grupos com matches)
                const isVisible = (matchesGlobal && matchesCols) || hasVisibleChildren;
                node.isVisible = isVisible;

                if (isVisible && (globalTerm || hasColFilters)) {
                    this.biState.expanded.add(node.id); // Auto-expandir ao filtrar
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

        // --- INTERAÇÕES DA ÁRVORE ---

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

        // --- GERENCIADOR DE COLUNAS ---

        openColumnManager() {
            // Cria um modal simples dinâmico para checkbox das colunas
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
                        <button class="btn btn-sm btn-primary" onclick="closeModals(); relatorioSystem.renderBiTable()">Aplicar</button>
                    </div>
                </div>
            `;
            
            // Reutiliza um modal secundário ou injeta um dialog temporário
            // Para simplificar, vou usar um alert customizado ou apenas assumir que temos um modal genérico
            // Aqui, vou usar o próprio ModalSystem se ele suportar replace, senão um overlay simples
            const colModal = document.createElement('div');
            colModal.className = 'modal-backdrop active';
            colModal.innerHTML = `<div class="modal-window modal-sm"><div class="modal-body">${modalHtml}</div></div>`;
            colModal.onclick = (e) => { if(e.target === colModal) colModal.remove(); };
            document.body.appendChild(colModal);
        }

        toggleBiColumn(col) {
            if (this.biState.hiddenCols.has(col)) this.biState.hiddenCols.delete(col);
            else this.biState.hiddenCols.add(col);
            // Re-render acontece ao fechar o modal ou pode ser imediato se desejar
        }

        // --- EXPORTAÇÃO ---

        exportBiToCsv() {
            let csvContent = "data:text/csv;charset=utf-8,";
            const visibleCols = this.biState.columnsOrder.filter(c => !this.biState.hiddenCols.has(c));
            
            // Header
            csvContent += "Estrutura;" + visibleCols.join(";") + "\r\n";

            // Rows (Recursivo)
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
            link.setAttribute("download", "analise_dre_bi.csv");
            document.body.appendChild(link);
            link.click();
            link.remove();
        }
    }

    // Instancia Globalmente
    window.relatorioSystem = new RelatorioSystem();

    // Helper Global
    window.fecharModal = function() {
        if (window.relatorioSystem && window.relatorioSystem.modal) {
            window.relatorioSystem.modal.close();
        }
    };
}