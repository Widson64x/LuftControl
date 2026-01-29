import time
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from Db.Connections import GetPostgresEngine

# Importação dos Modelos
from Models.POSTGRESS.DreOrdenamento import (
    DreOrdenamento, 
    calcular_proxima_ordem,
    reordenar_contexto,
    mover_elemento
)

class OrdenamentoDreService:
    """
    Serviço responsável pela gestão da ordem hierárquica da DRE.
    Contém lógicas otimizadas (Bulk Insert, Consultas em Lote) para alta performance.
    """

    def __init__(self):
        pass

    def _ObterSessao(self):
        """Cria e retorna uma sessão do PostgreSQL."""
        engine = GetPostgresEngine()
        return sessionmaker(bind=engine)()

    def InicializarOrdenamento(self, limpar=False):
        """
        Inicializa a tabela de ordenamento carregando dados de todas as entidades.
        Usa Bulk Insert para reduzir o tempo de execução.
        """
        session = self._ObterSessao()
        try:
            start = time.time()
            
            if limpar:
                session.execute(text('DELETE FROM "Dre_Schema"."DRE_Ordenamento"'))
                session.commit()
            
            intervalo = 10
            
            # Carrega existentes em um SET para lookup O(1)
            sql_existentes = text('SELECT tipo_no, id_referencia, contexto_pai FROM "Dre_Schema"."DRE_Ordenamento"')
            existentes = set()
            for row in session.execute(sql_existentes).fetchall():
                existentes.add((row[0], row[1], row[2]))
            
            novos = []
            
            # === NÍVEL 0: RAIZ ===
            ordem_raiz = intervalo
            
            # 1. Virtuais com ordem < 100
            sql_v = text('SELECT "Id", "Ordem" FROM "Dre_Schema"."DRE_Estrutura_No_Virtual" WHERE "Ordem" IS NOT NULL AND "Ordem" < 100 ORDER BY "Ordem"')
            for row in session.execute(sql_v).fetchall():
                if ('virtual', str(row[0]), 'root') not in existentes:
                    novos.append(DreOrdenamento(tipo_no='virtual', id_referencia=str(row[0]), contexto_pai='root', ordem=ordem_raiz, nivel_profundidade=0))
                ordem_raiz += intervalo
            
            # 2. Subgrupos raiz global
            sql_sg = text('SELECT "Id" FROM "Dre_Schema"."DRE_Estrutura_Hierarquia" WHERE "Id_Pai" IS NULL AND "Raiz_Centro_Custo_Codigo" IS NULL AND "Raiz_No_Virtual_Id" IS NULL ORDER BY "Nome"')
            for row in session.execute(sql_sg).fetchall():
                if ('subgrupo', str(row[0]), 'root') not in existentes:
                    novos.append(DreOrdenamento(tipo_no='subgrupo', id_referencia=str(row[0]), contexto_pai='root', ordem=ordem_raiz, nivel_profundidade=0))
                ordem_raiz += intervalo
            
            # 3. Tipos de CC
            sql_t = text('SELECT DISTINCT "Tipo" FROM "Dre_Schema"."Classificacao_Centro_Custo" WHERE "Tipo" IS NOT NULL ORDER BY "Tipo"')
            for row in session.execute(sql_t).fetchall():
                if ('tipo_cc', row[0], 'root') not in existentes:
                    novos.append(DreOrdenamento(tipo_no='tipo_cc', id_referencia=row[0], contexto_pai='root', ordem=ordem_raiz, nivel_profundidade=0))
                ordem_raiz += intervalo
            
            # 4. Virtuais com ordem >= 100 ou NULL
            sql_v2 = text('SELECT "Id" FROM "Dre_Schema"."DRE_Estrutura_No_Virtual" WHERE "Ordem" IS NULL OR "Ordem" >= 100 ORDER BY COALESCE("Ordem", 999), "Nome"')
            for row in session.execute(sql_v2).fetchall():
                if ('virtual', str(row[0]), 'root') not in existentes:
                    novos.append(DreOrdenamento(tipo_no='virtual', id_referencia=str(row[0]), contexto_pai='root', ordem=ordem_raiz, nivel_profundidade=0))
                ordem_raiz += intervalo
            
            # === NÍVEL 1: CCs dentro de Tipos ===
            sql_cc = text('SELECT "Codigo", "Tipo" FROM "Dre_Schema"."Classificacao_Centro_Custo" WHERE "Codigo" IS NOT NULL ORDER BY "Tipo", "Codigo"')
            ccs_by_tipo = {}
            for row in session.execute(sql_cc).fetchall():
                tipo = row[1]
                if tipo not in ccs_by_tipo: ccs_by_tipo[tipo] = []
                ccs_by_tipo[tipo].append(row[0])
            
            for tipo, codigos in ccs_by_tipo.items():
                ordem_cc = intervalo
                ctx = f"tipo_{tipo}"
                for cod in codigos:
                    if ('cc', str(cod), ctx) not in existentes:
                        novos.append(DreOrdenamento(tipo_no='cc', id_referencia=str(cod), contexto_pai=ctx, ordem=ordem_cc, nivel_profundidade=1))
                    ordem_cc += intervalo
            
            # === NÍVEL 2+: Subgrupos ===
            sql_subs = text("""
                SELECT "Id", "Id_Pai", "Raiz_Centro_Custo_Codigo", "Raiz_No_Virtual_Id"
                FROM "Dre_Schema"."DRE_Estrutura_Hierarquia"
                WHERE "Id_Pai" IS NOT NULL OR "Raiz_Centro_Custo_Codigo" IS NOT NULL OR "Raiz_No_Virtual_Id" IS NOT NULL
                ORDER BY "Id"
            """)
            subs_by_ctx = {}
            for row in session.execute(sql_subs).fetchall():
                sg_id, id_pai, cc_cod, virt_id = row
                if id_pai: ctx, nivel = f"sg_{id_pai}", 3
                elif cc_cod: ctx, nivel = f"cc_{cc_cod}", 2
                elif virt_id: ctx, nivel = f"virt_{virt_id}", 2
                else: continue
                
                if ctx not in subs_by_ctx: subs_by_ctx[ctx] = []
                subs_by_ctx[ctx].append((sg_id, nivel))
            
            for ctx, items in subs_by_ctx.items():
                ordem = intervalo
                for sg_id, nivel in items:
                    if ('subgrupo', str(sg_id), ctx) not in existentes:
                        novos.append(DreOrdenamento(tipo_no='subgrupo', id_referencia=str(sg_id), contexto_pai=ctx, ordem=ordem, nivel_profundidade=nivel))
                    ordem += intervalo
            
            # === CONTAS VINCULADAS ===
            sql_contas = text('SELECT "Conta_Contabil", "Id_Hierarquia" FROM "Dre_Schema"."DRE_Estrutura_Conta_Vinculo" ORDER BY "Id_Hierarquia", "Conta_Contabil"')
            contas_by_sg = {}
            for row in session.execute(sql_contas).fetchall():
                sg_id = row[1]
                if sg_id not in contas_by_sg: contas_by_sg[sg_id] = []
                contas_by_sg[sg_id].append(row[0])
            
            for sg_id, contas in contas_by_sg.items():
                ctx = f"sg_{sg_id}"
                ordem = intervalo
                for conta in contas:
                    if ('conta', str(conta), ctx) not in existentes:
                        novos.append(DreOrdenamento(tipo_no='conta', id_referencia=str(conta), contexto_pai=ctx, ordem=ordem, nivel_profundidade=99))
                    ordem += intervalo
            
            # === CONTAS PERSONALIZADAS ===
            sql_pers = text('SELECT "Id", "Id_Hierarquia", "Id_No_Virtual" FROM "Dre_Schema"."DRE_Estrutura_Conta_Personalizada" ORDER BY COALESCE("Id_Hierarquia", 0), COALESCE("Id_No_Virtual", 0), "Id"')
            pers_by_ctx = {}
            for row in session.execute(sql_pers).fetchall():
                cd_id, hier_id, virt_id = row
                if hier_id: ctx = f"sg_{hier_id}"
                elif virt_id: ctx = f"virt_{virt_id}"
                else: continue
                
                if ctx not in pers_by_ctx: pers_by_ctx[ctx] = []
                pers_by_ctx[ctx].append(cd_id)
            
            for ctx, items in pers_by_ctx.items():
                ordem = intervalo
                for cd_id in items:
                    if ('conta_detalhe', str(cd_id), ctx) not in existentes:
                        novos.append(DreOrdenamento(tipo_no='conta_detalhe', id_referencia=str(cd_id), contexto_pai=ctx, ordem=ordem, nivel_profundidade=99))
                    ordem += intervalo
            
            # === BULK INSERT ===
            if novos:
                session.bulk_save_objects(novos)
            
            session.commit()
            
            elapsed = time.time() - start
            print(f"⚡ InicializarOrdenamento: {len(novos)} registros criados em {elapsed*1000:.2f}ms")
            
            return {
                "success": True,
                "msg": f"Ordenamento inicializado! {len(novos)} registros criados em {elapsed*1000:.0f}ms."
            }

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def ObterOrdemEspecifica(self, tipo_no, id_referencia, contexto_pai='root'):
        """Retorna a ordem de um elemento específico."""
        session = self._ObterSessao()
        try:
            sql = text("""
                SELECT ordem, nivel_profundidade, caminho_completo
                FROM "Dre_Schema"."DRE_Ordenamento"
                WHERE tipo_no = :tipo AND id_referencia = :ref AND contexto_pai = :ctx
                LIMIT 1
            """)
            row = session.execute(sql, {"tipo": tipo_no, "ref": id_referencia, "ctx": contexto_pai}).first()
            
            if row:
                return {"ordem": row[0], "nivel": row[1], "caminho": row[2]}
            return {"ordem": None, "msg": "Não encontrado"}
        finally:
            session.close()

    def ListarFilhosOrdenados(self, contexto_pai):
        """Retorna lista de filhos ordenada com índice otimizado."""
        session = self._ObterSessao()
        try:
            start = time.time()
            sql = text("""
                SELECT "Id", tipo_no, id_referencia, ordem, nivel_profundidade
                FROM "Dre_Schema"."DRE_Ordenamento"
                WHERE contexto_pai = :ctx
                ORDER BY ordem
            """)
            result = session.execute(sql, {"ctx": contexto_pai}).fetchall()
            
            resultado = [{
                "id": r[0], "tipo_no": r[1], "id_referencia": r[2],
                "ordem": r[3], "nivel": r[4]
            } for r in result]
            
            elapsed = time.time() - start
            print(f"⚡ ListarFilhosOrdenados ({contexto_pai}): {len(resultado)} itens em {elapsed*1000:.2f}ms")
            return resultado
        finally:
            session.close()

    def ObterArvoreOrdenada(self):
        """
        SUPER OTIMIZADO: Carrega todos os dados em 6 queries e monta a árvore em Python.
        """
        session = self._ObterSessao()
        try:
            start = time.time()
            
            # Verifica se há dados
            count = session.execute(text('SELECT 1 FROM "Dre_Schema"."DRE_Ordenamento" LIMIT 1')).first()
            if not count:
                return None # Indica que precisa inicializar
            
            # === CARREGA TODOS OS DADOS EM BULK ===
            
            # 1. Ordenamento completo
            sql_ordem = text('SELECT tipo_no, id_referencia, contexto_pai, ordem, nivel_profundidade FROM "Dre_Schema"."DRE_Ordenamento" ORDER BY contexto_pai, ordem')
            ordenamento = session.execute(sql_ordem).fetchall()
            
            # 2. Nós virtuais
            sql_virt = text('SELECT "Id", "Nome", "Is_Calculado" FROM "Dre_Schema"."DRE_Estrutura_No_Virtual"')
            virtuais = {row[0]: {"nome": row[1], "is_calc": row[2]} for row in session.execute(sql_virt).fetchall()}
            
            # 3. CCs
            sql_cc = text('SELECT "Codigo", "Nome", "Tipo" FROM "Dre_Schema"."Classificacao_Centro_Custo" WHERE "Codigo" IS NOT NULL')
            ccs = {row[0]: {"nome": row[1], "tipo": row[2]} for row in session.execute(sql_cc).fetchall()}
            
            # 4. Subgrupos
            sql_sg = text('SELECT "Id", "Nome" FROM "Dre_Schema"."DRE_Estrutura_Hierarquia"')
            subgrupos = {row[0]: row[1] for row in session.execute(sql_sg).fetchall()}
            
            # 5. Contas (nomes)
            sql_contas = text('SELECT DISTINCT ON ("Conta") "Conta", "Título Conta" FROM "Dre_Schema"."Razao_Dados_Consolidado" WHERE "Conta" IS NOT NULL')
            contas = {str(row[0]): row[1] for row in session.execute(sql_contas).fetchall()}
            
            # 6. Contas personalizadas
            sql_pers = text('SELECT "Id", "Conta_Contabil", "Nome_Personalizado" FROM "Dre_Schema"."DRE_Estrutura_Conta_Personalizada"')
            personalizadas = {row[0]: {"conta": row[1], "nome": row[2]} for row in session.execute(sql_pers).fetchall()}
            
            # === AGRUPA ORDENAMENTO POR CONTEXTO ===
            ordem_por_contexto = {}
            for row in ordenamento:
                tipo, id_ref, ctx, ordem, nivel = row
                if ctx not in ordem_por_contexto:
                    ordem_por_contexto[ctx] = []
                ordem_por_contexto[ctx].append({"tipo": tipo, "id": id_ref, "ordem": ordem, "nivel": nivel})
            
            # === FUNÇÃO DE CONSTRUÇÃO RECURSIVA ===
            def construir_no(item):
                tipo = item["tipo"]
                id_ref = item["id"]
                ordem = item["ordem"]
                
                node = {"ordem": ordem, "children": []}
                ctx_filhos = None
                
                if tipo == 'tipo_cc':
                    node["id"] = f"tipo_{id_ref}"
                    node["text"] = id_ref
                    node["type"] = "root_tipo"
                    ctx_filhos = f"tipo_{id_ref}"
                    
                elif tipo == 'virtual':
                    try: virt_id = int(id_ref)
                    except: return None
                    virt = virtuais.get(virt_id)
                    if not virt: return None
                    node["id"] = f"virt_{virt_id}"
                    node["text"] = virt["nome"]
                    node["type"] = "root_virtual"
                    node["is_calculado"] = virt["is_calc"]
                    ctx_filhos = f"virt_{virt_id}"
                    
                elif tipo == 'cc':
                    try: cc_cod = int(id_ref)
                    except: return None
                    cc = ccs.get(cc_cod)
                    if not cc: return None
                    node["id"] = f"cc_{cc_cod}"
                    node["text"] = f"{cc_cod} - {cc['nome']}"
                    node["type"] = "root_cc"
                    ctx_filhos = f"cc_{cc_cod}"
                    
                elif tipo == 'subgrupo':
                    try: sg_id = int(id_ref)
                    except: return None
                    nome = subgrupos.get(sg_id)
                    if not nome: return None
                    node["id"] = f"sg_{sg_id}"
                    node["db_id"] = sg_id
                    node["text"] = nome
                    node["type"] = "subgrupo"
                    ctx_filhos = f"sg_{sg_id}"
                    
                elif tipo == 'conta':
                    conta_ref = str(id_ref)
                    nome = contas.get(conta_ref, "Sem Título")
                    node["id"] = f"conta_{conta_ref}"
                    node["text"] = f"Conta: {conta_ref} - {nome}"
                    node["type"] = "conta"
                    return node
                    
                elif tipo == 'conta_detalhe':
                    try: cd_id = int(id_ref)
                    except: return None
                    pers = personalizadas.get(cd_id)
                    if not pers: return None
                    node["id"] = f"cd_{cd_id}"
                    node["text"] = f"{pers['conta']} ({pers['nome'] or 'Orig'})"
                    node["type"] = "conta_detalhe"
                    return node
                else:
                    return None
                
                # Recursividade
                if ctx_filhos:
                    filhos_ordem = ordem_por_contexto.get(ctx_filhos, [])
                    for filho in filhos_ordem:
                        filho_node = construir_no(filho)
                        if filho_node:
                            node["children"].append(filho_node)
                
                return node
            
            # === MONTA ÁRVORE A PARTIR DA RAIZ ===
            arvore = []
            for item in ordem_por_contexto.get('root', []):
                node = construir_no(item)
                if node:
                    arvore.append(node)
            
            elapsed = time.time() - start
            print(f"⚡ ObterArvoreOrdenada: {len(arvore)} nós raiz em {elapsed*1000:.2f}ms")
            return arvore

        finally:
            session.close()

    def MoverNo(self, tipo_no, id_ref, ctx_origem, ctx_destino, nova_ordem, pos_relativa=None, id_relativo=None):
        """Move um nó para nova posição."""
        session = self._ObterSessao()
        try:
            if not ctx_destino: ctx_destino = ctx_origem

            if pos_relativa and id_relativo:
                sql = text('SELECT ordem FROM "Dre_Schema"."DRE_Ordenamento" WHERE id_referencia = :ref AND contexto_pai = :ctx LIMIT 1')
                ref = session.execute(sql, {"ref": id_relativo, "ctx": ctx_destino}).first()
                
                if ref:
                    if pos_relativa == 'antes': nova_ordem = ref[0] - 5
                    elif pos_relativa == 'depois': nova_ordem = ref[0] + 5
                    elif pos_relativa == 'dentro':
                        ctx_destino = f"sg_{id_relativo}"
                        nova_ordem = calcular_proxima_ordem(session, ctx_destino)
            
            mover_elemento(session, tipo_no, id_ref, ctx_origem, ctx_destino, nova_ordem)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def ReordenarLote(self, contexto, lista_nova_ordem):
        """Atualiza múltiplos registros em uma única query (Upsert)."""
        session = self._ObterSessao()
        try:
            start = time.time()
            if not lista_nova_ordem: return 0

            for item in lista_nova_ordem:
                sql = text("""
                    INSERT INTO "Dre_Schema"."DRE_Ordenamento" 
                        (tipo_no, id_referencia, contexto_pai, ordem)
                    VALUES (:tipo, :ref, :ctx, :ordem)
                    ON CONFLICT (tipo_no, id_referencia, contexto_pai) 
                    DO UPDATE SET ordem = EXCLUDED.ordem
                """)
                session.execute(sql, {
                    "tipo": item['tipo_no'],
                    "ref": item['id_referencia'],
                    "ctx": contexto,
                    "ordem": item['ordem']
                })
            
            session.commit()
            elapsed = time.time() - start
            print(f"⚡ ReordenarLote: {len(lista_nova_ordem)} itens em {elapsed*1000:.2f}ms")
            return len(lista_nova_ordem)
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def NormalizarContexto(self, contexto):
        """Normaliza a ordem de um contexto (10, 20, 30...)."""
        session = self._ObterSessao()
        try:
            reordenar_contexto(session, contexto, intervalo=10)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def SincronizarNovoElemento(self, tipo_no, id_ref, contexto, posicao):
        """Adiciona um novo elemento ao ordenamento."""
        session = self._ObterSessao()
        try:
            id_ref = str(id_ref)
            sql_check = text('SELECT ordem FROM "Dre_Schema"."DRE_Ordenamento" WHERE tipo_no = :tipo AND id_referencia = :ref AND contexto_pai = :ctx')
            existe = session.execute(sql_check, {"tipo": tipo_no, "ref": id_ref, "ctx": contexto}).first()
            
            if existe:
                return {"success": True, "msg": "Já existe", "ordem": existe[0]}
            
            if posicao == 'inicio':
                sql_min = text('SELECT MIN(ordem) FROM "Dre_Schema"."DRE_Ordenamento" WHERE contexto_pai = :ctx')
                min_ordem = session.execute(sql_min, {"ctx": contexto}).scalar() or 10
                nova_ordem = max(1, min_ordem - 10)
            elif posicao == 'fim':
                nova_ordem = calcular_proxima_ordem(session, contexto)
            else:
                try: nova_ordem = int(posicao)
                except: nova_ordem = calcular_proxima_ordem(session, contexto)
            
            if contexto == 'root': nivel = 0
            elif contexto.startswith('tipo_'): nivel = 1
            elif contexto.startswith('cc_') or contexto.startswith('virt_'): nivel = 2
            else: nivel = 3
            
            sql_insert = text("""
                INSERT INTO "Dre_Schema"."DRE_Ordenamento"
                    (tipo_no, id_referencia, contexto_pai, ordem, nivel_profundidade)
                VALUES (:tipo, :ref, :ctx, :ordem, :nivel)
            """)
            session.execute(sql_insert, {"tipo": tipo_no, "ref": id_ref, "ctx": contexto, "ordem": nova_ordem, "nivel": nivel})
            session.commit()
            
            return {"success": True, "msg": "Elemento adicionado", "ordem": nova_ordem}
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def RemoverElemento(self, tipo_no, id_ref, contexto):
        """Remove um elemento do ordenamento."""
        session = self._ObterSessao()
        try:
            id_ref = str(id_ref)
            sql = text("""
                DELETE FROM "Dre_Schema"."DRE_Ordenamento"
                WHERE tipo_no = :tipo AND id_referencia = :ref
            """ + (" AND contexto_pai = :ctx" if contexto else ""))
            
            params = {"tipo": tipo_no, "ref": id_ref}
            if contexto: params["ctx"] = contexto
            
            result = session.execute(sql, params)
            session.commit()
            return result.rowcount
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def ReordenarEmMassa(self, tipo_cc, ordem_nomes):
        """Reordena subgrupos em massa usando batch query."""
        session = self._ObterSessao()
        try:
            start = time.time()
            sql_busca = text('SELECT "Id", "Nome" FROM "Dre_Schema"."DRE_Estrutura_Hierarquia" WHERE "Raiz_Centro_Custo_Tipo" = :tipo AND "Nome" = ANY(:nomes)')
            rows = session.execute(sql_busca, {'tipo': tipo_cc, 'nomes': list(ordem_nomes)}).fetchall()
            
            mapa_ids = {}
            for r in rows:
                if r[1] not in mapa_ids: mapa_ids[r[1]] = []
                mapa_ids[r[1]].append(str(r[0]))

            updates = 0
            for index, nome_grupo in enumerate(ordem_nomes):
                nova_ordem = (index + 1) * 10
                ids = mapa_ids.get(nome_grupo, [])
                
                if ids:
                    sql_update = text("UPDATE \"Dre_Schema\".\"DRE_Ordenamento\" SET ordem = :ordem WHERE tipo_no = 'subgrupo' AND id_referencia = ANY(:ids)")
                    result = session.execute(sql_update, {"ordem": nova_ordem, "ids": ids})
                    updates += result.rowcount

            session.commit()
            elapsed = time.time() - start
            print(f"⚡ ReordenarEmMassa: {updates} atualizações em {elapsed*1000:.2f}ms")
            return updates
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()