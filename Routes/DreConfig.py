"""
Routes/DreConfig.py
Rotas para Configuração da Árvore DRE (Demonstração do Resultado do Exercício)
VERSÃO ATUALIZADA - Nomenclatura refatorada
"""

from flask import Blueprint, jsonify, request, abort, render_template
from flask_login import login_required
from sqlalchemy import text, func
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
# Imports adicionais para o sistema de ordem
from Models.POSTGRESS.DreOrdenamento import DreOrdenamento, calcular_proxima_ordem

dre_config_bp = Blueprint('DreConfig', __name__)


def get_session():
    """Cria e retorna uma sessão do PostgreSQL"""
    engine = get_postgres_engine()
    Session = sessionmaker(bind=engine)
    return Session()

@dre_config_bp.route('/Configuracao/CorrigirBanco', methods=['GET'])
def CorrigirBanco():
    """
    Rota utilitária para remover a constraint antiga que bloqueia duplicidade de contas.
    """
    session = get_session()
    try:
        # Comando para remover a trava antiga
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
    session = get_session()
    try:
        # 1. Remove a constraint UNIQUE antiga da coluna Conta_Contabil
        session.execute(text("""
            ALTER TABLE "Dre_Schema"."DRE_Estrutura_Conta_Personalizada" 
            DROP CONSTRAINT IF EXISTS "DRE_Estrutura_Conta_Personalizada_Conta_Contabil_key";
        """))
        
        # 2. Adiciona uma nova constraint composta (Conta + Grupo) para evitar duplicidade NO MESMO GRUPO, mas permitir em grupos diferentes
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
        
@dre_config_bp.route('/Configuracao/Arvore', methods=['GET'])
@login_required
def ViewConfiguracao():
    """Renderiza a página de configuração da árvore DRE"""
    return render_template('MENUS/ConfiguracaoDRE.html')


# --- ADICIONE ESTAS ROTAS NO FINAL DO ARQUIVO ---

@dre_config_bp.route('/Configuracao/RenameNoVirtual', methods=['POST'])
@login_required
def RenameNoVirtual():
    session = get_session()
    try:
        data = request.json
        # O ID vem como "virt_5", precisamos limpar
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
    session = get_session()
    try:
        data = request.json
        # O ID vem como "sg_10", precisamos limpar
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
    session = get_session()
    try:
        data = request.json
        # O ID vem como "cd_55", precisamos limpar
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
    Monta a árvore híbrida da DRE.
    ATUALIZADO: Agora busca o nome da conta contábil para exibir "Conta - Nome".
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

        # --- NOVO: Busca Mapa de Nomes das Contas ---
        # Cria um dicionário { '603010...': 'SALARIOS', ... } para acesso rápido
        sql_nomes = text("""
            SELECT DISTINCT "Conta", "Título Conta"
            FROM "Dre_Schema"."Razao_Dados_Consolidado"
            WHERE "Conta" IS NOT NULL
        """)
        res_nomes = session.execute(sql_nomes).fetchall()
        # Dicionário mágico: chave=numero, valor=nome
        mapa_nomes_contas = {str(row[0]): row[1] for row in res_nomes}

        # --- HELPERS DE MONTAGEM ---
        
        def get_contas_normais(sub_id):
            """Retorna contas normais vinculadas a um subgrupo com NOME"""
            lista = []
            for v in vinculos:
                if v.Id_Hierarquia == sub_id:
                    # Busca o nome no dicionário que criamos acima
                    conta_num = str(v.Conta_Contabil)
                    nome_conta = mapa_nomes_contas.get(conta_num, "Sem Título")
                    
                    # Formata o texto para: "Conta: 6030... - SALARIOS"
                    label_exibicao = f"Conta: {conta_num} - {nome_conta}"
                    
                    lista.append({
                        "id": f"conta_{conta_num}", 
                        "text": label_exibicao, # <--- AQUI ESTÁ A MUDANÇA
                        "type": "conta", 
                        "parent": sub_id
                    })
            return lista

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

        # --- 1. MONTAGEM DA ÁRVORE VIRTUAL ---
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

        # Adiciona os tipos reais logo após os virtuais
        final_tree.extend(list(tipos_map.values()))

        return jsonify(final_tree), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

# --- ADICIONE EM Routes/DreConfig.py ---

@dre_config_bp.route('/Configuracao/GetContasDoSubgrupo', methods=['POST'])
@login_required
def GetContasDoSubgrupo():
    """
    Retorna as contas vinculadas a um ID de Subgrupo específico.
    VERSÃO CORRIGIDA: Cast explícito de int e tratamento de erro.
    """
    session = get_session()
    try:
        data = request.json
        raw_id = data.get('id')
        
        # Validação de segurança
        if not raw_id: 
            return jsonify([]), 200
            
        try:
            sg_id = int(raw_id) # Garante que é número
        except ValueError:
            return jsonify([]), 200 # Se não for número, retorna lista vazia

        # Busca usando ORM explícito (mais seguro que filter_by em alguns casos)
        vinculos = session.query(DreContaVinculo.Conta_Contabil).filter(
            DreContaVinculo.Id_Hierarquia == sg_id
        ).all()
        
        # Retorna lista simples de strings
        lista = [str(v.Conta_Contabil) for v in vinculos]
        
        return jsonify(lista), 200

    except Exception as e:
        print(f"Erro em GetContasDoSubgrupo: {e}") # Mostra o erro real no terminal do Python
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
        
@dre_config_bp.route('/Configuracao/AddSubgrupo', methods=['POST'])
@login_required
def AddSubgrupo():
    """
    Adiciona subgrupo com trava de duplicidade dentro do mesmo pai.
    """
    session = get_session()
    try:
        data = request.json
        nome = data.get('nome')
        parent_node_id = str(data.get('parent_id')) 

        if not nome:
            return jsonify({"error": "Nome do grupo é obrigatório"}), 400

        # Lógica de Identificação do Pai (Mantida do original)
        novo_sub = DreHierarquia(Nome=nome)
        contexto_pai_ordem = ""
        
        filtro_duplicidade = {}

        if parent_node_id.startswith("cc_"):
            codigo_cc_int = int(parent_node_id.replace("cc_", ""))
            
            # TRAVA: Configura filtro
            filtro_duplicidade = {
                "Raiz_Centro_Custo_Codigo": codigo_cc_int,
                "Id_Pai": None # Raiz do CC
            }

            # ... (Lógica de busca de info do CC mantida) ...
            sql_info = text('SELECT "Tipo", "Nome" FROM "Dre_Schema"."Classificacao_Centro_Custo" WHERE "Codigo" = :cod LIMIT 1')
            result_info = session.execute(sql_info, {"cod": codigo_cc_int}).first()
            novo_sub.Raiz_Centro_Custo_Tipo = result_info[0] if result_info else "Indefinido"
            novo_sub.Raiz_Centro_Custo_Nome = result_info[1] if result_info else "Indefinido"
            novo_sub.Raiz_Centro_Custo_Codigo = codigo_cc_int
            contexto_pai_ordem = f"cc_{codigo_cc_int}"

        elif parent_node_id.startswith("virt_"):
            virt_id = int(parent_node_id.replace("virt_", ""))
            
            # TRAVA: Configura filtro
            filtro_duplicidade = {
                "Raiz_No_Virtual_Id": virt_id,
                "Id_Pai": None
            }

            no_virt = session.query(DreNoVirtual).get(virt_id)
            novo_sub.Raiz_No_Virtual_Id = virt_id
            novo_sub.Raiz_No_Virtual_Nome = no_virt.Nome
            contexto_pai_ordem = f"virt_{virt_id}"

        elif parent_node_id.startswith("sg_"):
            parent_id = int(parent_node_id.replace("sg_", ""))
            
            # TRAVA: Configura filtro
            filtro_duplicidade = { "Id_Pai": parent_id }

            novo_sub.Id_Pai = parent_id
            pai = session.query(DreHierarquia).get(parent_id)
            if pai:
                novo_sub.Raiz_Centro_Custo_Codigo = pai.Raiz_Centro_Custo_Codigo
                novo_sub.Raiz_Centro_Custo_Tipo = pai.Raiz_Centro_Custo_Tipo
                novo_sub.Raiz_No_Virtual_Id = pai.Raiz_No_Virtual_Id
            contexto_pai_ordem = f"sg_{parent_id}"

        # EXECUTA A TRAVA DE DUPLICIDADE
        # Verifica se já existe um irmão com o mesmo nome
        duplicado = session.query(DreHierarquia).filter_by(**filtro_duplicidade).filter(
            func.lower(DreHierarquia.Nome) == nome.strip().lower()
        ).first()

        if duplicado:
            return jsonify({"error": f"Já existe um grupo '{nome}' neste local."}), 400

        # Salva na Estrutura
        session.add(novo_sub)
        session.flush()

        # ... (Lógica de Ordenamento mantida) ...
        nova_ordem = calcular_proxima_ordem(session, contexto_pai_ordem)
        nivel = 2 if "cc_" in parent_node_id or "virt_" in parent_node_id else 3
        reg_ordem = DreOrdenamento(
            tipo_no='subgrupo', id_referencia=str(novo_sub.Id),
            contexto_pai=contexto_pai_ordem, ordem=nova_ordem, nivel_profundidade=nivel
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
    """
    Cria um subgrupo automaticamente para TODOS os Centros de Custo de um determinado TIPO.
    Ex: Cria "Pessoal" dentro de todos os CCs do tipo "Administrativo".
    """
    session = get_session()
    try:
        data = request.json
        nome_grupo = data.get('nome')
        tipo_cc = data.get('tipo_cc') # Ex: "Adm", "Operacional"

        if not nome_grupo or not tipo_cc:
            return jsonify({"error": "Nome do grupo e Tipo são obrigatórios"}), 400

        # 1. Busca todos os Centros de Custo desse Tipo
        sql_ccs = text("""
            SELECT "Codigo", "Nome", "Tipo"
            FROM "Dre_Schema"."Classificacao_Centro_Custo"
            WHERE "Tipo" = :tipo AND "Codigo" IS NOT NULL
        """)
        
        ccs = session.execute(sql_ccs, {"tipo": tipo_cc}).fetchall()

        if not ccs:
            return jsonify({"error": f"Nenhum Centro de Custo encontrado para o tipo '{tipo_cc}'"}), 404

        count_created = 0

        # 2. Cria o subgrupo para cada CC encontrado
        for cc in ccs:
            codigo = cc[0]
            nome_cc = cc[1]
            tipo = cc[2]

            # Opcional: Verifica se já existe um grupo com esse nome neste CC para não duplicar
            existe = session.query(DreHierarquia).filter_by(
                Raiz_Centro_Custo_Codigo=codigo,
                Nome=nome_grupo,
                Id_Pai=None # Apenas no nível raiz do CC
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

# --- ADICIONE AO FINAL DE Routes/DreConfig.py ---

@dre_config_bp.route('/Configuracao/DeleteSubgrupoEmMassa', methods=['POST'])
@login_required
def DeleteSubgrupoEmMassa():
    """
    Deleta um subgrupo pelo NOME em todos os CCs de um determinado TIPO.
    Agora faz DELETE EM CASCATA (Limpa as contas antes de apagar o grupo).
    """
    session = get_session()
    try:
        data = request.json
        tipo_cc = data.get('tipo_cc')       # Ex: "Adm"
        nome_grupo = data.get('nome_grupo') # Ex: "Utilidades"

        if not tipo_cc or not nome_grupo:
            return jsonify({"error": "Parâmetros inválidos"}), 400

        # 1. Busca todos os grupos alvo (Pai = None garante que são grupos de 1º nível dentro do CC)
        grupos_alvo = session.query(DreHierarquia).filter(
            DreHierarquia.Raiz_Centro_Custo_Tipo == tipo_cc,
            DreHierarquia.Nome == nome_grupo,
            DreHierarquia.Id_Pai == None
        ).all()

        if not grupos_alvo:
            return jsonify({"error": "Nenhum grupo encontrado com esse nome."}), 404

        ids_para_deletar = [g.Id for g in grupos_alvo]

        # --- LÓGICA DE CASCATA ---
        
        # A. Função auxiliar para pegar todos os IDs de filhos recursivamente
        def get_all_child_ids(parent_ids):
            all_ids = set(parent_ids)
            current_level = parent_ids
            
            while current_level:
                # Busca filhos do nível atual
                filhos = session.query(DreHierarquia.Id).filter(
                    DreHierarquia.Id_Pai.in_(current_level)
                ).all()
                
                if not filhos:
                    break
                    
                child_ids = [f.Id for f in filhos]
                all_ids.update(child_ids)
                current_level = child_ids
            
            return list(all_ids)

        # Pega a lista completa de IDs (Pais + Filhos + Netos...)
        todos_ids_envolvidos = get_all_child_ids(ids_para_deletar)

        if todos_ids_envolvidos:
            # B. Deleta Contas Vinculadas em Lote
            session.query(DreContaVinculo).filter(
                DreContaVinculo.Id_Hierarquia.in_(todos_ids_envolvidos)
            ).delete(synchronize_session=False)

            # C. Deleta Contas Personalizadas em Lote
            session.query(DreContaPersonalizada).filter(
                DreContaPersonalizada.Id_Hierarquia.in_(todos_ids_envolvidos)
            ).delete(synchronize_session=False)

            # D. Deleta os Grupos Hierárquicos em Lote
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


@dre_config_bp.route('/Configuracao/DesvincularContaEmMassa', methods=['POST'])
@login_required
def DesvincularContaEmMassa():
    """
    Remove vínculo em massa, suportando agora remoção da tabela personalizada.
    """
    session = get_session()
    try:
        data = request.json
        tipo_cc = data.get('tipo_cc') # Ex: "Adm"
        conta = str(data.get('conta')).strip()
        is_personalizada = data.get('is_personalizada', False) # Novo Flag

        if not tipo_cc or not conta:
            return jsonify({"error": "Dados inválidos"}), 400

        count = 0

        if is_personalizada:
            # --- REMOVE DA TABELA PERSONALIZADA ---
            # Busca todos os grupos desse tipo para varrer e limpar
            subgrupos_ids = session.query(DreHierarquia.Id).filter(
                DreHierarquia.Raiz_Centro_Custo_Tipo == tipo_cc
            ).all()
            ids = [s.Id for s in subgrupos_ids]
            
            if ids:
                res = session.query(DreContaPersonalizada).filter(
                    DreContaPersonalizada.Conta_Contabil == conta,
                    DreContaPersonalizada.Id_Hierarquia.in_(ids)
                ).delete(synchronize_session=False)
                count = res
        else:
            # --- REMOVE DA TABELA PADRÃO (Lógica Antiga) ---
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

# --- ADICIONE NO ARQUIVO Routes/DreConfig.py ---
@dre_config_bp.route('/Configuracao/GetSubgruposPorTipo', methods=['POST'])
@login_required
def GetSubgruposPorTipo():
    """
    Retorna lista distinta de nomes de subgrupos que existem dentro de um TIPO de CC.
    CORRIGIDO: Usa ORM para evitar erros de nome de tabela SQL.
    """
    session = get_session()
    try:
        data = request.json
        tipo_cc = data.get('tipo_cc') # Ex: "Adm"
        
        # Usa o ORM em vez de SQL Bruto para maior segurança
        # Busca apenas os NOMES distintos
        # Filtra pelo Tipo e garante que é um grupo raiz dentro do CC (Id_Pai None)
        subgrupos = session.query(DreHierarquia.Nome).filter(
            DreHierarquia.Raiz_Centro_Custo_Tipo == tipo_cc,
            DreHierarquia.Id_Pai == None 
        ).distinct().order_by(DreHierarquia.Nome).all()
        
        # O resultado vem como uma lista de tuplas [('Pessoal',), ('Geral',)], 
        # precisamos transformar em lista simples ['Pessoal', 'Geral']
        lista_nomes = [row.Nome for row in subgrupos]
        
        return jsonify(lista_nomes), 200

    except Exception as e:
        print(f"Erro no GetSubgruposPorTipo: {e}") # Ajuda no debug do console do Flask
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

# --- ADICIONE AO FINAL DE Routes/DreConfig.py ---

@dre_config_bp.route('/Configuracao/GetContasDoGrupoMassa', methods=['POST'])
@login_required
def GetContasDoGrupoMassa():
    """
    Retorna lista unificada de contas (Padrão + Personalizadas) vinculadas ao grupo.
    """
    session = get_session()
    try:
        data = request.json
        tipo_cc = data.get('tipo_cc')       # Ex: "Adm"
        nome_grupo = data.get('nome_grupo') # Ex: "Pessoal"

        if not tipo_cc or not nome_grupo:
             return jsonify([]), 200

        # 1. Identifica os IDs dos Subgrupos com esse nome e tipo
        ids_subgrupos = session.query(DreHierarquia.Id).filter(
            DreHierarquia.Raiz_Centro_Custo_Tipo == tipo_cc,
            DreHierarquia.Nome == nome_grupo
        ).all()
        
        ids = [i.Id for i in ids_subgrupos]
        
        if not ids:
            return jsonify([]), 200

        lista_final = []

        # 2. Busca Contas PADRÃO (Distinct)
        padrao = session.query(DreContaVinculo.Conta_Contabil).filter(
            DreContaVinculo.Id_Hierarquia.in_(ids)
        ).distinct().all()
        
        for p in padrao:
            lista_final.append({
                "conta": p.Conta_Contabil,
                "tipo": "padrao",
                "nome_personalizado": None
            })

        # 3. Busca Contas PERSONALIZADAS (Distinct)
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
        
        # Ordena pela conta para ficar bonito
        lista_final.sort(key=lambda x: x['conta'])
        
        return jsonify(lista_final), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
        
# Em Routes/DreConfig.py

@dre_config_bp.route('/Configuracao/VincularContaEmMassa', methods=['POST'])
@login_required
def VincularContaEmMassa():
    session = get_session()
    try:
        data = request.json
        tipo_cc = data.get('tipo_cc')       
        nome_subgrupo = data.get('nome_subgrupo') 
        conta = str(data.get('conta')).strip()    
        
        # Parâmetros da Personalização
        is_personalizada = data.get('is_personalizada', False)
        nome_personalizado_conta = data.get('nome_personalizado_conta') # O nome que você digitou no input

        if not all([tipo_cc, nome_subgrupo, conta]):
            return jsonify({"error": "Dados incompletos."}), 400

        # Busca os grupos destino
        subgrupos_alvo = session.query(DreHierarquia).filter(
            DreHierarquia.Raiz_Centro_Custo_Tipo == tipo_cc,
            DreHierarquia.Nome == nome_subgrupo
        ).all()

        if not subgrupos_alvo:
            return jsonify({"error": "Nenhum subgrupo encontrado."}), 404

        count_sucesso = 0

        for sg in subgrupos_alvo:
            
            # === CASO 1: VINCULAÇÃO PERSONALIZADA (RESOLVE SEU PROBLEMA) ===
            if is_personalizada:
                # Se você não digitou nome, tentamos pegar da tabela de origem, 
                # mas se digitou, USAMOS O QUE VOCÊ DIGITOU (ex: "FRETES DISTRIBUIÇÃO")
                nome_final = nome_personalizado_conta 
                
                if not nome_final:
                    # Fallback: Tenta achar um nome no banco se vier vazio
                    sql_nome = text('SELECT "Título Conta" FROM "Dre_Schema"."Razao_Dados_Consolidado" WHERE "Conta"=:c LIMIT 1')
                    res = session.execute(sql_nome, {'c': conta}).first()
                    nome_final = res[0] if res else "Sem Nome"

                # Verifica se já existe vínculo personalizado NESTE grupo
                conta_pers = session.query(DreContaPersonalizada).filter_by(
                    Id_Hierarquia=sg.Id,
                    Conta_Contabil=conta
                ).first()

                if conta_pers:
                    # ATUALIZA o nome se já existe (corrige nomes errados antigos)
                    conta_pers.Nome_Personalizado = nome_final
                else:
                    # CRIA novo se não existe
                    novo_p = DreContaPersonalizada(
                        Conta_Contabil=conta,
                        Nome_Personalizado=nome_final,
                        Id_Hierarquia=sg.Id,
                        Id_No_Virtual=None
                    )
                    session.add(novo_p)
                
                count_sucesso += 1

            # === CASO 2: VINCULAÇÃO PADRÃO (Mantido igual) ===
            else:
                cc_code = sg.Raiz_Centro_Custo_Codigo
                if cc_code is None: continue

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
        # Log mais detalhado do erro de integridade se ocorrer
        if "UniqueViolation" in str(e):
            return jsonify({"error": "Erro de duplicidade: Execute a rota de correção de banco primeiro."}), 500
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
        
@dre_config_bp.route('/Configuracao/AddNoVirtual', methods=['POST'])
@login_required
def AddNoVirtual():
    """
    Adiciona um novo Nó Virtual com trava de duplicidade de nome.
    """
    session = get_session()
    try:
        data = request.json
        nome = data.get('nome')
        
        if not nome: 
            return jsonify({"error": "Nome obrigatório"}), 400
        
        # TRAVA: Verifica se já existe Nó Virtual com este nome
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


@dre_config_bp.route('/Configuracao/VincularConta', methods=['POST'])
@login_required
def VincularConta():
    session = get_session()
    try:
        data = request.json
        conta = str(data.get('conta')).strip()
        subgrupo_node_id = data.get('subgrupo_id') 

        if not subgrupo_node_id.startswith("sg_"):
            raise Exception("Contas só podem ser vinculadas a Subgrupos.")

        sg_id = int(subgrupo_node_id.replace("sg_", ""))

        # Busca info do grupo
        subgrupo = session.query(DreHierarquia).get(sg_id)
        if not subgrupo: raise Exception("Subgrupo não encontrado.")
            
        # 2. Lógica de Rastreamento da Raiz (Recursiva)
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

        # Salva ou Atualiza Vínculo
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
            # Se já existe, removemos a ordem antiga para criar a nova no novo lugar
            session.query(DreOrdenamento).filter_by(
                tipo_no='conta', id_referencia=conta
            ).delete()

            vinculo.Id_Hierarquia = sg_id
            vinculo.Chave_Conta_Tipo_CC = chave_tipo
            vinculo.Chave_Conta_Codigo_CC = chave_cod

        # --- NOVO: Salva no Ordenamento ---
        contexto_pai = f"sg_{sg_id}"
        nova_ordem = calcular_proxima_ordem(session, contexto_pai)

        reg_ordem = DreOrdenamento(
            tipo_no='conta',
            id_referencia=conta,
            contexto_pai=contexto_pai,
            ordem=nova_ordem,
            nivel_profundidade=99 # Folha
        )
        session.add(reg_ordem)
        # ----------------------------------

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
    Deleta um subgrupo da hierarquia e TUDO que estiver dentro dele (Cascata).
    Remove recursivamente: Filhos, Contas Vinculadas e Contas Personalizadas.
    """
    session = get_session()
    try:
        data = request.json
        node_id = data.get('id') 
        
        if not node_id or not node_id.startswith('sg_'):
            return jsonify({"error": "Nó inválido para exclusão"}), 400
            
        db_id = int(node_id.replace('sg_', ''))
        
        # Função Recursiva para limpar a árvore de baixo para cima
        def delete_recursivo(id_pai):
            # 1. Busca todos os filhos deste grupo
            filhos = session.query(DreHierarquia).filter_by(Id_Pai=id_pai).all()
            for filho in filhos:
                delete_recursivo(filho.Id) # Recursão
            
            # 2. Deleta Contas Vinculadas a este grupo
            session.query(DreContaVinculo).filter_by(Id_Hierarquia=id_pai).delete()
            
            # 3. Deleta Contas Personalizadas vinculadas a este grupo
            session.query(DreContaPersonalizada).filter_by(Id_Hierarquia=id_pai).delete()
            
            # 4. Finalmente, deleta o grupo atual
            session.query(DreHierarquia).filter_by(Id=id_pai).delete()

        # Executa a limpeza
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
    Deleta um Nó Virtual e tudo que está pendurado nele (Cascata Completa).
    """
    session = get_session()
    try:
        data = request.json
        node_id = data.get('id')
        
        if not node_id or not node_id.startswith('virt_'):
            return jsonify({"error": "Nó inválido"}), 400
            
        virt_id = int(node_id.replace('virt_', ''))

        # 1. Busca todos os subgrupos que pertencem a este Nó Virtual
        subgrupos = session.query(DreHierarquia).filter_by(Raiz_No_Virtual_Id=virt_id).all()
        ids_hierarquia = [s.Id for s in subgrupos]

        if ids_hierarquia:
            # Limpa vínculos desses subgrupos
            session.query(DreContaVinculo).filter(
                DreContaVinculo.Id_Hierarquia.in_(ids_hierarquia)
            ).delete(synchronize_session=False)
            
            session.query(DreContaPersonalizada).filter(
                DreContaPersonalizada.Id_Hierarquia.in_(ids_hierarquia)
            ).delete(synchronize_session=False)
            
            # Deleta os subgrupos
            session.query(DreHierarquia).filter(
                DreHierarquia.Id.in_(ids_hierarquia)
            ).delete(synchronize_session=False)

        # 2. Deleta contas personalizadas penduradas diretamente no Nó Virtual
        session.query(DreContaPersonalizada).filter_by(Id_No_Virtual=virt_id).delete()

        # 3. Finalmente, deleta o Nó Virtual
        session.query(DreNoVirtual).filter_by(Id=virt_id).delete()
        
        session.commit()
        return jsonify({"success": True, "msg": "Estrutura virtual excluída."}), 200

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