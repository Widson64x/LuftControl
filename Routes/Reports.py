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
    DRE Gerencial Rigorosa.
    - Regra 1: Só exibe contas VINCULADAS (INNER JOIN).
    - Regra 2: Segue ordenamento configurado.
    - Regra 3: Estrutura Tipo > Grupo > Conta.
    """
    session = None
    try: 
        session = get_pg_session()
        
        sql_query = text("""
            WITH RECURSIVE 
            -- 1. Mapeia toda a hierarquia de Grupos (TreePath)
            TreePath AS (
                SELECT 
                    h."Id", 
                    h."Nome", 
                    h."Id_Pai", 
                    h."Raiz_Centro_Custo_Codigo", 
                    h."Raiz_No_Virtual_Id", 
                    h."Raiz_Centro_Custo_Tipo",
                    CAST(h."Nome" AS TEXT) as full_path
                FROM "Dre_Schema"."DRE_Estrutura_Hierarquia" h
                WHERE h."Id_Pai" IS NULL
                
                UNION ALL
                
                SELECT 
                    child."Id", 
                    child."Nome", 
                    child."Id_Pai", 
                    tp."Raiz_Centro_Custo_Codigo", 
                    tp."Raiz_No_Virtual_Id",
                    tp."Raiz_Centro_Custo_Tipo",
                    CAST(tp.full_path || '||' || child."Nome" AS TEXT)
                FROM "Dre_Schema"."DRE_Estrutura_Hierarquia" child
                JOIN TreePath tp ON child."Id_Pai" = tp."Id"
            ),

            -- 2. Busca a Ordem dos Blocos Principais (Raiz) na tabela de Ordenamento
            OrdemRaiz AS (
                SELECT id_referencia, ordem 
                FROM "Dre_Schema"."DRE_Ordenamento" 
                WHERE contexto_pai = 'root'
            )

            -- =================================================================
            -- QUERY PRINCIPAL (União de CCs Padrão + Virtuais)
            -- =================================================================
            SELECT * FROM (
                -- PARTE A: ESTRUTURA PADRÃO (Vinculada a CCs: Adm, Oper, Coml)
                SELECT 
                    'PADRAO' as origem_dado,
                    tca."origem", 
                    tca."Conta",
                    MAX(tca."Título Conta") AS "Titulo_Conta",
                    
                    -- Nível 1: TIPO (Ex: (-) DESPESAS OPERACIONAIS)
                    COALESCE(tp."Raiz_Centro_Custo_Tipo", 'Outros') AS "Tipo_CC",
                    
                    -- Nível 2: GRUPO (Ex: Pessoal, Veículos)
                    tp.full_path AS "Caminho_Subgrupos",
                    
                    -- Valores Mensais (Invertendo sinal para DRE: Crédito aumenta, Débito diminui resultado)
                    (COALESCE(SUM(tca."Saldo"), 0.0) * -1) AS "Total_Ano",
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

                    -- Ordenamento Prioritário
                    COALESCE(MAX(ord.ordem), 
                        CASE 
                            WHEN tp."Raiz_Centro_Custo_Tipo" = 'Oper' THEN 500 
                            WHEN tp."Raiz_Centro_Custo_Tipo" = 'Coml' THEN 510 
                            WHEN tp."Raiz_Centro_Custo_Tipo" = 'Adm' THEN 520 
                            ELSE 999 
                        END
                    ) as ordem_prioridade

                FROM "Dre_Schema"."Razao_Dados_Consolidado" tca
                -- INNER JOIN OBRIGATÓRIO: Só traz o que tem vínculo na estrutura
                INNER JOIN "Dre_Schema"."DRE_Estrutura_Conta_Vinculo" v 
                    ON tca."Conta" = v."Conta_Contabil" 
                    -- Garante que o vínculo é do CC correto
                    AND (tca."Conta" || CAST(tca."Centro de Custo" AS TEXT)) = v."Chave_Conta_Codigo_CC"
                INNER JOIN TreePath tp 
                    ON v."Id_Hierarquia" = tp."Id"
                LEFT JOIN OrdemRaiz ord 
                    ON ord.id_referencia = tp."Raiz_Centro_Custo_Tipo" 
                    AND ord.id_referencia IN ('Adm', 'Oper', 'Coml')

                WHERE tca."origem" IN ('FARMA', 'FARMADIST')
                GROUP BY tca."origem", tca."Conta", tp."Raiz_Centro_Custo_Tipo", tp.full_path

                UNION ALL

                -- PARTE B: ESTRUTURA VIRTUAL (Contas personalizadas ou vinculadas a nós virtuais)
                SELECT 
                    'VIRTUAL' as origem_dado,
                    tca."origem", 
                    tca."Conta",
                    COALESCE(MAX(cd."Nome_Personalizado"), MAX(tca."Título Conta")) AS "Titulo_Conta",
                    
                    MAX(nv."Nome") AS "Tipo_CC",
                    COALESCE(MAX(tp.full_path), 'Direto') AS "Caminho_Subgrupos",

                    (COALESCE(SUM(tca."Saldo"), 0.0) * -1) AS "Total_Ano",
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

                    -- Ordem: Pega do Nó Virtual ou da Tabela de Ordenamento
                    COALESCE(MAX(ord.ordem), MAX(nv."Ordem"), 0) as ordem_prioridade

                FROM "Dre_Schema"."Razao_Dados_Consolidado" tca
                -- Tenta achar vínculo normal em grupo virtual
                LEFT JOIN "Dre_Schema"."DRE_Estrutura_Conta_Vinculo" v ON tca."Conta" = v."Conta_Contabil"
                LEFT JOIN TreePath tp ON v."Id_Hierarquia" = tp."Id" AND tp."Raiz_No_Virtual_Id" IS NOT NULL
                -- Tenta achar conta personalizada direta
                LEFT JOIN "Dre_Schema"."DRE_Estrutura_Conta_Personalizada" cd ON tca."Conta" = cd."Conta_Contabil"
                LEFT JOIN "Dre_Schema"."DRE_Estrutura_No_Virtual" nv_direto ON cd."Id_No_Virtual" = nv_direto."Id"
                
                -- JOIN FINAL para pegar o nome do Nó Virtual (de um jeito ou de outro)
                INNER JOIN "Dre_Schema"."DRE_Estrutura_No_Virtual" nv 
                    ON (tp."Raiz_No_Virtual_Id" = nv."Id" OR nv_direto."Id" = nv."Id")
                
                LEFT JOIN OrdemRaiz ord ON CAST(nv."Id" AS VARCHAR) = ord.id_referencia

                WHERE tca."origem" IN ('FARMA', 'FARMADIST')
                GROUP BY tca."origem", tca."Conta"
            ) AS FinalResult
            ORDER BY ordem_prioridade ASC, "Tipo_CC", "Caminho_Subgrupos", "Conta";
        """)

        result = session.execute(sql_query)
        data = [dict(row._mapping) for row in result]
        
        return jsonify(data), 200

    except Exception as e: 
        current_app.logger.error(f"Erro no Relatório Rentabilidade: {e}") 
        abort(500, description=f"Erro SQL: {str(e)}")
    finally:
        if session: session.close()