from sqlalchemy import and_, case, extract, func, or_

from Models.SqlServer.Budget import BudgetItem, Budget
from Models.SqlServer.ContaPagar import ContaPagar, ContaPagarNotaFiscal, CentroCusto, PlanoConta
from Models.SqlServer.Fornecedor import Fornecedor


class RelatorioBudget:
    """
    Relatório base do módulo de Budget.
    Contém a lógica de filtros, consolidação e montagem do payload.
    """

    EMPRESAS_MATRIZ = {
        '1': 1,
        '2': 2,
        'INTEC': 1,
        'FARMA': 2,
        'TODOS': None,
    }

    STATUS_EM_APROVACAO = (1, 2)
    STATUS_APROVADO = (3, 5)
    STATUS_CONSIDERADOS = STATUS_EM_APROVACAO + STATUS_APROVADO

    MESES_RELATORIO = (
        (1, 'Janeiro', 'Jan', 'orcadoJaneiro', BudgetItem.Valor_JaneiroO),
        (2, 'Fevereiro', 'Fev', 'orcadoFevereiro', BudgetItem.Valor_FevereiroO),
        (3, 'Março', 'Mar', 'orcadoMarco', BudgetItem.Valor_MarcoO),
        (4, 'Abril', 'Abr', 'orcadoAbril', BudgetItem.Valor_AbrilO),
        (5, 'Maio', 'Mai', 'orcadoMaio', BudgetItem.Valor_MaioO),
        (6, 'Junho', 'Jun', 'orcadoJunho', BudgetItem.Valor_JunhoO),
        (7, 'Julho', 'Jul', 'orcadoJulho', BudgetItem.Valor_JulhoO),
        (8, 'Agosto', 'Ago', 'orcadoAgosto', BudgetItem.Valor_AgostoO),
        (9, 'Setembro', 'Set', 'orcadoSetembro', BudgetItem.Valor_SetembroO),
        (10, 'Outubro', 'Out', 'orcadoOutubro', BudgetItem.Valor_OutubroO),
        (11, 'Novembro', 'Nov', 'orcadoNovembro', BudgetItem.Valor_NovembroO),
        (12, 'Dezembro', 'Dez', 'orcadoDezembro', BudgetItem.Valor_DezembroO),
    )

    def __init__(self, session):
        self.session = session

    def _resolverCodigoEmpresaMatriz(self, filtroEmpresa):
        chave = str(filtroEmpresa or 'Todos').strip().upper()
        if chave not in self.EMPRESAS_MATRIZ:
            raise ValueError(f"Filtro de empresa inválido: {filtroEmpresa}")
        return self.EMPRESAS_MATRIZ[chave]

    def _extrairIdsNumericos(self, filtro):
        if filtro is None:
            return None

        if isinstance(filtro, (list, tuple, set)):
            valores = filtro
        else:
            texto = str(filtro).strip()
            if not texto or texto.upper() == 'TODOS':
                return None
            valores = texto.split(',')

        ids = [
            float(str(valor).strip())
            for valor in valores
            if str(valor).strip() and str(valor).strip().upper() != 'TODOS'
        ]
        return ids or None

    def _formatarIdFiltro(self, valor):
        if valor is None:
            return None

        try:
            numero = float(valor)
        except (TypeError, ValueError):
            return str(valor).strip()

        return str(int(numero)) if numero.is_integer() else str(numero)

    def _obterCondicaoValorOrcado(self):
        return or_(
            *[func.coalesce(coluna, 0) != 0 for _, _, _, _, coluna in self.MESES_RELATORIO]
        )

    def _obterSubconsultaDataDigitacaoNotaFiscal(self):
        return (
            self.session.query(
                ContaPagarNotaFiscal.Codigo_ContaPagar.label('codigoContaPagar'),
                func.max(ContaPagarNotaFiscal.Data_Digitacao).label('dataDigitacaoNotaFiscal'),
            )
            .group_by(ContaPagarNotaFiscal.Codigo_ContaPagar)
            .subquery()
        )

    def _obterDataDigitacaoEfetivaContaPagar(self, subconsultaDataDigitacaoNotaFiscal):
        return func.coalesce(
            subconsultaDataDigitacaoNotaFiscal.c.dataDigitacaoNotaFiscal,
            ContaPagar.Data_Digitacao,
        )

    def _obterValorEfetivoContaPagar(self):
        return func.coalesce(
            func.nullif(ContaPagar.Valor_RecebidoNotaFiscal, 0),
            ContaPagar.Valor_ContaPagar,
            0,
        )

    def _montarDescricaoComposta(self, codigo, descricao, padrao):
        codigo_texto = str(codigo).strip() if codigo is not None else ''
        descricao_texto = str(descricao).strip() if descricao is not None else ''

        if codigo_texto and descricao_texto:
            return f"{codigo_texto} - {descricao_texto}"
        return codigo_texto or descricao_texto or padrao

    def _montarChaveLinha(self, codigoCentroCusto, centroCusto, codigoContaContabil, contaContabil, codigoFornecedor, fornecedor):
        chave_cc = str(codigoCentroCusto) if codigoCentroCusto is not None else f"cc::{centroCusto}"
        chave_conta = str(codigoContaContabil) if codigoContaContabil is not None else f"conta::{contaContabil}"
        chave_fornecedor = str(codigoFornecedor) if codigoFornecedor is not None else f"fornecedor::{fornecedor}"
        return (chave_cc, chave_conta, chave_fornecedor)

    def _obterEstruturaMeses(self):
        return {
            numero: {
                'mes': numero,
                'nomeMes': nome,
                'abreviacaoMes': abreviacao,
                'orcado': 0.0,
                'emAprovacao': 0.0,
                'aprovado': 0.0,
                'total': 0.0,
                'emAprovacaoComBudget': 0.0,
                'aprovadoComBudget': 0.0,
                'totalComBudget': 0.0,
                'saldo': 0.0,
                'detalhes': [],
                'centrosCusto': 0,
            }
            for numero, nome, abreviacao, _, _ in self.MESES_RELATORIO
        }

    def _obterConsultaOrcadoMensal(self, ano, idsCentros, idsContasContabeis, codigoEmpresaMatriz):
        query = (
            self.session.query(
                CentroCusto.Codigo_CentroCusto.label('codigoCentroCusto'),
                CentroCusto.Numero_CentroCusto.label('numeroCentroCusto'),
                CentroCusto.Nome_CentroCusto.label('nomeCentroCusto'),
                PlanoConta.Codigo_ContaContabil.label('codigoContaContabil'),
                PlanoConta.Numero_ContaContabil.label('numeroContaContabil'),
                PlanoConta.Descricao_ContaContabil.label('descricaoContaContabil'),
                Fornecedor.Codigo_Fornecedor.label('codigoFornecedor'),
                Fornecedor.Nome_Fornecedor.label('nomeFornecedor'),
                *[
                    func.sum(coluna).label(rotulo)
                    for _, _, _, rotulo, coluna in self.MESES_RELATORIO
                ],
            )
            .select_from(BudgetItem)
            .join(Budget, BudgetItem.Codigo_Budget == Budget.Codigo_Budget)
            .outerjoin(CentroCusto, BudgetItem.Codigo_CentroCusto == CentroCusto.Codigo_CentroCusto)
            .outerjoin(PlanoConta, BudgetItem.Codigo_ContaContabil == PlanoConta.Codigo_ContaContabil)
            .outerjoin(Fornecedor, BudgetItem.Codigo_Fornecedor == Fornecedor.Codigo_Fornecedor)
            .filter(Budget.Ano_Vigencia == ano)
        )

        query = self._aplicarFiltrosComuns(
            query,
            BudgetItem.Codigo_CentroCusto,
            BudgetItem.Codigo_ContaContabil,
            BudgetItem.Codigo_EmpresaMatriz,
            idsCentros,
            idsContasContabeis,
            codigoEmpresaMatriz,
        )

        return query.group_by(
            CentroCusto.Codigo_CentroCusto,
            CentroCusto.Numero_CentroCusto,
            CentroCusto.Nome_CentroCusto,
            PlanoConta.Codigo_ContaContabil,
            PlanoConta.Numero_ContaContabil,
            PlanoConta.Descricao_ContaContabil,
            Fornecedor.Codigo_Fornecedor,
            Fornecedor.Nome_Fornecedor,
        )

    def _obterConsultaStatusMensal(self, ano, idsCentros, idsContasContabeis, codigoEmpresaMatriz):
        subconsultaDataDigitacaoNotaFiscal = self._obterSubconsultaDataDigitacaoNotaFiscal()
        dataDigitacaoEfetiva = self._obterDataDigitacaoEfetivaContaPagar(subconsultaDataDigitacaoNotaFiscal)
        valorEfetivoContaPagar = self._obterValorEfetivoContaPagar()
        mesCompetencia = extract('month', dataDigitacaoEfetiva)
        valorEmAprovacao = case(
            (ContaPagar.Opcao_StatusContaPagar.in_(self.STATUS_EM_APROVACAO), valorEfetivoContaPagar),
            else_=0,
        )
        valorAprovado = case(
            (ContaPagar.Opcao_StatusContaPagar.in_(self.STATUS_APROVADO), valorEfetivoContaPagar),
            else_=0,
        )
        valorComBudget = case(
            (ContaPagar.Codigo_BudgetItem.isnot(None), valorEfetivoContaPagar),
            else_=0,
        )
        valorEmAprovacaoComBudget = case(
            (
                and_(
                    ContaPagar.Codigo_BudgetItem.isnot(None),
                    ContaPagar.Opcao_StatusContaPagar.in_(self.STATUS_EM_APROVACAO),
                ),
                valorEfetivoContaPagar,
            ),
            else_=0,
        )
        valorAprovadoComBudget = case(
            (
                and_(
                    ContaPagar.Codigo_BudgetItem.isnot(None),
                    ContaPagar.Opcao_StatusContaPagar.in_(self.STATUS_APROVADO),
                ),
                valorEfetivoContaPagar,
            ),
            else_=0,
        )

        query = (
            self.session.query(
                mesCompetencia.label('mesCompetencia'),
                CentroCusto.Codigo_CentroCusto.label('codigoCentroCusto'),
                CentroCusto.Numero_CentroCusto.label('numeroCentroCusto'),
                CentroCusto.Nome_CentroCusto.label('nomeCentroCusto'),
                PlanoConta.Codigo_ContaContabil.label('codigoContaContabil'),
                PlanoConta.Numero_ContaContabil.label('numeroContaContabil'),
                PlanoConta.Descricao_ContaContabil.label('descricaoContaContabil'),
                Fornecedor.Codigo_Fornecedor.label('codigoFornecedor'),
                Fornecedor.Nome_Fornecedor.label('nomeFornecedor'),
                func.sum(valorEmAprovacao).label('emAprovacao'),
                func.sum(valorAprovado).label('aprovado'),
                func.sum(valorEfetivoContaPagar).label('total'),
                func.sum(valorEmAprovacaoComBudget).label('emAprovacaoComBudget'),
                func.sum(valorAprovadoComBudget).label('aprovadoComBudget'),
                func.sum(valorComBudget).label('totalComBudget'),
            )
            .select_from(ContaPagar)
            .outerjoin(
                subconsultaDataDigitacaoNotaFiscal,
                ContaPagar.Codigo_ContaPagar == subconsultaDataDigitacaoNotaFiscal.c.codigoContaPagar,
            )
            .outerjoin(CentroCusto, ContaPagar.Codigo_CentroCusto == CentroCusto.Codigo_CentroCusto)
            .outerjoin(PlanoConta, ContaPagar.Codigo_ContaContabil == PlanoConta.Codigo_ContaContabil)
            .outerjoin(Fornecedor, ContaPagar.Codigo_Fornecedor == Fornecedor.Codigo_Fornecedor)
            .filter(extract('year', dataDigitacaoEfetiva) == ano)
            .filter(ContaPagar.Opcao_StatusContaPagar.in_(self.STATUS_CONSIDERADOS))
        )

        query = self._aplicarFiltrosComuns(
            query,
            ContaPagar.Codigo_CentroCusto,
            ContaPagar.Codigo_ContaContabil,
            ContaPagar.Codigo_EmpresaMatriz,
            idsCentros,
            idsContasContabeis,
            codigoEmpresaMatriz,
        )

        return query.group_by(
            mesCompetencia,
            CentroCusto.Codigo_CentroCusto,
            CentroCusto.Numero_CentroCusto,
            CentroCusto.Nome_CentroCusto,
            PlanoConta.Codigo_ContaContabil,
            PlanoConta.Numero_ContaContabil,
            PlanoConta.Descricao_ContaContabil,
            Fornecedor.Codigo_Fornecedor,
            Fornecedor.Nome_Fornecedor,
        )

    def _obterRegistroConsolidado(self, acumulador, linha):
        centroCusto = self._montarDescricaoComposta(
            linha.numeroCentroCusto,
            linha.nomeCentroCusto,
            'Sem centro de custo vinculado'
        )
        contaContabil = self._montarDescricaoComposta(
            linha.numeroContaContabil,
            linha.descricaoContaContabil,
            'Sem conta contábil vinculada'
        )
        fornecedor = (str(linha.nomeFornecedor).strip() if linha.nomeFornecedor else '') or 'Sem fornecedor vinculado'
        chave = self._montarChaveLinha(
            linha.codigoCentroCusto,
            centroCusto,
            linha.codigoContaContabil,
            contaContabil,
            linha.codigoFornecedor,
            fornecedor,
        )

        if chave not in acumulador:
            acumulador[chave] = {
                'centroCusto': centroCusto,
                'contaContabil': contaContabil,
                'fornecedor': fornecedor,
                'orcado': 0.0,
                'emAprovacao': 0.0,
                'aprovado': 0.0,
                'total': 0.0,
                'emAprovacaoComBudget': 0.0,
                'aprovadoComBudget': 0.0,
                'totalComBudget': 0.0,
                'saldo': 0.0,
                'saldoComBudget': 0.0,
            }

        return acumulador[chave]

    def _obterConsultaRelacionamentosOrcados(self, ano, idsCentros, idsContasContabeis, codigoEmpresaMatriz):
        query = (
            self.session.query(
                CentroCusto.Codigo_CentroCusto.label('codigoCentroCusto'),
                CentroCusto.Numero_CentroCusto.label('numeroCentroCusto'),
                CentroCusto.Nome_CentroCusto.label('nomeCentroCusto'),
                PlanoConta.Codigo_ContaContabil.label('codigoContaContabil'),
                PlanoConta.Numero_ContaContabil.label('numeroContaContabil'),
                PlanoConta.Descricao_ContaContabil.label('descricaoContaContabil'),
            )
            .select_from(BudgetItem)
            .join(Budget, BudgetItem.Codigo_Budget == Budget.Codigo_Budget)
            .outerjoin(CentroCusto, BudgetItem.Codigo_CentroCusto == CentroCusto.Codigo_CentroCusto)
            .outerjoin(PlanoConta, BudgetItem.Codigo_ContaContabil == PlanoConta.Codigo_ContaContabil)
            .filter(Budget.Ano_Vigencia == ano)
            .filter(self._obterCondicaoValorOrcado())
        )

        query = self._aplicarFiltrosComuns(
            query,
            BudgetItem.Codigo_CentroCusto,
            BudgetItem.Codigo_ContaContabil,
            BudgetItem.Codigo_EmpresaMatriz,
            idsCentros,
            idsContasContabeis,
            codigoEmpresaMatriz,
        )

        return query.distinct()

    def _obterConsultaRelacionamentosStatus(self, ano, idsCentros, idsContasContabeis, codigoEmpresaMatriz):
        subconsultaDataDigitacaoNotaFiscal = self._obterSubconsultaDataDigitacaoNotaFiscal()
        dataDigitacaoEfetiva = self._obterDataDigitacaoEfetivaContaPagar(subconsultaDataDigitacaoNotaFiscal)
        valorEfetivoContaPagar = self._obterValorEfetivoContaPagar()
        query = (
            self.session.query(
                CentroCusto.Codigo_CentroCusto.label('codigoCentroCusto'),
                CentroCusto.Numero_CentroCusto.label('numeroCentroCusto'),
                CentroCusto.Nome_CentroCusto.label('nomeCentroCusto'),
                PlanoConta.Codigo_ContaContabil.label('codigoContaContabil'),
                PlanoConta.Numero_ContaContabil.label('numeroContaContabil'),
                PlanoConta.Descricao_ContaContabil.label('descricaoContaContabil'),
            )
            .select_from(ContaPagar)
            .outerjoin(
                subconsultaDataDigitacaoNotaFiscal,
                ContaPagar.Codigo_ContaPagar == subconsultaDataDigitacaoNotaFiscal.c.codigoContaPagar,
            )
            .outerjoin(CentroCusto, ContaPagar.Codigo_CentroCusto == CentroCusto.Codigo_CentroCusto)
            .outerjoin(PlanoConta, ContaPagar.Codigo_ContaContabil == PlanoConta.Codigo_ContaContabil)
            .filter(extract('year', dataDigitacaoEfetiva) == ano)
            .filter(ContaPagar.Opcao_StatusContaPagar.in_(self.STATUS_CONSIDERADOS))
            .filter(valorEfetivoContaPagar != 0)
        )

        query = self._aplicarFiltrosComuns(
            query,
            ContaPagar.Codigo_CentroCusto,
            ContaPagar.Codigo_ContaContabil,
            ContaPagar.Codigo_EmpresaMatriz,
            idsCentros,
            idsContasContabeis,
            codigoEmpresaMatriz,
        )

        return query.distinct()

    def _construirOpcoesFiltros(self, linhasRelacionamento):
        centros = {}
        contas = {}

        for linha in linhasRelacionamento:
            idCentro = self._formatarIdFiltro(linha.codigoCentroCusto)
            idConta = self._formatarIdFiltro(linha.codigoContaContabil)

            if idCentro and linha.nomeCentroCusto:
                centros[idCentro] = {
                    'id': idCentro,
                    'codigo': linha.numeroCentroCusto,
                    'nome': linha.nomeCentroCusto,
                }

            if idConta and linha.descricaoContaContabil:
                contas[idConta] = {
                    'id': idConta,
                    'codigo': linha.numeroContaContabil,
                    'descricao': linha.descricaoContaContabil,
                    'nome': f'{linha.numeroContaContabil} - {linha.descricaoContaContabil}',
                }

        centrosOrdenados = sorted(
            centros.values(),
            key=lambda item: (
                str(item.get('codigo') or ''),
                str(item.get('nome') or ''),
            )
        )
        contasOrdenadas = sorted(
            contas.values(),
            key=lambda item: (
                str(item.get('codigo') or ''),
                str(item.get('descricao') or ''),
            )
        )

        return centrosOrdenados, contasOrdenadas

    def _obterOpcoesFiltros(self, ano, idsCentros, idsContasContabeis, codigoEmpresaMatriz):
        relacionamentos = []
        relacionamentos.extend(
            self._obterConsultaRelacionamentosOrcados(
                ano,
                idsCentros,
                idsContasContabeis,
                codigoEmpresaMatriz,
            ).all()
        )
        relacionamentos.extend(
            self._obterConsultaRelacionamentosStatus(
                ano,
                idsCentros,
                idsContasContabeis,
                codigoEmpresaMatriz,
            ).all()
        )

        return self._construirOpcoesFiltros(relacionamentos)

    def _consolidarDetalhesMensais(self, ano, idsCentros, idsContasContabeis, codigoEmpresaMatriz):
        detalhesPorMes = {
            numero: {}
            for numero, _, _, _, _ in self.MESES_RELATORIO
        }

        for linha in self._obterConsultaOrcadoMensal(
            ano,
            idsCentros,
            idsContasContabeis,
            codigoEmpresaMatriz,
        ).all():
            for numeroMes, _, _, rotulo, _ in self.MESES_RELATORIO:
                valorOrcado = float(getattr(linha, rotulo) or 0.0)
                if valorOrcado == 0:
                    continue

                registro = self._obterRegistroConsolidado(detalhesPorMes[numeroMes], linha)
                registro['orcado'] += valorOrcado

        for linha in self._obterConsultaStatusMensal(
            ano,
            idsCentros,
            idsContasContabeis,
            codigoEmpresaMatriz,
        ).all():
            numeroMes = int(linha.mesCompetencia or 0)
            if numeroMes not in detalhesPorMes:
                continue

            registro = self._obterRegistroConsolidado(detalhesPorMes[numeroMes], linha)
            registro['emAprovacao'] += float(linha.emAprovacao or 0.0)
            registro['aprovado'] += float(linha.aprovado or 0.0)
            registro['total'] += float(linha.total or 0.0)
            registro['emAprovacaoComBudget'] += float(linha.emAprovacaoComBudget or 0.0)
            registro['aprovadoComBudget'] += float(linha.aprovadoComBudget or 0.0)
            registro['totalComBudget'] += float(linha.totalComBudget or 0.0)

        return detalhesPorMes

    def _montarRetornoMensal(self, detalhesPorMes):
        meses = self._obterEstruturaMeses()

        for numeroMes, linhasMes in detalhesPorMes.items():
            detalhes = []
            centrosCustoMes = set()

            for linha in linhasMes.values():
                linha['saldo'] = linha['orcado'] - linha['total']
                linha['saldoComBudget'] = linha['orcado'] - linha['totalComBudget']
                detalhes.append(linha)
                centrosCustoMes.add(linha['centroCusto'])

            detalhes.sort(key=lambda item: (
                item['centroCusto'],
                item['contaContabil'],
                item['fornecedor']
            ))

            meses[numeroMes]['detalhes'] = detalhes
            meses[numeroMes]['orcado'] = sum(linha['orcado'] for linha in detalhes)
            meses[numeroMes]['emAprovacao'] = sum(linha['emAprovacao'] for linha in detalhes)
            meses[numeroMes]['aprovado'] = sum(linha['aprovado'] for linha in detalhes)
            meses[numeroMes]['total'] = sum(linha['total'] for linha in detalhes)
            meses[numeroMes]['emAprovacaoComBudget'] = sum(linha['emAprovacaoComBudget'] for linha in detalhes)
            meses[numeroMes]['aprovadoComBudget'] = sum(linha['aprovadoComBudget'] for linha in detalhes)
            meses[numeroMes]['totalComBudget'] = sum(linha['totalComBudget'] for linha in detalhes)
            meses[numeroMes]['saldo'] = meses[numeroMes]['orcado'] - meses[numeroMes]['total']
            meses[numeroMes]['saldoComBudget'] = meses[numeroMes]['orcado'] - meses[numeroMes]['totalComBudget']
            meses[numeroMes]['centrosCusto'] = len(centrosCustoMes)

        return {
            'meses': [meses[numero] for numero, _, _, _, _ in self.MESES_RELATORIO]
        }

    def _aplicarFiltrosComuns(self, query, campoCentroCusto, campoContaContabil, campoEmpresaMatriz, idsCentros, idsContasContabeis, codigoEmpresaMatriz):
        if idsCentros:
            query = query.filter(campoCentroCusto.in_(idsCentros))

        if idsContasContabeis:
            query = query.filter(campoContaContabil.in_(idsContasContabeis))

        if codigoEmpresaMatriz is not None:
            query = query.filter(campoEmpresaMatriz == codigoEmpresaMatriz)

        return query

    def obterFiltrosDisponiveis(self, ano, filtroCentroCusto='Todos', filtroContaContabil='Todos', filtroEmpresa='Todos'):
        """
        Busca as opções válidas de Centros de Custo e Contas Contábeis conforme
        o ano, empresa e a seleção atual dos filtros.

        Returns:
            dict: Dicionário contendo as listas de centros de custo e contas contábeis.
        """
        codigoEmpresaMatriz = self._resolverCodigoEmpresaMatriz(filtroEmpresa)
        idsCentros = self._extrairIdsNumericos(filtroCentroCusto)
        idsContas = self._extrairIdsNumericos(filtroContaContabil)

        centrosDisponiveis, _ = self._obterOpcoesFiltros(
            ano,
            None,
            idsContas,
            codigoEmpresaMatriz,
        )
        _, contasDisponiveis = self._obterOpcoesFiltros(
            ano,
            idsCentros,
            None,
            codigoEmpresaMatriz,
        )

        return {
            'empresas': [
                {'id': 'Todos', 'nome': 'Todas as Empresas'},
                {'id': '1', 'nome': 'Intec'},
                {'id': '2', 'nome': 'Farma'}
            ],
            'centrosCusto': centrosDisponiveis,
            'contasContabeis': contasDisponiveis,
        }

    def gerarRelatorioBudget(self, ano, filtroCentroCusto='Todos', filtroContaContabil='Todos', filtroEmpresa='Todos'):
        """
        Gera o consolidado do orçamento comparando valores orçados com
        lançamentos em aprovação e aprovados, agrupando por Centro de Custo,
        Conta Contábil e Fornecedor.

        Args:
            ano (int): O ano de referência para filtragem dos dados.
            filtroCentroCusto (str): String com IDs dos centros de custo separados por vírgula ou 'Todos'.
            filtroContaContabil (str): ID da conta contábil ou 'Todos'.
            filtroEmpresa (str): Código lógico da empresa matriz ('1' Intec, '2' Farma ou 'Todos').

        Returns:
            dict: Estrutura com 12 meses do ano e o detalhamento mensal por centro, conta e fornecedor.
        """
        codigoEmpresaMatriz = self._resolverCodigoEmpresaMatriz(filtroEmpresa)
        idsCentros = self._extrairIdsNumericos(filtroCentroCusto)
        idsContasContabeis = self._extrairIdsNumericos(filtroContaContabil)
        detalhesPorMes = self._consolidarDetalhesMensais(
            ano,
            idsCentros,
            idsContasContabeis,
            codigoEmpresaMatriz,
        )

        return self._montarRetornoMensal(detalhesPorMes)