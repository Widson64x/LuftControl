from flask import Blueprint, jsonify, request, current_app, abort, render_template
from flask_login import login_required 
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func, or_ , String, text
from Models.POSTGRESS.Rentabilidade import RazaoConsolidada
from Db.Connections import get_postgres_engine

reports_bp = Blueprint('Reports', __name__) 

def get_pg_session():
    engine = get_postgres_engine()
    Session = sessionmaker(bind=engine)
    return Session()

@reports_bp.route('/', methods=['GET']) 
@login_required 
def PaginaRelatorios(): 
    return render_template('MENUS/Relatórios.html')

@reports_bp.route('/RelatorioRazao/Dados', methods=['GET']) 
@login_required 
def RelatorioRazaoDados(): 
    # ... (Código anterior de Dados mantido igual) ...
    session = None
    try: 
        session = get_pg_session()
        page = int(request.args.get('page', 1))
        search_term = request.args.get('search', '').strip()
        per_page = 1000
        offset = (page - 1) * per_page
        
        query = session.query(RazaoConsolidada)
        
        if search_term:
            termo_like = f"%{search_term}%"
            query = query.filter(or_(
                RazaoConsolidada.conta.ilike(termo_like),
                RazaoConsolidada.titulo_conta.ilike(termo_like),
                RazaoConsolidada.descricao.ilike(termo_like),
                RazaoConsolidada.numero.ilike(termo_like),
                RazaoConsolidada.origem.ilike(termo_like),
                RazaoConsolidada.nome_cc.ilike(termo_like),
                func.cast(RazaoConsolidada.debito, String).ilike(termo_like),
                func.cast(RazaoConsolidada.credito, String).ilike(termo_like)
            ))

        total_registros = query.count()
        total_paginas = (total_registros // per_page) + (1 if total_registros % per_page > 0 else 0)

        razoes = query.order_by(RazaoConsolidada.data).offset(offset).limit(per_page).all()
        
        result = []
        for i, r in enumerate(razoes, 1):
            item = {
                'id': i + offset,
                'origem': r.origem,
                'conta': r.conta, 
                'titulo_conta': r.titulo_conta,
                'data': r.data.isoformat() if r.data else None,
                'numero': r.numero,
                'descricao': r.descricao,
                'debito': float(r.debito) if r.debito else 0.0,
                'credito': float(r.credito) if r.credito else 0.0,
                'saldo': float(r.saldo) if r.saldo else 0.0,
                'mes': r.mes,
                'filial_id': r.filial_id,
                'centro_custo_id': r.centro_custo_id,
                'cc_cod': r.cc_cod,
                'nome_cc': r.nome_cc,
                'cliente': r.cliente,
                'filial_cliente': r.filial_cliente,
                'item': r.item,
                'cod_cl_valor': r.cod_cl_valor,
                'contra_partida_credito': r.contra_partida_credito,
                'chv_mes_conta': r.chv_mes_conta,
                'chv_mes_conta_cc': r.chv_mes_conta_cc,
                'chv_mes_nomecc_conta': r.chv_mes_nomecc_conta,
                'chv_mes_nomecc_conta_cc': r.chv_mes_nomecc_conta_cc,
                'chv_conta_formatada': r.chv_conta_formatada,
                'chv_conta_cc': r.chv_conta_cc
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
        if session: session.close()

@reports_bp.route('/RelatorioRazao/Resumo', methods=['GET']) 
@login_required 
def RelatorioRazaoResumo(): 
    # ... (Código anterior de Resumo mantido igual) ...
    session = None
    try: 
        session = get_pg_session()
        from sqlalchemy import func
        resumo = session.query(
            func.count().label('total_registros'),
            func.sum(RazaoConsolidada.debito).label('total_debito'),
            func.sum(RazaoConsolidada.credito).label('total_credito'),
            func.sum(RazaoConsolidada.saldo).label('saldo_total')
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
        if session: session.close()

# =============================================================================
# ROTA PRINCIPAL REFEITA: VISÃO ÚNICA E SEGURA
# =============================================================================
@reports_bp.route('/RelatorioRazao/Rentabilidade', methods=['GET'])
@login_required
def RelatorioRentabilidade(): 
    """
    Retorna DRE Híbrida Ordenada.
    Lógica de Ordenação:
    - Nós Virtuais: Usam o campo 'ordem' do banco (10, 20, 30...)
    - Tipos Reais (Adm, Oper): Ganham uma ordem fixa via SQL para ficarem abaixo das Receitas.
    """
    session = None
    try: 
        session = get_pg_session()
        
        sql_query = text("""
            WITH RECURSIVE TreePath AS (
                SELECT id, nome, parent_subgrupo_id, root_cc_codigo, root_virtual_id, 
                       CAST(nome AS TEXT) as full_path
                FROM "Dre_Schema"."Tb_Dre_Subgrupos"
                WHERE parent_subgrupo_id IS NULL
                UNION ALL
                SELECT s.id, s.nome, s.parent_subgrupo_id, tp.root_cc_codigo, tp.root_virtual_id,
                       CAST(tp.full_path || '||' || s.nome AS TEXT)
                FROM "Dre_Schema"."Tb_Dre_Subgrupos" s
                JOIN TreePath tp ON s.parent_subgrupo_id = tp.id
            ),
            VinculosValidos AS (
                SELECT v.conta_contabil, tp.root_cc_codigo AS codigo_cc_dono, tp.full_path AS caminho_grupo
                FROM "Dre_Schema"."Tb_Dre_Conta_Vinculo" v
                JOIN TreePath tp ON v.subgrupo_id = tp.id
            )

            -- =======================================================
            -- 1. ESTRUTURA PADRÃO (CENTROS DE CUSTO: ADM, OPER, COML)
            -- =======================================================
            SELECT 
                tca."origem", tca."Conta",
                MAX(tca."Título Conta") AS "Titulo_Conta",
                
                MAX(tcc."Tipo") AS "Tipo_CC", -- Ex: 'Adm', 'Oper'
                MAX(tcc."Nome") AS "Nome_CC", -- Ex: 'Tesouraria'
                
                COALESCE(MAX(vv.caminho_grupo), 'Não Classificado') AS "Caminho_Subgrupos",
                
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
                
                -- DEFINE A ORDEM VISUAL NA DRE PARA OS GRUPOS REAIS
                -- Receitas (Virtuais) geralmente são 10, 20...
                -- Então colocamos as despesas reais lá pelo 500.
                CASE 
                    WHEN MAX(tcc."Tipo") = 'Oper' THEN 500  -- Operacional vem antes
                    WHEN MAX(tcc."Tipo") = 'Coml' THEN 510  -- Comercial
                    WHEN MAX(tcc."Tipo") = 'Adm'  THEN 520  -- Adm por último
                    ELSE 999 
                END as ordem_prioridade

            FROM "Dre_Schema"."Tb_Razao_CONSOLIDADA" tca
            JOIN "Dre_Schema"."Tb_Centro_Custo_Classificacao" tcc ON tca."Centro de Custo" = tcc."Codigo CC."
            LEFT JOIN VinculosValidos vv ON tca."Conta" = vv.conta_contabil AND CAST(tca."Centro de Custo" AS INTEGER) = vv.codigo_cc_dono

            WHERE tca."origem" IN ('FARMA', 'FARMADIST')
            AND tca."Conta" NOT IN (SELECT conta_contabil FROM "Dre_Schema"."Tb_Dre_Conta_Detalhe")
            AND tca."Conta" NOT IN (
                SELECT v2.conta_contabil FROM "Dre_Schema"."Tb_Dre_Conta_Vinculo" v2
                JOIN "Dre_Schema"."Tb_Dre_Subgrupos" sg2 ON v2.subgrupo_id = sg2.id
                WHERE sg2.root_virtual_id IS NOT NULL
            )
            
            GROUP BY tca."origem", tca."Conta", tcc."Codigo CC."

            UNION ALL

            -- =======================================================
            -- 2. ESTRUTURA VIRTUAL (FATURAMENTO, IMPOSTOS - DETALHE)
            -- =======================================================
            SELECT 
                tca."origem", tca."Conta",
                COALESCE(MAX(cd.nome_personalizado), MAX(tca."Título Conta")) AS "Titulo_Conta",
                COALESCE(MAX(nv_direto.nome), MAX(nv_via_grupo.nome)) AS "Tipo_CC", -- Nome do Nó Virtual (ex: 1. Faturamento)
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
                
                -- Usa a ordem definida no banco para os Virtuais
                COALESCE(MAX(nv_direto.ordem), MAX(nv_via_grupo.ordem)) as ordem_prioridade

            FROM "Dre_Schema"."Tb_Razao_CONSOLIDADA" tca
            JOIN "Dre_Schema"."Tb_Dre_Conta_Detalhe" cd ON tca."Conta" = cd.conta_contabil
            LEFT JOIN "Dre_Schema"."Tb_Dre_No_Virtual" nv_direto ON cd.no_virtual_id = nv_direto.id
            LEFT JOIN TreePath tp ON cd.subgrupo_id = tp.id
            LEFT JOIN "Dre_Schema"."Tb_Dre_No_Virtual" nv_via_grupo ON tp.root_virtual_id = nv_via_grupo.id

            WHERE tca."origem" IN ('FARMA', 'FARMADIST')
            GROUP BY tca."origem", tca."Conta"

            UNION ALL

            -- =======================================================
            -- 3. ESTRUTURA VIRTUAL (NORMAL EM GRUPO VIRTUAL)
            -- =======================================================
            SELECT 
                tca."origem", tca."Conta",
                MAX(tca."Título Conta") AS "Titulo_Conta",
                MAX(nv.nome) AS "Tipo_CC", 
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
                
                MAX(nv.ordem) as ordem_prioridade

            FROM "Dre_Schema"."Tb_Razao_CONSOLIDADA" tca
            JOIN "Dre_Schema"."Tb_Dre_Conta_Vinculo" v ON tca."Conta" = v.conta_contabil
            JOIN TreePath tp ON v.subgrupo_id = tp.id
            JOIN "Dre_Schema"."Tb_Dre_No_Virtual" nv ON tp.root_virtual_id = nv.id

            WHERE tca."origem" IN ('FARMA', 'FARMADIST')
            AND tca."Conta" NOT IN (SELECT conta_contabil FROM "Dre_Schema"."Tb_Dre_Conta_Detalhe")

            GROUP BY tca."origem", tca."Conta"

            -- ORDENAÇÃO FINAL: Prioridade (Ordem) -> Tipo -> Nome CC -> Conta
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