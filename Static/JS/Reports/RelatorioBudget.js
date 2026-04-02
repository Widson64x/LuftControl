// ============================================================================
// Luft Control - MÓDULO: BUDGET
// Arquivo: Static/JS/Reports/RelatorioBudget.js
// Design System: LuftCore
// ============================================================================

class RelatorioBudget {
    /**
     * Inicializa o gerenciador do relatório de Budget.
     * @param {Object} modalSystem - Instância do wrapper de modais do LuftCore.
     */
    constructor(modalSystem) {
        this.modal = modalSystem;
        this.dadosBrutos = [];
        this.anoSelecionado = new Date().getFullYear();
    }

    /**
     * Busca os dados na API e orquestra a abertura do modal e exibição de carregamento.
     */
    async carregarRelatorio() {
        if (!this.modal) {
            this.modal = new LuftModalWrapper('modalRelatorio');
        }

        this.modal.open('<i class="fas fa-wallet text-primary"></i> Budget Gerencial', `Ano base: ${this.anoSelecionado}`);
        this.modal.showLoading('Calculando painel de orçamento...');

        try {
            const urlBase = (typeof API_ROUTES !== 'undefined' && API_ROUTES.getBudgetData) 
                            ? API_ROUTES.getBudgetData 
                            : '/Relatorios/budget/gerencial';

            const dados = await APIUtils.get(`${urlBase}?ano=${this.anoSelecionado}`);

            if (!dados || dados.length === 0) {
                this.dadosBrutos = [];
                this.renderizarInterface(true);
                return;
            }

            this.dadosBrutos = dados;
            this.renderizarInterface(false);

        } catch (erro) {
            console.error(erro);
            this.modal.showError(erro);
        }
    }

    /**
     * Atualiza o ano no estado e recarrega a requisição.
     * @param {string|number} ano - Ano para buscar o relatório.
     */
    alterarAno(ano) {
        this.anoSelecionado = ano;
        this.carregarRelatorio();
    }

    /**
     * Monta o HTML do relatório injetando os componentes visuais do LuftCore no modal.
     * @param {boolean} vazio - Indica se a tela de estado vazio deve ser exibida.
     */
    renderizarInterface(vazio = false) {
        const barraFerramentas = `
            <div class="luft-dre-toolbar">
                <div class="d-flex gap-2 align-items-center">
                    <select class="luft-year-selector" onchange="relatorioSystem.relatorioBudget.alterarAno(this.value)">
                        <option value="2025" ${this.anoSelecionado == 2025 ? 'selected' : ''}>2025</option>
                        <option value="2026" ${this.anoSelecionado == 2026 ? 'selected' : ''}>2026</option>
                    </select>
                </div>
            </div>`;

        let conteudoTabela = '';

        if (vazio) {
            conteudoTabela = `
                <div class="luft-hub-empty" style="flex: 1; border: none; border-radius: 0;">
                    <i class="fas fa-folder-open text-muted mb-3" style="font-size: 3rem;"></i>
                    <h4 class="text-main font-bold">Sem dados orçamentários</h4>
                    <p class="text-muted">Nenhum planejamento encontrado para este ano.</p>
                </div>`;
        } else {
            const linhas = this.dadosBrutos.map(linha => {
                const corDesvio = linha.Desvio < 0 ? 'text-danger' : 'text-success';
                const formatadorMoeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
                
                return `
                    <tr>
                        <td><i class="fas fa-building text-muted" style="margin-right: 8px;"></i> ${linha.Centro_Custo}</td>
                        <td class="text-end font-monospace">${formatadorMoeda.format(linha.Orcado)}</td>
                        <td class="text-end font-monospace">${formatadorMoeda.format(linha.Realizado)}</td>
                        <td class="text-end font-monospace font-bold ${corDesvio}">${formatadorMoeda.format(linha.Desvio)}</td>
                    </tr>
                `;
            }).join('');

            conteudoTabela = `
                <div class="luft-table-container" style="flex: 1; padding: 0;">
                    <table class="luft-table-modern">
                        <thead>
                            <tr>
                                <th>Centro de Custo</th>
                                <th class="text-end">Orçado</th>
                                <th class="text-end">Realizado</th>
                                <th class="text-end">Desvio</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${linhas}
                        </tbody>
                    </table>
                </div>`;
        }

        const rodape = `
            <div class="luft-dre-footer">
                <span>Visão: <strong>Sintético</strong> | Orçamento Geral</span>
                <span>Atualizado: ${new Date().toLocaleTimeString('pt-BR')}</span>
            </div>`;

        this.modal.setContent(`<div style="display: flex; flex-direction: column; height: 100%;">${barraFerramentas}${conteudoTabela}${rodape}</div>`);
    }
}