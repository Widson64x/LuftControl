"""
Routes/DreConfig.py
Rotas para Configuração da Árvore DRE (Demonstração do Resultado do Exercício)
VERSÃO ATUALIZADA - Nomenclatura refatorada
"""

from flask import Blueprint, jsonify, request, abort, render_template
from flask_login import login_required
from sqlalchemy import text
from Db.Connections import get_postgres_engine
from sqlalchemy.orm import sessionmaker

# Imports atualizados com novos nomes
from Models.POSTGRESS.DreEstrutura import (
    DreHierarquia, 
    DreContaVinculo, 
    DreNoVirtual, 
    DreContaPersonalizada
)
from Models.POSTGRESS.Rentabilidade import RazaoConsolidado

dre_config_bp = Blueprint('DreConfig', __name__)


def get_session():
    """Cria e retorna uma sessão do PostgreSQL"""
    engine = get_postgres_engine()
    Session = sessionmaker(bind=engine)
    return Session()


@dre_config_bp.route('/Configuracao/Arvore', methods=['GET'])
@login_required
def ViewConfiguracao():
    """Renderiza a página de configuração da árvore DRE"""
    return render_template('MENUS/ConfiguracaoDRE.html')


@dre_config_bp.route('/Configuracao/GetContasDisponiveis', methods=['GET'])
@login_required
def GetContasDisponiveis():
    """
    Retorna lista de contas contábeis disponíveis para vinculação.
    Busca contas distintas da VIEW consolidada.
    """
    session = get_session()
    try:
        sql = text("""
            SELECT DISTINCT "Conta", "Título Conta"
            FROM "Dre_Schema"."Razao_Dados_Consolidado"
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
    Monta a árvore híbrida da DRE:
    1. Estrutura Virtual (Faturamento, Impostos...) - TOPO
    2. Estrutura Padrão (Centros de Custo do ERP)
    
    ATUALIZADO: Usa nomenclatura nova das tabelas e colunas
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

        # 2. Busca Dados Dinâmicos (NOMES ATUALIZADOS)
        subgrupos = session.query(DreHierarquia).all()
        vinculos = session.query(DreContaVinculo).all()
        virtuais = session.query(DreNoVirtual).order_by(DreNoVirtual.Ordem).all()
        contas_detalhe = session.query(DreContaPersonalizada).all()

        # --- HELPERS DE MONTAGEM ---
        
        def get_contas_normais(sub_id):
            """Retorna contas normais vinculadas a um subgrupo"""
            return [
                {
                    "id": f"conta_{v.Conta_Contabil}", 
                    "text": f"Conta: {v.Conta_Contabil}", 
                    "type": "conta", 
                    "parent": sub_id
                } 
                for v in vinculos if v.Id_Hierarquia == sub_id
            ]

        def get_contas_detalhe(sub_id):
            """Retorna contas personalizadas vinculadas a um subgrupo"""
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
            """Recursivamente busca subgrupos filhos"""
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

        # --- LISTA FINAL QUE SERÁ RETORNADA ---
        final_tree = []

        # --- 1. MONTAGEM DA ÁRVORE VIRTUAL (PRIMEIRO NA LISTA) ---
        for v in virtuais:
            children_virtual = []
            
            # Subgrupos ligados diretamente a este Nó Virtual
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

            # Contas Detalhe ligadas diretamente ao Nó Virtual
            for c in contas_detalhe:
                if c.Id_No_Virtual == v.Id:
                    label = f"{c.Conta_Contabil} ({c.Nome_Personalizado or ''})"
                    children_virtual.append({
                        "id": f"cd_{c.Id}", 
                        "text": label, 
                        "type": "conta_detalhe", 
                        "parent": f"virt_{v.Id}"
                    })
            
            # O Nó Virtual agora é um "Root" por si só
            node_virtual = {
                "id": f"virt_{v.Id}",
                "text": v.Nome,
                "type": "root_virtual",
                "children": children_virtual
            }
            final_tree.append(node_virtual)

        # --- 2. MONTAGEM DA ÁRVORE PADRÃO (CENTROS DE CUSTO) ---
        tipos_map = {}
        
        for row in base_result:
            tipo = row['Tipo']
            nome_cc = row['Nome']
            codigo_cc = row['Codigo']  # ← ATUALIZADO
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
    """
    Adiciona um novo subgrupo à hierarquia.
    Pode ser filho de: Centro de Custo, Nó Virtual ou outro Subgrupo.
    
    ATUALIZADO: Usa novos nomes de atributos
    """
    session = get_session()
    try:
        data = request.json
        nome = data.get('nome')
        parent_node_id = str(data.get('parent_id')) 

        novo_sub = DreHierarquia(Nome=nome)

        # CASO 1: Pai é Raiz CC (ERP) - Ex: "cc_25110501"
        if parent_node_id.startswith("cc_"):
            codigo_cc_str = parent_node_id.replace("cc_", "")
            codigo_cc_int = int(codigo_cc_str)
            
            # Busca info do CC
            sql_info = text("""
                SELECT "Tipo", "Nome" 
                FROM "Dre_Schema"."Classificacao_Centro_Custo" 
                WHERE "Codigo" = :cod LIMIT 1
            """)
            result_info = session.execute(sql_info, {"cod": codigo_cc_int}).first()
            
            if result_info:
                novo_sub.Raiz_Centro_Custo_Tipo = result_info[0]
                novo_sub.Raiz_Centro_Custo_Nome = result_info[1]
            else:
                novo_sub.Raiz_Centro_Custo_Tipo = "Indefinido"
                novo_sub.Raiz_Centro_Custo_Nome = "Indefinido"

            novo_sub.Raiz_Centro_Custo_Codigo = codigo_cc_int
            novo_sub.Id_Pai = None
            
        # CASO 2: Pai é NÓ VIRTUAL - Ex: "virt_5"
        elif parent_node_id.startswith("virt_"):
            virt_id = int(parent_node_id.replace("virt_", ""))
            no_virt = session.query(DreNoVirtual).get(virt_id)
            
            if no_virt:
                novo_sub.Raiz_No_Virtual_Id = virt_id
                novo_sub.Raiz_No_Virtual_Nome = no_virt.Nome
                novo_sub.Id_Pai = None
            else:
                raise Exception("Nó virtual não encontrado")

        # CASO 3: Pai é OUTRO SUBGRUPO - Ex: "sg_15"
        elif parent_node_id.startswith("sg_"):
            parent_id = int(parent_node_id.replace("sg_", ""))
            novo_sub.Id_Pai = parent_id
            
            # Herança Híbrida: Verifica se o pai pertence a CC ou Virtual
            pai = session.query(DreHierarquia).get(parent_id)
            if pai:
                if pai.Raiz_No_Virtual_Id:
                    # Herda estrutura Virtual
                    novo_sub.Raiz_No_Virtual_Id = pai.Raiz_No_Virtual_Id
                    novo_sub.Raiz_No_Virtual_Nome = pai.Raiz_No_Virtual_Nome
                elif pai.Raiz_Centro_Custo_Codigo:
                    # Herda estrutura CC
                    novo_sub.Raiz_Centro_Custo_Codigo = pai.Raiz_Centro_Custo_Codigo
                    novo_sub.Raiz_Centro_Custo_Tipo = pai.Raiz_Centro_Custo_Tipo
                    novo_sub.Raiz_Centro_Custo_Nome = pai.Raiz_Centro_Custo_Nome
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
    """
    Adiciona um novo Nó Virtual (ex: Faturamento Líquido, Impostos).
    
    ATUALIZADO: Usa novos nomes de atributos
    """
    session = get_session()
    try:
        data = request.json
        nome = data.get('nome')
        
        if not nome: 
            return jsonify({"error": "Nome obrigatório"}), 400
        
        novo = DreNoVirtual(Nome=nome)
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
    
    ATUALIZADO: Usa novos nomes de atributos e tabelas
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
        subgrupo = session.query(DreHierarquia).get(sg_id)
        if not subgrupo:
            raise Exception("Subgrupo não encontrado.")
            
        # 2. Lógica de Rastreamento da Raiz (Recursiva)
        temp_parent = subgrupo
        root_cc_code = temp_parent.Raiz_Centro_Custo_Codigo
        root_virt_id = temp_parent.Raiz_No_Virtual_Id
        root_tipo = temp_parent.Raiz_Centro_Custo_Tipo or "Virtual"

        # Sobe a árvore até achar a raiz se as infos estiverem vazias
        while (root_cc_code is None and root_virt_id is None) and temp_parent.Id_Pai is not None:
            temp_parent = session.query(DreHierarquia).get(temp_parent.Id_Pai)
            root_cc_code = temp_parent.Raiz_Centro_Custo_Codigo
            root_virt_id = temp_parent.Raiz_No_Virtual_Id
            root_tipo = temp_parent.Raiz_Centro_Custo_Tipo or "Virtual"

        # 3. Geração das Chaves
        chave_tipo = f"{conta}{root_tipo}"
        
        if root_cc_code is not None:
            # É estrutura de Centro de Custo
            chave_cod = f"{conta}{root_cc_code}"
        elif root_virt_id is not None:
            # É estrutura Virtual
            chave_cod = f"{conta}VIRTUAL{root_virt_id}"
        else:
            raise Exception("Erro de integridade: Subgrupo sem raiz definida (CC ou Virtual).")

        # 4. Salva ou Atualiza
        vinculo = session.query(DreContaVinculo).filter_by(Conta_Contabil=conta).first()
        
        if vinculo:
            # Se já existe, move para o novo grupo
            vinculo.Id_Hierarquia = sg_id
            vinculo.Chave_Conta_Tipo_CC = chave_tipo
            vinculo.Chave_Conta_Codigo_CC = chave_cod
        else:
            # Cria novo
            vinculo = DreContaVinculo(
                Conta_Contabil=conta, 
                Id_Hierarquia=sg_id,
                Chave_Conta_Tipo_CC=chave_tipo,
                Chave_Conta_Codigo_CC=chave_cod
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
    """ 
    Vincula conta personalizada a um Nó Virtual OU Subgrupo.
    Permite renomear a conta para exibição customizada.
    
    ATUALIZADO: Usa novos nomes de atributos
    """
    session = get_session()
    try:
        data = request.json
        conta = data.get('conta')
        nome_personalizado = data.get('nome_personalizado')
        parent_id = data.get('parent_id')  # Ex: "virt_1" ou "sg_5"
        
        if not conta or not parent_id: 
            return jsonify({"error": "Dados incompletos"}), 400

        # Verifica se já existe detalhe para essa conta
        detalhe = session.query(DreContaPersonalizada).filter_by(Conta_Contabil=conta).first()
        
        if not detalhe:
            detalhe = DreContaPersonalizada(Conta_Contabil=conta)
            session.add(detalhe)
        
        # Atualiza nome
        if nome_personalizado:
            detalhe.Nome_Personalizado = nome_personalizado
            
        # Define onde pendurar
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


@dre_config_bp.route('/Configuracao/DeleteSubgrupo', methods=['POST'])
@login_required
def DeleteSubgrupo():
    """
    Deleta um subgrupo da hierarquia.
    Apenas permite exclusão se não houver itens dentro.
    
    ATUALIZADO: Usa novos nomes de atributos
    """
    session = get_session()
    try:
        data = request.json
        node_id = data.get('id') 
        
        if not node_id or not node_id.startswith('sg_'):
            return jsonify({"error": "Nó inválido para exclusão"}), 400
            
        db_id = int(node_id.replace('sg_', ''))
        
        # Verificações de segurança
        has_sub_children = session.query(DreHierarquia).filter_by(Id_Pai=db_id).count()
        has_contas = session.query(DreContaVinculo).filter_by(Id_Hierarquia=db_id).count()
        has_detalhes = session.query(DreContaPersonalizada).filter_by(Id_Hierarquia=db_id).count()
        
        if has_sub_children > 0 or has_contas > 0 or has_detalhes > 0:
            return jsonify({
                "error": "Não é possível excluir: Este grupo possui itens dentro dele."
            }), 400

        subgrupo = session.query(DreHierarquia).get(db_id)
        
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
    """
    Desvincula uma conta da estrutura DRE.
    Funciona tanto para contas normais quanto personalizadas.
    
    ATUALIZADO: Usa novos nomes de atributos
    """
    session = get_session()
    try:
        data = request.json
        node_id = data.get('id')
        
        # Verifica se é conta normal ou detalhe
        if node_id.startswith('conta_'):
            # Desvincula da tabela Padrão
            conta_contabil = node_id.replace('conta_', '')
            vinculo = session.query(DreContaVinculo).filter_by(
                Conta_Contabil=conta_contabil
            ).first()
            
            if vinculo:
                session.delete(vinculo)
                session.commit()
                return jsonify({"success": True}), 200
            
        elif node_id.startswith('cd_'):
            # Desvincula da tabela Detalhe
            cd_id = int(node_id.replace('cd_', ''))
            detalhe = session.query(DreContaPersonalizada).get(cd_id)
            
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


@dre_config_bp.route('/Configuracao/DeleteNoVirtual', methods=['POST'])
@login_required
def DeleteNoVirtual():
    """
    Deleta um Nó Virtual da estrutura.
    Apenas permite exclusão se não houver itens dentro.
    
    ATUALIZADO: Usa novos nomes de atributos
    """
    session = get_session()
    try:
        data = request.json
        node_id = data.get('id')
        
        if not node_id or not node_id.startswith('virt_'):
            return jsonify({"error": "Nó inválido"}), 400
            
        db_id = int(node_id.replace('virt_', ''))
        
        # Verificações de segurança
        has_sub_children = session.query(DreHierarquia).filter_by(
            Raiz_No_Virtual_Id=db_id
        ).count()
        has_contas = session.query(DreContaPersonalizada).filter_by(
            Id_No_Virtual=db_id
        ).count()
        
        if has_sub_children > 0 or has_contas > 0:
            return jsonify({
                "error": "Não é possível excluir: Este nó possui itens (grupos ou contas) dentro dele."
            }), 400

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
    """
    Replica uma estrutura completa (CC, Virtual ou Subgrupo) para múltiplos destinos.
    Copia recursivamente toda a hierarquia de subgrupos e contas.
    
    ATUALIZADO: Usa novos nomes de atributos e tabelas
    """
    session = get_session()
    try:
        data = request.json
        origem_node_id = data.get('origem_node_id')  # Ex: "cc_2511", "virt_1", "sg_50"
        destinos_ids = data.get('destinos_ids', [])  # Lista de IDs numéricos dos destinos

        if not destinos_ids:
            return jsonify({"error": "Selecione ao menos um destino."}), 400

        # --- 1. IDENTIFICA O QUE ESTÁ SENDO COPIADO ---
        itens_para_clonar = []
        tipo_origem = ""

        if origem_node_id.startswith("cc_"):
            # Copiar TODA a estrutura de um Centro de Custo
            cc_id = int(origem_node_id.replace("cc_", ""))
            itens_para_clonar = session.query(DreHierarquia).filter_by(
                Raiz_Centro_Custo_Codigo=cc_id, 
                Id_Pai=None
            ).all()
            tipo_origem = 'CC'
            
        elif origem_node_id.startswith("virt_"):
            # Copiar TODA a estrutura de um Nó Virtual
            virt_id = int(origem_node_id.replace("virt_", ""))
            itens_para_clonar = session.query(DreHierarquia).filter_by(
                Raiz_No_Virtual_Id=virt_id, 
                Id_Pai=None
            ).all()
            tipo_origem = 'VIRT'
            
        elif origem_node_id.startswith("sg_"):
            # Copiar UM SUBGRUPO ESPECÍFICO (e seus filhos)
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

        # --- 2. FUNÇÃO RECURSIVA DE CLONAGEM ---
        def clonar_recursivo(sub_origem, novo_pai_id, target_cc_code=None, 
                           target_virt_id=None, target_virt_nome=None):
            """
            Clona recursivamente um subgrupo e todos os seus filhos.
            """
            # Busca info do CC destino se necessário
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

            # Cria o novo subgrupo
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
            session.flush()  # Gera o ID

            # A. Copia Vínculos Normais
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

                # Evita duplicidade na chave
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

            # B. Copia Contas Detalhe (Apenas se for Virtual -> Virtual)
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

            # C. Recursão para filhos
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

        # --- 3. EXECUÇÃO DA CLONAGEM PARA CADA DESTINO ---
        count_sucesso = 0
        
        for dest_id in destinos_ids:
            dest_id = int(dest_id)
            
            # Define os parâmetros de destino
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

            # Clona cada item raiz da lista
            for item in itens_para_clonar:
                # Verifica se já existe (Merge seguro)
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
    """
    Cola (Deep Copy) uma estrutura de subgrupo em outro local.
    Diferente de Replicar, permite colar dentro de outro subgrupo.
    
    ATUALIZADO: Usa novos nomes de atributos e tabelas
    """
    session = get_session()
    try:
        data = request.json
        origem_id_str = data.get('origem_id')   # Ex: "sg_50"
        destino_id_str = data.get('destino_id')  # Ex: "sg_90" ou "cc_2511"

        if not origem_id_str or not destino_id_str:
            return jsonify({"error": "Origem ou Destino inválidos."}), 400

        # 1. Identificar a ORIGEM
        subgrupo_origem = None
        
        if origem_id_str.startswith("sg_"):
            sg_id = int(origem_id_str.replace("sg_", ""))
            subgrupo_origem = session.query(DreHierarquia).get(sg_id)
        else:
            return jsonify({"error": "Apenas Subgrupos podem ser copiados/colados."}), 400

        if not subgrupo_origem:
            return jsonify({"error": "Grupo de origem não encontrado."}), 404

        # 2. Identificar o DESTINO
        novo_pai_id = None
        target_cc_code = None
        target_cc_tipo = None
        target_cc_nome = None
        target_virt_id = None
        target_virt_nome = None

        # CASO A: Colando dentro de um Centro de Custo Raiz
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

        # CASO B: Colando dentro de um Nó Virtual Raiz
        elif destino_id_str.startswith("virt_"):
            target_virt_id = int(destino_id_str.replace("virt_", ""))
            novo_pai_id = None
            no_virt = session.query(DreNoVirtual).get(target_virt_id)
            if no_virt: 
                target_virt_nome = no_virt.Nome

        # CASO C: Colando dentro de outro Subgrupo
        elif destino_id_str.startswith("sg_"):
            novo_pai_id = int(destino_id_str.replace("sg_", ""))
            pai_destino = session.query(DreHierarquia).get(novo_pai_id)
            
            if pai_destino:
                target_cc_code = pai_destino.Raiz_Centro_Custo_Codigo
                target_cc_tipo = pai_destino.Raiz_Centro_Custo_Tipo
                target_cc_nome = pai_destino.Raiz_Centro_Custo_Nome
                target_virt_id = pai_destino.Raiz_No_Virtual_Id
                target_virt_nome = pai_destino.Raiz_No_Virtual_Nome
        
        # Evita colar dentro de si mesmo
        if novo_pai_id == subgrupo_origem.Id:
            return jsonify({"error": "Não é possível colar um grupo dentro dele mesmo."}), 400

        # 3. FUNÇÃO RECURSIVA DE CLONAGEM
        def clonar_recursivo(sub_source, id_pai_novo):
            """Clone recursivo do subgrupo"""
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

            # A. Copia Vínculos
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

            # B. Copia Contas Detalhe
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

            # C. Recursão para filhos
            filhos = session.query(DreHierarquia).filter_by(
                Id_Pai=sub_source.Id
            ).all()
            
            for filho in filhos:
                clonar_recursivo(filho, novo_sub.Id)

        # Executa clonagem
        clonar_recursivo(subgrupo_origem, novo_pai_id)
        
        session.commit()
        return jsonify({"success": True}), 200

    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()