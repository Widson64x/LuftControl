"""
Serviço para Configuração da Árvore DRE (Demonstração do Resultado do Exercício)
Gerencia toda a lógica de negócios, consultas e operações de banco de dados.
"""

import json
import time
from sqlalchemy import text, func
from sqlalchemy.orm import sessionmaker

from Db.Connections import GetPostgresEngine
from Models.Postgress.CTL_Dre_Estrutura import (
    CtlDreContaVinculo, 
    CtlDreNoVirtual, 
    CtlDreHierarquia, 
    CtlDreContaPersonalizada
)
from Models.Postgress.CTL_Dre_Ordenamento import CtlDreOrdenamento, calcular_proxima_ordem


class ConfiguracaoDreService:
    """
    Classe de serviço responsável por encapsular as regras de negócio relativas 
    à configuração e estruturação da DRE.
    """

    def obterSessao(self):
        """
        Cria e retorna uma sessão do banco de dados PostgreSQL.

        Retornos:
            Session: Objeto de sessão do SQLAlchemy instanciado.
        """
        engine = GetPostgresEngine()
        Sessao = sessionmaker(bind=engine)
        return Sessao()

    def limparOrdenamentoEmLote(self, sessao, itens: list):
        """
        Remove registros de ordenamento em lote com base em uma lista de tuplas.

        Parâmetros:
            sessao (Session): Sessão ativa do banco de dados.
            itens (list): Lista de tuplas contendo (tipo, idReferencia).
        """
        if not itens:
            return
        porTipo = {}
        for tipo, idReferencia in itens:
            if tipo not in porTipo:
                porTipo[tipo] = []
            porTipo[tipo].append(str(idReferencia))
        
        for tipo, ids in porTipo.items():
            sessao.query(CtlDreOrdenamento).filter(
                CtlDreOrdenamento.tipo_no == tipo,
                CtlDreOrdenamento.id_referencia.in_(ids)
            ).delete(synchronize_session=False)

    def limparOrdenamentoPorContextos(self, sessao, contextos: list):
        """
        Remove registros de ordenamento baseados em contextos pais.

        Parâmetros:
            sessao (Session): Sessão ativa do banco de dados.
            contextos (list): Lista de strings representando os contextos a serem limpos.
        """
        if not contextos:
            return
        sessao.query(CtlDreOrdenamento).filter(
            CtlDreOrdenamento.contexto_pai.in_(contextos)
        ).delete(synchronize_session=False)

    def gerarDescricaoFormula(self, formula: dict) -> str:
        """
        Gera uma representação textual e legível de uma fórmula em formato JSON.

        Parâmetros:
            formula (dict): Dicionário contendo a estrutura da fórmula.

        Retornos:
            str: Descrição matemática da fórmula gerada.
        """
        operacoes = {"soma": "+", "subtracao": "-", "multiplicacao": "×", "divisao": "÷"}
        operacao = formula.get('operacao', 'soma')
        operandos = formula.get('operandos', [])
        simbolo = operacoes.get(operacao, '+')
        rotulos = [str(operando.get('label') or operando.get('id', '?')) for operando in operandos]
        descricao = f" {simbolo} ".join(rotulos)
        
        if formula.get('multiplicador'):
            descricao = f"({descricao}) × {formula['multiplicador']}"
        return descricao

    def obterDadosArvore(self):
        """
        Monta a estrutura completa em árvore para visualização no frontend.

        Retornos:
            tuple: Contém os dados estruturados (list) ou dicionário de erro (dict), e o status code HTTP (int).
        """
        sessao = self.obterSessao()
        try:
            inicio = time.time()
            
            sqlBase = text("""
                SELECT DISTINCT "Tipo", "Nome", "Codigo" 
                FROM "Dre_Schema"."Tb_CTL_Cad_Centro_Custo"
                WHERE "Codigo" IS NOT NULL
                ORDER BY "Tipo", "Nome"
            """)
            resultadoBase = sessao.execute(sqlBase).mappings().all()

            subgrupos = sessao.query(CtlDreHierarquia).all()
            vinculos = sessao.query(CtlDreContaVinculo).all()
            virtuais = sessao.query(CtlDreNoVirtual).order_by(CtlDreNoVirtual.Ordem).all()
            contasDetalhe = sessao.query(CtlDreContaPersonalizada).all()
            
            sqlNomes = text("""
                SELECT DISTINCT "Conta", "Título Conta"
                FROM "Dre_Schema"."Vw_CTL_Razao_Consolidado"
                WHERE "Conta" IS NOT NULL
            """)
            resultadoNomes = sessao.execute(sqlNomes).fetchall()
            mapaNomesContas = {str(linha[0]): linha[1] for linha in resultadoNomes}

            vinculosPorHierarquia = {}
            for vinculo in vinculos:
                if vinculo.Id_Hierarquia not in vinculosPorHierarquia:
                    vinculosPorHierarquia[vinculo.Id_Hierarquia] = []
                vinculosPorHierarquia[vinculo.Id_Hierarquia].append(vinculo)
            
            detalhePorHierarquia = {}
            detalhePorVirtual = {}
            for conta in contasDetalhe:
                if conta.Id_Hierarquia:
                    if conta.Id_Hierarquia not in detalhePorHierarquia:
                        detalhePorHierarquia[conta.Id_Hierarquia] = []
                    detalhePorHierarquia[conta.Id_Hierarquia].append(conta)
                if conta.Id_No_Virtual:
                    if conta.Id_No_Virtual not in detalhePorVirtual:
                        detalhePorVirtual[conta.Id_No_Virtual] = []
                    detalhePorVirtual[conta.Id_No_Virtual].append(conta)
            
            subgruposPorPai = {}
            subgruposPorCentroCusto = {}
            subgruposPorVirtual = {}
            subgruposRaizGlobal = []
            
            for subgrupo in subgrupos:
                if subgrupo.Id_Pai:
                    if subgrupo.Id_Pai not in subgruposPorPai:
                        subgruposPorPai[subgrupo.Id_Pai] = []
                    subgruposPorPai[subgrupo.Id_Pai].append(subgrupo)
                elif subgrupo.Raiz_Centro_Custo_Codigo:
                    if subgrupo.Raiz_Centro_Custo_Codigo not in subgruposPorCentroCusto:
                        subgruposPorCentroCusto[subgrupo.Raiz_Centro_Custo_Codigo] = []
                    subgruposPorCentroCusto[subgrupo.Raiz_Centro_Custo_Codigo].append(subgrupo)
                elif subgrupo.Raiz_No_Virtual_Id:
                    if subgrupo.Raiz_No_Virtual_Id not in subgruposPorVirtual:
                        subgruposPorVirtual[subgrupo.Raiz_No_Virtual_Id] = []
                    subgruposPorVirtual[subgrupo.Raiz_No_Virtual_Id].append(subgrupo)
                else:
                    subgruposRaizGlobal.append(subgrupo)

            def listarContasNormais(idSubgrupo):
                lista = []
                for vinculo in vinculosPorHierarquia.get(idSubgrupo, []):
                    numeroConta = str(vinculo.Conta_Contabil)
                    nomeConta = mapaNomesContas.get(numeroConta, "Sem Título")
                    lista.append({
                        "id": f"conta_{numeroConta}", 
                        "text": f"Conta: {numeroConta} - {nomeConta}",
                        "type": "conta", 
                        "parent": idSubgrupo
                    })
                return lista

            def listarContasDetalhe(idSubgrupo):
                return [
                    {
                        "id": f"cd_{conta.Id}", 
                        "text": f"{conta.Conta_Contabil} ({conta.Nome_Personalizado or 'Orig'})", 
                        "type": "conta_detalhe", 
                        "parent": idSubgrupo
                    } 
                    for conta in detalhePorHierarquia.get(idSubgrupo, [])
                ]

            def listarFilhosSubgrupos(idPai):
                filhos = []
                for subgrupo in subgruposPorPai.get(idPai, []):
                    contas = listarContasNormais(subgrupo.Id) + listarContasDetalhe(subgrupo.Id)
                    noArvore = {
                        "id": f"sg_{subgrupo.Id}", 
                        "db_id": subgrupo.Id, 
                        "text": subgrupo.Nome, 
                        "type": "subgrupo",
                        "children": listarFilhosSubgrupos(subgrupo.Id) + contas
                    }
                    filhos.append(noArvore)
                return filhos

            arvoreFinal = []

            for grupoRaiz in subgruposRaizGlobal:
                noArvore = {
                    "id": f"sg_{grupoRaiz.Id}", "db_id": grupoRaiz.Id, "text": grupoRaiz.Nome, "type": "subgrupo", "parent": "root",
                    "children": (listarFilhosSubgrupos(grupoRaiz.Id) + listarContasNormais(grupoRaiz.Id) + listarContasDetalhe(grupoRaiz.Id))
                }
                arvoreFinal.append(noArvore)

            for virtual in virtuais:
                filhosVirtual = []
                for subgrupo in subgruposPorVirtual.get(virtual.Id, []):
                    contasDoGrupo = (listarFilhosSubgrupos(subgrupo.Id) + listarContasDetalhe(subgrupo.Id) + listarContasNormais(subgrupo.Id))
                    noArvore = {"id": f"sg_{subgrupo.Id}", "db_id": subgrupo.Id, "text": subgrupo.Nome, "type": "subgrupo", "children": contasDoGrupo}
                    filhosVirtual.append(noArvore)

                for conta in detalhePorVirtual.get(virtual.Id, []):
                    rotulo = f"{conta.Conta_Contabil} ({conta.Nome_Personalizado or ''})"
                    filhosVirtual.append({"id": f"cd_{conta.Id}", "text": rotulo, "type": "conta_detalhe", "parent": f"virt_{virtual.Id}"})
                
                noVirtual = {
                    "id": f"virt_{virtual.Id}", "text": virtual.Nome, "type": "root_virtual", "is_calculado": virtual.Is_Calculado,
                    "estilo_css": virtual.Estilo_CSS, "children": filhosVirtual
                }
                arvoreFinal.append(noVirtual)

            mapaTipos = {}
            for linha in resultadoBase:
                tipo, nomeCentroCusto, codigoCentroCusto = linha['Tipo'], linha['Nome'], linha['Codigo']
                rotuloCentroCusto = f"{codigoCentroCusto} - {nomeCentroCusto}"
                
                if tipo not in mapaTipos:
                    mapaTipos[tipo] = {"id": f"tipo_{tipo}", "text": tipo, "type": "root_tipo", "children": []}
                
                filhosDoCentroCusto = []
                for subgrupo in subgruposPorCentroCusto.get(codigoCentroCusto, []):
                    noArvore = {
                        "id": f"sg_{subgrupo.Id}", "db_id": subgrupo.Id, "text": subgrupo.Nome, "type": "subgrupo", 
                        "children": (listarFilhosSubgrupos(subgrupo.Id) + listarContasNormais(subgrupo.Id) + listarContasDetalhe(subgrupo.Id))
                    }
                    filhosDoCentroCusto.append(noArvore)

                noCentroCusto = {"id": f"cc_{codigoCentroCusto}", "text": rotuloCentroCusto, "type": "root_cc", "children": filhosDoCentroCusto}
                mapaTipos[tipo]["children"].append(noCentroCusto)

            arvoreFinal.extend(list(mapaTipos.values()))

            return arvoreFinal, 200

        except Exception as excecao:
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def obterContasDisponiveis(self):
        """
        Consulta as contas contábeis únicas consolidadas.

        Retornos:
            tuple: Contém a lista de contas formatada ou dicionário de erro, e o status code HTTP.
        """
        sessao = self.obterSessao()
        try:
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
            resultado = sessao.execute(sql).fetchall()
            contas = [{"numero": linha[0], "nome": linha[1]} for linha in resultado]
            return contas, 200
        except Exception as excecao:
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def obterContasSubgrupo(self, dados: dict):
        """
        Retorna as contas contábeis vinculadas a um subgrupo específico.

        Parâmetros:
            dados (dict): Dicionário contendo o identificador do subgrupo ('id').

        Retornos:
            tuple: Lista de contas ou erro, e o status code HTTP.
        """
        sessao = self.obterSessao()
        try:
            idOriginal = dados.get('id')
            if not idOriginal: 
                return [], 200
            try: 
                idSubgrupo = int(idOriginal)
            except ValueError: 
                return [], 200

            sql = text("""
                SELECT "Conta_Contabil" 
                FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo"
                WHERE "Id_Hierarquia" = :idSubgrupo
            """)
            resultado = sessao.execute(sql, {"idSubgrupo": idSubgrupo}).fetchall()
            return [str(linha[0]) for linha in resultado], 200
        except Exception as excecao:
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def obterSubgruposPorTipo(self, dados: dict):
        """
        Busca todos os subgrupos relacionados a um tipo de centro de custo.

        Parâmetros:
            dados (dict): Dicionário contendo 'tipo_cc'.

        Retornos:
            tuple: Lista de nomes dos subgrupos ordenados ou erro, e status code HTTP.
        """
        sessao = self.obterSessao()
        try:
            tipoCentroCusto = dados.get('tipo_cc') 
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
            linhas = sessao.execute(sql, {'tipo': tipoCentroCusto}).fetchall()
            return [linha[0] for linha in linhas], 200
        except Exception as excecao:
            return {'error': str(excecao)}, 500
        finally:
            sessao.close()

    def obterContasGrupoMassa(self, dados: dict):
        """
        Busca contas (padrão e personalizadas) ligadas a um nome de grupo e tipo de centro de custo específicos em massa.

        Parâmetros:
            dados (dict): Dicionário contendo 'tipo_cc' e 'nome_grupo'.

        Retornos:
            tuple: Lista de dicionários de contas combinadas ou erro, e status code HTTP.
        """
        sessao = self.obterSessao()
        try:
            tipoCentroCusto = dados.get('tipo_cc')
            nomeGrupo = dados.get('nome_grupo')
            if not tipoCentroCusto or not nomeGrupo: 
                return [], 200

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
            resultado = sessao.execute(sql, {'tipo': tipoCentroCusto, 'nome': nomeGrupo}).fetchall()
            listaFinal = [{"conta": linha[0], "tipo": linha[1], "nome_personalizado": linha[2]} for linha in resultado]
            return listaFinal, 200
        except Exception as excecao:
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def obterNosCalculados(self):
        """
        Consulta informações estruturais sobre os nós virtuais calculados.

        Retornos:
            tuple: Lista dos nós estruturada ou erro, e status code HTTP.
        """
        sessao = self.obterSessao()
        try:
            sql = text("""
                SELECT "Id", "Nome", "Ordem", "Formula_JSON", "Formula_Descricao", 
                       "Tipo_Exibicao", "Estilo_CSS"
                FROM "Dre_Schema"."Tb_CTL_Dre_No_Virtual"
                WHERE "Is_Calculado" = true
                ORDER BY "Ordem" ASC
            """)
            resultado = sessao.execute(sql).fetchall()
            nosCalculados = [{"id": n[0], "nome": n[1], "ordem": n[2], "formula": json.loads(n[3]) if n[3] else None, 
                    "formula_descricao": n[4], "tipo_exibicao": n[5], "estilo_css": n[6]} for n in resultado]
            return nosCalculados, 200
        except Exception as excecao:
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def obterOperandosDisponiveis(self):
        """
        Fornece os itens disponíveis para montagem de fórmulas, incluindo nós virtuais,
        tipos de centro de custo e subgrupos raízes.

        Retornos:
            tuple: Dicionário contendo os conjuntos disponíveis ou erro, e status code HTTP.
        """
        sessao = self.obterSessao()
        try:
            resultadoOperacoes = {"nos_virtuais": [], "tipos_cc": [], "subgrupos_raiz": []}
            
            sqlVirtuais = text('SELECT "Id", "Nome", "Is_Calculado" FROM "Dre_Schema"."Tb_CTL_Dre_No_Virtual" ORDER BY "Ordem" ASC')
            for linha in sessao.execute(sqlVirtuais).fetchall():
                resultadoOperacoes["nos_virtuais"].append({"id": linha[0], "nome": linha[1], "is_calculado": linha[2]})
            
            sqlTipos = text('SELECT DISTINCT "Tipo" FROM "Dre_Schema"."Tb_CTL_Cad_Centro_Custo" WHERE "Tipo" IS NOT NULL ORDER BY "Tipo"')
            for linha in sessao.execute(sqlTipos).fetchall():
                resultadoOperacoes["tipos_cc"].append({"id": linha[0], "nome": linha[0]})
            
            sqlSubgrupos = text('SELECT DISTINCT "Nome" FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" WHERE "Id_Pai" IS NULL ORDER BY "Nome"')
            for linha in sessao.execute(sqlSubgrupos).fetchall():
                resultadoOperacoes["subgrupos_raiz"].append({"id": linha[0], "nome": linha[0]})
            
            return resultadoOperacoes, 200
        except Exception as excecao:
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def adicionarSubgrupo(self, dados: dict):
        """
        Insere um novo subgrupo na hierarquia da DRE.

        Parâmetros:
            dados (dict): Dicionário contendo 'nome' e 'parent_id'.

        Retornos:
            tuple: Resultado da operação (com id em caso de sucesso) ou erro, e status code HTTP.
        """
        sessao = self.obterSessao()
        try:
            nome = dados.get('nome')
            idNoPai = str(dados.get('parent_id')) 

            if not nome: 
                return {"error": "Nome do grupo é obrigatório"}, 400

            novoSubgrupo = CtlDreHierarquia(Nome=nome)
            ordemContextoPai = ""
            profundidadeNivel = 3

            if idNoPai == 'root':
                novoSubgrupo.Id_Pai = None
                novoSubgrupo.Raiz_Centro_Custo_Codigo = None
                novoSubgrupo.Raiz_No_Virtual_Id = None
                ordemContextoPai = "root"
                profundidadeNivel = 0
                registroDuplicado = sessao.query(CtlDreHierarquia.Id).filter(
                    CtlDreHierarquia.Id_Pai == None, CtlDreHierarquia.Raiz_Centro_Custo_Codigo == None,
                    CtlDreHierarquia.Raiz_No_Virtual_Id == None, func.lower(CtlDreHierarquia.Nome) == nome.strip().lower()
                ).first()

            elif idNoPai.startswith("cc_"):
                codigoCentroCustoInteiro = int(idNoPai.replace("cc_", ""))
                sqlInfo = text("""
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
                resultadoInfo = sessao.execute(sqlInfo, {"cod": codigoCentroCustoInteiro, "nome": nome.strip()}).first()
                if resultadoInfo and resultadoInfo[2]: 
                    return {"error": f"Já existe um grupo '{nome}' neste local."}, 400
                
                novoSubgrupo.Raiz_Centro_Custo_Tipo = resultadoInfo[0] if resultadoInfo else "Indefinido"
                novoSubgrupo.Raiz_Centro_Custo_Nome = resultadoInfo[1] if resultadoInfo else "Indefinido"
                novoSubgrupo.Raiz_Centro_Custo_Codigo = codigoCentroCustoInteiro
                ordemContextoPai = f"cc_{codigoCentroCustoInteiro}"
                profundidadeNivel = 2
                registroDuplicado = None

            elif idNoPai.startswith("virt_"):
                idVirtual = int(idNoPai.replace("virt_", ""))
                sqlVirtual = text("""
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
                resultadoVirtual = sessao.execute(sqlVirtual, {"vid": idVirtual, "nome": nome.strip()}).first()
                if resultadoVirtual and resultadoVirtual[1]: 
                    return {"error": f"Já existe um grupo '{nome}' neste local."}, 400
                
                novoSubgrupo.Raiz_No_Virtual_Id = idVirtual
                novoSubgrupo.Raiz_No_Virtual_Nome = resultadoVirtual[0] if resultadoVirtual else None
                ordemContextoPai = f"virt_{idVirtual}"
                profundidadeNivel = 2
                registroDuplicado = None

            elif idNoPai.startswith("sg_"):
                idPaiSubgrupo = int(idNoPai.replace("sg_", ""))
                sqlPai = text("""
                    SELECT p."Raiz_Centro_Custo_Codigo", p."Raiz_Centro_Custo_Tipo", p."Raiz_No_Virtual_Id",
                        EXISTS(
                            SELECT 1 FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h
                            WHERE h."Id_Pai" = :pid AND LOWER(h."Nome") = LOWER(:nome)
                        ) as duplicado
                    FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" p
                    WHERE p."Id" = :pid
                """)
                resultadoPai = sessao.execute(sqlPai, {"pid": idPaiSubgrupo, "nome": nome.strip()}).first()
                if resultadoPai and resultadoPai[3]: 
                    return {"error": f"Já existe um grupo '{nome}' neste local."}, 400
                
                novoSubgrupo.Id_Pai = idPaiSubgrupo
                if resultadoPai:
                    novoSubgrupo.Raiz_Centro_Custo_Codigo = resultadoPai[0]
                    novoSubgrupo.Raiz_Centro_Custo_Tipo = resultadoPai[1]
                    novoSubgrupo.Raiz_No_Virtual_Id = resultadoPai[2]
                ordemContextoPai = f"sg_{idPaiSubgrupo}"
                profundidadeNivel = 3
                registroDuplicado = None
            else:
                registroDuplicado = None

            if 'registroDuplicado' in locals() and registroDuplicado: 
                return {"error": f"Já existe um grupo '{nome}' neste local."}, 400

            sessao.add(novoSubgrupo)
            sessao.flush()

            novaOrdem = calcular_proxima_ordem(sessao, ordemContextoPai)
            registroOrdem = CtlDreOrdenamento(tipo_no='subgrupo', id_referencia=str(novoSubgrupo.Id), contexto_pai=ordemContextoPai, ordem=novaOrdem, nivel_profundidade=profundidadeNivel)
            sessao.add(registroOrdem)

            sessao.commit()
            return {"success": True, "id": novoSubgrupo.Id}, 200
        except Exception as excecao:
            sessao.rollback()
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def adicionarSubgrupoSistematico(self, dados: dict):
        """
        Cria subgrupos raízes em massa para diversos centros de custo de determinado tipo.

        Parâmetros:
            dados (dict): Dicionário com 'nome' e 'tipo_cc'.

        Retornos:
            tuple: Resultado da criação em lote ou erro, e status code HTTP.
        """
        sessao = self.obterSessao()
        try:
            nomeGrupo = dados.get('nome')
            tipoCentroCusto = dados.get('tipo_cc')
            if not nomeGrupo or not tipoCentroCusto: 
                return {"error": "Nome do grupo e Tipo são obrigatórios"}, 400

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
            centrosCustoParaCriar = sessao.execute(sql, {"tipo": tipoCentroCusto, "nome": nomeGrupo}).fetchall()

            if not centrosCustoParaCriar:
                return {"success": True, "msg": "Nenhum grupo criado (todos os CCs já possuíam este grupo)."}, 200

            novosSubgrupos = []
            for centroCusto in centrosCustoParaCriar:
                novosSubgrupos.append(CtlDreHierarquia(
                    Nome=nomeGrupo, Id_Pai=None, Raiz_Centro_Custo_Codigo=centroCusto[0],
                    Raiz_Centro_Custo_Nome=centroCusto[1], Raiz_Centro_Custo_Tipo=centroCusto[2]
                ))
            
            sessao.bulk_save_objects(novosSubgrupos)
            sessao.commit()
            return {"success": True, "msg": f"Grupo '{nomeGrupo}' criado em {len(novosSubgrupos)} Centros de Custo!"}, 200
        except Exception as excecao:
            sessao.rollback()
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def adicionarNoVirtual(self, dados: dict):
        """
        Cria um novo nó de estrutura virtual.

        Parâmetros:
            dados (dict): Dicionário contendo 'nome' e, opcionalmente, 'cor'.

        Retornos:
            tuple: Resultado da inserção com ID criado ou erro, e status code HTTP.
        """
        sessao = self.obterSessao()
        try:
            nome = dados.get('nome')
            cor = dados.get('cor')
            estiloCss = f"color: {cor};" if cor else None
            
            if not nome: 
                return {"error": "Nome obrigatório"}, 400
            
            sql = text("""
                INSERT INTO "Dre_Schema"."Tb_CTL_Dre_No_Virtual" ("Nome", "Estilo_CSS")
                SELECT :nome, :estilo
                WHERE NOT EXISTS (
                    SELECT 1 FROM "Dre_Schema"."Tb_CTL_Dre_No_Virtual"
                    WHERE LOWER("Nome") = LOWER(:nome)
                )
                RETURNING "Id"
            """)
            resultado = sessao.execute(sql, {"nome": nome.strip(), "estilo": estiloCss})
            linhaPersistida = resultado.fetchone()
            
            if not linhaPersistida: 
                return {"error": f"Já existe um Nó Virtual chamado '{nome}'."}, 400
            
            sessao.commit()
            return {"success": True, "id": linhaPersistida[0]}, 200
        except Exception as excecao:
            sessao.rollback()
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def adicionarNoCalculado(self, dados: dict):
        """
        Insere um nó cujos valores são baseados em fórmulas matemáticas de outros nós.

        Parâmetros:
            dados (dict): Dicionário detalhado contendo a configuração da fórmula e metadados visuais.

        Retornos:
            tuple: Mensagem de confirmação ou erro, e status code HTTP.
        """
        sessao = self.obterSessao()
        try:
            nome = dados.get('nome')
            formula = dados.get('formula')
            if not nome: 
                return {"error": "Nome obrigatório"}, 400
            if not formula or 'operacao' not in formula: 
                return {"error": "Fórmula inválida"}, 400
            
            descricaoOperacao = self.gerarDescricaoFormula(formula)
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
            resultado = sessao.execute(sql, {
                "nome": nome.strip(), "ordem": dados.get('ordem', 0), "formula": json.dumps(formula),
                "descricao": descricaoOperacao, "tipo": dados.get('tipo_exibicao', 'valor'),
                "base": dados.get('base_percentual_id'), "estilo": dados.get('estilo_css')
            })
            linhaPersistida = resultado.fetchone()
            if not linhaPersistida: 
                return {"error": f"Já existe um nó chamado '{nome}'"}, 400
            
            sessao.commit()
            return {"success": True, "id": linhaPersistida[0], "msg": f"Nó calculado '{nome}' criado com sucesso!"}, 200
        except Exception as excecao:
            sessao.rollback()
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def vincularConta(self, dados: dict):
        """
        Gera relacionamento de uma conta contábil raiz a um determinado subgrupo.

        Parâmetros:
            dados (dict): Dados para o vínculo ('conta', 'subgrupo_id').

        Retornos:
            tuple: Resultado boolean do processo ou erro, e status code HTTP.
        """
        sessao = self.obterSessao()
        try:
            contaContabil = str(dados.get('conta')).strip()
            idNoSubgrupo = str(dados.get('subgrupo_id')) 

            if not idNoSubgrupo.startswith("sg_"): 
                return {"error": "Contas só podem ser vinculadas a Subgrupos."}, 400
            idSubgrupo = int(idNoSubgrupo.replace("sg_", ""))

            sqlRaiz = text("""
                WITH RECURSIVE hierarquia AS (
                    SELECT "Id", "Id_Pai", "Raiz_Centro_Custo_Codigo", "Raiz_Centro_Custo_Tipo", 
                           "Raiz_No_Virtual_Id", 0 as nivel
                    FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia"
                    WHERE "Id" = :sg_id
                    UNION ALL
                    SELECT p."Id", p."Id_Pai", p."Raiz_Centro_Custo_Codigo", p."Raiz_Centro_Custo_Tipo", 
                           p."Raiz_No_Virtual_Id", h.nivel + 1
                    FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" p
                    INNER JOIN hierarquia h ON h."Id_Pai" = p."Id"
                )
                SELECT "Raiz_Centro_Custo_Codigo", "Raiz_Centro_Custo_Tipo", "Raiz_No_Virtual_Id"
                FROM hierarquia
                WHERE "Raiz_Centro_Custo_Codigo" IS NOT NULL OR "Raiz_No_Virtual_Id" IS NOT NULL
                ORDER BY nivel ASC LIMIT 1
            """)
            resultadoRaiz = sessao.execute(sqlRaiz, {"sg_id": idSubgrupo}).first()
            
            codigoCentroCustoRaiz = resultadoRaiz[0] if resultadoRaiz else None
            tipoCentroCustoRaiz = resultadoRaiz[1] if resultadoRaiz and resultadoRaiz[1] else "Virtual"
            idVirtualRaiz = resultadoRaiz[2] if resultadoRaiz else None

            chaveCombinadaTipo = f"{contaContabil}{tipoCentroCustoRaiz}"
            chaveCombinadaCodigo = f"{contaContabil}{codigoCentroCustoRaiz}" if codigoCentroCustoRaiz else f"{contaContabil}VIRTUAL{idVirtualRaiz}"

            sqlVincularConta = text("""
                INSERT INTO "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" 
                    ("Conta_Contabil", "Id_Hierarquia", "Chave_Conta_Tipo_CC", "Chave_Conta_Codigo_CC")
                VALUES (:conta, :sg_id, :chave_tipo, :chave_cod)
                ON CONFLICT ("Chave_Conta_Codigo_CC") DO UPDATE SET
                    "Id_Hierarquia" = EXCLUDED."Id_Hierarquia",
                    "Chave_Conta_Tipo_CC" = EXCLUDED."Chave_Conta_Tipo_CC",
                    "Conta_Contabil" = EXCLUDED."Conta_Contabil"
            """)
            sessao.execute(sqlVincularConta, {"conta": contaContabil, "sg_id": idSubgrupo, "chave_tipo": chaveCombinadaTipo, "chave_cod": chaveCombinadaCodigo})

            sessao.query(CtlDreOrdenamento).filter(CtlDreOrdenamento.tipo_no == 'conta', CtlDreOrdenamento.id_referencia == contaContabil).delete()

            contextoOrdenamentoPai = f"sg_{idSubgrupo}"
            novaOrdemConta = calcular_proxima_ordem(sessao, contextoOrdenamentoPai)
            registroOrdemConta = CtlDreOrdenamento(tipo_no='conta', id_referencia=contaContabil, contexto_pai=contextoOrdenamentoPai, ordem=novaOrdemConta, nivel_profundidade=99)
            sessao.add(registroOrdemConta)

            sessao.commit()
            return {"success": True}, 200
        except Exception as excecao:
            sessao.rollback()
            print(f"Erro vincularConta: {str(excecao)}")
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def vincularContaDetalhe(self, dados: dict):
        """
        Vínculo de uma conta contábil personalizada, sobreescrevendo título da conta de detalhe.

        Parâmetros:
            dados (dict): Dicionário contento 'conta', 'nome_personalizado', 'parent_id'.

        Retornos:
            tuple: Resultado e status code HTTP.
        """
        sessao = self.obterSessao()
        try:
            contaContabil = str(dados.get('conta')).strip()
            nomeDaContaPersonalizada = dados.get('nome_personalizado')
            idDaContaPai = str(dados.get('parent_id'))

            if not contaContabil or not idDaContaPai: 
                return {"error": "Dados incompletos"}, 400

            idLocalHierarquia, idLocalNoVirtual = None, None
            if idDaContaPai.startswith("virt_"): 
                idLocalNoVirtual = int(idDaContaPai.replace("virt_", ""))
            elif idDaContaPai.startswith("sg_"): 
                idLocalHierarquia = int(idDaContaPai.replace("sg_", ""))

            if idLocalHierarquia:
                sqlVincularDetalhe = text("""
                    INSERT INTO "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada"
                        ("Conta_Contabil", "Nome_Personalizado", "Id_Hierarquia", "Id_No_Virtual")
                    VALUES (:conta, :nome, :hier, :virt)
                    ON CONFLICT ("Conta_Contabil", "Id_Hierarquia") DO UPDATE SET
                        "Nome_Personalizado" = EXCLUDED."Nome_Personalizado",
                        "Id_No_Virtual" = EXCLUDED."Id_No_Virtual"
                """)
            else:
                sqlVincularDetalhe = text("""
                    INSERT INTO "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada"
                        ("Conta_Contabil", "Nome_Personalizado", "Id_Hierarquia", "Id_No_Virtual")
                    VALUES (:conta, :nome, :hier, :virt)
                    ON CONFLICT ("Conta_Contabil", "Id_No_Virtual") DO UPDATE SET
                        "Nome_Personalizado" = EXCLUDED."Nome_Personalizado",
                        "Id_Hierarquia" = EXCLUDED."Id_Hierarquia"
                """)
            
            sessao.execute(sqlVincularDetalhe, {"conta": contaContabil, "nome": nomeDaContaPersonalizada, "hier": idLocalHierarquia, "virt": idLocalNoVirtual})
            sessao.commit()
            return {"success": True}, 200
        except Exception as excecao:
            sessao.rollback()
            print(f"Erro vincularContaDetalhe: {str(excecao)}")
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def renomearNoVirtual(self, dados: dict):
        """
        Altera o título de um nó virtual.

        Parâmetros:
            dados (dict): Contém 'novo_nome' e 'id'.

        Retornos:
            tuple: Resultado e status code HTTP.
        """
        sessao = self.obterSessao()
        try:
            sqlRenomearVirtual = text('UPDATE "Dre_Schema"."Tb_CTL_Dre_No_Virtual" SET "Nome" = :nome WHERE "Id" = :id')
            resultadoAtualizacao = sessao.execute(sqlRenomearVirtual, {"nome": dados.get('novo_nome'), "id": int(dados.get('id').replace('virt_', ''))})
            if resultadoAtualizacao.rowcount == 0: 
                return {"error": "Nó não encontrado"}, 404
            sessao.commit()
            return {"success": True}, 200
        except Exception as excecao:
            sessao.rollback()
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def renomearSubgrupo(self, dados: dict):
        """
        Altera o título de um subgrupo estrutural.

        Parâmetros:
            dados (dict): Contém 'novo_nome' e 'id'.

        Retornos:
            tuple: Resultado e status code HTTP.
        """
        sessao = self.obterSessao()
        try:
            sqlRenomearSubgrupo = text('UPDATE "Dre_Schema"."Tb_CTL_Dre_Hierarquia" SET "Nome" = :nome WHERE "Id" = :id')
            resultadoAtualizacao = sessao.execute(sqlRenomearSubgrupo, {"nome": dados.get('novo_nome'), "id": int(dados.get('id').replace('sg_', ''))})
            if resultadoAtualizacao.rowcount == 0: 
                return {"error": "Subgrupo não encontrado"}, 404
            sessao.commit()
            return {"success": True}, 200
        except Exception as excecao:
            sessao.rollback()
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def renomearContaPersonalizada(self, dados: dict):
        """
        Altera a descrição sobreescrita de uma conta personalizável na árvore.

        Parâmetros:
            dados (dict): Contém 'novo_nome' e 'id'.

        Retornos:
            tuple: Resultado e status code HTTP.
        """
        sessao = self.obterSessao()
        try:
            sqlRenomearPersonalizada = text('UPDATE "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" SET "Nome_Personalizado" = :nome WHERE "Id" = :id')
            resultadoAtualizacao = sessao.execute(sqlRenomearPersonalizada, {"nome": dados.get('novo_nome'), "id": int(dados.get('id').replace('cd_', ''))})
            if resultadoAtualizacao.rowcount == 0: 
                return {"error": "Conta detalhe não encontrada"}, 404
            sessao.commit()
            return {"success": True}, 200
        except Exception as excecao:
            sessao.rollback()
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def atualizarNoCalculado(self, dados: dict):
        """
        Altera parâmetros e equações de um nó derivado (calculado).

        Parâmetros:
            dados (dict): Elementos estruturais para atualização parcial.

        Retornos:
            tuple: Resultado e status code HTTP.
        """
        sessao = self.obterSessao()
        try:
            listaAtualizacoes, parametros = [], {"id": dados.get('id')}
            
            if dados.get('nome'):
                listaAtualizacoes.append('"Nome" = :nome')
                parametros["nome"] = dados.get('nome')
            if dados.get('formula'):
                listaAtualizacoes.extend(['"Formula_JSON" = :formula', '"Formula_Descricao" = :descricao'])
                parametros["formula"], parametros["descricao"] = json.dumps(dados.get('formula')), self.gerarDescricaoFormula(dados.get('formula'))
            if dados.get('ordem') is not None:
                listaAtualizacoes.append('"Ordem" = :ordem')
                parametros["ordem"] = dados.get('ordem')
            if dados.get('tipo_exibicao'):
                listaAtualizacoes.append('"Tipo_Exibicao" = :tipo')
                parametros["tipo"] = dados.get('tipo_exibicao')
            if dados.get('estilo_css') is not None:
                listaAtualizacoes.append('"Estilo_CSS" = :estilo')
                parametros["estilo"] = dados.get('estilo_css')
            
            if not listaAtualizacoes: 
                return {"error": "Nada para atualizar"}, 400
            
            sqlAtualizarCalculado = text(f'UPDATE "Dre_Schema"."Tb_CTL_Dre_No_Virtual" SET {", ".join(listaAtualizacoes)} WHERE "Id" = :id AND "Is_Calculado" = true')
            resultadoAlteracao = sessao.execute(sqlAtualizarCalculado, parametros)
            if resultadoAlteracao.rowcount == 0: 
                return {"error": "Nó não encontrado ou não é calculado"}, 404
            
            sessao.commit()
            return {"success": True, "msg": "Fórmula atualizada!"}, 200
        except Exception as excecao:
            sessao.rollback()
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def excluirSubgrupo(self, dados: dict):
        """
        Exclui as subestruturas que descendem do subgrupo solicitado, bem como a limpeza da ordem.

        Parâmetros:
            dados (dict): Contém o 'id' do nó correspondente ao prefixo local do frontend.

        Retornos:
            tuple: Status do processo ou exceção gerada, e status code HTTP.
        """
        sessao = self.obterSessao()
        try:
            identificadorDoNo = dados.get('id') 
            if not identificadorDoNo or not identificadorDoNo.startswith('sg_'): 
                return {"error": "Nó inválido para exclusão"}, 400
            idNoBancoDados = int(identificadorDoNo.replace('sg_', ''))
            
            sqlBuscaRecursivaIds = text("""
                WITH RECURSIVE todos_ids AS (
                    SELECT "Id" FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" WHERE "Id" = :id
                    UNION ALL
                    SELECT h."Id" 
                    FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h
                    INNER JOIN todos_ids t ON h."Id_Pai" = t."Id"
                )
                SELECT "Id" FROM todos_ids
            """)
            listaTotalIdsHierarquia = [linha[0] for linha in sessao.execute(sqlBuscaRecursivaIds, {"id": idNoBancoDados}).fetchall()]
            if not listaTotalIdsHierarquia: 
                return {"error": "Grupo não encontrado"}, 404
            
            contasParaLimpezaDeOrdem = []
            for linha in sessao.execute(text('SELECT "Conta_Contabil" FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": listaTotalIdsHierarquia}).fetchall():
                contasParaLimpezaDeOrdem.append(('conta', linha[0]))
            
            for linha in sessao.execute(text('SELECT "Id" FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": listaTotalIdsHierarquia}).fetchall():
                contasParaLimpezaDeOrdem.append(('conta_detalhe', str(linha[0])))
            
            self.limparOrdenamentoEmLote(sessao, contasParaLimpezaDeOrdem)
            self.limparOrdenamentoEmLote(sessao, [('subgrupo', str(idProcessado)) for idProcessado in listaTotalIdsHierarquia])
            self.limparOrdenamentoPorContextos(sessao, [f'sg_{idProcessado}' for idProcessado in listaTotalIdsHierarquia])
            
            sessao.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": listaTotalIdsHierarquia})
            sessao.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": listaTotalIdsHierarquia})
            sessao.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" WHERE "Id" = ANY(:ids)'), {"ids": listaTotalIdsHierarquia})
            sessao.commit()
            return {"success": True, "msg": "Grupo e todos os seus itens excluídos."}, 200
        except Exception as excecao:
            sessao.rollback()
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def desvincularConta(self, dados: dict):
        """
        Retira do banco de dados a associação unitária efetuada para a conta selecionada.

        Parâmetros:
            dados (dict): Contém 'id' do frontend (podendo ser 'conta_' ou 'cd_').

        Retornos:
            tuple: Resultado ou erro, e status code HTTP.
        """
        sessao = self.obterSessao()
        try:
            identificadorDoNo = dados.get('id')
            if identificadorDoNo.startswith('conta_'):
                contaSelecionada = identificadorDoNo.replace('conta_', '')
                sessao.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" WHERE "Conta_Contabil" = :conta'), {"conta": contaSelecionada})
                sessao.query(CtlDreOrdenamento).filter(CtlDreOrdenamento.tipo_no == 'conta', CtlDreOrdenamento.id_referencia == contaSelecionada).delete(synchronize_session=False)
            elif identificadorDoNo.startswith('cd_'):
                identificadorDetalhe = int(identificadorDoNo.replace('cd_', ''))
                sessao.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id" = :id'), {"id": identificadorDetalhe})
                sessao.query(CtlDreOrdenamento).filter(CtlDreOrdenamento.tipo_no == 'conta_detalhe', CtlDreOrdenamento.id_referencia == str(identificadorDetalhe)).delete(synchronize_session=False)
            else:
                return {"error": "Tipo de vínculo não reconhecido"}, 400
            sessao.commit()
            return {"success": True}, 200
        except Exception as excecao:
            sessao.rollback()
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def excluirNoVirtual(self, dados: dict):
        """
        Exclui nó do modelo de dados virtual (fictício), suas ramificações e contas detalhe acopladas.

        Parâmetros:
            dados (dict): Identificador formatado ('virt_xx') originado no frontend.

        Retornos:
            tuple: Resultado e status code HTTP.
        """
        sessao = self.obterSessao()
        try:
            identificadorDoNo = dados.get('id')
            if not identificadorDoNo or not identificadorDoNo.startswith('virt_'): 
                return {"error": "Nó inválido"}, 400
            identificadorVirtualLimpo = int(identificadorDoNo.replace('virt_', ''))
            
            sqlEncontrarFiliacoesVirtuais = text("""
                WITH RECURSIVE todos AS (
                    SELECT "Id" FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" WHERE "Raiz_No_Virtual_Id" = :vid
                    UNION ALL
                    SELECT h."Id" FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h
                    INNER JOIN todos t ON h."Id_Pai" = t."Id"
                )
                SELECT "Id" FROM todos
            """)
            idsHierarquicosRelacionados = [linha[0] for linha in sessao.execute(sqlEncontrarFiliacoesVirtuais, {"vid": identificadorVirtualLimpo}).fetchall()]
            itensDeOrdenamentoProcessados = []

            if idsHierarquicosRelacionados:
                for linha in sessao.execute(text('SELECT "Conta_Contabil" FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": idsHierarquicosRelacionados}).fetchall():
                    itensDeOrdenamentoProcessados.append(('conta', linha[0]))
                for linha in sessao.execute(text('SELECT "Id" FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": idsHierarquicosRelacionados}).fetchall():
                    itensDeOrdenamentoProcessados.append(('conta_detalhe', str(linha[0])))
                for idHierarquico in idsHierarquicosRelacionados: 
                    itensDeOrdenamentoProcessados.append(('subgrupo', str(idHierarquico)))
                
                sessao.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": idsHierarquicosRelacionados})
                sessao.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": idsHierarquicosRelacionados})
                sessao.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" WHERE "Id" = ANY(:ids)'), {"ids": idsHierarquicosRelacionados})

            for linha in sessao.execute(text('SELECT "Id" FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id_No_Virtual" = :vid'), {"vid": identificadorVirtualLimpo}).fetchall():
                itensDeOrdenamentoProcessados.append(('conta_detalhe', str(linha[0])))
            sessao.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id_No_Virtual" = :vid'), {"vid": identificadorVirtualLimpo})

            itensDeOrdenamentoProcessados.append(('virtual', str(identificadorVirtualLimpo)))
            self.limparOrdenamentoEmLote(sessao, itensDeOrdenamentoProcessados)
            self.limparOrdenamentoPorContextos(sessao, [f'virt_{identificadorVirtualLimpo}'] + [f'sg_{idProcessado}' for idProcessado in idsHierarquicosRelacionados])

            sessao.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_No_Virtual" WHERE "Id" = :vid'), {"vid": identificadorVirtualLimpo})
            sessao.commit()
            return {"success": True, "msg": "Estrutura virtual excluída."}, 200
        except Exception as excecao:
            sessao.rollback()
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def vincularContaEmMassa(self, dados: dict):
        """
        Opera o vínculo de uma conta contábil a variados locais dentro da hierarquia em massa.

        Parâmetros:
            dados (dict): Requisição da payload.

        Retornos:
            tuple: Resumo das ocorrências de sucesso.
        """
        sessao = self.obterSessao()
        try:
            tipoCentroCusto = dados.get('tipo_cc')
            nomeSubgrupoAlvo = dados.get('nome_subgrupo')
            contaContabilSelecionada = str(dados.get('conta')).strip()
            ehPersonalizada = dados.get('is_personalizada', False)
            nomeDaContaPersonalizado = dados.get('nome_personalizado_conta')
            
            if not all([tipoCentroCusto, nomeSubgrupoAlvo, contaContabilSelecionada]): 
                return {"error": "Dados incompletos."}, 400

            if ehPersonalizada:
                if not nomeDaContaPersonalizado:
                    resultadoQuery = sessao.execute(text('SELECT "Título Conta" FROM "Dre_Schema"."Vw_CTL_Razao_Consolidado" WHERE "Conta" = :c LIMIT 1'), {'c': contaContabilSelecionada}).first()
                    nomeDaContaPersonalizado = resultadoQuery[0] if resultadoQuery else "Sem Nome"
                
                sqlAdicionarEmMassa = text("""
                    INSERT INTO "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" ("Conta_Contabil", "Nome_Personalizado", "Id_Hierarquia")
                    SELECT :conta, :nome, h."Id"
                    FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h
                    WHERE h."Raiz_Centro_Custo_Tipo" = :tipo AND h."Nome" = :subgrupo
                    ON CONFLICT ("Conta_Contabil", "Id_Hierarquia") DO UPDATE SET "Nome_Personalizado" = EXCLUDED."Nome_Personalizado"
                """)
                resultadoBulk = sessao.execute(sqlAdicionarEmMassa, {"conta": contaContabilSelecionada, "nome": nomeDaContaPersonalizado, "tipo": tipoCentroCusto, "subgrupo": nomeSubgrupoAlvo})
                contagemDeSucesso = resultadoBulk.rowcount
            else:
                sqlAdicionarEmMassa = text("""
                    INSERT INTO "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" ("Conta_Contabil", "Id_Hierarquia", "Chave_Conta_Tipo_CC", "Chave_Conta_Codigo_CC")
                    SELECT CAST(:conta AS TEXT), h."Id", CAST(:conta AS TEXT) || :tipo, CAST(:conta AS TEXT) || CAST(h."Raiz_Centro_Custo_Codigo" AS TEXT)
                    FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h
                    WHERE h."Raiz_Centro_Custo_Tipo" = :tipo AND h."Nome" = :subgrupo AND h."Raiz_Centro_Custo_Codigo" IS NOT NULL
                    ON CONFLICT ("Chave_Conta_Codigo_CC") DO UPDATE SET "Id_Hierarquia" = EXCLUDED."Id_Hierarquia", "Chave_Conta_Tipo_CC" = EXCLUDED."Chave_Conta_Tipo_CC"
                """)
                resultadoBulk = sessao.execute(sqlAdicionarEmMassa, {"conta": contaContabilSelecionada, "tipo": tipoCentroCusto, "subgrupo": nomeSubgrupoAlvo})
                contagemDeSucesso = resultadoBulk.rowcount

            sessao.commit()
            mensagemAdicional = f" com nome '{nomeDaContaPersonalizado}'" if ehPersonalizada and nomeDaContaPersonalizado else ""
            return {"success": True, "msg": f"Conta {contaContabilSelecionada} vinculada em {contagemDeSucesso} locais{mensagemAdicional}."}, 200
        except Exception as excecao:
            sessao.rollback()
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def desvincularContaEmMassa(self, dados: dict):
        """
        Deleta agrupamentos contábeis a partir de solicitações massivas.

        Parâmetros:
            dados (dict): Tipo, Conta e Validador Lógico.

        Retornos:
            tuple: Desempenho e status code HTTP.
        """
        sessao = self.obterSessao()
        try:
            tipoCentroCusto = dados.get('tipo_cc')
            contaContabilSelecionada = str(dados.get('conta')).strip()
            ehPersonalizada = dados.get('is_personalizada', False)
            
            if not tipoCentroCusto or not contaContabilSelecionada: 
                return {"error": "Dados inválidos"}, 400

            if ehPersonalizada:
                sqlRemoverPersonalizadaEmMassa = text("""
                    DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" p
                    USING "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h
                    WHERE p."Id_Hierarquia" = h."Id" AND p."Conta_Contabil" = :conta AND h."Raiz_Centro_Custo_Tipo" = :tipo
                """)
                resultadoDelecao = sessao.execute(sqlRemoverPersonalizadaEmMassa, {"conta": contaContabilSelecionada, "tipo": tipoCentroCusto})
                contagemDeSucesso = resultadoDelecao.rowcount
            else:
                sessao.query(CtlDreOrdenamento).filter(CtlDreOrdenamento.tipo_no == 'conta', CtlDreOrdenamento.id_referencia == contaContabilSelecionada).delete(synchronize_session=False)
                chaveReferenciaCombinada = f"{contaContabilSelecionada}{tipoCentroCusto}"
                resultadoDelecao = sessao.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" WHERE "Chave_Conta_Tipo_CC" = :chave'), {"chave": chaveReferenciaCombinada})
                contagemDeSucesso = resultadoDelecao.rowcount

            sessao.commit()
            return {"success": True, "msg": f"Vínculo da conta {contaContabilSelecionada} removido de {contagemDeSucesso} locais."}, 200
        except Exception as excecao:
            sessao.rollback()
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def excluirSubgrupoEmMassa(self, dados: dict):
        """
        Operação destrutiva que remove subgrupos identicos que estão listados entre diversos perfis.

        Parâmetros:
            dados (dict): Localização paramétrica e nominal do recurso.

        Retornos:
            tuple: Total de baixas e status HTTP.
        """
        sessao = self.obterSessao()
        try:
            tipoCentroCusto = dados.get('tipo_cc')
            nomeDoGrupoEspecifico = dados.get('nome_grupo')
            
            if not tipoCentroCusto or not nomeDoGrupoEspecifico: 
                return {"error": "Parâmetros inválidos"}, 400

            sqlBuscarTodaHierarquia = text("""
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
            listaIntegralIdsHierarquia = [linha[0] for linha in sessao.execute(sqlBuscarTodaHierarquia, {"tipo": tipoCentroCusto, "nome": nomeDoGrupoEspecifico}).fetchall()]
            if not listaIntegralIdsHierarquia: 
                return {"error": "Nenhum grupo encontrado com esse nome."}, 404

            registrosDeOrdenamentoGerais = []
            for linha in sessao.execute(text('SELECT "Conta_Contabil" FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": listaIntegralIdsHierarquia}).fetchall():
                registrosDeOrdenamentoGerais.append(('conta', linha[0]))
            for linha in sessao.execute(text('SELECT "Id" FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": listaIntegralIdsHierarquia}).fetchall():
                registrosDeOrdenamentoGerais.append(('conta_detalhe', str(linha[0])))
            for idProcessado in listaIntegralIdsHierarquia: 
                registrosDeOrdenamentoGerais.append(('subgrupo', str(idProcessado)))
            
            self.limparOrdenamentoEmLote(sessao, registrosDeOrdenamentoGerais)
            self.limparOrdenamentoPorContextos(sessao, [f'sg_{idProcessado}' for idProcessado in listaIntegralIdsHierarquia])

            sessao.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": listaIntegralIdsHierarquia})
            sessao.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": listaIntegralIdsHierarquia})
            sessao.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" WHERE "Id" = ANY(:ids)'), {"ids": listaIntegralIdsHierarquia})
            sessao.commit()
            return {"success": True, "msg": f"Exclusão em massa concluída! {len(listaIntegralIdsHierarquia)} itens removidos."}, 200
        except Exception as excecao:
            sessao.rollback()
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()

    def replicarEstrutura(self):
        """
        Método de preenchimento (stub) mantido pelo legado.
        """
        return {"success": True, "msg": "ReplicarEstrutura em manutenção temporária após refatoração."}, 200

    def colarEstrutura(self):
        """
        Método de preenchimento (stub) mantido pelo legado.
        """
        return {"success": True, "msg": "ColarEstrutura em manutenção temporária após refatoração."}, 200

    def replicarTipoIntegral(self, dados: dict):
        """
        Migração profunda que reproduz subgrupos inteiros, contas e dependências operacionais para um tipo alvo.

        Parâmetros:
            dados (dict): Tipo do Blueprint nativo e o Destino solicitado.

        Retornos:
            tuple: Resultado da migração em lote com código HTTP.
        """
        sessao = self.obterSessao()
        try:
            tipoCentroCustoOrigem = dados.get('tipo_origem')
            tipoCentroCustoDestino = dados.get('tipo_destino')
            
            if not tipoCentroCustoOrigem or not tipoCentroCustoDestino: 
                return {"error": "Tipos obrigatórios."}, 400
            if tipoCentroCustoOrigem == tipoCentroCustoDestino: 
                return {"error": "Devem ser diferentes."}, 400

            sqlObterIdsDeDestinoExistentes = text('SELECT "Id" FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" WHERE "Raiz_Centro_Custo_Tipo" = :dest')
            idsExistentesNoDestino = [linha[0] for linha in sessao.execute(sqlObterIdsDeDestinoExistentes, {"dest": tipoCentroCustoDestino}).fetchall()]
            
            if idsExistentesNoDestino:
                self.limparOrdenamentoEmLote(sessao, [('subgrupo', str(idEx)) for idEx in idsExistentesNoDestino])
                self.limparOrdenamentoPorContextos(sessao, [f'sg_{idEx}' for idEx in idsExistentesNoDestino])
                sessao.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": idsExistentesNoDestino})
                sessao.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" WHERE "Id_Hierarquia" = ANY(:ids)'), {"ids": idsExistentesNoDestino})
                sessao.execute(text('DELETE FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" WHERE "Id" = ANY(:ids)'), {"ids": idsExistentesNoDestino})
            
            sqlListarCcsDeDestino = text('SELECT DISTINCT "Codigo", "Nome" FROM "Dre_Schema"."Tb_CTL_Cad_Centro_Custo" WHERE "Tipo" = :dest AND "Codigo" IS NOT NULL')
            centrosCustoDeDestinoProcessados = sessao.execute(sqlListarCcsDeDestino, {"dest": tipoCentroCustoDestino}).fetchall()

            sqlMapearBlueprint = text("""
                SELECT DISTINCT h."Nome", p."Nome" as "Nome_Pai", CASE WHEN h."Id_Pai" IS NULL THEN 0 ELSE 1 END as "Nivel"
                FROM "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h
                LEFT JOIN "Dre_Schema"."Tb_CTL_Dre_Hierarquia" p ON h."Id_Pai" = p."Id"
                WHERE h."Raiz_Centro_Custo_Tipo" = :orig ORDER BY "Nivel" ASC
            """)
            estruturaReferenciaVirtual = sessao.execute(sqlMapearBlueprint, {"orig": tipoCentroCustoOrigem}).fetchall()

            mapaRelacionalDeIdsCriados, rotulosDeGruposRaizes = {}, set()
            def transformarNomeParaAlvo(nomeCru): 
                return nomeCru.replace(tipoCentroCustoOrigem, tipoCentroCustoDestino) if nomeCru else nomeCru

            niveisParaGruposRaizes = [bloco for bloco in estruturaReferenciaVirtual if bloco.Nivel == 0]
            bufferDeInsercoesRaiz = []
            for ccProcessado in centrosCustoDeDestinoProcessados:
                for grupoRaizProcessado in niveisParaGruposRaizes:
                    nomeFormatado = transformarNomeParaAlvo(grupoRaizProcessado.Nome)
                    rotulosDeGruposRaizes.add(nomeFormatado)
                    bufferDeInsercoesRaiz.append({"Nome": nomeFormatado, "Id_Pai": None, "Raiz_Centro_Custo_Codigo": ccProcessado.Codigo, "Raiz_Centro_Custo_Nome": ccProcessado.Nome, "Raiz_Centro_Custo_Tipo": tipoCentroCustoDestino})

            if bufferDeInsercoesRaiz:
                statementSqlRaiz = text('INSERT INTO "Dre_Schema"."Tb_CTL_Dre_Hierarquia" ("Nome", "Id_Pai", "Raiz_Centro_Custo_Codigo", "Raiz_Centro_Custo_Nome", "Raiz_Centro_Custo_Tipo") VALUES (:Nome, :Id_Pai, :Raiz_Centro_Custo_Codigo, :Raiz_Centro_Custo_Nome, :Raiz_Centro_Custo_Tipo) RETURNING "Id", "Nome", "Raiz_Centro_Custo_Codigo"')
                for itemIterado in bufferDeInsercoesRaiz:
                    linhaRetornoProcessada = sessao.execute(statementSqlRaiz, itemIterado).fetchone()
                    mapaRelacionalDeIdsCriados[(linhaRetornoProcessada.Nome, linhaRetornoProcessada.Raiz_Centro_Custo_Codigo)] = linhaRetornoProcessada.Id

            niveisParaGruposFilhos = [bloco for bloco in estruturaReferenciaVirtual if bloco.Nivel == 1]
            bufferDeInsercoesFilhas = []
            for ccProcessado in centrosCustoDeDestinoProcessados:
                for grupoFilhoProcessado in niveisParaGruposFilhos:
                    nomeFormatadoPai, nomeFormatadoFilho = transformarNomeParaAlvo(grupoFilhoProcessado.Nome_Pai), transformarNomeParaAlvo(grupoFilhoProcessado.Nome)
                    identificadorRelativoPai = mapaRelacionalDeIdsCriados.get((nomeFormatadoPai, ccProcessado.Codigo))
                    if identificadorRelativoPai: 
                        bufferDeInsercoesFilhas.append({"Nome": nomeFormatadoFilho, "Id_Pai": identificadorRelativoPai, "Raiz_Centro_Custo_Codigo": ccProcessado.Codigo, "Raiz_Centro_Custo_Nome": ccProcessado.Nome, "Raiz_Centro_Custo_Tipo": tipoCentroCustoDestino, "Nome_Pai": nomeFormatadoPai })

            if bufferDeInsercoesFilhas:
                statementSqlFilhos = text('INSERT INTO "Dre_Schema"."Tb_CTL_Dre_Hierarquia" ("Nome", "Id_Pai", "Raiz_Centro_Custo_Codigo", "Raiz_Centro_Custo_Nome", "Raiz_Centro_Custo_Tipo") VALUES (:Nome, :Id_Pai, :Raiz_Centro_Custo_Codigo, :Raiz_Centro_Custo_Nome, :Raiz_Centro_Custo_Tipo) RETURNING "Id", "Nome", "Raiz_Centro_Custo_Codigo"')
                for itemIterado in bufferDeInsercoesFilhas:
                    linhaRetornoProcessada = sessao.execute(statementSqlFilhos, itemIterado).fetchone()
                    mapaRelacionalDeIdsCriados[(linhaRetornoProcessada.Nome, linhaRetornoProcessada.Raiz_Centro_Custo_Codigo)] = linhaRetornoProcessada.Id

            sqlPuxarContasDeOrigem = text('SELECT DISTINCT h."Nome" as "Nome_Grupo", v."Conta_Contabil" FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" v JOIN "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h ON v."Id_Hierarquia" = h."Id" WHERE h."Raiz_Centro_Custo_Tipo" = :orig')
            bufferContasVincular = []
            for linhaConsulta in sessao.execute(sqlPuxarContasDeOrigem, {"orig": tipoCentroCustoOrigem}).fetchall():
                nomeBaseDoGrupo = transformarNomeParaAlvo(linhaConsulta.Nome_Grupo)
                for ccProcessado in centrosCustoDeDestinoProcessados:
                    identificadorEstrutura = mapaRelacionalDeIdsCriados.get((nomeBaseDoGrupo, ccProcessado.Codigo))
                    if identificadorEstrutura: 
                        bufferContasVincular.append({"Conta_Contabil": str(linhaConsulta.Conta_Contabil), "Id_Hierarquia": identificadorEstrutura, "Chave_Conta_Tipo_CC": f"{linhaConsulta.Conta_Contabil}{tipoCentroCustoDestino}", "Chave_Conta_Codigo_CC": f"{linhaConsulta.Conta_Contabil}{ccProcessado.Codigo}"})

            if bufferContasVincular:
                sessao.execute(text('INSERT INTO "Dre_Schema"."Tb_CTL_Dre_Conta_Vinculo" ("Conta_Contabil", "Id_Hierarquia", "Chave_Conta_Tipo_CC", "Chave_Conta_Codigo_CC") VALUES (:Conta_Contabil, :Id_Hierarquia, :Chave_Conta_Tipo_CC, :Chave_Conta_Codigo_CC) ON CONFLICT ("Chave_Conta_Codigo_CC") DO UPDATE SET "Id_Hierarquia" = EXCLUDED."Id_Hierarquia"'), bufferContasVincular)

            sqlPuxarPersonalizaveis = text('SELECT DISTINCT h."Nome" as "Nome_Grupo", p."Conta_Contabil", p."Nome_Personalizado" FROM "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" p JOIN "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h ON p."Id_Hierarquia" = h."Id" WHERE h."Raiz_Centro_Custo_Tipo" = :orig')
            bufferPessoalDeInsercao = []
            for linhaConsulta in sessao.execute(sqlPuxarPersonalizaveis, {"orig": tipoCentroCustoOrigem}).fetchall():
                nomeBaseDoGrupo = transformarNomeParaAlvo(linhaConsulta.Nome_Grupo)
                for ccProcessado in centrosCustoDeDestinoProcessados:
                    identificadorEstrutura = mapaRelacionalDeIdsCriados.get((nomeBaseDoGrupo, ccProcessado.Codigo))
                    if identificadorEstrutura: 
                        bufferPessoalDeInsercao.append({"Conta_Contabil": str(linhaConsulta.Conta_Contabil), "Nome_Personalizado": linhaConsulta.Nome_Personalizado, "Id_Hierarquia": identificadorEstrutura})

            if bufferPessoalDeInsercao:
                sessao.execute(text('INSERT INTO "Dre_Schema"."Tb_CTL_Dre_Conta_Personalizada" ("Conta_Contabil", "Nome_Personalizado", "Id_Hierarquia") VALUES (:Conta_Contabil, :Nome_Personalizado, :Id_Hierarquia) ON CONFLICT ("Conta_Contabil", "Id_Hierarquia") DO UPDATE SET "Nome_Personalizado" = EXCLUDED."Nome_Personalizado"'), bufferPessoalDeInsercao)

            sqlOrdemParaOBlueprint = text('SELECT h."Nome", p."Nome" as "Nome_Pai", MIN(o.ordem) as "Ordem_Padrao" FROM "Dre_Schema"."Tb_CTL_Dre_Ordenamento" o JOIN "Dre_Schema"."Tb_CTL_Dre_Hierarquia" h ON o.id_referencia = CAST(h."Id" AS TEXT) LEFT JOIN "Dre_Schema"."Tb_CTL_Dre_Hierarquia" p ON h."Id_Pai" = p."Id" WHERE o.tipo_no = \'subgrupo\' AND h."Raiz_Centro_Custo_Tipo" = :orig GROUP BY h."Nome", p."Nome"')
            mapaAnaliticoDeOrdens = {(transformarNomeParaAlvo(linhaRetorno.Nome), transformarNomeParaAlvo(linhaRetorno.Nome_Pai)): linhaRetorno.Ordem_Padrao for linhaRetorno in sessao.execute(sqlOrdemParaOBlueprint, {"orig": tipoCentroCustoOrigem}).fetchall()}

            bufferFinalDeOrdenamento = []
            for (nomeDoSubgrupoMapeado, identificadorCusto), numeroIdNovoCriado in mapaRelacionalDeIdsCriados.items():
                identificadorVerificacaoRaiz = nomeDoSubgrupoMapeado in rotulosDeGruposRaizes
                if identificadorVerificacaoRaiz: 
                    contextoTemporario, profundidade, sequenciaOrdinal = f"cc_{identificadorCusto}", 2, mapaAnaliticoDeOrdens.get((nomeDoSubgrupoMapeado, None), 999)
                else:
                    registroEncontradoFilho = next((item for item in bufferDeInsercoesFilhas if item['Nome'] == nomeDoSubgrupoMapeado and item['Raiz_Centro_Custo_Codigo'] == identificadorCusto), None)
                    if registroEncontradoFilho: 
                        contextoTemporario, profundidade, sequenciaOrdinal = f"sg_{registroEncontradoFilho['Id_Pai']}", 3, mapaAnaliticoDeOrdens.get((nomeDoSubgrupoMapeado, registroEncontradoFilho['Nome_Pai']), 999)
                    else: 
                        continue
                bufferFinalDeOrdenamento.append(CtlDreOrdenamento(tipo_no='subgrupo', id_referencia=str(numeroIdNovoCriado), contexto_pai=contextoTemporario, ordem=sequenciaOrdinal, nivel_profundidade=profundidade))

            if bufferFinalDeOrdenamento: 
                sessao.bulk_save_objects(bufferFinalDeOrdenamento)
            sessao.commit()
            return {"success": True, "msg": f"Replicação completa concluída."}, 200
        except Exception as excecao:
            sessao.rollback()
            return {"error": str(excecao)}, 500
        finally:
            sessao.close()