"""
Routes/DreConfig.py - VERSÃO OTIMIZADA
Rotas para Configuração da Árvore DRE (Demonstração do Resultado do Exercício)
"""

from flask import Blueprint, jsonify, request, render_template, json
from flask_login import login_required
from sqlalchemy import text, func
from sqlalchemy.orm import sessionmaker, joinedload
from functools import lru_cache
import time

from Db.Connections import GetPostgresEngine

# --- NOVOS IMPORTS DE MODELS ---
from Models.POSTGRESS.CTL_Dre_Estrutura import (
    CtlDreContaVinculo, 
    CtlDreNoVirtual, 
    CtlDreHierarquia, 
    CtlDreContaPersonalizada
)
from Models.POSTGRESS.CTL_Dre_Ordenamento import CtlDreOrdenamento, calcular_proxima_ordem

dre_config_bp = Blueprint('DreConfig', __name__)

# ============================================================
# SEÇÃO 1: FUNÇÕES AUXILIARES OTIMIZADAS
# ============================================================

def get_session():
    """Cria e retorna uma sessão do PostgreSQL."""
    engine = GetPostgresEngine()
    Session = sessionmaker(bind=engine)
    return Session()


def limpar_ordenamento_bulk(session, items: list):
    if not items:
        return
    by_type = {}
    for tipo, id_ref in items:
        if tipo not in by_type:
            by_type[tipo] = []
        by_type[tipo].append(str(id_ref))
    
    for tipo, ids in by_type.items():
        session.query(CtlDreOrdenamento).filter(
            CtlDreOrdenamento.tipo_no == tipo,
            CtlDreOrdenamento.id_referencia.in_(ids)
        ).delete(synchronize_session=False)

def limpar_ordenamento_por_contextos(session, contextos: list):
    if not contextos:
        return
    session.query(CtlDreOrdenamento).filter(
        CtlDreOrdenamento.contexto_pai.in_(contextos)
    ).delete(synchronize_session=False)

def gerar_descricao_formula(formula: dict) -> str:
    operacoes = {"soma": "+", "subtracao": "-", "multiplicacao": "×", "divisao": "÷"}
    op = formula.get('operacao', 'soma')
    operandos = formula.get('operandos', [])
    simbolo = operacoes.get(op, '+')
    labels = [str(operando.get('label') or operando.get('id', '?')) for operando in operandos]
    descricao = f" {simbolo} ".join(labels)
    if formula.get('multiplicador'):
        descricao = f"({descricao}) × {formula['multiplicador']}"
    return descricao


# ============================================================
# SEÇÃO 2: ROTAS DE VISUALIZAÇÃO (VIEWS/TEMPLATES)
# ============================================================

@dre_config_bp.route('/Configuracao/Arvore', methods=['GET'])
@login_required
def ViewConfiguracao():
    return render_template('CONFIGS/ConfigsDRE.html')


# ============================================================
# SEÇÃO 3: ROTAS DE CONSULTA OTIMIZADAS
# ============================================================

@dre_config_bp.route('/Configuracao/GetDadosArvore', methods=['GET'])
@login_required
def GetDadosArvore():
    session = get_session()
    try:
        start = time.time()
        
        # --- ATUALIZADO ---
        sql_base = text("""
            SELECT DISTINCT "Tipo", "Nome", "Codigo" 
            FROM "Dre_Schema"."Tb_CTL_Cad_Centro_Custo"
            WHERE "Codigo" IS NOT NULL
            ORDER BY "Tipo", "Nome"
        """)
        base_result = session.execute(sql_base).mappings().all()

        subgrupos = session.query(CtlDreHierarquia).all()
        vinculos = session.query(CtlDreContaVinculo).all()
        virtuais = session.query(CtlDreNoVirtual).order_by(CtlDreNoVirtual.Ordem).all()
        contas_detalhe = session.query(CtlDreContaPersonalizada).all()
        
        # --- ATUALIZADO ---
        sql_nomes = text("""
            SELECT DISTINCT "Conta", "Título Conta"
            FROM "Dre_Schema"."Vw_CTL_Razao_Consolidado"
            WHERE "Conta" IS NOT NULL
        """)
        res_nomes = session.execute(sql_nomes).fetchall()
        mapa_nomes_contas = {str(row[0]): row[1] for row in res_nomes}

        vinculos_por_hierarquia = {}
        for v in vinculos:
            if v.Id_Hierarquia not in vinculos_por_hierarquia:
                vinculos_por_hierarquia[v.Id_Hierarquia] = []
            vinculos_por_hierarquia[v.Id_Hierarquia].append(v)
        
        detalhe_por_hierarquia = {}
        detalhe_por_virtual = {}
        for c in contas_detalhe:
            if c.Id_Hierarquia:
                if c.Id_Hierarquia not in detalhe_por_hierarquia:
                    detalhe_por_hierarquia[c.Id_Hierarquia] = []
                detalhe_por_hierarquia[c.Id_Hierarquia].append(c)
            if c.Id_No_Virtual:
                if c.Id_No_Virtual not in detalhe_por_virtual:
                    detalhe_por_virtual[c.Id_No_Virtual] = []
                detalhe_por_virtual[c.Id_No_Virtual].append(c)
        
        subgrupos_por_pai = {}
        subgrupos_por_cc = {}
        subgrupos_por_virtual = {}
        subgrupos_raiz_global = []
        
        for sg in subgrupos:
            if sg.Id_Pai:
                if sg.Id_Pai not in subgrupos_por_pai:
                    subgrupos_por_pai[sg.Id_Pai] = []
                subgrupos_por_pai[sg.Id_Pai].append(sg)
            elif sg.Raiz_Centro_Custo_Codigo:
                if sg.Raiz_Centro_Custo_Codigo not in subgrupos_por_cc:
                    subgrupos_por_cc[sg.Raiz_Centro_Custo_Codigo] = []
                subgrupos_por_cc[sg.Raiz_Centro_Custo_Codigo].append(sg)
            elif sg.Raiz_No_Virtual_Id:
                if sg.Raiz_No_Virtual_Id not in subgrupos_por_virtual:
                    subgrupos_por_virtual[sg.Raiz_No_Virtual_Id] = []
                subgrupos_por_virtual[sg.Raiz_No_Virtual_Id].append(sg)
            else:
                subgrupos_raiz_global.append(sg)

        def get_contas_normais(sub_id):
            lista = []
            for v in vinculos_por_hierarquia.get(sub_id, []):
                conta_num = str(v.Conta_Contabil)
                nome_conta = mapa_nomes_contas.get(conta_num, "Sem Título")
                lista.append({
                    "id": f"conta_{conta_num}", 
                    "text": f"Conta: {conta_num} - {nome_conta}",
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
                for c in detalhe_por_hierarquia.get(sub_id, [])
            ]

        def get_children_subgrupos(parent_id):
            children = []
            for sg in subgrupos_por_pai.get(parent_id, []):
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

        final_tree = []

        for gr in subgrupos_raiz_global:
            node = {
                "id": f"sg_{gr.Id}", "db_id": gr.Id, "text": gr.Nome, "type": "subgrupo", "parent": "root",
                "children": (get_children_subgrupos(gr.Id) + get_contas_normais(gr.Id) + get_contas_detalhe(gr.Id))
            }
            final_tree.append(node)

        for v in virtuais:
            children_virtual = []
            for sg in subgrupos_por_virtual.get(v.Id, []):
                contas_do_grupo = (get_children_subgrupos(sg.Id) + get_contas_detalhe(sg.Id) + get_contas_normais(sg.Id))
                node = {"id": f"sg_{sg.Id}", "db_id": sg.Id, "text": sg.Nome, "type": "subgrupo", "children": contas_do_grupo}
                children_virtual.append(node)

            for c in detalhe_por_virtual.get(v.Id, []):
                label = f"{c.Conta_Contabil} ({c.Nome_Personalizado or ''})"
                children_virtual.append({"id": f"cd_{c.Id}", "text": label, "type": "conta_detalhe", "parent": f"virt_{v.Id}"})
            
            node_virtual = {
                "id": f"virt_{v.Id}", "text": v.Nome, "type": "root_virtual", "is_calculado": v.Is_Calculado,
                "estilo_css": v.Estilo_CSS, "children": children_virtual
            }
            final_tree.append(node_virtual)

        tipos_map = {}
        for row in base_result:
            tipo, nome_cc, codigo_cc = row['Tipo'], row['Nome'], row['Codigo']
            label_cc = f"{codigo_cc} - {nome_cc}"
            
            if tipo not in tipos_map:
                tipos_map[tipo] = {"id": f"tipo_{tipo}", "text": tipo, "type": "root_tipo", "children": []}
            
            children_do_cc = []
            for sg in subgrupos_por_cc.get(codigo_cc, []):
                node = {
                    "id": f"sg_{sg.Id}", "db_id": sg.Id, "text": sg.Nome, "type": "subgrupo", 
                    "children": (get_children_subgrupos(sg.Id) + get_contas_normais(sg.Id) + get_contas_detalhe(sg.Id))
                }
                children_do_cc.append(node)

            node_cc = {"id": f"cc_{codigo_cc}", "text": label_cc, "type": "root_cc", "children": children_do_cc}
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
    session = get_session()
    try:
        # --- ATUALIZADO ---
        sql = text("""
            SELECT "Conta", "Título Conta"
            FROM (
                SELECT DISTINCT ON ("Conta") "Conta", "Título Conta"
                FROM "Dre_Schema"."Vw_CTL_Razao_Consolidado"
                WHERE "Conta" IS NOT NULL
                ORDER BY "Conta" ASC, "Título Conta" ASC
            ) sub
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
    session = get_session()
    try:
        data = request.json
        raw_id = data.get('id')
        if not raw_id: return jsonify([]), 200
        try: sg_id = int(raw_id)
        except ValueError: return jsonify([]), 200

        # --- ATUALIZADO ---
        sql = text("""
            SELECT "Conta_Contabil" 
            FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo"
            WHERE "Id_Hierarquia" = :sg_id
        """)
        result = session.execute(sql, {"sg_id": sg_id}).fetchall()
        return jsonify([str(row[0]) for row in result]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/GetSubgruposPorTipo', methods=['POST'])
@login_required
def GetSubgruposPorTipo():
    session = get_session()
    try:
        tipo_cc = request.json.get('tipo_cc') 
        # --- ATUALIZADO ---
        sql = text("""
            SELECT DISTINCT h."Nome", COALESCE(MIN(ord.ordem), 999999) as min_ordem
            FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h
            LEFT JOIN "Dre_Schema"."Tb_CTL_Dre_Ordenamento" ord 
                ON ord.tipo_no = 'subgrupo' 
                AND ord.id_referencia = CAST(h."Id" AS TEXT)
            WHERE h."Raiz_Centro_Custo_Tipo" = :tipo
            GROUP BY h."Nome"
            ORDER BY min_ordem ASC, h."Nome" ASC
        """)
        rows = session.execute(sql, {'tipo': tipo_cc}).fetchall()
        return jsonify([r[0] for r in rows]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/GetContasDoGrupoMassa', methods=['POST'])
@login_required
def GetContasDoGrupoMassa():
    session = get_session()
    try:
        tipo_cc = request.json.get('tipo_cc')
        nome_grupo = request.json.get('nome_grupo')
        if not tipo_cc or not nome_grupo: return jsonify([]), 200

        # --- ATUALIZADO ---
        sql = text("""
            WITH subgrupos_alvo AS (
                SELECT "Id" FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia"
                WHERE "Raiz_Centro_Custo_Tipo" = :tipo AND "Nome" = :nome
            )
            SELECT conta, tipo, nome_personalizado FROM (
                SELECT DISTINCT v."Conta_Contabil" as conta, 'padrao' as tipo, NULL as nome_personalizado
                FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" v
                WHERE v."Id_Hierarquia" IN (SELECT "Id" FROM subgrupos_alvo)
                
                UNION ALL
                
                SELECT DISTINCT p."Conta_Contabil" as conta, 'personalizada' as tipo, p."Nome_Personalizado" as nome_personalizado
                FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" p
                WHERE p."Id_Hierarquia" IN (SELECT "Id" FROM subgrupos_alvo)
            ) combined
            ORDER BY conta ASC
        """)
        result = session.execute(sql, {'tipo': tipo_cc, 'nome': nome_grupo}).fetchall()
        lista_final = [{"conta": row[0], "tipo": row[1], "nome_personalizado": row[2]} for row in result]
        return jsonify(lista_final), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/GetNosCalculados', methods=['GET'])
@login_required
def GetNosCalculados():
    session = get_session()
    try:
        # --- ATUALIZADO ---
        sql = text("""
            SELECT "Id", "Nome", "Ordem", "Formula_JSON", "Formula_Descricao", 
                   "Tipo_Exibicao", "Estilo_CSS"
            FROM "Dre_Schema"."Tb_CTL_Dre_No_Virtual"
            WHERE "Is_Calculado" = true
            ORDER BY "Ordem" ASC
        """)
        result = session.execute(sql).fetchall()
        nos = [{"id": n[0], "nome": n[1], "ordem": n[2], "formula": json.loads(n[3]) if n[3] else None, 
                "formula_descricao": n[4], "tipo_exibicao": n[5], "estilo_css": n[6]} for n in result]
        return jsonify(nos), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@dre_config_bp.route('/Configuracao/GetOperandosDisponiveis', methods=['GET'])
@login_required
def GetOperandosDisponiveis():
    session = get_session()
    try:
        resultado = {"nos_virtuais": [], "tipos_cc": [], "subgrupos_raiz": []}
        
        # --- ATUALIZADO ---
        sql_virtuais = text('SELECT "Id", "Nome", "Is_Calculado" FROM "Dre_Schema"."Tb_CTL_Dre_No_Virtual" ORDER BY "Ordem" ASC')
        for row in session.execute(sql_virtuais).fetchall():
            resultado["nos_virtuais"].append({"id": row[0], "nome": row[1], "is_calculado": row[2]})
        
        sql_tipos = text('SELECT DISTINCT "Tipo" FROM "Dre_Schema"."Tb_CTL_Cad_Centro_Custo" WHERE "Tipo" IS NOT NULL ORDER BY "Tipo"')
        for row in session.execute(sql_tipos).fetchall():
            resultado["tipos_cc"].append({"id": row[0], "nome": row[0]})
        
        sql_subgrupos = text('SELECT DISTINCT "Nome" FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" WHERE "Id_Pai" IS NULL ORDER BY "Nome"')
        for row in session.execute(sql_subgrupos).fetchall():
            resultado["subgrupos_raiz"].append({"id": row[0], "nome": row[0]})
        
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


# ============================================================
# SEÇÃO 4: ROTAS DE CRIAÇÃO (ADD) - OTIMIZADAS
# ============================================================

@dre_config_bp.route('/Configuracao/AddSubgrupo', methods=['POST'])
@login_required
def AddSubgrupo():
    session = get_session()
    try:
        data = request.json
        nome = data.get('nome')
        parent_node_id = str(data.get('parent_id')) 

        if not nome: return jsonify({"error": "Nome do grupo é obrigatório"}), 400

        novo_sub = CtlDreHierarquia(Nome=nome)
        contexto_pai_ordem = ""
        nivel = 3

        if parent_node_id == 'root':
            novo_sub.Id_Pai = None
            novo_sub.Raiz_Centro_Custo_Codigo = None
            novo_sub.Raiz_No_Virtual_Id = None
            contexto_pai_ordem = "root"
            nivel = 0
            duplicado = session.query(CtlDreHierarquia.Id).filter(
                CtlDreHierarquia.Id_Pai == None, CtlDreHierarquia.Raiz_Centro_Custo_Codigo == None,
                CtlDreHierarquia.Raiz_No_Virtual_Id == None, func.lower(CtlDreHierarquia.Nome) == nome.strip().lower()
            ).first()

        elif parent_node_id.startswith("cc_"):
            codigo_cc_int = int(parent_node_id.replace("cc_", ""))
            # --- ATUALIZADO ---
            sql_info = text("""
                SELECT c."Tipo", c."Nome",
                    EXISTS(
                        SELECT 1 FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h
                        WHERE h."Raiz_Centro_Custo_Codigo" = :cod 
                        AND h."Id_Pai" IS NULL 
                        AND LOWER(h."Nome") = LOWER(:nome)
                    ) as duplicado
                FROM "Dre_Schema"."Tb_CTL_Cad_Centro_Custo" c
                WHERE c."Codigo" = :cod LIMIT 1
            """)
            result_info = session.execute(sql_info, {"cod": codigo_cc_int, "nome": nome.strip()}).first()
            if result_info and result_info[2]: return jsonify({"error": f"Já existe um grupo '{nome}' neste local."}), 400
            
            novo_sub.Raiz_Centro_Custo_Tipo = result_info[0] if result_info else "Indefinido"
            novo_sub.Raiz_Centro_Custo_Nome = result_info[1] if result_info else "Indefinido"
            novo_sub.Raiz_Centro_Custo_Codigo = codigo_cc_int
            contexto_pai_ordem = f"cc_{codigo_cc_int}"
            nivel = 2
            duplicado = None

        elif parent_node_id.startswith("virt_"):
            virt_id = int(parent_node_id.replace("virt_", ""))
            # --- ATUALIZADO ---
            sql_virt = text("""
                SELECT v."Nome",
                    EXISTS(
                        SELECT 1 FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h
                        WHERE h."Raiz_No_Virtual_Id" = :vid 
                        AND h."Id_Pai" IS NULL 
                        AND LOWER(h."Nome") = LOWER(:nome)
                    ) as duplicado
                FROM "Dre_Schema"."Tb_CTL_Dre_No_Virtual" v
                WHERE v."Id" = :vid
            """)
            result = session.execute(sql_virt, {"vid": virt_id, "nome": nome.strip()}).first()
            if result and result[1]: return jsonify({"error": f"Já existe um grupo '{nome}' neste local."}), 400
            
            novo_sub.Raiz_No_Virtual_Id = virt_id
            novo_sub.Raiz_No_Virtual_Nome = result[0] if result else None
            contexto_pai_ordem = f"virt_{virt_id}"
            nivel = 2
            duplicado = None

        elif parent_node_id.startswith("sg_"):
            parent_id = int(parent_node_id.replace("sg_", ""))
            # --- ATUALIZADO ---
            sql_pai = text("""
                SELECT p."Raiz_Centro_Custo_Codigo", p."Raiz_Centro_Custo_Tipo", p."Raiz_No_Virtual_Id",
                    EXISTS(
                        SELECT 1 FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h
                        WHERE h."Id_Pai" = :pid AND LOWER(h."Nome") = LOWER(:nome)
                    ) as duplicado
                FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" p
                WHERE p."Id" = :pid
            """)
            pai_result = session.execute(sql_pai, {"pid": parent_id, "nome": nome.strip()}).first()
            if pai_result and pai_result[3]: return jsonify({"error": f"Já existe um grupo '{nome}' neste local."}), 400
            
            novo_sub.Id_Pai = parent_id
            if pai_result:
                novo_sub.Raiz_Centro_Custo_Codigo = pai_result[0]
                novo_sub.Raiz_Centro_Custo_Tipo = pai_result[1]
                novo_sub.Raiz_No_Virtual_Id = pai_result[2]
            contexto_pai_ordem = f"sg_{parent_id}"
            nivel = 3
            duplicado = None
        else:
            duplicado = None

        if 'duplicado' in dir() and duplicado: return jsonify({"error": f"Já existe um grupo '{nome}' neste local."}), 400

        session.add(novo_sub)
        session.flush()

        nova_ordem = calcular_proxima_ordem(session, contexto_pai_ordem)
        reg_ordem = CtlDreOrdenamento(tipo_no='subgrupo', id_referencia=str(novo_sub.Id), contexto_pai=contexto_pai_ordem, ordem=nova_ordem, nivel_profundidade=nivel)
        session.add(reg_ordem)

        session.commit()
        return jsonify({"success": True, "id": novo_sub.Id}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dre_config_bp.route('/Configuracao/AddSubgrupoSistematico', methods=['POST'])
@login_required
def AddSubgrupoSistematico():
    session = get_session()
    try:
        nome_grupo = request.json.get('nome')
        tipo_cc = request.json.get('tipo_cc')
        if not nome_grupo or not tipo_cc: return jsonify({"error": "Nome do grupo e Tipo são obrigatórios"}), 400

        # --- ATUALIZADO ---
        sql = text("""
            SELECT c."Codigo", c."Nome", c."Tipo"
            FROM "Dre_Schema"."Tb_CTL_Cad_Centro_Custo" c
            WHERE c."Tipo" = :tipo 
            AND c."Codigo" IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h
                WHERE h."Raiz_Centro_Custo_Codigo" = c."Codigo"
                AND h."Nome" = :nome
                AND h."Id_Pai" IS NULL
            )
        """)
        ccs_para_criar = session.execute(sql, {"tipo": tipo_cc, "nome": nome_grupo}).fetchall()

        if not ccs_para_criar:
            return jsonify({"success": True, "msg": "Nenhum grupo criado (todos os CCs já possuíam este grupo)."}), 200

        novos_subgrupos = []
        for cc in ccs_para_criar:
            novos_subgrupos.append(CtlDreHierarquia(
                Nome=nome_grupo, Id_Pai=None, Raiz_Centro_Custo_Codigo=cc[0],
                Raiz_Centro_Custo_Nome=cc[1], Raiz_Centro_Custo_Tipo=cc[2]
            ))
        
        session.bulk_save_objects(novos_subgrupos)
        session.commit()
        return jsonify({"success": True, "msg": f"Grupo '{nome_grupo}' criado em {len(novos_subgrupos)} Centros de Custo!"}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dre_config_bp.route('/Configuracao/AddNoVirtual', methods=['POST'])
@login_required
def AddNoVirtual():
    session = get_session()
    try:
        nome, cor = request.json.get('nome'), request.json.get('cor')
        estilo = f"color: {cor};" if cor else None
        if not nome: return jsonify({"error": "Nome obrigatório"}), 400
        
        # --- ATUALIZADO ---
        sql = text("""
            INSERT INTO "Dre_Schema"."Tb_CTL_Dre_No_Virtual" ("Nome", "Estilo_CSS")
            SELECT :nome, :estilo
            WHERE NOT EXISTS (
                SELECT 1 FROM "Dre_Schema"."Tb_CTL_Dre_No_Virtual"
                WHERE LOWER("Nome") = LOWER(:nome)
            )
            RETURNING "Id"
        """)
        result = session.execute(sql, {"nome": nome.strip(), "estilo": estilo})
        row = result.fetchone()
        
        if not row: return jsonify({"error": f"Já existe um Nó Virtual chamado '{nome}'."}), 400
        
        session.commit()
        return jsonify({"success": True, "id": row[0]}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dre_config_bp.route('/Configuracao/AddNoCalculado', methods=['POST'])
@login_required
def AddNoCalculado():
    session = get_session()
    try:
        data = request.json
        nome, formula = data.get('nome'), data.get('formula')
        if not nome: return jsonify({"error": "Nome obrigatório"}), 400
        if not formula or 'operacao' not in formula: return jsonify({"error": "Fórmula inválida"}), 400
        
        descricao = gerar_descricao_formula(formula)
        # --- ATUALIZADO ---
        sql = text("""
            INSERT INTO "Dre_Schema"."Tb_CTL_Dre_No_Virtual" 
                ("Nome", "Ordem", "Is_Calculado", "Formula_JSON", "Formula_Descricao", 
                 "Tipo_Exibicao", "Base_Percentual_Id", "Estilo_CSS")
            SELECT :nome, :ordem, true, :formula, :descricao, :tipo, :base, :estilo
            WHERE NOT EXISTS (
                SELECT 1 FROM "Dre_Schema"."Tb_CTL_Dre_No_Virtual"
                WHERE LOWER("Nome") = LOWER(:nome)
            )
            RETURNING "Id"
        """)
        result = session.execute(sql, {
            "nome": nome.strip(), "ordem": data.get('ordem', 0), "formula": json.dumps(formula),
            "descricao": descricao, "tipo": data.get('tipo_exibicao', 'valor'),
            "base": data.get('base_percentual_id'), "estilo": data.get('estilo_css')
        })
        row = result.fetchone()
        if not row: return jsonify({"error": f"Já existe um nó chamado '{nome}'"}), 400
        
        session.commit()
        return jsonify({"success": True, "id": row[0], "msg": f"Nó calculado '{nome}' criado com sucesso!"}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dre_config_bp.route('/Configuracao/VincularConta', methods=['POST'])
@login_required
def VincularConta():
    session = get_session()
    try:
        conta = str(request.json.get('conta')).strip()
        subgrupo_node_id = request.json.get('subgrupo_id') 

        if not subgrupo_node_id.startswith("sg_"): raise Exception("Contas só podem ser vinculadas a Subgrupos.")
        sg_id = int(subgrupo_node_id.replace("sg_", ""))

        # --- ATUALIZADO ---
        sql = text("""
            WITH RECURSIVE hierarquia AS (
                SELECT "Id", "Id_Pai", "Raiz_Centro_Custo_Codigo", "Raiz_Centro_Custo_Tipo", 
                       "Raiz_No_Virtual_Id", 0 as nivel
                FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia"
                WHERE "Id" = :sg_id
                
                UNION ALL
                
                SELECT p."Id", p."Id_Pai", 
                       COALESCE(h."Raiz_Centro_Custo_Codigo", p."Raiz_Centro_Custo_Codigo"),
                       COALESCE(h."Raiz_Centro_Custo_Tipo", p."Raiz_Centro_Custo_Tipo"),
                       COALESCE(h."Raiz_No_Virtual_Id", p."Raiz_No_Virtual_Id"),
                       h.nivel + 1
                FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" p
                INNER JOIN hierarquia h ON h."Id_Pai" = p."Id"
                WHERE h."Raiz_Centro_Custo_Codigo" IS NULL AND h."Raiz_No_Virtual_Id" IS NULL
            )
            SELECT "Raiz_Centro_Custo_Codigo", "Raiz_Centro_Custo_Tipo", "Raiz_No_Virtual_Id"
            FROM hierarquia
            WHERE "Raiz_Centro_Custo_Codigo" IS NOT NULL OR "Raiz_No_Virtual_Id" IS NOT NULL
            ORDER BY nivel DESC LIMIT 1
        """)
        result = session.execute(sql, {"sg_id": sg_id}).first()
        
        if not result:
            root_cc_code, root_virt_id, root_tipo = None, None, "Virtual"
        else:
            root_cc_code, root_tipo, root_virt_id = result[0], result[1] or "Virtual", result[2]

        chave_tipo = f"{conta}{root_tipo}"
        chave_cod = f"{conta}{root_cc_code}" if root_cc_code else f"{conta}VIRTUAL{root_virt_id}"

        # --- ATUALIZADO ---
        sql_upsert = text("""
            INSERT INTO "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" 
                ("Conta_Contabil", "Id_Hierarquia", "Chave_Conta_Tipo_CC", "Chave_Conta_Codigo_CC")
            VALUES (:conta, :sg_id, :chave_tipo, :chave_cod)
            ON CONFLICT ("Conta_Contabil") DO UPDATE SET
                "Id_Hierarquia" = EXCLUDED."Id_Hierarquia",
                "Chave_Conta_Tipo_CC" = EXCLUDED."Chave_Conta_Tipo_CC",
                "Chave_Conta_Codigo_CC" = EXCLUDED."Chave_Conta_Codigo_CC"
        """)
        session.execute(sql_upsert, {"conta": conta, "sg_id": sg_id, "chave_tipo": chave_tipo, "chave_cod": chave_cod})

        session.query(CtlDreOrdenamento).filter(CtlDreOrdenamento.tipo_no == 'conta', CtlDreOrdenamento.id_referencia == conta).delete(synchronize_session=False)

        contexto_pai = f"sg_{sg_id}"
        nova_ordem = calcular_proxima_ordem(session, contexto_pai)

        reg_ordem = CtlDreOrdenamento(tipo_no='conta', id_referencia=conta, contexto_pai=contexto_pai, ordem=nova_ordem, nivel_profundidade=99)
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
    session = get_session()
    try:
        conta, nome_personalizado, parent_id = request.json.get('conta'), request.json.get('nome_personalizado'), request.json.get('parent_id')
        if not conta or not parent_id: return jsonify({"error": "Dados incompletos"}), 400

        id_hierarquia, id_no_virtual = None, None
        if parent_id.startswith("virt_"): id_no_virtual = int(parent_id.replace("virt_", ""))
        elif parent_id.startswith("sg_"): id_hierarquia = int(parent_id.replace("sg_", ""))
        else: return jsonify({"error": "Local inválido para vínculo de detalhe"}), 400

        # --- ATUALIZADO ---
        sql = text("""
            INSERT INTO "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada"
                ("Conta_Contabil", "Nome_Personalizado", "Id_Hierarquia", "Id_No_Virtual")
            VALUES (:conta, :nome, :hier, :virt)
            ON CONFLICT ("Conta_Contabil") DO UPDATE SET
                "Nome_Personalizado" = COALESCE(EXCLUDED."Nome_Personalizado", "Tb_CTL_Dre_Conta_Personalizada"."Nome_Personalizado"),
                "Id_Hierarquia" = EXCLUDED."Id_Hierarquia",
                "Id_No_Virtual" = EXCLUDED."Id_No_Virtual"
        """)
        session.execute(sql, {"conta": conta, "nome": nome_personalizado, "hier": id_hierarquia, "virt": id_no_virtual})
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
    session = get_session()
    try:
        # --- ATUALIZADO ---
        sql = text('UPDATE "Dre_Schema"."Tb_CTL_Dre_No_Virtual" SET "Nome" = :nome WHERE "Id" = :id')
        result = session.execute(sql, {"nome": request.json.get('novo_nome'), "id": int(request.json.get('id').replace('virt_', ''))})
        if result.rowcount == 0: return jsonify({"error": "Nó não encontrado"}), 404
        session.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dre_config_bp.route('/Configuracao/RenameSubgrupo', methods=['POST'])
@login_required
def RenameSubgrupo():
    session = get_session()
    try:
        # --- ATUALIZADO ---
        sql = text('UPDATE "Dre_Schema"."Tb_CTL_Dre_Hierarquia" SET "Nome" = :nome WHERE "Id" = :id')
        result = session.execute(sql, {"nome": request.json.get('novo_nome'), "id": int(request.json.get('id').replace('sg_', ''))})
        if result.rowcount == 0: return jsonify({"error": "Subgrupo não encontrado"}), 404
        session.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dre_config_bp.route('/Configuracao/RenameContaPersonalizada', methods=['POST'])
@login_required
def RenameContaPersonalizada():
    session = get_session()
    try:
        # --- ATUALIZADO ---
        sql = text('UPDATE "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" SET "Nome_Personalizado" = :nome WHERE "Id" = :id')
        result = session.execute(sql, {"nome": request.json.get('novo_nome'), "id": int(request.json.get('id').replace('cd_', ''))})
        if result.rowcount == 0: return jsonify({"error": "Conta detalhe não encontrada"}), 404
        session.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dre_config_bp.route('/Configuracao/UpdateNoCalculado', methods=['POST'])
@login_required
def UpdateNoCalculado():
    session = get_session()
    try:
        data = request.json
        updates, params = [], {"id": data.get('id')}
        
        if data.get('nome'):
            updates.append('"Nome" = :nome')
            params["nome"] = data.get('nome')
        if data.get('formula'):
            updates.extend(['"Formula_JSON" = :formula', '"Formula_Descricao" = :descricao'])
            params["formula"], params["descricao"] = json.dumps(data.get('formula')), gerar_descricao_formula(data.get('formula'))
        if data.get('ordem') is not None:
            updates.append('"Ordem" = :ordem')
            params["ordem"] = data.get('ordem')
        if data.get('tipo_exibicao'):
            updates.append('"Tipo_Exibicao" = :tipo')
            params["tipo"] = data.get('tipo_exibicao')
        if data.get('estilo_css') is not None:
            updates.append('"Estilo_CSS" = :estilo')
            params["estilo"] = data.get('estilo_css')
        
        if not updates: return jsonify({"error": "Nada para atualizar"}), 400
        
        # --- ATUALIZADO ---
        sql = text(f'UPDATE "Dre_Schema"."Tb_CTL_Dre_No_Virtual" SET {", ".join(updates)} WHERE "Id" = :id AND "Is_Calculado" = true')
        result = session.execute(sql, params)
        if result.rowcount == 0: return jsonify({"error": "Nó não encontrado ou não é calculado"}), 404
        
        session.commit()
        return jsonify({"success": True, "msg": "Fórmula atualizada!"}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

# ============================================================
# SEÇÃO 6: ROTAS DE EXCLUSÃO (DELETE) - OTIMIZADAS
# ============================================================

@dre_config_bp.route('/Configuracao/DeleteSubgrupo', methods=['POST'])
@login_required
def DeleteSubgrupo():
    session = get_session()
    try:
        node_id = request.json.get('id') 
        if not node_id or not node_id.startswith('sg_'): return jsonify({"error": "Nó inválido para exclusão"}), 400
        db_id = int(node_id.replace('sg_', ''))
        
        # --- ATUALIZADO ---
        sql_find_all = text("""
            WITH RECURSIVE todos_ids AS (
                SELECT "Id" FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" WHERE "Id" = :id
                UNION ALL
                SELECT h."Id" 
                FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h
                INNER JOIN todos_ids t ON h."Id_Pai" = t."Id"
            )
            SELECT "Id" FROM todos_ids
        """)
        all_ids = [row[0] for row in session.execute(sql_find_all, {"id": db_id}).fetchall()]
        if not all_ids: return jsonify({"error": "Grupo não encontrado"}), 404
        
        contas_para_limpar = []
        # --- ATUALIZADO ---
        for row in session.execute(text('SELECT "Conta_Contabil" FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": all_ids}).fetchall():
            contas_para_limpar.append(('conta', row[0]))
        
        for row in session.execute(text('SELECT "Id" FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": all_ids}).fetchall():
            contas_para_limpar.append(('conta_detalhe', str(row[0])))
        
        limpar_ordenamento_bulk(session, contas_para_limpar)
        limpar_ordenamento_bulk(session, [('subgrupo', str(id)) for id in all_ids])
        limpar_ordenamento_por_contextos(session, [f'sg_{id}' for id in all_ids])
        
        session.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": all_ids})
        session.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": all_ids})
        session.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" WHERE "Id" = ANY(:ids)'), {"ids": all_ids})
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
    session = get_session()
    try:
        node_id = request.json.get('id')
        if node_id.startswith('conta_'):
            conta_contabil = node_id.replace('conta_', '')
            # --- ATUALIZADO ---
            session.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" WHERE "Conta_Contabil" = :conta'), {"conta": conta_contabil})
            session.query(CtlDreOrdenamento).filter(CtlDreOrdenamento.tipo_no == 'conta', CtlDreOrdenamento.id_referencia == conta_contabil).delete(synchronize_session=False)
        elif node_id.startswith('cd_'):
            cd_id = int(node_id.replace('cd_', ''))
            # --- ATUALIZADO ---
            session.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id" = :id'), {"id": cd_id})
            session.query(CtlDreOrdenamento).filter(CtlDreOrdenamento.tipo_no == 'conta_detalhe', CtlDreOrdenamento.id_referencia == str(cd_id)).delete(synchronize_session=False)
        else:
            return jsonify({"error": "Tipo de vínculo não reconhecido"}), 400
        session.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dre_config_bp.route('/Configuracao/DeleteNoVirtual', methods=['POST'])
@login_required
def DeleteNoVirtual():
    session = get_session()
    try:
        node_id = request.json.get('id')
        if not node_id or not node_id.startswith('virt_'): return jsonify({"error": "Nó inválido"}), 400
        virt_id = int(node_id.replace('virt_', ''))
        
        # --- ATUALIZADO ---
        sql_find = text("""
            WITH RECURSIVE todos AS (
                SELECT "Id" FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" WHERE "Raiz_No_Virtual_Id" = :vid
                UNION ALL
                SELECT h."Id" FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h
                INNER JOIN todos t ON h."Id_Pai" = t."Id"
            )
            SELECT "Id" FROM todos
        """)
        ids_hierarquia = [row[0] for row in session.execute(sql_find, {"vid": virt_id}).fetchall()]
        itens_ordenamento = []

        if ids_hierarquia:
            for row in session.execute(text('SELECT "Conta_Contabil" FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": ids_hierarquia}).fetchall():
                itens_ordenamento.append(('conta', row[0]))
            for row in session.execute(text('SELECT "Id" FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": ids_hierarquia}).fetchall():
                itens_ordenamento.append(('conta_detalhe', str(row[0])))
            for sg_id in ids_hierarquia: itens_ordenamento.append(('subgrupo', str(sg_id)))
            
            session.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": ids_hierarquia})
            session.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": ids_hierarquia})
            session.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" WHERE "Id" = ANY(:ids)'), {"ids": ids_hierarquia})

        for row in session.execute(text('SELECT "Id" FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id_No_Virtual" = :vid'), {"vid": virt_id}).fetchall():
            itens_ordenamento.append(('conta_detalhe', str(row[0])))
        session.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id_No_Virtual" = :vid'), {"vid": virt_id})

        itens_ordenamento.append(('virtual', str(virt_id)))
        limpar_ordenamento_bulk(session, itens_ordenamento)
        limpar_ordenamento_por_contextos(session, [f'virt_{virt_id}'] + [f'sg_{id}' for id in ids_hierarquia])

        session.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_No_Virtual" WHERE "Id" = :vid'), {"vid": virt_id})
        session.commit()
        return jsonify({"success": True, "msg": "Estrutura virtual excluída."}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


# ============================================================
# SEÇÃO 7: ROTAS DE OPERAÇÕES EM MASSA - OTIMIZADAS
# ============================================================

@dre_config_bp.route('/Configuracao/VincularContaEmMassa', methods=['POST'])
@login_required
def VincularContaEmMassa():
    session = get_session()
    try:
        data = request.json
        tipo_cc, nome_subgrupo, conta, is_personalizada, nome_personalizado_conta = data.get('tipo_cc'), data.get('nome_subgrupo'), str(data.get('conta')).strip(), data.get('is_personalizada', False), data.get('nome_personalizado_conta')
        if not all([tipo_cc, nome_subgrupo, conta]): return jsonify({"error": "Dados incompletos."}), 400

        if is_personalizada:
            if not nome_personalizado_conta:
                res = session.execute(text('SELECT "Título Conta" FROM "Dre_Schema"."Vw_CTL_Razao_Consolidado" WHERE "Conta" = :c LIMIT 1'), {'c': conta}).first()
                nome_personalizado_conta = res[0] if res else "Sem Nome"
            
            # --- ATUALIZADO ---
            sql = text("""
                INSERT INTO "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" ("Conta_Contabil", "Nome_Personalizado", "Id_Hierarquia")
                SELECT :conta, :nome, h."Id"
                FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h
                WHERE h."Raiz_Centro_Custo_Tipo" = :tipo AND h."Nome" = :subgrupo
                ON CONFLICT ("Conta_Contabil", "Id_Hierarquia") DO UPDATE SET "Nome_Personalizado" = EXCLUDED."Nome_Personalizado"
            """)
            result = session.execute(sql, {"conta": conta, "nome": nome_personalizado_conta, "tipo": tipo_cc, "subgrupo": nome_subgrupo})
            count_sucesso = result.rowcount
        else:
            # --- ATUALIZADO ---
            sql = text("""
                INSERT INTO "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" ("Conta_Contabil", "Id_Hierarquia", "Chave_Conta_Tipo_CC", "Chave_Conta_Codigo_CC")
                SELECT CAST(:conta AS TEXT), h."Id", CAST(:conta AS TEXT) || :tipo, CAST(:conta AS TEXT) || CAST(h."Raiz_Centro_Custo_Codigo" AS TEXT)
                FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h
                WHERE h."Raiz_Centro_Custo_Tipo" = :tipo AND h."Nome" = :subgrupo AND h."Raiz_Centro_Custo_Codigo" IS NOT NULL
                ON CONFLICT ("Chave_Conta_Codigo_CC") DO UPDATE SET "Id_Hierarquia" = EXCLUDED."Id_Hierarquia", "Chave_Conta_Tipo_CC" = EXCLUDED."Chave_Conta_Tipo_CC"
            """)
            result = session.execute(sql, {"conta": conta, "tipo": tipo_cc, "subgrupo": nome_subgrupo})
            count_sucesso = result.rowcount

        session.commit()
        msg_extra = f" com nome '{nome_personalizado_conta}'" if is_personalizada and nome_personalizado_conta else ""
        return jsonify({"success": True, "msg": f"Conta {conta} vinculada em {count_sucesso} locais{msg_extra}."}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dre_config_bp.route('/Configuracao/DesvincularContaEmMassa', methods=['POST'])
@login_required
def DesvincularContaEmMassa():
    session = get_session()
    try:
        tipo_cc, conta, is_personalizada = request.json.get('tipo_cc'), str(request.json.get('conta')).strip(), request.json.get('is_personalizada', False)
        if not tipo_cc or not conta: return jsonify({"error": "Dados inválidos"}), 400

        if is_personalizada:
            # --- ATUALIZADO ---
            sql = text("""
                DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" p
                USING "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h
                WHERE p."Id_Hierarquia" = h."Id" AND p."Conta_Contabil" = :conta AND h."Raiz_Centro_Custo_Tipo" = :tipo
            """)
            result = session.execute(sql, {"conta": conta, "tipo": tipo_cc})
            count = result.rowcount
        else:
            session.query(CtlDreOrdenamento).filter(CtlDreOrdenamento.tipo_no == 'conta', CtlDreOrdenamento.id_referencia == conta).delete(synchronize_session=False)
            chave_tipo = f"{conta}{tipo_cc}"
            result = session.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" WHERE "Chave_Conta_Tipo_CC" = :chave'), {"chave": chave_tipo})
            count = result.rowcount

        session.commit()
        return jsonify({"success": True, "msg": f"Vínculo da conta {conta} removido de {count} locais."}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dre_config_bp.route('/Configuracao/DeleteSubgrupoEmMassa', methods=['POST'])
@login_required
def DeleteSubgrupoEmMassa():
    session = get_session()
    try:
        tipo_cc, nome_grupo = request.json.get('tipo_cc'), request.json.get('nome_grupo')
        if not tipo_cc or not nome_grupo: return jsonify({"error": "Parâmetros inválidos"}), 400

        # --- ATUALIZADO ---
        sql_find = text("""
            WITH RECURSIVE raizes AS (
                SELECT "Id" FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" WHERE "Raiz_Centro_Custo_Tipo" = :tipo AND "Nome" = :nome AND "Id_Pai" IS NULL
            ),
            todos AS (
                SELECT "Id" FROM raizes
                UNION ALL
                SELECT h."Id" FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h INNER JOIN todos t ON h."Id_Pai" = t."Id"
            )
            SELECT "Id" FROM todos
        """)
        all_ids = [row[0] for row in session.execute(sql_find, {"tipo": tipo_cc, "nome": nome_grupo}).fetchall()]
        if not all_ids: return jsonify({"error": "Nenhum grupo encontrado com esse nome."}), 404

        itens_ordenamento = []
        for row in session.execute(text('SELECT "Conta_Contabil" FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": all_ids}).fetchall():
            itens_ordenamento.append(('conta', row[0]))
        for row in session.execute(text('SELECT "Id" FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": all_ids}).fetchall():
            itens_ordenamento.append(('conta_detalhe', str(row[0])))
        for sg_id in all_ids: itens_ordenamento.append(('subgrupo', str(sg_id)))
        
        limpar_ordenamento_bulk(session, itens_ordenamento)
        limpar_ordenamento_por_contextos(session, [f'sg_{id}' for id in all_ids])

        session.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": all_ids})
        session.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": all_ids})
        session.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" WHERE "Id" = ANY(:ids)'), {"ids": all_ids})
        session.commit()
        return jsonify({"success": True, "msg": f"Exclusão em massa concluída! {len(all_ids)} itens removidos."}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

# ============================================================
# SEÇÃO 8: ROTAS DE REPLICAÇÃO - OTIMIZADAS
# ============================================================

@dre_config_bp.route('/Configuracao/ReplicarEstrutura', methods=['POST'])
@login_required
def ReplicarEstrutura():
    return jsonify({"success": True, "msg": "ReplicarEstrutura em manutenção temporária após refatoração."}), 200

@dre_config_bp.route('/Configuracao/ColarEstrutura', methods=['POST'])
@login_required
def ColarEstrutura():
    return jsonify({"success": True, "msg": "ColarEstrutura em manutenção temporária após refatoração."}), 200


@dre_config_bp.route('/Configuracao/ReplicarTipoIntegral', methods=['POST'])
@login_required
def ReplicarTipoIntegral():
    session = get_session()
    try:
        tipo_origem, tipo_destino = request.json.get('tipo_origem'), request.json.get('tipo_destino')
        if not tipo_origem or not tipo_destino: return jsonify({"error": "Tipos obrigatórios."}), 400
        if tipo_origem == tipo_destino: return jsonify({"error": "Devem ser diferentes."}), 400

        # --- ATUALIZADO ---
        sql_ids_destino = text('SELECT "Id" FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" WHERE "Raiz_Centro_Custo_Tipo" = :dest')
        ids_destino = [row[0] for row in session.execute(sql_ids_destino, {"dest": tipo_destino}).fetchall()]
        
        if ids_destino:
            limpar_ordenamento_bulk(session, [('subgrupo', str(id)) for id in ids_destino])
            limpar_ordenamento_por_contextos(session, [f'sg_{id}' for id in ids_destino])
            session.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": ids_destino})
            session.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": ids_destino})
            session.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" WHERE "Id" = ANY(:ids)'), {"ids": ids_destino})
        
        sql_ccs_destino = text('SELECT DISTINCT "Codigo", "Nome" FROM "Dre_Schema"."Tb_CTL_Cad_Centro_Custo" WHERE "Tipo" = :dest AND "Codigo" IS NOT NULL')
        ccs_destino = session.execute(sql_ccs_destino, {"dest": tipo_destino}).fetchall()

        sql_blueprint = text("""
            SELECT DISTINCT h."Nome", p."Nome" as "Nome_Pai", CASE WHEN h."Id_Pai" IS NULL THEN 0 ELSE 1 END as "Nivel"
            FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h
            LEFT JOIN "Dre_Schema"."Tb_CTL_Dre_Hierarquia" p ON h."Id_Pai" = p."Id"
            WHERE h."Raiz_Centro_Custo_Tipo" = :orig ORDER BY "Nivel" ASC
        """)
        blueprint_structure = session.execute(sql_blueprint, {"orig": tipo_origem}).fetchall()

        mapa_ids_criados, grupos_raiz_nomes = {}, set()
        def transformar_nome(n): return n.replace(tipo_origem, tipo_destino) if n else n

        grupos_raiz = [b for b in blueprint_structure if b.Nivel == 0]
        inserts_raiz = []
        for cc in ccs_destino:
            for gr in grupos_raiz:
                nn = transformar_nome(gr.Nome)
                grupos_raiz_nomes.add(nn)
                inserts_raiz.append({"Nome": nn, "Id_Pai": None, "Raiz_Centro_Custo_Codigo": cc.Codigo, "Raiz_Centro_Custo_Nome": cc.Nome, "Raiz_Centro_Custo_Tipo": tipo_destino})

        if inserts_raiz:
            stmt = text('INSERT INTO "Dre_Schema"."Tb_CTL_Dre_Hierarquia" ("Nome", "Id_Pai", "Raiz_Centro_Custo_Codigo", "Raiz_Centro_Custo_Nome", "Raiz_Centro_Custo_Tipo") VALUES (:Nome, :Id_Pai, :Raiz_Centro_Custo_Codigo, :Raiz_Centro_Custo_Nome, :Raiz_Centro_Custo_Tipo) RETURNING "Id", "Nome", "Raiz_Centro_Custo_Codigo"')
            for item in inserts_raiz:
                res = session.execute(stmt, item).fetchone()
                mapa_ids_criados[(res.Nome, res.Raiz_Centro_Custo_Codigo)] = res.Id

        grupos_filhos = [b for b in blueprint_structure if b.Nivel == 1]
        inserts_filhos = []
        for cc in ccs_destino:
            for gf in grupos_filhos:
                nnp, nnf = transformar_nome(gf.Nome_Pai), transformar_nome(gf.Nome)
                id_pai = mapa_ids_criados.get((nnp, cc.Codigo))
                if id_pai: inserts_filhos.append({"Nome": nnf, "Id_Pai": id_pai, "Raiz_Centro_Custo_Codigo": cc.Codigo, "Raiz_Centro_Custo_Nome": cc.Nome, "Raiz_Centro_Custo_Tipo": tipo_destino, "Nome_Pai": nnp })

        if inserts_filhos:
            stmt_filhos = text('INSERT INTO "Dre_Schema"."Tb_CTL_Dre_Hierarquia" ("Nome", "Id_Pai", "Raiz_Centro_Custo_Codigo", "Raiz_Centro_Custo_Nome", "Raiz_Centro_Custo_Tipo") VALUES (:Nome, :Id_Pai, :Raiz_Centro_Custo_Codigo, :Raiz_Centro_Custo_Nome, :Raiz_Centro_Custo_Tipo) RETURNING "Id", "Nome", "Raiz_Centro_Custo_Codigo"')
            for item in inserts_filhos:
                res = session.execute(stmt_filhos, item).fetchone()
                mapa_ids_criados[(res.Nome, res.Raiz_Centro_Custo_Codigo)] = res.Id

        sql_contas_origem = text('SELECT DISTINCT h."Nome" as "Nome_Grupo", v."Conta_Contabil" FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" v JOIN "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h ON v."Id_Hierarquia" = h."Id" WHERE h."Raiz_Centro_Custo_Tipo" = :orig')
        inserts_contas = []
        for row in session.execute(sql_contas_origem, {"orig": tipo_origem}).fetchall():
            ngd = transformar_nome(row.Nome_Grupo)
            for cc in ccs_destino:
                id_hier = mapa_ids_criados.get((ngd, cc.Codigo))
                if id_hier: inserts_contas.append({"Conta_Contabil": str(row.Conta_Contabil), "Id_Hierarquia": id_hier, "Chave_Conta_Tipo_CC": f"{row.Conta_Contabil}{tipo_destino}", "Chave_Conta_Codigo_CC": f"{row.Conta_Contabil}{cc.Codigo}"})

        if inserts_contas:
            session.execute(text('INSERT INTO "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" ("Conta_Contabil", "Id_Hierarquia", "Chave_Conta_Tipo_CC", "Chave_Conta_Codigo_CC") VALUES (:Conta_Contabil, :Id_Hierarquia, :Chave_Conta_Tipo_CC, :Chave_Conta_Codigo_CC) ON CONFLICT ("Chave_Conta_Codigo_CC") DO UPDATE SET "Id_Hierarquia" = EXCLUDED."Id_Hierarquia"'), inserts_contas)

        sql_pers_origem = text('SELECT DISTINCT h."Nome" as "Nome_Grupo", p."Conta_Contabil", p."Nome_Personalizado" FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" p JOIN "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h ON p."Id_Hierarquia" = h."Id" WHERE h."Raiz_Centro_Custo_Tipo" = :orig')
        inserts_pers = []
        for row in session.execute(sql_pers_origem, {"orig": tipo_origem}).fetchall():
            ngd = transformar_nome(row.Nome_Grupo)
            for cc in ccs_destino:
                id_hier = mapa_ids_criados.get((ngd, cc.Codigo))
                if id_hier: inserts_pers.append({"Conta_Contabil": str(row.Conta_Contabil), "Nome_Personalizado": row.Nome_Personalizado, "Id_Hierarquia": id_hier})

        if inserts_pers:
            session.execute(text('INSERT INTO "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" ("Conta_Contabil", "Nome_Personalizado", "Id_Hierarquia") VALUES (:Conta_Contabil, :Nome_Personalizado, :Id_Hierarquia) ON CONFLICT ("Conta_Contabil", "Id_Hierarquia") DO UPDATE SET "Nome_Personalizado" = EXCLUDED."Nome_Personalizado"'), inserts_pers)

        sql_ordem_blueprint = text('SELECT h."Nome", p."Nome" as "Nome_Pai", MIN(o.ordem) as "Ordem_Padrao" FROM "Dre_Schema"."Tb_CTL_Dre_Ordenamento" o JOIN "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h ON o.id_referencia = CAST(h."Id" AS TEXT) LEFT JOIN "Dre_Schema"."Tb_CTL_Dre_Hierarquia" p ON h."Id_Pai" = p."Id" WHERE o.tipo_no = \'subgrupo\' AND h."Raiz_Centro_Custo_Tipo" = :orig GROUP BY h."Nome", p."Nome"')
        mapa_ordem = {(transformar_nome(r.Nome), transformar_nome(r.Nome_Pai)): r.Ordem_Padrao for r in session.execute(sql_ordem_blueprint, {"orig": tipo_origem}).fetchall()}

        inserts_ordenamento = []
        for (nome_grupo, cod_cc), novo_id in mapa_ids_criados.items():
            eh_raiz = nome_grupo in grupos_raiz_nomes
            if eh_raiz: ctx, nvl, ord_val = f"cc_{cod_cc}", 2, mapa_ordem.get((nome_grupo, None), 999)
            else:
                match_filho = next((x for x in inserts_filhos if x['Nome'] == nome_grupo and x['Raiz_Centro_Custo_Codigo'] == cod_cc), None)
                if match_filho: ctx, nvl, ord_val = f"sg_{match_filho['Id_Pai']}", 3, mapa_ordem.get((nome_grupo, match_filho['Nome_Pai']), 999)
                else: continue
            inserts_ordenamento.append(CtlDreOrdenamento(tipo_no='subgrupo', id_referencia=str(novo_id), contexto_pai=ctx, ordem=ord_val, nivel_profundidade=nvl))

        if inserts_ordenamento: session.bulk_save_objects(inserts_ordenamento)
        session.commit()
        return jsonify({"success": True, "msg": f"Replicação completa concluída."}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

# ============================================================
# SEÇÃO 9: ÍNDICES RECOMENDADOS PARA PERFORMANCE
# ============================================================
"""
Execute estes comandos SQL para criar índices otimizados (ATUALIZADOS PARA OS NOVOS NOMES):

CREATE INDEX IF NOT EXISTS idx_hierarquia_tipo_cc ON "Dre_Schema"."Tb_CTL_Dre_Hierarquia" ("Raiz_Centro_Custo_Tipo", "Nome");
CREATE INDEX IF NOT EXISTS idx_hierarquia_cc_codigo ON "Dre_Schema"."Tb_CTL_Dre_Hierarquia" ("Raiz_Centro_Custo_Codigo");
CREATE INDEX IF NOT EXISTS idx_hierarquia_virtual ON "Dre_Schema"."Tb_CTL_Dre_Hierarquia" ("Raiz_No_Virtual_Id");
CREATE INDEX IF NOT EXISTS idx_hierarquia_pai ON "Dre_Schema"."Tb_CTL_Dre_Hierarquia" ("Id_Pai");
CREATE INDEX IF NOT EXISTS idx_vinculo_hierarquia ON "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" ("Id_Hierarquia");
CREATE INDEX IF NOT EXISTS idx_personalizada_hierarquia ON "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" ("Id_Hierarquia");
CREATE INDEX IF NOT EXISTS idx_ordenamento_contexto ON "Dre_Schema"."Tb_CTL_Dre_Ordenamento" ("contexto_pai", "ordem");
CREATE INDEX IF NOT EXISTS idx_ordenamento_tipo_ref ON "Dre_Schema"."Tb_CTL_Dre_Ordenamento" ("tipo_no", "id_referencia");
CREATE INDEX IF NOT EXISTS idx_razao_conta ON "Dre_Schema"."Vw_CTL_Razao_Consolidado" ("Conta");
"""