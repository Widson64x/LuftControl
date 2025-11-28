"""
Routes/Reports.py
Rotas para Relatórios de Rentabilidade e Razão Contábil
VERSÃO CORRIGIDA - Consulta SQL dinâmica para evitar problemas de mapeamento ORM
"""

from flask import Blueprint, jsonify, request, current_app, abort, render_template
from flask_login import login_required 
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func, or_, String, text

from Db.Connections import get_postgres_engine

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
    DRE Gerencial Definitiva (CORRIGIDA).
    
    Correções:
    1. Tipagem (CAST de NULLs) para evitar erro no UNION.
    2. Correção de 'Outros': Agora busca o 'Raiz_No_Virtual_Nome' para exibir o nome correto do Nó Virtual.
    3. Filtro de Origem: Aceita parâmetro 'origem' (FARMA, FARMADIST, Consolidado)
    """
    session = None
    try: 
        session = get_pg_session()
        
        # Captura o filtro de origem da query string
        filtro_origem = request.args.get('origem', 'Consolidado')
        
        # Monta a cláusula WHERE baseada no filtro
        if filtro_origem == 'FARMA':
            origem_clause = "tca.\"origem\" = 'FARMA'"
        elif filtro_origem == 'FARMADIST':
            origem_clause = "tca.\"origem\" = 'FARMADIST'"
        else:  # Consolidado (padrão)
            origem_clause = "tca.\"origem\" IN ('FARMA', 'FARMADIST')"
        
        sql_query = text(f"""
            WITH RECURSIVE 
            -- 1. Mapeia Hierarquia (TreePath)
            TreePath AS (
                SELECT 
                    h."Id", h."Nome", h."Id_Pai", 
                    h."Raiz_Centro_Custo_Codigo", h."Raiz_No_Virtual_Id", 
                    h."Raiz_Centro_Custo_Tipo",
                    h."Raiz_No_Virtual_Nome", -- ADICIONADO: Nome do Nó Virtual
                    CAST(h."Nome" AS TEXT) as full_path
                FROM "Dre_Schema"."DRE_Estrutura_Hierarquia" h
                WHERE h."Id_Pai" IS NULL
                
                UNION ALL
                
                SELECT 
                    child."Id", child."Nome", child."Id_Pai", 
                    tp."Raiz_Centro_Custo_Codigo", tp."Raiz_No_Virtual_Id", 
                    tp."Raiz_Centro_Custo_Tipo",
                    tp."Raiz_No_Virtual_Nome", -- ADICIONADO: Repassa o nome para os filhos
                    CAST(tp.full_path || '||' || child."Nome" AS TEXT)
                FROM "Dre_Schema"."DRE_Estrutura_Hierarquia" child
                JOIN TreePath tp ON child."Id_Pai" = tp."Id"
            ),

            -- 2. Ordem
            OrdemRaiz AS (
                SELECT id_referencia, ordem FROM "Dre_Schema"."DRE_Ordenamento" WHERE contexto_pai = 'root'
            ),

            -- 3. MAPA DE DEFINIÇÕES
            Definicoes AS (
                -- 3.1 Vínculos Padrão (Subgrupos)
                SELECT 
                    v."Conta_Contabil",
                    tp."Raiz_Centro_Custo_Codigo" as "CC_Alvo",
                    tp."Id" as "Id_Hierarquia",
                    CAST(NULL AS INTEGER) as "Id_No_Virtual",
                    CAST(NULL AS TEXT) as "Nome_Personalizado_Def",
                    tp.full_path,
                    -- CORREÇÃO: Se não tiver Tipo (Adm/Oper), usa o Nome do Nó Virtual
                    COALESCE(tp."Raiz_Centro_Custo_Tipo", tp."Raiz_No_Virtual_Nome") as "Raiz_Centro_Custo_Tipo",
                    tp."Raiz_No_Virtual_Id" as "Root_Virtual_Id_Hierarquia"
                FROM "Dre_Schema"."DRE_Estrutura_Conta_Vinculo" v
                JOIN TreePath tp ON v."Id_Hierarquia" = tp."Id"

                UNION ALL

                -- 3.2 Vínculos Personalizados em Grupos
                SELECT 
                    p."Conta_Contabil",
                    tp."Raiz_Centro_Custo_Codigo" as "CC_Alvo",
                    p."Id_Hierarquia",
                    CAST(NULL AS INTEGER) as "Id_No_Virtual",
                    p."Nome_Personalizado",
                    tp.full_path,
                    -- CORREÇÃO: Mesmo aqui, garante o nome correto
                    COALESCE(tp."Raiz_Centro_Custo_Tipo", tp."Raiz_No_Virtual_Nome") as "Raiz_Centro_Custo_Tipo",
                    tp."Raiz_No_Virtual_Id"
                FROM "Dre_Schema"."DRE_Estrutura_Conta_Personalizada" p
                JOIN TreePath tp ON p."Id_Hierarquia" = tp."Id"
                WHERE p."Id_Hierarquia" IS NOT NULL

                UNION ALL

                -- 3.3 Vínculos Personalizados Diretos (Sem Subgrupo)
                SELECT 
                    p."Conta_Contabil",
                    CAST(NULL AS INTEGER) as "CC_Alvo",
                    CAST(NULL AS INTEGER) as "Id_Hierarquia",
                    p."Id_No_Virtual",
                    p."Nome_Personalizado",
                    'Direto' as full_path,
                    nv."Nome" as "Raiz_Centro_Custo_Tipo", -- Aqui já pegava o nome certo
                    nv."Id"
                FROM "Dre_Schema"."DRE_Estrutura_Conta_Personalizada" p
                JOIN "Dre_Schema"."DRE_Estrutura_No_Virtual" nv ON p."Id_No_Virtual" = nv."Id"
                WHERE p."Id_No_Virtual" IS NOT NULL
            ),

            -- 4. DADOS BRUTOS
            DadosBrutos AS (
                SELECT 
                    tca."origem", 
                    tca."Conta", 
                    
                    COALESCE(def."Nome_Personalizado_Def", tca."Título Conta") AS "Titulo_Final",
                    
                    -- Agora o 'Raiz_Centro_Custo_Tipo' virá preenchido corretamente (Nome do Nó ou Tipo do CC)
                    COALESCE(def."Raiz_Centro_Custo_Tipo", 'Outros') AS "Tipo_CC",
                    
                    COALESCE(def.full_path, 'Não Classificado') AS "Caminho_Subgrupos",
                    
                    tca."Saldo",
                    tca."Data",
                    
                    COALESCE(ord.ordem, 
                        CASE 
                            WHEN def."Raiz_Centro_Custo_Tipo" = 'Oper' THEN 500 
                            WHEN def."Raiz_Centro_Custo_Tipo" = 'Coml' THEN 510 
                            WHEN def."Raiz_Centro_Custo_Tipo" = 'Adm' THEN 520 
                            ELSE 999 
                        END
                    ) as ordem_base

                FROM "Dre_Schema"."Razao_Dados_Consolidado" tca
                
                INNER JOIN Definicoes def 
                    ON tca."Conta" = def."Conta_Contabil"
                    AND (
                        (def."CC_Alvo" IS NOT NULL AND CAST(tca."Centro de Custo" AS INTEGER) = def."CC_Alvo")
                        OR 
                        (def."CC_Alvo" IS NULL)
                    )
                
                LEFT JOIN OrdemRaiz ord 
                    ON (ord.id_referencia = def."Raiz_Centro_Custo_Tipo" 
                        OR ord.id_referencia = CAST(def."Root_Virtual_Id_Hierarquia" AS TEXT)
                        OR ord.id_referencia = CAST(def."Id_No_Virtual" AS TEXT))

                WHERE {origem_clause}
            )

            -- 5. AGRUPAMENTO FINAL
            SELECT 
                MAX("origem") as "origem",
                
                CASE 
                    WHEN COUNT(DISTINCT "Conta") > 1 THEN 'Agrupado' 
                    ELSE MAX("Conta") 
                END as "Conta",
                
                "Titulo_Final" as "Titulo_Conta",
                "Tipo_CC",
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
            GROUP BY "Tipo_CC", "Caminho_Subgrupos", "Titulo_Final"
            ORDER BY ordem_prioridade ASC, "Tipo_CC", "Caminho_Subgrupos", "Titulo_Final";
        """)

        result = session.execute(sql_query)
        data = [dict(row._mapping) for row in result]
        
        return jsonify(data), 200

    except Exception as e: 
        current_app.logger.error(f"Erro no Relatório Rentabilidade: {e}") 
        abort(500, description=f"Erro SQL: {str(e)}")
    finally:
        if session: session.close()