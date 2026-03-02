import datetime
import calendar
from dateutil import parser
import hashlib
import os
import pandas as pd
from sqlalchemy import text

# --- NOVOS IMPORTS ---
from Models.POSTGRESS.CTL_Ajustes import CtlAjusteRazao, CtlAjusteLog
from Settings import BaseConfig
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Utils.Hash_Utils import gerar_hash
from Utils.Common import parse_bool
from Utils.Logger import RegistrarLog 
from Db.Connections import GetPostgresEngine

class AjustesManuaisService:
    def __init__(self, session_db):
        self.session = session_db
        self.engine = GetPostgresEngine()
        self.schema = "Dre_Schema"

    def _RegistrarLog(self, ajuste_antigo, dados_novos, usuario):
        campos_mapeados = {
            'origem': 'Origem', 'Conta': 'Conta', 'Titulo_Conta': 'Titulo_Conta', 
            'Numero': 'Numero', 'Descricao': 'Descricao', 'Contra_Partida': 'Contra_Partida',
            'Filial': 'Filial', 'Centro_Custo': 'Centro_Custo', 'Item': 'Item',
            'Cod_Cl_Valor': 'Cod_Cl_Valor', 'Debito': 'Debito', 'Credito': 'Credito',
            'NaoOperacional': 'Is_Nao_Operacional', 'Exibir_Saldo': 'Exibir_Saldo',
            'Data': 'Data', 'Invalido': 'Invalido'
        }
        
        keys_front = dados_novos.keys()
        
        for json_key, model_attr in campos_mapeados.items():
            valor_novo_raw = dados_novos.get(json_key)
            if valor_novo_raw is None:
                if json_key == 'Titulo_Conta': valor_novo_raw = dados_novos.get('Título Conta')
                elif json_key == 'Centro_Custo': valor_novo_raw = dados_novos.get('Centro de Custo')
                elif json_key == 'Contra_Partida': valor_novo_raw = dados_novos.get('Contra Partida - Credito')

            valor_antigo_raw = getattr(ajuste_antigo, model_attr)

            val_antigo = str(valor_antigo_raw).strip() if valor_antigo_raw is not None else ''
            val_novo = str(valor_novo_raw).strip() if valor_novo_raw is not None else ''
            
            if model_attr == 'Data' and valor_antigo_raw:
                val_antigo = valor_antigo_raw.strftime('%Y-%m-%d')
                if val_novo and 'T' in val_novo: val_novo = val_novo.split('T')[0]
                try:
                    if 'GMT' in val_novo or ',' in val_novo:
                        from dateutil import parser
                        dt_temp = parser.parse(val_novo)
                        val_novo = dt_temp.strftime('%Y-%m-%d')
                except: pass
            
            if model_attr in ['Debito', 'Credito']:
                try:
                    f_antigo = float(valor_antigo_raw or 0)
                    f_novo = float(valor_novo_raw or 0)
                    if abs(f_antigo - f_novo) < 0.001: continue
                    val_antigo, val_novo = f"{f_antigo:.2f}", f"{f_novo:.2f}"
                except: pass
            
            if model_attr in ['Is_Nao_Operacional', 'Exibir_Saldo', 'Invalido']:
                val_antigo = 'Sim' if parse_bool(valor_antigo_raw) else 'Não'
                val_novo = 'Sim' if parse_bool(valor_novo_raw) else 'Não'

            if val_antigo != val_novo:
                RegistrarLog(f"Alteração detectada em {model_attr}: '{val_antigo}' -> '{val_novo}'", "DEBUG")
                novo_log = CtlAjusteLog(
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

    def ObterDadosGrid(self):
        RegistrarLog("Iniciando ObterDadosGrid", "SERVICE")
        
        # --- ATUALIZAÇÃO DA VIEW ---
        q_view = text('SELECT * FROM "Dre_Schema"."Vw_CTL_Razao_Consolidado" LIMIT 10000000') 
        res_view = self.session.execute(q_view)
        rows_view = [dict(row._mapping) for row in res_view]
        
        ajustes = self.session.query(CtlAjusteRazao).all()
        mapa_existentes = {aj.Hash_Linha_Original: aj for aj in ajustes}
        
        novos_ajustes_auto = []
        for row in rows_view:
            if str(row.get('Item')).strip() == '10190':
                h = gerar_hash(row)
                if h not in mapa_existentes:
                    now = datetime.datetime.now()
                    novo = CtlAjusteRazao(
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
            ajustes = self.session.query(CtlAjusteRazao).all()

        mapa_edicao = {}
        lista_adicionais = []
        for aj in ajustes:
            if aj.Tipo_Operacao in ['EDICAO', 'NO-OPER_AUTO']:
                if aj.Hash_Linha_Original: mapa_edicao[aj.Hash_Linha_Original] = aj
            elif aj.Tipo_Operacao in ['INCLUSAO', 'INTERGRUPO_AUTO']:
                lista_adicionais.append(aj)

        dados_finais = []
        
        def MontarLinha(base, ajuste=None, is_inclusao=False):
            row = base.copy()
            row['Exibir_Saldo'] = True 
            if ajuste:
                row.update({
                    'origem': ajuste.Origem, 'Conta': ajuste.Conta, 'Título Conta': ajuste.Titulo_Conta,
                    'Data': ajuste.Data.strftime('%Y-%m-%d') if ajuste.Data else None,
                    'Numero': ajuste.Numero, 'Descricao': ajuste.Descricao, 
                    'Contra Partida - Credito': ajuste.Contra_Partida,
                    'Filial': ajuste.Filial, 'Centro de Custo': ajuste.Centro_Custo,
                    'Item': ajuste.Item, 'Cod Cl. Valor': ajuste.Cod_Cl_Valor, 
                    'Debito': ajuste.Debito, 'Credito': ajuste.Credito, 
                    'NaoOperacional': ajuste.Is_Nao_Operacional, 'Status_Ajuste': ajuste.Status, 
                    'Ajuste_ID': ajuste.Id
                })
                if is_inclusao:
                    prefixo = "AUTO_" if 'INTERGRUPO' in str(ajuste.Tipo_Operacao) else "NEW_"
                    row['Hash_ID'] = f"{prefixo}{ajuste.Id}"
                    row['Tipo_Linha'] = 'Inclusao'
            
            row['Saldo'] = (float(row.get('Debito') or 0) - float(row.get('Credito') or 0)) if row.get('Exibir_Saldo') else 0.0
            return row

        for row in rows_view: 
            h = gerar_hash(row)
            aj = mapa_edicao.get(h)
            linha = MontarLinha(row, aj, is_inclusao=False)
            linha['Hash_ID'] = h
            linha['Tipo_Linha'] = 'Original'
            if not aj: linha['Status_Ajuste'] = 'Original'
            dados_finais.append(linha)

        for adic in lista_adicionais: 
            dados_finais.append(MontarLinha({}, adic, is_inclusao=True))
        
        return dados_finais

    def CriarAjusteManual(self, payload, usuario):
        RegistrarLog(f"Iniciando CriarAjusteManual. Usuario: {usuario}", "SERVICE")
        
        d = payload['Dados']
        now = datetime.datetime.now()
        data_ajuste = now
        data_raw = d.get('Data')
        if data_raw:
            try:
                if 'T' in str(data_raw): 
                    data_ajuste = datetime.datetime.strptime(data_raw.split('T')[0], '%Y-%m-%d')
                else: data_ajuste = parser.parse(str(data_raw))
            except: pass

        ajuste = CtlAjusteRazao()
        ajuste.Criado_Por = usuario
        ajuste.Data_Criacao = now
        ajuste.Tipo_Operacao = 'INCLUSAO'
        ajuste.Status = 'Pendente'
        
        raw_hash = f"{now.timestamp()}-{usuario}-{d.get('Descricao')}"
        ajuste.Hash_Linha_Original = hashlib.md5(raw_hash.encode('utf-8')).hexdigest()

        ajuste.Origem = 'MANUAL'
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
        self.session.flush() 
        
        log = CtlAjusteLog(
            Id_Ajuste=ajuste.Id, Campo_Alterado='TODOS', Valor_Antigo='-', 
            Valor_Novo='CRIADO_MANUALMENTE', Usuario_Acao=usuario, 
            Data_Acao=now, Tipo_Acao='INCLUSAO'
        )
        self.session.add(log)
        self.session.commit()
        return ajuste.Id
    
    def SalvarAjuste(self, payload, usuario):
        RegistrarLog(f"Iniciando SalvarAjuste. Usuario: {usuario}", "SERVICE")
        
        d = payload.get('Dados', {})
        hash_id = d.get('Hash_ID') or payload.get('Hash_ID')
        ajuste_id = d.get('Ajuste_ID') or payload.get('Ajuste_ID')
        ajuste = None
        is_novo = False

        if ajuste_id:
            ajuste = self.session.query(CtlAjusteRazao).get(ajuste_id)
        
        if not ajuste and hash_id and not str(hash_id).startswith('NEW_'):
            ajuste = self.session.query(CtlAjusteRazao).filter_by(Hash_Linha_Original=hash_id).first()
        
        if not ajuste:
            ajuste = CtlAjusteRazao()
            is_novo = True
            ajuste.Criado_Por = usuario
            ajuste.Data_Criacao = datetime.datetime.now()
            if payload.get('Tipo_Operacao') != 'INCLUSAO':
                ajuste.Hash_Linha_Original = hash_id
            self.session.add(ajuste)
        else:
            self._RegistrarLog(ajuste, d, usuario)

        tipo_solicitado = payload.get('Tipo_Operacao', 'EDICAO')
        if ajuste.Tipo_Operacao == 'INCLUSAO' or tipo_solicitado == 'INCLUSAO':
            ajuste.Tipo_Operacao = 'INCLUSAO'
        else:
            ajuste.Tipo_Operacao = 'EDICAO'

        ajuste.Status = 'Pendente'
        ajuste.Origem = d.get('origem', ajuste.Origem)
        if d.get('Conta'): ajuste.Conta = str(d.get('Conta')).strip()
        ajuste.Titulo_Conta = d.get('Titulo_Conta') or d.get('Título Conta')
        ajuste.Centro_Custo = d.get('Centro de Custo') or d.get('Centro_Custo')
        
        data_raw = d.get('Data')
        if data_raw:
            try: ajuste.Data = parser.parse(str(data_raw))
            except:
                if 'T' in str(data_raw): ajuste.Data = datetime.datetime.strptime(data_raw.split('T')[0], '%Y-%m-%d')

        ajuste.Numero = d.get('Numero')
        ajuste.Descricao = d.get('Descricao')
        ajuste.Contra_Partida = d.get('Contra_Partida') or d.get('Contra Partida - Credito')
        ajuste.Filial = d.get('Filial')
        ajuste.Item = d.get('Item')
        ajuste.Cod_Cl_Valor = d.get('Cod_Cl_Valor') or d.get('Cod Cl. Valor')
        ajuste.Debito = float(d.get('Debito') or 0)
        ajuste.Credito = float(d.get('Credito') or 0)
        ajuste.Invalido = parse_bool(d.get('Invalido'))
        ajuste.Is_Nao_Operacional = parse_bool(d.get('NaoOperacional'))
        ajuste.Exibir_Saldo = parse_bool(d.get('Exibir_Saldo', True))
        
        self.session.flush()
        
        if is_novo:
            log = CtlAjusteLog(
                Id_Ajuste=ajuste.Id, Campo_Alterado='TODOS', Valor_Antigo='-', 
                Valor_Novo='CRIADO_VIA_SALVAR', Usuario_Acao=usuario, 
                Data_Acao=datetime.datetime.now(), Tipo_Acao='CRIACAO'
            )
            self.session.add(log)
        
        self.session.commit()
        return ajuste.Id
    
    def AprovarAjuste(self, ajuste_id, acao, usuario):
        ajuste = self.session.query(CtlAjusteRazao).get(ajuste_id)
        if ajuste:
            novo_status = 'Aprovado' if acao == 'Aprovar' else 'Reprovado'
            log = CtlAjusteLog(Id_Ajuste=ajuste.Id, Campo_Alterado='Status', Valor_Antigo=ajuste.Status, 
                             Valor_Novo=novo_status, Usuario_Acao=usuario, Data_Acao=datetime.datetime.now(), Tipo_Acao='APROVACAO')
            self.session.add(log)
            ajuste.Status = novo_status
            ajuste.Aprovado_Por = usuario
            ajuste.Data_Aprovacao = datetime.datetime.now()
            self.session.commit()

    def ToggleInvalido(self, ajuste_id, acao, usuario):
        ajuste = self.session.query(CtlAjusteRazao).get(ajuste_id)
        if not ajuste: raise Exception('Ajuste não encontrado')
        novo_estado_invalido = (acao == 'INVALIDAR')
        log = CtlAjusteLog(
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
        logs = self.session.query(CtlAjusteLog).filter(CtlAjusteLog.Id_Ajuste == ajuste_id).order_by(CtlAjusteLog.Data_Acao.desc()).all()
        return [{
            'Id_Log': l.Id_Log, 'Campo': l.Campo_Alterado, 'De': l.Valor_Antigo, 'Para': l.Valor_Novo,
            'Usuario': l.Usuario_Acao, 'Data': l.Data_Acao.strftime('%d/%m/%Y %H:%M:%S'), 'Tipo': l.Tipo_Acao
        } for l in logs]

    def ProcessarIntergrupoIntec(self, ano, mes, data_gravacao):
        try:
            meses_map = {1: 'jan', 2: 'fev', 3: 'mar', 4: 'abr', 5: 'mai', 6: 'jun', 7: 'jul', 8: 'ago', 9: 'set', 10: 'out', 11: 'nov', 12: 'dez'}
            competencia_anomes = f"{ano}-{meses_map[mes]}"
            caminho_csv = os.path.join(BaseConfig().DataQVDPath(), "ValorFinanceiro.csv")
            
            if not os.path.exists(caminho_csv):
                 return ["Erro: Arquivo ValorFinanceiro.csv não encontrado."]

            df_qvd = None
            erros_leitura = []
            try:
                df_qvd = pd.read_csv(caminho_csv, sep=';', encoding='utf-8-sig', low_memory=False)
                if len(df_qvd.columns) <= 1: 
                    df_qvd = pd.read_csv(caminho_csv, sep=',', encoding='utf-8-sig', low_memory=False)
            except Exception as e: erros_leitura.append(f"UTF-8-SIG: {e}")

            if df_qvd is None or len(df_qvd.columns) <= 1:
                try:
                    df_qvd = pd.read_csv(caminho_csv, sep=';', encoding='latin1', low_memory=False)
                    if len(df_qvd.columns) <= 1: df_qvd = pd.read_csv(caminho_csv, sep=',', encoding='latin1', low_memory=False)
                except Exception as e: return [f"Erro leitura CSV. Detalhes no log."]

            def limpar_coluna(col): return col.strip().replace('Ï»¿', '').replace('\ufeff', '').upper()
            df_qvd.columns = [limpar_coluna(c) for c in df_qvd.columns]
            
            if 'INTERGROUP' not in df_qvd.columns: return [f"Erro: Coluna INTERGROUP inexistente. Verifique o CSV."]

            if 'VALORFINANCEIRO' in df_qvd.columns:
                if df_qvd['VALORFINANCEIRO'].dtype == object: df_qvd['VALORFINANCEIRO'] = df_qvd['VALORFINANCEIRO'].astype(str).str.replace('.', '').str.replace(',', '.')
                df_qvd['VALORFINANCEIRO'] = pd.to_numeric(df_qvd['VALORFINANCEIRO'], errors='coerce').fillna(0.0)
            
            cols_req = ['MODAL', 'EMPRESA', 'INTERGROUP', 'ANOMES']
            for c in cols_req:
                if c not in df_qvd.columns: return [f"Coluna obrigatória não encontrada: {c}"]

            df_novo_filtro = df_qvd[(df_qvd['MODAL'].str.upper() == 'AEREO') & (df_qvd['EMPRESA'].str.upper() == 'INTEC') & (df_qvd['INTERGROUP'].str.upper().isin(['S', 'N'])) & (df_qvd['ANOMES'] == competencia_anomes)]
            v_aereo_intec_especifico = df_novo_filtro['VALORFINANCEIRO'].sum()

            df_filtrado_s = df_qvd[(df_qvd['INTERGROUP'].str.upper() == 'S') & (df_qvd['EMPRESA'].str.upper() == 'INTEC') & (df_qvd['ANOMES'] == competencia_anomes)]
            v_rodoviario = df_filtrado_s[df_filtrado_s['MODAL'].str.upper() == 'RODOVIARIO']['VALORFINANCEIRO'].sum()
            v_aereo = df_filtrado_s[df_filtrado_s['MODAL'].str.upper() == 'AEREO']['VALORFINANCEIRO'].sum()

            if v_rodoviario == 0 and v_aereo == 0 and v_aereo_intec_especifico == 0: return []

            with self.engine.connect() as conn:
                # --- ATUALIZAÇÃO DA VIEW AQUI TAMBÉM ---
                query = text(f"""
                    SELECT * FROM "{self.schema}"."Vw_CTL_Razao_Consolidado"
                    WHERE "origem" = 'INTEC' AND "Conta" = '60101010201'
                    ORDER BY "Data" DESC LIMIT 1
                """)
                res = conn.execute(query).fetchone()
                if not res: return ["Template INTEC não encontrado"]
                template = dict(res._mapping)

            logs_intec = []
            lancamentos = [
                {'modal': 'AEREO', 'valor': v_aereo_intec_especifico, 'conta': '60101010201', 'tipo': 'D', 'sufixo': 'DEBITO'},
                {'modal': 'AEREO', 'valor': v_aereo_intec_especifico, 'conta': '60101010201A', 'tipo': 'C', 'sufixo': 'CREDITO'},
                {'modal': 'RODOVIARIO', 'valor': v_rodoviario, 'conta': '60101010201', 'tipo': 'D', 'sufixo': 'D'},
                {'modal': 'AEREO', 'valor': v_aereo, 'conta': '60101010201A', 'tipo': 'D', 'sufixo': 'D'},
                {'modal': 'RODOVIARIO', 'valor': v_rodoviario, 'conta': '60101010201B', 'tipo': 'C', 'sufixo': 'C'},
                {'modal': 'AEREO', 'valor': v_aereo, 'conta': '60101010201C', 'tipo': 'C', 'sufixo': 'C'}
            ]

            for lanc in lancamentos:
                if lanc['valor'] > 0:
                    v_abs = round(abs(lanc['valor']), 2)
                    val_debito = v_abs if lanc['tipo'] == 'D' else 0.0
                    val_credito = v_abs if lanc['tipo'] == 'C' else 0.0
                    desc_final = f"INTERGRUPO INTEC - {lanc['modal']} - {competencia_anomes} ({lanc['sufixo']})"

                    params_hash = {
                        'Conta': lanc['conta'], 'Data': data_gravacao, 'Descricao': desc_final,
                        'Debito': val_debito, 'Credito': val_credito, 'Filial': template.get('Filial'),
                        'Centro_Custo': template.get('Centro de Custo') or template.get('Centro_Custo'), 'Origem': 'INTEC'
                    }
                    hash_val = self._GerarHashIntergrupo(params_hash)

                    ajuste_existente = self.session.query(CtlAjusteRazao).filter(
                        CtlAjusteRazao.Origem == 'INTEC', CtlAjusteRazao.Conta == lanc['conta'],
                        CtlAjusteRazao.Descricao == desc_final, CtlAjusteRazao.Tipo_Operacao == 'INTERGRUPO_AUTO'
                    ).first()

                    if ajuste_existente:
                        valor_atual = ajuste_existente.Debito if lanc['tipo'] == 'D' else ajuste_existente.Credito
                        if abs(valor_atual - v_abs) > 0.01:
                            if lanc['tipo'] == 'D': ajuste_existente.Debito = v_abs
                            else: ajuste_existente.Credito = v_abs
                            ajuste_existente.Hash_Linha_Original = hash_val 
                            logs_intec.append(f"[{competencia_anomes}] {lanc['modal']} {lanc['sufixo']}: Atualizado para {v_abs}")
                    else:
                        ajuste = CtlAjusteRazao(
                            Conta=lanc['conta'], Titulo_Conta=template.get('Titulo_Conta', 'VENDA DE FRETES'),
                            Data=data_gravacao, Descricao=desc_final, Debito=val_debito, Credito=val_credito,
                            Filial=template.get('Filial'), Centro_Custo=template.get('Centro de Custo') or template.get('Centro_Custo'),
                            Item='INTERGRUPO', Origem='INTEC', Hash_Linha_Original=hash_val, 
                            Tipo_Operacao='INTERGRUPO_AUTO', Status='Aprovado', Invalido=False,
                            Criado_Por='SISTEMA_AUTO', Data_Aprovacao=datetime.datetime.now(), Exibir_Saldo=True
                        )
                        self.session.add(ajuste)
                        logs_intec.append(f"[{competencia_anomes}] {lanc['modal']} {lanc['sufixo']}: Criado {v_abs}")
            
            return logs_intec

        except Exception as e:
            return [f"ERRO CRÍTICO INTEC: {str(e)}"]
        
    def ProcessarIntergrupoFarma(self, ano, mes, data_inicio, data_fim, data_gravacao):
        """
        Processa as regras de intergrupo para a divisão Farma.
        REGRA 1 (Banco de Dados): Para contas gerais, soma apenas lançamentos onde a coluna 'Descricao' contenha 'INTEC'.
        REGRA 2 (CSV): Para a conta '60101010201', acessa o CSV, filtra Modal 'AEREO' e Empresa 'FARMA'.
        
        Args:
            ano (int): Ano para cálculo.
            mes (int): Mês para cálculo.
            data_inicio (datetime): Data de início do período (1º dia do mês).
            data_fim (datetime): Data de fim do período (Último dia do mês às 23:59:59).
            data_gravacao (datetime): Data em que o lançamento deve ser registado na DRE.
            
        Returns:
            list[str]: Logs contendo o resumo dos registos verificados, criados ou ajustados.
        """
        logs_farma = []
        
        try:
            # =========================================================================
            # PARTE 1: PROCESSAR CONTAS VIA BANCO DE DADOS (FILTRO 'INTEC' NA DESCRIÇÃO)
            # =========================================================================
            config_contas_banco = {
                '60301020290': {'destino': '60301020290B', 'descricao': 'ajuste intergrupo ( fretes Dist.)', 'titulo_origem': 'FRETE DISTRIBUIÇÃO', 'titulo_destino': 'FRETE DISTRIBUIÇÃO'},
                '60301020288': {'destino': '60301020288C', 'descricao': 'ajuste intergrupo ( fretes Aéreo)', 'titulo_origem': 'FRETES AEREO', 'titulo_destino': 'FRETES AEREO'}
            }
            
            for conta_origem, config in config_contas_banco.items():
                sql = text(f"""
                    SELECT "origem", "Descricao", "Debito", "Credito", "Item", "Filial", "Centro de Custo" as cc
                    FROM "{self.schema}"."Vw_CTL_Razao_Consolidado"
                    WHERE "Conta" = :conta AND "Data" >= :d_ini AND "Data" <= :d_fim
                    AND "origem" NOT IN ('INTEC')
                """)
                
                rows = self.session.execute(sql, {'conta': conta_origem, 'd_ini': data_inicio, 'd_fim': data_fim}).fetchall()

                agrupado_por_origem = {}

                for row in rows:
                    r_dict = dict(row._mapping)
                    descricao_texto = str(r_dict.get('Descricao') or '').upper()
                    
                    # FILTRO DE PRECISÃO: Só processa a linha se tiver 'INTEC' na descrição
                    if "INTEC" in descricao_texto:
                        orig = r_dict.get('origem')
                        
                        if orig not in agrupado_por_origem:
                            agrupado_por_origem[orig] = {
                                'deb': 0.0, 'cred': 0.0, 'item': r_dict.get('Item'),
                                'filial': r_dict.get('Filial'), 'cc': r_dict.get('cc'), 'origem': orig
                            }
                        
                        agrupado_por_origem[orig]['deb'] += float(r_dict.get('Debito') or 0.0)
                        agrupado_por_origem[orig]['cred'] += float(r_dict.get('Credito') or 0.0)
                        
                        if not agrupado_por_origem[orig]['filial'] and r_dict.get('Filial'): 
                            agrupado_por_origem[orig]['filial'] = r_dict.get('Filial')
                        if not agrupado_por_origem[orig]['cc'] and r_dict.get('cc'): 
                            agrupado_por_origem[orig]['cc'] = r_dict.get('cc')
                        if not agrupado_por_origem[orig]['item'] and r_dict.get('Item'): 
                            agrupado_por_origem[orig]['item'] = r_dict.get('Item')

                for orig, dados in agrupado_por_origem.items():
                    if not dados['deb'] and not dados['cred']: continue
                    
                    valor_ajuste = round(abs(dados['deb'] - dados['cred']), 2)
                    if valor_ajuste <= 0: continue
                    
                    p_orig = {
                        'Conta': conta_origem, 'Data': data_gravacao, 'Descricao': config['descricao'],
                        'Debito': 0.0, 'Credito': valor_ajuste, 'Filial': dados['filial'], 'Centro_Custo': dados['cc'], 'Origem': dados['origem']
                    }
                    h_orig = self._GerarHashIntergrupo(p_orig)

                    p_dest = {
                        'Conta': config['destino'], 'Data': data_gravacao, 'Descricao': config['descricao'],
                        'Debito': valor_ajuste, 'Credito': 0.0, 'Filial': dados['filial'], 'Centro_Custo': dados['cc'], 'Origem': dados['origem']
                    }
                    h_dest = self._GerarHashIntergrupo(p_dest)

                    ajuste_existente = self.session.query(CtlAjusteRazao).filter(
                        CtlAjusteRazao.Origem == dados['origem'], CtlAjusteRazao.Conta == config['destino'], 
                        CtlAjusteRazao.Tipo_Operacao == 'INTERGRUPO_AUTO', CtlAjusteRazao.Data == data_gravacao
                    ).first()

                    if ajuste_existente:
                        if abs(ajuste_existente.Debito - valor_ajuste) > 0.01:
                             ajuste_existente.Debito = valor_ajuste
                             ajuste_existente.Hash_Linha_Original = h_dest

                             par_origem = self.session.query(CtlAjusteRazao).filter(
                                 CtlAjusteRazao.Origem == dados['origem'], CtlAjusteRazao.Conta == conta_origem,
                                 CtlAjusteRazao.Tipo_Operacao == 'INTERGRUPO_AUTO', CtlAjusteRazao.Data == data_gravacao
                             ).first()
                             if par_origem: 
                                 par_origem.Credito = valor_ajuste
                                 par_origem.Hash_Linha_Original = h_orig
                             
                             logs_farma.append(f"[{mes:02d}/{ano}] {dados['origem']}: Atualizado {config['destino']} v:{valor_ajuste}")
                    else:
                        aj_origem = CtlAjusteRazao(
                            Conta=conta_origem, Titulo_Conta=config['titulo_origem'], Data=data_gravacao,
                            Descricao=config['descricao'], Debito=0.0, Credito=valor_ajuste,
                            Filial=dados['filial'], Centro_Custo=dados['cc'], Item=dados['item'], Origem=dados['origem'],
                            Tipo_Operacao='INTERGRUPO_AUTO', Status='Aprovado', Criado_Por='SISTEMA_AUTO',
                            Hash_Linha_Original=h_orig, Data_Aprovacao=datetime.datetime.now(), Exibir_Saldo=True
                        )
                        
                        aj_destino = CtlAjusteRazao(
                            Conta=config['destino'], Titulo_Conta=config['titulo_destino'], Data=data_gravacao,
                            Descricao=config['descricao'], Debito=valor_ajuste, Credito=0.0,
                            Filial=dados['filial'], Centro_Custo=dados['cc'], Item=dados['item'], Origem=dados['origem'],
                            Tipo_Operacao='INTERGRUPO_AUTO', Status='Aprovado', Criado_Por='SISTEMA_AUTO',
                            Hash_Linha_Original=h_dest, Data_Aprovacao=datetime.datetime.now(), Exibir_Saldo=True
                        )
                        
                        self.session.add(aj_origem)
                        self.session.add(aj_destino)
                        logs_farma.append(f"[{mes:02d}/{ano}] {dados['origem']}: Criado {conta_origem} -> {config['destino']} v:{valor_ajuste}")

            # =========================================================================
            # PARTE 2: PROCESSAR CONTA 60101010201 VIA CSV (FARMA - AEREO)
            # =========================================================================
            meses_map = {1: 'jan', 2: 'fev', 3: 'mar', 4: 'abr', 5: 'mai', 6: 'jun', 7: 'jul', 8: 'ago', 9: 'set', 10: 'out', 11: 'nov', 12: 'dez'}
            competencia_anomes = f"{ano}-{meses_map[mes]}"
            caminho_csv = os.path.join(BaseConfig().DataQVDPath(), "ValorFinanceiro.csv")
            
            if os.path.exists(caminho_csv):
                # Leitura robusta do CSV (Tratamento de BOM / encoding)
                df_qvd = None
                try:
                    df_qvd = pd.read_csv(caminho_csv, sep=';', encoding='utf-8-sig', low_memory=False)
                    if len(df_qvd.columns) <= 1:
                        df_qvd = pd.read_csv(caminho_csv, sep=',', encoding='utf-8-sig', low_memory=False)
                except: pass

                if df_qvd is None or len(df_qvd.columns) <= 1:
                    try:
                        df_qvd = pd.read_csv(caminho_csv, sep=';', encoding='latin1', low_memory=False)
                        if len(df_qvd.columns) <= 1:
                            df_qvd = pd.read_csv(caminho_csv, sep=',', encoding='latin1', low_memory=False)
                    except: pass

                if df_qvd is not None and len(df_qvd.columns) > 1:
                    # Limpeza das colunas
                    def limpar_coluna(col): return col.strip().replace('Ï»¿', '').replace('\ufeff', '').upper()
                    df_qvd.columns = [limpar_coluna(c) for c in df_qvd.columns]
                    
                    if 'VALORFINANCEIRO' in df_qvd.columns:
                        if df_qvd['VALORFINANCEIRO'].dtype == object:
                             df_qvd['VALORFINANCEIRO'] = df_qvd['VALORFINANCEIRO'].astype(str).str.replace('.', '').str.replace(',', '.')
                        df_qvd['VALORFINANCEIRO'] = pd.to_numeric(df_qvd['VALORFINANCEIRO'], errors='coerce').fillna(0.0)

                    # Filtro específico para FARMA AEREO
                    if all(c in df_qvd.columns for c in ['MODAL', 'EMPRESA', 'ANOMES']):
                        df_farma_aereo = df_qvd[
                            (df_qvd['MODAL'].str.upper() == 'AEREO') & 
                            (df_qvd['EMPRESA'].str.upper() == 'FARMA') & 
                            (df_qvd['ANOMES'] == competencia_anomes)
                        ]
                        
                        valor_csv_farma = round(df_farma_aereo['VALORFINANCEIRO'].sum(), 2)
                        
                        if valor_csv_farma > 0:
                            # Busca o template no banco apenas para pegar a Filial e CC
                            with self.engine.connect() as conn:
                                query = text(f"""
                                    SELECT * FROM "{self.schema}"."Vw_CTL_Razao_Consolidado"
                                    WHERE "origem" = 'FARMA' AND "Conta" = '60101010201'
                                    ORDER BY "Data" DESC LIMIT 1
                                """)
                                res = conn.execute(query).fetchone()
                                template = dict(res._mapping) if res else {}

                            origem_farma = 'FARMA'
                            desc_csv = 'VLR. CFE DIARIO AUXILIAR N/ DATA (aéreo)'

                            # ---------------------------------------------------------
                            # MECÂNICA DE LANÇAMENTOS (DEBITO E CREDITO)
                            # ---------------------------------------------------------
                            lancamentos = [
                                {'modal': 'AEREO', 'valor': valor_csv_farma, 'conta': '60101010201', 'tipo': 'D', 'sufixo': 'DEBITO'},
                                {'modal': 'AEREO', 'valor': valor_csv_farma, 'conta': '60101010201A', 'tipo': 'C', 'sufixo': 'CREDITO'}
                            ]

                            for lanc in lancamentos:
                                v_abs = round(abs(lanc['valor']), 2)
                                if v_abs <= 0: continue

                                val_debito = v_abs if lanc['tipo'] == 'D' else 0.0
                                val_credito = v_abs if lanc['tipo'] == 'C' else 0.0

                                params_hash = {
                                    'Conta': lanc['conta'], 'Data': data_gravacao, 'Descricao': desc_csv,
                                    'Debito': val_debito, 'Credito': val_credito, 
                                    'Filial': template.get('Filial', ''), 
                                    'Centro_Custo': template.get('Centro de Custo') or template.get('Centro_Custo', ''), 
                                    'Origem': origem_farma
                                }
                                hash_val = self._GerarHashIntergrupo(params_hash)

                                ajuste_existente = self.session.query(CtlAjusteRazao).filter(
                                    CtlAjusteRazao.Origem == origem_farma, 
                                    CtlAjusteRazao.Conta == lanc['conta'], 
                                    CtlAjusteRazao.Tipo_Operacao == 'INTERGRUPO_AUTO', 
                                    CtlAjusteRazao.Data == data_gravacao
                                ).first()

                                if ajuste_existente:
                                    valor_atual = ajuste_existente.Debito if lanc['tipo'] == 'D' else ajuste_existente.Credito
                                    if abs(valor_atual - v_abs) > 0.01:
                                        if lanc['tipo'] == 'D':
                                            ajuste_existente.Debito = v_abs
                                        else:
                                            ajuste_existente.Credito = v_abs
                                            
                                        ajuste_existente.Hash_Linha_Original = hash_val 
                                        logs_farma.append(f"[{mes:02d}/{ano}] FARMA (CSV) {lanc['sufixo']}: Atualizado {lanc['conta']} para {v_abs}")
                                else:
                                    novo_ajuste = CtlAjusteRazao(
                                        Conta=lanc['conta'], Titulo_Conta='VENDA DE FRETES', Data=data_gravacao,
                                        Descricao=desc_csv, Debito=val_debito, Credito=val_credito,
                                        Filial=template.get('Filial', ''), Centro_Custo=template.get('Centro de Custo') or template.get('Centro_Custo', ''), 
                                        Item=template.get('Item', ''), Origem=origem_farma,
                                        Tipo_Operacao='INTERGRUPO_AUTO', Status='Aprovado', Criado_Por='SISTEMA_AUTO_CSV',
                                        Hash_Linha_Original=hash_val, Data_Aprovacao=datetime.datetime.now(), Exibir_Saldo=True
                                    )
                                    self.session.add(novo_ajuste)
                                    logs_farma.append(f"[{mes:02d}/{ano}] FARMA (CSV) {lanc['sufixo']}: Criado {lanc['conta']} v:{v_abs}")
            else:
                RegistrarLog("Aviso FARMA: Arquivo ValorFinanceiro.csv não encontrado.", "WARNING")
                logs_farma.append("Aviso FARMA: Arquivo CSV não encontrado para a conta 60101010201.")

            return logs_farma
            
        except Exception as e:
            RegistrarLog(f"Erro no ProcessarIntergrupoFarma", "ERROR", e)
            raise e

    def GerarIntergrupo(self, ano, mes):
        logs_totais = []
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        data_inicio = datetime.datetime(ano, mes, 1)
        data_fim = datetime.datetime(ano, mes, ultimo_dia, 23, 59, 59)
        data_gravacao = datetime.datetime(ano, mes, ultimo_dia)

        try:
            logs_intec = self.ProcessarIntergrupoIntec(ano, mes, data_gravacao)
            logs_totais.extend(logs_intec)
            logs_farma = self.ProcessarIntergrupoFarma(ano, mes, data_inicio, data_fim, data_gravacao)
            logs_totais.extend(logs_farma)
            self.session.commit()
            
            qtd_registros = self.session.query(CtlAjusteRazao).filter(
                CtlAjusteRazao.Tipo_Operacao == 'INTERGRUPO_AUTO',
                text(f"EXTRACT(MONTH FROM \"Data\") = {mes}"),
                text(f"EXTRACT(YEAR FROM \"Data\") = {ano}")
            ).count()

            if qtd_registros < 12:
                aviso = f"ATENÇÃO CRÍTICA: Processo gerou apenas {qtd_registros} registros. Esperado no mínimo 12. Verifique os dados de origem (CSV ou Banco)."
                logs_totais.append(aviso)
            else:
                logs_totais.append(f"Sucesso: {qtd_registros} registros intergrupo validados (Mínimo 12 OK).")

            return logs_totais

        except Exception as e:
            self.session.rollback() 
            raise e