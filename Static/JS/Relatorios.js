// ============================================
// DRE CONTROL SYSTEM - RELATÓRIOS
// Arquivo: Static/js/Relatorios.js
// ============================================

class RelatorioSystem {
    constructor() {
        this.modal = new ModalSystem('modalRelatorio');
        this.currentData = null;
        this.currentPage = 1;
        this.totalPages = 1;
        this.currentSearch = ''; // Armazena o termo atual
        this.searchTimeout = null; // Timer para o debounce
        this.sortState = { column: -1, ascending: true };
        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.setupEventListeners();
        });
    }

    setupEventListeners() {
        // Listeners são gerenciados dinamicamente
    }

    /**
     * Carrega o relatório com paginação e busca global
     */
    async loadRazaoReport(page = 1) {
        this.currentPage = page;
        
        // Títulos dinâmicos
        let title = '📈 Relatório de Razão';
        if (this.currentSearch) title += ` - Buscando: "${this.currentSearch}"`;

        // Abre modal apenas se for a primeira carga
        if (page === 1 && !document.querySelector('.table-fixed-container')) {
            this.modal.open(title);
            this.modal.showLoading('Buscando dados no servidor...');
        } else {
            // Feedback visual suave se já estiver com a tabela aberta
            const table = document.getElementById('razaoTable');
            if (table) table.style.opacity = '0.5';
        }

        try {
            // Codifica o termo de busca
            const encodedSearch = encodeURIComponent(this.currentSearch);
            
            // Chama API com Search e Page
            const response = await APIUtils.get(`/Reports/RelatorioRazao/Dados?page=${page}&search=${encodedSearch}`);
            
            const data = response.dados || [];
            this.totalPages = response.total_paginas || 1;
            this.currentData = data;

            // Renderiza passando os DADOS e os METADADOS (Totais, Paginas, etc)
            this.renderRazaoReport(data, response);
            
            // Volta o scroll pro topo da tabela
            const container = document.querySelector('.table-fixed-container');
            if (container) container.scrollTop = 0;

        } catch (error) {
            console.error('Erro:', error);
            this.modal.showError(`Erro na busca: ${error.message}`);
        }
    }

    /**
     * Renderiza todos os componentes do relatório
     */
    renderRazaoReport(data, metaData) {
        const totals = this.calculateTotals(data);
        
        const summaryHtml = this.renderSummaryCards(totals, metaData.total_registros);
        
        // Passando metaData para a função da tabela
        const tableHtml = this.renderRazaoTable(data, metaData); 
        
        const paginationHtml = this.renderPaginationControls();

        this.modal.setContent(summaryHtml + paginationHtml + tableHtml);
        
        // Re-atachar listener de busca com Debounce
        setTimeout(() => {
             const searchInput = document.getElementById('serverSearch');
             if(searchInput) {
                 searchInput.value = this.currentSearch;
                 searchInput.focus();

                 searchInput.addEventListener('input', (e) => {
                     clearTimeout(this.searchTimeout);
                     this.searchTimeout = setTimeout(() => {
                         this.currentSearch = e.target.value;
                         this.loadRazaoReport(1); // Volta para pág 1 ao pesquisar
                     }, 800); // Espera 800ms após parar de digitar
                 });
             }
        }, 100);
    }

    renderPaginationControls() {
        // Se não houver páginas para navegar (0 ou 1), esconde os controles
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
                    <button class="btn btn-secondary btn-sm" 
                            onclick="relatorioSystem.loadRazaoReport(${this.currentPage - 1})"
                            ${isFirst ? 'disabled' : ''}>
                        <i class="fas fa-chevron-left"></i> Anterior
                    </button>
                    
                    <button class="btn btn-secondary btn-sm" 
                            onclick="relatorioSystem.loadRazaoReport(${this.currentPage + 1})"
                            ${isLast ? 'disabled' : ''}>
                        Próxima <i class="fas fa-chevron-right"></i>
                    </button>
                </div>
            </div>
        `;
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
                <div class="summary-card">
                    <div class="summary-label">
                        ${this.currentSearch ? 'Registros Encontrados' : 'Total da Base'}
                    </div>
                    <div class="summary-value">${FormatUtils.formatNumber(totalGlobal)}</div>
                    <div class="summary-change positive"><i class="fas fa-database"></i> Server-Side</div>
                </div>
                <div class="summary-card">
                    <div class="summary-label">Débito (Página Atual)</div>
                    <div class="summary-value text-danger">${FormatUtils.formatCurrency(totals.debito)}</div>
                </div>
                <div class="summary-card">
                    <div class="summary-label">Crédito (Página Atual)</div>
                    <div class="summary-value text-success">${FormatUtils.formatCurrency(totals.credito)}</div>
                </div>
                <div class="summary-card">
                    <div class="summary-label">Saldo (Página Atual)</div>
                    <div class="summary-value ${totals.saldo >= 0 ? 'text-success' : 'text-danger'}">
                        ${FormatUtils.formatCurrency(totals.saldo)}
                    </div>
                </div>
            </div>
            
            <div class="d-flex justify-between align-items-center mb-2">
                 <div class="input-group" style="max-width: 400px; min-width: 300px;">
                    <i class="input-group-icon fas fa-search"></i>
                    <input type="text" 
                           id="serverSearch" 
                           class="form-control" 
                           placeholder="🔍 Pesquisar em toda a base (Conta, Histórico, Valor)...">
                </div>
                <div class="text-muted text-end ms-3">
                    <small><i class="fas fa-info-circle"></i> A busca é realizada em todo o banco de dados.</small>
                </div>
            </div>
        `;
    }

    // CORREÇÃO AQUI: Adicionado o parâmetro metaData
    renderRazaoTable(data, metaData) {
        if (!data || data.length === 0) {
            return `
                <div class="alert alert-info text-center mt-4">
                    <h4><i class="fas fa-search"></i> Nenhum resultado encontrado</h4>
                    <p>Tente buscar por outro termo (conta, valor ou descrição).</p>
                </div>
            `;
        }

        const rows = data.map(item => `
            <tr>
                <td>${item.conta || '-'}</td>
                <td><small>${item.titulo_conta || '-'}</small></td>
                <td>${FormatUtils.formatDate(item.data)}</td>
                <td>${item.numero || ''}</td>
                <td><small>${item.descricao || '-'}</small></td>
                <td class="text-danger">${FormatUtils.formatCurrency(item.debito)}</td>
                <td class="text-success">${FormatUtils.formatCurrency(item.credito)}</td>
                <td class="${item.saldo >= 0 ? 'text-success' : 'text-danger'} font-bold">
                    ${FormatUtils.formatCurrency(item.saldo)}
                </td>
                <td>${item.filial_id || '-'}</td> 
                <td>${item.cc_cod || ''}</td>
                <td>${item.nome_cc || '-'}</td>
                <td>${item.origem || '-'}</td>
                <td><small>${item.cliente || '-'}</small></td>
                <td>${item.filial_cliente || '-'}</td>
                <td class="text-muted text-xs">${item.chv_mes_conta || ''}</td>
                <td class="text-muted text-xs">${item.chv_conta_cc || ''}</td>
                <td class="text-muted text-xs">${item.chv_mes_conta_cc || ''}</td>
                <td class="text-muted text-xs">${item.chv_mes_nomecc_conta || ''}</td>
                <td class="text-muted text-xs">${item.chv_mes_nomecc_conta_cc || ''}</td>
                <td class="text-muted text-xs">${item.chv_conta_formatada || ''}</td>
            </tr>
        `).join('');

        return `
            <style>
                .table-fixed-container {
                    height: 65vh;
                    overflow: auto;
                    border: 1px solid rgba(255,255,255,0.1);
                    border-radius: 8px;
                    background: var(--bg-card);
                    position: relative;
                    width: 100%;
                }
                .table-fixed-header th {
                    position: sticky;
                    top: 0;
                    background: #1e1e2f;
                    z-index: 100;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.3);
                    padding: 12px;
                }
                .table-fixed-container::-webkit-scrollbar { width: 12px; height: 12px; }
                .table-fixed-container::-webkit-scrollbar-track { background: #20202a; border-radius: 4px; }
                .table-fixed-container::-webkit-scrollbar-thumb { background: #4b4b5a; border-radius: 6px; border: 2px solid #20202a; }
                .text-xs { font-size: 0.7rem; opacity: 0.7; }
            </style>

            <div class="table-fixed-container">
                <table class="table-modern table-hover table-fixed-header" id="razaoTable" style="min-width: 2800px;">
                    <thead>
                        <tr>
                            <th onclick="relatorioSystem.sortColumn(0)">Conta <i class="fas fa-sort"></i></th>
                            <th onclick="relatorioSystem.sortColumn(1)">Título <i class="fas fa-sort"></i></th>
                            <th onclick="relatorioSystem.sortColumn(2)">Data <i class="fas fa-sort"></i></th>
                            <th>Núm.</th>
                            <th>Histórico</th>
                            <th onclick="relatorioSystem.sortColumn(5)">Débito <i class="fas fa-sort"></i></th>
                            <th onclick="relatorioSystem.sortColumn(6)">Crédito <i class="fas fa-sort"></i></th>
                            <th onclick="relatorioSystem.sortColumn(7)">Saldo <i class="fas fa-sort"></i></th>
                            <th>Filial</th>
                            <th>C.C.</th>
                            <th>Centro Custo</th>
                            <th>Origem</th>
                            <th>Cliente</th>
                            <th>Filial Cli.</th>
                            <th>Chv. Mes/Conta</th>
                            <th>Chv. Conta/CC</th>
                            <th>Chv. Mes/Conta/CC</th>
                            <th>Chv. Mes/NomeCC/Conta</th>
                            <th>Chv. Mes/NomeCC/Conta/CC</th>
                            <th>Chv. Conta Format.</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows}
                    </tbody>
                </table>
            </div>
            <div class="mt-2 text-end text-muted">
                <small>Exibindo ${data.length} de ${metaData.total_registros} registros.</small>
            </div>
        `;
    }

    sortColumn(columnIndex) {
        const table = document.getElementById('razaoTable');
        if (!table) return;
        
        if (this.sortState.column === columnIndex) {
            this.sortState.ascending = !this.sortState.ascending;
        } else {
            this.sortState.column = columnIndex;
            this.sortState.ascending = true;
        }
        TableUtils.sortTable(table, columnIndex, this.sortState.ascending);
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