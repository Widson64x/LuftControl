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

    def _gerar_hash_linha(self, row):
        """Rebater o MD5 exato que o SQL gerava para encontrar ajustes."""
        parts = [
            str(row.origem).strip() if row.origem else 'None',
            str(row.Filial).strip() if row.Filial else 'None',
            str(row.Numero).strip() if row.Numero else 'None',
            str(row.Item).strip() if row.Item else 'None',
            str(row.Conta).strip() if row.Conta else 'None',
            row.Data.strftime('%Y-%m-%d') if row.Data else 'None'
        ]
        raw_string = "-".join(parts)
        return hashlib.md5(raw_string.encode('utf-8')).hexdigest()

    def get_estrutura_hierarquia(self):
        """Busca e monta a árvore de hierarquia e definições de conta."""
        
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
                    tp."Raiz_Centro_Custo_Codigo", tp."Raiz_No_Virtual_Id", 
                    tp."Raiz_Centro_Custo_Tipo", tp."Raiz_No_Virtual_Nome", tp."Raiz_Centro_Custo_Nome",
                    CAST(tp.full_path || '||' || child."Nome" AS TEXT)
                FROM "Dre_Schema"."DRE_Estrutura_Hierarquia" child
                JOIN TreePath tp ON child."Id_Pai" = tp."Id"
            )
            SELECT * FROM TreePath
        """)
        tree_rows = self.session.execute(sql_tree).fetchall()
        
        # Mapa de ID Hierarquia -> Dados do Nó
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
            'Raiz_Centro_Custo_Nome', 'Raiz_No_Virtual_Id'
        ])

        definitions = defaultdict(list)
        
        for row in def_rows:
            cc_alvo = None
            full_path = None
            tipo_principal = None
            nome_cc_detalhe = None
            raiz_virt_id = None
            
            if row.Id_Hierarquia and row.Id_Hierarquia in tree_map:
                node = tree_map[row.Id_Hierarquia]
                cc_alvo = node.Raiz_Centro_Custo_Codigo
                full_path = node.full_path
                tipo_principal = node.Raiz_Centro_Custo_Tipo or node.Raiz_No_Virtual_Nome
                nome_cc_detalhe = node.Raiz_Centro_Custo_Nome
                raiz_virt_id = node.Raiz_No_Virtual_Id
            
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
                Raiz_No_Virtual_Id=raiz_virt_id
            )
            definitions[row.Conta_Contabil].append(obj_def)
            
        return tree_map, definitions

    def get_ajustes_map(self):
        """Busca todos os ajustes aprovados."""
        sql = text("""
            SELECT * FROM "Dre_Schema"."Ajustes_Razao" 
            WHERE "Status" != 'Reprovado'
        """)
        rows = self.session.execute(sql).fetchall()
        
        edicoes = {} # Chave: Hash
        inclusoes = [] # Lista de linhas
        
        for row in rows:
            if row.Tipo_Operacao == 'EDICAO':
                edicoes[row.Hash_Linha_Original] = row
            elif row.Tipo_Operacao == 'INCLUSAO':
                inclusoes.append(row)
                
        return edicoes, inclusoes

    def get_ordenamento(self):
        """Busca as ordens configuradas."""
        sql = text("SELECT id_referencia, tipo_no, ordem FROM \"Dre_Schema\".\"DRE_Ordenamento\" WHERE contexto_pai = 'root'")
        rows = self.session.execute(sql).fetchall()
        
        ordem_map = {}
        for r in rows:
            key = f"{r.tipo_no}:{r.id_referencia}"
            ordem_map[key] = r.ordem
        return ordem_map

    # =========================================================================
    # --- MÉTODOS DO RAZÃO (CORRIGIDO: FILTRO DE BUSCA NO UNION) ---
    # =========================================================================

    def get_razao_dados(self, page=1, per_page=50, search_term='', view_type='original'):
        """
        Retorna dados paginados do Razão.
        Se view_type='adjusted', faz UNION com a tabela de Ajustes (Inclusões) 
        e aplica patch de edições nos dados originais.
        """
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
            # Prepara filtro para tabela Ajustes_Razao (mapeando nomes de colunas diferentes)
            # Título Conta -> Titulo_Conta
            # Nome do CC -> '' (não existe, vira vazio)
            # origem -> Origem (Case Sensitive fix)
            filter_snippet_ajuste = ""
            if search_term:
                filter_snippet_ajuste = filter_snippet.replace('"Título Conta"', '"Titulo_Conta"') \
                                                      .replace('"Nome do CC"', "''") \
                                                      .replace('"origem"', '"Origem"')

            sql_query = f"""
                SELECT * FROM (
                    -- PARTE 1: DADOS ORIGINAIS
                    SELECT 
                        'RAZAO' as source_type,
                        "origem", "Conta", "Título Conta", "Data", "Numero", "Descricao", 
                        "Contra Partida - Credito", 
                        CAST("Filial" AS TEXT) as "Filial", 
                        CAST("Centro de Custo" AS TEXT) as "Centro de Custo",
                        "Item",
                        "Debito", "Credito", "Saldo", "Nome do CC"
                    FROM "Dre_Schema"."Razao_Dados_Consolidado"
                    WHERE 1=1 {filter_snippet}
                    
                    UNION ALL
                    
                    -- PARTE 2: INCLUSÕES
                    SELECT 
                        'AJUSTE' as source_type,
                        "Origem" as "origem",
                        "Conta",
                        "Titulo_Conta" as "Título Conta",
                        "Data",
                        "Numero",
                        "Descricao",
                        NULL as "Contra Partida - Credito",
                        "Filial",
                        "Centro_Custo" as "Centro de Custo",
                        "Item",
                        CASE WHEN "Exibir_Saldo" THEN COALESCE("Debito", 0) ELSE 0 END as "Debito",
                        CASE WHEN "Exibir_Saldo" THEN COALESCE("Credito", 0) ELSE 0 END as "Credito",
                        CASE WHEN "Exibir_Saldo" THEN (COALESCE("Debito", 0) - COALESCE("Credito", 0)) ELSE 0 END as "Saldo",
                        NULL as "Nome do CC"
                    FROM "Dre_Schema"."Ajustes_Razao"
                    WHERE "Tipo_Operacao" = 'INCLUSAO' 
                      AND "Status" != 'Reprovado'
                      {filter_snippet_ajuste}
                ) AS uniao_dados
                ORDER BY "Data", "Conta", "Numero"
                LIMIT :limit OFFSET :offset
            """
            
            sql_count = f"""
                SELECT SUM(cnt) FROM (
                    SELECT COUNT(*) as cnt FROM "Dre_Schema"."Razao_Dados_Consolidado" WHERE 1=1 {filter_snippet}
                    UNION ALL
                    SELECT COUNT(*) as cnt FROM "Dre_Schema"."Ajustes_Razao" 
                    WHERE "Tipo_Operacao" = 'INCLUSAO' AND "Status" != 'Reprovado'
                    {filter_snippet_ajuste}
                ) as tbl_counts
            """
            
        else:
            # ORIGINAL (Adicionada coluna 'Item' para consistência)
            sql_query = f"""
                SELECT 
                    'RAZAO' as source_type,
                    "origem", "Conta", "Título Conta", "Data", "Numero", "Descricao", 
                    "Contra Partida - Credito", "Filial", "Centro de Custo", "Item",
                    "Debito", "Credito", "Saldo", "Nome do CC"
                FROM "Dre_Schema"."Razao_Dados_Consolidado"
                WHERE 1=1 {filter_snippet}
                ORDER BY "Data", "Conta", "Numero"
                LIMIT :limit OFFSET :offset
            """
            sql_count = f'SELECT COUNT(*) FROM "Dre_Schema"."Razao_Dados_Consolidado" WHERE 1=1 {filter_snippet}'

        total_registros = self.session.execute(text(sql_count), params).scalar() or 0
        total_paginas = (total_registros // per_page) + (1 if total_registros % per_page > 0 else 0)
        
        rows = self.session.execute(text(sql_query), params).fetchall()
        
        result_list = []
        ajustes_edicao = {}
        
        if view_type == 'adjusted':
            ajustes_edicao, _ = self.get_ajustes_map()

        for i, r in enumerate(rows, 1):
            try:
                filial_val = int(r.Filial) if r.Filial and str(r.Filial).replace('.','').isdigit() else r.Filial
                cc_val = int(getattr(r, 'Centro de Custo')) if getattr(r, 'Centro de Custo') and str(getattr(r, 'Centro de Custo')).replace('.','').isdigit() else getattr(r, 'Centro de Custo')
            except:
                filial_val = r.Filial
                cc_val = getattr(r, 'Centro de Custo')

            row_dict = {
                'id': i + offset,
                'origem': r.origem,
                'conta': r.Conta, 
                'titulo_conta': getattr(r, 'Título Conta', ''),
                'data': r.Data.isoformat() if r.Data else None,
                'numero': r.Numero,
                'descricao': r.Descricao,
                'contra_partida': getattr(r, 'Contra Partida - Credito', ''),
                'filial': filial_val,
                'centro_custo': cc_val,
                'debito': float(r.Debito or 0),
                'credito': float(r.Credito or 0),
                'saldo': float(r.Saldo or 0),
                'nome_cc': getattr(r, 'Nome do CC', ''),
                'is_ajustado': False
            }

            if hasattr(r, 'source_type') and r.source_type == 'AJUSTE':
                row_dict['is_ajustado'] = True
                row_dict['origem'] = f"{row_dict['origem']} (INC)"
            
            elif (not hasattr(r, 'source_type') or r.source_type == 'RAZAO') and view_type == 'adjusted':
                # Agora o 'r' tem a coluna Item, então o hash funciona
                r_hash = self._gerar_hash_linha(r)
                if r_hash in ajustes_edicao:
                    adj = ajustes_edicao[r_hash]
                    if adj.Conta: row_dict['conta'] = adj.Conta
                    if adj.Titulo_Conta: row_dict['titulo_conta'] = adj.Titulo_Conta
                    if adj.Descricao: row_dict['descricao'] = adj.Descricao
                    
                    if adj.Exibir_Saldo:
                        row_dict['debito'] = float(adj.Debito or 0)
                        row_dict['credito'] = float(adj.Credito or 0)
                        row_dict['saldo'] = row_dict['debito'] - row_dict['credito']
                    else:
                        row_dict['debito'] = 0.0
                        row_dict['credito'] = 0.0
                        row_dict['saldo'] = 0.0
                    
                    row_dict['is_ajustado'] = True
                    row_dict['origem'] = f"{row_dict['origem']} (EDT)"

            result_list.append(row_dict)
        
        return {
            'pagina_atual': page,
            'total_paginas': total_paginas,
            'total_registros': total_registros,
            'termo_busca': search_term,
            'dados': result_list
        }

    def get_razao_resumo(self, view_type='original'):
        """Retorna totais."""
        sql_base = text("""
            SELECT 
                COUNT(*) as total_registros,
                COALESCE(SUM("Debito"), 0) as total_debito,
                COALESCE(SUM("Credito"), 0) as total_credito,
                COALESCE(SUM("Saldo"), 0) as saldo_total
            FROM "Dre_Schema"."Razao_Dados_Consolidado"
        """)
        base = self.session.execute(sql_base).fetchone()
        
        resumo = {
            'total_registros': base[0] or 0,
            'total_debito': float(base[1] or 0),
            'total_credito': float(base[2] or 0),
            'saldo_total': float(base[3] or 0)
        }

        if view_type == 'adjusted':
            sql_incl = text("""
                SELECT 
                    COUNT(*) as cnt,
                    COALESCE(SUM(CASE WHEN "Exibir_Saldo" THEN "Debito" ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN "Exibir_Saldo" THEN "Credito" ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN "Exibir_Saldo" THEN ("Debito" - "Credito") ELSE 0 END), 0)
                FROM "Dre_Schema"."Ajustes_Razao"
                WHERE "Tipo_Operacao" = 'INCLUSAO' AND "Status" != 'Reprovado'
            """)
            incl = self.session.execute(sql_incl).fetchone()
            
            if incl:
                resumo['total_registros'] += (incl[0] or 0)
                resumo['total_debito'] += float(incl[1] or 0)
                resumo['total_credito'] += float(incl[2] or 0)
                resumo['saldo_total'] += float(incl[3] or 0)

        return resumo

    def processar_relatorio(self, filtro_origem='Consolidado', agrupar_por_cc=False):
        """Processa DRE Gerencial."""
        tree_map, definitions = self.get_estrutura_hierarquia()
        ajustes_edicao, ajustes_inclusao = self.get_ajustes_map()
        ordem_map = self.get_ordenamento()
        
        where_origem = ""
        if filtro_origem == 'FARMA': where_origem = "WHERE \"origem\" = 'FARMA'"
        elif filtro_origem == 'FARMADIST': where_origem = "WHERE \"origem\" = 'FARMADIST'"
        else: where_origem = "WHERE \"origem\" IN ('FARMA', 'FARMADIST')"

        sql_raw = text(f"""
            SELECT "origem", "Conta", "Título Conta", "Data", "Numero", "Item", 
                   "Centro de Custo", "Saldo", "Debito", "Credito", "Filial"
            FROM "Dre_Schema"."Razao_Dados_Consolidado"
            {where_origem}
        """)
        raw_rows = self.session.execute(sql_raw).fetchall()

        aggregated_data = {} 

        def process_row(origem, conta, titulo, data, saldo, cc_original_str, row_hash=None):
            is_nao_operacional = False
            if row_hash and row_hash in ajustes_edicao:
                adj = ajustes_edicao[row_hash]
                origem = adj.Origem or origem
                conta = adj.Conta or conta
                titulo = adj.Titulo_Conta or titulo
                cc_original_str = str(adj.Centro_Custo) if adj.Centro_Custo else cc_original_str
                data = adj.Data or data
                is_nao_operacional = adj.Is_Nao_Operacional or False
                if adj.Exibir_Saldo: saldo = (float(adj.Debito or 0) - float(adj.Credito or 0))
                else: saldo = 0.0
            
            if is_nao_operacional: conta, titulo = '00000000000', 'Não Operacionais'

            rules = definitions.get(conta, [])
            match, cc_int = None, None
            try:
                if cc_original_str:
                    nums = ''.join(filter(str.isdigit, str(cc_original_str)))
                    if nums: cc_int = int(nums)
            except: pass

            for rule in rules:
                if rule.CC_Alvo is not None:
                    if cc_int == rule.CC_Alvo: match = rule; break
                else:
                    if match is None: match = rule
            
            if not match: return 

            tipo_cc = match.Tipo_Principal or 'Outros'
            root_virtual_id = match.Raiz_No_Virtual_Id
            caminho = match.full_path or 'Não Classificado'
            ordem = ordem_map.get(f"virtual:{root_virtual_id}", 999) if root_virtual_id else ordem_map.get(f"tipo_cc:{tipo_cc}", 999)

            group_key = (tipo_cc, root_virtual_id, caminho, titulo, conta, match.Raiz_Centro_Custo_Nome) if agrupar_por_cc else (tipo_cc, root_virtual_id, caminho, titulo, conta)

            if group_key not in aggregated_data:
                item = {
                    'origem': origem, 'Conta': conta, 'Titulo_Conta': titulo,
                    'Tipo_CC': tipo_cc, 'Root_Virtual_Id': root_virtual_id,
                    'Caminho_Subgrupos': caminho, 'ordem_prioridade': ordem, 'Total_Ano': 0.0
                }
                for m in self.meses[:-1]: item[m] = 0.0
                if agrupar_por_cc: item['Nome_CC'] = match.Raiz_Centro_Custo_Nome
                aggregated_data[group_key] = item

            if data:
                try:
                    mes_nome = self.meses[data.month - 1] 
                    val_inv = saldo * -1
                    aggregated_data[group_key][mes_nome] += val_inv
                    aggregated_data[group_key]['Total_Ano'] += val_inv
                except: pass

        for row in raw_rows:
            process_row(row.origem, row.Conta, row.__getattr__('Título Conta'), row.Data, row.Saldo, row.__getattr__('Centro de Custo'), self._gerar_hash_linha(row))

        for adj in ajustes_inclusao:
            saldo_adj = (float(adj.Debito or 0) - float(adj.Credito or 0)) if adj.Exibir_Saldo else 0.0
            conta_inc = '00000000000' if adj.Is_Nao_Operacional else adj.Conta
            titulo_inc = 'Não Operacionais' if adj.Is_Nao_Operacional else adj.Titulo_Conta
            process_row(adj.Origem, conta_inc, titulo_inc, adj.Data, saldo_adj, str(adj.Centro_Custo), None)

        final_list = list(aggregated_data.values())
        if agrupar_por_cc: final_list.sort(key=lambda x: (x['ordem_prioridade'], x['Tipo_CC'], x['Nome_CC'] or ''))
        else: final_list.sort(key=lambda x: x['ordem_prioridade'])
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