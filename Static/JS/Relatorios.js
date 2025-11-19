// ============================================
// DRE CONTROL SYSTEM - RELATÓRIOS
// Arquivo: Static/js/relatorios.js
// ============================================

/**
 * Sistema de Relatórios
 * Gerencia carregamento, renderização e exportação de relatórios
 */
class RelatorioSystem {
    constructor() {
        this.modal = new ModalSystem('modalRelatorio');
        this.currentData = null;
    }

    /**
     * Carrega relatório de Razão Consolidada
     */
    async carregarRazao() {
        this.modal.open('📈 Relatório de Razão Consolidada');
        this.modal.showLoading('Buscando dados do relatório...');

        try {
            const dados = await APIUtils.get('/Rentabilidade/RelatorioRazao');

            if (!dados || dados.length === 0) {
                this.modal.showEmpty('Nenhum registro encontrado no relatório');
                return;
            }

            this.currentData = dados;
            this.renderizarRelatorioRazao(dados);
            NotificationSystem.show('Relatório carregado com sucesso!', 'success');

        } catch (error) {
            console.error('Erro ao carregar relatório:', error);
            this.modal.showError(error.message);
            NotificationSystem.show('Erro ao carregar relatório', 'danger');
        }
    }

    /**
     * Renderiza o Relatório de Razão
     */
    renderizarRelatorioRazao(dados) {
        const totais = this.calcularTotais(dados);
        const summaryHtml = this.renderSummaryCards(totais, dados.length);
        const tableHtml = this.renderTableRazao(dados);
        
        this.modal.setContent(summaryHtml + tableHtml);
        this.setupTableFeatures();
    }

    /**
     * Calcula totais do relatório
     */
    calcularTotais(dados) {
        return dados.reduce((acc, item) => {
            acc.debito += item.debito || 0;
            acc.credito += item.credito || 0;
            acc.saldo += item.saldo || 0;
            return acc;
        }, { debito: 0, credito: 0, saldo: 0 });
    }

    /**
     * Renderiza cards de resumo
     */
    renderSummaryCards(totais, totalRegistros) {
        return `
            <div class="d-grid" style="grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1.5rem; margin-bottom: 2rem;">
                <div class="summary-card">
                    <div class="summary-label">Total de Registros</div>
                    <div class="summary-value">${FormatUtils.formatNumber(totalRegistros)}</div>
                    <div class="summary-change positive">
                        <i class="fas fa-chart-line"></i>
                        <span>Registros carregados</span>
                    </div>
                </div>

                <div class="summary-card">
                    <div class="summary-label">Total Débito</div>
                    <div class="summary-value text-danger">${FormatUtils.formatCurrency(totais.debito)}</div>
                    <div class="summary-change negative">
                        <i class="fas fa-arrow-down"></i>
                        <span>Saídas</span>
                    </div>
                </div>

                <div class="summary-card">
                    <div class="summary-label">Total Crédito</div>
                    <div class="summary-value text-success">${FormatUtils.formatCurrency(totais.credito)}</div>
                    <div class="summary-change positive">
                        <i class="fas fa-arrow-up"></i>
                        <span>Entradas</span>
                    </div>
                </div>

                <div class="summary-card">
                    <div class="summary-label">Saldo Total</div>
                    <div class="summary-value ${totais.saldo >= 0 ? 'text-success' : 'text-danger'}">
                        ${FormatUtils.formatCurrency(totais.saldo)}
                    </div>
                    <div class="summary-change ${totais.saldo >= 0 ? 'positive' : 'negative'}">
                        <i class="fas fa-${totais.saldo >= 0 ? 'check-circle' : 'exclamation-circle'}"></i>
                        <span>${totais.saldo >= 0 ? 'Positivo' : 'Negativo'}</span>
                    </div>
                </div>
            </div>

            <div class="d-flex align-items-center gap-md mb-4">
                <div style="flex: 1;">
                    <div class="input-group">
                        <i class="input-group-icon fas fa-search"></i>
                        <input type="text" 
                               id="searchTable" 
                               class="form-control" 
                               placeholder="🔍 Buscar na tabela...">
                    </div>
                </div>
                <button onclick="relatorioSystem.exportarExcel()" class="btn btn-secondary">
                    <i class="fas fa-file-excel"></i> Exportar Excel
                </button>
                <button onclick="relatorioSystem.exportarPDF()" class="btn btn-secondary">
                    <i class="fas fa-file-pdf"></i> Exportar PDF
                </button>
            </div>
        `;
    }

    /**
     * Renderiza tabela do relatório
     */
    renderTableRazao(dados) {
        const rows = dados.map(item => `
            <tr>
                <td>${item.conta || '-'}</td>
                <td>${item.titulo_conta || '-'}</td>
                <td>${FormatUtils.formatDate(item.data)}</td>
                <td>${item.cc_cod || '-'}</td>
                <td>${item.nome_cc || '-'}</td>
                <td class="text-danger">${FormatUtils.formatCurrency(item.debito)}</td>
                <td class="text-success">${FormatUtils.formatCurrency(item.credito)}</td>
                <td class="${item.saldo >= 0 ? 'text-success' : 'text-danger'}">
                    ${FormatUtils.formatCurrency(item.saldo)}
                </td>
                <td>${item.mes || '-'}</td>
                <td>
                    <span class="badge badge-${item.origem === 'FARMA' ? 'success' : 'info'}">
                        ${item.origem || 'N/A'}
                    </span>
                </td>
            </tr>
        `).join('');

        return `
            <div class="table-container">
                <table class="table" id="razaoTable">
                    <thead>
                        <tr>
                            <th onclick="relatorioSystem.sortColumn(0)">
                                Conta <i class="fas fa-sort"></i>
                            </th>
                            <th onclick="relatorioSystem.sortColumn(1)">
                                Título <i class="fas fa-sort"></i>
                            </th>
                            <th onclick="relatorioSystem.sortColumn(2)">
                                Data <i class="fas fa-sort"></i>
                            </th>
                            <th>CC Código</th>
                            <th>Centro de Custo</th>
                            <th onclick="relatorioSystem.sortColumn(5)">
                                Débito <i class="fas fa-sort"></i>
                            </th>
                            <th onclick="relatorioSystem.sortColumn(6)">
                                Crédito <i class="fas fa-sort"></i>
                            </th>
                            <th onclick="relatorioSystem.sortColumn(7)">
                                Saldo <i class="fas fa-sort"></i>
                            </th>
                            <th>Mês</th>
                            <th>Origem</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows}
                    </tbody>
                </table>
            </div>
        `;
    }

    /**
     * Configura funcionalidades da tabela
     */
    setupTableFeatures() {
        const searchInput = document.getElementById('searchTable');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.filterTable(e.target.value);
            });
        }

        this.sortState = { column: -1, ascending: true };
    }

    /**
     * Filtra tabela
     */
    filterTable(searchTerm) {
        const table = document.getElementById('razaoTable');
        if (!table) return;

        TableUtils.filterTable(table, searchTerm);

        // Atualiza contagem
        const visibleRows = table.querySelectorAll('tbody tr:not([style*="display: none"])');
        const totalRows = table.querySelectorAll('tbody tr');
        
        if (searchTerm) {
            NotificationSystem.show(
                `${visibleRows.length} de ${totalRows.length} registros encontrados`,
                'info',
                2000
            );
        }
    }

    /**
     * Ordena coluna da tabela
     */
    sortColumn(columnIndex) {
        const table = document.getElementById('razaoTable');
        if (!table) return;

        // Toggle sort direction
        if (this.sortState.column === columnIndex) {
            this.sortState.ascending = !this.sortState.ascending;
        } else {
            this.sortState.column = columnIndex;
            this.sortState.ascending = true;
        }

        TableUtils.sortTable(table, columnIndex, this.sortState.ascending);

        // Atualiza ícones
        table.querySelectorAll('th i').forEach(icon => {
            icon.className = 'fas fa-sort';
        });
        
        const th = table.querySelectorAll('th')[columnIndex];
        const icon = th.querySelector('i');
        if (icon) {
            icon.className = `fas fa-sort-${this.sortState.ascending ? 'up' : 'down'}`;
        }
    }

    /**
     * Exporta para Excel
     */
    exportarExcel() {
        NotificationSystem.show('Funcionalidade de exportação Excel em desenvolvimento', 'info');
        
        // TODO: Implementar exportação real
        // Sugestão: usar biblioteca como SheetJS (xlsx)
    }

    /**
     * Exporta para PDF
     */
    exportarPDF() {
        NotificationSystem.show('Funcionalidade de exportação PDF em desenvolvimento', 'info');
        
        // TODO: Implementar exportação real
        // Sugestão: usar biblioteca como jsPDF
    }

    /**
     * Carrega resumo de relatórios
     */
    async carregarResumo() {
        try {
            const resumo = await APIUtils.get('/Rentabilidade/RelatorioRazao/resumo');
            
            console.log('Resumo do relatório:', resumo);
            NotificationSystem.show('Resumo carregado com sucesso!', 'success');
            
            return resumo;
        } catch (error) {
            console.error('Erro ao carregar resumo:', error);
            NotificationSystem.show('Erro ao carregar resumo', 'danger');
            throw error;
        }
    }

    /**
     * Carrega relatório por mês
     */
    async carregarPorMes(mes) {
        this.modal.open(`📊 Relatório de Razão - ${mes}`);
        this.modal.showLoading(`Carregando dados de ${mes}...`);

        try {
            const dados = await APIUtils.get(`/Rentabilidade/RelatorioRazao/${mes}`);

            if (!dados || dados.dados.length === 0) {
                this.modal.showEmpty(`Nenhum registro encontrado para ${mes}`);
                return;
            }

            this.currentData = dados.dados;
            this.renderizarRelatorioRazao(dados.dados);
            NotificationSystem.show(`Dados de ${mes} carregados!`, 'success');

        } catch (error) {
            console.error('Erro ao carregar relatório por mês:', error);
            this.modal.showError(error.message);
            NotificationSystem.show('Erro ao carregar dados', 'danger');
        }
    }
}

// ============================================
// FUNÇÕES GLOBAIS PARA USO NO HTML
// ============================================

function carregarRelatorioRazao() {
    if (window.relatorioSystem) {
        window.relatorioSystem.carregarRazao();
    }
}

function fecharModal() {
    document.querySelectorAll('.modal-overlay').forEach(modal => {
        modal.classList.remove('active');
    });
    document.body.style.overflow = '';
}

// ============================================
// INICIALIZAÇÃO
// ============================================

let relatorioSystem;

document.addEventListener('DOMContentLoaded', () => {
    relatorioSystem = new RelatorioSystem();
    window.relatorioSystem = relatorioSystem;
    
    console.log('✅ Sistema de Relatórios inicializado');
});

// Exportar para uso global
window.RelatorioSystem = RelatorioSystem;
window.carregarRelatorioRazao = carregarRelatorioRazao;
window.fecharModal = fecharModal;