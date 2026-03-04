import json
import math
from collections import defaultdict, namedtuple
from sqlalchemy import text
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Utils.Utils import ReportUtils
from Utils.Logger import RegistrarLog

class RelatorioDreConsolidado:
    def __init__(self, session):
        self.session = session
        self.colunas = [
            'INTEC', 'FARMA', 'FARMA_DIST', 'POLO', 'JANDIRA', 
            'CABREUVA', 'NAO_OPER_INTEC', 'NAO_OPER_FARMA', 'INTERGRUPO', 'Total_Geral'
        ]

    def _ObterEstruturaHierarquia(self):
        from Reports.RelatorioDreGerencial import RelatorioDreGerencial
        dre_base = RelatorioDreGerencial(self.session)
        return dre_base._ObterEstruturaHierarquia()

    def _ObterOrdenamento(self):
        from Reports.RelatorioDreGerencial import RelatorioDreGerencial
        dre_base = RelatorioDreGerencial(self.session)
        return dre_base._ObterOrdenamento()

    def _ObterOrdemSubgruposPorContexto(self):
        from Reports.RelatorioDreGerencial import RelatorioDreGerencial
        dre_base = RelatorioDreGerencial(self.session)
        return dre_base._ObterOrdemSubgruposPorContexto()

    def _DeterminarColuna(self, origem, centro_custo, conta, is_nao_operacional, is_intergrupo):
        origem = str(origem).upper().strip() if origem else ''
        cc = str(centro_custo).upper().strip() if centro_custo else ''
        
        if is_intergrupo:
            return 'INTERGRUPO'
            
        if is_nao_operacional:
            if origem == 'INTEC': return 'NAO_OPER_INTEC'
            if origem in ['FARMA', 'FARMADIST']: return 'NAO_OPER_FARMA'
            return 'NAO_OPER_FARMA'

        if origem == 'INTEC':
            return 'INTEC'
        elif origem == 'FARMADIST':
            return 'FARMA_DIST'
        elif origem == 'FARMA':
            if 'POLO' in cc: return 'POLO'
            if 'JANDIRA' in cc: return 'JANDIRA'
            if 'CABREUVA' in cc: return 'CABREUVA'
            return 'FARMA'
            
        return None

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

            def ProcessRow(origem, conta, titulo, saldo, cc_original_str, is_nao_operacional=False, is_intergrupo=False, is_skeleton=False, forced_match=None):
                if not is_skeleton and is_nao_operacional:
                    conta = '00000000000'
                    titulo = 'Não Operacionais'

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
                    coluna_alvo = self._DeterminarColuna(origem, cc_original_str, conta, is_nao_operacional, is_intergrupo)
                    if coluna_alvo and coluna_alvo in self.colunas:
                        val_inv = saldo * -1 
                        aggregated_data[group_key][coluna_alvo] += val_inv
                        aggregated_data[group_key]['Total_Geral'] += val_inv

            for conta_def, lista_regras in definitions.items():
                titulo_conta = mapa_titulos.get(conta_def, "Conta Configurada")
                for regra in lista_regras:
                    ProcessRow("Config", conta_def, titulo_conta, 0.0, None, False, False, is_skeleton=True, forced_match=regra)

            params = {}
            where_clause = 'WHERE "Invalido" = false'
            if ano:
                params['ano'] = int(ano)
                where_clause += ' AND EXTRACT(YEAR FROM "Data") = :ano'

            sql_raw = text(f"""
                SELECT "origem", "Conta", "Título Conta", "Centro de Custo", "Saldo", "Is_Nao_Operacional", "Tipo_Operacao"
                FROM "Dre_Schema"."Tb_CTL_Razao_Consolidado" {where_clause}
            """)
            raw_rows = self.session.execute(sql_raw, params).fetchall()

            for row in raw_rows:
                is_intergrupo = (row.Tipo_Operacao == 'INTERGRUPO_AUTO')
                ProcessRow(
                    row.origem, row.Conta, getattr(row, 'Título Conta'), row.Saldo, 
                    getattr(row, 'Centro de Custo'), row.Is_Nao_Operacional, is_intergrupo, is_skeleton=False
                )

            final_list = list(aggregated_data.values())
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