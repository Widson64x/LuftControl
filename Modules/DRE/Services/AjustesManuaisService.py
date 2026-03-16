import datetime
import calendar
from dateutil import parser
import pandas as pd
from sqlalchemy import text, func

# --- NOVOS IMPORTS ALINHADOS COM A NOVA ARQUITETURA ---
from Models.Postgress.CTL_Razao import CtlRazaoConsolidado
from Models.Postgress.CTL_Ajustes import CtlAjusteLog
from Settings import BaseConfig
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from Utils.Common import parse_bool
from Utils.Logger import RegistrarLog 
from Db.Connections import GetPostgresEngine

class AjustesManuaisService:
    def __init__(self, session_db):
        self.session = session_db
        self.engine = GetPostgresEngine()
        self.schema = "Dre_Schema"

    # =========================================================================
    # LOG E AUDITORIA
    # =========================================================================
    def _RegistrarLog(self, registro_antigo, dados_novos, usuario, tipo_acao='EDICAO'):
        """
        Compara o objeto antigo com os dados que vieram da tela e salva as diferenças no Log.
        """
        campos_mapeados = {
            'origem': 'origem', 'Conta': 'Conta', 'Titulo_Conta': 'Titulo_Conta', 
            'Numero': 'Numero', 'Descricao': 'Descricao', 'Contra_Partida': 'Contra_Partida_Credito',
            'Filial': 'Filial', 'Centro_Custo': 'Centro_Custo', 'Item': 'Item',
            'Cod_Cl_Valor': 'Cod_Cl_Valor', 'Debito': 'Debito', 'Credito': 'Credito',
            'NaoOperacional': 'Is_Nao_Operacional', 'Exibir_Saldo': 'Exibir_Saldo',
            'Data': 'Data', 'Invalido': 'Invalido', 'Status': 'Status'
        }
        
        for json_key, model_attr in campos_mapeados.items():
            # Recupera o valor novo que veio da tela
            valor_novo_raw = dados_novos.get(json_key)
            if valor_novo_raw is None:
                if json_key == 'Titulo_Conta': valor_novo_raw = dados_novos.get('Título Conta')
                elif json_key == 'Centro_Custo': valor_novo_raw = dados_novos.get('Centro de Custo')
                elif json_key == 'Contra_Partida': valor_novo_raw = dados_novos.get('Contra Partida - Credito')

            # Recupera o valor antigo que está no banco
            valor_antigo_raw = getattr(registro_antigo, model_attr, None)

            val_antigo = str(valor_antigo_raw).strip() if valor_antigo_raw is not None else ''
            val_novo = str(valor_novo_raw).strip() if valor_novo_raw is not None else ''
            
            # Tratamento de Data
            if model_attr == 'Data' and valor_antigo_raw:
                val_antigo = valor_antigo_raw.strftime('%Y-%m-%d')
                if val_novo and 'T' in val_novo: val_novo = val_novo.split('T')[0]
                try:
                    if 'GMT' in val_novo or ',' in val_novo:
                        dt_temp = parser.parse(val_novo)
                        val_novo = dt_temp.strftime('%Y-%m-%d')
                except: pass
            
            # Tratamento de Números
            if model_attr in ['Debito', 'Credito']:
                try:
                    f_antigo = float(valor_antigo_raw or 0)
                    f_novo = float(valor_novo_raw or 0)
                    if abs(f_antigo - f_novo) < 0.001: continue
                    val_antigo, val_novo = f"{f_antigo:.2f}", f"{f_novo:.2f}"
                except: pass
            
            # Tratamento de Booleanos
            if model_attr in ['Is_Nao_Operacional', 'Exibir_Saldo', 'Invalido']:
                if valor_novo_raw is not None: # Só testa se enviaram algo
                    val_antigo = 'Sim' if parse_bool(valor_antigo_raw) else 'Não'
                    val_novo = 'Sim' if parse_bool(valor_novo_raw) else 'Não'

            # Se mudou, regista!
            if val_antigo != val_novo and valor_novo_raw is not None:
                RegistrarLog(f"Alteração {model_attr}: '{val_antigo}' -> '{val_novo}'", "DEBUG")
                novo_log = CtlAjusteLog(
                    Id_Registro=registro_antigo.Id,
                    Fonte_Registro=registro_antigo.Fonte,
                    Campo_Alterado=model_attr, 
                    Valor_Antigo=val_antigo, 
                    Valor_Novo=val_novo, 
                    Usuario_Acao=usuario, 
                    Data_Acao=datetime.datetime.now(), 
                    Tipo_Acao=tipo_acao
                )
                self.session.add(novo_log)

    # =========================================================================
    # GRID E OPERAÇÕES BÁSICAS
    # =========================================================================
    def ObterDadosGrid(self, ano=None, mes=None):
        """
        Lê diretamente da Tabela Consolidada usando RAW SQL para ultra-performance.
        Aplica filtro de Ano e Mês vindos da tela.
        """
        RegistrarLog(f"Iniciando ObterDadosGrid: Ano {ano} / Mes {mes}", "SERVICE")
        
        filtro_sql = ""
        parametros = {}
        
        # Se o utilizador enviou Ano e Mês da tela, montamos a cláusula WHERE
        if ano and mes:
            filtro_sql = """
                WHERE EXTRACT(YEAR FROM "Data") = :ano 
                  AND EXTRACT(MONTH FROM "Data") = :mes
            """
            parametros = {"ano": int(ano), "mes": int(mes)}
        
        # Adicionamos o filtro_sql na query
        # O LIMIT agora é só por segurança extrema (100.000), 
        # mas com o filtro de mês dificilmente chegará perto disso.
        query = text(f"""
            SELECT * FROM "{self.schema}"."Tb_CTL_Razao_Consolidado"
            {filtro_sql}
            ORDER BY "Data" DESC 
            LIMIT 100000 
        """)
        
        res = self.session.execute(query, parametros)
        dados_finais = []
        
        for row in res.mappings(): 
            saldo = (float(row.get('Debito') or 0) - float(row.get('Credito') or 0)) if row.get('Exibir_Saldo') else 0.0
            
            linha = {
                'Id': row.get('Id'),
                'Fonte': row.get('Fonte'),
                'origem': row.get('origem'),
                'Conta': row.get('Conta'),
                'Título Conta': row.get('Título Conta'),
                'Data': row.get('Data').strftime('%Y-%m-%d') if row.get('Data') else None,
                'Numero': row.get('Numero'),
                'Descricao': row.get('Descricao'),
                'Contra Partida - Credito': row.get('Contra Partida - Credito'),
                'Filial': row.get('Filial'),
                'Centro de Custo': row.get('Centro de Custo'),
                'Item': row.get('Item'),
                'Cod Cl. Valor': row.get('Cod Cl. Valor'),
                'Debito': row.get('Debito'),
                'Credito': row.get('Credito'),
                'NaoOperacional': row.get('Is_Nao_Operacional'),
                'Exibir_Saldo': row.get('Exibir_Saldo'),
                'Status_Ajuste': row.get('Status') or '',
                'Invalido': row.get('Invalido'),
                'Tipo_Operacao': row.get('Tipo_Operacao'),
                'Criado_Por': row.get('Criado_Por'),
                'Saldo': saldo
            }
            dados_finais.append(linha)
            
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

        # Função de proteção contra strings vazias em colunas numéricas
        def limpar_int(val):
            return int(val) if val and str(val).strip() else None

        # Descobrir o próximo ID para a fonte MANUAL
        max_id = self.session.query(func.max(CtlRazaoConsolidado.Id)).filter(CtlRazaoConsolidado.Fonte == 'MANUAL').scalar() or 0
        novo_id = max_id + 1

        novo_registro = CtlRazaoConsolidado(
            Id=novo_id,
            Fonte='MANUAL',
            Criado_Por=usuario,
            Data_Criacao=now,
            Tipo_Operacao='INCLUSAO',
            Status='Pendente',
            origem='MANUAL',
            Data=data_ajuste,
            Conta=str(d.get('Conta')).strip() if d.get('Conta') else None,
            Titulo_Conta=d.get('Titulo_Conta') or d.get('Título Conta'),
            Centro_Custo=limpar_int(d.get('Centro de Custo') or d.get('Centro_Custo')),
            Numero=d.get('Numero'),
            Descricao=d.get('Descricao'),
            Contra_Partida_Credito=d.get('Contra_Partida') or d.get('Contra Partida - Credito'),
            Filial=limpar_int(d.get('Filial')),
            Item=d.get('Item'),
            Cod_Cl_Valor=d.get('Cod_Cl_Valor') or d.get('Cod Cl. Valor'),
            Debito=float(d.get('Debito') or 0),
            Credito=float(d.get('Credito') or 0),
            Invalido=False,
            Is_Nao_Operacional=parse_bool(d.get('NaoOperacional')),
            Exibir_Saldo=True
        )

        self.session.add(novo_registro)
        self.session.flush() 
        
        log = CtlAjusteLog(
            Id_Registro=novo_registro.Id, Fonte_Registro=novo_registro.Fonte,
            Campo_Alterado='TODOS', Valor_Antigo='-', Valor_Novo='CRIADO_MANUALMENTE', 
            Usuario_Acao=usuario, Data_Acao=now, Tipo_Acao='INCLUSAO'
        )
        self.session.add(log)
        self.session.commit()
        return novo_registro.Id
    
    def SalvarAjuste(self, payload, usuario):
        RegistrarLog(f"Iniciando SalvarAjuste. Usuario: {usuario}", "SERVICE")
        
        d = payload.get('Dados', {})
        reg_id = d.get('Id') or payload.get('Id')
        reg_fonte = d.get('Fonte') or payload.get('Fonte')

        if not reg_id or not reg_fonte:
            raise Exception("Id e Fonte são obrigatórios para atualizar um registo.")

        registro = self.session.query(CtlRazaoConsolidado).filter_by(Id=reg_id, Fonte=reg_fonte).first()
        
        if not registro:
            raise Exception("Registo não encontrado na base de dados.")

        # Regista o log antes de alterar
        self._RegistrarLog(registro, d, usuario)

        if registro.Tipo_Operacao != 'INCLUSAO':
            registro.Tipo_Operacao = 'EDICAO'

        registro.Status = 'Pendente'
        
        # Função para limpar colunas numéricas sem sobrescrever com nulo se não enviado
        def limpar_int(val, default):
            if val is None: return default
            return int(val) if str(val).strip() else None

        if 'origem' in d: registro.origem = d.get('origem')
        if d.get('Conta') is not None: registro.Conta = str(d.get('Conta')).strip()
        
        if 'Titulo_Conta' in d or 'Título Conta' in d:
            registro.Titulo_Conta = d.get('Titulo_Conta') or d.get('Título Conta')
            
        cc_input = d.get('Centro de Custo') if 'Centro de Custo' in d else d.get('Centro_Custo')
        registro.Centro_Custo = limpar_int(cc_input, registro.Centro_Custo)
        
        data_raw = d.get('Data')
        if data_raw:
            try: registro.Data = parser.parse(str(data_raw))
            except:
                if 'T' in str(data_raw): registro.Data = datetime.datetime.strptime(data_raw.split('T')[0], '%Y-%m-%d')

        if 'Numero' in d: registro.Numero = d.get('Numero')
        if 'Descricao' in d: registro.Descricao = d.get('Descricao')
        
        cp_input = d.get('Contra_Partida') if 'Contra_Partida' in d else d.get('Contra Partida - Credito')
        if cp_input is not None: registro.Contra_Partida_Credito = cp_input
        
        if 'Filial' in d: registro.Filial = limpar_int(d.get('Filial'), registro.Filial)
        if 'Item' in d: registro.Item = d.get('Item')
        
        cl_input = d.get('Cod_Cl_Valor') if 'Cod_Cl_Valor' in d else d.get('Cod Cl. Valor')
        if cl_input is not None: registro.Cod_Cl_Valor = cl_input
        
        if 'Debito' in d: registro.Debito = float(d.get('Debito') or 0)
        if 'Credito' in d: registro.Credito = float(d.get('Credito') or 0)
        
        if 'Invalido' in d: registro.Invalido = parse_bool(d.get('Invalido'))
        if 'NaoOperacional' in d: registro.Is_Nao_Operacional = parse_bool(d.get('NaoOperacional'))
        if 'Exibir_Saldo' in d: registro.Exibir_Saldo = parse_bool(d.get('Exibir_Saldo', True))
        
        self.session.commit()
        return registro.Id
    
    def _ReverterEdicoesPendentes(self, registro):
        """
        Lê o histórico de logs em ordem decrescente (do mais novo para o mais velho)
        e desfaz todas as edições feitas desde a última vez que o registo esteve fechado.
        """
        # 1. Encontra o momento do último "Fechamento" (Aprovação, Reprovação, Inclusão, etc.)
        ultimo_fechamento = self.session.query(CtlAjusteLog).filter_by(
            Id_Registro=registro.Id, Fonte_Registro=registro.Fonte
        ).filter(
            CtlAjusteLog.Tipo_Acao.in_(['APROVACAO', 'REPROVACAO', 'INCLUSAO'])
        ).order_by(CtlAjusteLog.Data_Acao.desc()).first()

        data_corte = ultimo_fechamento.Data_Acao if ultimo_fechamento else datetime.datetime.min

        # 2. Pega todas as edições feitas DEPOIS desse momento, do mais recente para o mais antigo (DESC)
        logs_edicao = self.session.query(CtlAjusteLog).filter_by(
            Id_Registro=registro.Id, Fonte_Registro=registro.Fonte
        ).filter(
            CtlAjusteLog.Tipo_Acao == 'EDICAO',
            CtlAjusteLog.Data_Acao >= data_corte
        ).order_by(CtlAjusteLog.Id_Log.desc()).all()

        # 3. Restaura os valores antigos campo a campo, convertendo do texto do Log para o tipo real
        for log in logs_edicao:
            campo = log.Campo_Alterado
            v_antigo = log.Valor_Antigo

            if not hasattr(registro, campo):
                continue

            if campo in ['Debito', 'Credito']:
                setattr(registro, campo, float(v_antigo) if v_antigo and v_antigo != '-' else 0.0)
            elif campo in ['Is_Nao_Operacional', 'Exibir_Saldo', 'Invalido']:
                setattr(registro, campo, (v_antigo == 'Sim'))
            elif campo == 'Data':
                try:
                    if v_antigo and v_antigo != '-':
                        from dateutil import parser
                        setattr(registro, campo, parser.parse(v_antigo))
                except:
                    pass
            else:
                setattr(registro, campo, v_antigo if v_antigo != '-' else None)
        
        # 4. Recalcula o saldo após voltar os valores
        registro.Saldo = (float(registro.Debito or 0) - float(registro.Credito or 0)) if registro.Exibir_Saldo else 0.0


    def AprovarAjuste(self, reg_id, reg_fonte, acao, usuario):
        registro = self.session.query(CtlRazaoConsolidado).filter_by(Id=reg_id, Fonte=reg_fonte).first()
        if not registro:
            raise Exception("Registo não encontrado.")

        novo_status = 'Aprovado' if acao == 'Aprovar' else 'Reprovado'

        # --- LÓGICA DE REVERSÃO SE REJEITADO ---
        if acao == 'Reprovar':
            if registro.Tipo_Operacao == 'INCLUSAO':
                # Se era uma inclusão manual e foi rejeitada, ela morre aqui.
                registro.Invalido = True
                novo_status = 'Invalido'
            else:
                # Se era uma edição, revertemos os dados na máquina do tempo!
                self._ReverterEdicoesPendentes(registro)
                
                # Como os dados voltaram a ser os corretos (antigos), o status volta a Aprovado
                novo_status = 'Aprovado'
                registro.Criado_Por = 'Sistema'
                registro.Aprovado_Por = 'Sistema'
                
                # Se for do ERP, garante que a operação é tida como ORIGINAL novamente
                if registro.Fonte in ['FARMA', 'FARMADIST', 'INTEC']:
                    registro.Tipo_Operacao = 'ORIGINAL'
        
        # Regista a ação de aprovação/rejeição no Log
        log = CtlAjusteLog(
            Id_Registro=registro.Id, Fonte_Registro=registro.Fonte,
            Campo_Alterado='Status', Valor_Antigo=registro.Status or '', Valor_Novo=novo_status, 
            Usuario_Acao=usuario, Data_Acao=datetime.datetime.now(), Tipo_Acao='APROVACAO' if acao == 'Aprovar' else 'REPROVACAO'
        )
        self.session.add(log)
        
        registro.Status = novo_status
        if acao == 'Aprovar':
            registro.Aprovado_Por = usuario
        
        registro.Data_Aprovacao = datetime.datetime.now()
        self.session.commit()

    def ToggleInvalido(self, reg_id, reg_fonte, acao, usuario):
        registro = self.session.query(CtlRazaoConsolidado).filter_by(Id=reg_id, Fonte=reg_fonte).first()
        if not registro: raise Exception('Registo não encontrado')
        
        novo_estado_invalido = (acao == 'INVALIDAR')
        
        # Inteligência de Restauração: 
        # Se eu invalidar -> Fica 'Invalido'
        # Se eu restaurar algo 'ORIGINAL' -> Volta a ser 'Aprovado'
        # Se eu restaurar um ajuste/inclusão -> Volta a ser 'Pendente' (precisa ser reavaliado)
        if novo_estado_invalido:
            novo_status = 'Invalido'
        else:
            novo_status = 'Aprovado' if registro.Tipo_Operacao == 'ORIGINAL' else 'Pendente'

        log = CtlAjusteLog(
            Id_Registro=registro.Id, Fonte_Registro=registro.Fonte,
            Campo_Alterado='Invalido', Valor_Antigo=str(registro.Invalido), Valor_Novo=str(novo_estado_invalido),
            Usuario_Acao=usuario, Data_Acao=datetime.datetime.now(),
            Tipo_Acao='INVALIDACAO' if novo_estado_invalido else 'RESTAURACAO'
        )
        self.session.add(log)
        
        # Aplica as mudanças
        registro.Invalido = novo_estado_invalido
        registro.Status = novo_status
        
        # Se restaurou um dado Original do ERP, diz que quem aprovou foi o sistema
        if not novo_estado_invalido and registro.Tipo_Operacao == 'ORIGINAL':
            registro.Aprovado_Por = 'Sistema'
            
        self.session.commit()

    def ObterHistorico(self, reg_id, reg_fonte):
        logs = self.session.query(CtlAjusteLog).filter_by(Id_Registro=reg_id, Fonte_Registro=reg_fonte).order_by(CtlAjusteLog.Data_Acao.desc()).all()
        return [{
            'Id_Log': l.Id_Log, 'Campo': l.Campo_Alterado, 'De': l.Valor_Antigo, 'Para': l.Valor_Novo,
            'Usuario': l.Usuario_Acao, 'Data': l.Data_Acao.strftime('%d/%m/%Y %H:%M:%S'), 'Tipo': l.Tipo_Acao
        } for l in logs]

    # =========================================================================
    # PROCESSAMENTO DE INTERGRUPOS (Lançam direto na Consolidada)
    # =========================================================================
    def ProcessarIntergrupoIntec(self, ano, mes, data_gravacao):
        # A lógica de leitura do CSV mantém-se igual
        try:
            meses_map = {1: 'jan', 2: 'fev', 3: 'mar', 4: 'abr', 5: 'mai', 6: 'jun', 7: 'jul', 8: 'ago', 9: 'set', 10: 'out', 11: 'nov', 12: 'dez'}
            competencia_anomes = f"{ano}-{meses_map[mes]}"
            caminho_csv = os.path.join(BaseConfig().DataCSVPath(), "ValorFinanceiro.csv")
            
            if not os.path.exists(caminho_csv):
                 return ["Erro: Arquivo ValorFinanceiro.csv não encontrado."]

            df_csv = pd.read_csv(caminho_csv, sep=';', encoding='utf-8-sig', low_memory=False)
            if len(df_csv.columns) <= 1: 
                df_csv = pd.read_csv(caminho_csv, sep=',', encoding='utf-8-sig', low_memory=False)

            def limpar_coluna(col): return col.strip().replace('Ï»¿', '').replace('\ufeff', '').upper()
            df_csv.columns = [limpar_coluna(c) for c in df_csv.columns]
            
            if 'INTERGROUP' not in df_csv.columns: return [f"Erro: Coluna INTERGROUP inexistente. Verifique o CSV."]

            if 'VALORFINANCEIRO' in df_csv.columns:
                if df_csv['VALORFINANCEIRO'].dtype == object: df_csv['VALORFINANCEIRO'] = df_csv['VALORFINANCEIRO'].astype(str).str.replace('.', '').str.replace(',', '.')
                df_csv['VALORFINANCEIRO'] = pd.to_numeric(df_csv['VALORFINANCEIRO'], errors='coerce').fillna(0.0)
            
            df_novo_filtro = df_csv[(df_csv['MODAL'].str.upper() == 'AEREO') & (df_csv['EMPRESA'].str.upper() == 'INTEC') & (df_csv['INTERGROUP'].str.upper().isin(['S', 'N'])) & (df_csv['ANOMES'] == competencia_anomes)]
            v_aereo_intec_especifico = df_novo_filtro['VALORFINANCEIRO'].sum()

            df_filtrado_s = df_csv[(df_csv['INTERGROUP'].str.upper() == 'S') & (df_csv['EMPRESA'].str.upper() == 'INTEC') & (df_csv['ANOMES'] == competencia_anomes)]
            v_rodoviario = df_filtrado_s[df_filtrado_s['MODAL'].str.upper() == 'RODOVIARIO']['VALORFINANCEIRO'].sum()
            v_aereo = df_filtrado_s[df_filtrado_s['MODAL'].str.upper() == 'AEREO']['VALORFINANCEIRO'].sum()

            if v_rodoviario == 0 and v_aereo == 0 and v_aereo_intec_especifico == 0: return []

            # Busca template na própria base consolidada
            template = self.session.query(CtlRazaoConsolidado).filter_by(origem='INTEC', Conta='60101010201').order_by(CtlRazaoConsolidado.Data.desc()).first()
            if not template: return ["Template INTEC não encontrado"]

            logs_intec = []
            lancamentos = [
                {'modal': 'AEREO', 'valor': v_aereo_intec_especifico, 'conta': '60101010201', 'tipo': 'D', 'sufixo': 'DEBITO'},
                {'modal': 'AEREO', 'valor': v_aereo_intec_especifico, 'conta': '60101010201A', 'tipo': 'C', 'sufixo': 'CREDITO'},
                {'modal': 'RODOVIARIO', 'valor': v_rodoviario, 'conta': '60101010201', 'tipo': 'D', 'sufixo': 'D'},
                {'modal': 'AEREO', 'valor': v_aereo, 'conta': '60101010201A', 'tipo': 'D', 'sufixo': 'D'},
                {'modal': 'RODOVIARIO', 'valor': v_rodoviario, 'conta': '60101010201B', 'tipo': 'C', 'sufixo': 'C'},
                {'modal': 'AEREO', 'valor': v_aereo, 'conta': '60101010201C', 'tipo': 'C', 'sufixo': 'C'}
            ]

            max_id = self.session.query(func.max(CtlRazaoConsolidado.Id)).filter(CtlRazaoConsolidado.Fonte == 'INTERGRUPO_INTEC').scalar() or 0

            for lanc in lancamentos:
                if lanc['valor'] > 0:
                    v_abs = round(abs(lanc['valor']), 2)
                    val_debito = v_abs if lanc['tipo'] == 'D' else 0.0
                    val_credito = v_abs if lanc['tipo'] == 'C' else 0.0
                    desc_final = f"INTERGRUPO INTEC - {lanc['modal']} - {competencia_anomes} ({lanc['sufixo']})"

                    # Procura se o registo já existe na consolidada
                    reg_existente = self.session.query(CtlRazaoConsolidado).filter_by(
                        Fonte='INTERGRUPO_INTEC', Conta=lanc['conta'], Descricao=desc_final, Data=data_gravacao
                    ).first()

                    if reg_existente:
                        valor_atual = reg_existente.Debito if lanc['tipo'] == 'D' else reg_existente.Credito
                        if abs(valor_atual - v_abs) > 0.01:
                            if lanc['tipo'] == 'D': reg_existente.Debito = v_abs
                            else: reg_existente.Credito = v_abs
                            logs_intec.append(f"[{competencia_anomes}] {lanc['modal']} {lanc['sufixo']}: Atualizado para {v_abs}")
                    else:
                        max_id += 1
                        novo_reg = CtlRazaoConsolidado(
                            Id=max_id, Fonte='INTERGRUPO_INTEC', origem='INTEC',
                            Conta=lanc['conta'], Titulo_Conta=template.Titulo_Conta or 'VENDA DE FRETES',
                            Data=data_gravacao, Descricao=desc_final, Debito=val_debito, Credito=val_credito,
                            Filial=template.Filial, Centro_Custo=template.Centro_Custo, Item='INTERGRUPO',
                            Tipo_Operacao='INTERGRUPO_AUTO', Status='Aprovado', Invalido=False,
                            Criado_Por='SISTEMA_AUTO', Data_Aprovacao=datetime.datetime.now(), Exibir_Saldo=True
                        )
                        self.session.add(novo_reg)
                        logs_intec.append(f"[{competencia_anomes}] {lanc['modal']} {lanc['sufixo']}: Criado {v_abs}")
            
            return logs_intec

        except Exception as e:
            return [f"ERRO CRÍTICO INTEC: {str(e)}"]
        
    def ProcessarIntergrupoFarma(self, ano, mes, data_inicio, data_fim, data_gravacao):
        logs_farma = []
        try:
            config_contas_banco = {
                '60301020290': {'destino': '60301020290B', 'descricao': 'ajuste intergrupo ( fretes Dist.)', 'titulo_origem': 'FRETE DISTRIBUIÇÃO', 'titulo_destino': 'FRETE DISTRIBUIÇÃO'},
                '60301020288': {'destino': '60301020288C', 'descricao': 'ajuste intergrupo ( fretes Aéreo)', 'titulo_origem': 'FRETES AEREO', 'titulo_destino': 'FRETES AEREO'}
            }
            
            max_id = self.session.query(func.max(CtlRazaoConsolidado.Id)).filter(CtlRazaoConsolidado.Fonte == 'INTERGRUPO_FARMA').scalar() or 0

            for conta_origem, config in config_contas_banco.items():
                registros = self.session.query(CtlRazaoConsolidado).filter(
                    CtlRazaoConsolidado.Conta == conta_origem,
                    CtlRazaoConsolidado.Data >= data_inicio,
                    CtlRazaoConsolidado.Data <= data_fim,
                    CtlRazaoConsolidado.origem != 'INTEC'
                ).all()

                agrupado_por_origem = {}

                for r in registros:
                    descricao_texto = str(r.Descricao or '').upper()
                    if "INTEC" in descricao_texto:
                        orig = r.origem
                        if orig not in agrupado_por_origem:
                            agrupado_por_origem[orig] = { 'deb': 0.0, 'cred': 0.0, 'item': r.Item, 'filial': r.Filial, 'cc': r.Centro_Custo, 'origem': orig }
                        
                        agrupado_por_origem[orig]['deb'] += float(r.Debito or 0.0)
                        agrupado_por_origem[orig]['cred'] += float(r.Credito or 0.0)
                        
                        if not agrupado_por_origem[orig]['filial'] and r.Filial: agrupado_por_origem[orig]['filial'] = r.Filial
                        if not agrupado_por_origem[orig]['cc'] and r.Centro_Custo: agrupado_por_origem[orig]['cc'] = r.Centro_Custo
                        if not agrupado_por_origem[orig]['item'] and r.Item: agrupado_por_origem[orig]['item'] = r.Item

                for orig, dados in agrupado_por_origem.items():
                    if not dados['deb'] and not dados['cred']: continue
                    
                    valor_ajuste = round(abs(dados['deb'] - dados['cred']), 2)
                    if valor_ajuste <= 0: continue
                    
                    # Procura se já existe na Tabela Consolidada o destino
                    reg_destino_existente = self.session.query(CtlRazaoConsolidado).filter_by(
                        Fonte='INTERGRUPO_FARMA', origem=dados['origem'], Conta=config['destino'], Data=data_gravacao
                    ).first()

                    if reg_destino_existente:
                        if abs(reg_destino_existente.Debito - valor_ajuste) > 0.01:
                             reg_destino_existente.Debito = valor_ajuste
                             
                             reg_origem_existente = self.session.query(CtlRazaoConsolidado).filter_by(
                                 Fonte='INTERGRUPO_FARMA', origem=dados['origem'], Conta=conta_origem, Data=data_gravacao
                             ).first()
                             if reg_origem_existente: reg_origem_existente.Credito = valor_ajuste
                             logs_farma.append(f"[{mes:02d}/{ano}] {dados['origem']}: Atualizado {config['destino']} v:{valor_ajuste}")
                    else:
                        max_id += 1
                        aj_origem = CtlRazaoConsolidado(
                            Id=max_id, Fonte='INTERGRUPO_FARMA', origem=dados['origem'],
                            Conta=conta_origem, Titulo_Conta=config['titulo_origem'], Data=data_gravacao,
                            Descricao=config['descricao'], Debito=0.0, Credito=valor_ajuste,
                            Filial=dados['filial'], Centro_Custo=dados['cc'], Item=dados['item'],
                            Tipo_Operacao='INTERGRUPO_AUTO', Status='Aprovado', Criado_Por='SISTEMA_AUTO', Exibir_Saldo=True
                        )
                        max_id += 1
                        aj_destino = CtlRazaoConsolidado(
                            Id=max_id, Fonte='INTERGRUPO_FARMA', origem=dados['origem'],
                            Conta=config['destino'], Titulo_Conta=config['titulo_destino'], Data=data_gravacao,
                            Descricao=config['descricao'], Debito=valor_ajuste, Credito=0.0,
                            Filial=dados['filial'], Centro_Custo=dados['cc'], Item=dados['item'],
                            Tipo_Operacao='INTERGRUPO_AUTO', Status='Aprovado', Criado_Por='SISTEMA_AUTO', Exibir_Saldo=True
                        )
                        self.session.add(aj_origem)
                        self.session.add(aj_destino)
                        logs_farma.append(f"[{mes:02d}/{ano}] {dados['origem']}: Criado {conta_origem} -> {config['destino']} v:{valor_ajuste}")

            # PARTE 2: CSV
            meses_map = {1: 'jan', 2: 'fev', 3: 'mar', 4: 'abr', 5: 'mai', 6: 'jun', 7: 'jul', 8: 'ago', 9: 'set', 10: 'out', 11: 'nov', 12: 'dez'}
            competencia_anomes = f"{ano}-{meses_map[mes]}"
            caminho_csv = os.path.join(BaseConfig().DataCSVPath(), "ValorFinanceiro.csv")
            
            if os.path.exists(caminho_csv):
                df_csv = pd.read_csv(caminho_csv, sep=';', encoding='utf-8-sig', low_memory=False)
                if len(df_csv.columns) <= 1: df_csv = pd.read_csv(caminho_csv, sep=',', encoding='utf-8-sig', low_memory=False)

                def limpar_coluna(col): return col.strip().replace('Ï»¿', '').replace('\ufeff', '').upper()
                df_csv.columns = [limpar_coluna(c) for c in df_csv.columns]
                
                if 'VALORFINANCEIRO' in df_csv.columns:
                    if df_csv['VALORFINANCEIRO'].dtype == object: df_csv['VALORFINANCEIRO'] = df_csv['VALORFINANCEIRO'].astype(str).str.replace('.', '').str.replace(',', '.')
                    df_csv['VALORFINANCEIRO'] = pd.to_numeric(df_csv['VALORFINANCEIRO'], errors='coerce').fillna(0.0)

                if all(c in df_csv.columns for c in ['MODAL', 'EMPRESA', 'ANOMES']):
                    df_farma_aereo = df_csv[(df_csv['MODAL'].str.upper() == 'AEREO') & (df_csv['EMPRESA'].str.upper() == 'FARMA') & (df_csv['ANOMES'] == competencia_anomes)]
                    valor_csv_farma = round(df_farma_aereo['VALORFINANCEIRO'].sum(), 2)
                    
                    if valor_csv_farma > 0:
                        template = self.session.query(CtlRazaoConsolidado).filter_by(origem='FARMA', Conta='60101010201').first()
                        desc_csv = 'VLR. CFE DIARIO AUXILIAR N/ DATA (aéreo)'

                        lancamentos = [
                            {'valor': valor_csv_farma, 'conta': '60101010201', 'tipo': 'D', 'sufixo': 'DEBITO'},
                            {'valor': valor_csv_farma, 'conta': '60101010201A', 'tipo': 'C', 'sufixo': 'CREDITO'}
                        ]

                        for lanc in lancamentos:
                            v_abs = round(abs(lanc['valor']), 2)
                            val_debito = v_abs if lanc['tipo'] == 'D' else 0.0
                            val_credito = v_abs if lanc['tipo'] == 'C' else 0.0

                            reg_existente = self.session.query(CtlRazaoConsolidado).filter_by(
                                Fonte='INTERGRUPO_FARMA', Conta=lanc['conta'], Descricao=desc_csv, Data=data_gravacao
                            ).first()

                            if reg_existente:
                                valor_atual = reg_existente.Debito if lanc['tipo'] == 'D' else reg_existente.Credito
                                if abs(valor_atual - v_abs) > 0.01:
                                    if lanc['tipo'] == 'D': reg_existente.Debito = v_abs
                                    else: reg_existente.Credito = v_abs
                                    logs_farma.append(f"[{mes:02d}/{ano}] FARMA (CSV) {lanc['sufixo']}: Atualizado {lanc['conta']} para {v_abs}")
                            else:
                                max_id += 1
                                novo_ajuste = CtlRazaoConsolidado(
                                    Id=max_id, Fonte='INTERGRUPO_FARMA', origem='FARMA',
                                    Conta=lanc['conta'], Titulo_Conta='VENDA DE FRETES', Data=data_gravacao,
                                    Descricao=desc_csv, Debito=val_debito, Credito=val_credito,
                                    Filial=template.Filial if template else None, 
                                    Centro_Custo=template.Centro_Custo if template else None, 
                                    Tipo_Operacao='INTERGRUPO_AUTO', Status='Aprovado', Criado_Por='SISTEMA_AUTO_CSV', Exibir_Saldo=True
                                )
                                self.session.add(novo_ajuste)
                                logs_farma.append(f"[{mes:02d}/{ano}] FARMA (CSV) {lanc['sufixo']}: Criado {lanc['conta']} v:{v_abs}")
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
            
            # Conta na base de dados quantos intergrupos existem (para validação)
            qtd_registros = self.session.query(CtlRazaoConsolidado).filter(
                CtlRazaoConsolidado.Tipo_Operacao == 'INTERGRUPO_AUTO',
                text(f"EXTRACT(MONTH FROM \"Data\") = {mes}"),
                text(f"EXTRACT(YEAR FROM \"Data\") = {ano}")
            ).count()

            if qtd_registros < 12:
                aviso = f"ATENÇÃO CRÍTICA: Processo gerou apenas {qtd_registros} registros. Esperado no mínimo 12."
                logs_totais.append(aviso)
            else:
                logs_totais.append(f"Sucesso: {qtd_registros} registros intergrupo processados na Consolidada.")

            return logs_totais

        except Exception as e:
            self.session.rollback() 
            raise e