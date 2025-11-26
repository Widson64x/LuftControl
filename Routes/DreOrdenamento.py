# Routes/DreOrdenamento.py
"""
Rotas para Sistema de Ordenamento Hierárquico da DRE
Gerencia posições e movimentações de elementos na árvore.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required
from sqlalchemy import text, func
from sqlalchemy.orm import sessionmaker
from Db.Connections import get_postgres_engine

# Import dos modelos
from Models.POSTGRESS.DreOrdenamento import (
    DreOrdenamento, 
    DreOrdenamentoConfig,
    gerar_contexto_pai,
    calcular_proxima_ordem,
    reordenar_contexto,
    mover_elemento
)
from Models.POSTGRESS.DreEstrutura import (
    DreHierarquia, 
    DreContaVinculo, 
    DreNoVirtual, 
    DreContaPersonalizada
)

dre_ordem_bp = Blueprint('DreOrdenamento', __name__)

def get_session():
    """Cria e retorna uma sessão do PostgreSQL"""
    engine = get_postgres_engine()
    Session = sessionmaker(bind=engine)
    return Session()


# ============================================================
# INICIALIZAÇÃO E SINCRONIZAÇÃO
# ============================================================

@dre_ordem_bp.route('/Ordenamento/Inicializar', methods=['POST'])
@login_required
def inicializar_ordenamento():
    """
    Inicializa a tabela de ordenamento com base na estrutura existente.
    Deve ser executado UMA VEZ ou quando quiser resetar a ordem.
    
    Gera ordens automáticas baseadas em:
    - Tipos CC: Ordem alfabética
    - Virtuais: Ordem pelo campo 'Ordem' existente
    - CCs: Ordem por código
    - Subgrupos: Ordem por ID
    - Contas: Ordem por número da conta
    """
    session = get_session()
    try:
        # Limpa ordenamento existente (CUIDADO!)
        if request.json.get('limpar', False):
            session.query(DreOrdenamento).delete()
            session.commit()
        
        intervalo = 10
        registros_criados = 0
        
        # ========================================
        # NÍVEL 0: TIPOS DE CC E NÓS VIRTUAIS
        # ========================================
        
        # 1. Busca tipos únicos de CC
        sql_tipos = text("""
            SELECT DISTINCT "Tipo" 
            FROM "Dre_Schema"."Classificacao_Centro_Custo"
            WHERE "Tipo" IS NOT NULL
            ORDER BY "Tipo"
        """)
        tipos = session.execute(sql_tipos).fetchall()
        
        # Nós virtuais primeiro (se tiverem ordem menor)
        virtuais = session.query(DreNoVirtual).order_by(DreNoVirtual.Ordem).all()
        
        # Combina virtuais e tipos em ordem
        ordem_raiz = intervalo
        
        # Virtuais com ordem < 100 vão primeiro
        for v in virtuais:
            if v.Ordem and v.Ordem < 100:
                existe = session.query(DreOrdenamento).filter_by(
                    tipo_no='virtual',
                    id_referencia=str(v.Id),
                    contexto_pai='root'
                ).first()
                
                if not existe:
                    reg = DreOrdenamento(
                        tipo_no='virtual',
                        id_referencia=str(v.Id),
                        contexto_pai='root',
                        ordem=ordem_raiz,
                        nivel_profundidade=0,
                        caminho_completo=f"root/virt_{v.Id}"
                    )
                    session.add(reg)
                    registros_criados += 1
                ordem_raiz += intervalo
        
        # Tipos de CC
        for (tipo,) in tipos:
            existe = session.query(DreOrdenamento).filter_by(
                tipo_no='tipo_cc',
                id_referencia=tipo,
                contexto_pai='root'
            ).first()
            
            if not existe:
                reg = DreOrdenamento(
                    tipo_no='tipo_cc',
                    id_referencia=tipo,
                    contexto_pai='root',
                    ordem=ordem_raiz,
                    nivel_profundidade=0,
                    caminho_completo=f"root/tipo_{tipo}"
                )
                session.add(reg)
                registros_criados += 1
            ordem_raiz += intervalo
        
        # Virtuais com ordem >= 100 vão depois
        for v in virtuais:
            if not v.Ordem or v.Ordem >= 100:
                existe = session.query(DreOrdenamento).filter_by(
                    tipo_no='virtual',
                    id_referencia=str(v.Id),
                    contexto_pai='root'
                ).first()
                
                if not existe:
                    reg = DreOrdenamento(
                        tipo_no='virtual',
                        id_referencia=str(v.Id),
                        contexto_pai='root',
                        ordem=ordem_raiz,
                        nivel_profundidade=0,
                        caminho_completo=f"root/virt_{v.Id}"
                    )
                    session.add(reg)
                    registros_criados += 1
                ordem_raiz += intervalo
        
        # ========================================
        # NÍVEL 1: CENTROS DE CUSTO
        # ========================================
        sql_ccs = text("""
            SELECT "Codigo", "Nome", "Tipo"
            FROM "Dre_Schema"."Classificacao_Centro_Custo"
            WHERE "Codigo" IS NOT NULL
            ORDER BY "Tipo", "Codigo"
        """)
        ccs = session.execute(sql_ccs).fetchall()
        
        for codigo, nome, tipo in ccs:
            contexto = f"tipo_{tipo}"
            
            existe = session.query(DreOrdenamento).filter_by(
                tipo_no='cc',
                id_referencia=str(codigo),
                contexto_pai=contexto
            ).first()
            
            if not existe:
                ordem_cc = calcular_proxima_ordem(session, contexto, intervalo)
                reg = DreOrdenamento(
                    tipo_no='cc',
                    id_referencia=str(codigo),
                    contexto_pai=contexto,
                    ordem=ordem_cc,
                    nivel_profundidade=1,
                    caminho_completo=f"root/tipo_{tipo}/cc_{codigo}"
                )
                session.add(reg)
                registros_criados += 1
        
        # ========================================
        # NÍVEL 2+: SUBGRUPOS (Recursivo)
        # ========================================
        def processar_subgrupos(pai_id, contexto, nivel, caminho):
            nonlocal registros_criados
            
            if pai_id is None:
                # Subgrupos raiz de CC
                subgrupos = session.query(DreHierarquia).filter(
                    DreHierarquia.Id_Pai == None,
                    DreHierarquia.Raiz_Centro_Custo_Codigo != None
                ).order_by(DreHierarquia.Id).all()
                
                for sg in subgrupos:
                    ctx = f"cc_{sg.Raiz_Centro_Custo_Codigo}"
                    cam = f"root/tipo_{sg.Raiz_Centro_Custo_Tipo}/cc_{sg.Raiz_Centro_Custo_Codigo}"
                    processar_subgrupo_individual(sg, ctx, 2, cam)
                
                # Subgrupos raiz de Virtual
                subgrupos_virt = session.query(DreHierarquia).filter(
                    DreHierarquia.Id_Pai == None,
                    DreHierarquia.Raiz_No_Virtual_Id != None
                ).order_by(DreHierarquia.Id).all()
                
                for sg in subgrupos_virt:
                    ctx = f"virt_{sg.Raiz_No_Virtual_Id}"
                    cam = f"root/virt_{sg.Raiz_No_Virtual_Id}"
                    processar_subgrupo_individual(sg, ctx, 2, cam)
            else:
                # Subgrupos filhos
                subgrupos = session.query(DreHierarquia).filter(
                    DreHierarquia.Id_Pai == pai_id
                ).order_by(DreHierarquia.Id).all()
                
                for sg in subgrupos:
                    processar_subgrupo_individual(sg, contexto, nivel, caminho)
        
        def processar_subgrupo_individual(sg, contexto, nivel, caminho_pai):
            nonlocal registros_criados
            
            existe = session.query(DreOrdenamento).filter_by(
                tipo_no='subgrupo',
                id_referencia=str(sg.Id),
                contexto_pai=contexto
            ).first()
            
            novo_caminho = f"{caminho_pai}/sg_{sg.Id}"
            
            if not existe:
                ordem_sg = calcular_proxima_ordem(session, contexto, intervalo)
                reg = DreOrdenamento(
                    tipo_no='subgrupo',
                    id_referencia=str(sg.Id),
                    contexto_pai=contexto,
                    ordem=ordem_sg,
                    nivel_profundidade=nivel,
                    caminho_completo=novo_caminho
                )
                session.add(reg)
                registros_criados += 1
            
            # Processa filhos recursivamente
            novo_contexto = f"sg_{sg.Id}"
            processar_subgrupos(sg.Id, novo_contexto, nivel + 1, novo_caminho)
            
            # Processa contas deste subgrupo
            processar_contas_subgrupo(sg.Id, novo_contexto, nivel + 1, novo_caminho)
        
        def processar_contas_subgrupo(sg_id, contexto, nivel, caminho):
            nonlocal registros_criados
            
            # Contas normais
            vinculos = session.query(DreContaVinculo).filter_by(
                Id_Hierarquia=sg_id
            ).order_by(DreContaVinculo.Conta_Contabil).all()
            
            for v in vinculos:
                existe = session.query(DreOrdenamento).filter_by(
                    tipo_no='conta',
                    id_referencia=v.Conta_Contabil,
                    contexto_pai=contexto
                ).first()
                
                if not existe:
                    ordem = calcular_proxima_ordem(session, contexto, intervalo)
                    reg = DreOrdenamento(
                        tipo_no='conta',
                        id_referencia=v.Conta_Contabil,
                        contexto_pai=contexto,
                        ordem=ordem,
                        nivel_profundidade=nivel,
                        caminho_completo=f"{caminho}/conta_{v.Conta_Contabil}"
                    )
                    session.add(reg)
                    registros_criados += 1
            
            # Contas detalhe
            detalhes = session.query(DreContaPersonalizada).filter_by(
                Id_Hierarquia=sg_id
            ).order_by(DreContaPersonalizada.Conta_Contabil).all()
            
            for d in detalhes:
                existe = session.query(DreOrdenamento).filter_by(
                    tipo_no='conta_detalhe',
                    id_referencia=str(d.Id),
                    contexto_pai=contexto
                ).first()
                
                if not existe:
                    ordem = calcular_proxima_ordem(session, contexto, intervalo)
                    reg = DreOrdenamento(
                        tipo_no='conta_detalhe',
                        id_referencia=str(d.Id),
                        contexto_pai=contexto,
                        ordem=ordem,
                        nivel_profundidade=nivel,
                        caminho_completo=f"{caminho}/cd_{d.Id}"
                    )
                    session.add(reg)
                    registros_criados += 1
        
        # Executa processamento
        processar_subgrupos(None, None, 2, '')
        
        session.commit()
        
        return jsonify({
            "success": True,
            "msg": f"Ordenamento inicializado! {registros_criados} registros criados."
        }), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


# ============================================================
# CONSULTAS
# ============================================================

@dre_ordem_bp.route('/Ordenamento/GetOrdem', methods=['POST'])
@login_required
def get_ordem():
    """
    Retorna a ordem de um elemento específico.
    
    Body:
        tipo_no: str
        id_referencia: str
        contexto_pai: str (opcional, default='root')
    """
    session = get_session()
    try:
        data = request.json
        tipo_no = data.get('tipo_no')
        id_ref = data.get('id_referencia')
        contexto = data.get('contexto_pai', 'root')
        
        registro = session.query(DreOrdenamento).filter_by(
            tipo_no=tipo_no,
            id_referencia=id_ref,
            contexto_pai=contexto
        ).first()
        
        if registro:
            return jsonify({
                "ordem": registro.ordem,
                "nivel": registro.nivel_profundidade,
                "caminho": registro.caminho_completo
            }), 200
        else:
            return jsonify({"ordem": None, "msg": "Não encontrado"}), 200
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_ordem_bp.route('/Ordenamento/GetFilhosOrdenados', methods=['POST'])
@login_required
def get_filhos_ordenados():
    """
    Retorna todos os filhos de um contexto, ordenados.
    
    Body:
        contexto_pai: str (ex: 'root', 'tipo_Adm', 'cc_25110501', 'sg_15')
    """
    session = get_session()
    try:
        data = request.json
        contexto = data.get('contexto_pai', 'root')
        
        registros = session.query(DreOrdenamento).filter_by(
            contexto_pai=contexto
        ).order_by(DreOrdenamento.ordem).all()
        
        resultado = [{
            "id": r.Id,
            "tipo_no": r.tipo_no,
            "id_referencia": r.id_referencia,
            "ordem": r.ordem,
            "nivel": r.nivel_profundidade
        } for r in registros]
        
        return jsonify(resultado), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


# ============================================================
# MANIPULAÇÃO DE ORDEM
# ============================================================

@dre_ordem_bp.route('/Ordenamento/Mover', methods=['POST'])
@login_required
def mover_no():
    """
    Move um nó para nova posição.
    
    Body:
        tipo_no: str
        id_referencia: str
        contexto_origem: str
        contexto_destino: str
        nova_ordem: int (posição desejada)
        posicao_relativa: str (opcional: 'antes', 'depois', 'dentro')
        id_referencia_relativo: str (opcional: ID do elemento de referência)
    """
    session = get_session()
    try:
        data = request.json
        tipo_no = data.get('tipo_no')
        id_ref = data.get('id_referencia')
        ctx_origem = data.get('contexto_origem')
        ctx_destino = data.get('contexto_destino', ctx_origem)
        nova_ordem = data.get('nova_ordem')
        pos_relativa = data.get('posicao_relativa')
        id_relativo = data.get('id_referencia_relativo')
        
        # Calcula ordem se for relativa
        if pos_relativa and id_relativo:
            ref = session.query(DreOrdenamento).filter_by(
                id_referencia=id_relativo,
                contexto_pai=ctx_destino
            ).first()
            
            if ref:
                if pos_relativa == 'antes':
                    nova_ordem = ref.ordem - 5
                elif pos_relativa == 'depois':
                    nova_ordem = ref.ordem + 5
                elif pos_relativa == 'dentro':
                    # Muda o contexto para dentro do elemento
                    ctx_destino = f"sg_{id_relativo}"
                    nova_ordem = calcular_proxima_ordem(session, ctx_destino)
        
        mover_elemento(session, tipo_no, id_ref, ctx_origem, ctx_destino, nova_ordem)
        session.commit()
        
        return jsonify({"success": True, "msg": "Elemento movido!"}), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_ordem_bp.route('/Ordenamento/ReordenarLote', methods=['POST'])
@login_required
def reordenar_lote():
    """
    Reordena múltiplos elementos de uma vez (após drag-and-drop).
    
    Body:
        contexto_pai: str
        nova_ordem: list[{tipo_no, id_referencia, ordem}]
    """
    session = get_session()
    try:
        data = request.json
        contexto = data.get('contexto_pai')
        nova_ordem = data.get('nova_ordem', [])
        
        for item in nova_ordem:
            registro = session.query(DreOrdenamento).filter_by(
                tipo_no=item['tipo_no'],
                id_referencia=item['id_referencia'],
                contexto_pai=contexto
            ).first()
            
            if registro:
                registro.ordem = item['ordem']
            else:
                # Cria se não existir
                novo = DreOrdenamento(
                    tipo_no=item['tipo_no'],
                    id_referencia=item['id_referencia'],
                    contexto_pai=contexto,
                    ordem=item['ordem']
                )
                session.add(novo)
        
        session.commit()
        return jsonify({"success": True, "msg": f"{len(nova_ordem)} itens reordenados!"}), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_ordem_bp.route('/Ordenamento/Normalizar', methods=['POST'])
@login_required
def normalizar_contexto():
    """
    Normaliza a ordem de um contexto (10, 20, 30, ...).
    Útil após muitas movimentações.
    
    Body:
        contexto_pai: str
    """
    session = get_session()
    try:
        data = request.json
        contexto = data.get('contexto_pai', 'root')
        
        reordenar_contexto(session, contexto, intervalo=10)
        session.commit()
        
        return jsonify({"success": True, "msg": "Contexto normalizado!"}), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


# ============================================================
# INTEGRAÇÃO COM ÁRVORE EXISTENTE
# ============================================================

@dre_ordem_bp.route('/Ordenamento/GetArvoreOrdenada', methods=['GET'])
@login_required
def get_arvore_ordenada():
    """
    Retorna a árvore completa ORDENADA.
    Substitui a rota GetDadosArvore original quando ordenamento está ativo.
    """
    session = get_session()
    try:
        # Verifica se há dados de ordenamento
        tem_ordem = session.query(DreOrdenamento).first()
        
        if not tem_ordem:
            # Fallback: Retorna erro pedindo inicialização
            return jsonify({
                "error": "Ordenamento não inicializado",
                "msg": "Execute POST /Ordenamento/Inicializar primeiro"
            }), 400
        
        # Monta árvore recursivamente usando a tabela de ordenamento
        def montar_filhos(contexto_pai: str):
            filhos = []
            
            # Busca registros ordenados
            registros = session.query(DreOrdenamento).filter_by(
                contexto_pai=contexto_pai
            ).order_by(DreOrdenamento.ordem).all()
            
            for reg in registros:
                node = construir_no(reg)
                if node:
                    filhos.append(node)
            
            return filhos
        
        def construir_no(reg: DreOrdenamento):
            """Constrói um nó da árvore baseado no registro de ordenamento"""
            node = {
                "id": None,
                "text": None,
                "type": reg.tipo_no,
                "ordem": reg.ordem,
                "children": []
            }
            
            if reg.tipo_no == 'tipo_cc':
                node["id"] = f"tipo_{reg.id_referencia}"
                node["text"] = reg.id_referencia
                node["type"] = "root_tipo"
                node["children"] = montar_filhos(f"tipo_{reg.id_referencia}")
                
            elif reg.tipo_no == 'virtual':
                virt = session.query(DreNoVirtual).get(int(reg.id_referencia))
                if virt:
                    node["id"] = f"virt_{virt.Id}"
                    node["text"] = virt.Nome
                    node["type"] = "root_virtual"
                    node["children"] = montar_filhos(f"virt_{virt.Id}")
                else:
                    return None
                    
            elif reg.tipo_no == 'cc':
                sql = text("""
                    SELECT "Codigo", "Nome", "Tipo"
                    FROM "Dre_Schema"."Classificacao_Centro_Custo"
                    WHERE "Codigo" = :cod
                """)
                cc = session.execute(sql, {"cod": int(reg.id_referencia)}).first()
                if cc:
                    node["id"] = f"cc_{cc[0]}"
                    node["text"] = f"{cc[0]} - {cc[1]}"
                    node["type"] = "root_cc"
                    node["children"] = montar_filhos(f"cc_{cc[0]}")
                else:
                    return None
                    
            elif reg.tipo_no == 'subgrupo':
                sg = session.query(DreHierarquia).get(int(reg.id_referencia))
                if sg:
                    node["id"] = f"sg_{sg.Id}"
                    node["db_id"] = sg.Id
                    node["text"] = sg.Nome
                    node["type"] = "subgrupo"
                    node["children"] = montar_filhos(f"sg_{sg.Id}")
                else:
                    return None
                    
            elif reg.tipo_no == 'conta':
                # Busca nome da conta
                sql = text("""
                    SELECT DISTINCT "Conta", "Título Conta"
                    FROM "Dre_Schema"."Razao_Dados_Consolidado"
                    WHERE "Conta" = :conta
                    LIMIT 1
                """)
                conta_info = session.execute(sql, {"conta": reg.id_referencia}).first()
                nome = conta_info[1] if conta_info else "Sem Título"
                
                node["id"] = f"conta_{reg.id_referencia}"
                node["text"] = f"Conta: {reg.id_referencia} - {nome}"
                node["type"] = "conta"
                # Contas não têm filhos
                
            elif reg.tipo_no == 'conta_detalhe':
                cd = session.query(DreContaPersonalizada).get(int(reg.id_referencia))
                if cd:
                    node["id"] = f"cd_{cd.Id}"
                    node["text"] = f"{cd.Conta_Contabil} ({cd.Nome_Personalizado or 'Orig'})"
                    node["type"] = "conta_detalhe"
                else:
                    return None
            
            return node
        
        # Monta árvore a partir da raiz
        arvore = montar_filhos('root')
        
        return jsonify(arvore), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_ordem_bp.route('/Ordenamento/SincronizarNovo', methods=['POST'])
@login_required
def sincronizar_novo_elemento():
    """
    Adiciona um novo elemento ao ordenamento.
    Chamado automaticamente ao criar subgrupos/vincular contas.
    
    Body:
        tipo_no: str
        id_referencia: str
        contexto_pai: str
        posicao: str (opcional: 'inicio', 'fim', ou número)
    """
    session = get_session()
    try:
        data = request.json
        tipo_no = data.get('tipo_no')
        id_ref = str(data.get('id_referencia'))
        contexto = data.get('contexto_pai')
        posicao = data.get('posicao', 'fim')
        
        # Verifica se já existe
        existe = session.query(DreOrdenamento).filter_by(
            tipo_no=tipo_no,
            id_referencia=id_ref,
            contexto_pai=contexto
        ).first()
        
        if existe:
            return jsonify({"success": True, "msg": "Já existe", "ordem": existe.ordem}), 200
        
        # Calcula ordem
        if posicao == 'inicio':
            # Pega menor ordem e subtrai
            min_ordem = session.query(func.min(DreOrdenamento.ordem)).filter_by(
                contexto_pai=contexto
            ).scalar() or 10
            nova_ordem = max(1, min_ordem - 10)
        elif posicao == 'fim':
            nova_ordem = calcular_proxima_ordem(session, contexto)
        else:
            try:
                nova_ordem = int(posicao)
            except:
                nova_ordem = calcular_proxima_ordem(session, contexto)
        
        # Calcula nível baseado no contexto
        if contexto == 'root':
            nivel = 0
        elif contexto.startswith('tipo_'):
            nivel = 1
        elif contexto.startswith('cc_') or contexto.startswith('virt_'):
            nivel = 2
        else:
            # Subgrupos aninhados - busca nível do pai
            pai_ordem = session.query(DreOrdenamento).filter(
                DreOrdenamento.contexto_pai.contains(contexto.replace('sg_', ''))
            ).first()
            nivel = (pai_ordem.nivel_profundidade + 1) if pai_ordem else 3
        
        # Cria registro
        novo = DreOrdenamento(
            tipo_no=tipo_no,
            id_referencia=id_ref,
            contexto_pai=contexto,
            ordem=nova_ordem,
            nivel_profundidade=nivel
        )
        session.add(novo)
        session.commit()
        
        return jsonify({
            "success": True, 
            "msg": "Elemento adicionado ao ordenamento",
            "ordem": nova_ordem
        }), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_ordem_bp.route('/Ordenamento/RemoverElemento', methods=['POST'])
@login_required
def remover_do_ordenamento():
    """
    Remove um elemento do ordenamento.
    Chamado automaticamente ao deletar subgrupos/desvincular contas.
    
    Body:
        tipo_no: str
        id_referencia: str
        contexto_pai: str (opcional - se não informado, remove de todos)
    """
    session = get_session()
    try:
        data = request.json
        tipo_no = data.get('tipo_no')
        id_ref = str(data.get('id_referencia'))
        contexto = data.get('contexto_pai')
        
        query = session.query(DreOrdenamento).filter_by(
            tipo_no=tipo_no,
            id_referencia=id_ref
        )
        
        if contexto:
            query = query.filter_by(contexto_pai=contexto)
        
        deletados = query.delete()
        session.commit()
        
        return jsonify({
            "success": True, 
            "msg": f"{deletados} registro(s) removido(s) do ordenamento"
        }), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()