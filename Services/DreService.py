import hashlib
import json
import math
from datetime import datetime
from collections import defaultdict, namedtuple
from sqlalchemy import text

class DreService:
    def __init__(self, session):
        self.session = session
        # Colunas de meses para iteração
        self.meses = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez','Total_Ano']

    def aplicar_escala_milhares(self, data_rows):
        """
        Divide todos os valores monetários por 1000 para visão DRE (Milhares).
        """
        for row in data_rows:
            for col in self.meses:
                val = row.get(col)
                if val is not None and isinstance(val, (int, float)):
                    row[col] = val / 1000.0
        return data_rows
    
    def _gerar_hash_linha(self, row):
        """
        Gera o HASH único da linha para identificar ajustes.
        Lógica idêntica ao Routes/Adjustments.py.
        Chave: ORIGEM + CONTA + DATA + NUMERO + TIPO(C ou D)
        """
        def clean_str(val):
            if val is None: return 'None'
            s = str(val).strip()
            return 'None' if s == '' or s.lower() == 'none' else s

        # 1. Origem
        origem = clean_str(getattr(row, 'origem', '') or getattr(row, 'Origem', ''))

        # 2. Conta
        conta = clean_str(getattr(row, 'Conta', ''))

        # 3. Data (Formatação Estrita YYYY-MM-DD)
        dt_val = getattr(row, 'Data', None)
        dt_str = 'None'
        if dt_val:
            if hasattr(dt_val, 'strftime'):
                dt_str = dt_val.strftime('%Y-%m-%d')
            else:
                # Fallback para string, pega apenas a parte da data antes do espaço/T
                s_dt = str(dt_val).strip()
                if ' ' in s_dt: s_dt = s_dt.split(' ')[0]
                if 'T' in s_dt: s_dt = s_dt.split('T')[0]
                dt_str = s_dt

        # 4. Numero
        numero = clean_str(getattr(row, 'Numero', ''))

        # 5. Tipo de Lançamento (Crédito ou Débito)
        # Necessário para diferenciar pernas de lançamentos com mesmo doc e data
        val_deb = float(getattr(row, 'Debito', 0) or 0)
        val_cred = float(getattr(row, 'Credito', 0) or 0)
        
        tipo = 'D' # Default para linhas zeradas ou puramente débito
        if val_cred > 0 and val_deb == 0:
            tipo = 'C'
        elif val_deb > 0 and val_cred == 0:
            tipo = 'D'
        elif val_cred > 0 and val_deb > 0:
            # Caso híbrido: define pelo maior valor
            tipo = 'C' if val_cred >= val_deb else 'D'
        
        # Montagem da String Raw
        raw = f"{origem}-{conta}-{dt_str}-{numero}-{tipo}"
        
        # Retorna MD5
        return hashlib.md5(raw.encode('utf-8')).hexdigest()

    def get_estrutura_hierarquia(self):
        """
        Monta a árvore de estrutura da DRE e mapeia as regras de vínculos.
        """
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
                    # Se não tem tipo nem virtual pai, é um grupo raiz (ex: TESTE)
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

    def get_ajustes_map(self):
        """
        Retorna dicionários de Ajustes para aplicação rápida.
        Separa o que é EDIÇÃO (Override de linha existente) do que é INCLUSÃO (Linha nova).
        """
        # Busca apenas ajustes ativos (não reprovados)
        sql = text("""
            SELECT * FROM "Dre_Schema"."Ajustes_Razao" 
            WHERE "Status" != 'Reprovado' AND "Invalido" = false
        """)
        rows = self.session.execute(sql).fetchall()
        
        edicoes = {}
        # Não precisamos retornar 'inclusoes' aqui para o Grid, 
        # pois elas virão via SQL UNION na query principal.
        # Mas mantemos a lógica caso precise em outros lugares.
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

    def get_ordenamento(self):
        sql = text("SELECT id_referencia, tipo_no, ordem FROM \"Dre_Schema\".\"DRE_Ordenamento\" WHERE contexto_pai = 'root'")
        rows = self.session.execute(sql).fetchall()
        return {f"{r.tipo_no}:{r.id_referencia}": r.ordem for r in rows}

    # =========================================================================
    # --- MÉTODOS DO RELATÓRIO (DRE / RENTABILIDADE) ---
    # =========================================================================

    def processar_relatorio(self, filtro_origem='Consolidado', agrupar_por_cc=False):
        """
        Processa DRE Gerencial Híbrida (Estrutura + Dados + Ajustes).
        Lógica: SEMPRE aplica os ajustes (Edições e Inclusões) sobre os dados base.
        """
        # 1. Carrega Estruturas e Ajustes
        tree_map, definitions = self.get_estrutura_hierarquia()
        ajustes_edicao, ajustes_inclusao = self.get_ajustes_map() # Já traz filtrado por validade/status
        ordem_map = self.get_ordenamento()
        
        # 2. Mapa de Títulos para o Esqueleto (Configuração)
        sql_nomes = text('SELECT DISTINCT "Conta", "Título Conta" FROM "Dre_Schema"."Razao_Dados_Consolidado"')
        res_nomes = self.session.execute(sql_nomes).fetchall()
        mapa_titulos = {row[0]: row[1] for row in res_nomes}

        aggregated_data = {} 

        # --- FUNÇÃO INTERNA: Processa uma linha (seja do banco ou do ajuste) ---
        def process_row(origem, conta, titulo, data, saldo, cc_original_str, row_hash=None, is_skeleton=False, forced_match=None):
            
            # A. APLICAÇÃO DE EDIÇÕES (Overrides)
            # Se a linha tem um hash (vem do banco) e está no mapa de edições:
            if not is_skeleton and row_hash and row_hash in ajustes_edicao:
                adj = ajustes_edicao[row_hash]
                
                # Se o ajuste invalida a linha, paramos aqui (ela não entra na soma)
                if adj.Invalido: return 
                
                # Sobrescreve dados com o que está no ajuste
                origem = adj.Origem or origem
                conta = adj.Conta or conta
                titulo = adj.Titulo_Conta or titulo
                cc_original_str = str(adj.Centro_Custo) if adj.Centro_Custo else cc_original_str
                data = adj.Data or data
                
                # Regra visual de Não Operacional
                if adj.Is_Nao_Operacional:
                    conta = '00000000000'
                    titulo = 'Não Operacionais'
                
                # Recalcula o saldo baseado no ajuste
                if adj.Exibir_Saldo:
                    saldo = (float(adj.Debito or 0) - float(adj.Credito or 0))
                else:
                    saldo = 0.0

            # B. ENCONTRA A REGRA NA ÁRVORE (De/Para)
            match = forced_match
            if not match:
                rules = definitions.get(conta, [])
                if not rules: return # Conta sem vínculo na DRE é ignorada
                
                # Tenta match específico por Centro de Custo
                if cc_original_str:
                    cc_int = None
                    try: 
                        cc_int = int(''.join(filter(str.isdigit, str(cc_original_str))))
                    except: pass
                    
                    if cc_int is not None:
                        for rule in rules:
                            if rule.CC_Alvo is not None and cc_int == rule.CC_Alvo:
                                match = rule; break
                
                # Se não achou regra por CC, usa a regra genérica da conta
                if not match: 
                    match = rules[0]
            
            if not match: return

            # C. DEFINIÇÃO DA CHAVE DE AGRUPAMENTO
            tipo_cc = match.Tipo_Principal or 'Outros'
            root_virtual_id = match.Raiz_No_Virtual_Id
            caminho = match.full_path or 'Não Classificado'
            
            # Define Ordem de Exibição
            ordem = 999
            if root_virtual_id:
                ordem = ordem_map.get(f"virtual:{root_virtual_id}", 999)
            elif match.Is_Root_Group:
                if match.Id_Hierarquia:
                    ordem = ordem_map.get(f"subgrupo:{match.Id_Hierarquia}") or 0
            else:
                ordem = ordem_map.get(f"tipo_cc:{tipo_cc}", 999)

            # Labels para o Relatório
            conta_display = match.Nome_Personalizado_Def if match.Nome_Personalizado_Def else conta
            titulo_para_exibicao = match.Nome_Personalizado_Def if match.Nome_Personalizado_Def else titulo
            
            # Chave única da linha no DRE
            group_key = (tipo_cc, root_virtual_id, caminho, titulo_para_exibicao, conta_display)
            if agrupar_por_cc: 
                group_key = group_key + (match.Raiz_Centro_Custo_Nome,)

            # D. INICIALIZAÇÃO NO DICIONÁRIO (Se primeira vez)
            if group_key not in aggregated_data:
                item = {
                    'origem': origem, 'Conta': conta_display, 'Titulo_Conta': titulo_para_exibicao,
                    'Tipo_CC': tipo_cc, 'Root_Virtual_Id': root_virtual_id, 'Caminho_Subgrupos': caminho, 
                    'ordem_prioridade': ordem, 'Total_Ano': 0.0
                }
                for m in self.meses[:-1]: item[m] = 0.0 # Inicializa Jan a Dez com 0
                if agrupar_por_cc: item['Nome_CC'] = match.Raiz_Centro_Custo_Nome
                aggregated_data[group_key] = item

            # E. ACUMULAÇÃO DE VALORES (Soma)
            if not is_skeleton and data:
                try:
                    mes_nome = self.meses[data.month - 1]
                    # DRE inverte sinal: No banco, Crédito é positivo (Receita). 
                    # Se você quer ver Receita positiva na DRE, multiplique por -1 se a lógica contábil for C+ D-.
                    # Ajuste conforme sua regra de sinal de exibição:
                    val_inv = saldo * -1 
                    
                    aggregated_data[group_key][mes_nome] += val_inv
                    aggregated_data[group_key]['Total_Ano'] += val_inv
                except: pass

        # ---------------------------------------------------------------------
        # EXECUÇÃO DO PROCESSAMENTO
        # ---------------------------------------------------------------------

        # 1. Gera Esqueleto (Linhas configuradas que devem aparecer mesmo zeradas)
        for conta_def, lista_regras in definitions.items():
            titulo_conta = mapa_titulos.get(conta_def, "Conta Configurada")
            for regra in lista_regras:
                process_row("Config", conta_def, titulo_conta, None, 0.0, None, None, is_skeleton=True, forced_match=regra)

        # 2. Busca Dados do Razão (Banco de Dados)
        where_origem = ""
        params_sql = {}
        if filtro_origem == 'FARMA': 
            where_origem = "WHERE \"origem\" = 'FARMA'"
        elif filtro_origem == 'FARMADIST': 
            where_origem = "WHERE \"origem\" = 'FARMADIST'"
        else: 
            where_origem = "WHERE \"origem\" IN ('FARMA', 'FARMADIST')"
        
        sql_raw = text(f"""
            SELECT "origem", "Conta", "Título Conta", "Data", "Numero", "Centro de Custo", "Saldo", "Filial", "Item", "Debito", "Credito"
            FROM "Dre_Schema"."Razao_Dados_Consolidado" {where_origem}
        """)
        
        raw_rows = self.session.execute(sql_raw).fetchall()

        # Processa cada linha do banco (verificando se tem edição)
        for row in raw_rows:
            process_row(
                row.origem, row.Conta, getattr(row, 'Título Conta'), row.Data, row.Saldo, 
                getattr(row, 'Centro de Custo'), self._gerar_hash_linha(row), is_skeleton=False
            )

        # 3. Processa INCLUSÕES (Linhas novas criadas via Ajustes ou Intergrupo)
        for adj in ajustes_inclusao:
            # Filtro de Origem nas Inclusões
            if filtro_origem != 'Consolidado' and adj.Origem != filtro_origem:
                continue

            if not adj.Invalido:
                # Calcula saldo do ajuste
                saldo_adj = (float(adj.Debito or 0) - float(adj.Credito or 0)) if adj.Exibir_Saldo else 0.0
                
                # Tratamento Não Operacional
                c = '00000000000' if adj.Is_Nao_Operacional else adj.Conta
                t = 'Não Operacionais' if adj.Is_Nao_Operacional else adj.Titulo_Conta
                
                process_row(
                    adj.Origem, c, t, adj.Data, saldo_adj, str(adj.Centro_Custo), 
                    None, is_skeleton=False
                )

        # 4. Finalização e Ordenação
        final_list = list(aggregated_data.values())
        if agrupar_por_cc: 
            final_list.sort(key=lambda x: (x['ordem_prioridade'], x['Tipo_CC'], x['Nome_CC'] or ''))
        else: 
            final_list.sort(key=lambda x: x['ordem_prioridade'])
        
        return final_list

    def calcular_nos_virtuais(self, data_rows):
        """Calcula fórmulas (EBITDA, Lucro Líquido, etc)."""
        memoria = defaultdict(lambda: {m: 0.0 for m in self.meses})
        
        # Popula memória com dados processados
        for row in data_rows:
            tipo = str(row['Tipo_CC']).strip()
            virt_id = row.get('Root_Virtual_Id')
            keys_to_update = [f"tipo_cc:{tipo}"]
            if virt_id:
                keys_to_update.append(f"no_virtual:{virt_id}")
                keys_to_update.append(f"no_virtual:{tipo}") # Backup por nome

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
                        # Fallback por nome se ID não achou (ex: LEGADO)
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
                    
                    # Atualiza memória para fórmulas em cadeia
                    memoria[f"no_virtual:{form.Id}"][mes] = final_val
                    memoria[f"no_virtual:{form.Nome}"][mes] = final_val

                novas_linhas.append(nova_linha)
            except Exception as e:
                print(f"Erro ao calcular fórmula {form.Nome}: {e}")

        todos = data_rows + novas_linhas
        todos.sort(key=lambda x: x.get('ordem_prioridade', 999))
        return todos

    # =========================================================================
    # --- MÉTODOS DO RAZÃO (GRID) - CORRIGIDO ---
    # =========================================================================

    def get_razao_dados(self, page=1, per_page=50, search_term='', view_type='original'):
        """
        Busca dados do Razão com paginação.
        Se view_type='adjusted', faz um UNION no SQL com a tabela de ajustes 
        para trazer as inclusões/intergrupos como linhas nativas.
        """
        offset = (page - 1) * per_page
        params = {'limit': per_page, 'offset': offset}
        
        # Filtros de Busca
        filter_snippet = ""
        filter_snippet_ajuste = ""
        
        if search_term:
            # Filtro para a tabela principal (Razão)
            filter_snippet = """
                AND (
                    "Conta"::TEXT ILIKE :termo OR "Título Conta" ILIKE :termo
                    OR "Descricao" ILIKE :termo OR "Numero"::TEXT ILIKE :termo
                    OR "origem" ILIKE :termo
                )
            """
            # Filtro para a tabela de Ajustes (Nomes de colunas podem variar levemente)
            filter_snippet_ajuste = """
                AND (
                    "Conta"::TEXT ILIKE :termo OR "Titulo_Conta" ILIKE :termo
                    OR "Descricao" ILIKE :termo OR "Numero"::TEXT ILIKE :termo
                    OR "Origem" ILIKE :termo
                )
            """
            params['termo'] = f"%{search_term}%"

        # --- QUERY SQL PRINCIPAL ---
        if view_type == 'adjusted':
            # MODO AJUSTADO: Razão + Inclusões (Union)
            # Nota: Mapeamos explicitamente as colunas da tabela de Ajustes para bater com a View
            sql_query = f"""
                SELECT * FROM (
                    -- PARTE 1: DADOS ORIGINAIS DO RAZÃO
                    SELECT 
                        'RAZAO' as source_type,
                        "origem", 
                        "Conta", 
                        "Título Conta", 
                        "Data", 
                        "Numero", 
                        "Descricao", 
                        "Contra Partida - Credito", 
                        CAST("Filial" AS TEXT) as "Filial", 
                        CAST("Centro de Custo" AS TEXT) as "Centro de Custo", 
                        "Item", 
                        COALESCE("Debito", 0) as "Debito", 
                        COALESCE("Credito", 0) as "Credito", 
                        "Saldo",
                        "Nome do CC",
                        NULL as "Hash_Ajuste_ID" -- Placeholder
                    FROM "Dre_Schema"."Razao_Dados_Consolidado" 
                    WHERE 1=1 {filter_snippet}
                    
                    UNION ALL
                    
                    -- PARTE 2: INCLUSÕES E INTERGRUPO (Tabela de Ajustes)
                    SELECT 
                        'AJUSTE' as source_type,
                        "Origem" as "origem", 
                        "Conta", 
                        "Titulo_Conta" as "Título Conta", 
                        "Data", 
                        "Numero", 
                        "Descricao", 
                        "Contra_Partida" as "Contra Partida - Credito", 
                        "Filial", 
                        "Centro_Custo" as "Centro de Custo", 
                        "Item", 
                        CASE WHEN "Exibir_Saldo" THEN COALESCE("Debito", 0) ELSE 0 END as "Debito", 
                        CASE WHEN "Exibir_Saldo" THEN COALESCE("Credito", 0) ELSE 0 END as "Credito", 
                        CASE WHEN "Exibir_Saldo" THEN (COALESCE("Debito", 0) - COALESCE("Credito", 0)) ELSE 0 END as "Saldo",
                        NULL as "Nome do CC",
                        CAST("Id" AS TEXT) as "Hash_Ajuste_ID"
                    FROM "Dre_Schema"."Ajustes_Razao" 
                    WHERE "Tipo_Operacao" IN ('INCLUSAO', 'INTERGRUPO_AUTO') 
                      AND "Status" != 'Reprovado' 
                      AND "Invalido" = false
                      {filter_snippet_ajuste}
                      
                ) AS uniao_dados 
                ORDER BY "Data" DESC, "Conta" ASC, "Numero" ASC
                LIMIT :limit OFFSET :offset
            """
            
            # Count também precisa do Union para a paginação bater
            sql_count = f"""
                SELECT SUM(cnt) FROM (
                    SELECT COUNT(*) as cnt FROM "Dre_Schema"."Razao_Dados_Consolidado" WHERE 1=1 {filter_snippet}
                    UNION ALL
                    SELECT COUNT(*) as cnt FROM "Dre_Schema"."Ajustes_Razao" 
                    WHERE "Tipo_Operacao" IN ('INCLUSAO', 'INTERGRUPO_AUTO') 
                      AND "Status" != 'Reprovado' 
                      AND "Invalido" = false {filter_snippet_ajuste}
                ) as total_tbl
            """
        else:
            # MODO ORIGINAL: Apenas View
            sql_query = f"""
                SELECT 
                    'RAZAO' as source_type,
                    "origem", "Conta", "Título Conta", "Data", "Numero", "Descricao", 
                    "Contra Partida - Credito", "Filial", "Centro de Custo", "Item", 
                    "Debito", "Credito", "Saldo", "Nome do CC", NULL as "Hash_Ajuste_ID"
                FROM "Dre_Schema"."Razao_Dados_Consolidado" 
                WHERE 1=1 {filter_snippet} 
                ORDER BY "Data" DESC, "Conta" ASC, "Numero" ASC
                LIMIT :limit OFFSET :offset
            """
            sql_count = f'SELECT COUNT(*) FROM "Dre_Schema"."Razao_Dados_Consolidado" WHERE 1=1 {filter_snippet}'

        # Executa Count
        total_registros = self.session.execute(text(sql_count), params).scalar() or 0
        total_paginas = (total_registros // per_page) + (1 if total_registros % per_page > 0 else 0)
        
        # Executa Busca de Dados
        rows = self.session.execute(text(sql_query), params).fetchall()
        
        result_list = []
        
        # Carrega mapa de edições (Overrides) apenas se estiver no modo ajustado
        ajustes_edicao = {}
        if view_type == 'adjusted': 
            ajustes_edicao, _ = self.get_ajustes_map()

        for i, r in enumerate(rows, 1):
            # Cria o objeto base
            row_dict = {
                'id': i + offset, 
                'origem': r.origem, 
                'conta': r.Conta, 
                'titulo_conta': getattr(r, 'Título Conta', ''), 
                'data': r.Data.isoformat() if r.Data else None, 
                'numero': r.Numero, 
                'descricao': r.Descricao, 
                'centro_custo': getattr(r, 'Centro de Custo', ''),
                'filial': getattr(r, 'Filial', ''),
                'item': getattr(r, 'Item', ''),
                'debito': float(r.Debito or 0), 
                'credito': float(r.Credito or 0), 
                'saldo': float(r.Saldo or 0), 
                'is_ajustado': False
            }
            
            # CENÁRIO 1: Linha é uma INCLUSÃO/INTERGRUPO (Vem do UNION 'AJUSTE')
            if hasattr(r, 'source_type') and r.source_type == 'AJUSTE':
                row_dict['is_ajustado'] = True
                row_dict['origem'] = f"{r.origem} (NOVO)" # Marcador visual
                # O ID pode ser o Hash temporário ou ID do ajuste
                row_dict['Hash_ID'] = f"NEW_{r.Hash_Ajuste_ID}" 

            # CENÁRIO 2: Linha é do RAZÃO, mas verificamos se tem EDIÇÃO (Override)
            elif view_type == 'adjusted':
                r_hash = self._gerar_hash_linha(r)
                
                if r_hash in ajustes_edicao:
                    adj = ajustes_edicao[r_hash]
                    
                    # Aplica a edição visualmente na linha
                    if not adj.Invalido:
                        if adj.Exibir_Saldo: 
                            row_dict['saldo'] = float(adj.Debito or 0) - float(adj.Credito or 0)
                            row_dict['debito'] = float(adj.Debito or 0)
                            row_dict['credito'] = float(adj.Credito or 0)
                        else: 
                            row_dict['saldo'] = 0.0
                            row_dict['debito'] = 0.0
                            row_dict['credito'] = 0.0
                        
                        row_dict['is_ajustado'] = True
                        row_dict['origem'] = f"{r.origem} (EDIT)"
                        
                        if adj.Descricao: row_dict['descricao'] = adj.Descricao
                        if adj.Conta: row_dict['conta'] = adj.Conta
                        if adj.Titulo_Conta: row_dict['titulo_conta'] = adj.Titulo_Conta
                        if adj.Centro_Custo: row_dict['centro_custo'] = adj.Centro_Custo
                        if adj.Filial: row_dict['filial'] = adj.Filial

            result_list.append(row_dict)
            
        return {
            'pagina_atual': page, 
            'total_paginas': total_paginas, 
            'total_registros': total_registros, 
            'dados': result_list
        }

    def get_razao_resumo(self, view_type='original'):
        """
        Retorna o sumário (totais) considerando o modo ajustado se solicitado.
        """
        if view_type == 'adjusted':
            sql = text("""
                SELECT 
                    SUM(cnt), SUM(deb), SUM(cred), SUM(sal)
                FROM (
                    SELECT COUNT(*) as cnt, SUM("Debito") as deb, SUM("Credito") as cred, SUM("Saldo") as sal 
                    FROM "Dre_Schema"."Razao_Dados_Consolidado"
                    
                    UNION ALL
                    
                    SELECT COUNT(*) as cnt, SUM("Debito") as deb, SUM("Credito") as cred, SUM("Debito" - "Credito") as sal
                    FROM "Dre_Schema"."Ajustes_Razao"
                    WHERE "Tipo_Operacao" IN ('INCLUSAO', 'INTERGRUPO_AUTO') 
                      AND "Status" != 'Reprovado' AND "Invalido" = false
                ) as tbl_union
            """)
        else:
            sql = text("""
                SELECT COUNT(*), SUM("Debito"), SUM("Credito"), SUM("Saldo") 
                FROM "Dre_Schema"."Razao_Dados_Consolidado"
            """)
            
        base = self.session.execute(sql).fetchone()
        
        return {
            'total_registros': base[0] or 0, 
            'total_debito': float(base[1] or 0), 
            'total_credito': float(base[2] or 0), 
            'saldo_total': float(base[3] or 0)
        }

    def export_razao_full(self, search_term='', view_type='original'):
        """
        Busca TODOS os registros para exportação Excel.
        Utiliza a mesma lógica de UNION para garantir que as inclusões apareçam.
        """
        params = {}
        filter_snippet = ""
        filter_snippet_ajuste = ""
        
        if search_term:
            params['termo'] = f"%{search_term}%"
            filter_snippet = """
                AND (
                    "Conta"::TEXT ILIKE :termo OR "Título Conta" ILIKE :termo
                    OR "Descricao" ILIKE :termo OR "Numero"::TEXT ILIKE :termo
                    OR "origem" ILIKE :termo
                )
            """
            filter_snippet_ajuste = """
                AND (
                    "Conta"::TEXT ILIKE :termo OR "Titulo_Conta" ILIKE :termo
                    OR "Descricao" ILIKE :termo OR "Numero"::TEXT ILIKE :termo
                    OR "Origem" ILIKE :termo
                )
            """

        # Constrói a Query
        if view_type == 'adjusted':
            sql = text(f"""
                SELECT * FROM (
                    SELECT 
                        'RAZAO' as source_type,
                        "origem", "Conta", "Título Conta", "Data", "Numero", 
                        "Descricao", "Contra Partida - Credito" as "Contra Partida", 
                        CAST("Filial" AS TEXT) as "Filial", 
                        CAST("Centro de Custo" AS TEXT) as "Centro de Custo", 
                        "Item", "Cod Cl. Valor",
                        "Debito", "Credito", "Saldo"
                    FROM "Dre_Schema"."Razao_Dados_Consolidado"
                    WHERE 1=1 {filter_snippet}
                    
                    UNION ALL
                    
                    SELECT 
                        'AJUSTE' as source_type,
                        "Origem", "Conta", "Titulo_Conta", "Data", "Numero", 
                        "Descricao", "Contra_Partida", 
                        "Filial", "Centro_Custo", "Item", "Cod_Cl_Valor",
                        CASE WHEN "Exibir_Saldo" THEN COALESCE("Debito", 0) ELSE 0 END, 
                        CASE WHEN "Exibir_Saldo" THEN COALESCE("Credito", 0) ELSE 0 END,
                        CASE WHEN "Exibir_Saldo" THEN (COALESCE("Debito", 0) - COALESCE("Credito", 0)) ELSE 0 END
                    FROM "Dre_Schema"."Ajustes_Razao"
                    WHERE "Tipo_Operacao" IN ('INCLUSAO', 'INTERGRUPO_AUTO') 
                      AND "Status" != 'Reprovado' AND "Invalido" = false {filter_snippet_ajuste}
                ) as tbl_final
                ORDER BY "Data", "Conta"
            """)
        else:
            sql = text(f"""
                SELECT 
                    'RAZAO' as source_type,
                    "origem", "Conta", "Título Conta", "Data", "Numero", 
                    "Descricao", "Contra Partida - Credito" as "Contra Partida", 
                    "Filial", "Centro de Custo", "Item", "Cod Cl. Valor", 
                    "Debito", "Credito", "Saldo"
                FROM "Dre_Schema"."Razao_Dados_Consolidado"
                WHERE 1=1 {filter_snippet}
                ORDER BY "Data", "Conta"
            """)
            
        rows = self.session.execute(sql, params).fetchall()
        
        # Mapa de Edições (Apenas se ajustado)
        ajustes_edicao = {}
        if view_type == 'adjusted':
            ajustes_edicao, _ = self.get_ajustes_map()

        final_data = []

        for r in rows:
            # Converte row do SQLAlchemy para dict
            row_dict = dict(r._mapping)
            
            # Se for linha de AJUSTE (Inclusão), marcamos e adicionamos direto
            if row_dict.get('source_type') == 'AJUSTE':
                row_dict['origem'] = f"{row_dict['origem']} (NOVO)"
                del row_dict['source_type'] # Limpa coluna auxiliar
                final_data.append(row_dict)
                continue
            
            # Se for linha do RAZÃO, verificamos Override
            del row_dict['source_type'] # Limpa coluna auxiliar
            
            if view_type == 'adjusted':
                # Precisamos gerar o hash para ver se tem edição
                # Nota: _gerar_hash_linha espera um objeto com atributos, 
                # aqui 'r' é um Row do SQLAlchemy que permite acesso por atributo, então funciona.
                r_hash = self._gerar_hash_linha(r)
                
                if r_hash in ajustes_edicao:
                    adj = ajustes_edicao[r_hash]
                    if not adj.Invalido:
                        row_dict['origem'] = f"{row_dict['origem']} (AJUSTE)"
                        
                        # Sobrescreve campos
                        if adj.Conta: row_dict['Conta'] = adj.Conta
                        if adj.Titulo_Conta: row_dict['Título Conta'] = adj.Titulo_Conta
                        if adj.Descricao: row_dict['Descricao'] = adj.Descricao
                        if adj.Centro_Custo: row_dict['Centro de Custo'] = adj.Centro_Custo
                        
                        d = float(adj.Debito or 0)
                        c = float(adj.Credito or 0)
                        if adj.Exibir_Saldo:
                            row_dict['Debito'] = d
                            row_dict['Credito'] = c
                            row_dict['Saldo'] = d - c
                        else:
                            row_dict['Debito'] = 0
                            row_dict['Credito'] = 0
                            row_dict['Saldo'] = 0

            final_data.append(row_dict)
        
        return final_data