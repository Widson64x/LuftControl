// ============================================================================
// T-Controllership - SISTEMA DE RELATÓRIOS FINANCEIROS
// Arquivo: Static/js/Relatorios.js
// ============================================================================

class RelatorioSystem {
    constructor() {
        this.modal = new ModalSystem('modalRelatorio');
        
        // Estado Razão
        this.currentData = null;
        this.currentPage = 1;
        this.totalPages = 1;
        this.currentSearch = ''; 
        this.searchTimeout = null; 
        this.sortState = { column: -1, ascending: true };

        // Estado BI (Rentabilidade)
        this.cachedBiData = null;     
        this.biViewMode = 'detailed'; // 'detailed' (Com CC) ou 'direct' (Agrupado por Tipo)
        
        window.toggleBiRow = (id) => this.handleBiToggle(id);
        window.relatorioSystem = this;

        this.init();
    }

    init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupEventListeners());
        } else {
            this.setupEventListeners();
        }
    }

    setupEventListeners() {
        console.log('✅ RelatorioSystem Inicializado');
    }

    // =========================================================================
    // PARTE 1: RELATÓRIO DE RAZÃO (Mantido igual)
    // =========================================================================
    async loadRazaoReport(page = 1) {
        this.currentPage = page;
        let title = '📈 Relatório de Razão';
        if (this.currentSearch) title += ` - Buscando: "${this.currentSearch}"`;

        if (page === 1 && !document.querySelector('#razaoTable')) {
            this.modal.open(title);
            this.modal.showLoading('Buscando dados no servidor...');
        } else {
            const table = document.getElementById('razaoTable');
            if (table) table.style.opacity = '0.5';
        }

        try {
            const encodedSearch = encodeURIComponent(this.currentSearch);
            const response = await APIUtils.get(`/Reports/RelatorioRazao/Dados?page=${page}&search=${encodedSearch}`);
            
            const data = response.dados || [];
            this.totalPages = response.total_paginas || 1;
            this.currentData = data;

            this.renderRazaoReport(data, response);
            const container = document.querySelector('.table-fixed-container');
            if (container) container.scrollTop = 0;

        } catch (error) {
            console.error('Erro:', error);
            this.modal.showError(`Erro na busca: ${error.message}`);
        }
    }

    renderRazaoReport(data, metaData) {
        const totals = this.calculateTotals(data);
        const summaryHtml = this.renderSummaryCards(totals, metaData.total_registros);
        const tableHtml = this.renderRazaoTable(data, metaData); 
        const paginationHtml = this.renderPaginationControls();

        this.modal.setContent(summaryHtml + paginationHtml + tableHtml);
        
        setTimeout(() => {
             const searchInput = document.getElementById('serverSearch');
             if(searchInput) {
                 searchInput.value = this.currentSearch;
                 searchInput.focus();
                 searchInput.addEventListener('input', (e) => {
                     clearTimeout(this.searchTimeout);
                     this.searchTimeout = setTimeout(() => {
                         this.currentSearch = e.target.value;
                         this.loadRazaoReport(1); 
                     }, 800); 
                 });
             }
        }, 100);
    }

    renderPaginationControls() {
        if (this.totalPages <= 1) return '';
        const isFirst = this.currentPage === 1;
        const isLast = this.currentPage >= this.totalPages;
        return `
            <div class="d-flex align-items-center justify-content-between mb-3 p-2" style="background: rgba(255,255,255,0.05); border-radius: 8px;">
                <div class="text-muted">
                    Página <span class="text-white font-bold">${this.currentPage}</span> de ${this.totalPages}
                    ${this.currentSearch ? `<small class="ms-2 text-info">(Filtrado por: ${this.currentSearch})</small>` : ''}
                </div>
                <div class="btn-group">
                    <button class="btn btn-secondary btn-sm" onclick="relatorioSystem.loadRazaoReport(${this.currentPage - 1})" ${isFirst ? 'disabled' : ''}><i class="fas fa-chevron-left"></i> Anterior</button>
                    <button class="btn btn-secondary btn-sm" onclick="relatorioSystem.loadRazaoReport(${this.currentPage + 1})" ${isLast ? 'disabled' : ''}>Próxima <i class="fas fa-chevron-right"></i></button>
                </div>
            </div>`;
    }

    calculateTotals(data) {
        return data.reduce((acc, item) => {
            acc.debito += parseFloat(item.debito) || 0;
            acc.credito += parseFloat(item.credito) || 0;
            acc.saldo += parseFloat(item.saldo) || 0;
            return acc;
        }, { debito: 0, credito: 0, saldo: 0 });
    }

    renderSummaryCards(totals, totalGlobal) {
        return `
            <div class="summary-grid">
                <div class="summary-card"><div class="summary-label">${this.currentSearch ? 'Registros Encontrados' : 'Total da Base'}</div><div class="summary-value">${FormatUtils.formatNumber(totalGlobal)}</div><div class="summary-change positive"><i class="fas fa-database"></i> Server-Side</div></div>
                <div class="summary-card"><div class="summary-label">Débito (Página Atual)</div><div class="summary-value text-danger">${FormatUtils.formatCurrency(totals.debito)}</div></div>
                <div class="summary-card"><div class="summary-label">Crédito (Página Atual)</div><div class="summary-value text-success">${FormatUtils.formatCurrency(totals.credito)}</div></div>
                <div class="summary-card"><div class="summary-label">Saldo (Página Atual)</div><div class="summary-value ${totals.saldo >= 0 ? 'text-success' : 'text-danger'}">${FormatUtils.formatCurrency(totals.saldo)}</div></div>
            </div>
            <div class="d-flex justify-between align-items-center mb-2">
                 <div class="input-group" style="max-width: 400px; min-width: 300px;"><i class="input-group-icon fas fa-search"></i><input type="text" id="serverSearch" class="form-control" placeholder="🔍 Pesquisar..."></div>
            </div>`;
    }

    renderRazaoTable(data, metaData) {
        if (!data || data.length === 0) return `<div class="alert alert-info text-center mt-4"><h4><i class="fas fa-search"></i> Nenhum resultado encontrado</h4></div>`;
        
        const rows = data.map(item => `
            <tr>
                <td>${item.conta || '-'}</td>
                <td><small>${item.titulo_conta || '-'}</small></td>
                <td>${FormatUtils.formatDate(item.data)}</td>
                <td>${item.numero || ''}</td>
                <td><small>${item.descricao || '-'}</small></td>
                <td class="text-danger">${FormatUtils.formatCurrency(item.debito)}</td>
                <td class="text-success">${FormatUtils.formatCurrency(item.credito)}</td>
                <td class="${item.saldo >= 0 ? 'text-success' : 'text-danger'} font-bold">${FormatUtils.formatCurrency(item.saldo)}</td>
                <td>${item.filial_id || '-'}</td> 
                <td>${item.cc_cod || ''}</td>
                <td>${item.nome_cc || '-'}</td>
                <td>${item.origem || '-'}</td>
            </tr>`).join('');

        return `<div class="table-fixed-container"><table class="table-modern table-hover table-fixed-header" id="razaoTable" style="min-width: 1600px;"><thead><tr><th onclick="relatorioSystem.sortColumn(0)">Conta</th><th>Título</th><th>Data</th><th>Núm.</th><th>Histórico</th><th>Débito</th><th>Crédito</th><th>Saldo</th><th>Filial</th><th>C.C.</th><th>Centro Custo</th><th>Origem</th></tr></thead><tbody>${rows}</tbody></table></div><div class="mt-2 text-end text-muted"><small>Exibindo ${data.length} de ${metaData.total_registros} registros.</small></div>`;
    }

    sortColumn(columnIndex) {
        const table = document.getElementById('razaoTable');
        if (!table) return;
        if (this.sortState.column === columnIndex) this.sortState.ascending = !this.sortState.ascending;
        else { this.sortState.column = columnIndex; this.sortState.ascending = true; }
        TableUtils.sortTable(table, columnIndex, this.sortState.ascending);
    }

    // =========================================================================
    // PARTE 2: RELATÓRIO RENTABILIDADE (BI TREE GRID)
    // =========================================================================

    async loadRentabilidadeReport() {
        this.modal.open('📊 Análise de Rentabilidade');
        this.modal.showLoading('Calculando cubos e hierarquias...');

        try {
            if (!this.cachedBiData) {
                const response = await APIUtils.get(`/Reports/RelatorioRazao/Rentabilidade`);
                this.cachedBiData = response || [];
            }
            if (this.cachedBiData.length === 0) {
                this.modal.setContent('<div class="alert alert-warning">Nenhum dado encontrado.</div>');
                return;
            }
            this.renderBiView();
        } catch (error) {
            console.error(error);
            this.modal.showError(`Erro ao gerar BI: ${error.message}`);
        }
    }

    switchBiView(mode) {
        this.biViewMode = mode;
        this.renderBiView();
    }

    renderBiView() {
        // Aqui acontece a mágica da mudança de visão
        const treeData = this.buildHierarchy(this.cachedBiData);
        const tableHtml = this.renderTreeTable(treeData);
        
        const controlsHtml = `
            <div class="d-flex justify-content-between align-items-center mb-3" style="background: rgba(0,0,0,0.2); padding: 10px; border-radius: 8px;">
                <div class="btn-group">
                    <button class="btn btn-sm ${this.biViewMode === 'detailed' ? 'btn-primary' : 'btn-secondary'}" 
                            onclick="relatorioSystem.switchBiView('detailed')"
                            title="Tipo > Centro de Custo > Subgrupos">
                        <i class="fas fa-sitemap"></i> Detalhado (Por C.C.)
                    </button>
                    <button class="btn btn-sm ${this.biViewMode === 'direct' ? 'btn-primary' : 'btn-secondary'}" 
                            onclick="relatorioSystem.switchBiView('direct')"
                            title="Tipo > Subgrupos (Soma todos os CCs)">
                        <i class="fas fa-stream"></i> Direto (Consolidado)
                    </button>
                </div>
                <button class="btn btn-sm btn-outline-light" onclick="relatorioSystem.expandAll()"><i class="fas fa-expand-arrows-alt"></i> Expandir Tudo</button>
            </div>`;

        this.modal.setContent(controlsHtml + tableHtml);
    }

    /**
     * CONSTRUÇÃO DA ÁRVORE (A LÓGICA DA DUPLA VISÃO)
     */
    buildHierarchy(data) {
        const root = {};

        data.forEach(row => {
            let levels = [];

            // === 1. DEFINIÇÃO DOS NÍVEIS SUPERIORES ===
            if (this.biViewMode === 'detailed') {
                // VISÃO DETALHADA: Adm -> Tesouraria -> Pessoal
                levels.push(row.Tipo_CC || 'Sem Tipo');
                if (row.Nome_CC) levels.push(row.Nome_CC); // Se for Virtual, Nome_CC é null e não entra
            } else {
                // VISÃO DIRETA: Adm -> Pessoal (Ignora Tesouraria, RH, etc)
                levels.push(row.Tipo_CC || 'Sem Tipo');
                // PULA O NOME DO CC AQUI
            }

            // === 2. SUBGRUPOS (O "MEIO" DA ÁRVORE) ===
            const subgruposRaw = row.Caminho_Subgrupos;
            if (subgruposRaw && subgruposRaw !== 'Não Classificado' && subgruposRaw !== 'Direto') {
                // Divide a string "Pessoal||Salarios" em array
                const dynamicLevels = subgruposRaw.split('||');
                levels = levels.concat(dynamicLevels);
            } else if (subgruposRaw === 'Não Classificado') {
                levels.push('Não Classificado');
            }

            // === 3. TÍTULO DA CONTA (PENÚLTIMO NÍVEL) ===
            levels.push(row.Titulo_Conta || 'Sem Título');

            // === 4. PROCESSAMENTO RECURSIVO ===
            let currentLevel = root;

            levels.forEach((key) => {
                // Se o nó (ex: "Pessoal") não existe neste nível, cria.
                // Se já existe (criado por outro CC), REUSA e SOMA os valores.
                if (!currentLevel[key]) {
                    currentLevel[key] = { 
                        _isLeaf: false, 
                        _data: this.createZeroedMonths(), 
                        _children: {} 
                    };
                }
                this.accumulateValues(currentLevel[key]._data, row);
                currentLevel = currentLevel[key]._children;
            });

            // === 5. FOLHA (A CONTA CONTÁBIL) ===
            const contaKey = `📄 ${row.Conta}`; 
            if (!currentLevel[contaKey]) {
                currentLevel[contaKey] = { _isLeaf: true, _data: this.createZeroedMonths() };
            }
            this.accumulateValues(currentLevel[contaKey]._data, row);
        });

        return root;
    }

    createZeroedMonths() {
        return { Jan:0, Fev:0, Mar:0, Abr:0, Mai:0, Jun:0, Jul:0, Ago:0, Set:0, Out:0, Nov:0, Dez:0, Total_Ano:0 };
    }

    accumulateValues(target, source) {
        const keys = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez', 'Total_Ano'];
        keys.forEach(k => { target[k] += (parseFloat(source[k]) || 0); });
    }

    renderTreeTable(treeData) {
        const rowsHtml = this.renderTreeNodes(treeData, 0);
        return `
            <style>
                .bi-table { width: 100%; border-collapse: collapse; font-family: 'Segoe UI', sans-serif; font-size: 0.85rem; }
                .bi-table th { background: #1e1e2f; color: #fff; padding: 10px; position: sticky; top: 0; z-index: 10; text-align: right; border-bottom: 2px solid #444; }
                .bi-table th:first-child { text-align: left; min-width: 350px; padding-left: 20px; }
                .bi-row { border-bottom: 1px solid rgba(255,255,255,0.05); cursor: pointer; transition: background 0.2s; }
                .bi-row:hover { background: rgba(255,255,255,0.08); }
                .level-0 { background: #2b2b3c; font-weight: bold; color: #ffd700; }
                .level-1 { background: #252535; font-weight: 600; color: #8be9fd; }
                .level-2 { background: #20202e; color: #f8f8f2; }
                .level-3 { background: #1a1a24; color: #bd93f9; }
                .bi-cell { padding: 8px; text-align: right; white-space: nowrap; border-right: 1px solid rgba(255,255,255,0.02); }
                .bi-name { text-align: left; border-right: none;}
                .toggle-icon { display: inline-block; width: 20px; text-align: center; margin-right: 5px; transition: transform 0.2s; }
                .text-neg { color: #ff5555; } .text-pos { color: #50fa7b; } .text-zero { color: #666; }
            </style>
            <div class="table-fixed-container" style="height: 70vh;">
                <table class="bi-table">
                    <thead><tr><th>Estrutura / Conta</th><th>Jan</th><th>Fev</th><th>Mar</th><th>Abr</th><th>Mai</th><th>Jun</th><th>Jul</th><th>Ago</th><th>Set</th><th>Out</th><th>Nov</th><th>Dez</th><th style="background: #2a2a3a;">Total</th></tr></thead>
                    <tbody>${rowsHtml}</tbody>
                </table>
            </div>`;
    }

    renderTreeNodes(nodes, level, parentId = 'root') {
        let html = '';
        const months = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez', 'Total_Ano'];

        Object.keys(nodes).sort().forEach((key, index) => {
            const node = nodes[key];
            const isLeaf = node._isLeaf;
            const uniqueId = `${parentId}-${index}`;
            const padding = level * 25; 
            const values = node._data;
            
            const cellsHtml = months.map(m => {
                const val = values[m];
                let colorClass = val < 0 ? 'text-neg' : (val > 0 ? 'text-pos' : 'text-zero');
                return `<td class="bi-cell ${colorClass}">${val === 0 ? '-' : FormatUtils.formatNumber(val)}</td>`;
            }).join('');

            let icon = isLeaf ? '<i class="fas fa-file-invoice toggle-icon" style="opacity:0.3; font-size: 0.8em;"></i>' : `<i id="icon-${uniqueId}" class="fas fa-chevron-right toggle-icon"></i>`;
            let clickAction = isLeaf ? '' : `onclick="window.toggleBiRow('${uniqueId}')"`;
            const rowDisplay = level === 0 ? 'table-row' : 'none'; 
            
            // Ajuste para não quebrar cores em níveis profundos
            const levelClass = level > 3 ? 3 : level;

            html += `<tr class="bi-row level-${levelClass}" data-id="${uniqueId}" data-parent="${parentId}" style="display: ${rowDisplay}" ${clickAction}><td class="bi-cell bi-name" style="padding-left: ${10 + padding}px;">${icon} ${key}</td>${cellsHtml}</tr>`;

            if (!isLeaf && node._children) {
                html += this.renderTreeNodes(node._children, level + 1, uniqueId);
            }
        });
        return html;
    }

    handleBiToggle(id) {
        const children = document.querySelectorAll(`[data-parent="${id}"]`);
        const icon = document.getElementById(`icon-${id}`);
        if (children.length === 0) return;
        const isClosed = children[0].style.display === 'none';

        if (isClosed) {
            children.forEach(child => child.style.display = 'table-row');
            if(icon) { icon.className = 'fas fa-chevron-down toggle-icon'; icon.style.transform = 'rotate(0deg)'; }
        } else {
            this.closeChildrenRecursively(id);
            if(icon) { icon.className = 'fas fa-chevron-right toggle-icon'; }
        }
    }

    closeChildrenRecursively(parentId) {
        const children = document.querySelectorAll(`[data-parent="${parentId}"]`);
        children.forEach(child => {
            child.style.display = 'none';
            const childId = child.getAttribute('data-id');
            const icon = document.getElementById(`icon-${childId}`);
            if(icon) icon.className = 'fas fa-chevron-right toggle-icon';
            this.closeChildrenRecursively(childId);
        });
    }

    expandAll() {
        const allRows = document.querySelectorAll('.bi-row');
        allRows.forEach(row => row.style.display = 'table-row');
        const allIcons = document.querySelectorAll('.toggle-icon.fa-chevron-right');
        allIcons.forEach(icon => icon.className = 'fas fa-chevron-down toggle-icon');
    }

    exportToExcel() { NotificationSystem.show('Em breve...', 'info'); }
    exportToPDF() { NotificationSystem.show('Em breve...', 'info'); }
}

let relatorioSystem;
document.addEventListener('DOMContentLoaded', () => {
    relatorioSystem = new RelatorioSystem();
    window.relatorioSystem = relatorioSystem;
});
window.fecharModal = () => window.relatorioSystem.modal.close();