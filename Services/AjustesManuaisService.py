import datetime
import calendar
from dateutil import parser
import hashlib
import os
import pandas as pd
from sqlalchemy import text
from Models.POSTGRESS.Ajustes import AjustesRazao, AjustesLog
from Settings import BaseConfig
from Utils.ExcelUtils import ler_qvd_para_dataframe
from Utils.Hash_Utils import gerar_hash
from Utils.Common import parse_bool
from Utils.Logger import RegistrarLog 
from Db.Connections import GetPostgresEngine

class AjustesManuaisService:
    def __init__(self, session_db):
        self.session = session_db
        self.engine = GetPostgresEngine()
        self.schema = "Dre_Schema"

    # --- HELPERS INTERNOS ---

    def _RegistrarLog(self, ajuste_antigo, dados_novos, usuario):
        """
        Gera logs comparando o objeto do banco (ajuste_antigo) com o JSON (dados_novos)
        """
        # Mapeamento: Chave no JSON do Front -> Atributo na Model do Banco
        campos_mapeados = {
            'origem': 'Origem', 
            'Conta': 'Conta', 
            'Titulo_Conta': 'Titulo_Conta', # Verifica se no JS está Titulo_Conta ou Título Conta
            'Numero': 'Numero', 
            'Descricao': 'Descricao', 
            'Contra_Partida': 'Contra_Partida',
            'Filial': 'Filial', 
            'Centro_Custo': 'Centro_Custo', # No JS deve ser 'Centro_Custo' ou 'Centro de Custo'
            'Item': 'Item',
            'Cod_Cl_Valor': 'Cod_Cl_Valor', 
            'Debito': 'Debito', 
            'Credito': 'Credito',
            'NaoOperacional': 'Is_Nao_Operacional', 
            'Exibir_Saldo': 'Exibir_Saldo',
            'Data': 'Data', 
            'Invalido': 'Invalido'
        }
        
        # Normalização de chaves flexíveis (caso o front mande com espaço ou acento)
        keys_front = dados_novos.keys()
        
        for json_key, model_attr in campos_mapeados.items():
            # Tenta pegar valor exato, se não achar, tenta buscar chaves alternativas comuns
            valor_novo_raw = dados_novos.get(json_key)
            
            # Fallbacks para chaves que costumam dar problema
            if valor_novo_raw is None:
                if json_key == 'Titulo_Conta': 
                    valor_novo_raw = dados_novos.get('Título Conta')
                elif json_key == 'Centro_Custo': 
                    valor_novo_raw = dados_novos.get('Centro de Custo')
                elif json_key == 'Contra_Partida': 
                    valor_novo_raw = dados_novos.get('Contra Partida - Credito')

            valor_antigo_raw = getattr(ajuste_antigo, model_attr)

            # Tratamento para comparação justa
            val_antigo = str(valor_antigo_raw).strip() if valor_antigo_raw is not None else ''
            val_novo = str(valor_novo_raw).strip() if valor_novo_raw is not None else ''
            
            # Tratamento especial de Data
            if model_attr == 'Data' and valor_antigo_raw:
                val_antigo = valor_antigo_raw.strftime('%Y-%m-%d')
                if val_novo and 'T' in val_novo: val_novo = val_novo.split('T')[0]
                # Tenta converter o novo para formato YYYY-MM-DD se vier 'Mon, 15 Sep...'
                try:
                    if 'GMT' in val_novo or ',' in val_novo:
                        from dateutil import parser
                        dt_temp = parser.parse(val_novo)
                        val_novo = dt_temp.strftime('%Y-%m-%d')
                except: pass
            
            # Tratamento especial de Float (Dinheiro)
            if model_attr in ['Debito', 'Credito']:
                try:
                    f_antigo = float(valor_antigo_raw or 0)
                    f_novo = float(valor_novo_raw or 0)
                    if abs(f_antigo - f_novo) < 0.001: continue
                    val_antigo, val_novo = f"{f_antigo:.2f}", f"{f_novo:.2f}"
                except: pass
            
            # Tratamento Booleano
            if model_attr in ['Is_Nao_Operacional', 'Exibir_Saldo', 'Invalido']:
                val_antigo = 'Sim' if parse_bool(valor_antigo_raw) else 'Não'
                val_novo = 'Sim' if parse_bool(valor_novo_raw) else 'Não'

            if val_antigo != val_novo:
                RegistrarLog(f"Alteração detectada em {model_attr}: '{val_antigo}' -> '{val_novo}'", "DEBUG")
                novo_log = AjustesLog(
                    Id_Ajuste=ajuste_antigo.Id, Campo_Alterado=model_attr, 
                    Valor_Antigo=val_antigo, Valor_Novo=val_novo, 
                    Usuario_Acao=usuario, Data_Acao=datetime.datetime.now(), 
                    Tipo_Acao='EDICAO'
                )
                self.session.add(novo_log)
                
    def _GerarHashIntergrupo(self, row):
        def Clean(val):
            if val is None: return 'None'
            s = str(val).strip()
            return 'None' if s == '' or s.lower() == 'none' else s

        campos = [
            row.get('Conta'), row.get('Data'), row.get('Descricao'),
            str(row.get('Debito') or 0.0), str(row.get('Credito') or 0.0),
            row.get('Filial'), row.get('Centro_Custo') or row.get('Centro de Custo'),
            row.get('Origem') 
        ]
        
        raw_str = "".join([Clean(x) for x in campos])
        return hashlib.md5(raw_str.encode('utf-8')).hexdigest()

    # --- MÉTODOS DE GRID/CRUD ---
    def ObterDadosGrid(self):
        RegistrarLog("Iniciando ObterDadosGrid", "SERVICE")
        
        q_view = text('SELECT * FROM "Dre_Schema"."Razao_Dados_Consolidado" LIMIT 10000000') 
        res_view = self.session.execute(q_view)
        rows_view = [dict(row._mapping) for row in res_view]
        
        ajustes = self.session.query(AjustesRazao).all()
        mapa_existentes = {aj.Hash_Linha_Original: aj for aj in ajustes}
        # Registra ajustes automáticos para itens 10190, se não existirem
        novos_ajustes_auto = []
        for row in rows_view:
            if str(row.get('Item')).strip() == '10190':
                h = gerar_hash(row)
                if h not in mapa_existentes:
                    now = datetime.datetime.now()
                    novo = AjustesRazao(
                        Hash_Linha_Original=h, Tipo_Operacao='NO-OPER_AUTO', Status='Aprovado',
                        Origem=row.get('origem'), Conta=row.get('Conta'), Titulo_Conta=row.get('Título Conta'),
                        Data=row.get('Data'), Numero=row.get('Numero'), Descricao=row.get('Descricao'),
                        Contra_Partida=row.get('Contra Partida - Credito'), 
                        Filial=str(row.get('Filial') or ''), Centro_Custo=str(row.get('Centro de Custo') or ''),
                        Item=str(row.get('Item')), Cod_Cl_Valor=str(row.get('Cod Cl. Valor') or ''),
                        Debito=float(row.get('Debito') or 0), Credito=float(row.get('Credito') or 0),
                        Is_Nao_Operacional=True, Exibir_Saldo=True, Invalido=False,
                        Criado_Por='SISTEMA_AUTO', Data_Criacao=now, Aprovado_Por='Sistema', Data_Aprovacao=now
                    )
                    novos_ajustes_auto.append(novo)
                    mapa_existentes[h] = novo
        
        if novos_ajustes_auto:
            self.session.bulk_save_objects(novos_ajustes_auto)
            self.session.commit()
            ajustes = self.session.query(AjustesRazao).all()

        mapa_edicao = {}
        lista_adicionais = []
        for aj in ajustes:
            if aj.Tipo_Operacao in ['EDICAO', 'NO-OPER_AUTO']:
                if aj.Hash_Linha_Original: mapa_edicao[aj.Hash_Linha_Original] = aj
            elif aj.Tipo_Operacao in ['INCLUSAO', 'INTERGRUPO_AUTO']:
                lista_adicionais.append(aj)

        dados_finais = []
        
        # Dentro de ObterDadosGrid -> MontarLinha
        def MontarLinha(base, ajuste=None, is_inclusao=False):
            row = base.copy()
            row['Exibir_Saldo'] = True 
            if ajuste:
                row.update({
                    'origem': ajuste.Origem, 
                    'Conta': ajuste.Conta, 
                    'Título Conta': ajuste.Titulo_Conta,  # Alinhado com o JS
                    'Data': ajuste.Data.strftime('%Y-%m-%d') if ajuste.Data else None,
                    'Numero': ajuste.Numero, 
                    'Descricao': ajuste.Descricao, 
                    'Contra Partida - Credito': ajuste.Contra_Partida, # Alinhado com o JS
                    'Filial': ajuste.Filial, 
                    'Centro de Custo': ajuste.Centro_Custo, # Alinhado com o JS
                    'Item': ajuste.Item,
                    'Cod Cl. Valor': ajuste.Cod_Cl_Valor, 
                    'Debito': ajuste.Debito, 
                    'Credito': ajuste.Credito, 
                    'NaoOperacional': ajuste.Is_Nao_Operacional, 
                    'Status_Ajuste': ajuste.Status, 
                    'Ajuste_ID': ajuste.Id
                })
                if is_inclusao:
                    prefixo = "AUTO_" if 'INTERGRUPO' in str(ajuste.Tipo_Operacao) else "NEW_"
                    row['Hash_ID'] = f"{prefixo}{ajuste.Id}"
                    row['Tipo_Linha'] = 'Inclusao'
            
            row['Saldo'] = (float(row.get('Debito') or 0) - float(row.get('Credito') or 0)) if row.get('Exibir_Saldo') else 0.0
            return row

        for row in rows_view: # Percorre os dados da view, e adiciona ajustes de edição se existirem
            h = gerar_hash(row)
            aj = mapa_edicao.get(h)
            linha = MontarLinha(row, aj, is_inclusao=False)
            linha['Hash_ID'] = h
            linha['Tipo_Linha'] = 'Original'
            if not aj: linha['Status_Ajuste'] = 'Original'
            dados_finais.append(linha)

        for adic in lista_adicionais: # Adiciona ajustes automáticos como linhas adicionais
            dados_finais.append(MontarLinha({}, adic, is_inclusao=True))
        
        return dados_finais

    def CriarAjusteManual(self, payload, usuario):
        """
        Cria um novo ajuste do zero (INCLUSAO).
        Gera um Hash novo baseado no conteúdo para garantir unicidade no banco.
        """
        RegistrarLog(f"Iniciando CriarAjusteManual. Usuario: {usuario}", "SERVICE")
        
        d = payload['Dados']
        now = datetime.datetime.now()

        # Mapeamento e Tratamento de Data
        data_ajuste = now
        data_raw = d.get('Data')
        if data_raw:
            try:
                if 'T' in str(data_raw): 
                    data_ajuste = datetime.datetime.strptime(data_raw.split('T')[0], '%Y-%m-%d')
                else:
                    data_ajuste = parser.parse(str(data_raw))
            except:
                pass # Mantém o now se falhar

        # Prepara o objeto
        ajuste = AjustesRazao()
        ajuste.Criado_Por = usuario
        ajuste.Data_Criacao = now
        ajuste.Tipo_Operacao = 'INCLUSAO' # Forçado
        ajuste.Status = 'Pendente'
        
        # Gera um Hash único para este registro novo (Timestamp + Usuario + Descricao)
        # Isso é necessário pois o banco ou o Grid esperam um Hash único
        raw_hash = f"{now.timestamp()}-{usuario}-{d.get('Descricao')}"
        ajuste.Hash_Linha_Original = hashlib.md5(raw_hash.encode('utf-8')).hexdigest()

        # Mapeamento de Campos
        ajuste.Origem = 'MANUAL' # Inclusões manuais geralmente têm essa origem
        ajuste.Data = data_ajuste
        
        if d.get('Conta'): ajuste.Conta = str(d.get('Conta')).strip()
        ajuste.Titulo_Conta = d.get('Titulo_Conta') or d.get('Título Conta')
        ajuste.Centro_Custo = d.get('Centro de Custo') or d.get('Centro_Custo')
        ajuste.Numero = d.get('Numero')
        ajuste.Descricao = d.get('Descricao')
        ajuste.Contra_Partida = d.get('Contra_Partida') or d.get('Contra Partida - Credito')
        ajuste.Filial = d.get('Filial')
        ajuste.Item = d.get('Item')
        ajuste.Cod_Cl_Valor = d.get('Cod_Cl_Valor') or d.get('Cod Cl. Valor')
        
        ajuste.Debito = float(d.get('Debito') or 0)
        ajuste.Credito = float(d.get('Credito') or 0)
        
        ajuste.Invalido = False
        ajuste.Is_Nao_Operacional = parse_bool(d.get('NaoOperacional'))
        ajuste.Exibir_Saldo = True

        self.session.add(ajuste)
        self.session.flush() # Gera o ID
        
        # Log de Criação
        log = AjustesLog(
            Id_Ajuste=ajuste.Id, 
            Campo_Alterado='TODOS', 
            Valor_Antigo='-', 
            Valor_Novo='CRIADO_MANUALMENTE', 
            Usuario_Acao=usuario, 
            Data_Acao=now, 
            Tipo_Acao='INCLUSAO'
        )
        self.session.add(log)
        
        self.session.commit()
        return ajuste.Id
    
    def SalvarAjuste(self, payload, usuario):
        RegistrarLog(f"Iniciando SalvarAjuste. Usuario: {usuario}", "SERVICE")
        
        d = payload.get('Dados', {})
        
        # Identificadores vindos do Front-end
        hash_id = d.get('Hash_ID') or payload.get('Hash_ID')
        ajuste_id = d.get('Ajuste_ID') or payload.get('Ajuste_ID')
        
        ajuste = None
        is_novo = False

        RegistrarLog(f"Payload ID: {ajuste_id} | Hash: {hash_id}", "DEBUG")
        
        # 1. TENTA LOCALIZAR O REGISTRO
        if ajuste_id:
            ajuste = self.session.query(AjustesRazao).get(ajuste_id)
        
        # Só busca por Hash se não for uma inclusão manual nova (Inclusões manuais usam ID)
        if not ajuste and hash_id and not str(hash_id).startswith('NEW_'):
            ajuste = self.session.query(AjustesRazao).filter_by(Hash_Linha_Original=hash_id).first()
        
        # 2. CRIAÇÃO DE NOVO OBJETO (Se não existir no banco)
        if not ajuste:
            ajuste = AjustesRazao()
            is_novo = True
            ajuste.Criado_Por = usuario
            ajuste.Data_Criacao = datetime.datetime.now()
            
            # Trava de Hash: Só grava Hash_Linha_Original se não for uma INCLUSAO manual
            if payload.get('Tipo_Operacao') != 'INCLUSAO':
                ajuste.Hash_Linha_Original = hash_id
            
            self.session.add(ajuste)
        else:
            # Se o ajuste já existia, registra o log de alteração antes de atualizar
            self._RegistrarLog(ajuste, d, usuario)

        # 3. TRAVA LÓGICA DO TIPO DE OPERAÇÃO
        tipo_solicitado = payload.get('Tipo_Operacao', 'EDICAO')
        
        # Se já é INCLUSAO, ou se está sendo criado como tal, mantém. 
        # Não permite que uma INCLUSAO vire EDICAO.
        if ajuste.Tipo_Operacao == 'INCLUSAO' or tipo_solicitado == 'INCLUSAO':
            ajuste.Tipo_Operacao = 'INCLUSAO'
        else:
            ajuste.Tipo_Operacao = 'EDICAO'

        # 4. ATUALIZAÇÃO DOS CAMPOS
        ajuste.Status = 'Pendente'
        ajuste.Origem = d.get('origem', ajuste.Origem)
        
        # Dados da Conta
        if d.get('Conta'): ajuste.Conta = str(d.get('Conta')).strip()
        ajuste.Titulo_Conta = d.get('Titulo_Conta') or d.get('Título Conta')
        ajuste.Centro_Custo = d.get('Centro de Custo') or d.get('Centro_Custo')
        
        # Tratamento de Data
        data_raw = d.get('Data')
        if data_raw:
            try:
                ajuste.Data = parser.parse(str(data_raw))
            except:
                if 'T' in str(data_raw): 
                    ajuste.Data = datetime.datetime.strptime(data_raw.split('T')[0], '%Y-%m-%d')

        # Campos Financeiros e Descritivos
        ajuste.Numero = d.get('Numero')
        ajuste.Descricao = d.get('Descricao')
        ajuste.Contra_Partida = d.get('Contra_Partida') or d.get('Contra Partida - Credito')
        ajuste.Filial = d.get('Filial')
        ajuste.Item = d.get('Item')
        ajuste.Cod_Cl_Valor = d.get('Cod_Cl_Valor') or d.get('Cod Cl. Valor')
        ajuste.Debito = float(d.get('Debito') or 0)
        ajuste.Credito = float(d.get('Credito') or 0)
        
        # Booleans de Controle
        ajuste.Invalido = parse_bool(d.get('Invalido'))
        ajuste.Is_Nao_Operacional = parse_bool(d.get('NaoOperacional'))
        ajuste.Exibir_Saldo = parse_bool(d.get('Exibir_Saldo', True))
        
        self.session.flush()
        
        if is_novo:
            log = AjustesLog(
                Id_Ajuste=ajuste.Id, Campo_Alterado='TODOS', Valor_Antigo='-', 
                Valor_Novo='CRIADO_VIA_SALVAR', Usuario_Acao=usuario, 
                Data_Acao=datetime.datetime.now(), Tipo_Acao='CRIACAO'
            )
            self.session.add(log)
        
        self.session.commit()
        return ajuste.Id
    
    def AprovarAjuste(self, ajuste_id, acao, usuario):
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

    def ToggleInvalido(self, ajuste_id, acao, usuario):
        ajuste = self.session.query(AjustesRazao).get(ajuste_id)
        if not ajuste: raise Exception('Ajuste não encontrado')
        novo_estado_invalido = (acao == 'INVALIDAR')
        log = AjustesLog(
            Id_Ajuste=ajuste.Id, Campo_Alterado='Invalido', 
            Valor_Antigo=str(ajuste.Invalido), Valor_Novo=str(novo_estado_invalido),
            Usuario_Acao=usuario, Data_Acao=datetime.datetime.now(),
            Tipo_Acao='INVALIDACAO' if novo_estado_invalido else 'RESTAURACAO'
        )
        self.session.add(log)
        ajuste.Invalido = novo_estado_invalido
        ajuste.Status = 'Invalido' if novo_estado_invalido else 'Pendente'
        self.session.commit()

    def ObterHistorico(self, ajuste_id):
        logs = self.session.query(AjustesLog).filter(AjustesLog.Id_Ajuste == ajuste_id).order_by(AjustesLog.Data_Acao.desc()).all()
        return [{
            'Id_Log': l.Id_Log, 'Campo': l.Campo_Alterado, 'De': l.Valor_Antigo, 'Para': l.Valor_Novo,
            'Usuario': l.Usuario_Acao, 'Data': l.Data_Acao.strftime('%d/%m/%Y %H:%M:%S'), 'Tipo': l.Tipo_Acao
        } for l in logs]

    # --- PROCESSAMENTO INTERGRUPO ---
    def ProcessarIntergrupoIntec(self, ano, mes, data_gravacao):
        try:
            meses_map = {
                1: 'jan', 2: 'fev', 3: 'mar', 4: 'abr', 5: 'mai', 6: 'jun', 
                7: 'jul', 8: 'ago', 9: 'set', 10: 'out', 11: 'nov', 12: 'dez'
            }
            competencia_anomes = f"{ano}-{meses_map[mes]}"
            
            caminho_qvd = os.path.join(BaseConfig().DataQVDPath(), "ValorFinanceiro.qvd")
            df_qvd = ler_qvd_para_dataframe(caminho_qvd)

            if 'ValorFinanceiro' in df_qvd.columns:
                df_qvd['ValorFinanceiro'] = pd.to_numeric(df_qvd['ValorFinanceiro'], errors='coerce').fillna(0.0)
            
            # --- NOVO FILTRO ESPECÍFICO (CONTA 60101010201 - AEREO INTEC) ---
            # Filtra Modal AEREO, Empresa INTEC, Intergroup S e N, no Anomes atual
            df_novo_filtro = df_qvd[
                (df_qvd['Modal'] == 'AEREO') & 
                (df_qvd['Empresa'] == 'INTEC') & 
                (df_qvd['INTERGROUP'].isin(['S', 'N'])) & 
                (df_qvd['Anomes'] == competencia_anomes)
            ]
            v_aereo_intec_especifico = df_novo_filtro['ValorFinanceiro'].sum()

            # --- FILTROS ANTERIORES (INTERGROUP = 'S') ---
            df_filtrado_s = df_qvd[(df_qvd['INTERGROUP'] == 'S') & (df_qvd['Empresa'] == 'INTEC') & (df_qvd['Anomes'] == competencia_anomes)]
            
            v_rodoviario = df_filtrado_s[df_filtrado_s['Modal'] == 'RODOVIARIO']['ValorFinanceiro'].sum()
            v_aereo = df_filtrado_s[df_filtrado_s['Modal'] == 'AEREO']['ValorFinanceiro'].sum()

            RegistrarLog(f"QVD Intec. Mes: {competencia_anomes}, Novo Aereo Intec: {v_aereo_intec_especifico}, Rodo: {v_rodoviario}, Aereo: {v_aereo}", "DEBUG")

            if v_rodoviario == 0 and v_aereo == 0 and v_aereo_intec_especifico == 0:
                return []

            with self.engine.connect() as conn:
                query = text(f"""
                    SELECT * FROM "{self.schema}"."Razao_Dados_Consolidado"
                    WHERE "origem" = 'INTEC' AND "Conta" = '60101010201'
                    ORDER BY "Data" DESC LIMIT 1
                """)
                res = conn.execute(query).fetchone()
                if not res: return ["Template INTEC não encontrado"]
                template = dict(res._mapping)

            logs_intec = []
            
            # LISTA DE LANÇAMENTOS (O novo lançamento entra primeiro)
            lancamentos = [
                # NOVO LANÇAMENTO (AEREO INTEC S/N)
                {'modal': 'AEREO', 'valor': v_aereo_intec_especifico, 'conta': '60101010201', 'tipo': 'D', 'sufixo': 'DEBITO'},
                {'modal': 'AEREO', 'valor': v_aereo_intec_especifico, 'conta': '60101010201A', 'tipo': 'C', 'sufixo': 'CREDITO'},

                # DÉBITOS ORIGINAIS (INTERGROUP S)
                {'modal': 'RODOVIARIO', 'valor': v_rodoviario, 'conta': '60101010201', 'tipo': 'D', 'sufixo': 'D'},
                {'modal': 'AEREO', 'valor': v_aereo, 'conta': '60101010201A', 'tipo': 'D', 'sufixo': 'D'},
                
                # CRÉDITOS ORIGINAIS (CONTRA-PARTIDA)
                {'modal': 'RODOVIARIO', 'valor': v_rodoviario, 'conta': '60101010201B', 'tipo': 'C', 'sufixo': 'C'},
                {'modal': 'AEREO', 'valor': v_aereo, 'conta': '60101010201C', 'tipo': 'C', 'sufixo': 'C'}
            ]

            for lanc in lancamentos:
                if lanc['valor'] > 0:
                    v_abs = round(abs(lanc['valor']), 2)
                    
                    val_debito = v_abs if lanc['tipo'] == 'D' else 0.0
                    val_credito = v_abs if lanc['tipo'] == 'C' else 0.0
                    
                    # A descrição agora carrega o sufixo para garantir unicidade no banco
                    desc_final = f"INTERGRUPO INTEC - {lanc['modal']} - {competencia_anomes} ({lanc['sufixo']})"

                    params_hash = {
                        'Conta': lanc['conta'], 'Data': data_gravacao,
                        'Descricao': desc_final,
                        'Debito': val_debito, 'Credito': val_credito,
                        'Filial': template.get('Filial'),
                        'Centro_Custo': template.get('Centro de Custo') or template.get('Centro_Custo'),
                        'Origem': 'INTEC'
                    }
                    hash_val = self._GerarHashIntergrupo(params_hash)

                    # Busca o ajuste específico para esta linha (Débito ou Crédito)
                    ajuste_existente = self.session.query(AjustesRazao).filter(
                        AjustesRazao.Origem == 'INTEC',
                        AjustesRazao.Conta == lanc['conta'],
                        AjustesRazao.Descricao == desc_final, # Filtro exato pela nova descrição
                        AjustesRazao.Tipo_Operacao == 'INTERGRUPO_AUTO'
                    ).first()

                    if ajuste_existente:
                        # Atualiza o valor se houver diferença
                        valor_atual = ajuste_existente.Debito if lanc['tipo'] == 'D' else ajuste_existente.Credito
                        if abs(valor_atual - v_abs) > 0.01:
                            if lanc['tipo'] == 'D':
                                ajuste_existente.Debito = v_abs
                            else:
                                ajuste_existente.Credito = v_abs
                                
                            ajuste_existente.Hash_Linha_Original = hash_val 
                            logs_intec.append(f"[{competencia_anomes}] {lanc['modal']} {lanc['sufixo']}: Atualizado")
                    else:
                        # Cria a nova linha (Seja Débito ou Crédito)
                        ajuste = AjustesRazao(
                            Conta=lanc['conta'],
                            Titulo_Conta=template.get('Titulo_Conta', 'VENDA DE FRETES'),
                            Data=data_gravacao,
                            Descricao=desc_final,
                            Debito=val_debito, Credito=val_credito,
                            Filial=template.get('Filial'),
                            Centro_Custo=template.get('Centro de Custo') or template.get('Centro_Custo'),
                            Item='INTERGRUPO',
                            Origem='INTEC',
                            Hash_Linha_Original=hash_val, 
                            Tipo_Operacao='INTERGRUPO_AUTO',
                            Status='Aprovado', Invalido=False,
                            Criado_Por='SISTEMA_QVD', Data_Aprovacao=datetime.datetime.now(),
                            Exibir_Saldo=True
                        )
                        self.session.add(ajuste)
                        logs_intec.append(f"[{competencia_anomes}] {lanc['modal']} {lanc['sufixo']}: Criado")
            
            return logs_intec

        except Exception as e:
            RegistrarLog(f"Falha INTEC QVD", "ERROR", e)
            return [f"ERRO INTEC: {str(e)}"]

    def GerarIntergrupo(self, ano, mes):
        RegistrarLog(f"Iniciando GerarIntergrupo MENSAL. {mes}/{ano}", "SYSTEM")
        
        config_contas = {
            '60301020290': {'destino': '60301020290B', 'descricao': 'ajuste intergrupo ( fretes Dist.)', 'titulo_origem': 'FRETE DISTRIBUIÇÃO', 'titulo_destino': 'FRETE DISTRIBUIÇÃO'},
            '60301020288': {'destino': '60301020288C', 'descricao': 'ajuste intergrupo ( fretes Aéreo)', 'titulo_origem': 'FRETES AEREO', 'titulo_destino': 'FRETES AEREO'},
            '60101010201': {'destino': '60101010201A', 'descricao': 'VLR. CFE DIARIO AUXILIAR N/ DATA (aéreo)', 'titulo_origem': 'VENDA DE FRETES', 'titulo_destino': 'VENDA DE FRETES'}
        }
        
        logs_totais = []
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        data_inicio = datetime.datetime(ano, mes, 1)
        data_fim = datetime.datetime(ano, mes, ultimo_dia, 23, 59, 59)
        data_gravacao = datetime.datetime(ano, mes, ultimo_dia)

        try:
            logs_intec = self.ProcessarIntergrupoIntec(ano, mes, data_gravacao)
            logs_totais.extend(logs_intec)

            for conta_origem, config in config_contas.items():
                sql = text(f"""
                    SELECT "origem", SUM("Debito") as deb, SUM("Credito") as cred, 
                        MAX("Item") as item, MAX("Filial") as filial, MAX("Centro de Custo") as cc
                    FROM "{self.schema}"."Razao_Dados_Consolidado"
                    WHERE "Conta" = :conta AND "Data" >= :d_ini AND "Data" <= :d_fim
                    AND "origem" NOT IN ('INTEC')
                    GROUP BY "origem"
                """)
                
                rows = self.session.execute(sql, {'conta': conta_origem, 'd_ini': data_inicio, 'd_fim': data_fim}).fetchall()

                for row in rows:
                    if not row.deb and not row.cred: continue
                    valor_ajuste = round(abs(float(row.deb or 0.0) - float(row.cred or 0.0)), 2)
                    if valor_ajuste <= 0: continue
                    
                    # Preparar dados para Hash Origem
                    p_orig = {
                        'Conta': conta_origem, 'Data': data_gravacao, 'Descricao': config['descricao'],
                        'Debito': 0.0, 'Credito': valor_ajuste, 'Filial': row.filial, 'Centro_Custo': row.cc, 'Origem': row.origem
                    }
                    h_orig = self._GerarHashIntergrupo(p_orig)

                    # Preparar dados para Hash Destino
                    p_dest = {
                        'Conta': config['destino'], 'Data': data_gravacao, 'Descricao': config['descricao'],
                        'Debito': valor_ajuste, 'Credito': 0.0, 'Filial': row.filial, 'Centro_Custo': row.cc, 'Origem': row.origem
                    }
                    h_dest = self._GerarHashIntergrupo(p_dest)

                    # Verifica Existência
                    ajuste_existente = self.session.query(AjustesRazao).filter(
                        AjustesRazao.Origem == row.origem,
                        AjustesRazao.Conta == config['destino'], 
                        AjustesRazao.Tipo_Operacao == 'INTERGRUPO_AUTO',
                        AjustesRazao.Data == data_gravacao
                    ).first()

                    if ajuste_existente:
                        if abs(ajuste_existente.Debito - valor_ajuste) > 0.01:
                             ajuste_existente.Debito = valor_ajuste
                             ajuste_existente.Hash_Linha_Original = h_dest # Atualiza Hash Destino

                             par_origem = self.session.query(AjustesRazao).filter(
                                 AjustesRazao.Origem == row.origem,
                                 AjustesRazao.Conta == conta_origem,
                                 AjustesRazao.Tipo_Operacao == 'INTERGRUPO_AUTO',
                                 AjustesRazao.Data == data_gravacao
                             ).first()
                             if par_origem: 
                                 par_origem.Credito = valor_ajuste
                                 par_origem.Hash_Linha_Original = h_orig # Atualiza Hash Origem
                             
                             logs_totais.append(f"[{mes:02d}/{ano}] {row.origem}: Atualizado {config['destino']} v:{valor_ajuste}")
                    else:
                        aj_origem = AjustesRazao(
                            Conta=conta_origem, Titulo_Conta=config['titulo_origem'], Data=data_gravacao,
                            Descricao=config['descricao'], Debito=0.0, Credito=valor_ajuste,
                            Filial=row.filial, Centro_Custo=row.cc, Item=row.item, Origem=row.origem,
                            Tipo_Operacao='INTERGRUPO_AUTO', Status='Aprovado', Criado_Por='SISTEMA_AUTO',
                            Hash_Linha_Original=h_orig, # Hash Origem
                            Data_Aprovacao=datetime.datetime.now(), Exibir_Saldo=True
                        )
                        
                        aj_destino = AjustesRazao(
                            Conta=config['destino'], Titulo_Conta=config['titulo_destino'], Data=data_gravacao,
                            Descricao=config['descricao'], Debito=valor_ajuste, Credito=0.0,
                            Filial=row.filial, Centro_Custo=row.cc, Item=row.item, Origem=row.origem,
                            Tipo_Operacao='INTERGRUPO_AUTO', Status='Aprovado', Criado_Por='SISTEMA_AUTO',
                            Hash_Linha_Original=h_dest, # Hash Destino
                            Data_Aprovacao=datetime.datetime.now(), Exibir_Saldo=True
                        )
                        
                        self.session.add(aj_origem)
                        self.session.add(aj_destino)
                        logs_totais.append(f"[{mes:02d}/{ano}] {row.origem}: Criado {conta_origem} -> {config['destino']} v:{valor_ajuste}")

            return logs_totais

        except Exception as e:
            RegistrarLog("Erro ao persistir ajustes intergrupo", "ERROR", e)
            raise e