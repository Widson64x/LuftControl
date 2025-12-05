# Services/DreService.py
import hashlib
import json
from datetime import datetime
from sqlalchemy import text
from collections import defaultdict, namedtuple
import math

class DreService:
    def __init__(self, session):
        self.session = session
        self.meses = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez','Total_Ano']

    def aplicar_escala_milhares(self, data_rows):
        """
        Divide todos os valores monetários por 1000 para visão DRE.
        Realizado no Backend para garantir precisão.
        """
        for row in data_rows:
            # Colunas de meses + Total_Ano
            cols_to_scale = self.meses 
            
            for col in cols_to_scale:
                val = row.get(col)
                if val is not None and isinstance(val, (int, float)):
                    # Divide por 1000 e arredonda para evitar dízimas irrelevantes na visualização
                    row[col] = val / 1000.0
        
        return data_rows
    
    def _gerar_hash_linha(self, row):
        """Rebater o MD5 exato que o SQL gerava para encontrar ajustes."""
        parts = [
            str(row.origem).strip() if row.origem else 'None',
            str(row.Filial).strip() if getattr(row, 'Filial', None) else 'None',
            str(row.Numero).strip() if getattr(row, 'Numero', None) else 'None',
            str(row.Item).strip() if getattr(row, 'Item', None) else 'None',
            str(row.Conta).strip() if getattr(row, 'Conta', None) else 'None',
            row.Data.strftime('%Y-%m-%d') if getattr(row, 'Data', None) else 'None'
        ]
        raw_string = "-".join(parts)
        return hashlib.md5(raw_string.encode('utf-8')).hexdigest()

    def get_estrutura_hierarquia(self):
        """
        Busca a árvore e define como cada conta deve ser classificada.
        (Atualizado para detectar Grupos Raiz Globais corretamente)
        """
        
        # 1. Buscar Hierarquia (TreePath)
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

        # 2. Buscar Definições (Vínculos e Personalizadas)
        sql_defs = text("""
            SELECT 
                v."Conta_Contabil", 
                v."Id_Hierarquia", 
                NULL::int as "Id_No_Virtual",
                NULL::text as "Nome_Personalizado",
                'Vinculo' as "Origem_Regra",
                NULL::text as "Nome_Virtual_Direto",
                NULL::int as "Id_Virtual_Direto"
            FROM "Dre_Schema"."DRE_Estrutura_Conta_Vinculo" v
            
            UNION ALL
            
            SELECT 
                p."Conta_Contabil", 
                p."Id_Hierarquia", 
                NULL::int, 
                p."Nome_Personalizado",
                'Personalizado_Hierarquia',
                NULL::text,
                NULL::int
            FROM "Dre_Schema"."DRE_Estrutura_Conta_Personalizada" p
            WHERE p."Id_Hierarquia" IS NOT NULL
            
            UNION ALL
            
            SELECT 
                p."Conta_Contabil", 
                NULL::int, 
                p."Id_No_Virtual",
                p."Nome_Personalizado",
                'Personalizado_Virtual',
                nv."Nome",
                nv."Id"
            FROM "Dre_Schema"."DRE_Estrutura_Conta_Personalizada" p
            JOIN "Dre_Schema"."DRE_Estrutura_No_Virtual" nv ON p."Id_No_Virtual" = nv."Id"
            WHERE p."Id_No_Virtual" IS NOT NULL
        """)
        def_rows = self.session.execute(sql_defs).fetchall()
        
        Definition = namedtuple('Definition', [
            'Conta_Contabil', 'CC_Alvo', 'Id_Hierarquia', 'Id_No_Virtual', 
            'Nome_Personalizado_Def', 'full_path', 'Tipo_Principal', 
            'Raiz_Centro_Custo_Nome', 'Raiz_No_Virtual_Id', 'Is_Root_Group'
        ])

        definitions = defaultdict(list)
        
        for row in def_rows:
            cc_alvo = None
            full_path = None
            tipo_principal = None
            nome_cc_detalhe = None
            raiz_virt_id = None
            is_root_group = False
            
            if row.Id_Hierarquia and row.Id_Hierarquia in tree_map:
                node = tree_map[row.Id_Hierarquia]
                cc_alvo = node.Raiz_Centro_Custo_Codigo
                full_path = node.full_path
                nome_cc_detalhe = node.Raiz_Centro_Custo_Nome
                raiz_virt_id = node.Raiz_No_Virtual_Id
                
                # --- LÓGICA DE CATEGORIZAÇÃO ---
                if node.Raiz_Centro_Custo_Tipo:
                    # É filho de um Tipo de CC (ex: ADM, COML)
                    tipo_principal = node.Raiz_Centro_Custo_Tipo
                elif node.Raiz_No_Virtual_Nome:
                    # É filho de um Nó Virtual (ex: EBITDA)
                    tipo_principal = node.Raiz_No_Virtual_Nome
                else:
                    # É um Subgrupo Raiz Global (ex: TESTE)
                    # O nome do grupo raiz é a primeira parte do path
                    root_name = full_path.split('||')[0]
                    tipo_principal = root_name
                    is_root_group = True

            elif row.Id_No_Virtual:
                full_path = 'Direto'
                tipo_principal = row.Nome_Virtual_Direto
                raiz_virt_id = row.Id_Virtual_Direto
            
            obj_def = Definition(
                Conta_Contabil=row.Conta_Contabil,
                CC_Alvo=cc_alvo,
                Id_Hierarquia=row.Id_Hierarquia,
                Id_No_Virtual=row.Id_No_Virtual,
                Nome_Personalizado_Def=row.Nome_Personalizado,
                full_path=full_path,
                Tipo_Principal=tipo_principal,
                Raiz_Centro_Custo_Nome=nome_cc_detalhe,
                Raiz_No_Virtual_Id=raiz_virt_id,
                Is_Root_Group=is_root_group
            )
            definitions[row.Conta_Contabil].append(obj_def)
            
        return tree_map, definitions

    def get_ajustes_map(self):
        sql = text("""
            SELECT * FROM "Dre_Schema"."Ajustes_Razao" 
            WHERE "Status" != 'Reprovado'
        """)
        rows = self.session.execute(sql).fetchall()
        
        edicoes = {}
        inclusoes = []
        
        for row in rows:
            if row.Tipo_Operacao == 'EDICAO':
                edicoes[row.Hash_Linha_Original] = row
            elif row.Tipo_Operacao == 'INCLUSAO':
                inclusoes.append(row)
                
        return edicoes, inclusoes

    def get_ordenamento(self):
        sql = text("SELECT id_referencia, tipo_no, ordem FROM \"Dre_Schema\".\"DRE_Ordenamento\" WHERE contexto_pai = 'root'")
        rows = self.session.execute(sql).fetchall()
        ordem_map = {f"{r.tipo_no}:{r.id_referencia}": r.ordem for r in rows}
        return ordem_map

    # =========================================================================
    # --- MÉTODOS DO RELATÓRIO (MODIFICADO) ---
    # =========================================================================

    def processar_relatorio(self, filtro_origem='Consolidado', agrupar_por_cc=False):
        """Processa DRE Gerencial Híbrida (Estrutura + Dados + Ajustes)."""
        tree_map, definitions = self.get_estrutura_hierarquia()
        ajustes_edicao, ajustes_inclusao = self.get_ajustes_map()
        ordem_map = self.get_ordenamento()
        
        # Mapa para exibir nomes de contas no esqueleto
        sql_nomes = text('SELECT DISTINCT "Conta", "Título Conta" FROM "Dre_Schema"."Razao_Dados_Consolidado"')
        res_nomes = self.session.execute(sql_nomes).fetchall()
        mapa_titulos = {row[0]: row[1] for row in res_nomes}

        aggregated_data = {} 

        # --- FUNÇÃO DE PROCESSAMENTO DE LINHA ---
        def process_row(origem, conta, titulo, data, saldo, cc_original_str, row_hash=None, is_skeleton=False, forced_match=None):
            """
            Processa uma linha de dado ou de estrutura.
            
            forced_match: Usado quando is_skeleton=True para garantir que TODAS as regras
            de uma conta sejam criadas, não apenas a primeira.
            """
            
            # 1. APLICAÇÃO DE EDIÇÕES (PRIORIDADE MÁXIMA)
            # Se a linha tem um hash e existe na tabela de ajustes, sobrescreve tudo.
            if not is_skeleton and row_hash and row_hash in ajustes_edicao:
                adj = ajustes_edicao[row_hash]
                
                if adj.Invalido:
                    return # Ignora linha se foi marcada como inválida
                
                # Sobrescreve dados com o ajuste
                origem = adj.Origem or origem
                conta = adj.Conta or conta
                titulo = adj.Titulo_Conta or titulo
                cc_original_str = str(adj.Centro_Custo) if adj.Centro_Custo else cc_original_str
                data = adj.Data or data
                
                # Regra de Não Operacional (Transforma em 0000...)
                if adj.Is_Nao_Operacional:
                    conta = '00000000000'
                    titulo = 'Não Operacionais'
                
                # Recalcula saldo se necessário
                if adj.Exibir_Saldo:
                    saldo = (float(adj.Debito or 0) - float(adj.Credito or 0))
                else:
                    saldo = 0.0

            # 2. ENCONTRA A REGRA DE CLASSIFICAÇÃO NA ÁRVORE
            match = forced_match # Se veio forçado do esqueleto, usa ele.
            
            if not match:
                rules = definitions.get(conta, [])
                if not rules: return # Conta não configurada na DRE não aparece

                # Se for dado real, tenta casar pelo Centro de Custo específico
                if cc_original_str:
                    cc_int = None
                    try: 
                        cc_int = int(''.join(filter(str.isdigit, str(cc_original_str))))
                    except: pass
                    
                    if cc_int is not None:
                        for rule in rules:
                            if rule.CC_Alvo is not None and cc_int == rule.CC_Alvo:
                                match = rule; break
                
                # Se não achou regra específica por CC, pega a regra Default (genérica)
                if not match:
                    # Como já geramos o esqueleto para todas as regras, 
                    # aqui podemos pegar a primeira disponível para acumular o valor
                    match = rules[0]
            
            if not match: return

            # 3. DEFINIÇÃO DA CHAVE DE AGRUPAMENTO
            tipo_cc = match.Tipo_Principal or 'Outros' # Aqui entrará "TESTE" se for root
            root_virtual_id = match.Raiz_No_Virtual_Id
            caminho = match.full_path or 'Não Classificado'
            
            # Lógica de Ordenação dos Blocos Principais
            ordem = 999
            if root_virtual_id:
                ordem = ordem_map.get(f"virtual:{root_virtual_id}", 999)
            elif match.Is_Root_Group:
                # Se for Grupo Raiz (TESTE), tenta achar a ordem do subgrupo
                if match.Id_Hierarquia:
                    ordem_db = ordem_map.get(f"subgrupo:{match.Id_Hierarquia}")
                    if ordem_db is not None:
                         ordem = ordem_db
                    else:
                         ordem = 0 # Joga para o topo se não tiver ordem definida
            else:
                ordem = ordem_map.get(f"tipo_cc:{tipo_cc}", 999)

            # Labels para Contas Personalizadas
            conta_para_chave = f"GRP_{match.Nome_Personalizado_Def}" if match.Nome_Personalizado_Def else conta
            titulo_para_exibicao = match.Nome_Personalizado_Def if match.Nome_Personalizado_Def else titulo
            conta_display = match.Nome_Personalizado_Def if match.Nome_Personalizado_Def else conta

            # Chave única da linha
            group_key = (tipo_cc, root_virtual_id, caminho, titulo_para_exibicao, conta_para_chave)
            if agrupar_por_cc: 
                group_key = group_key + (match.Raiz_Centro_Custo_Nome,)

            # 4. INICIALIZAÇÃO DA LINHA (Se não existir)
            if group_key not in aggregated_data:
                item = {
                    'origem': origem, 'Conta': conta_display, 'Titulo_Conta': titulo_para_exibicao,
                    'Tipo_CC': tipo_cc, 'Root_Virtual_Id': root_virtual_id, 'Caminho_Subgrupos': caminho, 
                    'ordem_prioridade': ordem, 'Total_Ano': 0.0
                }
                for m in self.meses[:-1]: item[m] = 0.0
                if agrupar_por_cc: item['Nome_CC'] = match.Raiz_Centro_Custo_Nome
                aggregated_data[group_key] = item

            # 5. ACUMULAÇÃO DE VALORES (Apenas se tiver dados e não for esqueleto)
            if not is_skeleton and data:
                try:
                    mes_nome = self.meses[data.month - 1]
                    val_inv = saldo * -1 # Inverte sinal
                    aggregated_data[group_key][mes_nome] += val_inv
                    aggregated_data[group_key]['Total_Ano'] += val_inv
                except: pass

        # =====================================================================
        # PASSO 1: GERA O ESQUELETO COMPLETO
        # =====================================================================
        # Iteramos sobre TODAS as regras de TODAS as contas para garantir
        # que cada "vínculo" configurado gere uma linha no relatório, mesmo que zerada.
        for conta_def, lista_regras in definitions.items():
            titulo_conta = mapa_titulos.get(conta_def, "Conta Configurada")
            for regra in lista_regras:
                # Aqui passamos 'forced_match=regra' para criar a linha em TODOS os grupos
                # onde essa conta foi vinculada (ADM, COML, TESTE, etc.)
                process_row("Config", conta_def, titulo_conta, None, 0.0, None, None, is_skeleton=True, forced_match=regra)

        # =====================================================================
        # PASSO 2: PROCESSA DADOS DO RAZÃO
        # =====================================================================
        where_origem = ""
        if filtro_origem == 'FARMA': where_origem = "WHERE \"origem\" = 'FARMA'"
        elif filtro_origem == 'FARMADIST': where_origem = "WHERE \"origem\" = 'FARMADIST'"
        else: where_origem = "WHERE \"origem\" IN ('FARMA', 'FARMADIST')"
        
        sql_raw = text(f"""
            SELECT "origem", "Conta", "Título Conta", "Data", "Numero", "Centro de Custo", "Saldo", "Filial", "Item"
            FROM "Dre_Schema"."Razao_Dados_Consolidado" {where_origem}
        """)
        raw_rows = self.session.execute(sql_raw).fetchall()

        for row in raw_rows:
            # Aqui NÃO passamos forced_match. O sistema vai achar o match baseado no CC da linha
            # e somar na chave criada no Passo 1 (ou criar nova se for genérica).
            # A prioridade de ajustes (hash) acontece dentro do process_row.
            process_row(
                row.origem, row.Conta, row.__getattr__('Título Conta'), 
                row.Data, row.Saldo, row.__getattr__('Centro de Custo'), 
                self._gerar_hash_linha(row), 
                is_skeleton=False
            )

        # =====================================================================
        # PASSO 3: PROCESSA INCLUSÕES MANUAIS (SEM RAZÃO)
        # =====================================================================
        for adj in ajustes_inclusao:
            if not adj.Invalido:
                saldo_adj = (float(adj.Debito or 0) - float(adj.Credito or 0)) if adj.Exibir_Saldo else 0.0
                c = '00000000000' if adj.Is_Nao_Operacional else adj.Conta
                t = 'Não Operacionais' if adj.Is_Nao_Operacional else adj.Titulo_Conta
                
                process_row(
                    adj.Origem, c, t, adj.Data, saldo_adj, str(adj.Centro_Custo), 
                    None, is_skeleton=False
                )

        # Finalização e Ordenação
        final_list = list(aggregated_data.values())
        if agrupar_por_cc: 
            final_list.sort(key=lambda x: (x['ordem_prioridade'], x['Tipo_CC'], x['Nome_CC'] or ''))
        else: 
            final_list.sort(key=lambda x: x['ordem_prioridade'])
        
        return final_list

    def calcular_nos_virtuais(self, data_rows):
        """Calcula fórmulas (Nós Virtuais)."""
        memoria = defaultdict(lambda: {m: 0.0 for m in self.meses})
        
        for row in data_rows:
            tipo = str(row['Tipo_CC']).strip()
            virt_id = row.get('Root_Virtual_Id')
            keys_to_update = [f"tipo_cc:{tipo}"]
            if virt_id:
                keys_to_update.append(f"no_virtual:{virt_id}")
                keys_to_update.append(f"no_virtual:{tipo}")

            for m in self.meses:
                val = row.get(m, 0.0)
                for k in keys_to_update:
                    memoria[k][m] += val
        
        sql_formulas = text("""
            SELECT nv."Id", nv."Nome", nv."Formula_JSON", nv."Estilo_CSS", nv."Tipo_Exibicao", COALESCE(ord.ordem, 999) as ordem
            FROM "Dre_Schema"."DRE_Estrutura_No_Virtual" nv
            LEFT JOIN "Dre_Schema"."DRE_Ordenamento" ord ON ord.id_referencia = CAST(nv."Id" AS TEXT) AND ord.contexto_pai = 'root'
            WHERE nv."Is_Calculado" = true
            ORDER BY ordem ASC
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
                    'origem': 'Calculado',
                    'Conta': f"CALC_{form.Id}",
                    'Titulo_Conta': form.Nome,
                    'Tipo_CC': form.Nome,
                    'Caminho_Subgrupos': 'Calculado',
                    'ordem_prioridade': form.ordem,
                    'Is_Calculado': True,
                    'Estilo_CSS': form.Estilo_CSS,
                    'Tipo_Exibicao': form.Tipo_Exibicao,
                    'Root_Virtual_Id': form.Id 
                }

                for mes in self.meses:
                    vals = []
                    for op in operandos:
                        chave = f"{op['tipo']}:{str(op['id']).strip()}"
                        val = memoria.get(chave, {}).get(mes, 0.0)
                        if val == 0.0:
                             for k_mem, v_mem in memoria.items():
                                 if k_mem.lower() == chave.lower():
                                     val = v_mem.get(mes, 0.0)
                                     break
                        vals.append(val)
                    
                    res = 0.0
                    if not vals: res = 0.0
                    elif operacao == 'soma': res = sum(vals)
                    elif operacao == 'subtracao': res = vals[0] - sum(vals[1:])
                    elif operacao == 'multiplicacao': res = math.prod(vals)
                    elif operacao == 'divisao': res = vals[0] / vals[1] if (len(vals) > 1 and vals[1] != 0) else 0.0
                    
                    final_val = res * multiplicador
                    nova_linha[mes] = final_val
                    memoria[f"no_virtual:{form.Id}"][mes] = final_val
                    memoria[f"no_virtual:{form.Nome}"][mes] = final_val

                novas_linhas.append(nova_linha)
            except Exception as e:
                print(f"Erro ao calcular fórmula {form.Nome}: {e}")

        todos = data_rows + novas_linhas
        todos.sort(key=lambda x: x.get('ordem_prioridade', 999))
        return todos

    # (Métodos get_razao_dados e get_razao_resumo mantidos como no seu arquivo original)
    def get_razao_dados(self, page=1, per_page=50, search_term='', view_type='original'):
        offset = (page - 1) * per_page
        params = {'limit': per_page, 'offset': offset}
        filter_snippet = ""
        if search_term:
            filter_snippet = """
                AND (
                    "Conta"::TEXT ILIKE :termo OR "Título Conta" ILIKE :termo
                    OR "Descricao" ILIKE :termo OR "Numero"::TEXT ILIKE :termo
                    OR "origem" ILIKE :termo
                )
            """
            params['termo'] = f"%{search_term}%"

        if view_type == 'adjusted':
            filter_snippet_ajuste = ""
            if search_term:
                filter_snippet_ajuste = filter_snippet.replace('"Título Conta"', '"Titulo_Conta"').replace('"Nome do CC"', "''").replace('"origem"', '"Origem"')
            sql_query = f"""
                SELECT * FROM (
                    SELECT 'RAZAO' as source_type, "origem", "Conta", "Título Conta", "Data", "Numero", "Descricao", "Contra Partida - Credito", CAST("Filial" AS TEXT) as "Filial", CAST("Centro de Custo" AS TEXT) as "Centro de Custo", "Item", "Debito", "Credito", "Saldo", "Nome do CC"
                    FROM "Dre_Schema"."Razao_Dados_Consolidado" WHERE 1=1 {filter_snippet}
                    UNION ALL
                    SELECT 'AJUSTE' as source_type, "Origem", "Conta", "Titulo_Conta", "Data", "Numero", "Descricao", NULL, "Filial", "Centro_Custo", "Item", CASE WHEN "Exibir_Saldo" THEN COALESCE("Debito", 0) ELSE 0 END, CASE WHEN "Exibir_Saldo" THEN COALESCE("Credito", 0) ELSE 0 END, CASE WHEN "Exibir_Saldo" THEN (COALESCE("Debito", 0) - COALESCE("Credito", 0)) ELSE 0 END, NULL
                    FROM "Dre_Schema"."Ajustes_Razao" WHERE "Tipo_Operacao" = 'INCLUSAO' AND "Status" != 'Reprovado' {filter_snippet_ajuste}
                ) AS uniao_dados ORDER BY "Data", "Conta", "Numero" LIMIT :limit OFFSET :offset
            """
            sql_count = f"SELECT COUNT(*) FROM \"Dre_Schema\".\"Razao_Dados_Consolidado\" WHERE 1=1 {filter_snippet}" 
        else:
            sql_query = f"""
                SELECT 'RAZAO' as source_type, "origem", "Conta", "Título Conta", "Data", "Numero", "Descricao", "Contra Partida - Credito", "Filial", "Centro de Custo", "Item", "Debito", "Credito", "Saldo", "Nome do CC"
                FROM "Dre_Schema"."Razao_Dados_Consolidado" WHERE 1=1 {filter_snippet} ORDER BY "Data", "Conta", "Numero" LIMIT :limit OFFSET :offset
            """
            sql_count = f'SELECT COUNT(*) FROM "Dre_Schema"."Razao_Dados_Consolidado" WHERE 1=1 {filter_snippet}'

        total_registros = self.session.execute(text(sql_count), params).scalar() or 0
        total_paginas = (total_registros // per_page) + (1 if total_registros % per_page > 0 else 0)
        rows = self.session.execute(text(sql_query), params).fetchall()
        
        result_list = []
        ajustes_edicao = {}
        if view_type == 'adjusted': ajustes_edicao, _ = self.get_ajustes_map()

        for i, r in enumerate(rows, 1):
            row_dict = {'id': i + offset, 'origem': r.origem, 'conta': r.Conta, 'titulo_conta': getattr(r, 'Título Conta', ''), 'data': r.Data.isoformat() if r.Data else None, 'numero': r.Numero, 'descricao': r.Descricao, 'debito': float(r.Debito or 0), 'credito': float(r.Credito or 0), 'saldo': float(r.Saldo or 0), 'is_ajustado': False}
            if hasattr(r, 'source_type') and r.source_type == 'AJUSTE':
                row_dict['is_ajustado'] = True; row_dict['origem'] += " (INC)"
            elif view_type == 'adjusted':
                r_hash = self._gerar_hash_linha(r)
                if r_hash in ajustes_edicao:
                    adj = ajustes_edicao[r_hash]
                    if adj.Exibir_Saldo: row_dict['saldo'] = float(adj.Debito or 0) - float(adj.Credito or 0)
                    else: row_dict['saldo'] = 0.0
                    row_dict['is_ajustado'] = True; row_dict['origem'] += " (EDT)"
            result_list.append(row_dict)
        return {'pagina_atual': page, 'total_paginas': total_paginas, 'total_registros': total_registros, 'dados': result_list}

    def get_razao_resumo(self, view_type='original'):
        sql = text("SELECT COUNT(*), SUM(\"Debito\"), SUM(\"Credito\"), SUM(\"Saldo\") FROM \"Dre_Schema\".\"Razao_Dados_Consolidado\"")
        base = self.session.execute(sql).fetchone()
        return {'total_registros': base[0] or 0, 'total_debito': float(base[1] or 0), 'total_credito': float(base[2] or 0), 'saldo_total': float(base[3] or 0)}