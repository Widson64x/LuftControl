import os
import uuid
from copy import copy
from datetime import datetime
from decimal import Decimal, InvalidOperation

from openpyxl import load_workbook
from sqlalchemy import extract, func

from Db.Connections import GetSqlServerSession
from Models.SqlServer.Budget import Budget, BudgetItem
from Models.SqlServer.ContaPagar import ContaPagar, ContaPagarNotaFiscal, PlanoConta
from Models.SqlServer.Fornecedor import Fornecedor
from Modules.SISTEMA.Services.GestorCentroCustoService import GestorCentroCustoService


class AcompanhamentoMensalService:
    PASTA_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', 'Data', 'Base'))
    ARQUIVO_TEMPLATE = os.path.join(PASTA_BASE, 'Template - budget - MENSAL.xlsx')
    PASTA_TEMPORARIA = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '../../..', 'Data', 'Temp', 'BudgetAcompanhamentoMensal')
    )

    STATUS_CONSIDERADOS = (1, 2, 3, 5)
    LINHA_INTRO_DETALHE = 18
    LINHA_INICIAL_DETALHE = 19
    QUANTIDADE_MINIMA_LINHAS = 9
    COLUNAS_PLANILHA = tuple(range(1, 11))
    FORMATO_DATA = 'dd/mm/yyyy'
    FORMATO_MOEDA = '#,##0.00'

    MESES = (
        (1, 'Janeiro', 'Jan', BudgetItem.Valor_JaneiroO),
        (2, 'Fevereiro', 'Fev', BudgetItem.Valor_FevereiroO),
        (3, 'Março', 'Mar', BudgetItem.Valor_MarcoO),
        (4, 'Abril', 'Abr', BudgetItem.Valor_AbrilO),
        (5, 'Maio', 'Mai', BudgetItem.Valor_MaioO),
        (6, 'Junho', 'Jun', BudgetItem.Valor_JunhoO),
        (7, 'Julho', 'Jul', BudgetItem.Valor_JulhoO),
        (8, 'Agosto', 'Ago', BudgetItem.Valor_AgostoO),
        (9, 'Setembro', 'Set', BudgetItem.Valor_SetembroO),
        (10, 'Outubro', 'Out', BudgetItem.Valor_OutubroO),
        (11, 'Novembro', 'Nov', BudgetItem.Valor_NovembroO),
        (12, 'Dezembro', 'Dez', BudgetItem.Valor_DezembroO),
    )

    def __init__(self):
        self._gestor_service = GestorCentroCustoService()
        self._garantirEstrutura()

    def obterContextoGestor(self, codigo_usuario):
        gestor = self._gestor_service.obterGestorConfigurado(codigo_usuario)
        agora = datetime.now()

        return {
            'gestor': gestor,
            'centros_custo': list(gestor.get('centros_custo', [])) if gestor else [],
            'ano_padrao': agora.year,
            'ano_opcoes': [agora.year - indice for indice in range(5)],
            'meses_preenchidos': agora.month,
            'template_disponivel': os.path.exists(self.ARQUIVO_TEMPLATE),
        }

    def gerarArquivo(self, codigo_usuario, ano=None, codigo_centro_custo=None):
        agora = datetime.now()
        ano_referencia = self._normalizarAno(ano or agora.year, agora.year)
        gestor = self._obterGestorObrigatorio(codigo_usuario)
        centro = self._resolverCentroSelecionado(gestor, codigo_centro_custo)

        sessao = GetSqlServerSession()
        try:
            codigo_centro_decimal = self._converterCodigoDecimal(centro['codigo'])
            totais_budget = self._obterTotaisBudget(sessao, ano_referencia, codigo_centro_decimal)
            lancamentos_mensais = self._obterLancamentosMensais(sessao, ano_referencia, codigo_centro_decimal)
        finally:
            sessao.close()

        workbook = load_workbook(self.ARQUIVO_TEMPLATE)
        try:
            self._atualizarAbaLista(workbook['Lista'], ano_referencia, centro)

            linha_acumulada_anterior = None
            nome_aba_anterior = None
            for numero_mes, nome_aba, abreviacao, _ in self.MESES:
                planilha = workbook[nome_aba]
                lancamentos_mes = lancamentos_mensais.get(numero_mes, [])
                linha_acumulada_atual = self._preencherAbaMensal(
                    planilha=planilha,
                    ano=ano_referencia,
                    numero_mes=numero_mes,
                    abreviacao_mes=abreviacao,
                    gestor=gestor,
                    centro=centro,
                    total_ano=totais_budget['total_ano'],
                    total_mes=totais_budget['meses'].get(numero_mes, 0.0),
                    lancamentos=lancamentos_mes,
                    nome_aba_anterior=nome_aba_anterior,
                    linha_acumulada_anterior=linha_acumulada_anterior,
                )
                nome_aba_anterior = nome_aba
                linha_acumulada_anterior = linha_acumulada_atual

            nome_seguro_centro = self._normalizarNomeArquivo(centro['numero'])
            nome_seguro_responsavel = self._normalizarNomeArquivo(gestor['nome_usuario'])
            nome_arquivo = (
                f"acompanhamento_{uuid.uuid4().hex[:8]}_{ano_referencia}_{nome_seguro_centro}_{nome_seguro_responsavel}.xlsx"
            )
            caminho_saida = os.path.join(self.PASTA_TEMPORARIA, nome_arquivo)
            workbook.save(caminho_saida)
        finally:
            workbook.close()

        return {
            'tokenDownload': nome_arquivo,
            'nomeArquivo': nome_arquivo,
            'ano': ano_referencia,
            'centroCusto': centro,
            'gestor': {
                'codigo_usuario': gestor['codigo_usuario'],
                'nome_usuario': gestor['nome_usuario'],
                'cargo': gestor.get('cargo') or 'Gestor',
            },
            'mesesPreenchidos': min(agora.month, 12) if ano_referencia == agora.year else 12,
        }

    def obterCaminhoArquivoGerado(self, token_download):
        token_seguro = os.path.basename(str(token_download or '').strip())
        if not token_seguro or not token_seguro.startswith('acompanhamento_'):
            raise ValueError('Arquivo gerado inválido ou expirado.')

        caminho_arquivo = os.path.join(self.PASTA_TEMPORARIA, token_seguro)
        if not os.path.exists(caminho_arquivo):
            raise ValueError('Arquivo gerado inválido ou expirado.')

        return caminho_arquivo

    def _garantirEstrutura(self):
        os.makedirs(self.PASTA_TEMPORARIA, exist_ok=True)
        if not os.path.exists(self.ARQUIVO_TEMPLATE):
            raise ValueError(
                'O template padrão do Budget não foi encontrado em Data/Base/Template - budget - MENSAL.xlsx.'
            )

    def _normalizarAno(self, ano, ano_atual):
        try:
            ano_normalizado = int(str(ano).strip())
        except (TypeError, ValueError):
            raise ValueError('Ano inválido para gerar a planilha de acompanhamento.')

        if ano_normalizado < 2020 or ano_normalizado > ano_atual:
            raise ValueError('Selecione um ano atual ou anterior para gerar a planilha.')

        return ano_normalizado

    def _obterGestorObrigatorio(self, codigo_usuario):
        gestor = self._gestor_service.obterGestorConfigurado(codigo_usuario)
        if not gestor:
            raise ValueError('Seu usuário não possui centros de custo configurados para essa rotina.')

        centros = gestor.get('centros_custo', [])
        if not centros:
            raise ValueError('Seu usuário não possui centros de custo configurados para essa rotina.')

        return gestor

    def _resolverCentroSelecionado(self, gestor, codigo_centro_custo):
        # Cria uma cópia da lista de centros para evitar mutações acidentais e 
        # facilitar a busca
        centros = list(gestor.get('centros_custo', []))
        
        # Se a lista tiver apenas um centro e nenhum código for fornecido, 
        # retorna esse centro diretamente
        if len(centros) == 1 and not codigo_centro_custo:
            return centros[0]

        # Cria uma versão normalizada do código de centro de custo para comparação,
        codigo_normalizado = str(codigo_centro_custo or '').strip()
        # Se o código normalizado estiver vazio, significa que o usuário não 
        # selecionou um centro válido
        if not codigo_normalizado:
            raise ValueError('Selecione o centro de custo que sera usado para gerar a planilha.')
        
        # Para para cada centro de custo na lista do gestor, normaliza o código do centro e 
        # compara com o código fornecido
        for centro in centros:
            if str(centro.get('codigo')) == codigo_normalizado:
                # Retorna o centro correspondente se encontrar uma correspondência exata
                return centro

        raise ValueError('O centro de custo selecionado nao pertence ao gestor informado.')

    def _converterCodigoDecimal(self, valor):
        try:
            return Decimal(str(valor).strip())
        except (InvalidOperation, AttributeError, ValueError):
            raise ValueError('Codigo de centro de custo invalido para gerar a planilha.')

    def _obterTotaisBudget(self, sessao, ano, codigo_centro_custo):
        colunas_mes = [
            func.coalesce(func.sum(coluna), 0).label(f'mes_{numero}')
            for numero, _, _, coluna in self.MESES
        ]

        registro = (
            sessao.query(*colunas_mes)
            .select_from(BudgetItem)
            .join(Budget, BudgetItem.Codigo_Budget == Budget.Codigo_Budget)
            .filter(Budget.Ano_Vigencia == ano)
            .filter(BudgetItem.Codigo_CentroCusto == codigo_centro_custo)
            .one()
        )

        meses = {
            numero: float(getattr(registro, f'mes_{numero}') or 0.0)
            for numero, _, _, _ in self.MESES
        }
        return {
            'meses': meses,
            'total_ano': sum(meses.values()),
        }

    def _obterLancamentosMensais(self, sessao, ano, codigo_centro_custo):
        subconsulta_data_nota = (
            sessao.query(
                ContaPagarNotaFiscal.Codigo_ContaPagar.label('codigoContaPagar'),
                func.max(ContaPagarNotaFiscal.Data_Digitacao).label('dataDigitacaoNotaFiscal'),
            )
            .group_by(ContaPagarNotaFiscal.Codigo_ContaPagar)
            .subquery()
        )

        data_efetiva = func.coalesce(subconsulta_data_nota.c.dataDigitacaoNotaFiscal, ContaPagar.Data_Digitacao)
        valor_efetivo = func.coalesce(
            func.nullif(ContaPagar.Valor_RecebidoNotaFiscal, 0),
            ContaPagar.Valor_ContaPagar,
            0,
        )

        registros = (
            sessao.query(
                extract('month', data_efetiva).label('mesCompetencia'),
                PlanoConta.Numero_ContaContabil.label('numeroContaContabil'),
                PlanoConta.Descricao_ContaContabil.label('descricaoContaContabil'),
                Fornecedor.Nome_Fornecedor.label('nomeFornecedor'),
                ContaPagar.Descricao_Item.label('descricaoItem'),
                ContaPagar.Numero_Documento.label('numeroDocumento'),
                ContaPagar.Data_Emissao.label('dataEmissao'),
                data_efetiva.label('dataEntrega'),
                valor_efetivo.label('valor'),
            )
            .select_from(ContaPagar)
            .outerjoin(
                subconsulta_data_nota,
                ContaPagar.Codigo_ContaPagar == subconsulta_data_nota.c.codigoContaPagar,
            )
            .outerjoin(PlanoConta, ContaPagar.Codigo_ContaContabil == PlanoConta.Codigo_ContaContabil)
            .outerjoin(Fornecedor, ContaPagar.Codigo_Fornecedor == Fornecedor.Codigo_Fornecedor)
            .filter(ContaPagar.Codigo_CentroCusto == codigo_centro_custo)
            .filter(extract('year', data_efetiva) == ano)
            .filter(ContaPagar.Opcao_StatusContaPagar.in_(self.STATUS_CONSIDERADOS))
            .filter(valor_efetivo != 0)
            .order_by(
                extract('month', data_efetiva),
                data_efetiva,
                ContaPagar.Data_Emissao,
                PlanoConta.Numero_ContaContabil,
                Fornecedor.Nome_Fornecedor,
            )
            .all()
        )

        lancamentos_por_mes = {
            numero: []
            for numero, _, _, _ in self.MESES
        }

        for registro in registros:
            numero_mes = int(registro.mesCompetencia or 0)
            if numero_mes not in lancamentos_por_mes:
                continue

            conta = self._montarTextoConta(registro.numeroContaContabil, registro.descricaoContaContabil)
            fornecedor = self._normalizarTexto(registro.nomeFornecedor) or 'Sem fornecedor vinculado'
            descricao = (
                self._normalizarTexto(registro.descricaoItem)
                or self._normalizarTexto(registro.numeroDocumento)
                or 'Sem descricao'
            )

            lancamentos_por_mes[numero_mes].append(
                {
                    'conta_contabil': conta,
                    'fornecedor': fornecedor,
                    'descricao': descricao,
                    'data_emissao': registro.dataEmissao,
                    'data_entrega': registro.dataEntrega,
                    'valor': float(registro.valor or 0.0),
                }
            )

        return lancamentos_por_mes

    def _montarTextoConta(self, numero, descricao):
        numero_texto = self._normalizarTexto(numero)

        """ 
        - Comentado para evitar que a descrição da conta contabil 
        seja omitida quando o número for preenchido, mas a descrição 
        estiver vazia ou nula.


        descricao_texto = self._normalizarTexto(descricao)
        if numero_texto and descricao_texto:
            return f'{numero_texto} - {descricao_texto}'
        return numero_texto or descricao_texto or 'Sem conta contabil vinculada'
        """

        return numero_texto or 'Sem conta contabil vinculada'

    def _atualizarAbaLista(self, planilha, ano, centro):
        for indice, (_, _, abreviacao, _) in enumerate(self.MESES, start=2):
            planilha.cell(row=indice, column=2).value = f'{abreviacao}/{ano}'

        for indice in range(2, 200):
            planilha.cell(row=indice, column=4).value = None
            planilha.cell(row=indice, column=5).value = None

        planilha.cell(row=2, column=4).value = self._normalizarNumero(centro['codigo'])
        planilha.cell(row=2, column=5).value = centro['nome']

    def _preencherAbaMensal(
        self,
        planilha,
        ano,
        numero_mes,
        abreviacao_mes,
        gestor,
        centro,
        total_ano,
        total_mes,
        lancamentos,
        nome_aba_anterior,
        linha_acumulada_anterior,
    ):
        modelos = self._capturarModelosLinha(planilha)
        quantidade_linhas = max(self.QUANTIDADE_MINIMA_LINHAS, len(lancamentos))

        linha_total = self.LINHA_INICIAL_DETALHE + quantidade_linhas
        linha_saldo_mensal = linha_total + 2
        linha_percentual_mensal = linha_total + 3
        linha_acumulado = linha_total + 6
        linha_saldo_acumulado = linha_total + 7
        linha_percentual_ano = linha_total + 8
        linha_aprovador = linha_total + 11
        linha_data = linha_total + 12
        linha_final = linha_data

        self._limparRegiaoDinamica(planilha, max(planilha.max_row, linha_final))

        self._aplicarModeloLinha(planilha, self.LINHA_INTRO_DETALHE, modelos['intro'])
        for deslocamento in range(quantidade_linhas):
            linha_atual = self.LINHA_INICIAL_DETALHE + deslocamento
            self._aplicarModeloLinha(planilha, linha_atual, modelos['detalhe'])

        self._aplicarModeloLinha(planilha, linha_total, modelos['total'])
        self._aplicarModeloLinha(planilha, linha_total + 1, modelos['blank_1'])
        self._aplicarModeloLinha(planilha, linha_saldo_mensal, modelos['saldo_mensal'])
        self._aplicarModeloLinha(planilha, linha_percentual_mensal, modelos['percentual_mensal'])
        self._aplicarModeloLinha(planilha, linha_percentual_mensal + 1, modelos['blank_2'])
        self._aplicarModeloLinha(planilha, linha_percentual_mensal + 2, modelos['blank_3'])
        self._aplicarModeloLinha(planilha, linha_acumulado, modelos['acumulado'])
        self._aplicarModeloLinha(planilha, linha_saldo_acumulado, modelos['saldo_acumulado'])
        self._aplicarModeloLinha(planilha, linha_percentual_ano, modelos['percentual_ano'])
        self._aplicarModeloLinha(planilha, linha_percentual_ano + 1, modelos['blank_4'])
        self._aplicarModeloLinha(planilha, linha_percentual_ano + 2, modelos['blank_5'])
        self._aplicarModeloLinha(planilha, linha_aprovador, modelos['aprovador'])
        self._aplicarModeloLinha(planilha, linha_data, modelos['data'])

        self._aplicarMesclagens(
            planilha,
            quantidade_linhas=quantidade_linhas,
            linha_total=linha_total,
            linha_saldo_mensal=linha_saldo_mensal,
            linha_percentual_ano=linha_percentual_ano,
            linha_aprovador=linha_aprovador,
            linha_data=linha_data,
        )

        planilha['D1'] = f'ANÁLISE  MENSAL  BUDGET {ano}'
        planilha['C6'] = f'{abreviacao_mes}/{ano}'
        planilha['C7'] = self._montarResponsavel(gestor)
        planilha['C8'] = f"{centro['nome']}"
        planilha['H11'] = total_ano
        planilha['H13'] = total_mes
        planilha['H11'].number_format = self.FORMATO_MOEDA
        planilha['H13'].number_format = self.FORMATO_MOEDA

        if numero_mes == 1:
            planilha['H15'] = 0
        else:
            planilha['H15'] = f"='{nome_aba_anterior}'!H{linha_acumulada_anterior}"
        planilha['H15'].number_format = self.FORMATO_MOEDA

        for indice in range(quantidade_linhas):
            linha_atual = self.LINHA_INICIAL_DETALHE + indice
            lancamento = lancamentos[indice] if indice < len(lancamentos) else None
            planilha.cell(row=linha_atual, column=2).value = lancamento['conta_contabil'] if lancamento else None
            planilha.cell(row=linha_atual, column=3).value = lancamento['fornecedor'] if lancamento else None
            planilha.cell(row=linha_atual, column=5).value = lancamento['descricao'] if lancamento else None
            planilha.cell(row=linha_atual, column=6).value = lancamento['data_emissao'] if lancamento else None
            planilha.cell(row=linha_atual, column=7).value = lancamento['data_entrega'] if lancamento else None
            planilha.cell(row=linha_atual, column=8).value = lancamento['valor'] if lancamento else None
            planilha.cell(row=linha_atual, column=6).number_format = self.FORMATO_DATA
            planilha.cell(row=linha_atual, column=7).number_format = self.FORMATO_DATA
            planilha.cell(row=linha_atual, column=8).number_format = self.FORMATO_MOEDA

        planilha.cell(row=linha_total, column=8).value = (
            f'=SUM(H{self.LINHA_INICIAL_DETALHE}:H{linha_total - 1})'
        )
        planilha.cell(row=linha_total, column=8).number_format = self.FORMATO_MOEDA
        planilha.cell(row=linha_saldo_mensal, column=8).value = f'=IF(H13=0,0,H13-H{linha_total})'
        planilha.cell(row=linha_saldo_mensal, column=8).number_format = self.FORMATO_MOEDA
        planilha.cell(row=linha_percentual_mensal, column=8).value = f'=IF(H13=0,0,H{linha_total}/H13)'
        planilha.cell(row=linha_percentual_mensal, column=8).number_format = '0.00%'
        planilha.cell(row=linha_acumulado, column=8).value = f'=H15+H{linha_total}'
        planilha.cell(row=linha_acumulado, column=8).number_format = self.FORMATO_MOEDA
        planilha.cell(row=linha_saldo_acumulado, column=8).value = f'=H11-H{linha_acumulado}'
        planilha.cell(row=linha_saldo_acumulado, column=8).number_format = self.FORMATO_MOEDA
        planilha.cell(row=linha_percentual_ano, column=8).value = f'=IFERROR(H{linha_acumulado}/H11,0)'
        planilha.cell(row=linha_percentual_ano, column=8).number_format = '0.00%'

        return linha_acumulado

    def _capturarModelosLinha(self, planilha):
        return {
            'intro': self._capturarLinha(planilha, 18),
            'detalhe': self._capturarLinha(planilha, 19),
            'total': self._capturarLinha(planilha, 28),
            'blank_1': self._capturarLinha(planilha, 29),
            'saldo_mensal': self._capturarLinha(planilha, 30),
            'percentual_mensal': self._capturarLinha(planilha, 31),
            'blank_2': self._capturarLinha(planilha, 32),
            'blank_3': self._capturarLinha(planilha, 33),
            'acumulado': self._capturarLinha(planilha, 34),
            'saldo_acumulado': self._capturarLinha(planilha, 35),
            'percentual_ano': self._capturarLinha(planilha, 36),
            'blank_4': self._capturarLinha(planilha, 37),
            'blank_5': self._capturarLinha(planilha, 38),
            'aprovador': self._capturarLinha(planilha, 39),
            'data': self._capturarLinha(planilha, 40),
        }

    def _capturarLinha(self, planilha, numero_linha):
        return {
            'altura': planilha.row_dimensions[numero_linha].height,
            'colunas': {
                indice_coluna: {
                    'valor': planilha.cell(row=numero_linha, column=indice_coluna).value,
                    'estilo': copy(planilha.cell(row=numero_linha, column=indice_coluna)._style),
                }
                for indice_coluna in self.COLUNAS_PLANILHA
            },
        }

    def _aplicarModeloLinha(self, planilha, numero_linha, modelo):
        planilha.row_dimensions[numero_linha].height = modelo['altura']
        for indice_coluna, configuracao in modelo['colunas'].items():
            celula = planilha.cell(row=numero_linha, column=indice_coluna)
            celula._style = copy(configuracao['estilo'])
            celula.value = configuracao['valor']

    def _limparRegiaoDinamica(self, planilha, ultima_linha):
        for faixa_mesclada in list(planilha.merged_cells.ranges):
            if faixa_mesclada.max_row >= self.LINHA_INTRO_DETALHE and faixa_mesclada.min_row <= ultima_linha:
                planilha.unmerge_cells(str(faixa_mesclada))

        for numero_linha in range(self.LINHA_INTRO_DETALHE, ultima_linha + 1):
            for indice_coluna in self.COLUNAS_PLANILHA:
                planilha.cell(row=numero_linha, column=indice_coluna).value = None

    def _aplicarMesclagens(
        self,
        planilha,
        quantidade_linhas,
        linha_total,
        linha_saldo_mensal,
        linha_percentual_ano,
        linha_aprovador,
        linha_data,
    ):
        planilha.merge_cells(start_row=18, start_column=2, end_row=18, end_column=8)

        for deslocamento in range(quantidade_linhas):
            linha_atual = self.LINHA_INICIAL_DETALHE + deslocamento
            planilha.merge_cells(start_row=linha_atual, start_column=3, end_row=linha_atual, end_column=4)

        planilha.merge_cells(start_row=linha_total, start_column=6, end_row=linha_total, end_column=7)
        planilha.merge_cells(start_row=linha_saldo_mensal, start_column=6, end_row=linha_saldo_mensal, end_column=7)
        planilha.merge_cells(start_row=linha_saldo_mensal + 1, start_column=6, end_row=linha_saldo_mensal + 1, end_column=7)
        planilha.merge_cells(start_row=linha_saldo_mensal + 4, start_column=6, end_row=linha_saldo_mensal + 4, end_column=7)
        planilha.merge_cells(start_row=linha_saldo_mensal + 5, start_column=6, end_row=linha_saldo_mensal + 5, end_column=7)
        planilha.merge_cells(start_row=linha_percentual_ano, start_column=2, end_row=linha_percentual_ano, end_column=3)
        planilha.merge_cells(start_row=linha_percentual_ano, start_column=6, end_row=linha_percentual_ano, end_column=7)
        planilha.merge_cells(start_row=linha_percentual_ano + 1, start_column=2, end_row=linha_percentual_ano + 1, end_column=3)
        planilha.merge_cells(start_row=linha_aprovador, start_column=2, end_row=linha_aprovador, end_column=3)
        planilha.merge_cells(start_row=linha_data, start_column=2, end_row=linha_data, end_column=3)

    def _montarResponsavel(self, gestor):
        nome = self._normalizarTexto(gestor.get('nome_usuario')) or 'Gestor'
        
        """
        - Comentado para evitar que o cargo do gestor seja exibido na planilha de 
        acompanhamento mensal,

        
        cargo = self._normalizarTexto(gestor.get('cargo'))
        if cargo:
            return f'{nome} - {cargo}'
        return nome
        """
        return nome

    def _normalizarTexto(self, valor):
        if valor is None:
            return None

        texto = str(valor).strip()
        return texto or None

    def _normalizarNumero(self, valor):
        texto = self._normalizarTexto(valor)
        if texto is None:
            return None

        return int(texto) if texto.isdigit() else texto

    def _normalizarNomeArquivo(self, valor):
        texto = self._normalizarTexto(valor) or 'arquivo'
        permitido = [caractere if caractere.isalnum() else '_' for caractere in texto]
        return ''.join(permitido).strip('_') or 'arquivo'