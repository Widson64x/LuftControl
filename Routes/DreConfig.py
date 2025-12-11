"""
Routes/DreConfig.py
Rotas para Configuração da Árvore DRE (Demonstração do Resultado do Exercício)

ORGANIZAÇÃO:
    1. Imports e Configuração
    2. Funções Auxiliares (Session, Ordenamento, Fórmulas)
    3. Rotas de Visualização (Views/Templates)
    4. Rotas de Consulta (GET - Leitura de dados)
    5. Rotas de Criação (ADD - Novos registros)
    6. Rotas de Atualização (UPDATE/RENAME)
    7. Rotas de Exclusão (DELETE/DESVINCULAR)
    8. Rotas de Operações em Massa
    9. Rotas de Replicação/Clonagem
    10. Rotas Utilitárias (Correções de banco, Testes)
"""

from flask import Blueprint, jsonify, request, render_template, json
from flask_login import login_required
from sqlalchemy import text, func
from sqlalchemy.orm import sessionmaker

from Db.Connections import get_postgres_engine
from Models.POSTGRESS.DreEstrutura import (
    DreContaVinculo, 
    DreNoVirtual, 
    DreHierarquia, 
    DreContaPersonalizada
)
from Models.POSTGRESS.DreOrdenamento import DreOrdenamento, calcular_proxima_ordem

dre_config_bp = Blueprint('DreConfig', __name__)


# ============================================================
# SEÇÃO 1: FUNÇÕES AUXILIARES
# ============================================================

def get_session():
    """Cria e retorna uma sessão do PostgreSQL."""
    engine = get_postgres_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def limpar_ordenamento(session, tipo_no: str, id_referencia: str, contexto_pai: str = None):
    """
    Remove registro(s) de ordenamento de um elemento.
    
    Args:
        session: Sessão SQLAlchemy
        tipo_no: Tipo do nó ('subgrupo', 'conta', 'conta_detalhe', 'virtual', etc.)
        id_referencia: ID ou código do elemento
        contexto_pai: (Opcional) Se informado, deleta apenas nesse contexto específico
    """
    query = session.query(DreOrdenamento).filter(
        DreOrdenamento.tipo_no == tipo_no,
        DreOrdenamento.id_referencia == str(id_referencia)
    )
    
    if contexto_pai:
        query = query.filter(DreOrdenamento.contexto_pai == contexto_pai)
    
    query.delete(synchronize_session=False)


def limpar_ordenamento_em_lote(session, tipo_no: str, ids: list):
    """
    Remove registros de ordenamento em lote.
    
    Args:
        session: Sessão SQLAlchemy
        tipo_no: Tipo do nó
        ids: Lista de IDs/códigos a remover
    """
    if not ids:
        return
        
    ids_str = [str(i) for i in ids]
    session.query(DreOrdenamento).filter(
        DreOrdenamento.tipo_no == tipo_no,
        DreOrdenamento.id_referencia.in_(ids_str)
    ).delete(synchronize_session=False)


def limpar_ordenamento_por_contexto(session, contexto_pai: str):
    """
    Remove TODOS os registros de ordenamento de um contexto.
    Útil quando deleta um nó pai (remove todos os filhos do ordenamento).
    
    Args:
        session: Sessão SQLAlchemy
        contexto_pai: Contexto a limpar (ex: 'sg_15', 'virt_1')
    """
    session.query(DreOrdenamento).filter(
        DreOrdenamento.contexto_pai == contexto_pai
    ).delete(synchronize_session=False)


def gerar_descricao_formula(formula: dict) -> str:
    """
    Gera descrição legível da fórmula.
    Ex: "Faturamento + Operacional"
    """
    operacoes = {
        "soma": "+",
        "subtracao": "-",
        "multiplicacao": "×",
        "divisao": "÷"
    }
    
    op = formula.get('operacao', 'soma')
    operandos = formula.get('operandos', [])
    simbolo = operacoes.get(op, '+')
    
    labels = []
    for operando in operandos:
        label = operando.get('label') or operando.get('id', '?')
        labels.append(str(label))
    
    descricao = f" {simbolo} ".join(labels)
    
    if formula.get('multiplicador'):
        descricao = f"({descricao}) × {formula['multiplicador']}"
    
    return descricao


def get_all_child_ids(session, parent_ids: list) -> list:
    """
    Busca recursivamente todos os IDs de filhos de uma lista de pais.
    Retorna lista completa incluindo os IDs originais.
    """
    all_ids = set(parent_ids)
    current_level = parent_ids
    
    while current_level:
        filhos = session.query(DreHierarquia.Id).filter(
            DreHierarquia.Id_Pai.in_(current_level)
        ).all()
        
        if not filhos:
            break
            
        child_ids = [f.Id for f in filhos]
        all_ids.update(child_ids)
        current_level = child_ids
    
    return list(all_ids)


# ============================================================
# SEÇÃO 2: ROTAS DE VISUALIZAÇÃO (VIEWS/TEMPLATES)
# ============================================================

@dre_config_bp.route('/Configuracao/Arvore', methods=['GET'])
@login_required
def ViewConfiguracao():
    """Renderiza a página de configuração da árvore DRE."""
    return render_template('MENUS/ConfiguracaoDRE.html')


# ============================================================
# SEÇÃO 3: ROTAS DE CONSULTA (GET - LEITURA)
# ============================================================

@dre_config_bp.route('/Configuracao/GetDadosArvore', methods=['GET'])
@login_required
def GetDadosArvore():
    """
    Monta a árvore híbrida da DRE.
    Retorna estrutura completa com Nós Virtuais, Centros de Custo e agora GRUPOS RAIZ.
    """
    session = get_session()
    try:
        # 1. Busca Base Fixa (Centros de Custo)
        sql_base = text("""
            SELECT DISTINCT "Tipo", "Nome", "Codigo" 
            FROM "Dre_Schema"."Classificacao_Centro_Custo"
            WHERE "Codigo" IS NOT NULL
            ORDER BY "Tipo", "Nome", "Codigo"
        """)
        base_result = session.execute(sql_base).mappings().all()

        # 2. Busca Dados Dinâmicos
        subgrupos = session.query(DreHierarquia).all()
        vinculos = session.query(DreContaVinculo).all()
        virtuais = session.query(DreNoVirtual).order_by(DreNoVirtual.Ordem).all()
        contas_detalhe = session.query(DreContaPersonalizada).all()

        # 3. Busca Mapa de Nomes das Contas
        sql_nomes = text("""
            SELECT DISTINCT "Conta", "Título Conta"
            FROM "Dre_Schema"."Razao_Dados_Consolidado"
            WHERE "Conta" IS NOT NULL
        """)
        res_nomes = session.execute(sql_nomes).fetchall()
        mapa_nomes_contas = {str(row[0]): row[1] for row in res_nomes}

        # --- HELPERS DE MONTAGEM ---
        def get_contas_normais(sub_id):
            lista = []
            for v in vinculos:
                if v.Id_Hierarquia == sub_id:
                    conta_num = str(v.Conta_Contabil)
                    nome_conta = mapa_nomes_contas.get(conta_num, "Sem Título")
                    label_exibicao = f"Conta: {conta_num} - {nome_conta}"
                    
                    lista.append({
                        "id": f"conta_{conta_num}", 
                        "text": label_exibicao,
                        "type": "conta", 
                        "parent": sub_id
                    })
            return lista

        def get_contas_detalhe(sub_id):
            return [
                {
                    "id": f"cd_{c.Id}", 
                    "text": f"{c.Conta_Contabil} ({c.Nome_Personalizado or 'Orig'})", 
                    "type": "conta_detalhe", 
                    "parent": sub_id
                } 
                for c in contas_detalhe if c.Id_Hierarquia == sub_id
            ]

        def get_children_subgrupos(parent_id):
            children = []
            for sg in subgrupos:
                if sg.Id_Pai == parent_id:
                    contas = get_contas_normais(sg.Id) + get_contas_detalhe(sg.Id)
                    node = {
                        "id": f"sg_{sg.Id}", 
                        "db_id": sg.Id, 
                        "text": sg.Nome, 
                        "type": "subgrupo",
                        "children": get_children_subgrupos(sg.Id) + contas
                    }
                    children.append(node)
            return children

        # --- LISTA FINAL ---
        final_tree = []

        # 0. GRUPOS RAIZ GLOBAL (NOVO)
        # Filtra subgrupos que não têm Pai, nem CC raiz, nem Virtual raiz
        grupos_raiz = [sg for sg in subgrupos if sg.Id_Pai is None and sg.Raiz_Centro_Custo_Codigo is None and sg.Raiz_No_Virtual_Id is None]
        
        for gr in grupos_raiz:
            node = {
                "id": f"sg_{gr.Id}", 
                "db_id": gr.Id, 
                "text": gr.Nome, 
                "type": "subgrupo",
                "parent": "root", # Marcador visual para o JS
                "children": (
                    get_children_subgrupos(gr.Id) + 
                    get_contas_normais(gr.Id) + 
                    get_contas_detalhe(gr.Id)
                )
            }
            final_tree.append(node)

        # 1. MONTAGEM DA ÁRVORE VIRTUAL
        for v in virtuais:
            children_virtual = []
            
            for sg in subgrupos:
                if sg.Raiz_No_Virtual_Id == v.Id and sg.Id_Pai is None:
                    contas_do_grupo = (
                        get_children_subgrupos(sg.Id) + 
                        get_contas_detalhe(sg.Id) + 
                        get_contas_normais(sg.Id)
                    )
                    node = {
                        "id": f"sg_{sg.Id}", 
                        "db_id": sg.Id, 
                        "text": sg.Nome, 
                        "type": "subgrupo", 
                        "children": contas_do_grupo
                    }
                    children_virtual.append(node)

            for c in contas_detalhe:
                if c.Id_No_Virtual == v.Id:
                    label = f"{c.Conta_Contabil} ({c.Nome_Personalizado or ''})"
                    children_virtual.append({
                        "id": f"cd_{c.Id}", 
                        "text": label, 
                        "type": "conta_detalhe", 
                        "parent": f"virt_{v.Id}"
                    })
            
            node_virtual = {
                "id": f"virt_{v.Id}",
                "text": v.Nome,
                "type": "root_virtual",
                "is_calculado": v.Is_Calculado,
                "children": children_virtual
            }
            final_tree.append(node_virtual)

        # 2. MONTAGEM DA ÁRVORE PADRÃO (CENTROS DE CUSTO)
        tipos_map = {}
        
        for row in base_result:
            tipo = row['Tipo']
            nome_cc = row['Nome']
            codigo_cc = row['Codigo'] 
            label_cc = f"{codigo_cc} - {nome_cc}"
            
            if tipo not in tipos_map:
                tipos_map[tipo] = {
                    "id": f"tipo_{tipo}", 
                    "text": tipo, 
                    "type": "root_tipo", 
                    "children": []
                }
            
            children_do_cc = []
            for sg in subgrupos:
                if sg.Raiz_Centro_Custo_Codigo == codigo_cc and sg.Id_Pai is None:
                    node = {
                        "id": f"sg_{sg.Id}", 
                        "db_id": sg.Id, 
                        "text": sg.Nome, 
                        "type": "subgrupo", 
                        "children": (
                            get_children_subgrupos(sg.Id) + 
                            get_contas_normais(sg.Id) + 
                            get_contas_detalhe(sg.Id)
                        )
                    }
                    children_do_cc.append(node)

            node_cc = {
                "id": f"cc_{codigo_cc}", 
                "text": label_cc,        
                "type": "root_cc", 
                "children": children_do_cc
            }
            tipos_map[tipo]["children"].append(node_cc)

        final_tree.extend(list(tipos_map.values()))

        return jsonify(final_tree), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/GetContasDisponiveis', methods=['GET'])
@login_required
def GetContasDisponiveis():
    """Retorna lista de contas contábeis disponíveis para vinculação."""
    session = get_session()
    try:
        sql = text("""
            SELECT DISTINCT "Conta", "Título Conta"
            FROM "Dre_Schema"."Razao_Dados_Consolidado"
            WHERE "Conta" IS NOT NULL
            ORDER BY "Conta" ASC
        """)
        
        result = session.execute(sql).fetchall()
        contas = [{"numero": row[0], "nome": row[1]} for row in result]
        
        return jsonify(contas), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/GetContasDoSubgrupo', methods=['POST'])
@login_required
def GetContasDoSubgrupo():
    """Retorna as contas vinculadas a um ID de Subgrupo específico."""
    session = get_session()
    try:
        data = request.json
        raw_id = data.get('id')
        
        if not raw_id: 
            return jsonify([]), 200
            
        try:
            sg_id = int(raw_id)
        except ValueError:
            return jsonify([]), 200

        vinculos = session.query(DreContaVinculo.Conta_Contabil).filter(
            DreContaVinculo.Id_Hierarquia == sg_id
        ).all()
        
        lista = [str(v.Conta_Contabil) for v in vinculos]
        
        return jsonify(lista), 200

    except Exception as e:
        print(f"Erro em GetContasDoSubgrupo: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/GetSubgruposPorTipo', methods=['POST'])
@login_required
def GetSubgruposPorTipo():
    """
    Retorna lista de nomes ordenada pela posição média no banco.
    """
    session = get_session()
    try:
        data = request.json
        tipo_cc = data.get('tipo_cc') 
        
        # Query Corrigida:
        # 1. Filtra subgrupos pelo Tipo diretamente (garantia de encontrar).
        # 2. Faz Left Join com Ordenamento para pegar a ordem atual.
        # 3. Ordena pelo MIN(ordem) para refletir a posição salva.
        sql = text("""
            SELECT h."Nome", MIN(ord.ordem) as min_ordem
            FROM "Dre_Schema"."DRE_Estrutura_Hierarquia" h
            LEFT JOIN "Dre_Schema"."DRE_Ordenamento" ord 
                ON CAST(h."Id" AS TEXT) = ord.id_referencia 
                AND ord.tipo_no = 'subgrupo'
            WHERE h."Raiz_Centro_Custo_Tipo" = :tipo
            GROUP BY h."Nome"
            ORDER BY min_ordem ASC NULLS LAST, h."Nome" ASC
        """)
        
        rows = session.execute(sql, {'tipo': tipo_cc}).fetchall()
        
        # Retorna lista de nomes
        grupos = [r[0] for r in rows]
        
        return jsonify(grupos), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/GetContasDoGrupoMassa', methods=['POST'])
@login_required
def GetContasDoGrupoMassa():
    """Retorna lista unificada de contas (Padrão + Personalizadas) vinculadas ao grupo."""
    session = get_session()
    try:
        data = request.json
        tipo_cc = data.get('tipo_cc')
        nome_grupo = data.get('nome_grupo')

        if not tipo_cc or not nome_grupo:
             return jsonify([]), 200

        ids_subgrupos = session.query(DreHierarquia.Id).filter(
            DreHierarquia.Raiz_Centro_Custo_Tipo == tipo_cc,
            DreHierarquia.Nome == nome_grupo
        ).all()
        
        ids = [i.Id for i in ids_subgrupos]
        
        if not ids:
            return jsonify([]), 200

        lista_final = []

        # Contas Padrão
        padrao = session.query(DreContaVinculo.Conta_Contabil).filter(
            DreContaVinculo.Id_Hierarquia.in_(ids)
        ).distinct().all()
        
        for p in padrao:
            lista_final.append({
                "conta": p.Conta_Contabil,
                "tipo": "padrao",
                "nome_personalizado": None
            })

        # Contas Personalizadas
        personalizadas = session.query(
            DreContaPersonalizada.Conta_Contabil,
            DreContaPersonalizada.Nome_Personalizado
        ).filter(
            DreContaPersonalizada.Id_Hierarquia.in_(ids)
        ).distinct().all()

        for p in personalizadas:
            lista_final.append({
                "conta": p.Conta_Contabil,
                "tipo": "personalizada",
                "nome_personalizado": p.Nome_Personalizado
            })
        
        lista_final.sort(key=lambda x: x['conta'])
        
        return jsonify(lista_final), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/GetNosCalculados', methods=['GET'])
@login_required
def GetNosCalculados():
    """Retorna lista de todos os nós calculados com suas fórmulas."""
    session = get_session()
    try:
        nos = session.query(DreNoVirtual).filter(
            DreNoVirtual.Is_Calculado == True
        ).order_by(DreNoVirtual.Ordem).all()
        
        result = []
        for n in nos:
            result.append({
                "id": n.Id,
                "nome": n.Nome,
                "ordem": n.Ordem,
                "formula": json.loads(n.Formula_JSON) if n.Formula_JSON else None,
                "formula_descricao": n.Formula_Descricao,
                "tipo_exibicao": n.Tipo_Exibicao,
                "estilo_css": n.Estilo_CSS
            })
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/GetOperandosDisponiveis', methods=['GET'])
@login_required
def GetOperandosDisponiveis():
    """Retorna lista de elementos que podem ser usados como operandos em fórmulas."""
    session = get_session()
    try:
        resultado = {
            "nos_virtuais": [],
            "tipos_cc": [],
            "subgrupos_raiz": [] # Novo campo
        }
        
        # 1. Nós Virtuais
        nos = session.query(DreNoVirtual).order_by(DreNoVirtual.Ordem).all()
        for n in nos:
            resultado["nos_virtuais"].append({
                "id": n.Id,
                "nome": n.Nome,
                "is_calculado": n.Is_Calculado
            })
        
        # 2. Tipos de Centro de Custo
        sql_tipos = text("""
            SELECT DISTINCT "Tipo" 
            FROM "Dre_Schema"."Classificacao_Centro_Custo"
            WHERE "Tipo" IS NOT NULL
            ORDER BY "Tipo"
        """)
        tipos = session.execute(sql_tipos).fetchall()
        for row in tipos:
            tipo_valor = row[0]
            resultado["tipos_cc"].append({
                "id": tipo_valor,
                "nome": tipo_valor
            })
        
        # 3. Subgrupos de primeiro nível (Globais ou Raiz de Tipo)
        # Filtra grupos que não são filhos de outros grupos
        # E agrupa por nome para evitar duplicatas visuais (ex: 'Pessoal' aparece em vários CCs)
        sql_subgrupos = text("""
            SELECT DISTINCT "Nome"
            FROM "Dre_Schema"."DRE_Estrutura_Hierarquia"
            WHERE "Id_Pai" IS NULL
            ORDER BY "Nome"
        """)
        subgrupos = session.execute(sql_subgrupos).fetchall()
        
        for row in subgrupos:
            nome_grupo = row[0]
            # Usamos o Nome como ID lógico, pois o cálculo agregará todos os grupos com esse nome
            resultado["subgrupos_raiz"].append({
                "id": nome_grupo,
                "nome": nome_grupo
            })
        
        return jsonify(resultado), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


# ============================================================
# SEÇÃO 4: ROTAS DE CRIAÇÃO (ADD)
# ============================================================

@dre_config_bp.route('/Configuracao/AddSubgrupo', methods=['POST'])
@login_required
def AddSubgrupo():
    """Adiciona subgrupo. Suporta: CC, Virtual, Subgrupo Pai e agora ROOT."""
    session = get_session()
    try:
        data = request.json
        nome = data.get('nome')
        parent_node_id = str(data.get('parent_id')) 

        if not nome:
            return jsonify({"error": "Nome do grupo é obrigatório"}), 400

        novo_sub = DreHierarquia(Nome=nome)
        contexto_pai_ordem = ""
        filtro_duplicidade = {}
        nivel = 3

        # --- LÓGICA PARA GRUPO RAIZ GLOBAL ---
        if parent_node_id == 'root':
            novo_sub.Id_Pai = None
            novo_sub.Raiz_Centro_Custo_Codigo = None
            novo_sub.Raiz_No_Virtual_Id = None
            
            filtro_duplicidade = {
                "Id_Pai": None,
                "Raiz_Centro_Custo_Codigo": None,
                "Raiz_No_Virtual_Id": None
            }
            contexto_pai_ordem = "root"
            nivel = 0 # Nível mais alto, junto com Tipos e Virtuais

        elif parent_node_id.startswith("cc_"):
            codigo_cc_int = int(parent_node_id.replace("cc_", ""))
            
            filtro_duplicidade = {
                "Raiz_Centro_Custo_Codigo": codigo_cc_int,
                "Id_Pai": None
            }

            sql_info = text('SELECT "Tipo", "Nome" FROM "Dre_Schema"."Classificacao_Centro_Custo" WHERE "Codigo" = :cod LIMIT 1')
            result_info = session.execute(sql_info, {"cod": codigo_cc_int}).first()
            novo_sub.Raiz_Centro_Custo_Tipo = result_info[0] if result_info else "Indefinido"
            novo_sub.Raiz_Centro_Custo_Nome = result_info[1] if result_info else "Indefinido"
            novo_sub.Raiz_Centro_Custo_Codigo = codigo_cc_int
            contexto_pai_ordem = f"cc_{codigo_cc_int}"
            nivel = 2

        elif parent_node_id.startswith("virt_"):
            virt_id = int(parent_node_id.replace("virt_", ""))
            
            filtro_duplicidade = {
                "Raiz_No_Virtual_Id": virt_id,
                "Id_Pai": None
            }

            no_virt = session.query(DreNoVirtual).get(virt_id)
            novo_sub.Raiz_No_Virtual_Id = virt_id
            novo_sub.Raiz_No_Virtual_Nome = no_virt.Nome if no_virt else None
            contexto_pai_ordem = f"virt_{virt_id}"
            nivel = 2

        elif parent_node_id.startswith("sg_"):
            parent_id = int(parent_node_id.replace("sg_", ""))
            
            filtro_duplicidade = {"Id_Pai": parent_id}

            novo_sub.Id_Pai = parent_id
            pai = session.query(DreHierarquia).get(parent_id)
            if pai:
                novo_sub.Raiz_Centro_Custo_Codigo = pai.Raiz_Centro_Custo_Codigo
                novo_sub.Raiz_Centro_Custo_Tipo = pai.Raiz_Centro_Custo_Tipo
                novo_sub.Raiz_No_Virtual_Id = pai.Raiz_No_Virtual_Id
            contexto_pai_ordem = f"sg_{parent_id}"
            nivel = 3

        # Trava de Duplicidade
        duplicado = session.query(DreHierarquia).filter_by(**filtro_duplicidade).filter(
            func.lower(DreHierarquia.Nome) == nome.strip().lower()
        ).first()

        if duplicado:
            return jsonify({"error": f"Já existe um grupo '{nome}' neste local."}), 400

        session.add(novo_sub)
        session.flush()

        # Ordenamento
        nova_ordem = calcular_proxima_ordem(session, contexto_pai_ordem)
        
        reg_ordem = DreOrdenamento(
            tipo_no='subgrupo', 
            id_referencia=str(novo_sub.Id),
            contexto_pai=contexto_pai_ordem, 
            ordem=nova_ordem, 
            nivel_profundidade=nivel
        )
        session.add(reg_ordem)

        session.commit()
        return jsonify({"success": True}), 200

    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/AddSubgrupoSistematico', methods=['POST'])
@login_required
def AddSubgrupoSistematico():
    """Cria um subgrupo automaticamente para TODOS os CCs de um TIPO."""
    session = get_session()
    try:
        data = request.json
        nome_grupo = data.get('nome')
        tipo_cc = data.get('tipo_cc')

        if not nome_grupo or not tipo_cc:
            return jsonify({"error": "Nome do grupo e Tipo são obrigatórios"}), 400

        sql_ccs = text("""
            SELECT "Codigo", "Nome", "Tipo"
            FROM "Dre_Schema"."Classificacao_Centro_Custo"
            WHERE "Tipo" = :tipo AND "Codigo" IS NOT NULL
        """)
        
        ccs = session.execute(sql_ccs, {"tipo": tipo_cc}).fetchall()

        if not ccs:
            return jsonify({"error": f"Nenhum Centro de Custo encontrado para o tipo '{tipo_cc}'"}), 404

        count_created = 0

        for cc in ccs:
            codigo = cc[0]
            nome_cc = cc[1]
            tipo = cc[2]

            existe = session.query(DreHierarquia).filter_by(
                Raiz_Centro_Custo_Codigo=codigo,
                Nome=nome_grupo,
                Id_Pai=None
            ).first()

            if not existe:
                novo_sub = DreHierarquia(
                    Nome=nome_grupo,
                    Id_Pai=None,
                    Raiz_Centro_Custo_Codigo=codigo,
                    Raiz_Centro_Custo_Nome=nome_cc,
                    Raiz_Centro_Custo_Tipo=tipo
                )
                session.add(novo_sub)
                count_created += 1
        
        session.commit()
        
        if count_created == 0:
            return jsonify({"success": True, "msg": "Nenhum grupo criado (todos os CCs já possuíam este grupo)."}), 200
            
        return jsonify({"success": True, "msg": f"Grupo '{nome_grupo}' criado em {count_created} Centros de Custo do tipo '{tipo_cc}'!"}), 200

    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/AddNoVirtual', methods=['POST'])
@login_required
def AddNoVirtual():
    """Adiciona um novo Nó Virtual com trava de duplicidade de nome."""
    session = get_session()
    try:
        data = request.json
        nome = data.get('nome')
        
        if not nome: 
            return jsonify({"error": "Nome obrigatório"}), 400
        
        existe = session.query(DreNoVirtual).filter(
            func.lower(DreNoVirtual.Nome) == nome.strip().lower()
        ).first()

        if existe:
            return jsonify({"error": f"Já existe um Nó Virtual chamado '{nome}'."}), 400
        
        novo = DreNoVirtual(Nome=nome)
        session.add(novo)
        session.commit()
        
        return jsonify({"success": True}), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/AddNoCalculado', methods=['POST'])
@login_required
def AddNoCalculado():
    """Cria um novo Nó Virtual do tipo CALCULADO."""
    session = get_session()
    try:
        data = request.json
        nome = data.get('nome')
        formula = data.get('formula')
        ordem = data.get('ordem', 0)
        tipo_exibicao = data.get('tipo_exibicao', 'valor')
        estilo_css = data.get('estilo_css')
        base_pct_id = data.get('base_percentual_id')
        
        if not nome:
            return jsonify({"error": "Nome obrigatório"}), 400
        
        if not formula or 'operacao' not in formula:
            return jsonify({"error": "Fórmula inválida"}), 400
        
        existe = session.query(DreNoVirtual).filter(
            func.lower(DreNoVirtual.Nome) == nome.strip().lower()
        ).first()
        
        if existe:
            return jsonify({"error": f"Já existe um nó chamado '{nome}'"}), 400
        
        descricao = gerar_descricao_formula(formula)
        
        novo = DreNoVirtual(
            Nome=nome,
            Ordem=ordem,
            Is_Calculado=True,
            Formula_JSON=json.dumps(formula),
            Formula_Descricao=descricao,
            Tipo_Exibicao=tipo_exibicao,
            Base_Percentual_Id=base_pct_id,
            Estilo_CSS=estilo_css
        )
        
        session.add(novo)
        session.commit()
        
        return jsonify({
            "success": True,
            "id": novo.Id,
            "msg": f"Nó calculado '{nome}' criado com sucesso!"
        }), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/VincularConta', methods=['POST'])
@login_required
def VincularConta():
    """Vincula uma conta contábil a um subgrupo."""
    session = get_session()
    try:
        data = request.json
        conta = str(data.get('conta')).strip()
        subgrupo_node_id = data.get('subgrupo_id') 

        if not subgrupo_node_id.startswith("sg_"):
            raise Exception("Contas só podem ser vinculadas a Subgrupos.")

        sg_id = int(subgrupo_node_id.replace("sg_", ""))

        subgrupo = session.query(DreHierarquia).get(sg_id)
        if not subgrupo: 
            raise Exception("Subgrupo não encontrado.")
            
        # Rastreamento da Raiz
        temp_parent = subgrupo
        root_cc_code = temp_parent.Raiz_Centro_Custo_Codigo
        root_virt_id = temp_parent.Raiz_No_Virtual_Id
        root_tipo = temp_parent.Raiz_Centro_Custo_Tipo or "Virtual"

        while (root_cc_code is None and root_virt_id is None) and temp_parent.Id_Pai is not None:
            temp_parent = session.query(DreHierarquia).get(temp_parent.Id_Pai)
            root_cc_code = temp_parent.Raiz_Centro_Custo_Codigo
            root_virt_id = temp_parent.Raiz_No_Virtual_Id
            root_tipo = temp_parent.Raiz_Centro_Custo_Tipo or "Virtual"

        chave_tipo = f"{conta}{root_tipo}"
        chave_cod = f"{conta}{root_cc_code}" if root_cc_code else f"{conta}VIRTUAL{root_virt_id}"

        vinculo = session.query(DreContaVinculo).filter_by(Conta_Contabil=conta).first()

        if not vinculo:
            vinculo = DreContaVinculo(
                Conta_Contabil=conta, 
                Id_Hierarquia=sg_id,
                Chave_Conta_Tipo_CC=chave_tipo,
                Chave_Conta_Codigo_CC=chave_cod
            )
            session.add(vinculo)
        else:
            # Remove ordem antiga
            limpar_ordenamento(session, 'conta', conta)
            
            vinculo.Id_Hierarquia = sg_id
            vinculo.Chave_Conta_Tipo_CC = chave_tipo
            vinculo.Chave_Conta_Codigo_CC = chave_cod

        # Ordenamento
        contexto_pai = f"sg_{sg_id}"
        nova_ordem = calcular_proxima_ordem(session, contexto_pai)

        reg_ordem = DreOrdenamento(
            tipo_no='conta',
            id_referencia=conta,
            contexto_pai=contexto_pai,
            ordem=nova_ordem,
            nivel_profundidade=99
        )
        session.add(reg_ordem)

        session.commit()
        return jsonify({"success": True}), 200

    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/VincularContaDetalhe', methods=['POST'])
@login_required
def VincularContaDetalhe():
    """Vincula conta personalizada a um Nó Virtual OU Subgrupo."""
    session = get_session()
    try:
        data = request.json
        conta = data.get('conta')
        nome_personalizado = data.get('nome_personalizado')
        parent_id = data.get('parent_id')
        
        if not conta or not parent_id: 
            return jsonify({"error": "Dados incompletos"}), 400

        detalhe = session.query(DreContaPersonalizada).filter_by(Conta_Contabil=conta).first()
        
        if not detalhe:
            detalhe = DreContaPersonalizada(Conta_Contabil=conta)
            session.add(detalhe)
        
        if nome_personalizado:
            detalhe.Nome_Personalizado = nome_personalizado
            
        if parent_id.startswith("virt_"):
            detalhe.Id_No_Virtual = int(parent_id.replace("virt_", ""))
            detalhe.Id_Hierarquia = None
        elif parent_id.startswith("sg_"):
            detalhe.Id_Hierarquia = int(parent_id.replace("sg_", ""))
            detalhe.Id_No_Virtual = None
        else:
            return jsonify({"error": "Local inválido para vínculo de detalhe"}), 400

        session.commit()
        return jsonify({"success": True}), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


# ============================================================
# SEÇÃO 5: ROTAS DE ATUALIZAÇÃO (UPDATE/RENAME)
# ============================================================

@dre_config_bp.route('/Configuracao/RenameNoVirtual', methods=['POST'])
@login_required
def RenameNoVirtual():
    """Renomeia um Nó Virtual."""
    session = get_session()
    try:
        data = request.json
        node_id = data.get('id').replace('virt_', '')
        novo_nome = data.get('novo_nome')
        
        node = session.query(DreNoVirtual).get(int(node_id))
        if node:
            node.Nome = novo_nome
            session.commit()
            return jsonify({"success": True}), 200
        return jsonify({"error": "Nó não encontrado"}), 404
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/RenameSubgrupo', methods=['POST'])
@login_required
def RenameSubgrupo():
    """Renomeia um Subgrupo."""
    session = get_session()
    try:
        data = request.json
        node_id = data.get('id').replace('sg_', '')
        novo_nome = data.get('novo_nome')
        
        node = session.query(DreHierarquia).get(int(node_id))
        if node:
            node.Nome = novo_nome
            session.commit()
            return jsonify({"success": True}), 200
        return jsonify({"error": "Subgrupo não encontrado"}), 404
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/RenameContaPersonalizada', methods=['POST'])
@login_required
def RenameContaPersonalizada():
    """Renomeia uma Conta Personalizada."""
    session = get_session()
    try:
        data = request.json
        node_id = data.get('id').replace('cd_', '')
        novo_nome = data.get('novo_nome')
        
        conta = session.query(DreContaPersonalizada).get(int(node_id))
        if conta:
            conta.Nome_Personalizado = novo_nome
            session.commit()
            return jsonify({"success": True}), 200
        return jsonify({"error": "Conta detalhe não encontrada"}), 404
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/UpdateNoCalculado', methods=['POST'])
@login_required
def UpdateNoCalculado():
    """Atualiza a fórmula de um nó calculado existente."""
    session = get_session()
    try:
        data = request.json
        node_id = data.get('id')
        formula = data.get('formula')
        nome = data.get('nome')
        ordem = data.get('ordem')
        tipo_exibicao = data.get('tipo_exibicao')
        estilo_css = data.get('estilo_css')
        
        no = session.query(DreNoVirtual).get(node_id)
        
        if not no:
            return jsonify({"error": "Nó não encontrado"}), 404
        
        if not no.Is_Calculado:
            return jsonify({"error": "Este nó não é calculado"}), 400
        
        if nome:
            no.Nome = nome
        if formula:
            no.Formula_JSON = json.dumps(formula)
            no.Formula_Descricao = gerar_descricao_formula(formula)
        if ordem is not None:
            no.Ordem = ordem
        if tipo_exibicao:
            no.Tipo_Exibicao = tipo_exibicao
        if estilo_css is not None:
            no.Estilo_CSS = estilo_css
        
        session.commit()
        
        return jsonify({"success": True, "msg": "Fórmula atualizada!"}), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


# ============================================================
# SEÇÃO 6: ROTAS DE EXCLUSÃO (DELETE/DESVINCULAR)
# ============================================================

@dre_config_bp.route('/Configuracao/DeleteSubgrupo', methods=['POST'])
@login_required
def DeleteSubgrupo():
    """
    Deleta um subgrupo da hierarquia e TUDO que estiver dentro dele (Cascata).
    Remove recursivamente: Filhos, Contas Vinculadas, Contas Personalizadas E ORDENAMENTO.
    """
    session = get_session()
    try:
        data = request.json
        node_id = data.get('id') 
        
        if not node_id or not node_id.startswith('sg_'):
            return jsonify({"error": "Nó inválido para exclusão"}), 400
            
        db_id = int(node_id.replace('sg_', ''))
        
        def delete_recursivo(id_pai):
            # 1. Busca filhos
            filhos = session.query(DreHierarquia).filter_by(Id_Pai=id_pai).all()
            for filho in filhos:
                delete_recursivo(filho.Id)
            
            # 2. Coleta contas para limpar ordenamento
            contas_vinculadas = session.query(DreContaVinculo.Conta_Contabil).filter_by(
                Id_Hierarquia=id_pai
            ).all()
            
            contas_personalizadas = session.query(DreContaPersonalizada.Id).filter_by(
                Id_Hierarquia=id_pai
            ).all()
            
            # 3. Limpa ordenamento das contas
            for (conta,) in contas_vinculadas:
                limpar_ordenamento(session, 'conta', conta)
            
            for (cd_id,) in contas_personalizadas:
                limpar_ordenamento(session, 'conta_detalhe', str(cd_id))
            
            # 4. Limpa ordenamento dos filhos neste contexto
            limpar_ordenamento_por_contexto(session, f'sg_{id_pai}')
            
            # 5. Deleta Contas Vinculadas
            session.query(DreContaVinculo).filter_by(Id_Hierarquia=id_pai).delete()
            
            # 6. Deleta Contas Personalizadas
            session.query(DreContaPersonalizada).filter_by(Id_Hierarquia=id_pai).delete()
            
            # 7. Limpa ordenamento do próprio subgrupo
            limpar_ordenamento(session, 'subgrupo', str(id_pai))
            
            # 8. Deleta o grupo
            session.query(DreHierarquia).filter_by(Id=id_pai).delete()

        delete_recursivo(db_id)
        
        session.commit()
        return jsonify({"success": True, "msg": "Grupo e todos os seus itens excluídos."}), 200

    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/DesvincularConta', methods=['POST'])
@login_required
def DesvincularConta():
    """
    Desvincula uma conta da estrutura DRE.
    Funciona para contas normais e personalizadas.
    LIMPA O ORDENAMENTO!
    """
    session = get_session()
    try:
        data = request.json
        node_id = data.get('id')
        
        if node_id.startswith('conta_'):
            conta_contabil = node_id.replace('conta_', '')
            vinculo = session.query(DreContaVinculo).filter_by(
                Conta_Contabil=conta_contabil
            ).first()
            
            if vinculo:
                # Limpa ordenamento
                limpar_ordenamento(session, 'conta', conta_contabil)
                
                session.delete(vinculo)
                session.commit()
                return jsonify({"success": True}), 200
            
        elif node_id.startswith('cd_'):
            cd_id = int(node_id.replace('cd_', ''))
            detalhe = session.query(DreContaPersonalizada).get(cd_id)
            
            if detalhe:
                # Limpa ordenamento
                limpar_ordenamento(session, 'conta_detalhe', str(cd_id))
                
                session.delete(detalhe)
                session.commit()
                return jsonify({"success": True}), 200
        
        return jsonify({"error": "Vínculo não encontrado"}), 404
            
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/DeleteNoVirtual', methods=['POST'])
@login_required
def DeleteNoVirtual():
    """
    Deleta um Nó Virtual e tudo que está pendurado nele (Cascata Completa).
    LIMPA O ORDENAMENTO!
    """
    session = get_session()
    try:
        data = request.json
        node_id = data.get('id')
        
        if not node_id or not node_id.startswith('virt_'):
            return jsonify({"error": "Nó inválido"}), 400
            
        virt_id = int(node_id.replace('virt_', ''))

        # 1. Busca subgrupos do Nó Virtual
        subgrupos = session.query(DreHierarquia).filter_by(Raiz_No_Virtual_Id=virt_id).all()
        ids_hierarquia = [s.Id for s in subgrupos]

        if ids_hierarquia:
            # Coleta contas para limpeza
            contas_vinculadas = session.query(DreContaVinculo.Conta_Contabil).filter(
                DreContaVinculo.Id_Hierarquia.in_(ids_hierarquia)
            ).all()
            
            contas_personalizadas = session.query(DreContaPersonalizada.Id).filter(
                DreContaPersonalizada.Id_Hierarquia.in_(ids_hierarquia)
            ).all()
            
            # Limpa ordenamento das contas
            for (conta,) in contas_vinculadas:
                limpar_ordenamento(session, 'conta', conta)
            
            for (cd_id,) in contas_personalizadas:
                limpar_ordenamento(session, 'conta_detalhe', str(cd_id))
            
            # Limpa ordenamento dos subgrupos
            limpar_ordenamento_em_lote(session, 'subgrupo', ids_hierarquia)
            
            # Deleta vínculos
            session.query(DreContaVinculo).filter(
                DreContaVinculo.Id_Hierarquia.in_(ids_hierarquia)
            ).delete(synchronize_session=False)
            
            session.query(DreContaPersonalizada).filter(
                DreContaPersonalizada.Id_Hierarquia.in_(ids_hierarquia)
            ).delete(synchronize_session=False)
            
            # Deleta subgrupos
            session.query(DreHierarquia).filter(
                DreHierarquia.Id.in_(ids_hierarquia)
            ).delete(synchronize_session=False)

        # 2. Contas personalizadas diretas no Nó Virtual
        contas_diretas = session.query(DreContaPersonalizada.Id).filter_by(
            Id_No_Virtual=virt_id
        ).all()
        
        for (cd_id,) in contas_diretas:
            limpar_ordenamento(session, 'conta_detalhe', str(cd_id))
        
        session.query(DreContaPersonalizada).filter_by(Id_No_Virtual=virt_id).delete()

        # 3. Limpa ordenamento do contexto e do próprio nó
        limpar_ordenamento_por_contexto(session, f'virt_{virt_id}')
        limpar_ordenamento(session, 'virtual', str(virt_id))

        # 4. Deleta o Nó Virtual
        session.query(DreNoVirtual).filter_by(Id=virt_id).delete()
        
        session.commit()
        return jsonify({"success": True, "msg": "Estrutura virtual excluída."}), 200

    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


# ============================================================
# SEÇÃO 7: ROTAS DE OPERAÇÕES EM MASSA
# ============================================================

@dre_config_bp.route('/Configuracao/VincularContaEmMassa', methods=['POST'])
@login_required
def VincularContaEmMassa():
    """Vincula conta em massa para todos os CCs de um tipo."""
    session = get_session()
    try:
        data = request.json
        tipo_cc = data.get('tipo_cc')       
        nome_subgrupo = data.get('nome_subgrupo') 
        conta = str(data.get('conta')).strip()    
        is_personalizada = data.get('is_personalizada', False)
        nome_personalizado_conta = data.get('nome_personalizado_conta')

        if not all([tipo_cc, nome_subgrupo, conta]):
            return jsonify({"error": "Dados incompletos."}), 400

        subgrupos_alvo = session.query(DreHierarquia).filter(
            DreHierarquia.Raiz_Centro_Custo_Tipo == tipo_cc,
            DreHierarquia.Nome == nome_subgrupo
        ).all()

        if not subgrupos_alvo:
            return jsonify({"error": "Nenhum subgrupo encontrado."}), 404

        count_sucesso = 0

        for sg in subgrupos_alvo:
            if is_personalizada:
                nome_final = nome_personalizado_conta 
                
                if not nome_final:
                    sql_nome = text('SELECT "Título Conta" FROM "Dre_Schema"."Razao_Dados_Consolidado" WHERE "Conta"=:c LIMIT 1')
                    res = session.execute(sql_nome, {'c': conta}).first()
                    nome_final = res[0] if res else "Sem Nome"

                conta_pers = session.query(DreContaPersonalizada).filter_by(
                    Id_Hierarquia=sg.Id,
                    Conta_Contabil=conta
                ).first()

                if conta_pers:
                    conta_pers.Nome_Personalizado = nome_final
                else:
                    novo_p = DreContaPersonalizada(
                        Conta_Contabil=conta,
                        Nome_Personalizado=nome_final,
                        Id_Hierarquia=sg.Id,
                        Id_No_Virtual=None
                    )
                    session.add(novo_p)
                
                count_sucesso += 1

            else:
                cc_code = sg.Raiz_Centro_Custo_Codigo
                if cc_code is None: 
                    continue

                chave_tipo = f"{conta}{tipo_cc}"
                chave_cod = f"{conta}{cc_code}"

                vinculo = session.query(DreContaVinculo).filter_by(
                    Chave_Conta_Codigo_CC=chave_cod
                ).first()

                if vinculo:
                    if vinculo.Id_Hierarquia != sg.Id:
                        vinculo.Id_Hierarquia = sg.Id
                        vinculo.Chave_Conta_Tipo_CC = chave_tipo
                        count_sucesso += 1
                else:
                    novo_v = DreContaVinculo(
                        Conta_Contabil=conta,
                        Id_Hierarquia=sg.Id,
                        Chave_Conta_Tipo_CC=chave_tipo,
                        Chave_Conta_Codigo_CC=chave_cod
                    )
                    session.add(novo_v)
                    count_sucesso += 1

        session.commit()
        
        msg_extra = f" com nome '{nome_personalizado_conta}'" if is_personalizada and nome_personalizado_conta else ""
        return jsonify({
            "success": True, 
            "msg": f"Conta {conta} vinculada em {count_sucesso} locais{msg_extra}."
        }), 200

    except Exception as e:
        session.rollback()
        if "UniqueViolation" in str(e):
            return jsonify({"error": "Erro de duplicidade: Execute a rota de correção de banco primeiro."}), 500
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/DesvincularContaEmMassa', methods=['POST'])
@login_required
def DesvincularContaEmMassa():
    """
    Remove vínculo em massa.
    LIMPA O ORDENAMENTO!
    """
    session = get_session()
    try:
        data = request.json
        tipo_cc = data.get('tipo_cc')
        conta = str(data.get('conta')).strip()
        is_personalizada = data.get('is_personalizada', False)

        if not tipo_cc or not conta:
            return jsonify({"error": "Dados inválidos"}), 400

        count = 0

        if is_personalizada:
            subgrupos_ids = session.query(DreHierarquia.Id).filter(
                DreHierarquia.Raiz_Centro_Custo_Tipo == tipo_cc
            ).all()
            ids = [s.Id for s in subgrupos_ids]
            
            if ids:
                # Busca IDs das contas personalizadas para limpar ordenamento
                contas_para_limpar = session.query(DreContaPersonalizada.Id).filter(
                    DreContaPersonalizada.Conta_Contabil == conta,
                    DreContaPersonalizada.Id_Hierarquia.in_(ids)
                ).all()
                
                for (cd_id,) in contas_para_limpar:
                    limpar_ordenamento(session, 'conta_detalhe', str(cd_id))
                
                res = session.query(DreContaPersonalizada).filter(
                    DreContaPersonalizada.Conta_Contabil == conta,
                    DreContaPersonalizada.Id_Hierarquia.in_(ids)
                ).delete(synchronize_session=False)
                count = res
        else:
            # Limpa ordenamento da conta
            limpar_ordenamento(session, 'conta', conta)
            
            chave_tipo = f"{conta}{tipo_cc}"
            res = session.query(DreContaVinculo).filter_by(
                Chave_Conta_Tipo_CC=chave_tipo
            ).delete()
            count = res

        session.commit()
        
        return jsonify({
            "success": True, 
            "msg": f"Vínculo da conta {conta} removido de {count} locais."
        }), 200

    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/DeleteSubgrupoEmMassa', methods=['POST'])
@login_required
def DeleteSubgrupoEmMassa():
    """
    Deleta um subgrupo pelo NOME em todos os CCs de um TIPO.
    DELETE EM CASCATA incluindo ORDENAMENTO.
    """
    session = get_session()
    try:
        data = request.json
        tipo_cc = data.get('tipo_cc')
        nome_grupo = data.get('nome_grupo')

        if not tipo_cc or not nome_grupo:
            return jsonify({"error": "Parâmetros inválidos"}), 400

        grupos_alvo = session.query(DreHierarquia).filter(
            DreHierarquia.Raiz_Centro_Custo_Tipo == tipo_cc,
            DreHierarquia.Nome == nome_grupo,
            DreHierarquia.Id_Pai == None
        ).all()

        if not grupos_alvo:
            return jsonify({"error": "Nenhum grupo encontrado com esse nome."}), 404

        ids_para_deletar = [g.Id for g in grupos_alvo]
        todos_ids_envolvidos = get_all_child_ids(session, ids_para_deletar)

        if todos_ids_envolvidos:
            # Coleta contas para limpeza
            contas_vinculadas = session.query(DreContaVinculo.Conta_Contabil).filter(
                DreContaVinculo.Id_Hierarquia.in_(todos_ids_envolvidos)
            ).all()
            
            contas_personalizadas = session.query(DreContaPersonalizada.Id).filter(
                DreContaPersonalizada.Id_Hierarquia.in_(todos_ids_envolvidos)
            ).all()
            
            # Limpa ordenamento das contas
            for (conta,) in contas_vinculadas:
                limpar_ordenamento(session, 'conta', conta)
            
            for (cd_id,) in contas_personalizadas:
                limpar_ordenamento(session, 'conta_detalhe', str(cd_id))
            
            # Limpa ordenamento dos subgrupos
            limpar_ordenamento_em_lote(session, 'subgrupo', todos_ids_envolvidos)
            
            # Limpa ordenamento dos contextos
            for sg_id in todos_ids_envolvidos:
                limpar_ordenamento_por_contexto(session, f'sg_{sg_id}')

            # Deleta dados
            session.query(DreContaVinculo).filter(
                DreContaVinculo.Id_Hierarquia.in_(todos_ids_envolvidos)
            ).delete(synchronize_session=False)

            session.query(DreContaPersonalizada).filter(
                DreContaPersonalizada.Id_Hierarquia.in_(todos_ids_envolvidos)
            ).delete(synchronize_session=False)

            session.query(DreHierarquia).filter(
                DreHierarquia.Id.in_(todos_ids_envolvidos)
            ).delete(synchronize_session=False)
        
        session.commit()
        
        return jsonify({
            "success": True, 
            "msg": f"Exclusão em massa concluída! Grupos e vínculos removidos de {len(grupos_alvo)} locais."
        }), 200

    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


# ============================================================
# SEÇÃO 8: ROTAS DE REPLICAÇÃO/CLONAGEM
# ============================================================

@dre_config_bp.route('/Configuracao/ReplicarEstrutura', methods=['POST'])
@login_required
def ReplicarEstrutura():
    """Replica uma estrutura completa para múltiplos destinos."""
    session = get_session()
    try:
        data = request.json
        origem_node_id = data.get('origem_node_id')
        destinos_ids = data.get('destinos_ids', [])

        if not destinos_ids:
            return jsonify({"error": "Selecione ao menos um destino."}), 400

        # Identifica origem
        itens_para_clonar = []
        tipo_origem = ""

        if origem_node_id.startswith("cc_"):
            cc_id = int(origem_node_id.replace("cc_", ""))
            itens_para_clonar = session.query(DreHierarquia).filter_by(
                Raiz_Centro_Custo_Codigo=cc_id, 
                Id_Pai=None
            ).all()
            tipo_origem = 'CC'
            
        elif origem_node_id.startswith("virt_"):
            virt_id = int(origem_node_id.replace("virt_", ""))
            itens_para_clonar = session.query(DreHierarquia).filter_by(
                Raiz_No_Virtual_Id=virt_id, 
                Id_Pai=None
            ).all()
            tipo_origem = 'VIRT'
            
        elif origem_node_id.startswith("sg_"):
            sg_id = int(origem_node_id.replace("sg_", ""))
            subgrupo = session.query(DreHierarquia).get(sg_id)
            
            if subgrupo:
                itens_para_clonar = [subgrupo]
                if subgrupo.Raiz_Centro_Custo_Codigo: 
                    tipo_origem = 'SUB_CC'
                elif subgrupo.Raiz_No_Virtual_Id: 
                    tipo_origem = 'SUB_VIRT'

        if not itens_para_clonar:
            return jsonify({"error": "Não há itens para clonar na origem selecionada."}), 400

        def clonar_recursivo(sub_origem, novo_pai_id, target_cc_code=None, 
                           target_virt_id=None, target_virt_nome=None):
            target_cc_tipo = None
            target_cc_nome = None
            
            if target_cc_code:
                sql_cc = text("""
                    SELECT "Tipo", "Nome" 
                    FROM "Dre_Schema"."Classificacao_Centro_Custo" 
                    WHERE "Codigo" = :cod
                """)
                res_cc = session.execute(sql_cc, {"cod": target_cc_code}).first()
                if res_cc:
                    target_cc_tipo = res_cc[0]
                    target_cc_nome = res_cc[1]

            novo_sub = DreHierarquia(
                Nome=sub_origem.Nome,
                Id_Pai=novo_pai_id,
                Raiz_Centro_Custo_Codigo=target_cc_code,
                Raiz_Centro_Custo_Tipo=target_cc_tipo,
                Raiz_Centro_Custo_Nome=target_cc_nome,
                Raiz_No_Virtual_Id=target_virt_id,
                Raiz_No_Virtual_Nome=target_virt_nome
            )
            session.add(novo_sub)
            session.flush()

            # Copia Vínculos
            vinculos = session.query(DreContaVinculo).filter_by(
                Id_Hierarquia=sub_origem.Id
            ).all()
            
            for v in vinculos:
                chave_cod = None
                chave_tipo = None
                
                if target_cc_code:
                    chave_cod = f"{v.Conta_Contabil}{target_cc_code}"
                    chave_tipo = f"{v.Conta_Contabil}{target_cc_tipo}"
                elif target_virt_id:
                    chave_cod = f"{v.Conta_Contabil}VIRTUAL{target_virt_id}"
                    chave_tipo = f"{v.Conta_Contabil}Virtual"

                existe = session.query(DreContaVinculo).filter_by(
                    Chave_Conta_Codigo_CC=chave_cod
                ).first()
                
                if not existe and chave_cod:
                    novo_v = DreContaVinculo(
                        Conta_Contabil=v.Conta_Contabil,
                        Id_Hierarquia=novo_sub.Id,
                        Chave_Conta_Tipo_CC=chave_tipo,
                        Chave_Conta_Codigo_CC=chave_cod
                    )
                    session.add(novo_v)

            # Copia Contas Detalhe
            if target_virt_id:
                detalhes = session.query(DreContaPersonalizada).filter_by(
                    Id_Hierarquia=sub_origem.Id
                ).all()
                
                for d in detalhes:
                    novo_d = DreContaPersonalizada(
                        Conta_Contabil=d.Conta_Contabil,
                        Nome_Personalizado=d.Nome_Personalizado,
                        Id_Hierarquia=novo_sub.Id,
                        Id_No_Virtual=None
                    )
                    session.add(novo_d)

            # Recursão
            filhos = session.query(DreHierarquia).filter_by(
                Id_Pai=sub_origem.Id
            ).all()
            
            for filho in filhos:
                clonar_recursivo(
                    filho, 
                    novo_sub.Id, 
                    target_cc_code, 
                    target_virt_id, 
                    target_virt_nome
                )

        count_sucesso = 0
        
        for dest_id in destinos_ids:
            dest_id = int(dest_id)
            
            t_cc = None
            t_virt_id = None
            t_virt_nome = None

            if tipo_origem in ['CC', 'SUB_CC']:
                t_cc = dest_id
            elif tipo_origem in ['VIRT', 'SUB_VIRT']:
                t_virt_id = dest_id
                no_virt = session.query(DreNoVirtual).get(dest_id)
                if no_virt: 
                    t_virt_nome = no_virt.Nome

            for item in itens_para_clonar:
                filtro_existente = {
                    'Nome': item.Nome,
                    'Id_Pai': None
                }
                if t_cc: 
                    filtro_existente['Raiz_Centro_Custo_Codigo'] = t_cc
                if t_virt_id: 
                    filtro_existente['Raiz_No_Virtual_Id'] = t_virt_id
                
                existe = session.query(DreHierarquia).filter_by(**filtro_existente).first()
                
                if not existe:
                    clonar_recursivo(item, None, t_cc, t_virt_id, t_virt_nome)
            
            count_sucesso += 1

        session.commit()
        return jsonify({
            "success": True, 
            "msg": f"Estrutura replicada com sucesso para {count_sucesso} destinos!"
        }), 200

    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/ColarEstrutura', methods=['POST'])
@login_required
def ColarEstrutura():
    """Cola (Deep Copy) uma estrutura de subgrupo em outro local."""
    session = get_session()
    try:
        data = request.json
        origem_id_str = data.get('origem_id')
        destino_id_str = data.get('destino_id')

        if not origem_id_str or not destino_id_str:
            return jsonify({"error": "Origem ou Destino inválidos."}), 400

        # Identificar ORIGEM
        subgrupo_origem = None
        
        if origem_id_str.startswith("sg_"):
            sg_id = int(origem_id_str.replace("sg_", ""))
            subgrupo_origem = session.query(DreHierarquia).get(sg_id)
        else:
            return jsonify({"error": "Apenas Subgrupos podem ser copiados/colados."}), 400

        if not subgrupo_origem:
            return jsonify({"error": "Grupo de origem não encontrado."}), 404

        # Identificar DESTINO
        novo_pai_id = None
        target_cc_code = None
        target_cc_tipo = None
        target_cc_nome = None
        target_virt_id = None
        target_virt_nome = None

        if destino_id_str.startswith("cc_"):
            target_cc_code = int(destino_id_str.replace("cc_", ""))
            novo_pai_id = None
            
            sql_cc = text("""
                SELECT "Tipo", "Nome" 
                FROM "Dre_Schema"."Classificacao_Centro_Custo" 
                WHERE "Codigo" = :cod
            """)
            res_cc = session.execute(sql_cc, {"cod": target_cc_code}).first()
            if res_cc:
                target_cc_tipo = res_cc[0]
                target_cc_nome = res_cc[1]

        elif destino_id_str.startswith("virt_"):
            target_virt_id = int(destino_id_str.replace("virt_", ""))
            novo_pai_id = None
            no_virt = session.query(DreNoVirtual).get(target_virt_id)
            if no_virt: 
                target_virt_nome = no_virt.Nome

        elif destino_id_str.startswith("sg_"):
            novo_pai_id = int(destino_id_str.replace("sg_", ""))
            pai_destino = session.query(DreHierarquia).get(novo_pai_id)
            
            if pai_destino:
                target_cc_code = pai_destino.Raiz_Centro_Custo_Codigo
                target_cc_tipo = pai_destino.Raiz_Centro_Custo_Tipo
                target_cc_nome = pai_destino.Raiz_Centro_Custo_Nome
                target_virt_id = pai_destino.Raiz_No_Virtual_Id
                target_virt_nome = pai_destino.Raiz_No_Virtual_Nome
        
        if novo_pai_id == subgrupo_origem.Id:
            return jsonify({"error": "Não é possível colar um grupo dentro dele mesmo."}), 400

        def clonar_recursivo(sub_source, id_pai_novo):
            novo_sub = DreHierarquia(
                Nome=sub_source.Nome,
                Id_Pai=id_pai_novo,
                Raiz_Centro_Custo_Codigo=target_cc_code,
                Raiz_Centro_Custo_Tipo=target_cc_tipo,
                Raiz_Centro_Custo_Nome=target_cc_nome,
                Raiz_No_Virtual_Id=target_virt_id,
                Raiz_No_Virtual_Nome=target_virt_nome
            )
            session.add(novo_sub)
            session.flush()

            # Copia Vínculos
            vinculos = session.query(DreContaVinculo).filter_by(
                Id_Hierarquia=sub_source.Id
            ).all()
            
            for v in vinculos:
                chave_cod = None
                chave_tipo = None
                
                if target_cc_code:
                    chave_cod = f"{v.Conta_Contabil}{target_cc_code}"
                    chave_tipo = f"{v.Conta_Contabil}{target_cc_tipo}"
                elif target_virt_id:
                    chave_cod = f"{v.Conta_Contabil}VIRTUAL{target_virt_id}"
                    chave_tipo = f"{v.Conta_Contabil}Virtual"

                existe = session.query(DreContaVinculo).filter_by(
                    Chave_Conta_Codigo_CC=chave_cod
                ).first()
                
                if not existe and chave_cod:
                    novo_v = DreContaVinculo(
                        Conta_Contabil=v.Conta_Contabil,
                        Id_Hierarquia=novo_sub.Id,
                        Chave_Conta_Tipo_CC=chave_tipo,
                        Chave_Conta_Codigo_CC=chave_cod
                    )
                    session.add(novo_v)

            # Copia Contas Detalhe
            detalhes = session.query(DreContaPersonalizada).filter_by(
                Id_Hierarquia=sub_source.Id
            ).all()
            
            for d in detalhes:
                novo_d = DreContaPersonalizada(
                    Conta_Contabil=d.Conta_Contabil,
                    Nome_Personalizado=d.Nome_Personalizado,
                    Id_Hierarquia=novo_sub.Id,
                    Id_No_Virtual=None
                )
                session.add(novo_d)

            # Recursão
            filhos = session.query(DreHierarquia).filter_by(
                Id_Pai=sub_source.Id
            ).all()
            
            for filho in filhos:
                clonar_recursivo(filho, novo_sub.Id)

        clonar_recursivo(subgrupo_origem, novo_pai_id)
        
        session.commit()
        return jsonify({"success": True}), 200

    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


# ============================================================
# SEÇÃO 9: ROTAS UTILITÁRIAS (CORREÇÕES/TESTES)
# ============================================================

@dre_config_bp.route('/Configuracao/CorrigirBanco', methods=['GET'])
def CorrigirBanco():
    """Remove a constraint antiga que bloqueia duplicidade de contas."""
    session = get_session()
    try:
        sql_drop = text("""
            ALTER TABLE "Dre_Schema"."DRE_Estrutura_Conta_Vinculo" 
            DROP CONSTRAINT IF EXISTS "DRE_Estrutura_Conta_Vinculo_Conta_Contabil_key";
        """)
        session.execute(sql_drop)
        session.commit()
        return jsonify({"success": True, "msg": "Banco corrigido! Agora você pode vincular contas em massa."}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/CorrigirConstraintPersonalizada', methods=['GET'])
def CorrigirConstraintPersonalizada():
    """Corrige constraint de contas personalizadas."""
    session = get_session()
    try:
        session.execute(text("""
            ALTER TABLE "Dre_Schema"."DRE_Estrutura_Conta_Personalizada" 
            DROP CONSTRAINT IF EXISTS "DRE_Estrutura_Conta_Personalizada_Conta_Contabil_key";
        """))
        
        session.execute(text("""
            ALTER TABLE "Dre_Schema"."DRE_Estrutura_Conta_Personalizada" 
            DROP CONSTRAINT IF EXISTS "uq_personalizada_grupo";
        """))
        
        session.execute(text("""
            ALTER TABLE "Dre_Schema"."DRE_Estrutura_Conta_Personalizada" 
            ADD CONSTRAINT "uq_personalizada_grupo" UNIQUE ("Conta_Contabil", "Id_Hierarquia");
        """))

        session.commit()
        return jsonify({"success": True, "msg": "Banco corrigido! Agora uma conta pode ser personalizada em múltiplos grupos."}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Teste/VerificarTabelaNoVirtual', methods=['GET'])
@login_required
def TesteVerificarTabelaNoVirtual():
    """Testa a existência da tabela DRE_Estrutura_No_Virtual."""
    session = get_session()
    resultados = {}
    
    try:
        sql_check = text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'Dre_Schema' 
            AND table_name = 'DRE_Estrutura_No_Virtual'
        """)
        result_sql = session.execute(sql_check).fetchone()
        resultados['sql_direto'] = {
            'existe': result_sql is not None,
            'resultado': result_sql[0] if result_sql else None
        }
        
        sql_todas = text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'Dre_Schema'
            ORDER BY table_name
        """)
        todas_tabelas = session.execute(sql_todas).fetchall()
        resultados['todas_tabelas_schema'] = [t[0] for t in todas_tabelas]
        
        try:
            count = session.query(DreNoVirtual).count()
            resultados['sqlalchemy_orm'] = {
                'sucesso': True,
                'count': count
            }
        except Exception as e_orm:
            resultados['sqlalchemy_orm'] = {
                'sucesso': False,
                'erro': str(e_orm)
            }
        
        sql_case = text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'Dre_Schema' 
            AND lower(table_name) LIKE '%virtual%'
        """)
        result_case = session.execute(sql_case).fetchall()
        resultados['tabelas_com_virtual'] = [t[0] for t in result_case]
        
        sql_colunas = text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'Dre_Schema' 
            AND table_name = 'DRE_Estrutura_No_Virtual'
            ORDER BY ordinal_position
        """)
        colunas = session.execute(sql_colunas).fetchall()
        resultados['colunas_tabela'] = [{'nome': c[0], 'tipo': c[1]} for c in colunas]
        
        return jsonify(resultados), 200
        
    except Exception as e:
        return jsonify({"error": str(e), "resultados_parciais": resultados}), 500
    finally:
        session.close()