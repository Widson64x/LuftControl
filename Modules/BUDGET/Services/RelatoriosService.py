from Db.Connections import GetSqlServerSession
from Modules.BUDGET.Reports.RelatorioBudget import RelatorioBudget
from Modules.SISTEMA.Services.CentroCustoConfigService import CentroCustoConfigService

class RelatoriosService:
    """
    Serviço fachada para os relatórios do módulo de Budget.
    Centraliza o ciclo de vida da sessão e delega para as classes de report.
    """

    def _ObterSessao(self):
        return GetSqlServerSession()

    def _resolverCentrosPermitidos(self, codigo_usuario):
        """Retorna a lista de CCs permitidos para o usuário, ou None quando não há restrição."""
        if not codigo_usuario:
            return None
        return CentroCustoConfigService().obterCentrosCustoDoGestor(codigo_usuario)

    def obterFiltrosDisponiveis(self, ano, filtroCentroCusto='Todos', filtroContaContabil='Todos', filtroEmpresa='Todos', codigo_usuario=None):
        centrosPermitidos = self._resolverCentrosPermitidos(codigo_usuario)
        sessao = self._ObterSessao()
        try:
            relatorio = RelatorioBudget(sessao)
            return relatorio.obterFiltrosDisponiveis(ano, filtroCentroCusto, filtroContaContabil, filtroEmpresa, centrosPermitidos)
        finally:
            sessao.close()

    def obterFiltrosAnalitico(self, ano, filtroEmpresa='Todos', filtroCentroCusto='Todos', codigo_usuario=None):
        centrosPermitidos = self._resolverCentrosPermitidos(codigo_usuario)
        sessao = self._ObterSessao()
        try:
            relatorio = RelatorioBudget(sessao)
            return relatorio.obterFiltrosAnalitico(ano, filtroEmpresa, filtroCentroCusto, centrosPermitidos)
        finally:
            sessao.close()

    def gerarRelatorioBudget(self, ano, filtroCentroCusto='Todos', filtroContaContabil='Todos', filtroEmpresa='Todos', codigo_usuario=None):
        centrosPermitidos = self._resolverCentrosPermitidos(codigo_usuario)
        sessao = self._ObterSessao()
        try:
            relatorio = RelatorioBudget(sessao)
            return relatorio.gerarRelatorioBudget(int(ano), filtroCentroCusto, filtroContaContabil, filtroEmpresa, centrosPermitidos)
        finally:
            sessao.close()

    def gerarRelatorioBudgetAnalitico(self, ano, mes, filtroCentroCusto='Todos', filtroEmpresa='Todos', filtroFilial='Todos', codigo_usuario=None):
        centrosPermitidos = self._resolverCentrosPermitidos(codigo_usuario)
        sessao = self._ObterSessao()
        try:
            relatorio = RelatorioBudget(sessao)
            return relatorio.gerarRelatorioBudgetAnalitico(ano, mes, filtroCentroCusto, filtroEmpresa, filtroFilial, centrosPermitidos)
        finally:
            sessao.close()

    def obterDetalhesBudget(
        self,
        ano,
        mes,
        codigoCentroCusto=None,
        codigoContaContabil=None,
        codigoFornecedor=None,
        modoSaldo='todos_itens',
        filtroEmpresa='Todos',
        codigo_usuario=None,
    ):
        centrosPermitidos = self._resolverCentrosPermitidos(codigo_usuario)
        sessao = self._ObterSessao()
        try:
            relatorio = RelatorioBudget(sessao)
            return relatorio.obterDetalhesBudget(
                ano,
                mes,
                codigoCentroCusto,
                codigoContaContabil,
                codigoFornecedor,
                modoSaldo,
                filtroEmpresa,
                centrosPermitidos,
            )
        finally:
            sessao.close()