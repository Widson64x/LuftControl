// ============================================================================
// T-Controllership - SISTEMA DE RELATÓRIOS FINANCEIROS
// Arquivo: Static/js/Relatorios.js
// VERSÃO CORRIGIDA - Inicialização robusta
// ============================================================================

// Guard contra múltiplas inicializações
if (typeof window.relatorioSystemInitialized === 'undefined') {
    window.relatorioSystemInitialized = true;

class RelatorioSystem {
    constructor() {
        this.modal = null;
        
        // Estado Razão
        this.currentData = null;
        this.currentPage = 1;
        this.totalPages = 1;
        this.currentSearch = ''; 
        this.searchTimeout = null; 
        this.sortState = { column: -1, ascending: true };

        // Estado BI (Rentabilidade / DRE)
        this.cachedBiData = null;     
        this.biViewMode = 'direct';

        this.init();
    }

    init() {
        // Aguarda DOM estar pronto
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupSystem());
        } else {
            this.setupSystem();
        }
    }

    setupSystem() {
        // Inicializa modal
        this.modal = new ModalSystem('modalRelatorio');
        
        // Hooks globais
        window.toggleBiRow = (id) => this.handleBiToggle(id);
        
        console.log('✅ RelatorioSystem Inicializado');
    }

    // =========================================================================
    // PARTE 1: RELATÓRIO DE RAZÃO (BASE COMPLETA)
    // =========================================================================
    async loadRazaoReport(page = 1) {
        // Garante que modal está inicializado
        if (!this.modal) {
            this.modal = new ModalSystem('modalRelatorio');
        }

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
                    <button class="btn btn-secondary btn-sm" onclick="window.relatorioSystem.loadRazaoReport(${this.currentPage - 1})" ${isFirst ? 'disabled' : ''}><i class="fas fa-chevron-left"></i> Anterior</button>
                    <button class="btn btn-secondary btn-sm" onclick="window.relatorioSystem.loadRazaoReport(${this.currentPage + 1})" ${isLast ? 'disabled' : ''}>Próxima <i class="fas fa-chevron-right"></i></button>
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

        return `<div class="table-fixed-container"><table class="table-modern table-hover table-fixed-header" id="razaoTable" style="min-width: 1600px;"><thead><tr><th onclick="window.relatorioSystem.sortColumn(0)">Conta</th><th>Título</th><th>Data</th><th>Núm.</th><th>Histórico</th><th>Débito</th><th>Crédito</th><th>Saldo</th><th>Filial</th><th>C.C.</th><th>Centro Custo</th><th>Origem</th></tr></thead><tbody>${rows}</tbody></table></div><div class="mt-2 text-end text-muted"><small>Exibindo ${data.length} de ${metaData.total_registros} registros.</small></div>`;
    }

    sortColumn(columnIndex) {
        const table = document.getElementById('razaoTable');
        if (!table) return;
        if (this.sortState.column === columnIndex) this.sortState.ascending = !this.sortState.ascending;
        else { this.sortState.column = columnIndex; this.sortState.ascending = true; }
        TableUtils.sortTable(table, columnIndex, this.sortState.ascending);
    }

    // =========================================================================
    // PARTE 2: RELATÓRIO DRE / RENTABILIDADE (BI TREE GRID)
    // =========================================================================

    async loadRentabilidadeReport() {
        // Garante que modal está inicializado
        if (!this.modal) {
            this.modal = new ModalSystem('modalRelatorio');
        }

        this.modal.open('📊 Análise de Rentabilidade');
        this.modal.showLoading('Calculando estrutura e saldos...');

        try {
            const response = await APIUtils.get(`/Reports/RelatorioRazao/Rentabilidade`);
            this.cachedBiData = response || [];
            
            if (this.cachedBiData.length === 0) {
                this.modal.setContent('<div class="alert alert-warning">Nenhuma conta vinculada encontrada para exibição. Verifique a Configuração de Hierarquia.</div>');
                return;
            }
            this.renderBiView();
        } catch (error) {
            console.error(error);
            this.modal.showError(`Erro ao gerar BI: ${error.message}`);
        }
    }

    renderBiView() {
        const treeData = this.buildHierarchy(this.cachedBiData);
        const tableHtml = this.renderTreeTable(treeData);
        
        const controlsHtml = `
            <div class="d-flex justify-content-between align-items-center mb-3" style="background: rgba(0,0,0,0.2); padding: 10px; border-radius: 8px;">
                <div>
                    <span class="text-white font-bold ms-2"><i class="fas fa-stream"></i> Visão DRE Gerencial</span>
                    <small class="text-muted ms-2">(Contas cadastradas e ordenadas)</small>
                </div>
                <div class="btn-group">
                    <button class="btn btn-sm btn-outline-light" onclick="window.relatorioSystem.expandAll()"><i class="fas fa-expand-arrows-alt"></i> Expandir Tudo</button>
                    <button class="btn btn-sm btn-outline-light" onclick="window.relatorioSystem.collapseAll()"><i class="fas fa-compress-arrows-alt"></i> Recolher Tudo</button>
                </div>
            </div>`;

        this.modal.setContent(controlsHtml + tableHtml);
    }

    buildHierarchy(data) {
        const root = {};

        data.forEach(row => {
            let levels = [];

            levels.push(row.Tipo_CC || 'Outros');

            const subgruposRaw = row.Caminho_Subgrupos;
            if (subgruposRaw && subgruposRaw !== 'Não Classificado' && subgruposRaw !== 'Direto') {
                const dynamicLevels = subgruposRaw.split('||');
                levels = levels.concat(dynamicLevels);
            } else if (subgruposRaw === 'Não Classificado') {
                levels.push('Não Classificado');
            }

            let currentLevel = root;
            levels.forEach((key) => {
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

            const contaLabel = `📄 ${row.Conta} - ${row.Titulo_Conta || 'Sem Título'}`; 
            
            if (!currentLevel[contaLabel]) {
                currentLevel[contaLabel] = { _isLeaf: true, _data: this.createZeroedMonths() };
            }
            this.accumulateValues(currentLevel[contaLabel]._data, row);
        });

        return root;
    }

    createZeroedMonths() {
        return { Jan:0, Fev:0, Mar:0, Abr:0, Mai:0, Jun:0, Jul:0, Ago:0, Set:0, Out:0, Nov:0, Dez:0, Total_Ano:0 };
    }

    accumulateValues(target, source) {
        const keys = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez', 'Total_Ano'];
        keys.forEach(k => { 
            target[k] += (parseFloat(source[k]) || 0); 
        });
    }

    renderTreeTable(treeData) {
        const rowsHtml = this.renderTreeNodes(treeData, 0);
        return `
            <style>
                .bi-table { width: 100%; border-collapse: collapse; font-family: 'Inter', sans-serif; font-size: 0.85rem; }
                .bi-table th { background: #1e1e2f; color: #fff; padding: 12px 8px; position: sticky; top: 0; z-index: 10; text-align: right; border-bottom: 2px solid #444; font-weight: 600; }
                .bi-table th:first-child { text-align: left; min-width: 400px; padding-left: 20px; }
                
                .bi-row { border-bottom: 1px solid rgba(255,255,255,0.05); cursor: pointer; transition: background 0.15s; }
                .bi-row:hover { background: rgba(255,255,255,0.08); }
                
                .level-0 { background: #252530; font-weight: 800; color: #ffca28; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid rgba(255,255,255,0.1); }
                .level-1 { background: #20202a; font-weight: 700; color: #90caf9; }
                .level-2 { background: #1a1a22; font-weight: 600; color: #e0e0e0; }
                .level-3 { font-weight: normal; color: #b0bec5; font-size: 0.9em; font-style: italic;}
                
                .bi-cell { padding: 8px; text-align: right; white-space: nowrap; border-right: 1px solid rgba(255,255,255,0.02); }
                .bi-name { text-align: left; border-right: none; display: flex; align-items: center;}
                
                .toggle-icon { margin-right: 8px; width: 16px; text-align: center; transition: transform 0.2s; opacity: 0.7; }
                .text-neg { color: #ff5252; } .text-pos { color: #69f0ae; } .text-zero { color: #555; }
            </style>
            <div class="table-fixed-container" style="height: 75vh;">
                <table class="bi-table">
                    <thead><tr><th>Estrutura DRE</th><th>Jan</th><th>Fev</th><th>Mar</th><th>Abr</th><th>Mai</th><th>Jun</th><th>Jul</th><th>Ago</th><th>Set</th><th>Out</th><th>Nov</th><th>Dez</th><th style="background: #333;">Total</th></tr></thead>
                    <tbody>${rowsHtml}</tbody>
                </table>
            </div>`;
    }

    renderTreeNodes(nodes, level, parentId = 'root') {
        let html = '';
        const months = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez', 'Total_Ano'];

        Object.keys(nodes).forEach((key, index) => {
            const node = nodes[key];
            const isLeaf = node._isLeaf;
            const uniqueId = `${parentId}-${index}`;
            
            const padding = level * 24; 
            const values = node._data;
            
            const cellsHtml = months.map(m => {
                const val = values[m];
                let colorClass = val < 0 ? 'text-neg' : (val > 0 ? 'text-pos' : 'text-zero');
                const formatted = val === 0 ? '-' : new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val);
                return `<td class="bi-cell ${colorClass}">${formatted}</td>`;
            }).join('');

            let icon = isLeaf ? '<i class="fas fa-file-alt toggle-icon" style="font-size: 0.8em;"></i>' : `<i id="icon-${uniqueId}" class="fas fa-chevron-right toggle-icon"></i>`;
            let clickAction = isLeaf ? '' : `onclick="window.toggleBiRow('${uniqueId}')"`;
            
            const rowDisplay = level === 0 ? 'table-row' : 'none';
            
            if(level === 0 && !isLeaf) {
                icon = `<i id="icon-${uniqueId}" class="fas fa-chevron-down toggle-icon"></i>`;
            }

            const levelClass = isLeaf ? 'level-3' : `level-${Math.min(level, 2)}`;

            html += `
                <tr class="bi-row ${levelClass}" data-id="${uniqueId}" data-parent="${parentId}" style="display: ${rowDisplay}" ${clickAction}>
                    <td class="bi-cell bi-name" style="padding-left: ${10 + padding}px;">
                        ${icon} <span>${key}</span>
                    </td>
                    ${cellsHtml}
                </tr>`;

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
            if(icon) {
                icon.classList.remove('fa-chevron-right');
                icon.classList.add('fa-chevron-down');
            }
        } else {
            this.closeChildrenRecursively(id);
            if(icon) {
                icon.classList.remove('fa-chevron-down');
                icon.classList.add('fa-chevron-right');
            }
        }
    }

    closeChildrenRecursively(parentId) {
        const children = document.querySelectorAll(`[data-parent="${parentId}"]`);
        children.forEach(child => {
            child.style.display = 'none';
            const childId = child.getAttribute('data-id');
            
            const icon = document.getElementById(`icon-${childId}`);
            if(icon && icon.classList.contains('fa-chevron-down')) {
                icon.classList.remove('fa-chevron-down');
                icon.classList.add('fa-chevron-right');
            }
            
            this.closeChildrenRecursively(childId);
        });
    }

    expandAll() {
        const allRows = document.querySelectorAll('.bi-row');
        allRows.forEach(row => row.style.display = 'table-row');
        const allIcons = document.querySelectorAll('.toggle-icon.fa-chevron-right');
        allIcons.forEach(icon => {
            icon.classList.remove('fa-chevron-right');
            icon.classList.add('fa-chevron-down');
        });
    }

    collapseAll() {
        const allRows = document.querySelectorAll('.bi-row');
        allRows.forEach(row => {
            if (row.getAttribute('data-parent') !== 'root') {
                row.style.display = 'none';
            }
        });
        const allIcons = document.querySelectorAll('.toggle-icon.fa-chevron-down');
        allIcons.forEach(icon => {
            icon.classList.remove('fa-chevron-down');
            icon.classList.add('fa-chevron-right');
        });
        
        const rootIcons = document.querySelectorAll('[data-parent="root"] .toggle-icon');
        rootIcons.forEach(icon => {
            icon.classList.remove('fa-chevron-right');
            icon.classList.add('fa-chevron-down');
        });
    }

    exportToExcel() { NotificationSystem.show('Em breve...', 'info'); }
    exportToPDF() { NotificationSystem.show('Em breve...', 'info'); }
}

// Cria instância global IMEDIATAMENTE
window.relatorioSystem = new RelatorioSystem();

// Função auxiliar global
window.fecharModal = function() {
    if (window.relatorioSystem && window.relatorioSystem.modal) {
        window.relatorioSystem.modal.close();
    }
};

} // Fim do guard