from flask import Blueprint, jsonify, request, abort, render_template
from flask_login import login_required
from sqlalchemy import text
from Db.Connections import get_postgres_engine
from sqlalchemy.orm import sessionmaker

# Importe suas models aqui
from Models.POSTGRESS.DreEstrutura import DreSubgrupo, DreContaVinculo, DreNoVirtual, DreContaDetalhe
from Models.POSTGRESS.Rentabilidade import RazaoConsolidada

dre_config_bp = Blueprint('DreConfig', __name__)

def get_session():
    engine = get_postgres_engine()
    Session = sessionmaker(bind=engine)
    return Session()

@dre_config_bp.route('/Configuracao/Arvore', methods=['GET'])
@login_required
def ViewConfiguracao():
    return render_template('MENUS/ConfiguracaoDRE.html')

@dre_config_bp.route('/Configuracao/GetContasDisponiveis', methods=['GET'])
@login_required
def GetContasDisponiveis():
    session = get_session()
    try:
        # Busca apenas contas distintas para não trazer milhares de linhas repetidas
        sql = text("""
            SELECT DISTINCT "Conta", "Título Conta"
            FROM "Dre_Schema"."Tb_Razao_CONSOLIDADA"
            WHERE "Conta" IS NOT NULL
            ORDER BY "Conta" ASC
        """)
        
        result = session.execute(sql).fetchall()
        
        contas = [
            {"numero": row[0], "nome": row[1]} 
            for row in result
        ]
        
        return jsonify(contas), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dre_config_bp.route('/Configuracao/GetDadosArvore', methods=['GET'])
@login_required
def GetDadosArvore():
    """
    Monta a árvore híbrida: 
    1. Estrutura Virtual (Faturamento, Impostos...) -> AGORA NO TOPO
    2. Estrutura Padrão (Centros de Custo do ERP)
    """
    session = get_session()
    try:
        # 1. Busca Base Fixa (Centros de Custo)
        sql_base = text("""
            SELECT DISTINCT "Tipo", "Nome", "Codigo CC." 
            FROM "Dre_Schema"."Tb_Centro_Custo_Classificacao"
            WHERE "Codigo CC." IS NOT NULL
            ORDER BY "Tipo", "Nome", "Codigo CC."
        """)
        base_result = session.execute(sql_base).mappings().all()

        # 2. Busca Dados Dinâmicos
        subgrupos = session.query(DreSubgrupo).all()
        vinculos = session.query(DreContaVinculo).all()
        virtuais = session.query(DreNoVirtual).order_by(DreNoVirtual.ordem).all()
        contas_detalhe = session.query(DreContaDetalhe).all()

        # --- HELPERS DE MONTAGEM ---
        
        def get_contas_normais(sub_id):
            return [
                {"id": f"conta_{v.conta_contabil}", "text": f"Conta: {v.conta_contabil}", "type": "conta", "parent": sub_id} 
                for v in vinculos if v.subgrupo_id == sub_id
            ]

        def get_contas_detalhe(sub_id):
            return [
                {"id": f"cd_{c.id}", "text": f"{c.conta_contabil} ({c.nome_personalizado or 'Orig'})", "type": "conta_detalhe", "parent": sub_id} 
                for c in contas_detalhe if c.subgrupo_id == sub_id
            ]

        def get_children_subgrupos(parent_id):
            children = []
            for sg in subgrupos:
                if sg.parent_subgrupo_id == parent_id:
                    contas = get_contas_normais(sg.id) + get_contas_detalhe(sg.id)
                    node = {
                        "id": f"sg_{sg.id}", 
                        "db_id": sg.id, 
                        "text": sg.nome, 
                        "type": "subgrupo",
                        "children": get_children_subgrupos(sg.id) + contas
                    }
                    children.append(node)
            return children

        # --- LISTA FINAL QUE SERÁ RETORNADA ---
        final_tree = []

        # --- 1. MONTAGEM DA ÁRVORE VIRTUAL (PRIMEIRO NA LISTA) ---
        # Agora eles são adicionados diretamente na raiz, sem grupo agrupador
        for v in virtuais:
            children_virtual = []
            
            # Subgrupos ligados diretamente a este Nó Virtual
            for sg in subgrupos:
                if sg.root_virtual_id == v.id and sg.parent_subgrupo_id is None:
                    contas_do_grupo = get_children_subgrupos(sg.id) + get_contas_detalhe(sg.id) + get_contas_normais(sg.id)
                    node = {
                        "id": f"sg_{sg.id}", 
                        "db_id": sg.id, 
                        "text": sg.nome, 
                        "type": "subgrupo",
                        "children": contas_do_grupo
                    }
                    children_virtual.append(node)

            # Contas Detalhe ligadas diretamente ao Nó Virtual
            for c in contas_detalhe:
                if c.no_virtual_id == v.id:
                    label = f"{c.conta_contabil} ({c.nome_personalizado or ''})"
                    children_virtual.append({
                        "id": f"cd_{c.id}", 
                        "text": label, 
                        "type": "conta_detalhe", 
                        "parent": f"virt_{v.id}"
                    })
            
            # O Nó Virtual agora é um "Root" por si só
            node_virtual = {
                "id": f"virt_{v.id}",
                "text": v.nome,       # Ex: FATURAMENTO LÍQUIDO
                "type": "root_virtual", # Mantém o tipo amarelo/destaque
                "children": children_virtual
            }
            final_tree.append(node_virtual)


        # --- 2. MONTAGEM DA ÁRVORE PADRÃO (CENTROS DE CUSTO) ---
        tipos_map = {}
        
        for row in base_result:
            tipo = row['Tipo']
            nome_cc = row['Nome']
            codigo_cc = row['Codigo CC.']
            label_cc = f"{codigo_cc} - {nome_cc}"
            
            if tipo not in tipos_map:
                tipos_map[tipo] = {"id": f"tipo_{tipo}", "text": tipo, "type": "root_tipo", "children": []}
            
            children_do_cc = []
            for sg in subgrupos:
                if sg.root_cc_codigo == codigo_cc and sg.parent_subgrupo_id is None:
                    node = {
                        "id": f"sg_{sg.id}", 
                        "db_id": sg.id, 
                        "text": sg.nome, 
                        "type": "subgrupo",
                        "children": get_children_subgrupos(sg.id) + get_contas_normais(sg.id) + get_contas_detalhe(sg.id)
                    }
                    children_do_cc.append(node)

            node_cc = {
                "id": f"cc_{codigo_cc}", 
                "text": label_cc,       
                "type": "root_cc", 
                "children": children_do_cc
            }
            tipos_map[tipo]["children"].append(node_cc)

        # Adiciona os tipos reais (Adm, Oper, etc) logo após os virtuais
        final_tree.extend(list(tipos_map.values()))

        return jsonify(final_tree), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dre_config_bp.route('/Configuracao/AddSubgrupo', methods=['POST'])
@login_required
def AddSubgrupo():
    session = get_session()
    try:
        data = request.json
        nome = data.get('nome')
        parent_node_id = str(data.get('parent_id')) 

        novo_sub = DreSubgrupo(nome=nome)

        # CASO 1: Pai é Raiz CC (ERP) - Ex: "cc_25110501"
        if parent_node_id.startswith("cc_"):
            codigo_cc_str = parent_node_id.replace("cc_", "")
            codigo_cc_int = int(codigo_cc_str)
            
            # Busca info do CC
            sql_info = text("""
                SELECT "Tipo", "Nome" 
                FROM "Dre_Schema"."Tb_Centro_Custo_Classificacao" 
                WHERE "Codigo CC." = :cod LIMIT 1
            """)
            result_info = session.execute(sql_info, {"cod": codigo_cc_int}).first()
            
            if result_info:
                novo_sub.root_cc_tipo = result_info[0]
                novo_sub.root_cc_nome = result_info[1]
            else:
                novo_sub.root_cc_tipo = "Indefinido"
                novo_sub.root_cc_nome = "Indefinido"

            novo_sub.root_cc_codigo = codigo_cc_int
            novo_sub.parent_subgrupo_id = None
            
        # CASO 2: Pai é NÓ VIRTUAL - Ex: "virt_5"
        elif parent_node_id.startswith("virt_"):
            virt_id = int(parent_node_id.replace("virt_", ""))
            no_virt = session.query(DreNoVirtual).get(virt_id)
            
            if no_virt:
                novo_sub.root_virtual_id = virt_id
                novo_sub.root_virtual_nome = no_virt.nome
                novo_sub.parent_subgrupo_id = None
            else:
                raise Exception("Nó virtual não encontrado")

        # CASO 3: Pai é OUTRO SUBGRUPO - Ex: "sg_15"
        elif parent_node_id.startswith("sg_"):
            parent_id = int(parent_node_id.replace("sg_", ""))
            novo_sub.parent_subgrupo_id = parent_id
            
            # Herança Híbrida: Verifica se o pai pertence a CC ou Virtual
            pai = session.query(DreSubgrupo).get(parent_id)
            if pai:
                if pai.root_virtual_id:
                    # Herda estrutura Virtual
                    novo_sub.root_virtual_id = pai.root_virtual_id
                    novo_sub.root_virtual_nome = pai.root_virtual_nome
                elif pai.root_cc_codigo:
                    # Herda estrutura CC
                    novo_sub.root_cc_codigo = pai.root_cc_codigo
                    novo_sub.root_cc_tipo = pai.root_cc_tipo
                    novo_sub.root_cc_nome = pai.root_cc_nome
        else:
            raise Exception("Nó pai inválido.")

        session.add(novo_sub)
        session.commit()
        return jsonify({"success": True}), 200
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
        data = request.json
        nome = data.get('nome')
        if not nome: return jsonify({"error": "Nome obrigatório"}), 400
        
        novo = DreNoVirtual(nome=nome)
        session.add(novo)
        session.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dre_config_bp.route('/Configuracao/VincularConta', methods=['POST'])
@login_required
def VincularConta():
    """ 
    Vincula conta padrão (sem renomear).
    Funciona tanto para Subgrupos de CC quanto para Subgrupos Virtuais.
    """
    session = get_session()
    try:
        data = request.json
        conta = str(data.get('conta')).strip()
        subgrupo_node_id = data.get('subgrupo_id') 

        if not subgrupo_node_id.startswith("sg_"):
            raise Exception("Contas só podem ser vinculadas a Subgrupos.")

        sg_id = int(subgrupo_node_id.replace("sg_", ""))
        
        # 1. Busca o Subgrupo
        subgrupo = session.query(DreSubgrupo).get(sg_id)
        if not subgrupo:
            raise Exception("Subgrupo não encontrado.")
            
        # 2. Lógica de Rastreamento da Raiz (Recursiva)
        # Precisamos saber se esse subgrupo pertence a um CC ou a um Nó Virtual
        temp_parent = subgrupo
        root_cc_code = temp_parent.root_cc_codigo
        root_virt_id = temp_parent.root_virtual_id
        root_tipo = temp_parent.root_cc_tipo or "Virtual"

        # Sobe a árvore até achar a raiz se as infos estiverem vazias no nível atual
        while (root_cc_code is None and root_virt_id is None) and temp_parent.parent_subgrupo_id is not None:
            temp_parent = session.query(DreSubgrupo).get(temp_parent.parent_subgrupo_id)
            root_cc_code = temp_parent.root_cc_codigo
            root_virt_id = temp_parent.root_virtual_id
            root_tipo = temp_parent.root_cc_tipo or "Virtual"

        # 3. Geração das Chaves
        chave_tipo = f"{conta}{root_tipo}"
        
        # AQUI ESTAVA O PROBLEMA: 
        # Se for Virtual, não temos CC Code. Vamos criar uma chave virtual única.
        if root_cc_code is not None:
            # É estrutura de Centro de Custo
            chave_cod = f"{conta}{root_cc_code}"
        elif root_virt_id is not None:
            # É estrutura Virtual
            chave_cod = f"{conta}VIRTUAL{root_virt_id}"
        else:
            raise Exception("Erro de integridade: Subgrupo sem raiz definida (CC ou Virtual).")

        # 4. Salva ou Atualiza
        vinculo = session.query(DreContaVinculo).filter_by(conta_contabil=conta).first()
        if vinculo:
            # Se já existe, move para o novo grupo
            vinculo.subgrupo_id = sg_id
            vinculo.key_conta_tipo_cc = chave_tipo
            vinculo.key_conta_cod_cc = chave_cod
        else:
            # Cria novo
            vinculo = DreContaVinculo(
                conta_contabil=conta, 
                subgrupo_id=sg_id,
                key_conta_tipo_cc=chave_tipo,
                key_conta_cod_cc=chave_cod
            )
            session.add(vinculo)
        
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
    """ Vincula conta personalizada a um Nó Virtual OU Subgrupo """
    session = get_session()
    try:
        data = request.json
        conta = data.get('conta')
        nome_personalizado = data.get('nome_personalizado')
        parent_id = data.get('parent_id') # Ex: "virt_1" ou "sg_5"
        
        if not conta or not parent_id: return jsonify({"error": "Dados incompletos"}), 400

        # Verifica se já existe detalhe para essa conta
        detalhe = session.query(DreContaDetalhe).filter_by(conta_contabil=conta).first()
        if not detalhe:
            detalhe = DreContaDetalhe(conta_contabil=conta)
            session.add(detalhe)
        
        # Atualiza nome
        if nome_personalizado:
            detalhe.nome_personalizado = nome_personalizado
            
        # Define onde pendurar
        if parent_id.startswith("virt_"):
            detalhe.no_virtual_id = int(parent_id.replace("virt_", ""))
            detalhe.subgrupo_id = None
        elif parent_id.startswith("sg_"):
            detalhe.subgrupo_id = int(parent_id.replace("sg_", ""))
            detalhe.no_virtual_id = None
        else:
             return jsonify({"error": "Local inválido para vínculo de detalhe"}), 400

        session.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dre_config_bp.route('/Configuracao/DeleteSubgrupo', methods=['POST'])
@login_required
def DeleteSubgrupo():
    session = get_session()
    try:
        data = request.json
        node_id = data.get('id') 
        
        if not node_id or not node_id.startswith('sg_'):
            return jsonify({"error": "Nó inválido para exclusão"}), 400
            
        db_id = int(node_id.replace('sg_', ''))
        
        has_sub_children = session.query(DreSubgrupo).filter_by(parent_subgrupo_id=db_id).count()
        has_contas = session.query(DreContaVinculo).filter_by(subgrupo_id=db_id).count()
        has_detalhes = session.query(DreContaDetalhe).filter_by(subgrupo_id=db_id).count()
        
        if has_sub_children > 0 or has_contas > 0 or has_detalhes > 0:
            return jsonify({"error": "Não é possível excluir: Este grupo possui itens dentro dele."}), 400

        subgrupo = session.query(DreSubgrupo).get(db_id)
        if subgrupo:
            session.delete(subgrupo)
            session.commit()
            return jsonify({"success": True}), 200
        else:
            return jsonify({"error": "Subgrupo não encontrado"}), 404

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
        data = request.json
        node_id = data.get('id')
        
        # Verifica se é conta normal ou detalhe
        if node_id.startswith('conta_'):
            # Desvincula da tabela Padrão
            conta_contabil = node_id.replace('conta_', '')
            vinculo = session.query(DreContaVinculo).filter_by(conta_contabil=conta_contabil).first()
            if vinculo:
                session.delete(vinculo)
                session.commit()
                return jsonify({"success": True}), 200
            
        elif node_id.startswith('cd_'):
            # Desvincula da tabela Detalhe
            cd_id = int(node_id.replace('cd_', ''))
            detalhe = session.query(DreContaDetalhe).get(cd_id)
            if detalhe:
                session.delete(detalhe)
                session.commit()
                return jsonify({"success": True}), 200
        
        return jsonify({"error": "Vínculo não encontrado"}), 404
            
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

# --- NOVA ROTA: DELETAR NÓ VIRTUAL ---
@dre_config_bp.route('/Configuracao/DeleteNoVirtual', methods=['POST'])
@login_required
def DeleteNoVirtual():
    session = get_session()
    try:
        data = request.json
        node_id = data.get('id')
        
        if not node_id or not node_id.startswith('virt_'):
            return jsonify({"error": "Nó inválido"}), 400
            
        db_id = int(node_id.replace('virt_', ''))
        
        # Verificações de segurança
        has_sub_children = session.query(DreSubgrupo).filter_by(root_virtual_id=db_id).count()
        has_contas = session.query(DreContaDetalhe).filter_by(no_virtual_id=db_id).count()
        
        if has_sub_children > 0 or has_contas > 0:
            return jsonify({"error": "Não é possível excluir: Este nó possui itens (grupos ou contas) dentro dele."}), 400

        no_virtual = session.query(DreNoVirtual).get(db_id)
        if no_virtual:
            session.delete(no_virtual)
            session.commit()
            return jsonify({"success": True}), 200
        else:
            return jsonify({"error": "Nó virtual não encontrado"}), 404

    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dre_config_bp.route('/Configuracao/ReplicarEstrutura', methods=['POST'])
@login_required
def ReplicarEstrutura():
    session = get_session()
    try:
        data = request.json
        origem_node_id = data.get('origem_node_id') # Ex: "cc_2511", "virt_1", "sg_50"
        destinos_ids = data.get('destinos_ids', []) # Lista de IDs numéricos dos destinos (Raízes)

        if not destinos_ids:
            return jsonify({"error": "Selecione ao menos um destino."}), 400

        # --- 1. IDENTIFICA O QUE ESTÁ SENDO COPIADO ---
        
        itens_para_clonar = [] # Lista de objetos DreSubgrupo para clonar
        tipo_origem = ""       # 'CC', 'VIRT', 'SUB_CC', 'SUB_VIRT'

        if origem_node_id.startswith("cc_"):
            # Copiar TODA a estrutura de um Centro de Custo
            cc_id = int(origem_node_id.replace("cc_", ""))
            itens_para_clonar = session.query(DreSubgrupo).filter_by(root_cc_codigo=cc_id, parent_subgrupo_id=None).all()
            tipo_origem = 'CC'
            
        elif origem_node_id.startswith("virt_"):
            # Copiar TODA a estrutura de um Nó Virtual
            virt_id = int(origem_node_id.replace("virt_", ""))
            itens_para_clonar = session.query(DreSubgrupo).filter_by(root_virtual_id=virt_id, parent_subgrupo_id=None).all()
            tipo_origem = 'VIRT'
            
        elif origem_node_id.startswith("sg_"):
            # Copiar UM SUBGRUPO ESPECÍFICO (e seus filhos)
            sg_id = int(origem_node_id.replace("sg_", ""))
            subgrupo = session.query(DreSubgrupo).get(sg_id)
            if subgrupo:
                itens_para_clonar = [subgrupo]
                if subgrupo.root_cc_codigo: tipo_origem = 'SUB_CC'
                elif subgrupo.root_virtual_id: tipo_origem = 'SUB_VIRT'

        if not itens_para_clonar:
            return jsonify({"error": "Não há itens para clonar na origem selecionada."}), 400

        # --- 2. FUNÇÃO RECURSIVA DE CLONAGEM ---
        def clonar_recursivo(sub_origem, novo_pai_id, target_cc_code=None, target_virt_id=None, target_virt_nome=None):
            # Busca info do CC destino se necessário (para preencher nome/tipo corretamente)
            target_cc_tipo = None
            target_cc_nome = None
            
            if target_cc_code:
                # Pequena query auxiliar para pegar dados do CC destino
                sql_cc = text('SELECT "Tipo", "Nome" FROM "Dre_Schema"."Tb_Centro_Custo_Classificacao" WHERE "Codigo CC." = :cod')
                res_cc = session.execute(sql_cc, {"cod": target_cc_code}).first()
                if res_cc:
                    target_cc_tipo = res_cc[0]
                    target_cc_nome = res_cc[1]

            # Cria o novo subgrupo
            novo_sub = DreSubgrupo(
                nome=sub_origem.nome,
                parent_subgrupo_id=novo_pai_id,
                # Dados de CC
                root_cc_codigo=target_cc_code,
                root_cc_tipo=target_cc_tipo,
                root_cc_nome=target_cc_nome,
                # Dados de Virtual
                root_virtual_id=target_virt_id,
                root_virtual_nome=target_virt_nome
            )
            session.add(novo_sub)
            session.flush() # Gera o ID

            # A. Copia Vínculos Normais (Tb_Dre_Conta_Vinculo)
            vinculos = session.query(DreContaVinculo).filter_by(subgrupo_id=sub_origem.id).all()
            for v in vinculos:
                chave_cod = None
                chave_tipo = None
                
                if target_cc_code:
                    chave_cod = f"{v.conta_contabil}{target_cc_code}"
                    chave_tipo = f"{v.conta_contabil}{target_cc_tipo}"
                elif target_virt_id:
                    chave_cod = f"{v.conta_contabil}VIRTUAL{target_virt_id}"
                    chave_tipo = f"{v.conta_contabil}Virtual"

                # Evita duplicidade na chave
                existe = session.query(DreContaVinculo).filter_by(key_conta_cod_cc=chave_cod).first()
                if not existe:
                    novo_v = DreContaVinculo(
                        conta_contabil=v.conta_contabil,
                        subgrupo_id=novo_sub.id,
                        key_conta_tipo_cc=chave_tipo,
                        key_conta_cod_cc=chave_cod
                    )
                    session.add(novo_v)

            # B. Copia Contas Detalhe (Apenas se for Virtual -> Virtual)
            if target_virt_id:
                detalhes = session.query(DreContaDetalhe).filter_by(subgrupo_id=sub_origem.id).all()
                for d in detalhes:
                    # Verifica se conta já existe solta ou em outro lugar (opcional, aqui permitimos duplicar o detalhe em outro nó)
                    novo_d = DreContaDetalhe(
                        conta_contabil=d.conta_contabil,
                        nome_personalizado=d.nome_personalizado,
                        subgrupo_id=novo_sub.id,
                        no_virtual_id=None # Fica null pois está ligado ao subgrupo
                    )
                    session.add(novo_d)

            # Recursão para filhos
            filhos = session.query(DreSubgrupo).filter_by(parent_subgrupo_id=sub_origem.id).all()
            for filho in filhos:
                clonar_recursivo(filho, novo_sub.id, target_cc_code, target_virt_id, target_virt_nome)


        # --- 3. EXECUÇÃO DA CLONAGEM PARA CADA DESTINO ---
        count_sucesso = 0
        
        for dest_id in destinos_ids:
            dest_id = int(dest_id)
            
            # Define os parâmetros de destino baseado no tipo da origem
            t_cc = None
            t_virt_id = None
            t_virt_nome = None

            if tipo_origem in ['CC', 'SUB_CC']:
                t_cc = dest_id
            elif tipo_origem in ['VIRT', 'SUB_VIRT']:
                t_virt_id = dest_id
                # Busca nome do virtual destino
                no_virt = session.query(DreNoVirtual).get(dest_id)
                if no_virt: t_virt_nome = no_virt.nome

            # Clona cada item raiz da lista
            for item in itens_para_clonar:
                # Verifica se já existe um grupo com esse nome na raiz do destino (Merge seguro)
                filtro_existente = {
                    'nome': item.nome,
                    'parent_subgrupo_id': None
                }
                if t_cc: filtro_existente['root_cc_codigo'] = t_cc
                if t_virt_id: filtro_existente['root_virtual_id'] = t_virt_id
                
                existe = session.query(DreSubgrupo).filter_by(**filtro_existente).first()
                
                if not existe:
                    clonar_recursivo(item, None, t_cc, t_virt_id, t_virt_nome)
            
            count_sucesso += 1

        session.commit()
        return jsonify({"success": True, "msg": f"Estrutura replicada com sucesso para {count_sucesso} destinos!"}), 200

    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
        
# --- NOVA ROTA: COLAR ESTRUTURA (Deep Copy) ---
@dre_config_bp.route('/Configuracao/ColarEstrutura', methods=['POST'])
@login_required
def ColarEstrutura():
    session = get_session()
    try:
        data = request.json
        origem_id_str = data.get('origem_id')  # Ex: "sg_50"
        destino_id_str = data.get('destino_id') # Ex: "sg_90" ou "cc_2511"

        if not origem_id_str or not destino_id_str:
            return jsonify({"error": "Origem ou Destino inválidos."}), 400

        # 1. Identificar a ORIGEM (O que será copiado?)
        subgrupo_origem = None
        if origem_id_str.startswith("sg_"):
            sg_id = int(origem_id_str.replace("sg_", ""))
            subgrupo_origem = session.query(DreSubgrupo).get(sg_id)
        else:
            return jsonify({"error": "Apenas Subgrupos podem ser copiados/colados."}), 400

        if not subgrupo_origem:
            return jsonify({"error": "Grupo de origem não encontrado."}), 404

        # 2. Identificar o DESTINO (Onde será colado?)
        # Precisamos descobrir quem será o Pai e qual é o Contexto Raiz (CC ou Virtual)
        novo_pai_id = None
        target_cc_code = None
        target_cc_tipo = None
        target_cc_nome = None
        target_virt_id = None
        target_virt_nome = None

        # CASO A: Colando dentro de um Centro de Custo Raiz
        if destino_id_str.startswith("cc_"):
            target_cc_code = int(destino_id_str.replace("cc_", ""))
            novo_pai_id = None # Fica na raiz
            
            # Busca dados do CC
            sql_cc = text('SELECT "Tipo", "Nome" FROM "Dre_Schema"."Tb_Centro_Custo_Classificacao" WHERE "Codigo CC." = :cod')
            res_cc = session.execute(sql_cc, {"cod": target_cc_code}).first()
            if res_cc:
                target_cc_tipo = res_cc[0]
                target_cc_nome = res_cc[1]

        # CASO B: Colando dentro de um Nó Virtual Raiz
        elif destino_id_str.startswith("virt_"):
            target_virt_id = int(destino_id_str.replace("virt_", ""))
            novo_pai_id = None
            no_virt = session.query(DreNoVirtual).get(target_virt_id)
            if no_virt: target_virt_nome = no_virt.nome

        # CASO C: Colando dentro de outro Subgrupo (Aninhamento)
        elif destino_id_str.startswith("sg_"):
            novo_pai_id = int(destino_id_str.replace("sg_", ""))
            # O destino herda o contexto do pai onde está sendo colado
            pai_destino = session.query(DreSubgrupo).get(novo_pai_id)
            if pai_destino:
                target_cc_code = pai_destino.root_cc_codigo
                target_cc_tipo = pai_destino.root_cc_tipo
                target_cc_nome = pai_destino.root_cc_nome
                target_virt_id = pai_destino.root_virtual_id
                target_virt_nome = pai_destino.root_virtual_nome
        
        # Evita colar um grupo dentro dele mesmo (Ciclo)
        if novo_pai_id == subgrupo_origem.id:
             return jsonify({"error": "Não é possível colar um grupo dentro dele mesmo."}), 400


        # 3. FUNÇÃO RECURSIVA DE CLONAGEM
        def clonar_recursivo(sub_source, id_pai_novo):
            # Cria o clone do grupo
            novo_sub = DreSubgrupo(
                nome=sub_source.nome,
                parent_subgrupo_id=id_pai_novo,
                root_cc_codigo=target_cc_code,
                root_cc_tipo=target_cc_tipo,
                root_cc_nome=target_cc_nome,
                root_virtual_id=target_virt_id,
                root_virtual_nome=target_virt_nome
            )
            session.add(novo_sub)
            session.flush() # Gera ID

            # A. Copia Vínculos Normais (Contas)
            vinculos = session.query(DreContaVinculo).filter_by(subgrupo_id=sub_source.id).all()
            for v in vinculos:
                chave_cod = None
                chave_tipo = None
                
                if target_cc_code:
                    chave_cod = f"{v.conta_contabil}{target_cc_code}"
                    chave_tipo = f"{v.conta_contabil}{target_cc_tipo}"
                elif target_virt_id:
                    chave_cod = f"{v.conta_contabil}VIRTUAL{target_virt_id}"
                    chave_tipo = f"{v.conta_contabil}Virtual"

                # Verifica duplicidade antes de inserir
                existe = session.query(DreContaVinculo).filter_by(key_conta_cod_cc=chave_cod).first()
                if not existe and chave_cod:
                    novo_v = DreContaVinculo(
                        conta_contabil=v.conta_contabil,
                        subgrupo_id=novo_sub.id,
                        key_conta_tipo_cc=chave_tipo,
                        key_conta_cod_cc=chave_cod
                    )
                    session.add(novo_v)

            # B. Copia Contas Detalhe (Apenas para Virtual)
            detalhes = session.query(DreContaDetalhe).filter_by(subgrupo_id=sub_source.id).all()
            for d in detalhes:
                novo_d = DreContaDetalhe(
                    conta_contabil=d.conta_contabil,
                    nome_personalizado=d.nome_personalizado,
                    subgrupo_id=novo_sub.id,
                    no_virtual_id=None
                )
                session.add(novo_d)

            # C. Recursão para subgrupos filhos
            filhos = session.query(DreSubgrupo).filter_by(parent_subgrupo_id=sub_source.id).all()
            for filho in filhos:
                clonar_recursivo(filho, novo_sub.id)

        # Executa
        clonar_recursivo(subgrupo_origem, novo_pai_id)
        
        session.commit()
        return jsonify({"success": True}), 200

    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()