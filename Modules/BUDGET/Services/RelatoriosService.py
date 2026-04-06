from Db.Connections import GetSqlServerSession
from Modules.BUDGET.Reports.RelatorioBudget import RelatorioBudget

class RelatoriosService:
    """
    Serviço fachada para os relatórios do módulo de Budget.
    Centraliza o ciclo de vida da sessão e delega para as classes de report.
    """

    def _ObterSessao(self):
        return GetSqlServerSession()

    def obterFiltrosDisponiveis(self, ano, filtroCentroCusto='Todos', filtroContaContabil='Todos', filtroEmpresa='Todos'):
        sessao = self._ObterSessao()
        try:
            relatorio = RelatorioBudget(sessao)
            return relatorio.obterFiltrosDisponiveis(ano, filtroCentroCusto, filtroContaContabil, filtroEmpresa)
        finally:
            sessao.close()

    def gerarRelatorioBudget(self, ano, filtroCentroCusto='Todos', filtroContaContabil='Todos', filtroEmpresa='Todos'):
        sessao = self._ObterSessao()
        try:
            relatorio = RelatorioBudget(sessao)
            return relatorio.gerarRelatorioBudget(ano, filtroCentroCusto, filtroContaContabil, filtroEmpresa)
        finally:
            sessao.close()