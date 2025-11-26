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
    
    Query Params:
        - page (int): Número da página (default: 1)
        - search (str): Termo de busca (opcional)
    
    ATUALIZADO: Usa nome novo da VIEW (Razao_Dados_Consolidado)
    Mantém nomes originais das colunas (do Excel)
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
        
        # Filtro de busca
        if search_term:
            termo_like = f"%{search_term}%"
            query = query.filter(or_(
                RazaoConsolidado.Conta.ilike(termo_like),
                RazaoConsolidado.Titulo_Conta.ilike(termo_like),
                RazaoConsolidado.Descricao.ilike(termo_like),
                RazaoConsolidado.Numero.ilike(termo_like),
                RazaoConsolidado.origem.ilike(termo_like),
                RazaoConsolidado.Nome_CC.ilike(termo_like),
                func.cast(RazaoConsolidado.Debito, String).ilike(termo_like),
                func.cast(RazaoConsolidado.Credito, String).ilike(termo_like)
            ))

        # Contagem
        total_registros = query.count()
        total_paginas = (total_registros // per_page) + (1 if total_registros % per_page > 0 else 0)

        # Busca paginada
        razoes = query.order_by(RazaoConsolidado.Data).offset(offset).limit(per_page).all()
        
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
    
    Returns:
        - total_registros: Quantidade de lançamentos
        - total_debito: Soma de todos os débitos
        - total_credito: Soma de todos os créditos
        - saldo_total: Saldo final (débito - crédito)
    
    ATUALIZADO: Usa nome novo da VIEW
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
    Retorna DRE Híbrida Ordenada.
    
    Estrutura:
    1. Nós Virtuais (Faturamento, Impostos...) - Ordenados pelo campo 'ordem'
    2. Centros de Custo Reais (Adm, Oper, Coml) - Ordenação fixa no SQL
    
    Cada linha contém:
    - Origem (FARMA/FARMADIST)
    - Conta contábil
    - Título da conta
    - Tipo_CC (Nome do Nó Virtual ou Tipo de CC)
    - Nome_CC (Nome do Centro de Custo, se aplicável)
    - Caminho_Subgrupos (hierarquia completa)
    - Valores mensais (Jan-Dez)
    - Total_Ano
    - ordem_prioridade (para ordenação)
    
    ATUALIZADO: Usa nomes novos de tabelas e colunas
    """
    session = None
    try: 
        session = get_pg_session()
        
        sql_query = text("""
            -- ================================================================
            -- CTE RECURSIVA: Constrói caminho completo da hierarquia
            -- ================================================================
            WITH RECURSIVE TreePath AS (
                SELECT 
                    "Id", 
                    "Nome", 
                    "Id_Pai", 
                    "Raiz_Centro_Custo_Codigo", 
                    "Raiz_No_Virtual_Id", 
                    CAST("Nome" AS TEXT) as full_path
                FROM "Dre_Schema"."DRE_Estrutura_Hierarquia"
                WHERE "Id_Pai" IS NULL
                
                UNION ALL
                
                SELECT 
                    s."Id", 
                    s."Nome", 
                    s."Id_Pai", 
                    tp."Raiz_Centro_Custo_Codigo", 
                    tp."Raiz_No_Virtual_Id",
                    CAST(tp.full_path || '||' || s."Nome" AS TEXT)
                FROM "Dre_Schema"."DRE_Estrutura_Hierarquia" s
                JOIN TreePath tp ON s."Id_Pai" = tp."Id"
            ),
            
            -- ================================================================
            -- CTE: Mapa de vínculos válidos (conta -> grupo)
            -- ================================================================
            VinculosValidos AS (
                SELECT 
                    v."Conta_Contabil", 
                    tp."Raiz_Centro_Custo_Codigo" AS codigo_cc_dono, 
                    tp.full_path AS caminho_grupo
                FROM "Dre_Schema"."DRE_Estrutura_Conta_Vinculo" v
                JOIN TreePath tp ON v."Id_Hierarquia" = tp."Id"
            )

            -- ================================================================
            -- QUERY 1: ESTRUTURA PADRÃO (CENTROS DE CUSTO: ADM, OPER, COML)
            -- ================================================================
            SELECT 
                tca."origem", 
                tca."Conta",
                MAX(tca."Título Conta") AS "Titulo_Conta",
                
                MAX(tcc."Tipo") AS "Tipo_CC",
                MAX(tcc."Nome") AS "Nome_CC",
                
                COALESCE(MAX(vv.caminho_grupo), 'Não Classificado') AS "Caminho_Subgrupos",
                
                -- Valores Mensais (multiplicados por -1 para inverter sinal)
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 1 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Jan",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 2 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Fev",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 3 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Mar",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 4 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Abr",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 5 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Mai",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 6 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Jun",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 7 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Jul",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 8 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Ago",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 9 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Set",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 10 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Out",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 11 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Nov",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 12 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Dez",
                (COALESCE(SUM(tca."Saldo"), 0.0) * -1) AS "Total_Ano",
                
                -- Ordem de Exibição (Despesas ficam após Receitas Virtuais)
                CASE 
                    WHEN MAX(tcc."Tipo") = 'Oper' THEN 500
                    WHEN MAX(tcc."Tipo") = 'Coml' THEN 510
                    WHEN MAX(tcc."Tipo") = 'Adm'  THEN 520
                    ELSE 999 
                END as ordem_prioridade

            FROM "Dre_Schema"."Razao_Dados_Consolidado" tca
            JOIN "Dre_Schema"."Classificacao_Centro_Custo" tcc 
                ON tca."Centro de Custo" = tcc."Codigo"
            LEFT JOIN VinculosValidos vv 
                ON tca."Conta" = vv."Conta_Contabil" 
                AND CAST(tca."Centro de Custo" AS INTEGER) = vv.codigo_cc_dono

            WHERE tca."origem" IN ('FARMA', 'FARMADIST')
            -- Exclui contas que estão em estruturas virtuais
            AND tca."Conta" NOT IN (
                SELECT "Conta_Contabil" 
                FROM "Dre_Schema"."DRE_Estrutura_Conta_Personalizada"
            )
            AND tca."Conta" NOT IN (
                SELECT v2."Conta_Contabil" 
                FROM "Dre_Schema"."DRE_Estrutura_Conta_Vinculo" v2
                JOIN "Dre_Schema"."DRE_Estrutura_Hierarquia" sg2 
                    ON v2."Id_Hierarquia" = sg2."Id"
                WHERE sg2."Raiz_No_Virtual_Id" IS NOT NULL
            )
            
            GROUP BY tca."origem", tca."Conta", tcc."Codigo"

            UNION ALL

            -- ================================================================
            -- QUERY 2: ESTRUTURA VIRTUAL - CONTAS PERSONALIZADAS (DETALHE)
            -- ================================================================
            SELECT 
                tca."origem", 
                tca."Conta",
                COALESCE(MAX(cd."Nome_Personalizado"), MAX(tca."Título Conta")) AS "Titulo_Conta",
                
                -- Nome do Nó Virtual (ex: "1. FATURAMENTO LÍQUIDO")
                COALESCE(MAX(nv_direto."Nome"), MAX(nv_via_grupo."Nome")) AS "Tipo_CC",
                CAST(NULL AS VARCHAR) AS "Nome_CC", 
                
                COALESCE(MAX(tp.full_path), 'Direto') AS "Caminho_Subgrupos",

                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 1 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Jan",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 2 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Fev",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 3 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Mar",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 4 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Abr",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 5 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Mai",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 6 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Jun",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 7 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Jul",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 8 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Ago",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 9 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Set",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 10 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Out",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 11 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Nov",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 12 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Dez",
                (COALESCE(SUM(tca."Saldo"), 0.0) * -1) AS "Total_Ano",
                
                -- Usa ordem definida no banco para Nós Virtuais
                COALESCE(MAX(nv_direto."Ordem"), MAX(nv_via_grupo."Ordem")) as ordem_prioridade

            FROM "Dre_Schema"."Razao_Dados_Consolidado" tca
            JOIN "Dre_Schema"."DRE_Estrutura_Conta_Personalizada" cd 
                ON tca."Conta" = cd."Conta_Contabil"
            LEFT JOIN "Dre_Schema"."DRE_Estrutura_No_Virtual" nv_direto 
                ON cd."Id_No_Virtual" = nv_direto."Id"
            LEFT JOIN TreePath tp 
                ON cd."Id_Hierarquia" = tp."Id"
            LEFT JOIN "Dre_Schema"."DRE_Estrutura_No_Virtual" nv_via_grupo 
                ON tp."Raiz_No_Virtual_Id" = nv_via_grupo."Id"

            WHERE tca."origem" IN ('FARMA', 'FARMADIST')
            GROUP BY tca."origem", tca."Conta"

            UNION ALL

            -- ================================================================
            -- QUERY 3: ESTRUTURA VIRTUAL - CONTAS NORMAIS EM GRUPO VIRTUAL
            -- ================================================================
            SELECT 
                tca."origem", 
                tca."Conta",
                MAX(tca."Título Conta") AS "Titulo_Conta",
                
                MAX(nv."Nome") AS "Tipo_CC", 
                CAST(NULL AS VARCHAR) AS "Nome_CC",
                MAX(tp.full_path) AS "Caminho_Subgrupos",

                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 1 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Jan",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 2 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Fev",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 3 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Mar",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 4 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Abr",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 5 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Mai",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 6 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Jun",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 7 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Jul",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 8 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Ago",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 9 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Set",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 10 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Out",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 11 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Nov",
                (COALESCE(SUM(CASE WHEN EXTRACT(MONTH FROM tca."Data") = 12 THEN tca."Saldo" ELSE 0 END), 0.0) * -1) AS "Dez",
                (COALESCE(SUM(tca."Saldo"), 0.0) * -1) AS "Total_Ano",
                
                MAX(nv."Ordem") as ordem_prioridade

            FROM "Dre_Schema"."Razao_Dados_Consolidado" tca
            JOIN "Dre_Schema"."DRE_Estrutura_Conta_Vinculo" v 
                ON tca."Conta" = v."Conta_Contabil"
            JOIN TreePath tp 
                ON v."Id_Hierarquia" = tp."Id"
            JOIN "Dre_Schema"."DRE_Estrutura_No_Virtual" nv 
                ON tp."Raiz_No_Virtual_Id" = nv."Id"

            WHERE tca."origem" IN ('FARMA', 'FARMADIST')
            AND tca."Conta" NOT IN (
                SELECT "Conta_Contabil" 
                FROM "Dre_Schema"."DRE_Estrutura_Conta_Personalizada"
            )

            GROUP BY tca."origem", tca."Conta"

            -- ================================================================
            -- ORDENAÇÃO FINAL
            -- ================================================================
            ORDER BY ordem_prioridade ASC, "Tipo_CC", "Nome_CC", "Conta";
        """)

        result = session.execute(sql_query)
        data = [dict(row._mapping) for row in result]
        
        return jsonify(data), 200

    except Exception as e: 
        current_app.logger.error(f"Erro no Relatório Rentabilidade: {e}") 
        abort(500, description=f"Erro SQL: {str(e)}")
    finally:
        if session:
            session.close()