from sqlalchemy import and_, case, collate, extract, func, literal, or_

from Models.SqlServer.Budget import BudgetItem, Budget, BudgetGrupo
from Models.SqlServer.ContaPagar import ContaPagar, ContaPagarNotaFiscal, CentroCusto, PlanoConta
from Models.SqlServer.Empresa import Empresa, TbFilial
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

    MESES_POR_NUMERO = {
        numero: {
            'mes': numero,
            'nome': nome,
            'abreviacao': abreviacao,
            'coluna': coluna,
        }
        for numero, nome, abreviacao, _, coluna in MESES_RELATORIO
    }

    def __init__(self, session):
        """Inicializa o serviço de relatório com a sessão de banco ativa."""
        self.session = session

    def _resolverCodigoEmpresaMatriz(self, filtroEmpresa):
        """Converte o filtro lógico de empresa para o código da empresa matriz."""
        chave = str(filtroEmpresa or 'Todos').strip().upper() # Garanti que 'None' seja tratado como 'Todos' e 
                                                              # normalizar a chave
        if chave not in self.EMPRESAS_MATRIZ:
        # Se a chave não for reconhecida, levanta um erro para evitar consultas inválidas
            raise ValueError(f"Filtro de empresa inválido: {filtroEmpresa}")
        # Se a chave for válida, retorna o código da empresa matriz correspondente (ou None para 'Todos')
        return self.EMPRESAS_MATRIZ[chave]

    def _extrairIdsNumericos(self, filtro):
        """Extrai IDs numéricos de filtros textuais/listas, ignorando a opção 'Todos'."""
        if filtro is None:
            return None

        # Se o filtro já for uma coleção ex: (Uma lista, tupla ou conjunto), 
        # usamos diretamente; caso contrário, processamos a string
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
        """Normaliza um identificador para string, removendo casas decimais desnecessárias."""
        if valor is None:
            return None

        try:
            numero = float(valor)
        except (TypeError, ValueError):
            return str(valor).strip()

        return str(int(numero)) if numero.is_integer() else str(numero)

    def _extrairIdsInteiros(self, filtro, minimo=None, maximo=None):
        """Extrai IDs inteiros válidos de um filtro, com limites opcionais."""
        ids = self._extrairIdsNumericos(filtro)
        if ids is None:
            return None

        inteiros = []
        vistos = set()
        for valor in ids:
            inteiro = int(valor)
            if inteiro != valor:
                raise ValueError(f"Valor inválido para filtro inteiro: {valor}")

            if minimo is not None and inteiro < minimo:
                raise ValueError(f"Valor inválido para filtro: {inteiro}")

            if maximo is not None and inteiro > maximo:
                raise ValueError(f"Valor inválido para filtro: {inteiro}")

            if inteiro not in vistos:
                vistos.add(inteiro)
                inteiros.append(inteiro)

        return inteiros or None

    def _extrairValoresTexto(self, filtro):
        """Extrai valores textuais únicos de um filtro, preservando a ordem original."""
        if filtro is None:
            return None

        if isinstance(filtro, (list, tuple, set)):
            valores = filtro
        else:
            texto = str(filtro).strip()
            if not texto or texto.upper() == 'TODOS':
                return None
            valores = texto.split(',')

        textos = []
        for valor in valores:
            texto = str(valor).strip()
            if not texto or texto.upper() == 'TODOS':
                continue
            if texto not in textos:
                textos.append(texto)

        return textos or None

    def _obterDocumentoNormalizadoSql(self, campo):
        """Gera expressão SQL para normalizar documentos removendo pontuações."""
        return func.replace(
            # Remove pontos e barras, substituindo por string vazia, e depois remove hífens
            func.replace(
                func.replace(func.coalesce(campo, ''), '.', ''),
                '/',
                '',
            ),
            '-',
            '',
        )

    def _obterSubconsultaFiliais(self):
        """Monta subconsulta de filiais por empresa a partir do CNPJ normalizado."""
        cnpjNormalizado = self._obterDocumentoNormalizadoSql(Empresa.CNPJ_Empresa)

        return (
            # SELECT que traz o código da empresa e o nome da filial, juntando as tabelas Empresa e 
            # TbFilial pelo CNPJ normalizado
            self.session.query(
                Empresa.Codigo_Empresa.label('codigoEmpresa'),
                TbFilial.nomefilial.label('nomeFilial'),
            )
            .select_from(Empresa)
            .join(
                TbFilial,
                cnpjNormalizado == collate(TbFilial.cgc, 'SQL_Latin1_General_CP1_CI_AS'),
            )
            .distinct()
            .subquery()
        )

    def _obterSubconsultaFiliaisConsolidadas(self):
        """Consolida filiais por empresa, marcando múltiplas ocorrências quando necessário."""
        subconsultaFiliais = self._obterSubconsultaFiliais()
        quantidadeFiliais = func.count(subconsultaFiliais.c.nomeFilial)

        # AQUI É FEITA A CONSOLIDAÇÃO: SE HOUVER MAIS DE UMA FILIAL PARA A MESMA EMPRESA, O NOME VIRA 'Multiplas filiais', 
        # SENÃO FICA O NOME DA FILIAL
        nomeFilialConsolidado = case(
            (quantidadeFiliais > 1, literal('Multiplas filiais')),
            else_=func.min(subconsultaFiliais.c.nomeFilial),
        )

        return (
            # SELECT que traz o código da empresa e o nome da filial consolidado, agrupando por código da empresa para 
            # identificar múltiplas filiais
            self.session.query(
                subconsultaFiliais.c.codigoEmpresa.label('codigoEmpresa'),
                nomeFilialConsolidado.label('nomeFilial'),
            )
            .group_by(subconsultaFiliais.c.codigoEmpresa)
            .subquery()
        )

    def _aplicarFiltroFilial(self, query, campoCodigoEmpresa, filiaisSelecionadas):
        """Aplica o filtro de filial em uma consulta com base no código de empresa."""
        if filiaisSelecionadas:
            subconsultaFiliais = self._obterSubconsultaFiliais()
            # SELECT que traz os códigos das empresas que possuem as filiais selecionadas, filtrando pela lista de filiais e 
            # garantindo que sejam distintas
            empresasFiltradas = (
                self.session.query(subconsultaFiliais.c.codigoEmpresa)
                .filter(subconsultaFiliais.c.nomeFilial.in_(filiaisSelecionadas))
                .distinct()
            )
            query = query.filter(campoCodigoEmpresa.in_(empresasFiltradas))
        return query

    def _construirExpressaoSomaColunas(self, colunas):
        """Cria expressão SQL de soma para múltiplas colunas com coalesce."""
        expressao = None
        for coluna in colunas:
            trecho = func.coalesce(coluna, 0)
            expressao = trecho if expressao is None else expressao + trecho
        # Está função soma as colunas de orçamento dos meses selecionados, tratando valores nulos como zero, 
        # para garantir que a soma seja correta mesmo quando alguns meses não tiverem valores preenchidos. 
        # O resultado é uma expressão SQL que pode ser usada diretamente nas consultas para calcular o total orçado no período selecionado.
        return expressao

    def _obterCondicaoValorOrcado(self):
        """Retorna condição SQL para identificar linhas com orçamento diferente de zero."""
        return or_(
            # Se pelo menos uma das colunas de orçamento dos meses tiver valor diferente de zero, a condição será verdadeira,
            # e a linha será considerada no relatório. Caso contrário, se todas as colunas forem zero ou nulas, a linha será ignorada.
            *(func.coalesce(coluna, 0) != 0 for _, _, _, _, coluna in self.MESES_RELATORIO)
        )

    def _obterSubconsultaDataDigitacaoNotaFiscal(self):
        """Monta subconsulta com a última data de digitação por conta a pagar."""
        return (
            # Agrupa por conta a pagar para obter a data mais recente de digitação da nota fiscal.
            # Essa data é usada como prioridade no cálculo de competência do realizado.
            self.session.query(
                ContaPagarNotaFiscal.Codigo_ContaPagar.label('codigoContaPagar'),
                func.max(ContaPagarNotaFiscal.Data_Digitacao).label('dataDigitacaoNotaFiscal'),
            )
            .group_by(ContaPagarNotaFiscal.Codigo_ContaPagar)
            .subquery()
        )

    def _obterDataDigitacaoEfetivaContaPagar(self, subconsultaDataDigitacaoNotaFiscal):
        """Retorna expressão SQL da data efetiva de digitação da conta a pagar."""
        return func.coalesce(
            subconsultaDataDigitacaoNotaFiscal.c.dataDigitacaoNotaFiscal,
            ContaPagar.Data_Digitacao,
        )

    def _obterValorEfetivoContaPagar(self):
        """Retorna expressão SQL do valor efetivo da conta a pagar."""
        return func.coalesce(
            func.nullif(ContaPagar.Valor_RecebidoNotaFiscal, 0),
            ContaPagar.Valor_ContaPagar,
            0,
        )

    def _montarDescricaoComposta(self, codigo, descricao, padrao):
        """Combina código e descrição em uma representação textual única."""
        codigo_texto = str(codigo).strip() if codigo is not None else ''
        descricao_texto = str(descricao).strip() if descricao is not None else ''

        if codigo_texto and descricao_texto:
            return f"{codigo_texto} - {descricao_texto}"
        return codigo_texto or descricao_texto or padrao

    def _montarChaveLinha(
        self,
        codigoCentroCusto,
        centroCusto,
        codigoContaContabil,
        contaContabil,
        codigoFornecedor,
        fornecedor,
    ):
        """Monta chave estável de agrupamento para o consolidado mensal."""
        chave_cc = str(codigoCentroCusto) if codigoCentroCusto is not None else f"cc::{centroCusto}"
        chave_conta = str(codigoContaContabil) if codigoContaContabil is not None else f"conta::{contaContabil}"
        chave_fornecedor = str(codigoFornecedor) if codigoFornecedor is not None else f"fornecedor::{fornecedor}"
        return (chave_cc, chave_conta, chave_fornecedor)

    def _obterEstruturaMeses(self):
        """Inicializa a estrutura base de retorno para os 12 meses do relatório."""
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

    def _resolverMesRelatorio(self, mes):
        """Resolve metadados de um mês válido para uso em consultas e payload."""
        try:
            numeroMes = int(mes)
        except (TypeError, ValueError):
            raise ValueError(f"Mês inválido: {mes}")

        dadosMes = self.MESES_POR_NUMERO.get(numeroMes)
        if dadosMes:
            return dadosMes

        raise ValueError(f"Mês inválido: {mes}")

    def _resolverMesesRelatorio(self, filtroMes):
        """Resolve a lista final de meses a considerar no relatório analítico."""
        mesesSelecionados = self._extrairIdsInteiros(filtroMes, 1, 12)

        if not mesesSelecionados:
            return [
                self._resolverMesRelatorio(numero)
                for numero, _, _, _, _ in self.MESES_RELATORIO
            ]

        return [self._resolverMesRelatorio(numero) for numero in mesesSelecionados]

    def _descreverSelecaoMeses(self, mesesInfo):
        """Gera descrição legível da seleção de meses para o payload de referência."""
        if len(mesesInfo) == 1:
            return mesesInfo[0]['nome']

        if len(mesesInfo) <= 3:
            return ', '.join(mes['abreviacao'] for mes in mesesInfo)

        return f"{len(mesesInfo)} meses selecionados"

    def _obterConsultaOrcadoMensal(self, ano, idsCentros, idsContasContabeis, codigoEmpresaMatriz):
        """Monta consulta SQL de valores orçados agrupados por dimensão contábil."""
        query = (
            # Consulta base do orçamento: agrega os 12 meses por centro, conta e fornecedor.
            # joins com CentroCusto/PlanoConta/Fornecedor são left join para não perder linhas sem vínculo cadastral.
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

        # Aplica os filtros de centro, conta e empresa matriz de forma padronizada.
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
        """Monta consulta SQL de realizado mensal por status e vínculo com budget."""
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
            # Consulta base do realizado:
            # - usa data efetiva (nota fiscal quando existir, senão data da conta);
            # - separa valores por status (em aprovação/aprovado);
            # - calcula também os totais vinculados a budget.
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

        # Reaproveita a mesma regra de filtros do orçamento para manter coerência entre visões.
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

    def _obterSubconsultaMapeamentoGrupoAnalitico(self, ano, idsCentros, codigoEmpresaMatriz, filiaisSelecionadas):
        """Monta mapeamento auxiliar para vincular contas realizadas a grupo orçamentário."""
        query = (
            # Mapa de fallback para descobrir grupo orçamentário por combinação
            # empresa matriz + empresa + centro de custo + conta contábil.
            # min(...) é usado para garantir um único grupo quando houver duplicidades.
            self.session.query(
                BudgetItem.Codigo_EmpresaMatriz.label('codigoEmpresaMatriz'),
                BudgetItem.Codigo_Empresa.label('codigoEmpresa'),
                BudgetItem.Codigo_CentroCusto.label('codigoCentroCusto'),
                BudgetItem.Codigo_ContaContabil.label('codigoContaContabil'),
                func.min(BudgetGrupo.Codigo_BudgetGrupo).label('codigoGrupo'),
                func.min(BudgetGrupo.Descricao_BudgetGrupo).label('descricaoGrupo'),
            )
            .select_from(BudgetItem)
            .join(Budget, BudgetItem.Codigo_Budget == Budget.Codigo_Budget)
            .outerjoin(BudgetGrupo, BudgetItem.Codigo_BudgetGrupo == BudgetGrupo.Codigo_BudgetGrupo)
            .filter(Budget.Ano_Vigencia == ano)
        )

        # Filtra o mapeamento pela mesma janela de dados usada no relatório analítico.
        query = self._aplicarFiltrosComuns(
            query,
            BudgetItem.Codigo_CentroCusto,
            BudgetItem.Codigo_ContaContabil,
            BudgetItem.Codigo_EmpresaMatriz,
            idsCentros,
            None,
            codigoEmpresaMatriz,
        )
        # Quando filial é informada, restringe apenas empresas daquela(s) filial(is).
        query = self._aplicarFiltroFilial(query, BudgetItem.Codigo_Empresa, filiaisSelecionadas)

        return query.group_by(
            BudgetItem.Codigo_EmpresaMatriz,
            BudgetItem.Codigo_Empresa,
            BudgetItem.Codigo_CentroCusto,
            BudgetItem.Codigo_ContaContabil,
        ).subquery()

    def _obterConsultaOrcadoAnalitico(self, ano, mesesInfo, idsCentros, codigoEmpresaMatriz, filiaisSelecionadas):
        """Monta consulta do orçamento analítico consolidado por grupo/conta/filial."""
        colunasMes = [mes['coluna'] for mes in mesesInfo]
        expressaoOrcado = self._construirExpressaoSomaColunas(colunasMes)
        subconsultaFiliaisConsolidadas = self._obterSubconsultaFiliaisConsolidadas()

        query = (
            # Orçado analítico:
            # soma os meses selecionados e agrupa por grupo orçamentário, filial, centro e conta.
            # A filial vem da subconsulta consolidada para refletir "Multiplas filiais" quando aplicável.
            self.session.query(
                BudgetGrupo.Codigo_BudgetGrupo.label('codigoGrupo'),
                BudgetGrupo.Descricao_BudgetGrupo.label('descricaoGrupo'),
                subconsultaFiliaisConsolidadas.c.nomeFilial.label('nomeFilial'),
                CentroCusto.Codigo_CentroCusto.label('codigoCentroCusto'),
                CentroCusto.Numero_CentroCusto.label('numeroCentroCusto'),
                CentroCusto.Nome_CentroCusto.label('nomeCentroCusto'),
                PlanoConta.Codigo_ContaContabil.label('codigoContaContabil'),
                PlanoConta.Numero_ContaContabil.label('numeroContaContabil'),
                PlanoConta.Descricao_ContaContabil.label('descricaoContaContabil'),
                func.sum(expressaoOrcado).label('orcado'),
            )
            .select_from(BudgetItem)
            .join(Budget, BudgetItem.Codigo_Budget == Budget.Codigo_Budget)
            .outerjoin(BudgetGrupo, BudgetItem.Codigo_BudgetGrupo == BudgetGrupo.Codigo_BudgetGrupo)
            .outerjoin(subconsultaFiliaisConsolidadas, BudgetItem.Codigo_Empresa == subconsultaFiliaisConsolidadas.c.codigoEmpresa)
            .outerjoin(CentroCusto, BudgetItem.Codigo_CentroCusto == CentroCusto.Codigo_CentroCusto)
            .outerjoin(PlanoConta, BudgetItem.Codigo_ContaContabil == PlanoConta.Codigo_ContaContabil)
            .filter(Budget.Ano_Vigencia == ano)
        )

        # Filtros comuns (centro/empresa) e filtro opcional de filial.
        query = self._aplicarFiltrosComuns(
            query,
            BudgetItem.Codigo_CentroCusto,
            BudgetItem.Codigo_ContaContabil,
            BudgetItem.Codigo_EmpresaMatriz,
            idsCentros,
            None,
            codigoEmpresaMatriz,
        )
        query = self._aplicarFiltroFilial(query, BudgetItem.Codigo_Empresa, filiaisSelecionadas)

        return query.group_by(
            BudgetGrupo.Codigo_BudgetGrupo,
            BudgetGrupo.Descricao_BudgetGrupo,
            subconsultaFiliaisConsolidadas.c.nomeFilial,
            CentroCusto.Codigo_CentroCusto,
            CentroCusto.Numero_CentroCusto,
            CentroCusto.Nome_CentroCusto,
            PlanoConta.Codigo_ContaContabil,
            PlanoConta.Numero_ContaContabil,
            PlanoConta.Descricao_ContaContabil,
        )

    def _obterConsultaRealizadoAnalitico(self, ano, mesesInfo, idsCentros, codigoEmpresaMatriz, filiaisSelecionadas):
        """Monta consulta do realizado analítico no período informado."""
        subconsultaDataDigitacaoNotaFiscal = self._obterSubconsultaDataDigitacaoNotaFiscal()
        dataDigitacaoEfetiva = self._obterDataDigitacaoEfetivaContaPagar(subconsultaDataDigitacaoNotaFiscal)
        valorEfetivoContaPagar = self._obterValorEfetivoContaPagar()
        subconsultaFiliaisConsolidadas = self._obterSubconsultaFiliaisConsolidadas()
        subconsultaMapeamentoGrupo = self._obterSubconsultaMapeamentoGrupoAnalitico(
            ano,
            idsCentros,
            codigoEmpresaMatriz,
            filiaisSelecionadas,
        )

        grupoCodigo = func.coalesce(BudgetGrupo.Codigo_BudgetGrupo, subconsultaMapeamentoGrupo.c.codigoGrupo)
        grupoDescricao = func.coalesce(BudgetGrupo.Descricao_BudgetGrupo, subconsultaMapeamentoGrupo.c.descricaoGrupo)
        valorComBudget = case(
            (ContaPagar.Codigo_BudgetItem.isnot(None), valorEfetivoContaPagar),
            else_=0,
        )
        mesesSelecionados = [mes['mes'] for mes in mesesInfo]

        query = (
            # Realizado analítico:
            # 1) tenta obter grupo pelo vínculo direto BudgetItem->BudgetGrupo;
            # 2) se não houver vínculo direto, usa o mapeamento auxiliar por dimensões contábeis.
            self.session.query(
                grupoCodigo.label('codigoGrupo'),
                grupoDescricao.label('descricaoGrupo'),
                subconsultaFiliaisConsolidadas.c.nomeFilial.label('nomeFilial'),
                CentroCusto.Codigo_CentroCusto.label('codigoCentroCusto'),
                CentroCusto.Numero_CentroCusto.label('numeroCentroCusto'),
                CentroCusto.Nome_CentroCusto.label('nomeCentroCusto'),
                PlanoConta.Codigo_ContaContabil.label('codigoContaContabil'),
                PlanoConta.Numero_ContaContabil.label('numeroContaContabil'),
                PlanoConta.Descricao_ContaContabil.label('descricaoContaContabil'),
                func.sum(valorEfetivoContaPagar).label('realizadoTotal'),
                func.sum(valorComBudget).label('realizadoComBudget'),
            )
            .select_from(ContaPagar)
            .outerjoin(
                subconsultaDataDigitacaoNotaFiscal,
                ContaPagar.Codigo_ContaPagar == subconsultaDataDigitacaoNotaFiscal.c.codigoContaPagar,
            )
            .outerjoin(BudgetItem, ContaPagar.Codigo_BudgetItem == BudgetItem.Codigo_BudgetItem)
            .outerjoin(BudgetGrupo, BudgetItem.Codigo_BudgetGrupo == BudgetGrupo.Codigo_BudgetGrupo)
            .outerjoin(
                subconsultaMapeamentoGrupo,
                # Junção por chave de negócio para encontrar grupo quando o título não está ligado ao budget item.
                and_(
                    subconsultaMapeamentoGrupo.c.codigoEmpresaMatriz == ContaPagar.Codigo_EmpresaMatriz,
                    subconsultaMapeamentoGrupo.c.codigoEmpresa == ContaPagar.Codigo_Empresa,
                    subconsultaMapeamentoGrupo.c.codigoCentroCusto == ContaPagar.Codigo_CentroCusto,
                    subconsultaMapeamentoGrupo.c.codigoContaContabil == ContaPagar.Codigo_ContaContabil,
                ),
            )
            .outerjoin(subconsultaFiliaisConsolidadas, ContaPagar.Codigo_Empresa == subconsultaFiliaisConsolidadas.c.codigoEmpresa)
            .outerjoin(CentroCusto, ContaPagar.Codigo_CentroCusto == CentroCusto.Codigo_CentroCusto)
            .outerjoin(PlanoConta, ContaPagar.Codigo_ContaContabil == PlanoConta.Codigo_ContaContabil)
            .filter(extract('year', dataDigitacaoEfetiva) == ano)
            .filter(extract('month', dataDigitacaoEfetiva).in_(mesesSelecionados))
            .filter(ContaPagar.Opcao_StatusContaPagar.in_(self.STATUS_CONSIDERADOS))
            .filter(valorEfetivoContaPagar != 0)
        )

        # Reaplica os filtros padronizados e o filtro opcional de filial.
        query = self._aplicarFiltrosComuns(
            query,
            ContaPagar.Codigo_CentroCusto,
            ContaPagar.Codigo_ContaContabil,
            ContaPagar.Codigo_EmpresaMatriz,
            idsCentros,
            None,
            codigoEmpresaMatriz,
        )
        query = self._aplicarFiltroFilial(query, ContaPagar.Codigo_Empresa, filiaisSelecionadas)

        return query.group_by(
            grupoCodigo,
            grupoDescricao,
            subconsultaFiliaisConsolidadas.c.nomeFilial,
            CentroCusto.Codigo_CentroCusto,
            CentroCusto.Numero_CentroCusto,
            CentroCusto.Nome_CentroCusto,
            PlanoConta.Codigo_ContaContabil,
            PlanoConta.Numero_ContaContabil,
            PlanoConta.Descricao_ContaContabil,
        )

    def _obterRegistroConsolidado(self, acumulador, linha):
        """Obtém/cria registro acumulador para o relatório mensal consolidado."""
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
                'codigoCentroCusto': str(int(linha.codigoCentroCusto)) if getattr(linha, 'codigoCentroCusto', None) is not None else None,
                'codigoContaContabil': str(int(linha.codigoContaContabil)) if getattr(linha, 'codigoContaContabil', None) is not None else None,
                'codigoFornecedor': str(int(linha.codigoFornecedor)) if getattr(linha, 'codigoFornecedor', None) is not None else None,
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

    def _obterRegistroAnalitico(self, acumulador, linha):
        """Obtém/cria registro acumulador para o relatório analítico por grupo e conta."""
        grupo = (str(getattr(linha, 'descricaoGrupo', '') or '').strip()) or 'Sem grupo orçamentário'
        filial = (str(getattr(linha, 'nomeFilial', '') or '').strip()) or 'Sem filial vinculada'
        numeroConta = str(getattr(linha, 'numeroContaContabil', '') or '').strip()
        descricaoConta = str(getattr(linha, 'descricaoContaContabil', '') or '').strip()
        contaContabil = self._montarDescricaoComposta(
            numeroConta,
            descricaoConta,
            'Sem conta contábil vinculada'
        )
        chaveConta = self._formatarIdFiltro(getattr(linha, 'codigoContaContabil', None)) or contaContabil
        chave = (grupo, chaveConta)

        if chave not in acumulador:
            acumulador[chave] = {
                'grupo': grupo,
                'codigoContaContabil': chaveConta,
                'numeroContaContabil': numeroConta or None,
                'descricaoContaContabil': descricaoConta or contaContabil,
                'contaContabil': contaContabil,
                'filiais': set(),
                'orcado': 0.0,
                'realizadoTotal': 0.0,
                'realizadoComBudget': 0.0,
                '_centrosCusto': set(),
            }

        idCentro = self._formatarIdFiltro(getattr(linha, 'codigoCentroCusto', None))
        if idCentro:
            acumulador[chave]['_centrosCusto'].add(idCentro)

        acumulador[chave]['filiais'].add(filial)

        return acumulador[chave]

    def _obterOpcoesFiliaisAnalitico(self, ano, idsCentros, codigoEmpresaMatriz):
        """Lista filiais disponíveis no analítico com base em orçamento e realizado."""
        subconsultaFiliais = self._obterSubconsultaFiliais()
        filiais = set()

        queryOrcado = (
            # Busca filiais que aparecem no ORÇADO dentro do recorte informado.
            self.session.query(subconsultaFiliais.c.nomeFilial.label('nomeFilial'))
            .select_from(BudgetItem)
            .join(Budget, BudgetItem.Codigo_Budget == Budget.Codigo_Budget)
            .join(subconsultaFiliais, BudgetItem.Codigo_Empresa == subconsultaFiliais.c.codigoEmpresa)
            .filter(Budget.Ano_Vigencia == ano)
        )

        # Aplica os filtros de centro/empresa no conjunto de filiais vindas do orçamento.
        queryOrcado = self._aplicarFiltrosComuns(
            queryOrcado,
            BudgetItem.Codigo_CentroCusto,
            BudgetItem.Codigo_ContaContabil,
            BudgetItem.Codigo_EmpresaMatriz,
            idsCentros,
            None,
            codigoEmpresaMatriz,
        )

        for linha in queryOrcado.distinct().all():
            if linha.nomeFilial:
                filiais.add(str(linha.nomeFilial).strip())

        subconsultaDataDigitacaoNotaFiscal = self._obterSubconsultaDataDigitacaoNotaFiscal()
        dataDigitacaoEfetiva = self._obterDataDigitacaoEfetivaContaPagar(subconsultaDataDigitacaoNotaFiscal)

        queryStatus = (
            # Busca filiais que aparecem no REALIZADO (contas a pagar) para o mesmo recorte.
            self.session.query(subconsultaFiliais.c.nomeFilial.label('nomeFilial'))
            .select_from(ContaPagar)
            .outerjoin(
                subconsultaDataDigitacaoNotaFiscal,
                ContaPagar.Codigo_ContaPagar == subconsultaDataDigitacaoNotaFiscal.c.codigoContaPagar,
            )
            .join(subconsultaFiliais, ContaPagar.Codigo_Empresa == subconsultaFiliais.c.codigoEmpresa)
            .filter(extract('year', dataDigitacaoEfetiva) == ano)
            .filter(ContaPagar.Opcao_StatusContaPagar.in_(self.STATUS_CONSIDERADOS))
        )

        # Aplica os filtros de centro/empresa no conjunto de filiais vindas do realizado.
        queryStatus = self._aplicarFiltrosComuns(
            queryStatus,
            ContaPagar.Codigo_CentroCusto,
            ContaPagar.Codigo_ContaContabil,
            ContaPagar.Codigo_EmpresaMatriz,
            idsCentros,
            None,
            codigoEmpresaMatriz,
        )

        for linha in queryStatus.distinct().all():
            if linha.nomeFilial:
                filiais.add(str(linha.nomeFilial).strip())

        return sorted(filiais, key=lambda valor: valor.lower())

    def _obterConsultaRelacionamentosOrcados(self, ano, idsCentros, idsContasContabeis, codigoEmpresaMatriz):
        """Monta consulta de relacionamentos válidos com base em dados orçados."""
        query = (
            # Relacionamentos possíveis entre centro e conta no ORÇADO.
            # Apenas linhas com algum valor de orçamento diferente de zero entram no resultado.
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

        # Filtros do contexto atual (empresa, centros e contas selecionadas).
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
        """Monta consulta de relacionamentos válidos com base em dados realizados."""
        subconsultaDataDigitacaoNotaFiscal = self._obterSubconsultaDataDigitacaoNotaFiscal()
        dataDigitacaoEfetiva = self._obterDataDigitacaoEfetivaContaPagar(subconsultaDataDigitacaoNotaFiscal)
        valorEfetivoContaPagar = self._obterValorEfetivoContaPagar()
        query = (
            # Relacionamentos possíveis entre centro e conta no REALIZADO.
            # Considera apenas títulos em status válidos e com valor efetivo diferente de zero.
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

        # Filtros do contexto atual (empresa, centros e contas selecionadas).
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
        """Converte relacionamentos em opções de filtros de centro de custo e conta."""
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
        """Reúne opções de filtros combinando fontes de orçamento e realizado."""
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
        """Consolida os detalhes mensais do relatório base em memória."""
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
        """Transforma os acumuladores mensais no payload final do relatório consolidado."""
        meses = self._obterEstruturaMeses()

        for numeroMes, linhasMes in detalhesPorMes.items():
            detalhes = []
            centrosCustoMes = set()
            totalOrcado = 0.0
            totalEmAprovacao = 0.0
            totalAprovado = 0.0
            totalRealizado = 0.0
            totalEmAprovacaoComBudget = 0.0
            totalAprovadoComBudget = 0.0
            totalComBudget = 0.0

            for linha in linhasMes.values():
                linha['saldo'] = linha['orcado'] - linha['total']
                linha['saldoComBudget'] = linha['orcado'] - linha['totalComBudget']
                detalhes.append(linha)
                centrosCustoMes.add(linha['centroCusto'])

                totalOrcado += linha['orcado']
                totalEmAprovacao += linha['emAprovacao']
                totalAprovado += linha['aprovado']
                totalRealizado += linha['total']
                totalEmAprovacaoComBudget += linha['emAprovacaoComBudget']
                totalAprovadoComBudget += linha['aprovadoComBudget']
                totalComBudget += linha['totalComBudget']

            detalhes.sort(key=lambda item: (
                item['centroCusto'],
                item['contaContabil'],
                item['fornecedor']
            ))

            meses[numeroMes]['detalhes'] = detalhes
            meses[numeroMes]['orcado'] = totalOrcado
            meses[numeroMes]['emAprovacao'] = totalEmAprovacao
            meses[numeroMes]['aprovado'] = totalAprovado
            meses[numeroMes]['total'] = totalRealizado
            meses[numeroMes]['emAprovacaoComBudget'] = totalEmAprovacaoComBudget
            meses[numeroMes]['aprovadoComBudget'] = totalAprovadoComBudget
            meses[numeroMes]['totalComBudget'] = totalComBudget
            meses[numeroMes]['saldo'] = totalOrcado - totalRealizado
            meses[numeroMes]['saldoComBudget'] = totalOrcado - totalComBudget
            meses[numeroMes]['centrosCusto'] = len(centrosCustoMes)

        return {
            'meses': [meses[numero] for numero, _, _, _, _ in self.MESES_RELATORIO]
        }

    def _aplicarFiltrosComuns(
        self,
        query,
        campoCentroCusto,
        campoContaContabil,
        campoEmpresaMatriz,
        idsCentros,
        idsContasContabeis,
        codigoEmpresaMatriz,
    ):
        """Aplica filtros compartilhados por múltiplas consultas do relatório."""
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

    def obterFiltrosAnalitico(self, ano, filtroEmpresa='Todos', filtroCentroCusto='Todos'):
        """Retorna filtros disponíveis para a visão analítica do orçamento."""
        codigoEmpresaMatriz = self._resolverCodigoEmpresaMatriz(filtroEmpresa)
        idsCentros = self._extrairIdsNumericos(filtroCentroCusto)
        centrosDisponiveis, _ = self._obterOpcoesFiltros(
            ano,
            None,
            None,
            codigoEmpresaMatriz,
        )
        filiaisDisponiveis = self._obterOpcoesFiliaisAnalitico(
            ano,
            idsCentros,
            codigoEmpresaMatriz,
        )

        return {
            'empresas': [
                {'id': 'Todos', 'nome': 'Todas as Empresas'},
                {'id': '1', 'nome': 'Intec'},
                {'id': '2', 'nome': 'Farma'},
            ],
            'meses': [
                {
                    'id': str(numero),
                    'nome': nome,
                    'abreviacao': abreviacao,
                }
                for numero, nome, abreviacao, _, _ in self.MESES_RELATORIO
            ],
            'centrosCusto': centrosDisponiveis,
            'filiais': [
                {
                    'id': filial,
                    'nome': filial,
                }
                for filial in filiaisDisponiveis
            ],
            'filialHabilitada': True,
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

    def gerarRelatorioBudgetAnalitico(self, ano, mes, filtroCentroCusto='Todos', filtroEmpresa='Todos', filtroFilial='Todos'):
        """
        Gera o relatório analítico por grupo e conta contábil para um ou mais meses.

        Args:
            ano (int): Ano de referência para os dados.
            mes (str | int | list): Mês, lista de meses ou 'Todos'.
            filtroCentroCusto (str): IDs de centros de custo separados por vírgula ou 'Todos'.
            filtroEmpresa (str): Código lógico da empresa matriz ('1', '2' ou 'Todos').
            filtroFilial (str): Nome(s) de filial separados por vírgula ou 'Todos'.

        Returns:
            dict: Payload analítico com referência, filtros, resumo e agrupamento por grupo.
        """
        mesesInfo = self._resolverMesesRelatorio(mes)
        codigoEmpresaMatriz = self._resolverCodigoEmpresaMatriz(filtroEmpresa)
        idsCentros = self._extrairIdsNumericos(filtroCentroCusto)
        filiaisSelecionadas = self._extrairValoresTexto(filtroFilial)
        acumulador = {}

        for linha in self._obterConsultaOrcadoAnalitico(
            ano,
            mesesInfo,
            idsCentros,
            codigoEmpresaMatriz,
            filiaisSelecionadas,
        ).all():
            registro = self._obterRegistroAnalitico(acumulador, linha)
            registro['orcado'] += float(linha.orcado or 0.0)

        for linha in self._obterConsultaRealizadoAnalitico(
            ano,
            mesesInfo,
            idsCentros,
            codigoEmpresaMatriz,
            filiaisSelecionadas,
        ).all():
            registro = self._obterRegistroAnalitico(acumulador, linha)
            registro['realizadoTotal'] += float(linha.realizadoTotal or 0.0)
            registro['realizadoComBudget'] += float(linha.realizadoComBudget or 0.0)

        gruposMap = {}
        totalOrcado = 0.0
        totalRealizadoTotal = 0.0
        totalRealizadoComBudget = 0.0

        for registro in acumulador.values():
            orcado = float(registro['orcado'] or 0.0)
            realizadoTotal = float(registro['realizadoTotal'] or 0.0)
            realizadoComBudget = float(registro['realizadoComBudget'] or 0.0)

            contaPayload = {
                'codigoContaContabil': registro['codigoContaContabil'],
                'numeroContaContabil': registro['numeroContaContabil'],
                'descricaoContaContabil': registro['descricaoContaContabil'],
                'contaContabil': registro['contaContabil'],
                'filiais': sorted(registro['filiais'], key=lambda valor: valor.lower()),
                'orcado': orcado,
                'realizadoTotal': realizadoTotal,
                'realizadoComBudget': realizadoComBudget,
                'quantidadeCentrosCusto': len(registro['_centrosCusto']),
            }

            gruposMap.setdefault(registro['grupo'], []).append(contaPayload)
            totalOrcado += orcado
            totalRealizadoTotal += realizadoTotal
            totalRealizadoComBudget += realizadoComBudget

        grupos = []
        for nomeGrupo in sorted(gruposMap.keys(), key=lambda valor: valor.lower()):
            contas = sorted(
                gruposMap[nomeGrupo],
                key=lambda item: (
                    str(item.get('numeroContaContabil') or ''),
                    str(item.get('descricaoContaContabil') or ''),
                )
            )
            orcadoGrupo = sum(item['orcado'] for item in contas)
            realizadoGrupoTotal = sum(item['realizadoTotal'] for item in contas)
            realizadoGrupoComBudget = sum(item['realizadoComBudget'] for item in contas)

            grupos.append({
                'id': nomeGrupo,
                'grupo': nomeGrupo,
                'orcado': orcadoGrupo,
                'realizadoTotal': realizadoGrupoTotal,
                'realizadoComBudget': realizadoGrupoComBudget,
                'quantidadeContas': len(contas),
                'contas': contas,
            })

        totalDiferenca = totalOrcado - totalRealizadoTotal
        totalDiferencaComBudget = totalOrcado - totalRealizadoComBudget
        totalConsumo = None
        totalConsumoComBudget = None
        if totalOrcado > 0:
            totalConsumo = (totalRealizadoTotal / totalOrcado) * 100
            totalConsumoComBudget = (totalRealizadoComBudget / totalOrcado) * 100

        return {
            'referencia': {
                'ano': int(ano),
                'meses': [mes['mes'] for mes in mesesInfo],
                'nomesMeses': [mes['nome'] for mes in mesesInfo],
                'abreviacoesMeses': [mes['abreviacao'] for mes in mesesInfo],
                'descricaoMeses': self._descreverSelecaoMeses(mesesInfo),
            },
            'filtros': {
                'empresa': filtroEmpresa,
                'centroCusto': filtroCentroCusto,
                'filial': filtroFilial,
                'filialHabilitada': True,
            },
            'resumo': {
                'orcado': totalOrcado,
                'realizadoTotal': totalRealizadoTotal,
                'realizadoComBudget': totalRealizadoComBudget,
                'diferenca': totalDiferenca,
                'diferencaComBudget': totalDiferencaComBudget,
                'consumoPercentual': totalConsumo,
                'consumoPercentualComBudget': totalConsumoComBudget,
                'quantidadeGrupos': len(grupos),
                'quantidadeContas': sum(grupo['quantidadeContas'] for grupo in grupos),
            },
            'grupos': grupos,
        }

    def _obterContextoBudgetDetalhes(
        self,
        ano,
        mes,
        idsCentros,
        idsContasContabeis,
        idFornecedor,
        codigoEmpresaMatriz,
        modoSaldo,
    ):
        """Calcula valores de contexto orçamentário para o drill-down do modal de detalhes."""

        # ── Orçado: budget por mês via BudgetItem ──────────────────────────
        queryOrcado = (
            self.session.query(
                *[func.sum(coluna).label(rotulo)
                  for _, _, _, rotulo, coluna in self.MESES_RELATORIO],
            )
            .select_from(BudgetItem)
            .join(Budget, BudgetItem.Codigo_Budget == Budget.Codigo_Budget)
            .filter(Budget.Ano_Vigencia == int(ano))
        )
        queryOrcado = self._aplicarFiltrosComuns(
            queryOrcado,
            BudgetItem.Codigo_CentroCusto,
            BudgetItem.Codigo_ContaContabil,
            BudgetItem.Codigo_EmpresaMatriz,
            idsCentros,
            idsContasContabeis,
            codigoEmpresaMatriz,
        )
        if idFornecedor is not None:
            queryOrcado = queryOrcado.filter(BudgetItem.Codigo_Fornecedor == idFornecedor)

        linhaOrcado = queryOrcado.one_or_none()

        mesAtual = int(mes)
        budgetMes = 0.0
        budgetAnual = 0.0
        budgetAcumulado = 0.0
        if linhaOrcado:
            for numero, _, _, rotulo, _ in self.MESES_RELATORIO:
                valor = float(getattr(linhaOrcado, rotulo, None) or 0)
                budgetAnual += valor
                if numero == mesAtual:
                    budgetMes = valor
                if numero <= mesAtual:
                    budgetAcumulado += valor

        # ── Realizado: consumo acumulado meses 1..mes ──────────────────────
        subconsultaNF = self._obterSubconsultaDataDigitacaoNotaFiscal()
        dataEfetiva = self._obterDataDigitacaoEfetivaContaPagar(subconsultaNF)
        valorEfetivo = self._obterValorEfetivoContaPagar()

        queryAcumulado = (
            self.session.query(
                extract('month', dataEfetiva).label('mesCompetencia'),
                func.sum(valorEfetivo).label('totalMes'),
            )
            .select_from(ContaPagar)
            .outerjoin(subconsultaNF, ContaPagar.Codigo_ContaPagar == subconsultaNF.c.codigoContaPagar)
            .filter(extract('year', dataEfetiva) == int(ano))
            .filter(extract('month', dataEfetiva) <= mesAtual)
            .filter(ContaPagar.Opcao_StatusContaPagar.in_(self.STATUS_CONSIDERADOS))
            .group_by(extract('month', dataEfetiva))
        )

        if codigoEmpresaMatriz is not None:
            queryAcumulado = queryAcumulado.filter(ContaPagar.Codigo_EmpresaMatriz == codigoEmpresaMatriz)
        if idsCentros:
            queryAcumulado = queryAcumulado.filter(ContaPagar.Codigo_CentroCusto.in_(idsCentros))
        if idsContasContabeis:
            queryAcumulado = queryAcumulado.filter(ContaPagar.Codigo_ContaContabil.in_(idsContasContabeis))
        if idFornecedor is not None:
            queryAcumulado = queryAcumulado.filter(ContaPagar.Codigo_Fornecedor == idFornecedor)
        if modoSaldo == 'somente_budget':
            queryAcumulado = queryAcumulado.filter(ContaPagar.Codigo_BudgetItem.isnot(None))

        consumoAcumuladoAtual = 0.0
        consumoAcumuladoAnterior = 0.0
        for linha in queryAcumulado.all():
            valor = float(linha.totalMes or 0)
            consumoAcumuladoAtual += valor
            if int(linha.mesCompetencia) < mesAtual:
                consumoAcumuladoAnterior += valor

        return {
            'budgetAnual': budgetAnual,
            'budgetMes': budgetMes,
            'budgetAcumulado': budgetAcumulado,
            'consumoAcumuladoAnterior': consumoAcumuladoAnterior,
            'consumoAcumuladoAtual': consumoAcumuladoAtual,
        }

    def obterDetalhesBudget(
        self,
        ano,
        mes,
        codigoCentroCusto=None,
        codigoContaContabil=None,
        codigoFornecedor=None,
        modoSaldo='todos_itens',
        filtroEmpresa='Todos',
    ):
        """
        Retorna os lançamentos individuais de ContaPagar que compõem a linha
        selecionada no relatório gerencial de Budget (drill-down por nível).

        Args:
            ano (int): Ano de referência.
            mes (int): Mês de competência (1–12).
            codigoCentroCusto (str|None): ID(s) numérico(s) do centro de custo (vírgula separado) ou None para todos.
            codigoContaContabil (str|None): ID(s) numérico(s) da conta contábil (vírgula separado) ou None para todas.
            codigoFornecedor (str|None): ID numérico do fornecedor ou None para todos.
            modoSaldo (str): 'todos_itens' considera todos os lançamentos;
                             'somente_budget' considera apenas os vinculados a budget.
            filtroEmpresa (str): Código lógico da empresa matriz.

        Returns:
            dict: Payload com lista de lançamentos, totalizadores e contexto orçamentário.
        """
        STATUS_DESCRICAO = {
            1: 'Em Aprovação',
            2: 'Em Aprovação',
            3: 'Aprovado',
            5: 'Aprovado',
        }

        codigoEmpresaMatriz = self._resolverCodigoEmpresaMatriz(filtroEmpresa)
        idsCentros = self._extrairIdsNumericos(codigoCentroCusto)
        idsContasContabeis = self._extrairIdsNumericos(codigoContaContabil)
        idFornecedor = int(codigoFornecedor) if codigoFornecedor else None

        subconsultaNF = self._obterSubconsultaDataDigitacaoNotaFiscal()
        dataEfetiva = self._obterDataDigitacaoEfetivaContaPagar(subconsultaNF)
        valorEfetivo = self._obterValorEfetivoContaPagar()

        query = (
            self.session.query(
                ContaPagar.Codigo_ContaPagar,
                ContaPagar.Opcao_TipoDocumento,
                ContaPagar.Numero_Documento,
                ContaPagar.Sequencia_Item,
                ContaPagar.Descricao_Item,
                ContaPagar.Data_Emissao,
                ContaPagar.Data_Digitacao,
                ContaPagar.Data_Aprovacao,
                ContaPagar.Valor_ContaPagar,
                ContaPagar.Valor_RecebidoNotaFiscal,
                ContaPagar.Opcao_StatusContaPagar,
                ContaPagar.Nome_UltimoAprovador,
                ContaPagar.Codigo_BudgetItem,
                ContaPagar.DescricaoCondicaoPagamento,
                dataEfetiva.label('dataDigitacaoEfetiva'),
                valorEfetivo.label('valorEfetivo'),
                Fornecedor.Codigo_Fornecedor.label('codigoFornecedorJoin'),
                Fornecedor.Nome_Fornecedor,
                CentroCusto.Numero_CentroCusto,
                CentroCusto.Nome_CentroCusto,
                PlanoConta.Numero_ContaContabil,
                PlanoConta.Descricao_ContaContabil,
            )
            .select_from(ContaPagar)
            .outerjoin(subconsultaNF, ContaPagar.Codigo_ContaPagar == subconsultaNF.c.codigoContaPagar)
            .outerjoin(CentroCusto, ContaPagar.Codigo_CentroCusto == CentroCusto.Codigo_CentroCusto)
            .outerjoin(PlanoConta, ContaPagar.Codigo_ContaContabil == PlanoConta.Codigo_ContaContabil)
            .outerjoin(Fornecedor, ContaPagar.Codigo_Fornecedor == Fornecedor.Codigo_Fornecedor)
            .filter(extract('year', dataEfetiva) == int(ano))
            .filter(extract('month', dataEfetiva) == int(mes))
            .filter(ContaPagar.Opcao_StatusContaPagar.in_(self.STATUS_CONSIDERADOS))
        )

        if codigoEmpresaMatriz is not None:
            query = query.filter(ContaPagar.Codigo_EmpresaMatriz == codigoEmpresaMatriz)
        if idsCentros:
            query = query.filter(ContaPagar.Codigo_CentroCusto.in_(idsCentros))
        if idsContasContabeis:
            query = query.filter(ContaPagar.Codigo_ContaContabil.in_(idsContasContabeis))
        if idFornecedor is not None:
            query = query.filter(ContaPagar.Codigo_Fornecedor == idFornecedor)
        if modoSaldo == 'somente_budget':
            query = query.filter(ContaPagar.Codigo_BudgetItem.isnot(None))

        resultados = query.order_by(
            dataEfetiva,
            ContaPagar.Codigo_ContaPagar,
        ).all()

        lancamentos = []
        for linha in resultados:
            descCentroCusto = self._montarDescricaoComposta(
                getattr(linha, 'Numero_CentroCusto', None),
                getattr(linha, 'Nome_CentroCusto', None),
                'Não informado',
            )
            descContaContabil = self._montarDescricaoComposta(
                getattr(linha, 'Numero_ContaContabil', None),
                getattr(linha, 'Descricao_ContaContabil', None),
                'Não informada',
            )

            lancamentos.append({
                'codigoConta': linha.Codigo_ContaPagar,
                'tipoDocumento': (linha.Opcao_TipoDocumento or '').strip(),
                'numeroDocumento': (linha.Numero_Documento or '').strip(),
                'sequenciaItem': (linha.Sequencia_Item or '').strip(),
                'descricaoItem': (linha.Descricao_Item or '').strip(),
                'dataEmissao': linha.Data_Emissao.strftime('%d/%m/%Y') if linha.Data_Emissao else None,
                'dataDigitacao': linha.Data_Digitacao.strftime('%d/%m/%Y') if linha.Data_Digitacao else None,
                'dataEfetiva': linha.dataDigitacaoEfetiva.strftime('%d/%m/%Y') if linha.dataDigitacaoEfetiva else None,
                'dataAprovacao': linha.Data_Aprovacao.strftime('%d/%m/%Y') if linha.Data_Aprovacao else None,
                'valorContaPagar': float(linha.Valor_ContaPagar or 0),
                'valorNotaFiscal': float(linha.Valor_RecebidoNotaFiscal or 0),
                'valorEfetivo': float(linha.valorEfetivo or 0),
                'status': linha.Opcao_StatusContaPagar,
                'descricaoStatus': STATUS_DESCRICAO.get(linha.Opcao_StatusContaPagar, str(linha.Opcao_StatusContaPagar or '')),
                'ultimoAprovador': (linha.Nome_UltimoAprovador or '').strip(),
                'codigoBudgetItem': linha.Codigo_BudgetItem,
                'possuiBudget': linha.Codigo_BudgetItem is not None,
                'condicaoPagamento': (linha.DescricaoCondicaoPagamento or '').strip(),
                'centroCusto': descCentroCusto,
                'contaContabil': descContaContabil,
                'fornecedor': (getattr(linha, 'Nome_Fornecedor', None) or '').strip() or 'Sem fornecedor vinculado',
            })

        totalEmAprovacao = sum(l['valorEfetivo'] for l in lancamentos if l['status'] in self.STATUS_EM_APROVACAO)
        totalAprovado = sum(l['valorEfetivo'] for l in lancamentos if l['status'] in self.STATUS_APROVADO)
        totalMes = totalEmAprovacao + totalAprovado

        ctx = self._obterContextoBudgetDetalhes(
            ano, mes, idsCentros, idsContasContabeis, idFornecedor, codigoEmpresaMatriz, modoSaldo
        )

        saldoBudgetMensal  = ctx['budgetMes'] - totalMes
        pctBudgetMes       = round(totalMes / ctx['budgetMes'] * 100, 2) if ctx['budgetMes'] else 0.0
        saldoBudgetAcumulado = ctx['budgetAcumulado'] - ctx['consumoAcumuladoAtual']
        pctBudgetAno         = round(ctx['consumoAcumuladoAtual'] / ctx['budgetAnual'] * 100, 2) if ctx['budgetAnual'] else 0.0

        return {
            'lancamentos': lancamentos,
            'totalEmAprovacao': totalEmAprovacao,
            'totalAprovado': totalAprovado,
            'totalGeral': totalMes,
            'quantidade': len(lancamentos),
            # Contexto orçamentário para os KPIs do modal
            'budgetAnual': ctx['budgetAnual'],
            'budgetMes': ctx['budgetMes'],
            'consumoAcumuladoAnterior': ctx['consumoAcumuladoAnterior'],
            'totalMes': totalMes,
            'saldoBudgetMensal': saldoBudgetMensal,
            'pctBudgetMes': pctBudgetMes,
            'consumoAcumuladoAtual': ctx['consumoAcumuladoAtual'],
            'saldoBudgetAcumulado': saldoBudgetAcumulado,
            'pctBudgetAno': pctBudgetAno,
        }