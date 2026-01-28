import datetime
import calendar
import hashlib
from sqlalchemy import text
from Models.POSTGRESS.Ajustes import AjustesRazao, AjustesLog, AjustesIntergrupoLog
from Utils.Hash_Utils import gerar_hash
from Utils.Common import parse_bool
# Importando o Logger
from Utils.Logger import RegistrarLog 

class AjustesManuaisService:
    def __init__(self, session_db):
        # Guardamos a sessão para usar nos métodos
        self.session = session_db

    # --- HELPERS INTERNOS (Métodos auxiliares) ---

    def _RegistrarLog(self, ajuste_antigo, dados_novos, usuario):
        """
        Registra logs de edição comparando valor antigo vs novo.
        Se nada mudou, vida que segue. Se mudou, dedura no banco.
        """
        campos_mapeados = {
            'origem': 'Origem', 'Conta': 'Conta', 'Titulo_Conta': 'Titulo_Conta',
            'Numero': 'Numero', 'Descricao': 'Descricao', 'Contra_Partida': 'Contra_Partida',
            'Filial': 'Filial', 'Centro de Custo': 'Centro_Custo', 'Item': 'Item',
            'Cod_Cl_Valor': 'Cod_Cl_Valor', 'Debito': 'Debito', 'Credito': 'Credito',
            'NaoOperacional': 'Is_Nao_Operacional', 'Exibir_Saldo': 'Exibir_Saldo',
            'Data': 'Data', 'Invalido': 'Invalido'
        }
        
        for json_key, model_attr in campos_mapeados.items():
            # Pegando os valores crus pra não ter erro de interpretação
            valor_novo_raw = dados_novos.get(json_key)
            valor_antigo_raw = getattr(ajuste_antigo, model_attr)

            val_antigo = str(valor_antigo_raw) if valor_antigo_raw is not None else ''
            val_novo = str(valor_novo_raw) if valor_novo_raw is not None else ''
            
            # Formata Data pra ficar bonitinho na comparação
            if model_attr == 'Data' and valor_antigo_raw:
                val_antigo = valor_antigo_raw.strftime('%Y-%m-%d')
                if val_novo and 'T' in val_novo: val_novo = val_novo.split('T')[0]
            
            # Compara floats com tolerância (pra evitar aquele 0.00000001 de diferença)
            if model_attr in ['Debito', 'Credito']:
                try:
                    f_antigo = float(valor_antigo_raw or 0)
                    f_novo = float(valor_novo_raw or 0)
                    if abs(f_antigo - f_novo) < 0.001: continue
                    val_antigo, val_novo = str(f_antigo), str(f_novo)
                except: pass
            
            # Normaliza booleanos para Sim/Não
            if model_attr in ['Is_Nao_Operacional', 'Exibir_Saldo', 'Invalido']:
                val_antigo = 'Sim' if parse_bool(valor_antigo_raw) else 'Não'
                val_novo = 'Sim' if parse_bool(valor_novo_raw) else 'Não'

            # Se for diferente, anota no caderninho (Log)
            if val_antigo != val_novo:
                novo_log = AjustesLog(
                    Id_Ajuste=ajuste_antigo.Id, Campo_Alterado=model_attr, 
                    Valor_Antigo=val_antigo, Valor_Novo=val_novo, 
                    Usuario_Acao=usuario, Data_Acao=datetime.datetime.now(), 
                    Tipo_Acao='EDICAO'
                )
                self.session.add(novo_log)

    def _GerarHashIntergrupo(self, row):
        """
        Gera um ID único (MD5) para linhas de intergrupo.
        Usa valores de débito/crédito na chave pra garantir unicidade.
        """
        def Clean(val):
            # Limpa o valor pra string, lidando com Nones
            if val is None: return 'None'
            s = str(val).strip()
            return 'None' if s == '' or s.lower() == 'none' else s

        campos = [
            row.get('Conta'), row.get('Data'), row.get('Descricao'),
            str(row.get('Debito') or 0.0), str(row.get('Credito') or 0.0),
            row.get('Filial'), row.get('Centro_Custo') or row.get('Centro de Custo'),
            row.get('Origem') 
        ]
        
        lista_limpa = []
        for item in campos:
            val = item
            if isinstance(item, (datetime.date, datetime.datetime)):
                val = item.strftime('%Y-%m-%d')
            lista_limpa.append(Clean(val))

        raw_str = "".join(lista_limpa)
        return hashlib.md5(raw_str.encode('utf-8')).hexdigest()

    # --- MÉTODOS PRINCIPAIS (Ação real) ---

    def ObterDadosGrid(self):
        """
        O Grande Chefão.
        1. Pega tudo do ERP (View).
        2. Pega todos os ajustes do banco.
        3. Cria ajustes automáticos pro item 10190 se precisarem existir.
        4. Mistura tudo numa lista só pro front-end ser feliz.
        """
        RegistrarLog("Iniciando ObterDadosGrid (Carga do Razão + Ajustes)", "SERVICE")
        
        # 1. Carrega dados da View (Razão Original)
        # Nota: Mantido o LIMIT 10M, que é praticamente 'tudo', mas previne travar o servidor se tiver infinito.
        q_view = text('SELECT * FROM "Dre_Schema"."Razao_Dados_Consolidado" LIMIT 10000000') 
        res_view = self.session.execute(q_view)
        rows_view = [dict(row._mapping) for row in res_view]
        
        RegistrarLog(f"Dados da View Carregados. Linhas: {len(rows_view)}", "DEBUG")

        # [REMOVIDO] Bloco de Debug que contava linhas (Farma, Intec, etc). 
        # Era código morto gastando CPU à toa. Tchau, brigado.

        # 2. Carrega TODOS os Ajustes Existentes
        ajustes = self.session.query(AjustesRazao).all()
        # Mapeia por Hash pra busca ficar O(1) e voar baixo
        mapa_existentes = {aj.Hash_Linha_Original: aj for aj in ajustes}
        
        # 3. Regra Automática: Item 10190
        # Se achar esse item na view e não tiver ajuste, cria um automático
        novos_ajustes_auto = []
        for row in rows_view:
            if str(row.get('Item')).strip() == '10190':
                h = gerar_hash(row)
                
                if h not in mapa_existentes:
                    now = datetime.datetime.now()
                    novo_ajuste = AjustesRazao(
                        Hash_Linha_Original=h, Tipo_Operacao='NO-OPER_AUTO', Status='Aprovado',
                        Origem=row.get('origem'), Conta=row.get('Conta'), Titulo_Conta=row.get('Título Conta'),
                        Data=row.get('Data'), Numero=row.get('Numero'), Descricao=row.get('Descricao'),
                        Contra_Partida=row.get('Contra Partida - Credito'), 
                        Filial=str(row.get('Filial')) if row.get('Filial') else None,
                        Centro_Custo=str(row.get('Centro de Custo')) if row.get('Centro de Custo') else None,
                        Item=str(row.get('Item')), Cod_Cl_Valor=str(row.get('Cod Cl. Valor')) if row.get('Cod Cl. Valor') else None,
                        Debito=float(row.get('Debito') or 0), Credito=float(row.get('Credito') or 0),
                        Is_Nao_Operacional=True, Exibir_Saldo=True, Invalido=False,
                        Criado_Por='SISTEMA_AUTO', Data_Criacao=now, Aprovado_Por='Sistema (Auto 10190)', Data_Aprovacao=now
                    )
                    novos_ajustes_auto.append(novo_ajuste)
                    mapa_existentes[h] = novo_ajuste

        # Salva em lote pra não matar o banco de requisições
        if novos_ajustes_auto:
            self.session.bulk_save_objects(novos_ajustes_auto)
            self.session.commit()
            ajustes = self.session.query(AjustesRazao).all() # Reload para garantir IDs frescos
            RegistrarLog(f"Gerados {len(novos_ajustes_auto)} ajustes automáticos para Item 10190.", "INFO")
        
        # 4. Segregação: Quem é edição e quem é inclusão pura?
        mapa_edicao = {}
        lista_adicionais = []
        for aj in ajustes:
            if aj.Tipo_Operacao in ['EDICAO', 'NO-OPER_AUTO']:
                if aj.Hash_Linha_Original: mapa_edicao[aj.Hash_Linha_Original] = aj
            elif aj.Tipo_Operacao in ['INCLUSAO', 'INTERGRUPO_AUTO']:
                lista_adicionais.append(aj)

        # 5. Construção Final do Retorno
        dados_finais = []

        def MontarLinha(base, ajuste=None, is_inclusao=False):
            # Função interna pra padronizar o dicionário de saída
            row = base.copy()
            row['Exibir_Saldo'] = True 
            if ajuste:  # Se tiver ajuste (edição ou inclusão), sobrescreve os campos abaixo
                row.update({
                    'origem': ajuste.Origem, 'Conta': ajuste.Conta, 'Título Conta': ajuste.Titulo_Conta,
                    'Data': ajuste.Data.strftime('%Y-%m-%d') if ajuste.Data else None,
                    'Numero': ajuste.Numero, 'Descricao': ajuste.Descricao, 'Contra Partida - Credito': ajuste.Contra_Partida, 
                    'Filial': ajuste.Filial, 'Centro de Custo': ajuste.Centro_Custo, 'Item': ajuste.Item,
                    'Cod Cl. Valor': ajuste.Cod_Cl_Valor, 'Debito': ajuste.Debito, 'Credito': ajuste.Credito, 
                    'NaoOperacional': ajuste.Is_Nao_Operacional, 'Exibir_Saldo': ajuste.Exibir_Saldo, 
                    'Invalido': ajuste.Invalido, 'Status_Ajuste': ajuste.Status, 
                    'Ajuste_ID': ajuste.Id, 'Criado_Por': ajuste.Criado_Por 
                })
                if is_inclusao:
                    prefixo = "AUTO_" if ajuste.Tipo_Operacao == 'INTERGRUPO_AUTO' else "NEW_"
                    row['Hash_ID'] = f"{prefixo}{ajuste.Id}"
                    row['Tipo_Linha'] = 'Inclusao'
                
            if row.get('Exibir_Saldo'):
                row['Saldo'] = (float(row.get('Debito') or 0) - float(row.get('Credito') or 0))
            else:
                row['Saldo'] = 0.0
            return row

        # Processa linhas originais (com ou sem edição)
        for row in rows_view:
            h = gerar_hash(row)
            ajuste = mapa_edicao.get(h)
            linha = MontarLinha(row, ajuste, is_inclusao=False)
            linha['Hash_ID'] = h
            linha['Tipo_Linha'] = 'Original'
            if not ajuste: linha['Status_Ajuste'] = 'Original'
            dados_finais.append(linha)

        # Adiciona as linhas puramente novas (inclusões manuais ou intergrupo)
        for adic in lista_adicionais:
            dados_finais.append(MontarLinha({}, adic, is_inclusao=True))
        
        RegistrarLog(f"Grid montado com sucesso. Total de linhas enviadas: {len(dados_finais)}", "SERVICE")
        return dados_finais

    def SalvarAjuste(self, payload, usuario):
        """
        Recebe o payload do front e salva.
        Se já existe, atualiza. Se não, cria. Simples assim.
        """
        RegistrarLog(f"Iniciando SalvarAjuste. Usuario: {usuario}", "SERVICE")
        
        d = payload['Dados']
        hash_id = payload.get('Hash_ID')
        ajuste_id = payload.get('Ajuste_ID')
        
        ajuste = None
        is_novo = False
        
        # Tenta achar pelo ID direto
        if ajuste_id:
            ajuste = self.session.query(AjustesRazao).get(ajuste_id)
        
        # Se não achou e é edição, tenta pelo Hash da linha original
        if not ajuste and payload['Tipo_Operacao'] == 'EDICAO':
            ajuste = self.session.query(AjustesRazao).filter_by(Hash_Linha_Original=hash_id).first()
        
        # Se ainda não achou, é novo mesmo
        if not ajuste:
            ajuste = AjustesRazao()
            is_novo = True
            ajuste.Criado_Por = usuario
            ajuste.Data_Criacao = datetime.datetime.now()
            self.session.add(ajuste)
        else:
            # Se já existe, loga o que mudou antes de sobrescrever
            self._RegistrarLog(ajuste, d, usuario)

        # Atualiza os campos
        ajuste.Tipo_Operacao = payload['Tipo_Operacao']
        ajuste.Hash_Linha_Original = hash_id
        ajuste.Status = 'Pendente' # Toda alteração volta pra pendente
        
        ajuste.Origem = d.get('origem')
        ajuste.Conta = d.get('Conta')
        ajuste.Titulo_Conta = d.get('Titulo_Conta')
        if d.get('Data'): ajuste.Data = datetime.datetime.strptime(d['Data'], '%Y-%m-%d')
        ajuste.Numero = d.get('Numero')
        ajuste.Descricao = d.get('Descricao')
        ajuste.Contra_Partida = d.get('Contra_Partida')
        ajuste.Filial = d.get('Filial')
        ajuste.Centro_Custo = d.get('Centro de Custo')
        ajuste.Item = d.get('Item')
        ajuste.Cod_Cl_Valor = d.get('Cod_Cl_Valor')
        ajuste.Debito = float(d.get('Debito') or 0)
        ajuste.Credito = float(d.get('Credito') or 0)
        
        ajuste.Invalido = parse_bool(d.get('Invalido'))
        ajuste.Is_Nao_Operacional = parse_bool(d.get('NaoOperacional'))
        ajuste.Exibir_Saldo = parse_bool(d.get('Exibir_Saldo'))
        
        self.session.flush() # Garante que o ID foi gerado se for novo

        if is_novo:
            log = AjustesLog(Id_Ajuste=ajuste.Id, Campo_Alterado='TODOS', Valor_Antigo='-', 
                             Valor_Novo='CRIADO', Usuario_Acao=usuario, Data_Acao=datetime.datetime.now(), Tipo_Acao='CRIACAO')
            self.session.add(log)
        
        self.session.commit()
        RegistrarLog(f"Ajuste salvo com sucesso. ID: {ajuste.Id}, Operacao: {payload['Tipo_Operacao']}", "INFO")
        return ajuste.Id

    def AprovarAjuste(self, ajuste_id, acao, usuario):
        """
        Carimba o passaporte do ajuste: Aprovado ou Reprovado.
        """
        RegistrarLog(f"Processando Aprovação. ID: {ajuste_id}, Acao: {acao}, User: {usuario}", "SERVICE")
        
        ajuste = self.session.query(AjustesRazao).get(ajuste_id)
        if ajuste:
            novo_status = 'Aprovado' if acao == 'Aprovar' else 'Reprovado'
            log = AjustesLog(Id_Ajuste=ajuste.Id, Campo_Alterado='Status', Valor_Antigo=ajuste.Status, 
                             Valor_Novo=novo_status, Usuario_Acao=usuario, Data_Acao=datetime.datetime.now(), Tipo_Acao='APROVACAO')
            self.session.add(log)
            ajuste.Status = novo_status
            ajuste.Aprovado_Por = usuario
            ajuste.Data_Aprovacao = datetime.datetime.now()
            self.session.commit()
            RegistrarLog(f"Ajuste {ajuste_id} marcado como {novo_status}", "INFO")
        else:
            RegistrarLog(f"Falha ao aprovar: Ajuste {ajuste_id} não encontrado.", "WARNING")

    def ToggleInvalido(self, ajuste_id, acao, usuario):
        """
        Marca como inválido (esconde) ou restaura.
        """
        RegistrarLog(f"Toggle Invalido. ID: {ajuste_id}, Acao: {acao}", "SERVICE")
        
        ajuste = self.session.query(AjustesRazao).get(ajuste_id)
        if not ajuste: 
            RegistrarLog(f"Toggle Invalido falhou: Ajuste {ajuste_id} não existe", "ERROR")
            raise Exception('Ajuste não encontrado')

        novo_estado_invalido = (acao == 'INVALIDAR')
        log = AjustesLog(
            Id_Ajuste=ajuste.Id, Campo_Alterado='Invalido', 
            Valor_Antigo=str(ajuste.Invalido), Valor_Novo=str(novo_estado_invalido),
            Usuario_Acao=usuario, Data_Acao=datetime.datetime.now(),
            Tipo_Acao='INVALIDACAO' if novo_estado_invalido else 'RESTAURACAO'
        )
        self.session.add(log)

        ajuste.Invalido = novo_estado_invalido
        if novo_estado_invalido:
            ajuste.Status = 'Invalido'
        else:
            ajuste.Status = 'Pendente'
        self.session.commit()
        RegistrarLog(f"Status Invalido atualizado para: {novo_estado_invalido}", "INFO")

    def ObterHistorico(self, ajuste_id):
        """
        Retorna a capivara completa do ajuste.
        """
        # Apenas debug leve
        RegistrarLog(f"Buscando histórico para ajuste ID: {ajuste_id}", "DEBUG")
        logs = self.session.query(AjustesLog).filter(AjustesLog.Id_Ajuste == ajuste_id).order_by(AjustesLog.Data_Acao.desc()).all()
        return [{
            'Id_Log': l.Id_Log, 'Campo': l.Campo_Alterado, 'De': l.Valor_Antigo, 'Para': l.Valor_Novo,
            'Usuario': l.Usuario_Acao, 'Data': l.Data_Acao.strftime('%d/%m/%Y %H:%M:%S'), 'Tipo': l.Tipo_Acao
        } for l in logs]

    def GerarIntergrupo(self, ano):
        """
        Executa a lógica complexa de geração de ajustes intergrupo.
        Cruza contas, datas e filiais pra gerar os pares de D/C.
        """
        RegistrarLog(f"Iniciando Rotina GerarIntergrupo. Ano: {ano}", "SYSTEM")
        
        # Configuração hardcoded das contas (regra de negócio)
        config_contas = {
            '60301020290': {'destino': '60301020290B', 'descricao': 'ajuste intergrupo ( fretes Dist.)', 'titulo_origem': 'FRETE DISTRIBUIÇÃO', 'titulo_destino': 'FRETE DISTRIBUIÇÃO'},
            '60301020288': {'destino': '60301020288C', 'descricao': 'ajuste intergrupo ( fretes Aéreo)', 'titulo_origem': 'FRETES AEREO', 'titulo_destino': 'FRETES AEREO'},
            '60101010201': {'destino': '60101010201A', 'descricao': 'VLR. CFE DIARIO AUXILIAR N/ DATA (aéreo)', 'titulo_origem': 'VENDA DE FRETES', 'titulo_destino': 'VENDA DE FRETES'}
        }
        
        logs_retorno = []

        def SalvarLogInterno(mes, conta, origem_erp, valor, tipo, acao, id_orig=None, id_dest=None, hash_val=None):
            # Log técnico específico dessa rotina
            novo_log = AjustesIntergrupoLog(
                Ano=ano, Mes=mes, Conta_Origem=conta, Origem_ERP=origem_erp, 
                Valor_Encontrado_ERP=valor, Tipo_Fluxo=tipo, Id_Ajuste_Origem=id_orig, 
                Id_Ajuste_Destino=id_dest, Acao_Realizada=acao, Hash_Gerado=hash_val, 
                Data_Processamento=datetime.datetime.now()
            )
            self.session.add(novo_log)

        for conta_origem, config in config_contas.items():
            conta_destino = config['destino']
            desc_regra = config['descricao']
            titulo_origem = config['titulo_origem']
            titulo_destino = config['titulo_destino']

            for mes in range(1, 13):
                ultimo_dia = calendar.monthrange(ano, mes)[1]
                data_inicio = datetime.datetime(ano, mes, 1)
                data_fim_busca = datetime.datetime(ano, mes, ultimo_dia, 23, 59, 59)
                data_gravacao = datetime.datetime(ano, mes, ultimo_dia, 0, 0, 0)

                # A. VERIFICAÇÃO RIGOROSA NO ERP
                # Se já tem dado na conta destino no ERP, a gente não mexe.
                qtd_erp = self.session.execute(text("""
                    SELECT COUNT(*) FROM "Dre_Schema"."Razao_Dados_Consolidado"
                    WHERE "Conta" = :conta AND "Data" >= :d_ini AND "Data" <= :d_fim
                """), {'conta': conta_destino, 'd_ini': data_inicio, 'd_fim': data_fim_busca}).scalar()

                if qtd_erp > 0:
                    logs_retorno.append(f"[{conta_origem} | {mes:02d}/{ano}] PULADO: Já consolidado no ERP.")
                    continue

                # B. BUSCA DADOS BRUTOS (Origem)
                rows = self.session.execute(text("""
                    SELECT "origem", "Debito", "Credito", "Item", "Filial", "Centro de Custo"
                    FROM "Dre_Schema"."Razao_Dados_Consolidado"
                    WHERE "Conta" = :conta AND "Data" >= :d_ini AND "Data" <= :d_fim
                    ORDER BY "Data" ASC
                """), {'conta': conta_origem, 'd_ini': data_inicio, 'd_fim': data_fim_busca}).fetchall()

                # C. AGRUPAMENTO (Soma tudo por origem)
                dados_agrupados = {}
                for row in rows:
                    org = str(row.origem) if row.origem else 'SEM_ORIGEM'
                    if org not in dados_agrupados:
                        dados_agrupados[org] = {'deb': 0.0, 'cred': 0.0, 'last_item': 'INTERGRUPO', 'last_filial': '99', 'last_cc': 'SEM_CC'}
                    dados_agrupados[org]['deb'] += float(row.Debito or 0.0)
                    dados_agrupados[org]['cred'] += float(row.Credito or 0.0)
                    if row.Item: dados_agrupados[org]['last_item'] = str(row.Item)
                    if row.Filial: dados_agrupados[org]['last_filial'] = str(row.Filial)
                    cc = getattr(row, 'Centro de Custo', None) or getattr(row, 'Centro_Custo', None)
                    if cc: dados_agrupados[org]['last_cc'] = str(cc)

                if not dados_agrupados: continue

                # D. PROCESSAMENTO (Gera os ajustes)
                for org_atual, valores in dados_agrupados.items():
                    prefixo_log = f"[{conta_origem} | {org_atual} | {mes:02d}/{ano}]"
                    soma_debito_real = round(abs(valores['deb']), 2)
                    soma_credito_real = round(abs(valores['cred']), 2)
                    item_real = valores['last_item']
                    filial_ref = valores['last_filial']
                    cc_ref = valores['last_cc']

                    # --- FLUXO DE DÉBITOS ---
                    if soma_debito_real > 0.00:
                        # Busca se já criamos esse ajuste antes
                        ajuste_deb_origem = self.session.query(AjustesRazao).filter(
                            AjustesRazao.Conta == conta_origem, AjustesRazao.Data == data_gravacao,
                            AjustesRazao.Origem == org_atual, AjustesRazao.Tipo_Operacao == 'INTERGRUPO_AUTO',
                            AjustesRazao.Credito > 0, AjustesRazao.Invalido == False
                        ).first()

                        # Parâmetros pra gerar o hash e garantir unicidade
                        row_origem_params = {'Conta': conta_origem, 'Data': data_gravacao, 'Descricao': desc_regra, 'Debito': 0.0, 'Credito': soma_debito_real, 'Filial': filial_ref, 'Centro_Custo': cc_ref, 'Origem': org_atual}
                        hash_novo_origem = self._GerarHashIntergrupo(row_origem_params)

                        row_destino_params = {'Conta': conta_destino, 'Data': data_gravacao, 'Descricao': desc_regra, 'Debito': soma_debito_real, 'Credito': 0.0, 'Filial': filial_ref, 'Centro_Custo': cc_ref, 'Origem': org_atual}
                        hash_novo_destino = self._GerarHashIntergrupo(row_destino_params)

                        if ajuste_deb_origem:
                            # Se já existe e mudou valor ou item, atualiza
                            if abs(ajuste_deb_origem.Credito - soma_debito_real) > 0.01 or ajuste_deb_origem.Item != item_real:
                                ajuste_deb_origem.Credito = soma_debito_real
                                ajuste_deb_origem.Item = item_real
                                ajuste_deb_origem.Hash_Linha_Original = hash_novo_origem
                                
                                # Busca o par dele (destino)
                                ajuste_deb_destino = self.session.query(AjustesRazao).filter(
                                    AjustesRazao.Conta == conta_destino, AjustesRazao.Data == data_gravacao,
                                    AjustesRazao.Origem == org_atual, AjustesRazao.Tipo_Operacao == 'INTERGRUPO_AUTO',
                                    AjustesRazao.Debito > 0, AjustesRazao.Invalido == False
                                ).first()
                                
                                if ajuste_deb_destino:
                                    ajuste_deb_destino.Debito = soma_debito_real
                                    ajuste_deb_destino.Item = item_real
                                    ajuste_deb_destino.Hash_Linha_Original = hash_novo_destino
                                
                                SalvarLogInterno(mes, conta_origem, org_atual, soma_debito_real, 'DEBITO', 'ATUALIZACAO', id_orig=ajuste_deb_origem.Id, id_dest=ajuste_deb_destino.Id if ajuste_deb_destino else None, hash_val=hash_novo_origem)
                                logs_retorno.append(f"{prefixo_log} [DEBITO] ATUALIZADO: {soma_debito_real}")
                        else:
                            # Se não existe, cria o par (Origem e Destino)
                            l1 = AjustesRazao(
                                Conta=conta_origem, Titulo_Conta=titulo_origem, Data=data_gravacao, Descricao=desc_regra,
                                Debito=0.0, Credito=soma_debito_real, Filial=filial_ref, Centro_Custo=cc_ref, Item=item_real, 
                                Hash_Linha_Original=hash_novo_origem, Tipo_Operacao='INTERGRUPO_AUTO', Origem=org_atual, 
                                Status='Aprovado', Invalido=False, Criado_Por='SISTEMA_AUTO', Aprovado_Por='SISTEMA_AUTO', 
                                Data_Aprovacao=datetime.datetime.now(), Is_Nao_Operacional=False, Exibir_Saldo=True
                            )
                            l2 = AjustesRazao(
                                Conta=conta_destino, Titulo_Conta=titulo_destino, Data=data_gravacao, Descricao=desc_regra,
                                Debito=soma_debito_real, Credito=0.0, Filial=filial_ref, Centro_Custo=cc_ref, Item=item_real, 
                                Hash_Linha_Original=hash_novo_destino, Tipo_Operacao='INTERGRUPO_AUTO', Origem=org_atual, 
                                Status='Aprovado', Invalido=False, Criado_Por='SISTEMA_AUTO', Aprovado_Por='SISTEMA_AUTO', 
                                Data_Aprovacao=datetime.datetime.now(), Is_Nao_Operacional=False, Exibir_Saldo=True
                            )
                            self.session.add(l1); self.session.add(l2)
                            self.session.flush()
                            SalvarLogInterno(mes, conta_origem, org_atual, soma_debito_real, 'DEBITO', 'CRIACAO', id_orig=l1.Id, id_dest=l2.Id, hash_val=hash_novo_origem)
                            logs_retorno.append(f"{prefixo_log} [DEBITO] CRIADO: {soma_debito_real}")

                    # --- FLUXO DE CRÉDITOS ---
                    if soma_credito_real > 0.00:
                        ajuste_cred_origem = self.session.query(AjustesRazao).filter(
                            AjustesRazao.Conta == conta_origem, AjustesRazao.Data == data_gravacao,
                            AjustesRazao.Origem == org_atual, AjustesRazao.Tipo_Operacao == 'INTERGRUPO_AUTO',
                            AjustesRazao.Debito > 0, AjustesRazao.Invalido == False
                        ).first()

                        row_origem_cred_params = {'Conta': conta_origem, 'Data': data_gravacao, 'Descricao': desc_regra, 'Debito': soma_credito_real, 'Credito': 0.0, 'Filial': filial_ref, 'Centro_Custo': cc_ref, 'Origem': org_atual}
                        hash_novo_origem_cred = self._GerarHashIntergrupo(row_origem_cred_params)

                        row_destino_cred_params = {'Conta': conta_destino, 'Data': data_gravacao, 'Descricao': desc_regra, 'Debito': 0.0, 'Credito': soma_credito_real, 'Filial': filial_ref, 'Centro_Custo': cc_ref, 'Origem': org_atual}
                        hash_novo_destino_cred = self._GerarHashIntergrupo(row_destino_cred_params)

                        if ajuste_cred_origem:
                            if abs(ajuste_cred_origem.Debito - soma_credito_real) > 0.01 or ajuste_cred_origem.Item != item_real:
                                ajuste_cred_origem.Debito = soma_credito_real
                                ajuste_cred_origem.Item = item_real
                                ajuste_cred_origem.Hash_Linha_Original = hash_novo_origem_cred
                                
                                ajuste_cred_destino = self.session.query(AjustesRazao).filter(
                                    AjustesRazao.Conta == conta_destino, AjustesRazao.Data == data_gravacao,
                                    AjustesRazao.Origem == org_atual, AjustesRazao.Tipo_Operacao == 'INTERGRUPO_AUTO',
                                    AjustesRazao.Credito > 0, AjustesRazao.Invalido == False
                                ).first()
                                
                                if ajuste_cred_destino:
                                    ajuste_cred_destino.Credito = soma_credito_real
                                    ajuste_cred_destino.Item = item_real
                                    ajuste_cred_destino.Hash_Linha_Original = hash_novo_destino_cred
                                
                                SalvarLogInterno(mes, conta_origem, org_atual, soma_credito_real, 'CREDITO', 'ATUALIZACAO', id_orig=ajuste_cred_origem.Id, id_dest=ajuste_cred_destino.Id if ajuste_cred_destino else None, hash_val=hash_novo_origem_cred)
                                logs_retorno.append(f"{prefixo_log} [CREDITO] ATUALIZADO: {soma_credito_real}")
                        else:
                            l3 = AjustesRazao(
                                Conta=conta_origem, Titulo_Conta=titulo_origem, Data=data_gravacao, Descricao=desc_regra,
                                Debito=soma_credito_real, Credito=0.0, Filial=filial_ref, Centro_Custo=cc_ref, Item=item_real, 
                                Hash_Linha_Original=hash_novo_origem_cred, Tipo_Operacao='INTERGRUPO_AUTO', Origem=org_atual, 
                                Status='Aprovado', Invalido=False, Criado_Por='SISTEMA_AUTO', Aprovado_Por='SISTEMA_AUTO', 
                                Data_Aprovacao=datetime.datetime.now(), Is_Nao_Operacional=False, Exibir_Saldo=True
                            )
                            l4 = AjustesRazao(
                                Conta=conta_destino, Titulo_Conta=titulo_destino, Data=data_gravacao, Descricao=desc_regra,
                                Debito=0.0, Credito=soma_credito_real, Filial=filial_ref, Centro_Custo=cc_ref, Item=item_real, 
                                Hash_Linha_Original=hash_novo_destino_cred, Tipo_Operacao='INTERGRUPO_AUTO', Origem=org_atual, 
                                Status='Aprovado', Invalido=False, Criado_Por='SISTEMA_AUTO', Aprovado_Por='SISTEMA_AUTO', 
                                Data_Aprovacao=datetime.datetime.now(), Is_Nao_Operacional=False, Exibir_Saldo=True
                            )
                            self.session.add(l3); self.session.add(l4)
                            self.session.flush()
                            SalvarLogInterno(mes, conta_origem, org_atual, soma_credito_real, 'CREDITO', 'CRIACAO', id_orig=l3.Id, id_dest=l4.Id, hash_val=hash_novo_origem_cred)
                            logs_retorno.append(f"{prefixo_log} [CREDITO] CRIADO: {soma_credito_real}")

        self.session.commit()
        RegistrarLog(f"Rotina Intergrupo finalizada com sucesso. Logs gerados: {len(logs_retorno)}", "SYSTEM")
        return logs_retorno