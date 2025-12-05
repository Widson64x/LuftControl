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

def getSession():
    """Cria e retorna uma sessão do PostgreSQL"""
    engine = get_postgres_engine()
    Session = sessionmaker(bind=engine)
    return Session()


# ============================================================
# INICIALIZAÇÃO E SINCRONIZAÇÃO
# ============================================================

@dre_ordem_bp.route('/Ordenamento/Inicializar', methods=['POST'])
@login_required
def inicializarOrdenamento():
    """
    Inicializa a tabela de ordenamento com base na estrutura existente.
    Inclui agora Subgrupos Globais (Raiz).
    """
    session = getSession()
    try:
        # Limpa ordenamento existente (CUIDADO!)
        if request.json.get('limpar', False):
            session.query(DreOrdenamento).delete()
            session.commit()
        
        intervalo = 10
        registros_criados = 0
        
        # ========================================
        # HELPERS DE RECURSIVIDADE
        # ========================================
        def processarContasSubgrupo(sg_id, contexto, nivel, caminho):
            nonlocal registros_criados
            # Contas normais
            vinculos = session.query(DreContaVinculo).filter_by(
                Id_Hierarquia=sg_id
            ).order_by(DreContaVinculo.Conta_Contabil).all()
            
            for v in vinculos:
                existe = session.query(DreOrdenamento).filter_by(
                    tipo_no='conta', id_referencia=v.Conta_Contabil, contexto_pai=contexto
                ).first()
                if not existe:
                    ordem = calcular_proxima_ordem(session, contexto, intervalo)
                    reg = DreOrdenamento(
                        tipo_no='conta', id_referencia=v.Conta_Contabil, contexto_pai=contexto,
                        ordem=ordem, nivel_profundidade=nivel, caminho_completo=f"{caminho}/conta_{v.Conta_Contabil}"
                    )
                    session.add(reg)
                    registros_criados += 1
            
            # Contas detalhe
            detalhes = session.query(DreContaPersonalizada).filter_by(
                Id_Hierarquia=sg_id
            ).order_by(DreContaPersonalizada.Conta_Contabil).all()
            
            for d in detalhes:
                existe = session.query(DreOrdenamento).filter_by(
                    tipo_no='conta_detalhe', id_referencia=str(d.Id), contexto_pai=contexto
                ).first()
                if not existe:
                    ordem = calcular_proxima_ordem(session, contexto, intervalo)
                    reg = DreOrdenamento(
                        tipo_no='conta_detalhe', id_referencia=str(d.Id), contexto_pai=contexto,
                        ordem=ordem, nivel_profundidade=nivel, caminho_completo=f"{caminho}/cd_{d.Id}"
                    )
                    session.add(reg)
                    registros_criados += 1

        def processarSubgrupoIndividual(sg, contexto, nivel, caminho_pai):
            nonlocal registros_criados
            existe = session.query(DreOrdenamento).filter_by(
                tipo_no='subgrupo', id_referencia=str(sg.Id), contexto_pai=contexto
            ).first()
            novo_caminho = f"{caminho_pai}/sg_{sg.Id}"
            
            if not existe:
                ordem_sg = calcular_proxima_ordem(session, contexto, intervalo)
                reg = DreOrdenamento(
                    tipo_no='subgrupo', id_referencia=str(sg.Id), contexto_pai=contexto,
                    ordem=ordem_sg, nivel_profundidade=nivel, caminho_completo=novo_caminho
                )
                session.add(reg)
                registros_criados += 1
            
            novo_contexto = f"sg_{sg.Id}"
            processarSubgrupos(sg.Id, novo_contexto, nivel + 1, novo_caminho)
            processarContasSubgrupo(sg.Id, novo_contexto, nivel + 1, novo_caminho)

        def processarSubgrupos(pai_id, contexto, nivel, caminho):
            nonlocal registros_criados
            if pai_id is None:
                # Subgrupos raiz de CC
                subgrupos_cc = session.query(DreHierarquia).filter(
                    DreHierarquia.Id_Pai == None, DreHierarquia.Raiz_Centro_Custo_Codigo != None
                ).order_by(DreHierarquia.Id).all()
                for sg in subgrupos_cc:
                    ctx = f"cc_{sg.Raiz_Centro_Custo_Codigo}"
                    cam = f"root/tipo_{sg.Raiz_Centro_Custo_Tipo}/cc_{sg.Raiz_Centro_Custo_Codigo}"
                    processarSubgrupoIndividual(sg, ctx, 2, cam)
                
                # Subgrupos raiz de Virtual
                subgrupos_virt = session.query(DreHierarquia).filter(
                    DreHierarquia.Id_Pai == None, DreHierarquia.Raiz_No_Virtual_Id != None
                ).order_by(DreHierarquia.Id).all()
                for sg in subgrupos_virt:
                    ctx = f"virt_{sg.Raiz_No_Virtual_Id}"
                    cam = f"root/virt_{sg.Raiz_No_Virtual_Id}"
                    processarSubgrupoIndividual(sg, ctx, 2, cam)

            else:
                subgrupos = session.query(DreHierarquia).filter(
                    DreHierarquia.Id_Pai == pai_id
                ).order_by(DreHierarquia.Id).all()
                for sg in subgrupos:
                    processarSubgrupoIndividual(sg, contexto, nivel, caminho)

        # ========================================
        # EXECUÇÃO NÍVEL 0 (RAIZ)
        # ========================================
        
        ordem_raiz = intervalo

        # 1. Nós Virtuais < 100
        virtuais = session.query(DreNoVirtual).order_by(DreNoVirtual.Ordem).all()
        for v in virtuais:
            if v.Ordem and v.Ordem < 100:
                existe = session.query(DreOrdenamento).filter_by(tipo_no='virtual', id_referencia=str(v.Id), contexto_pai='root').first()
                if not existe:
                    reg = DreOrdenamento(
                        tipo_no='virtual', id_referencia=str(v.Id), contexto_pai='root',
                        ordem=ordem_raiz, nivel_profundidade=0, caminho_completo=f"root/virt_{v.Id}"
                    )
                    session.add(reg)
                    registros_criados += 1
                ordem_raiz += intervalo
        
        # 2. Subgrupos Globais (Raiz) - NOVO
        subgrupos_raiz_global = session.query(DreHierarquia).filter(
            DreHierarquia.Id_Pai == None,
            DreHierarquia.Raiz_Centro_Custo_Codigo == None,
            DreHierarquia.Raiz_No_Virtual_Id == None
        ).order_by(DreHierarquia.Nome).all()

        for sg in subgrupos_raiz_global:
            existe = session.query(DreOrdenamento).filter_by(
                tipo_no='subgrupo', id_referencia=str(sg.Id), contexto_pai='root'
            ).first()
            if not existe:
                reg = DreOrdenamento(
                    tipo_no='subgrupo', id_referencia=str(sg.Id), contexto_pai='root',
                    ordem=ordem_raiz, nivel_profundidade=0, caminho_completo=f"root/sg_{sg.Id}"
                )
                session.add(reg)
                registros_criados += 1
            
            ordem_raiz += intervalo
            # Processa recursivamente os filhos deste grupo raiz
            novo_contexto = f"sg_{sg.Id}"
            novo_caminho = f"root/sg_{sg.Id}"
            processarSubgrupos(sg.Id, novo_contexto, 1, novo_caminho)
            processarContasSubgrupo(sg.Id, novo_contexto, 1, novo_caminho)

        # 3. Tipos de CC
        sql_tipos = text("""
            SELECT DISTINCT "Tipo" FROM "Dre_Schema"."Classificacao_Centro_Custo"
            WHERE "Tipo" IS NOT NULL ORDER BY "Tipo"
        """)
        tipos = session.execute(sql_tipos).fetchall()
        for (tipo,) in tipos:
            existe = session.query(DreOrdenamento).filter_by(tipo_no='tipo_cc', id_referencia=tipo, contexto_pai='root').first()
            if not existe:
                reg = DreOrdenamento(
                    tipo_no='tipo_cc', id_referencia=tipo, contexto_pai='root',
                    ordem=ordem_raiz, nivel_profundidade=0, caminho_completo=f"root/tipo_{tipo}"
                )
                session.add(reg)
                registros_criados += 1
            ordem_raiz += intervalo

        # 4. Virtuais Restantes (>= 100)
        for v in virtuais:
            if not v.Ordem or v.Ordem >= 100:
                existe = session.query(DreOrdenamento).filter_by(tipo_no='virtual', id_referencia=str(v.Id), contexto_pai='root').first()
                if not existe:
                    reg = DreOrdenamento(
                        tipo_no='virtual', id_referencia=str(v.Id), contexto_pai='root',
                        ordem=ordem_raiz, nivel_profundidade=0, caminho_completo=f"root/virt_{v.Id}"
                    )
                    session.add(reg)
                    registros_criados += 1
                ordem_raiz += intervalo
        
        # 5. Centros de Custo (Nível 1)
        sql_ccs = text("""
            SELECT "Codigo", "Nome", "Tipo" FROM "Dre_Schema"."Classificacao_Centro_Custo"
            WHERE "Codigo" IS NOT NULL ORDER BY "Tipo", "Codigo"
        """)
        ccs = session.execute(sql_ccs).fetchall()
        for codigo, nome, tipo in ccs:
            contexto = f"tipo_{tipo}"
            existe = session.query(DreOrdenamento).filter_by(tipo_no='cc', id_referencia=str(codigo), contexto_pai=contexto).first()
            if not existe:
                ordem_cc = calcular_proxima_ordem(session, contexto, intervalo)
                reg = DreOrdenamento(
                    tipo_no='cc', id_referencia=str(codigo), contexto_pai=contexto,
                    ordem=ordem_cc, nivel_profundidade=1, caminho_completo=f"root/tipo_{tipo}/cc_{codigo}"
                )
                session.add(reg)
                registros_criados += 1

        # 6. Processa Subgrupos de CC e Virtuais (que não são raiz global)
        processarSubgrupos(None, None, 2, '')
        
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
def getOrdem():
    """
    Retorna a ordem de um elemento específico.
    
    Body:
        tipo_no: str
        id_referencia: str
        contexto_pai: str (opcional, default='root')
    """
    session = getSession()
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
def getFilhosOrdenados():
    """
    Retorna todos os filhos de um contexto, ordenados.
    
    Body:
        contexto_pai: str (ex: 'root', 'tipo_Adm', 'cc_25110501', 'sg_15')
    """
    session = getSession()
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
def moverNo():
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
    session = getSession()
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
def reordenarLote():
    """
    Reordena múltiplos elementos de uma vez (após drag-and-drop).
    
    Body:
        contexto_pai: str
        nova_ordem: list[{tipo_no, id_referencia, ordem}]
    """
    session = getSession()
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
def normalizarContexto():
    """
    Normaliza a ordem de um contexto (10, 20, 30, ...).
    Útil após muitas movimentações.
    
    Body:
        contexto_pai: str
    """
    session = getSession()
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
def getArvoreOrdenada():
    """
    Retorna a árvore completa ORDENADA.
    Substitui a rota GetDadosArvore original quando ordenamento está ativo.
    """
    session = getSession()
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
        def montarFilhos(contexto_pai: str):
            filhos = []
            
            # Busca registros ordenados
            registros = session.query(DreOrdenamento).filter_by(
                contexto_pai=contexto_pai
            ).order_by(DreOrdenamento.ordem).all()
            
            for reg in registros:
                node = construirNo(reg)
                if node:
                    filhos.append(node)
            
            return filhos
        
        def _clean_id(id_str: str) -> str:
            if id_str is None:
                return id_str
            # Remove prefixes usados na UI para evitar problemas ao converter
            for p in ('tipo_', 'virt_', 'cc_', 'sg_', 'conta_', 'cd_'):
                if isinstance(id_str, str) and id_str.startswith(p):
                    return id_str[len(p):]
            return id_str


        def construirNo(reg: DreOrdenamento):
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
                node["children"] = montarFilhos(f"tipo_{reg.id_referencia}")

            elif reg.tipo_no == 'virtual':
                try:
                    virt_id = int(_clean_id(reg.id_referencia))
                except Exception:
                    return None
                virt = session.query(DreNoVirtual).get(virt_id)
                if virt:
                    node["id"] = f"virt_{virt.Id}"
                    node["text"] = virt.Nome
                    node["type"] = "root_virtual"
                    node["children"] = montarFilhos(f"virt_{virt.Id}")
                else:
                    return None

            elif reg.tipo_no == 'cc':
                sql = text("""
                    SELECT "Codigo", "Nome", "Tipo"
                    FROM "Dre_Schema"."Classificacao_Centro_Custo"
                    WHERE "Codigo" = :cod
                """)
                try:
                    cod = int(_clean_id(reg.id_referencia))
                except Exception:
                    return None
                cc = session.execute(sql, {"cod": cod}).first()
                if cc:
                    node["id"] = f"cc_{cc[0]}"
                    node["text"] = f"{cc[0]} - {cc[1]}"
                    node["type"] = "root_cc"
                    node["children"] = montarFilhos(f"cc_{cc[0]}")
                else:
                    return None

            elif reg.tipo_no == 'subgrupo':
                try:
                    sg_id = int(_clean_id(reg.id_referencia))
                except Exception:
                    return None
                sg = session.query(DreHierarquia).get(sg_id)
                if sg:
                    node["id"] = f"sg_{sg.Id}"
                    node["db_id"] = sg.Id
                    node["text"] = sg.Nome
                    node["type"] = "subgrupo"
                    node["children"] = montarFilhos(f"sg_{sg.Id}")
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
                conta_ref = _clean_id(str(reg.id_referencia))
                conta_info = session.execute(sql, {"conta": conta_ref}).first()
                nome = conta_info[1] if conta_info else "Sem Título"

                node["id"] = f"conta_{conta_ref}"
                node["text"] = f"Conta: {conta_ref} - {nome}"
                node["type"] = "conta"
                # Contas não têm filhos

            elif reg.tipo_no == 'conta_detalhe':
                try:
                    cd_id = int(_clean_id(reg.id_referencia))
                except Exception:
                    return None
                cd = session.query(DreContaPersonalizada).get(cd_id)
                if cd:
                    node["id"] = f"cd_{cd.Id}"
                    node["text"] = f"{cd.Conta_Contabil} ({cd.Nome_Personalizado or 'Orig'})"
                    node["type"] = "conta_detalhe"
                else:
                    return None

            return node
        
        # Monta árvore a partir da raiz
        arvore = montarFilhos('root')
        
        return jsonify(arvore), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_ordem_bp.route('/Ordenamento/SincronizarNovo', methods=['POST'])
@login_required
def sincronizarNovoElemento():
    """
    Adiciona um novo elemento ao ordenamento.
    Chamado automaticamente ao criar subgrupos/vincular contas.
    
    Body:
        tipo_no: str
        id_referencia: str
        contexto_pai: str
        posicao: str (opcional: 'inicio', 'fim', ou número)
    """
    session = getSession()
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
def removerDoOrdenamento():
    """
    Remove um elemento do ordenamento.
    Chamado automaticamente ao deletar subgrupos/desvincular contas.
    
    Body:
        tipo_no: str
        id_referencia: str
        contexto_pai: str (opcional - se não informado, remove de todos)
    """
    session = getSession()
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