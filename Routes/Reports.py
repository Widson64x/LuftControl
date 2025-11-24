from flask import Blueprint, jsonify, request, current_app, abort, render_template
from flask_login import login_required 
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func, or_ , String
from Models.POSTGRESS.DRE import RazaoConsolidada
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
    """
    Retorna dados paginados com BUSCA GLOBAL.
    Parâmetros: ?page=1&search=termo
    """
    session = None
    try: 
        session = get_pg_session()
        
        # Parâmetros da Requisição
        page = int(request.args.get('page', 1))
        search_term = request.args.get('search', '').strip() # Termo de busca
        per_page = 1000
        offset = (page - 1) * per_page
        
        # 1. Monta a Query Base
        query = session.query(RazaoConsolidada)
        
        # 2. Aplica Filtro de Busca (Se houver termo)
        if search_term:
            # Procura o termo na Conta, Descrição, Número, Origem ou Valor
            # ILIKE faz a busca ser case-insensitive (ignora maiúsculas/minúsculas)
            termo_like = f"%{search_term}%"
            query = query.filter(or_(
                RazaoConsolidada.conta.ilike(termo_like),
                RazaoConsolidada.titulo_conta.ilike(termo_like),
                RazaoConsolidada.descricao.ilike(termo_like),
                RazaoConsolidada.numero.ilike(termo_like),
                RazaoConsolidada.origem.ilike(termo_like),
                RazaoConsolidada.nome_cc.ilike(termo_like),
                # Convertendo números para texto para poder pesquisar valor também se quiser
                func.cast(RazaoConsolidada.debito, String).ilike(termo_like),
                func.cast(RazaoConsolidada.credito, String).ilike(termo_like)
            ))

        # 3. Conta o total DEPOIS do filtro (para calcular páginas corretamente)
        total_registros = query.count()
        total_paginas = (total_registros // per_page) + (1 if total_registros % per_page > 0 else 0)

        # 4. Aplica Paginação e Ordenação
        razoes = query.order_by(RazaoConsolidada.data)\
                      .offset(offset)\
                      .limit(per_page)\
                      .all()
        
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
        current_app.logger.error(f"Erro busca global: {e}") 
        abort(500, description=f"Erro: {str(e)}")
    finally:
        if session:
            session.close()

# O Resumo Global continua o mesmo (não precisa alterar, pois é o resumo da tabela inteira)
@reports_bp.route('/RelatorioRazao/Resumo', methods=['GET']) 
@login_required 
def RelatorioRazaoResumo(): 
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
        if session:
            session.close()