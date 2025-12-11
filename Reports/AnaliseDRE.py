# Reports/AnaliseDRE.py
import json
import math
from collections import defaultdict, namedtuple
from sqlalchemy import text
from Utils.hash_utils import gerar_hash
from Reports.Shared.Utils import ReportUtils

class AnaliseDREReport:
    def __init__(self, session):
        self.session = session
        self.meses = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez','Total_Ano']

    def _get_estrutura_hierarquia(self):
        # 1. Recursive CTE para montar os caminhos (TreePath)
        sql_tree = text("""
            WITH RECURSIVE TreePath AS (
                SELECT 
                    h."Id", h."Nome", h."Id_Pai", 
                    h."Raiz_Centro_Custo_Codigo", h."Raiz_No_Virtual_Id", 
                    h."Raiz_Centro_Custo_Tipo", h."Raiz_No_Virtual_Nome", h."Raiz_Centro_Custo_Nome",
                    CAST(h."Nome" AS TEXT) as full_path
                FROM "Dre_Schema"."DRE_Estrutura_Hierarquia" h
                WHERE h."Id_Pai" IS NULL
                UNION ALL
                SELECT 
                    child."Id", child."Nome", child."Id_Pai", 
                    COALESCE(child."Raiz_Centro_Custo_Codigo", tp."Raiz_Centro_Custo_Codigo"),
                    COALESCE(child."Raiz_No_Virtual_Id", tp."Raiz_No_Virtual_Id"),
                    COALESCE(child."Raiz_Centro_Custo_Tipo", tp."Raiz_Centro_Custo_Tipo"),
                    COALESCE(child."Raiz_No_Virtual_Nome", tp."Raiz_No_Virtual_Nome"),
                    COALESCE(child."Raiz_Centro_Custo_Nome", tp."Raiz_Centro_Custo_Nome"),
                    CAST(tp.full_path || '||' || child."Nome" AS TEXT)
                FROM "Dre_Schema"."DRE_Estrutura_Hierarquia" child
                JOIN TreePath tp ON child."Id_Pai" = tp."Id"
            )
            SELECT * FROM TreePath
        """)
        tree_rows = self.session.execute(sql_tree).fetchall()
        tree_map = {row.Id: row for row in tree_rows}

        # 2. Busca Vínculos e Personalizações
        sql_defs = text("""
            SELECT v."Conta_Contabil", v."Id_Hierarquia", NULL::int as "Id_No_Virtual", NULL::text as "Nome_Personalizado", 'Vinculo' as "Origem_Regra", NULL::text as "Nome_Virtual_Direto", NULL::int as "Id_Virtual_Direto"
            FROM "Dre_Schema"."DRE_Estrutura_Conta_Vinculo" v
            UNION ALL
            SELECT p."Conta_Contabil", p."Id_Hierarquia", NULL::int, p."Nome_Personalizado", 'Personalizado_Hierarquia', NULL::text, NULL::int
            FROM "Dre_Schema"."DRE_Estrutura_Conta_Personalizada" p WHERE p."Id_Hierarquia" IS NOT NULL
            UNION ALL
            SELECT p."Conta_Contabil", NULL::int, p."Id_No_Virtual", p."Nome_Personalizado", 'Personalizado_Virtual', nv."Nome", nv."Id"
            FROM "Dre_Schema"."DRE_Estrutura_Conta_Personalizada" p JOIN "Dre_Schema"."DRE_Estrutura_No_Virtual" nv ON p."Id_No_Virtual" = nv."Id" WHERE p."Id_No_Virtual" IS NOT NULL
        """)
        def_rows = self.session.execute(sql_defs).fetchall()
        
        Definition = namedtuple('Definition', ['Conta_Contabil', 'CC_Alvo', 'Id_Hierarquia', 'Id_No_Virtual', 'Nome_Personalizado_Def', 'full_path', 'Tipo_Principal', 'Raiz_Centro_Custo_Nome', 'Raiz_No_Virtual_Id', 'Is_Root_Group'])
        definitions = defaultdict(list)
        
        for row in def_rows:
            cc_alvo = None; full_path = None; tipo_principal = None; nome_cc_detalhe = None; raiz_virt_id = None; is_root_group = False
            
            if row.Id_Hierarquia and row.Id_Hierarquia in tree_map:
                node = tree_map[row.Id_Hierarquia]
                cc_alvo = node.Raiz_Centro_Custo_Codigo
                full_path = node.full_path
                nome_cc_detalhe = node.Raiz_Centro_Custo_Nome
                raiz_virt_id = node.Raiz_No_Virtual_Id
                
                if node.Raiz_Centro_Custo_Tipo: 
                    tipo_principal = node.Raiz_Centro_Custo_Tipo
                elif node.Raiz_No_Virtual_Nome: 
                    tipo_principal = node.Raiz_No_Virtual_Nome
                else:
                    root_name = full_path.split('||')[0]
                    tipo_principal = root_name
                    is_root_group = True
            elif row.Id_No_Virtual:
                full_path = 'Direto'
                tipo_principal = row.Nome_Virtual_Direto
                raiz_virt_id = row.Id_Virtual_Direto
            
            obj_def = Definition(Conta_Contabil=row.Conta_Contabil, CC_Alvo=cc_alvo, Id_Hierarquia=row.Id_Hierarquia, Id_No_Virtual=row.Id_No_Virtual, Nome_Personalizado_Def=row.Nome_Personalizado, full_path=full_path, Tipo_Principal=tipo_principal, Raiz_Centro_Custo_Nome=nome_cc_detalhe, Raiz_No_Virtual_Id=raiz_virt_id, Is_Root_Group=is_root_group)
            definitions[row.Conta_Contabil].append(obj_def)
            
        return tree_map, definitions

    def _get_ajustes_map(self):
        """Retorna dicionários de Ajustes (Edições e Inclusões)."""
        sql = text("""
            SELECT * FROM "Dre_Schema"."Ajustes_Razao" 
            WHERE "Status" != 'Reprovado' AND "Invalido" = false
        """)
        rows = self.session.execute(sql).fetchall()
        
        edicoes = {}
        inclusoes = []
        for row in rows:
            # Tipos que SUBSTITUEM linha existente (Merge)
            if row.Tipo_Operacao in ['EDICAO', 'NO-OPER_AUTO']:
                if row.Hash_Linha_Original:
                    edicoes[row.Hash_Linha_Original] = row
            # Tipos que CRIAM NOVA linha (Append)
            elif row.Tipo_Operacao in ['INCLUSAO', 'INTERGRUPO_AUTO']:
                inclusoes.append(row)
        return edicoes, inclusoes

    def _get_ordenamento(self):
        sql = text("SELECT id_referencia, tipo_no, ordem FROM \"Dre_Schema\".\"DRE_Ordenamento\" WHERE contexto_pai = 'root'")
        rows = self.session.execute(sql).fetchall()
        return {f"{r.tipo_no}:{r.id_referencia}": r.ordem for r in rows}

    def processar_relatorio(self, filtro_origem='Consolidado', agrupar_por_cc=False, filtro_cc=None):
        """
        Gera os dados base do relatório.
        Agora suporta filtragem por Centro de Custo Específico.
        """
        tree_map, definitions = self._get_estrutura_hierarquia()
        ajustes_edicao, ajustes_inclusao = self._get_ajustes_map()
        ordem_map = self._get_ordenamento()
        
        sql_nomes = text('SELECT DISTINCT "Conta", "Título Conta" FROM "Dre_Schema"."Razao_Dados_Consolidado"')
        res_nomes = self.session.execute(sql_nomes).fetchall()
        mapa_titulos = {row[0]: row[1] for row in res_nomes}

        aggregated_data = {} 

        def process_row(origem, conta, titulo, data, saldo, cc_original_str, row_hash=None, is_skeleton=False, forced_match=None):
            # A. EDIÇÕES (Prioridade sobre dados originais)
            if not is_skeleton and row_hash and row_hash in ajustes_edicao:
                adj = ajustes_edicao[row_hash]
                if adj.Invalido: return 
                
                # Override com valores do ajuste
                origem = adj.Origem or origem
                conta = adj.Conta or conta
                titulo = adj.Titulo_Conta or titulo
                cc_original_str = str(adj.Centro_Custo) if adj.Centro_Custo else cc_original_str
                data = adj.Data or data
                
                if adj.Is_Nao_Operacional:
                    conta = '00000000000'
                    titulo = 'Não Operacionais'
                
                if adj.Exibir_Saldo:
                    saldo = (float(adj.Debito or 0) - float(adj.Credito or 0))
                else:
                    saldo = 0.0

            # B. MATCH (Encontrar regra de hierarquia)
            match = forced_match
            if not match:
                rules = definitions.get(conta, [])
                if not rules: return
                
                # Tenta match específico por CC alvo na regra
                if cc_original_str:
                    cc_int = None
                    try: cc_int = int(''.join(filter(str.isdigit, str(cc_original_str))))
                    except: pass
                    if cc_int is not None:
                        for rule in rules:
                            if rule.CC_Alvo is not None and cc_int == rule.CC_Alvo:
                                match = rule; break
                # Se não achou específico, pega o genérico (CC_Alvo null)
                if not match: 
                    match = rules[0]
            
            if not match: return

            # C. AGRUPAMENTO E SOMA
            tipo_cc = match.Tipo_Principal or 'Outros'
            root_virtual_id = match.Raiz_No_Virtual_Id
            caminho = match.full_path or 'Não Classificado'
            
            # Definição de Ordem
            ordem = 999
            if root_virtual_id:
                ordem = ordem_map.get(f"virtual:{root_virtual_id}", 999)
            elif match.Is_Root_Group:
                if match.Id_Hierarquia:
                    ordem = ordem_map.get(f"subgrupo:{match.Id_Hierarquia}") or 0
            else:
                ordem = ordem_map.get(f"tipo_cc:{tipo_cc}", 999)

            conta_display = match.Nome_Personalizado_Def if match.Nome_Personalizado_Def else conta
            titulo_para_exibicao = match.Nome_Personalizado_Def if match.Nome_Personalizado_Def else titulo
            
            group_key = (tipo_cc, root_virtual_id, caminho, titulo_para_exibicao, conta_display)
            if agrupar_por_cc: 
                group_key = group_key + (match.Raiz_Centro_Custo_Nome,)

            if group_key not in aggregated_data:
                item = {
                    'origem': origem, 'Conta': conta_display, 'Titulo_Conta': titulo_para_exibicao,
                    'Tipo_CC': tipo_cc, 'Root_Virtual_Id': root_virtual_id, 'Caminho_Subgrupos': caminho, 
                    'ordem_prioridade': ordem, 'Total_Ano': 0.0
                }
                for m in self.meses[:-1]: item[m] = 0.0
                if agrupar_por_cc: item['Nome_CC'] = match.Raiz_Centro_Custo_Nome
                aggregated_data[group_key] = item

            if not is_skeleton and data:
                try:
                    mes_nome = self.meses[data.month - 1]
                    val_inv = saldo * -1 # Inverte sinal (Crédito é receita positiva no DRE)
                    aggregated_data[group_key][mes_nome] += val_inv
                    aggregated_data[group_key]['Total_Ano'] += val_inv
                except: pass

        # 1. Esqueleto (Garante que a estrutura apareça vazia se necessário)
        for conta_def, lista_regras in definitions.items():
            titulo_conta = mapa_titulos.get(conta_def, "Conta Configurada")
            for regra in lista_regras:
                process_row("Config", conta_def, titulo_conta, None, 0.0, None, None, is_skeleton=True, forced_match=regra)

        # 2. Construção da Query SQL Dinâmica
        where_clauses = []
        params = {}
        
        # Filtro Origem
        if filtro_origem == 'FARMA':
            where_clauses.append("\"origem\" = 'FARMA'")
        elif filtro_origem == 'FARMADIST':
            where_clauses.append("\"origem\" = 'FARMADIST'")
        else:
            where_clauses.append("\"origem\" IN ('FARMA', 'FARMADIST')")
            
        # Filtro Centro de Custo (NOVO)
        if filtro_cc and filtro_cc != 'Todos':
            where_clauses.append("\"Centro de Custo\" = :cc")
            params['cc'] = filtro_cc

        where_final = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        sql_raw = text(f"""
            SELECT "origem", "Conta", "Título Conta", "Data", "Numero", "Centro de Custo", "Saldo", "Filial", "Item", "Debito", "Credito"
            FROM "Dre_Schema"."Razao_Dados_Consolidado" {where_final}
        """)
        
        raw_rows = self.session.execute(sql_raw, params).fetchall()
        for row in raw_rows:
            h = gerar_hash(row)
            process_row(
                row.origem, row.Conta, getattr(row, 'Título Conta'), row.Data, row.Saldo, 
                getattr(row, 'Centro de Custo'), h, is_skeleton=False
            )

        # 3. Inclusões Manuais (Aplica filtro de CC nelas também)
        for adj in ajustes_inclusao:
            # Filtro Origem
            if filtro_origem != 'Consolidado' and adj.Origem != filtro_origem: continue
            
            # Filtro CC nas inclusões
            if filtro_cc and filtro_cc != 'Todos':
                # Compara convertendo para string para evitar erro de tipo
                if str(adj.Centro_Custo or '').strip() != str(filtro_cc).strip():
                    continue

            if not adj.Invalido:
                saldo_adj = (float(adj.Debito or 0) - float(adj.Credito or 0)) if adj.Exibir_Saldo else 0.0
                c = '00000000000' if adj.Is_Nao_Operacional else adj.Conta
                t = 'Não Operacionais' if adj.Is_Nao_Operacional else adj.Titulo_Conta
                
                process_row(
                    adj.Origem, c, t, adj.Data, saldo_adj, str(adj.Centro_Custo), 
                    None, is_skeleton=False
                )

        final_list = list(aggregated_data.values())
        if agrupar_por_cc: 
            final_list.sort(key=lambda x: (x['ordem_prioridade'], x['Tipo_CC'], x['Nome_CC'] or ''))
        else: 
            final_list.sort(key=lambda x: x['ordem_prioridade'])
        
        return final_list

    def calcular_nos_virtuais(self, data_rows):
        """Versão com Logs de Debug para Subgrupos"""
        print("\n\n=== INÍCIO DO CÁLCULO DE FÓRMULAS ===")
        memoria = defaultdict(lambda: {m: 0.0 for m in self.meses})
        
        debug_descontos_found = False

        # 1. Popula memória
        for row in data_rows:
            tipo = str(row.get('Tipo_CC', '')).strip()
            virt_id = row.get('Root_Virtual_Id')
            caminho = str(row.get('Caminho_Subgrupos', '')).strip()
            
            keys_to_update = [f"tipo_cc:{tipo}"]
            
            # Indexa partes do caminho (SUBGRUPOS)
            if caminho and caminho != 'None':
                partes = caminho.split('||')
                for p in partes:
                    p_limpa = p.strip()
                    if p_limpa:
                        keys_to_update.append(f"subgrupo:{p_limpa}")
                        # DEBUG: Se encontrar DESCONTOS, avisa
                        if "DESCONTOS" in p_limpa.upper():
                            debug_descontos_found = True
                            # print(f"[DEBUG] Dado encontrado para subgrupo:DESCONTOS -> Valor Jan: {row.get('Jan')}")

            # Indexa pelo Título da Conta também
            titulo = str(row.get('Titulo_Conta', '')).strip()
            if titulo: keys_to_update.append(f"subgrupo:{titulo}")

            if virt_id:
                keys_to_update.append(f"no_virtual:{virt_id}")
                keys_to_update.append(f"no_virtual:{tipo}")

            for m in self.meses:
                val = row.get(m, 0.0)
                if val != 0:
                    for k in keys_to_update:
                        memoria[k][m] += val
        
        if not debug_descontos_found:
            print("[ALERTA] Nenhuma linha foi associada ao subgrupo 'DESCONTOS' durante a carga!")
            print("Verifique se o nome no banco é exatamente 'DESCONTOS' ou se está dentro de outra hierarquia.")
        else:
            print("[SUCESSO] Dados para 'DESCONTOS' foram carregados na memória.")

        # 2. Busca e Calcula Fórmulas
        sql_formulas = text("""
            SELECT nv."Id", nv."Nome", nv."Formula_JSON", nv."Estilo_CSS", nv."Tipo_Exibicao", COALESCE(ord.ordem, 999) as ordem
            FROM "Dre_Schema"."DRE_Estrutura_No_Virtual" nv
            LEFT JOIN "Dre_Schema"."DRE_Ordenamento" ord ON ord.id_referencia = CAST(nv."Id" AS TEXT) AND ord.contexto_pai = 'root'
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

                # DEBUG ESPECÍFICO
                isDebugTarget = "FATURAMENTO" in form.Nome.upper() or "LÍQUIDO" in form.Nome.upper()
                if isDebugTarget:
                    print(f"--- Calculando: {form.Nome} ---")

                nova_linha = {
                    'origem': 'Calculado', 'Conta': f"CALC_{form.Id}", 'Titulo_Conta': form.Nome,
                    'Tipo_CC': form.Nome, 'Caminho_Subgrupos': 'Calculado', 'ordem_prioridade': form.ordem,
                    'Is_Calculado': True, 'Estilo_CSS': form.Estilo_CSS, 'Tipo_Exibicao': form.Tipo_Exibicao,
                    'Root_Virtual_Id': form.Id 
                }

                for mes in self.meses:
                    vals = []
                    for op in operandos:
                        tipo_op = op.get('tipo')
                        id_op = str(op.get('id')).strip()
                        chave = f"{tipo_op}:{id_op}"
                        
                        val = memoria.get(chave, {}).get(mes, 0.0)
                        
                        # Fallback case-insensitive
                        if val == 0.0:
                             for k_mem, v_mem in memoria.items():
                                 if k_mem.lower() == chave.lower():
                                     val = v_mem.get(mes, 0.0); break
                        
                        if isDebugTarget and mes == 'Jan':
                            print(f"   Operando: {op.get('label')} | Chave: {chave} | Valor Jan: {val}")

                        vals.append(val)
                    
                    res = 0.0
                    if vals:
                        if operacao == 'soma': res = sum(vals)
                        elif operacao == 'subtracao': res = vals[0] - sum(vals[1:])
                        elif operacao == 'multiplicacao': res = math.prod(vals)
                        elif operacao == 'divisao': res = vals[0] / vals[1] if (len(vals) > 1 and vals[1] != 0) else 0.0
                    
                    final_val = res * multiplicador
                    nova_linha[mes] = final_val
                    memoria[f"no_virtual:{form.Id}"][mes] = final_val
                    memoria[f"no_virtual:{form.Nome}"][mes] = final_val

                novas_linhas.append(nova_linha)
            except Exception as e:
                print(f"Erro {form.Nome}: {e}")

        todos = data_rows + novas_linhas
        todos.sort(key=lambda x: x.get('ordem_prioridade', 999))
        return todos

    def aplicar_milhares(self, data):
        return ReportUtils.aplicar_escala_milhares(data, self.meses)