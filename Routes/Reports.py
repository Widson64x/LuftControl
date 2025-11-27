"""
Routes/Reports.py
Rotas para Relatórios de Rentabilidade e Razão Contábil
VERSÃO ATUALIZADA - Nomenclatura refatorada
"""

from flask import Blueprint, jsonify, request, current_app, abort, render_template
from flask_login import login_required 
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func, or_, String, text

from Models.POSTGRESS.Rentabilidade import RazaoConsolidado
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
    """
    session = None
    try: 
        session = get_pg_session()
        
        # Parâmetros
        page = int(request.args.get('page', 1))
        search_term = request.args.get('search', '').strip()
        per_page = 1000
        offset = (page - 1) * per_page
        
        # Query base
        query = session.query(RazaoConsolidado)
        
        # Filtro de busca - inclui CC (CC_Cod), Nome_CC, Cliente e Filial Cliente
        if search_term:
            termo_like = f"%{search_term}%"
            query = query.filter(or_(
                RazaoConsolidado.Conta.ilike(termo_like),
                RazaoConsolidado.Titulo_Conta.ilike(termo_like),
                RazaoConsolidado.Descricao.ilike(termo_like),
                RazaoConsolidado.Numero.ilike(termo_like),
                RazaoConsolidado.origem.ilike(termo_like),
                RazaoConsolidado.Nome_CC.ilike(termo_like),
                RazaoConsolidado.Cliente.ilike(termo_like),
                RazaoConsolidado.Filial_Cliente.ilike(termo_like),
                RazaoConsolidado.CC_Cod.ilike(termo_like),
                func.cast(RazaoConsolidado.Debito, String).ilike(termo_like),
                func.cast(RazaoConsolidado.Credito, String).ilike(termo_like)
            ))

        # Contagem total (antes da paginação)
        total_registros = query.count()
        total_paginas = (total_registros // per_page) + (1 if total_registros % per_page > 0 else 0)

        # Busca paginada — ordenação determinística
        razoes = query.order_by(RazaoConsolidado.Data, RazaoConsolidado.Conta, RazaoConsolidado.Numero).offset(offset).limit(per_page).all()
        
        # Formata resultado
        result = []
        for i, r in enumerate(razoes, 1):
            item = {
                'id': i + offset,
                'origem': r.origem,
                'conta': r.Conta, 
                'titulo_conta': r.Titulo_Conta,
                'data': r.Data.isoformat() if r.Data else None,
                'numero': r.Numero,
                'descricao': r.Descricao,
                'debito': float(r.Debito) if r.Debito else 0.0,
                'credito': float(r.Credito) if r.Credito else 0.0,
                'saldo': float(r.Saldo) if r.Saldo else 0.0,
                'mes': r.Mes,
                'filial_id': r.Filial,
                'centro_custo_id': r.Centro_Custo,
                'cc_cod': r.CC_Cod,
                'nome_cc': r.Nome_CC,
                'cliente': r.Cliente,
                'filial_cliente': r.Filial_Cliente,
                'item': r.Item,
                'cod_cl_valor': r.Cod_Cl_Valor,
                'contra_partida_credito': r.Contra_Partida_Credito,
                'chv_mes_conta': r.Chv_Mes_Conta,
                'chv_mes_conta_cc': r.Chv_Mes_Conta_CC,
                'chv_mes_nomecc_conta': r.Chv_Mes_NomeCC_Conta,
                'chv_mes_nomecc_conta_cc': r.Chv_Mes_NomeCC_Conta_CC,
                'chv_conta_formatada': r.Chv_Conta_Formatada,
                'chv_conta_cc': r.Chv_Conta_CC
            }
            result.append(item)
        
        return jsonify({
            'pagina_atual': page,
            'total_paginas': total_paginas,
            'total_registros': total_registros,
            'termo_busca': search_term,
            'dados': result
        }), 200
        
    except Exception as e: 
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
        
        resumo = session.query(
            func.count().label('total_registros'),
            func.sum(RazaoConsolidado.Debito).label('total_debito'),
            func.sum(RazaoConsolidado.Credito).label('total_credito'),
            func.sum(RazaoConsolidado.Saldo).label('saldo_total')
        ).first()
        
        result = {
            'total_registros': resumo.total_registros or 0,
            'total_debito': float(resumo.total_debito) if resumo.total_debito else 0.0,
            'total_credito': float(resumo.total_credito) if resumo.total_credito else 0.0,
            'saldo_total': float(resumo.saldo_total) if resumo.saldo_total else 0.0
        }
        
        return jsonify(result), 200
        
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
    
    Correções de Tipagem SQL:
    - Adicionado CAST(NULL AS INTEGER) e CAST(NULL AS TEXT) para evitar erro de DatatypeMismatch no UNION.
    """
    session = None
    try: 
        session = get_pg_session()
        
        sql_query = text("""
            WITH RECURSIVE 
            -- 1. Mapeia Hierarquia (TreePath)
            TreePath AS (
                SELECT 
                    h."Id", h."Nome", h."Id_Pai", 
                    h."Raiz_Centro_Custo_Codigo", h."Raiz_No_Virtual_Id", h."Raiz_Centro_Custo_Tipo",
                    CAST(h."Nome" AS TEXT) as full_path
                FROM "Dre_Schema"."DRE_Estrutura_Hierarquia" h
                WHERE h."Id_Pai" IS NULL
                UNION ALL
                SELECT 
                    child."Id", child."Nome", child."Id_Pai", 
                    tp."Raiz_Centro_Custo_Codigo", tp."Raiz_No_Virtual_Id", tp."Raiz_Centro_Custo_Tipo",
                    CAST(tp.full_path || '||' || child."Nome" AS TEXT)
                FROM "Dre_Schema"."DRE_Estrutura_Hierarquia" child
                JOIN TreePath tp ON child."Id_Pai" = tp."Id"
            ),

            -- 2. Ordem
            OrdemRaiz AS (
                SELECT id_referencia, ordem FROM "Dre_Schema"."DRE_Ordenamento" WHERE contexto_pai = 'root'
            ),

            -- 3. MAPA DE DEFINIÇÕES (UNION CORRIGIDO COM CASTS)
            Definicoes AS (
                -- 3.1 Vínculos Padrão
                SELECT 
                    v."Conta_Contabil",
                    tp."Raiz_Centro_Custo_Codigo" as "CC_Alvo",
                    tp."Id" as "Id_Hierarquia",
                    CAST(NULL AS INTEGER) as "Id_No_Virtual", -- CAST CORRIGIDO
                    CAST(NULL AS TEXT) as "Nome_Personalizado_Def", -- CAST CORRIGIDO
                    tp.full_path,
                    tp."Raiz_Centro_Custo_Tipo",
                    tp."Raiz_No_Virtual_Id" as "Root_Virtual_Id_Hierarquia"
                FROM "Dre_Schema"."DRE_Estrutura_Conta_Vinculo" v
                JOIN TreePath tp ON v."Id_Hierarquia" = tp."Id"

                UNION ALL

                -- 3.2 Vínculos Personalizados em Grupos
                SELECT 
                    p."Conta_Contabil",
                    tp."Raiz_Centro_Custo_Codigo" as "CC_Alvo",
                    p."Id_Hierarquia",
                    CAST(NULL AS INTEGER) as "Id_No_Virtual", -- CAST CORRIGIDO
                    p."Nome_Personalizado",
                    tp.full_path,
                    tp."Raiz_Centro_Custo_Tipo",
                    tp."Raiz_No_Virtual_Id"
                FROM "Dre_Schema"."DRE_Estrutura_Conta_Personalizada" p
                JOIN TreePath tp ON p."Id_Hierarquia" = tp."Id"
                WHERE p."Id_Hierarquia" IS NOT NULL

                UNION ALL

                -- 3.3 Vínculos Personalizados Diretos
                SELECT 
                    p."Conta_Contabil",
                    CAST(NULL AS INTEGER) as "CC_Alvo", -- CAST CORRIGIDO
                    CAST(NULL AS INTEGER) as "Id_Hierarquia", -- CAST CORRIGIDO
                    p."Id_No_Virtual",
                    p."Nome_Personalizado",
                    'Direto' as full_path,
                    nv."Nome" as "Raiz_Centro_Custo_Tipo",
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

                WHERE tca."origem" IN ('FARMA', 'FARMADIST')
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