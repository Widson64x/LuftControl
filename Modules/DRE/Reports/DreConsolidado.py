import json
import math
from collections import defaultdict
from sqlalchemy import text
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from Utils.Utils import ReportUtils
from Utils.Logger import RegistrarLog

class DreConsolidado:
    def __init__(self, session):
        self.session = session
        self.colunas = [
            'INTEC', 'FARMA', 'FARMA_DIST', 'POLO', 'JANDIRA', 
            'CABREUVA', 'NAO_OPER_INTEC', 'NAO_OPER_FARMA', 'INTERGRUPO', 'Total_Geral'
        ]

    def _ObterEstruturaHierarquia(self):
        from Modules.DRE.Reports.DreGerencial import DreGerencial
        dre_base = DreGerencial(self.session)
        return dre_base._ObterEstruturaHierarquia()

    def _ObterOrdenamento(self):
        from Modules.DRE.Reports.DreGerencial import DreGerencial
        dre_base = DreGerencial(self.session)
        return dre_base._ObterOrdenamento()

    def _ObterOrdemSubgruposPorContexto(self):
        from Modules.DRE.Reports.DreGerencial import DreGerencial
        dre_base = DreGerencial(self.session)
        return dre_base._ObterOrdemSubgruposPorContexto()

    # PASSO 2: Adicionado o parâmetro 'item_cod'
    def _DeterminarColuna(self, origem, centro_custo, conta, is_nao_operacional, is_intergrupo, filial_cliente=None, item_cod=None):
        origem = str(origem).upper().strip() if origem else ''
        cc = str(centro_custo).upper().strip() if centro_custo else ''
        filial = str(filial_cliente).upper().strip() if filial_cliente else ''
        
        # Tratamento da nova variável 'item_cod'
        item = str(item_cod).strip() if item_cod else ''
        
        if is_intergrupo:
            return 'INTERGRUPO'
            
        # PASSO 4: Nova regra! Verifica o Item em vez de 'is_nao_operacional'
        if item == '10190':
            if origem == 'INTEC': return 'NAO_OPER_INTEC'
            if origem in ['FARMA', 'FARMADIST']: return 'NAO_OPER_FARMA'
            return 'NAO_OPER_FARMA'

        if origem == 'INTEC':
            return 'INTEC'
        elif origem == 'FARMADIST':
            return 'FARMA_DIST'
        elif origem == 'FARMA':
            if 'POLO' in cc: return 'POLO'
            # Se tiver o item específico para JANDIRA, ele prevalece sobre o centro de custo
            if 'JANDIRA' in filial: return 'JANDIRA' 
            if 'ITAPEVI 15' in filial: return 'CABREUVA'
            return 'FARMA'
            
        return None

    # Contas manipuladas (B/C) e contas originais cujo INTERGRUPO vem exclusivamente de B/C
    CONTAS_INTERGRUPO_MANIPULADAS = {'60101010201B', '60101010201C', '60301020288C', '60301020290B'}
    CONTAS_INTERGRUPO_ORIGINAIS = {'60101010201', '60101010201A', '60301020288', '60301020290', '60101020201', '60101020202'}

    def processarSaldosIntergrupo(self, aggregatedData, ano=None):
        """Processa saldos de contas intergrupo manipuladas e os reatribui às contas originais.

        Realiza a transformação de sufixo das contas originais para localizar os
        registros intergrupo no banco de dados, e transfere os saldos encontrados
        de volta para as contas de origem.

        Mapeamento:
            - '60101010201B'  -> conta original '60101010201'  (qualquer tipoCC)
            - '60101010201C'  -> conta original '60101010201A' (qualquer tipoCC)
            - '60301020288C'  -> conta original '60301020288'  (tipoCC = 'Oper')
            - '60301020290B'  -> conta original '60301020290'  (tipoCC = 'Oper')

        Impostos derivados do FATURAMENTO BRUTO:
            - '60101020201'  = Total INTERGRUPO do FATURAMENTO BRUTO * 7.6%
            - '60101020202'  = Total INTERGRUPO do FATURAMENTO BRUTO * 1.65%

        Args:
            aggregatedData (dict): Dicionário de dados agregados do relatório,
                onde cada chave é uma tupla de agrupamento e o valor é um dict
                com os saldos por coluna.
            ano (int, optional): Ano de referência para filtrar os registros.

        Returns:
            dict: O mesmo dicionário aggregatedData com os saldos intergrupo
                incorporados nas contas originais.
        """
        RegistrarLog("[INTERGRUPO] Iniciando processarSaldosIntergrupo", "INFO")

        # Mapeamento: contaManipulada -> (contaOriginal, tipoCC_filtro)
        # tipoCC_filtro = None significa que aceita qualquer Tipo_CC
        mapaContasIntergrupo = {
            '60101010201B': ('60101010201',  None),
            '60101010201C': ('60101010201A', None),
            '60301020288C': ('60301020288',  'Oper'),
            '60301020290B': ('60301020290',  'Oper'),
        }

        contasManipuladas = list(mapaContasIntergrupo.keys())
        RegistrarLog(f"[INTERGRUPO] Contas manipuladas a buscar: {contasManipuladas}", "INFO")

        # Consulta SQL para buscar saldos das contas manipuladas com flag intergrupo
        listaPlaceholders = ', '.join([f':conta{i}' for i in range(len(contasManipuladas))])
        sqlIntergrupo = text(f"""
            SELECT tcrc."Conta", tcrc."Saldo"
            FROM "Dre_Schema"."Tb_CTL_Razao_Consolidado" tcrc
            WHERE tcrc."Is_Intergrupo" = TRUE
              AND tcrc."Conta" IN ({listaPlaceholders})
        """)

        paramsIntergrupo = {f'conta{i}': c for i, c in enumerate(contasManipuladas)}

        try:
            registrosIntergrupo = self.session.execute(
                sqlIntergrupo, paramsIntergrupo
            ).fetchall()
            RegistrarLog(f"[INTERGRUPO] Registros retornados do banco: {len(registrosIntergrupo)}", "INFO")
        except Exception as e:
            RegistrarLog("Erro ao buscar saldos intergrupo manipulados", "ERROR", e)
            return aggregatedData

        # Acumula saldos por conta manipulada
        saldosPorContaManipulada = defaultdict(float)
        for registro in registrosIntergrupo:
            contaManipulada = str(registro.Conta).strip()
            saldo = float(registro.Saldo) if registro.Saldo else 0.0
            saldosPorContaManipulada[contaManipulada] += saldo
            RegistrarLog(
                f"[INTERGRUPO] Registro DB -> Conta: {contaManipulada}, Saldo bruto: {saldo}",
                "INFO"
            )

        RegistrarLog(
            f"[INTERGRUPO] Saldos acumulados por conta manipulada: {dict(saldosPorContaManipulada)}",
            "INFO"
        )

        # Transfere os saldos das contas manipuladas para as contas originais
        for contaManipulada, (contaOriginal, tipoCC_filtro) in mapaContasIntergrupo.items():
            saldoTransferido = saldosPorContaManipulada.get(contaManipulada, 0.0)
            RegistrarLog(
                f"[INTERGRUPO] Mapeamento: {contaManipulada} -> {contaOriginal} (tipoCC: {tipoCC_filtro}) | Saldo a transferir: {saldoTransferido}",
                "INFO"
            )
            if saldoTransferido == 0.0:
                RegistrarLog(f"[INTERGRUPO] Saldo zerado para {contaManipulada}, pulando.", "INFO")
                continue

            # Localiza a group_key correspondente à conta original no aggregatedData
            chaveAlvo = None
            for groupKey, itemData in aggregatedData.items():
                contaMatch = itemData.get('Conta') == contaOriginal
                # Quando tipoCC_filtro é definido, exige correspondência exata
                tipoCCMatch = (tipoCC_filtro is None) or (itemData.get('Tipo_CC') == tipoCC_filtro)
                if contaMatch and tipoCCMatch:
                    chaveAlvo = groupKey
                    break

            if chaveAlvo is not None:
                valorAnteriorIntergrupo = aggregatedData[chaveAlvo].get('INTERGRUPO', 0.0)
                valorAnteriorTotal = aggregatedData[chaveAlvo].get('Total_Geral', 0.0)

                # Aplica inversão de sinal conforme padrão do relatório
                valorInvertido = saldoTransferido * -1
                aggregatedData[chaveAlvo]['INTERGRUPO'] += valorInvertido
                aggregatedData[chaveAlvo]['Total_Geral'] += valorInvertido

                RegistrarLog(
                    f"[INTERGRUPO] Conta original '{contaOriginal}' (tipoCC: {tipoCC_filtro}) encontrada. "
                    f"INTERGRUPO antes: {valorAnteriorIntergrupo} -> depois: {aggregatedData[chaveAlvo]['INTERGRUPO']} | "
                    f"Total_Geral antes: {valorAnteriorTotal} -> depois: {aggregatedData[chaveAlvo]['Total_Geral']} | "
                    f"Valor aplicado (invertido): {valorInvertido}",
                    "INFO"
                )
            else:
                RegistrarLog(
                    f"[INTERGRUPO] ATENCAO: Conta original '{contaOriginal}' (tipoCC: {tipoCC_filtro}) NAO encontrada no aggregatedData. "
                    f"Contas disponiveis: {[(v.get('Conta'), v.get('Tipo_CC')) for v in aggregatedData.values()]}",
                    "WARNING"
                )
        # -- ETAPA 2: Calculo de impostos sobre FATURAMENTO BRUTO INTERGRUPO --
        # Soma apenas o INTERGRUPO das contas originais que receberam saldos de B/C
        contasFaturamentoBruto = {'60101010201', '60101010201A'}
        totalFaturamentoBrutoIntergrupo = sum(
            itemData.get('INTERGRUPO', 0.0) for itemData in aggregatedData.values()
            if itemData.get('Conta') in contasFaturamentoBruto
        )
        RegistrarLog(
            f"[INTERGRUPO] Total FATURAMENTO BRUTO (INTERGRUPO): {totalFaturamentoBrutoIntergrupo}",
            "INFO"
        )

        # Mapeamento: conta de imposto -> percentual sobre o FATURAMENTO BRUTO
        mapaImpostosIntergrupo = {
            '60101020201': 0.076,   # 7,6%
            '60101020202': 0.0165,  # 1,65%
        }

        # Inverter o sinal dos impostos
        totalFaturamentoBrutoIntergrupo = totalFaturamentoBrutoIntergrupo * -1  

        for contaImposto, percentual in mapaImpostosIntergrupo.items():
            valorImposto = totalFaturamentoBrutoIntergrupo * percentual
            RegistrarLog(
                f"[INTERGRUPO] Imposto '{contaImposto}': FATURAMENTO_BRUTO({totalFaturamentoBrutoIntergrupo}) * {percentual*100}% = {valorImposto}",
                "INFO"
            )

            if valorImposto == 0.0:
                RegistrarLog(f"[INTERGRUPO] Valor do imposto zerado para {contaImposto}, pulando.", "INFO")
                continue

            # Localiza a conta de imposto no aggregatedData
            chaveImposto = None
            for groupKey, itemData in aggregatedData.items():
                if itemData.get('Conta') == contaImposto:
                    chaveImposto = groupKey
                    break

            if chaveImposto is not None:
                anteriorIntergrupo = aggregatedData[chaveImposto].get('INTERGRUPO', 0.0)
                anteriorTotal = aggregatedData[chaveImposto].get('Total_Geral', 0.0)

                aggregatedData[chaveImposto]['INTERGRUPO'] += valorImposto
                aggregatedData[chaveImposto]['Total_Geral'] += valorImposto

                RegistrarLog(
                    f"[INTERGRUPO] Imposto '{contaImposto}' aplicado. "
                    f"INTERGRUPO antes: {anteriorIntergrupo} -> depois: {aggregatedData[chaveImposto]['INTERGRUPO']} | "
                    f"Total_Geral antes: {anteriorTotal} -> depois: {aggregatedData[chaveImposto]['Total_Geral']}",
                    "INFO"
                )
            else:
                RegistrarLog(
                    f"[INTERGRUPO] ATENCAO: Conta de imposto '{contaImposto}' NAO encontrada no aggregatedData.",
                    "WARNING"
                )

        RegistrarLog("[INTERGRUPO] processarSaldosIntergrupo finalizado.", "INFO")
        return aggregatedData

    def _removerContasManipuladas(self, listaResultados):
        """Remove da lista final as linhas referentes às contas manipuladas.

        As contas auxiliares (B e C) são utilizadas apenas para transferência
        de saldos intergrupo. Após o processamento, elas devem ser excluídas
        da visualização da hierarquia.

        Args:
            listaResultados (list): Lista de dicts representando as linhas do relatório.

        Returns:
            list: Lista filtrada sem as contas manipuladas.
        """
        return [
            item for item in listaResultados
            if item.get('Conta') not in self.CONTAS_INTERGRUPO_MANIPULADAS
        ]

    def ProcessarRelatorio(self, ano=None):
        try:
            tree_map, definitions = self._ObterEstruturaHierarquia()
            ordem_map = self._ObterOrdenamento()
            ordem_subgrupos_contexto = self._ObterOrdemSubgruposPorContexto()
            
            sql_css = text('SELECT "Id", "Estilo_CSS" FROM "Dre_Schema"."Tb_CTL_Dre_No_Virtual"')
            css_map = {row.Id: row.Estilo_CSS for row in self.session.execute(sql_css).fetchall() if row.Estilo_CSS}
            
            sql_nomes = text('SELECT DISTINCT "Conta", "Título Conta" FROM "Dre_Schema"."Tb_CTL_Razao_Consolidado"')
            mapa_titulos = {row[0]: row[1] for row in self.session.execute(sql_nomes).fetchall()}

            aggregated_data = {}

            # PASSO 2: Adicionado 'item_cod' aos parâmetros
            def ProcessRow(origem, conta, titulo, saldo, cc_original_str, is_nao_operacional=False, is_intergrupo=False, is_skeleton=False, forced_match=None, filial_cliente=None, item_cod=None):
                
                # PASSO 3: O bloco de código que transformava a conta em '00000000000' foi removido
                # para que possas visualizar exatamente as contas originais.

                match = forced_match
                if not match:
                    rules = definitions.get(conta, [])
                    if not rules: return
                    cc_int = None
                    if cc_original_str:
                        try: cc_int = int(''.join(filter(str.isdigit, str(cc_original_str))))
                        except: pass
                        if cc_int is not None:
                            for rule in rules:
                                if rule.CC_Alvo is not None and cc_int == rule.CC_Alvo:
                                    match = rule; break
                    if not match: match = rules[0]
                
                if not match: return

                tipo_cc = match.Tipo_Principal or 'Outros'
                root_virtual_id = match.Raiz_No_Virtual_Id
                caminho = match.full_path or 'Não Classificado'
                
                ordem = 999
                ordem_secundaria = 500
                
                if root_virtual_id: ordem = ordem_map.get(f"virtual:{root_virtual_id}", 999)
                elif match.Is_Root_Group:
                    if match.Id_Hierarquia: ordem = ordem_map.get(f"subgrupo:{match.Id_Hierarquia}", 0)
                else: ordem = ordem_map.get(f"tipo_cc:{tipo_cc}", 999)
                
                if caminho and caminho not in ['Não Classificado', 'Direto', 'Calculado']:
                    partes = caminho.split('||')
                    if partes:
                        chave_busca = (partes[0].strip(), str(tipo_cc).strip())
                        ordem_secundaria = ordem_subgrupos_contexto.get(chave_busca, 999)

                conta_display = conta 
                titulo_para_exibicao = match.Nome_Personalizado_Def if match.Nome_Personalizado_Def else titulo
                
                group_key = (tipo_cc, root_virtual_id, caminho, match.full_ordem_path, titulo_para_exibicao, conta_display)

                if group_key not in aggregated_data:
                    css_style = css_map.get(root_virtual_id, None)
                    item = {
                        'Conta': conta_display, 'Titulo_Conta': titulo_para_exibicao,
                        'Tipo_CC': tipo_cc, 'Root_Virtual_Id': root_virtual_id, 
                        'Caminho_Subgrupos': caminho, 'Caminho_Ordem': match.full_ordem_path,
                        'Ordem_Conta': match.Ordem_Conta, 'ordem_prioridade': ordem, 
                        'ordem_secundaria': ordem_secundaria, 'Estilo_CSS': css_style 
                    }
                    for col in self.colunas: item[col] = 0.0
                    aggregated_data[group_key] = item
                else:
                    if match.Ordem_Conta < aggregated_data[group_key]['Ordem_Conta']:
                        aggregated_data[group_key]['Ordem_Conta'] = match.Ordem_Conta

                if not is_skeleton and saldo != 0:
                    # Passamos também o item_cod para _DeterminarColuna
                    coluna_alvo = self._DeterminarColuna(origem, cc_original_str, conta, is_nao_operacional, is_intergrupo, filial_cliente, item_cod)

                    # Contas originais cujo INTERGRUPO vem de B/C: ignora atribuicao a coluna INTERGRUPO aqui
                    if coluna_alvo == 'INTERGRUPO' and conta in self.CONTAS_INTERGRUPO_ORIGINAIS:
                        return

                    if coluna_alvo and coluna_alvo in self.colunas:
                        val_inv = saldo * -1 
                        aggregated_data[group_key][coluna_alvo] += val_inv
                        aggregated_data[group_key]['Total_Geral'] += val_inv

            for conta_def, lista_regras in definitions.items():
                titulo_conta = mapa_titulos.get(conta_def, "Conta Configurada")
                for regra in lista_regras:
                    ProcessRow("Config", conta_def, titulo_conta, 0.0, None, False, False, is_skeleton=True, forced_match=regra, filial_cliente=None, item_cod=None)

            params = {}
            where_clause = 'WHERE "Invalido" = false'
            if ano:
                params['ano'] = int(ano)
                where_clause += ' AND EXTRACT(YEAR FROM "Data") = :ano'

            # PASSO 1: Adicionada a coluna "Item" à consulta SQL
            sql_raw = text(f"""
                SELECT "origem", "Conta", "Título Conta", "Centro de Custo", "Saldo", "Is_Nao_Operacional", "Tipo_Operacao", "Filial Cliente", "Item"
                FROM "Dre_Schema"."Tb_CTL_Razao_Consolidado" {where_clause}
            """)
            raw_rows = self.session.execute(sql_raw, params).fetchall()

            for row in raw_rows:
                # Ignora contas manipuladas (B/C) no loop principal; tratadas em processarSaldosIntergrupo
                contaAtual = str(row.Conta).strip() if row.Conta else ''
                if contaAtual in self.CONTAS_INTERGRUPO_MANIPULADAS:
                    continue

                is_intergrupo = (row.Tipo_Operacao == 'INTERGRUPO_AUTO')
                # Enviando getattr(row, 'Item', None)
                ProcessRow(
                    row.origem, row.Conta, getattr(row, 'Título Conta'), row.Saldo, 
                    getattr(row, 'Centro de Custo'), row.Is_Nao_Operacional, is_intergrupo, 
                    is_skeleton=False, filial_cliente=getattr(row, 'Filial Cliente', None),
                    item_cod=getattr(row, 'Item', None)
                )

            # Processa saldos intergrupo antes de montar a lista final
            aggregated_data = self.processarSaldosIntergrupo(aggregated_data, ano)

            final_list = list(aggregated_data.values())

            # Remove contas manipuladas (B e C) da visualização
            final_list = self._removerContasManipuladas(final_list)

            final_list.sort(key=lambda x: (x.get('ordem_prioridade', 999), x.get('ordem_secundaria', 500), x.get('Caminho_Subgrupos') or '', x.get('Conta', '')))
            
            return final_list
        
        except Exception as e:
            RegistrarLog("Erro no Relatório DRE Consolidado", "ERROR", e)
            raise e
        
    def CalcularNosVirtuais(self, data_rows):
        memoria = defaultdict(lambda: {c: 0.0 for c in self.colunas})

        for row in data_rows:
            tipo = str(row.get('Tipo_CC', '')).strip()
            virt_id = row.get('Root_Virtual_Id')
            caminho = str(row.get('Caminho_Subgrupos', '')).strip()
            
            keys_to_update = [f"tipo_cc:{tipo}"]
            if caminho and caminho != 'None':
                for p in caminho.split('||'):
                    p_limpa = p.strip()
                    if p_limpa: keys_to_update.append(f"subgrupo:{p_limpa}")

            titulo = str(row.get('Titulo_Conta', '')).strip()
            if titulo: keys_to_update.append(f"subgrupo:{titulo}")

            if virt_id:
                keys_to_update.append(f"no_virtual:{virt_id}")
                keys_to_update.append(f"no_virtual:{tipo}")

            for col in self.colunas:
                val = row.get(col, 0.0)
                if val != 0:
                    for k in keys_to_update:
                        memoria[k][col] += val
        
        sql_formulas = text("""
            SELECT nv."Id", nv."Nome", nv."Formula_JSON", nv."Estilo_CSS", nv."Tipo_Exibicao", COALESCE(ord.ordem, 999) as ordem
            FROM "Dre_Schema"."Tb_CTL_Dre_No_Virtual" nv
            LEFT JOIN "Dre_Schema"."Tb_CTL_Dre_Ordenamento" ord ON ord.id_referencia = CAST(nv."Id" AS TEXT) AND ord.contexto_pai = 'root'
            WHERE nv."Is_Calculado" = true ORDER BY ordem ASC
        """)
        formulas = self.session.execute(sql_formulas).fetchall()
        
        novas_linhas = []
        for form in formulas:
            if not form.Formula_JSON: continue
            try:
                f_data = json.loads(form.Formula_JSON)
                operandos = f_data.get('operandos', [])
                operacao = f_data.get('operacao', 'soma')
                multiplicador = float(f_data.get('multiplicador', 1))

                nova_linha = {
                    'Conta': f"CALC_{form.Id}", 'Titulo_Conta': form.Nome,
                    'Tipo_CC': form.Nome, 'Caminho_Subgrupos': 'Calculado', 'ordem_prioridade': form.ordem,
                    'ordem_secundaria': 0, 'Is_Calculado': True, 'Estilo_CSS': form.Estilo_CSS, 
                    'Tipo_Exibicao': form.Tipo_Exibicao, 'Root_Virtual_Id': form.Id 
                }

                for col in self.colunas:
                    vals = []
                    for op in operandos:
                        tipo_op = op.get('tipo')
                        id_op = str(op.get('id')).strip()
                        chave = f"{tipo_op}:{id_op}"
                        
                        val = memoria.get(chave, {}).get(col, 0.0)
                        if val == 0.0:
                             for k_mem, v_mem in memoria.items():
                                 if k_mem.lower() == chave.lower():
                                     val = v_mem.get(col, 0.0); break
                        vals.append(val)
                    
                    res = 0.0
                    if vals:
                        if operacao == 'soma': res = sum(vals)
                        elif operacao == 'subtracao': res = vals[0] - sum(vals[1:])
                        elif operacao == 'multiplicacao': res = math.prod(vals)
                        elif operacao == 'divisao': res = vals[0] / vals[1] if (len(vals) > 1 and vals[1] != 0) else 0.0
                    
                    final_val = res * multiplicador
                    nova_linha[col] = final_val
                    memoria[f"no_virtual:{form.Id}"][col] = final_val
                    memoria[f"no_virtual:{form.Nome}"][col] = final_val

                novas_linhas.append(nova_linha)
            except Exception as e:
                RegistrarLog(f"Erro ao calcular fórmula '{form.Nome}'", "ERROR", e)

        todos = data_rows + novas_linhas
        todos.sort(key=lambda x: (x.get('ordem_prioridade', 999), x.get('ordem_secundaria', 0)))
        return todos

    def AplicarMilhares(self, data):
        return ReportUtils.aplicar_escala_milhares(data, self.colunas)