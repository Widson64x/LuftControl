"""
Routes/Reports.py
Rotas para Relatórios de Rentabilidade e Razão Contábil
VERSÃO CORRIGIDA - Consulta SQL dinâmica para evitar problemas de mapeamento ORM
"""

from flask import Blueprint, jsonify, request, current_app, abort, render_template
from flask_login import login_required 
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func, or_, String, text
import json


from Db.Connections import get_postgres_engine
from Helpers.Security import requires_permission

reports_bp = Blueprint('Reports', __name__) 


def get_pg_session():
    """Cria e retorna uma sessão do PostgreSQL"""
    engine = get_postgres_engine()
    Session = sessionmaker(bind=engine)
    return Session()


@reports_bp.route('/', methods=['GET']) 
@login_required 
def PaginaRelatorios():
    """Renderiza a página principal de relatórios"""
    return render_template('MENUS/Relatórios.html')


@reports_bp.route('/RelatorioRazao/Dados', methods=['GET']) 
@login_required 
def RelatorioRazaoDados():
    """
    Retorna dados paginados do Razão Consolidado com filtro de busca.
    VERSÃO CORRIGIDA - Novas chaves atualizadas
    """
    session = None
    try: 
        session = get_pg_session()
        
        # Parâmetros
        page = int(request.args.get('page', 1))
        search_term = request.args.get('search', '').strip()
        per_page = 1000
        offset = (page - 1) * per_page
        
        # Monta a query SQL dinâmica
        base_sql = """
            SELECT 
                "origem",
                "Conta",
                "Título Conta",
                "Data",
                "Numero",
                "Descricao",
                "Contra Partida - Credito",
                "Filial",
                "Centro de Custo",
                "Item",
                "Cod Cl. Valor",
                "Debito",
                "Credito",
                "Saldo",
                "Mes",
                "CC",
                "Nome do CC",
                "Cliente",
                "Filial Cliente",
                "Chv_Mes_Conta",
                "Chv_Mes_Conta_CC",
                "Chv_Mes_NomeCC_Conta",
                "Chv_Mes_NomeCC_Conta_CC",
                "Chv_Conta_Formatada",
                "Chv_Mes_NomeCC_Conta_CodCC"
            FROM "Dre_Schema"."Razao_Dados_Consolidado"
        """
        
        count_sql = 'SELECT COUNT(*) FROM "Dre_Schema"."Razao_Dados_Consolidado"'
        
        # Filtro de busca
        where_clause = ""
        params = {}
        
        if search_term:
            where_clause = """
                WHERE (
                    "Conta"::TEXT ILIKE :termo 
                    OR "Título Conta" ILIKE :termo
                    OR "Descricao" ILIKE :termo
                    OR "Numero"::TEXT ILIKE :termo
                    OR "origem" ILIKE :termo
                    OR "Nome do CC" ILIKE :termo
                    OR "Cliente" ILIKE :termo
                    OR "Filial Cliente" ILIKE :termo
                    OR "CC"::TEXT ILIKE :termo
                    OR "Debito"::TEXT ILIKE :termo
                    OR "Credito"::TEXT ILIKE :termo
                )
            """
            params['termo'] = f"%{search_term}%"
        
        # Query de contagem
        count_result = session.execute(
            text(count_sql + (" " + where_clause if where_clause else "")), 
            params
        ).scalar()
        
        total_registros = count_result or 0
        total_paginas = (total_registros // per_page) + (1 if total_registros % per_page > 0 else 0)

        # Query de dados
        data_sql = base_sql + where_clause + """
            ORDER BY "Data", "Conta", "Numero"
            LIMIT :limit OFFSET :offset
        """
        params['limit'] = per_page
        params['offset'] = offset
        
        result = session.execute(text(data_sql), params)
        rows = result.fetchall()
        
        # Formata resultado
        result_list = []
        for i, r in enumerate(rows, 1):
            item = {
                'id': i + offset,
                'origem': r[0],
                'conta': r[1], 
                'titulo_conta': r[2],
                'data': r[3].isoformat() if r[3] else None,
                'numero': r[4],
                'descricao': r[5],
                'contra_partida_credito': r[6],
                'filial_id': r[7],
                'centro_custo_id': r[8],
                'item': r[9],
                'cod_cl_valor': r[10],
                'debito': float(r[11]) if r[11] else 0.0,
                'credito': float(r[12]) if r[12] else 0.0,
                'saldo': float(r[13]) if r[13] else 0.0,
                'mes': r[14],
                'cc_cod': r[15],
                'nome_cc': r[16],
                'cliente': r[17],
                'filial_cliente': r[18],
                'chv_mes_conta': r[19],
                'chv_mes_conta_cc': r[20],
                'chv_mes_nomecc_conta': r[21],
                'chv_mes_nomecc_conta_cc': r[22],
                'chv_conta_formatada': r[23],
                'chv_mes_nomecc_conta_codcc': r[24]
            }
            result_list.append(item)
        
        return jsonify({
            'pagina_atual': page,
            'total_paginas': total_paginas,
            'total_registros': total_registros,
            'termo_busca': search_term,
            'dados': result_list
        }), 200
        
    except Exception as e: 
        current_app.logger.error(f"Erro no RelatorioRazaoDados: {e}")
        abort(500, description=f"Erro: {str(e)}")
    finally:
        if session: 
            session.close()

@reports_bp.route('/RelatorioRazao/Resumo', methods=['GET']) 
@login_required 
def RelatorioRazaoResumo():
    """
    Retorna resumo estatístico do Razão Consolidado.
    """
    session = None
    try: 
        session = get_pg_session()
        
        sql = text("""
            SELECT 
                COUNT(*) as total_registros,
                COALESCE(SUM("Debito"), 0) as total_debito,
                COALESCE(SUM("Credito"), 0) as total_credito,
                COALESCE(SUM("Saldo"), 0) as saldo_total
            FROM "Dre_Schema"."Razao_Dados_Consolidado"
        """)
        
        result = session.execute(sql).fetchone()
        
        return jsonify({
            'total_registros': result[0] or 0,
            'total_debito': float(result[1]) if result[1] else 0.0,
            'total_credito': float(result[2]) if result[2] else 0.0,
            'saldo_total': float(result[3]) if result[3] else 0.0
        }), 200
        
    except Exception as e: 
        abort(500, description=str(e))
    finally:
        if session: 
            session.close()

@reports_bp.route('/RelatorioRazao/Rentabilidade', methods=['GET'])
@login_required
def RelatorioRentabilidade():
    """
    DRE Gerencial Híbrida: SQL busca dados reais (com Ajustes) + Python calcula fórmulas.
    REGRA DEFINITIVA: 
    1. Se 'Is_Nao_Operacional' for TRUE, a Conta vira '00000000000' e Título 'Não Operacionais' NA ORIGEM.
    2. O JOIN com a árvore (Definicoes) usa essa nova conta para descobrir Grupo, Subgrupo e Ordem automaticamente.
    """
    session = None
    try: 
        session = get_pg_session()
        
        # 1. Filtros
        filtro_origem = request.args.get('origem', 'Consolidado')
        if filtro_origem == 'FARMA': origem_clause = "tca.\"origem\" = 'FARMA'"
        elif filtro_origem == 'FARMADIST': origem_clause = "tca.\"origem\" = 'FARMADIST'"
        else: origem_clause = "tca.\"origem\" IN ('FARMA', 'FARMADIST')"
        
        # 2. SQL
        sql_query = text(f"""
            WITH RECURSIVE 
            TreePath AS (
                SELECT 
                    h."Id", h."Nome", h."Id_Pai", 
                    h."Raiz_Centro_Custo_Codigo", h."Raiz_No_Virtual_Id", 
                    h."Raiz_Centro_Custo_Tipo", h."Raiz_No_Virtual_Nome",
                    CAST(h."Nome" AS TEXT) as full_path
                FROM "Dre_Schema"."DRE_Estrutura_Hierarquia" h
                WHERE h."Id_Pai" IS NULL
                UNION ALL
                SELECT 
                    child."Id", child."Nome", child."Id_Pai", 
                    tp."Raiz_Centro_Custo_Codigo", tp."Raiz_No_Virtual_Id", 
                    tp."Raiz_Centro_Custo_Tipo", tp."Raiz_No_Virtual_Nome",
                    CAST(tp.full_path || '||' || child."Nome" AS TEXT)
                FROM "Dre_Schema"."DRE_Estrutura_Hierarquia" child
                JOIN TreePath tp ON child."Id_Pai" = tp."Id"
            ),
            OrdemRaiz AS (
                SELECT id_referencia, tipo_no, ordem 
                FROM "Dre_Schema"."DRE_Ordenamento" 
                WHERE contexto_pai = 'root'
            ),
            Definicoes AS (
                SELECT 
                    v."Conta_Contabil", tp."Raiz_Centro_Custo_Codigo" as "CC_Alvo",
                    tp."Id" as "Id_Hierarquia", NULL::int as "Id_No_Virtual",
                    NULL::text as "Nome_Personalizado_Def", tp.full_path,
                    COALESCE(tp."Raiz_Centro_Custo_Tipo", tp."Raiz_No_Virtual_Nome") as "Raiz_Centro_Custo_Tipo",
                    tp."Raiz_No_Virtual_Id" as "Root_Virtual_Id"
                FROM "Dre_Schema"."DRE_Estrutura_Conta_Vinculo" v
                JOIN TreePath tp ON v."Id_Hierarquia" = tp."Id"
                UNION ALL
                SELECT 
                    p."Conta_Contabil", tp."Raiz_Centro_Custo_Codigo", p."Id_Hierarquia",
                    NULL::int, p."Nome_Personalizado", tp.full_path,
                    COALESCE(tp."Raiz_Centro_Custo_Tipo", tp."Raiz_No_Virtual_Nome"),
                    tp."Raiz_No_Virtual_Id"
                FROM "Dre_Schema"."DRE_Estrutura_Conta_Personalizada" p
                JOIN TreePath tp ON p."Id_Hierarquia" = tp."Id"
                WHERE p."Id_Hierarquia" IS NOT NULL
                UNION ALL
                SELECT 
                    p."Conta_Contabil", NULL::int, NULL::int, p."Id_No_Virtual",
                    p."Nome_Personalizado", 'Direto', nv."Nome", nv."Id"
                FROM "Dre_Schema"."DRE_Estrutura_Conta_Personalizada" p
                JOIN "Dre_Schema"."DRE_Estrutura_No_Virtual" nv ON p."Id_No_Virtual" = nv."Id"
                WHERE p."Id_No_Virtual" IS NOT NULL
            ),
            DadosUnificados AS (
                -- 1. Dados Originais + Edições (Hash Padronizado)
                SELECT
                    COALESCE(adj."Origem", base."origem") as "origem",
                    
                    -- AQUI A MÁGICA: Se for não operacional, forçamos a conta 00000000000
                    CASE 
                        WHEN COALESCE(adj."Is_Nao_Operacional", FALSE) = TRUE THEN '00000000000'
                        ELSE COALESCE(adj."Conta", base."Conta") 
                    END as "Conta",
                    
                    CASE 
                        WHEN COALESCE(adj."Is_Nao_Operacional", FALSE) = TRUE THEN 'Não Operacionais'
                        ELSE COALESCE(adj."Titulo_Conta", base."Título Conta") 
                    END as "Titulo_Conta",
                    
                    COALESCE(adj."Centro_Custo", CAST(base."Centro de Custo" AS TEXT)) as "Centro de Custo",
                    COALESCE(adj."Data", base."Data") as "Data",
                    
                    CASE
                        WHEN adj."Id" IS NOT NULL THEN
                            CASE WHEN adj."Exibir_Saldo" = TRUE THEN (COALESCE(adj."Debito",0) - COALESCE(adj."Credito",0)) ELSE 0.0 END
                        ELSE base."Saldo"
                    END as "Saldo",
                    
                    COALESCE(adj."Is_Nao_Operacional", FALSE) as "Is_Nao_Operacional"
                    
                FROM "Dre_Schema"."Razao_Dados_Consolidado" base
                LEFT JOIN "Dre_Schema"."Ajustes_Razao" adj
                    ON adj."Hash_Linha_Original" = md5(
                        COALESCE(TRIM(CAST(base."origem" AS TEXT)), 'None') || '-' ||
                        COALESCE(TRIM(CAST(base."Filial" AS TEXT)), 'None') || '-' ||
                        COALESCE(TRIM(CAST(base."Numero" AS TEXT)), 'None') || '-' ||
                        COALESCE(TRIM(CAST(base."Item" AS TEXT)), 'None') || '-' ||
                        COALESCE(TRIM(CAST(base."Conta" AS TEXT)), 'None') || '-' ||
                        COALESCE(TO_CHAR(base."Data", 'YYYY-MM-DD'), 'None')
                    )
                    AND adj."Tipo_Operacao" = 'EDICAO'
                    AND adj."Status" != 'Reprovado' 
                    
                UNION ALL
                
                -- 2. Inclusões
                SELECT
                    "Origem", 
                    
                    -- AQUI TAMBÉM: Inclusões manuais seguem a mesma regra
                    CASE 
                        WHEN "Is_Nao_Operacional" = TRUE THEN '00000000000'
                        ELSE "Conta" 
                    END,
                    
                    CASE 
                        WHEN "Is_Nao_Operacional" = TRUE THEN 'Não Operacionais'
                        ELSE "Titulo_Conta" 
                    END,
                    
                    "Centro_Custo", "Data",
                    CASE WHEN "Exibir_Saldo" = TRUE THEN (COALESCE("Debito",0) - COALESCE("Credito",0)) ELSE 0.0 END as "Saldo",
                    "Is_Nao_Operacional"
                FROM "Dre_Schema"."Ajustes_Razao"
                WHERE "Tipo_Operacao" = 'INCLUSAO' AND "Status" != 'Reprovado'
            ),
            DadosBrutos AS (
                SELECT 
                    tca."origem", 
                    tca."Conta", -- Agora já vem tratado como '00000000000' se necessário
                    
                    -- Prioriza nome personalizado da árvore (se houver), senão usa o título (que já pode ser 'Não Operacionais')
                    COALESCE(def."Nome_Personalizado_Def", tca."Titulo_Conta") AS "Titulo_Final",
                    
                    -- O INNER JOIN abaixo vai pegar a "Definição" da conta '00000000000'
                    -- Logo, ele vai trazer o Grupo/Virtual/Ordem que você configurou na árvore para essa conta
                    COALESCE(def."Raiz_Centro_Custo_Tipo", 'Outros') AS "Tipo_CC",
                    COALESCE(def.full_path, 'Não Classificado') AS "Caminho_Subgrupos",
                    def."Root_Virtual_Id",
                    COALESCE(ord.ordem, 999) as ordem_base,
                    
                    tca."Saldo", 
                    tca."Data"
                    
                FROM DadosUnificados tca
                -- O JOIN agora acontece com a conta transformada.
                -- Se virou '00000000000', ele busca a regra da '00000000000'
                INNER JOIN Definicoes def 
                    ON tca."Conta" = def."Conta_Contabil"
                    AND (
                        (def."CC_Alvo" IS NOT NULL AND CAST(NULLIF(regexp_replace(tca."Centro de Custo", '[^0-9]', '', 'g'), '') AS INTEGER) = def."CC_Alvo") 
                        OR (def."CC_Alvo" IS NULL)
                    )
                LEFT JOIN OrdemRaiz ord 
                    ON (
                        (ord.tipo_no = 'tipo_cc' AND ord.id_referencia = def."Raiz_Centro_Custo_Tipo") 
                        OR 
                        (ord.tipo_no = 'virtual' AND ord.id_referencia = CAST(def."Root_Virtual_Id" AS TEXT))
                    )
                WHERE {origem_clause}
            )
            SELECT 
                MAX("origem") as "origem",
                MAX("Conta") as "Conta",
                "Titulo_Final" as "Titulo_Conta",
                "Tipo_CC",
                "Root_Virtual_Id",
                "Caminho_Subgrupos",
                (COALESCE(SUM("Saldo"), 0.0) * -1) AS "Total_Ano",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 1 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Jan",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 2 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Fev",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 3 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Mar",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 4 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Abr",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 5 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Mai",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 6 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Jun",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 7 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Jul",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 8 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Ago",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 9 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Set",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 10 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Out",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 11 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Nov",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 12 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Dez",
                MIN("ordem_base") as ordem_prioridade
            FROM DadosBrutos
            GROUP BY "Tipo_CC", "Root_Virtual_Id", "Caminho_Subgrupos", "Titulo_Final", "Conta"
            ORDER BY ordem_prioridade ASC;
        """)

        result = session.execute(sql_query)
        data_rows = [dict(row._mapping) for row in result]

        # 3. MOTOR DE CÁLCULO PYTHON
        memoria_calculo = {}
        meses = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez','Total_Ano']
        
        for row in data_rows:
            nome_tipo = str(row['Tipo_CC']).strip()
            key_tipo = f"tipo_cc:{nome_tipo}"
            if key_tipo not in memoria_calculo: memoria_calculo[key_tipo] = {m: 0.0 for m in meses}

            key_virt_id = None
            if row.get('Root_Virtual_Id'):
                key_virt_id = f"no_virtual:{row['Root_Virtual_Id']}"
                if key_virt_id not in memoria_calculo: memoria_calculo[key_virt_id] = {m: 0.0 for m in meses}
                
                nome_virt = str(row['Tipo_CC']).strip()
                key_virt_nome = f"no_virtual:{nome_virt}"
                if key_virt_nome not in memoria_calculo: memoria_calculo[key_virt_nome] = {m: 0.0 for m in meses}

            for m in meses:
                val = float(row.get(m) or 0.0)
                memoria_calculo[key_tipo][m] += val
                if key_virt_id: 
                    memoria_calculo[key_virt_id][m] += val
                    memoria_calculo[f"no_virtual:{str(row['Tipo_CC']).strip()}"][m] += val

        # 4. Fórmulas
        sql_nos_calculados = text("""
            SELECT nv."Id", nv."Nome", nv."Formula_JSON", nv."Formula_Descricao", nv."Estilo_CSS", nv."Tipo_Exibicao", COALESCE(ord.ordem, 999) as ordem_prioridade
            FROM "Dre_Schema"."DRE_Estrutura_No_Virtual" nv
            LEFT JOIN "Dre_Schema"."DRE_Ordenamento" ord ON ord.id_referencia = CAST(nv."Id" AS TEXT) AND ord.contexto_pai = 'root'
            WHERE nv."Is_Calculado" = true
            ORDER BY ordem_prioridade ASC
        """)
        nos_calculados = session.execute(sql_nos_calculados).fetchall()

        for no in nos_calculados:
            if not no.Formula_JSON: continue
            try:
                formula = json.loads(no.Formula_JSON)
                operandos = formula.get('operandos', [])
                operacao = formula.get('operacao', 'soma')
                
                nova_linha = {
                    'origem': 'Calculado',
                    'Conta': f"CALC_{no.Id}",
                    'Titulo_Conta': no.Nome,
                    'Tipo_CC': no.Nome, 
                    'Caminho_Subgrupos': 'Calculado',
                    'ordem_prioridade': no.ordem_prioridade,
                    'Is_Calculado': True,
                    'Estilo_CSS': no.Estilo_CSS,
                    'Tipo_Exibicao': no.Tipo_Exibicao
                }
                
                for mes in meses:
                    valores_ops = []
                    for op in operandos:
                        id_op = str(op['id']).strip()
                        tipo = op['tipo']
                        chave = f"{tipo}:{id_op}"
                        val = memoria_calculo.get(chave, {}).get(mes, 0.0)
                        if val == 0.0 and tipo == 'no_virtual':
                             for k,v in memoria_calculo.items():
                                 if k.lower() == chave.lower(): val = v.get(mes, 0.0); break
                        valores_ops.append(val)
                    
                    res = 0.0
                    if not valores_ops: res = 0.0
                    elif operacao == 'soma': res = sum(valores_ops)
                    elif operacao == 'subtracao': res = valores_ops[0] - sum(valores_ops[1:])
                    elif operacao == 'multiplicacao': 
                        import math
                        res = math.prod(valores_ops)
                    elif operacao == 'divisao': res = valores_ops[1] != 0 and valores_ops[0] / valores_ops[1] or 0.0

                    nova_linha[mes] = res * float(formula.get('multiplicador', 1))

                chave_calc = f"no_virtual:{no.Id}"
                memoria_calculo[chave_calc] = {m: nova_linha[m] for m in meses}
                memoria_calculo[f"no_virtual:{no.Nome}"] = {m: nova_linha[m] for m in meses}
                
                data_rows.append(nova_linha)
            except Exception as e:
                print(f"Erro calculo {no.Nome}: {e}")

        data_rows.sort(key=lambda x: x.get('ordem_prioridade', 999))
        return jsonify(data_rows), 200

    except Exception as e: 
        current_app.logger.error(f"Erro no Relatório Rentabilidade: {e}") 
        abort(500, description=f"Erro SQL/Python: {str(e)}")
    finally:
        if session: session.close()

@reports_bp.route('/RelatorioRazao/RentabilidadePorCC', methods=['GET'])
@login_required
def RelatorioRentabilidadePorCC():
    """
    DRE Gerencial detalhada por CENTRO DE CUSTO.
    INTEGRAÇÃO COM AJUSTES RAZÃO + REGRA NÃO OPERACIONAL (CONTA 00000000000)
    """
    session = None
    try: 
        session = get_pg_session()
        
        filtro_origem = request.args.get('origem', 'Consolidado')
        if filtro_origem == 'FARMA': origem_clause = "tca.\"origem\" = 'FARMA'"
        elif filtro_origem == 'FARMADIST': origem_clause = "tca.\"origem\" = 'FARMADIST'"
        else: origem_clause = "tca.\"origem\" IN ('FARMA', 'FARMADIST')"
        
        sql_query = text(f"""
            WITH RECURSIVE 
            TreePath AS (
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
            ),
            OrdemRaiz AS (
                SELECT id_referencia, tipo_no, ordem 
                FROM "Dre_Schema"."DRE_Ordenamento" 
                WHERE contexto_pai = 'root'
            ),
            Definicoes AS (
                SELECT 
                    v."Conta_Contabil", tp."Raiz_Centro_Custo_Codigo" as "CC_Alvo",
                    tp."Id" as "Id_Hierarquia", NULL::int as "Id_No_Virtual",
                    NULL::text as "Nome_Personalizado_Def", tp.full_path,
                    COALESCE(tp."Raiz_Centro_Custo_Tipo", tp."Raiz_No_Virtual_Nome") as "Tipo_Principal",
                    tp."Raiz_Centro_Custo_Nome" as "Nome_CC_Detalhe",
                    tp."Raiz_No_Virtual_Id" as "Root_Virtual_Id",
                    tp."Raiz_Centro_Custo_Codigo" as "Codigo_CC_Raiz"
                FROM "Dre_Schema"."DRE_Estrutura_Conta_Vinculo" v
                JOIN TreePath tp ON v."Id_Hierarquia" = tp."Id"
                UNION ALL
                SELECT 
                    p."Conta_Contabil", tp."Raiz_Centro_Custo_Codigo", p."Id_Hierarquia",
                    NULL::int, p."Nome_Personalizado", tp.full_path,
                    COALESCE(tp."Raiz_Centro_Custo_Tipo", tp."Raiz_No_Virtual_Nome"),
                    tp."Raiz_Centro_Custo_Nome",
                    tp."Raiz_No_Virtual_Id",
                    tp."Raiz_Centro_Custo_Codigo"
                FROM "Dre_Schema"."DRE_Estrutura_Conta_Personalizada" p
                JOIN TreePath tp ON p."Id_Hierarquia" = tp."Id"
                WHERE p."Id_Hierarquia" IS NOT NULL
                UNION ALL
                SELECT 
                    p."Conta_Contabil", NULL::int, NULL::int, p."Id_No_Virtual",
                    p."Nome_Personalizado", 'Direto', nv."Nome", NULL::text, nv."Id", NULL::int
                FROM "Dre_Schema"."DRE_Estrutura_Conta_Personalizada" p
                JOIN "Dre_Schema"."DRE_Estrutura_No_Virtual" nv ON p."Id_No_Virtual" = nv."Id"
                WHERE p."Id_No_Virtual" IS NOT NULL
            ),
            DadosUnificados AS (
                SELECT
                    COALESCE(adj."Origem", base."origem") as "origem",
                    
                    -- AQUI A MÁGICA TAMBÉM NO RELATÓRIO POR CC
                    CASE 
                        WHEN COALESCE(adj."Is_Nao_Operacional", FALSE) = TRUE THEN '00000000000'
                        ELSE COALESCE(adj."Conta", base."Conta") 
                    END as "Conta",
                    
                    CASE 
                        WHEN COALESCE(adj."Is_Nao_Operacional", FALSE) = TRUE THEN 'Não Operacionais'
                        ELSE COALESCE(adj."Titulo_Conta", base."Título Conta") 
                    END as "Titulo_Conta",
                    
                    COALESCE(adj."Centro_Custo", CAST(base."Centro de Custo" AS TEXT)) as "Centro de Custo",
                    COALESCE(adj."Data", base."Data") as "Data",
                    CASE
                        WHEN adj."Id" IS NOT NULL THEN
                            CASE WHEN adj."Exibir_Saldo" = TRUE THEN (COALESCE(adj."Debito",0) - COALESCE(adj."Credito",0)) ELSE 0.0 END
                        ELSE base."Saldo"
                    END as "Saldo",
                    COALESCE(adj."Is_Nao_Operacional", FALSE) as "Is_Nao_Operacional"
                FROM "Dre_Schema"."Razao_Dados_Consolidado" base
                LEFT JOIN "Dre_Schema"."Ajustes_Razao" adj
                    ON adj."Hash_Linha_Original" = md5(
                        COALESCE(TRIM(CAST(base."origem" AS TEXT)), 'None') || '-' ||
                        COALESCE(TRIM(CAST(base."Filial" AS TEXT)), 'None') || '-' ||
                        COALESCE(TRIM(CAST(base."Numero" AS TEXT)), 'None') || '-' ||
                        COALESCE(TRIM(CAST(base."Item" AS TEXT)), 'None') || '-' ||
                        COALESCE(TRIM(CAST(base."Conta" AS TEXT)), 'None') || '-' ||
                        COALESCE(TO_CHAR(base."Data", 'YYYY-MM-DD'), 'None')
                    )
                    AND adj."Tipo_Operacao" = 'EDICAO'
                    AND adj."Status" != 'Reprovado'
                UNION ALL
                SELECT
                    "Origem", 
                    CASE WHEN "Is_Nao_Operacional" = TRUE THEN '00000000000' ELSE "Conta" END,
                    CASE WHEN "Is_Nao_Operacional" = TRUE THEN 'Não Operacionais' ELSE "Titulo_Conta" END,
                    "Centro_Custo", "Data",
                    CASE WHEN "Exibir_Saldo" = TRUE THEN (COALESCE("Debito",0) - COALESCE("Credito",0)) ELSE 0.0 END as "Saldo",
                    "Is_Nao_Operacional"
                FROM "Dre_Schema"."Ajustes_Razao"
                WHERE "Tipo_Operacao" = 'INCLUSAO' AND "Status" != 'Reprovado'
            ),
            DadosBrutos AS (
                SELECT 
                    tca."origem", 
                    tca."Conta",
                    
                    COALESCE(def."Nome_Personalizado_Def", tca."Titulo_Conta") AS "Titulo_Final",
                    
                    -- AQUI O SQL VAI BUSCAR A ESTRUTURA DA CONTA 00000000000
                    COALESCE(def."Tipo_Principal", 'Outros') AS "Tipo_CC",
                    def."Nome_CC_Detalhe" AS "Nome_CC",
                    COALESCE(def.full_path, 'Não Classificado') AS "Caminho_Subgrupos",
                    def."Root_Virtual_Id",
                    def."Codigo_CC_Raiz",
                    
                    COALESCE((
                        SELECT ordem FROM "Dre_Schema"."DRE_Ordenamento" 
                        WHERE (tipo_no = 'tipo_cc' AND id_referencia = def."Tipo_Principal")
                           OR (tipo_no = 'virtual' AND id_referencia = CAST(def."Root_Virtual_Id" AS TEXT))
                        LIMIT 1
                    ), 999) as ordem_base,
                    
                    tca."Saldo", 
                    tca."Data"
                    
                FROM DadosUnificados tca
                INNER JOIN Definicoes def 
                    ON tca."Conta" = def."Conta_Contabil"
                    AND (
                        (def."CC_Alvo" IS NOT NULL AND CAST(NULLIF(regexp_replace(tca."Centro de Custo", '[^0-9]', '', 'g'), '') AS INTEGER) = def."CC_Alvo") 
                        OR (def."CC_Alvo" IS NULL)
                    )
                WHERE {origem_clause}
            )
            SELECT 
                MAX("origem") as "origem",
                MAX("Conta") as "Conta",
                "Titulo_Final" as "Titulo_Conta",
                "Tipo_CC",
                "Nome_CC",
                "Root_Virtual_Id",
                "Caminho_Subgrupos",
                (COALESCE(SUM("Saldo"), 0.0) * -1) AS "Total_Ano",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 1 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Jan",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 2 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Fev",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 3 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Mar",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 4 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Abr",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 5 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Mai",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 6 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Jun",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 7 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Jul",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 8 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Ago",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 9 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Set",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 10 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Out",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 11 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Nov",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM "Data") = 12 THEN "Saldo" ELSE 0 END), 0.0) * -1) AS "Dez",
                MIN("ordem_base") as ordem_prioridade
            FROM DadosBrutos
            GROUP BY "Tipo_CC", "Nome_CC", "Root_Virtual_Id", "Caminho_Subgrupos", "Titulo_Final", "Conta"
            ORDER BY ordem_prioridade ASC, "Tipo_CC" ASC, "Nome_CC" ASC;
        """)

        result = session.execute(sql_query)
        data_rows = [dict(row._mapping) for row in result]
        return jsonify(data_rows), 200

    except Exception as e: 
        current_app.logger.error(f"Erro no Relatório Rentabilidade por CC: {e}") 
        abort(500, description=f"Erro SQL/Python: {str(e)}")
    finally:
        if session: session.close()