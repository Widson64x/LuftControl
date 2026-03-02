import datetime
import calendar
from dateutil import parser
import hashlib
import os
import pandas as pd
from sqlalchemy import text
from Models.POSTGRESS.Ajustes import AjustesRazao, AjustesLog
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
        """
        Inicializa o serviço de Ajustes Manuais.
        
        Args:
            session_db: Sessão ativa da base de dados PostgreSQL.
        """
        self.session = session_db
        self.engine = GetPostgresEngine()
        self.schema = "Dre_Schema"

    # --- HELPERS INTERNOS ---

    def _RegistrarLog(self, ajuste_antigo, dados_novos, usuario):
        """
        Gera e regista logs de auditoria detalhados comparando o objeto atual da base de dados 
        (ajuste_antigo) com os novos dados recebidos (dados_novos).
        
        Args:
            ajuste_antigo (AjustesRazao): O objeto de ajuste como se encontra atualmente na base de dados.
            dados_novos (dict): Dicionário contendo os novos dados vindos do frontend.
            usuario (str): Identificação do utilizador que está a realizar a alteração.
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
        """
        Gera um hash MD5 único para uma linha de intergrupo baseando-se nos campos chave.
        Garante a correta identificação da linha e previne duplicações na base de dados.
        
        Args:
            row (dict): Dicionário com os dados da linha.
            
        Returns:
            str: Hash MD5 gerado a partir dos valores concatenados.
        """
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
        """
        Obtém e consolida os dados necessários para exibir na grelha (grid) principal.
        Cruza os dados da vista (view) consolidada com os ajustes manuais e automáticos registados,
        gerando linhas adicionais para novas inclusões e modificando as linhas originais conforme editadas.
        
        Returns:
            list[dict]: Lista de dicionários correspondentes a cada linha da grelha.
        """
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
        Cria um novo ajuste manual a partir do zero (INCLUSÃO pura).
        Gera um Hash novo baseado no conteúdo para garantir a unicidade.
        
        Args:
            payload (dict): Os dados enviados pela interface.
            usuario (str): Identificação do utilizador que realizou a ação.
            
        Returns:
            int: O ID do ajuste gerado na base de dados.
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
        """
        Guarda as alterações realizadas num ajuste existente (EDIÇÃO) ou salva uma inclusão 
        proveniente de outro fluxo. Atualiza os dados se a linha já existir ou cria uma nova 
        se for referenciada pela primeira vez.
        
        Args:
            payload (dict): Os dados enviados pela interface.
            usuario (str): Identificação do utilizador que realizou a ação.
            
        Returns:
            int: O ID do ajuste manipulado.
        """
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
        """
        Altera o estado de um ajuste para 'Aprovado' ou 'Reprovado'.
        
        Args:
            ajuste_id (int): ID do ajuste a ser processado.
            acao (str): Ação executada ('Aprovar' ou outra que resulta em 'Reprovado').
            usuario (str): Identificação do utilizador que aprovou.
        """
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
        """
        Alterna a flag 'Invalido' num ajuste, desativando ou reativando o mesmo.
        
        Args:
            ajuste_id (int): ID do ajuste.
            acao (str): Ação ('INVALIDAR' para definir como inválido).
            usuario (str): Identificação do utilizador.
        """
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
        """
        Devolve o histórico de logs/alterações efetuadas sobre um determinado ajuste.
        
        Args:
            ajuste_id (int): ID do ajuste.
            
        Returns:
            list[dict]: Lista cronológica (mais recente primeiro) contendo os logs formatados.
        """
        logs = self.session.query(AjustesLog).filter(AjustesLog.Id_Ajuste == ajuste_id).order_by(AjustesLog.Data_Acao.desc()).all()
        return [{
            'Id_Log': l.Id_Log, 'Campo': l.Campo_Alterado, 'De': l.Valor_Antigo, 'Para': l.Valor_Novo,
            'Usuario': l.Usuario_Acao, 'Data': l.Data_Acao.strftime('%d/%m/%Y %H:%M:%S'), 'Tipo': l.Tipo_Acao
        } for l in logs]

    # --- PROCESSAMENTO INTERGRUPO ---
    def ProcessarIntergrupoIntec(self, ano, mes, data_gravacao):
        """
        Realiza a leitura e processamento do ficheiro ValorFinanceiro.csv da empresa INTEC.
        Filtra os modais (Aéreo e Rodoviário) e gera as rubricas (Débito e Crédito) necessárias
        para regularização financeira intergrupo de forma automática.
        
        Args:
            ano (int): Ano de processamento.
            mes (int): Mês de processamento.
            data_gravacao (datetime): Data em que o lançamento deve ser registado na DRE.
            
        Returns:
            list[str]: Lista de mensagens de log descrevendo o que foi gerado/atualizado.
        """
        try:
            meses_map = {
                1: 'jan', 2: 'fev', 3: 'mar', 4: 'abr', 5: 'mai', 6: 'jun', 
                7: 'jul', 8: 'ago', 9: 'set', 10: 'out', 11: 'nov', 12: 'dez'
            }
            competencia_anomes = f"{ano}-{meses_map[mes]}"
            
            caminho_csv = os.path.join(BaseConfig().DataQVDPath(), "ValorFinanceiro.csv")
            
            if not os.path.exists(caminho_csv):
                 RegistrarLog(f"Arquivo CSV não encontrado: {caminho_csv}", "ERROR")
                 return ["Erro: Arquivo ValorFinanceiro.csv não encontrado."]

            # --- LEITURA ROBUSTA DE CSV (BOM FIX) ---
            df_qvd = None
            erros_leitura = []
            
            # Tentativa 1: UTF-8-SIG (Remove o BOM automaticamente) com ponto e vírgula
            try:
                df_qvd = pd.read_csv(caminho_csv, sep=';', encoding='utf-8-sig', low_memory=False)
                if len(df_qvd.columns) <= 1: # Se falhar o separador
                    df_qvd = pd.read_csv(caminho_csv, sep=',', encoding='utf-8-sig', low_memory=False)
            except Exception as e:
                erros_leitura.append(f"UTF-8-SIG: {e}")

            # Tentativa 2: Latin1 (Caso não seja UTF-8) se a anterior falhou ou não carregou colunas
            if df_qvd is None or len(df_qvd.columns) <= 1:
                try:
                    df_qvd = pd.read_csv(caminho_csv, sep=';', encoding='latin1', low_memory=False)
                    if len(df_qvd.columns) <= 1:
                         df_qvd = pd.read_csv(caminho_csv, sep=',', encoding='latin1', low_memory=False)
                except Exception as e:
                    erros_leitura.append(f"Latin1: {e}")
                    RegistrarLog(f"Falha leitura CSV: {erros_leitura}", "ERROR")
                    return [f"Erro leitura CSV. Detalhes no log."]

            # --- LIMPEZA DE COLUNAS (CRÍTICO) ---
            # Remove espaços e caracteres de BOM (Ï»¿ ou \ufeff) que possam ter sobrado
            def limpar_coluna(col):
                c = col.strip()
                c = c.replace('Ï»¿', '') # BOM visto como Latin1
                c = c.replace('\ufeff', '') # BOM Unicode
                return c.upper()

            df_qvd.columns = [limpar_coluna(c) for c in df_qvd.columns]
            
            # Validação Final das Colunas
            if 'INTERGROUP' not in df_qvd.columns:
                colunas_encontradas = ", ".join(df_qvd.columns)
                RegistrarLog(f"Coluna 'INTERGROUP' não encontrada após limpeza. Cols: [{colunas_encontradas}]", "ERROR")
                return [f"Erro: Coluna INTERGROUP inexistente. Verifique o CSV."]

            if 'VALORFINANCEIRO' in df_qvd.columns:
                if df_qvd['VALORFINANCEIRO'].dtype == object:
                     df_qvd['VALORFINANCEIRO'] = df_qvd['VALORFINANCEIRO'].astype(str).str.replace('.', '').str.replace(',', '.')
                df_qvd['VALORFINANCEIRO'] = pd.to_numeric(df_qvd['VALORFINANCEIRO'], errors='coerce').fillna(0.0)
            
            # --- FILTROS ---
            cols_req = ['MODAL', 'EMPRESA', 'INTERGROUP', 'ANOMES']
            for c in cols_req:
                if c not in df_qvd.columns:
                    return [f"Coluna obrigatória não encontrada: {c}"]

            # Filtro 1: Aereo Intec Específico
            # Condições: Apenas o modal AEREO, Empresa INTEC, marcadores de intergroup específicos 'S' ou 'N', dentro da competência (Mês/Ano).
            df_novo_filtro = df_qvd[
                (df_qvd['MODAL'].str.upper() == 'AEREO') & 
                (df_qvd['EMPRESA'].str.upper() == 'INTEC') & 
                (df_qvd['INTERGROUP'].str.upper().isin(['S', 'N'])) & 
                (df_qvd['ANOMES'] == competencia_anomes)
            ]
            v_aereo_intec_especifico = df_novo_filtro['VALORFINANCEIRO'].sum()

            # Filtro 2: Padrão (Intergroup = S)
            # Condições: Filtro genérico que apenas olha para o INTERGROUP marcado com 'S' na Empresa INTEC para a dada competência.
            df_filtrado_s = df_qvd[
                (df_qvd['INTERGROUP'].str.upper() == 'S') & 
                (df_qvd['EMPRESA'].str.upper() == 'INTEC') & 
                (df_qvd['ANOMES'] == competencia_anomes)
            ]
            
            # Sub-agrupamentos do Filtro 2 (por tipo de MODAL):
            v_rodoviario = df_filtrado_s[df_filtrado_s['MODAL'].str.upper() == 'RODOVIARIO']['VALORFINANCEIRO'].sum()
            v_aereo = df_filtrado_s[df_filtrado_s['MODAL'].str.upper() == 'AEREO']['VALORFINANCEIRO'].sum()

            RegistrarLog(f"CSV Intec OK. Mês: {competencia_anomes} | Aereo(S/N): {v_aereo_intec_especifico} | Rodo(S): {v_rodoviario} | Aereo(S): {v_aereo}", "DEBUG")

            if v_rodoviario == 0 and v_aereo == 0 and v_aereo_intec_especifico == 0:
                RegistrarLog(f"Nenhum valor encontrado no CSV para {competencia_anomes}. Abortando Intec.", "WARNING")
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
            
            # --- COMENTÁRIO SOBRE AS REGRAS DOS LANÇAMENTOS INTERGRUPO ---
            # Aqui é onde ocorre o balanceamento financeiro intergrupo (débito/crédito).
            # Para cada cálculo extraído acima, é preciso realizar a "Perna a Débito" e a "Contra-partida a Crédito",
            # garantindo que o fecho contábil esteja equilibrado para o Modal / Filtro correspondente.
            lancamentos = [
                # >> FILTRO 1 (Aéreo Intec Específico: INTERGROUP in ('S', 'N'))
                # Lança o total de Aéreo Específico (v_aereo_intec_especifico) a Débito na conta '60101010201'
                {'modal': 'AEREO', 'valor': v_aereo_intec_especifico, 'conta': '60101010201', 'tipo': 'D', 'sufixo': 'DEBITO'},
                # Lança a contra-partida (Crédito) do Aéreo Específico na conta destino '60101010201A'
                {'modal': 'AEREO', 'valor': v_aereo_intec_especifico, 'conta': '60101010201A', 'tipo': 'C', 'sufixo': 'CREDITO'},
                
                # >> FILTRO 2 - Sub-agrupamento Rodoviário (INTERGROUP == 'S')
                # Lança o total Rodoviário (v_rodoviario) a Débito na conta principal '60101010201'
                {'modal': 'RODOVIARIO', 'valor': v_rodoviario, 'conta': '60101010201', 'tipo': 'D', 'sufixo': 'D'},
                
                # >> FILTRO 2 - Sub-agrupamento Aéreo (INTERGROUP == 'S')
                # Lança o total de Aéreo (v_aereo) a Débito na conta paralela '60101010201A'
                {'modal': 'AEREO', 'valor': v_aereo, 'conta': '60101010201A', 'tipo': 'D', 'sufixo': 'D'},
                
                # >> FILTRO 2 - CONTRA-PARTIDAS DE CRÉDITO (INTERGROUP == 'S')
                # Lança a contra-partida (Crédito) do Rodoviário na conta destino '60101010201B'
                {'modal': 'RODOVIARIO', 'valor': v_rodoviario, 'conta': '60101010201B', 'tipo': 'C', 'sufixo': 'C'},
                # Lança a contra-partida (Crédito) do Aéreo Padrão na conta destino '60101010201C'
                {'modal': 'AEREO', 'valor': v_aereo, 'conta': '60101010201C', 'tipo': 'C', 'sufixo': 'C'}
            ]

            for lanc in lancamentos:
                if lanc['valor'] > 0:
                    v_abs = round(abs(lanc['valor']), 2)
                    
                    val_debito = v_abs if lanc['tipo'] == 'D' else 0.0
                    val_credito = v_abs if lanc['tipo'] == 'C' else 0.0
                    
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

                    ajuste_existente = self.session.query(AjustesRazao).filter(
                        AjustesRazao.Origem == 'INTEC',
                        AjustesRazao.Conta == lanc['conta'],
                        AjustesRazao.Descricao == desc_final,
                        AjustesRazao.Tipo_Operacao == 'INTERGRUPO_AUTO'
                    ).first()

                    if ajuste_existente:
                        valor_atual = ajuste_existente.Debito if lanc['tipo'] == 'D' else ajuste_existente.Credito
                        if abs(valor_atual - v_abs) > 0.01:
                            if lanc['tipo'] == 'D':
                                ajuste_existente.Debito = v_abs
                            else:
                                ajuste_existente.Credito = v_abs
                                
                            ajuste_existente.Hash_Linha_Original = hash_val 
                            logs_intec.append(f"[{competencia_anomes}] {lanc['modal']} {lanc['sufixo']}: Atualizado para {v_abs}")
                    else:
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
                            Criado_Por='SISTEMA_AUTO', Data_Aprovacao=datetime.datetime.now(),
                            Exibir_Saldo=True
                        )
                        self.session.add(ajuste)
                        logs_intec.append(f"[{competencia_anomes}] {lanc['modal']} {lanc['sufixo']}: Criado {v_abs}")
            
            return logs_intec

        except Exception as e:
            RegistrarLog(f"Falha Crítica no INTEC CSV", "ERROR", e)
            return [f"ERRO CRÍTICO INTEC: {str(e)}"]
        
    def ProcessarIntergrupoFarma(self, ano, mes, data_inicio, data_fim, data_gravacao):
        """
        Processa as regras de intergrupo para a divisão Farma (tudo exceto INTEC).
        Faz o cruzamento de saldos de contas específicas.
        REGRA DE FILTRO: 
        - Contas gerais: Soma apenas lançamentos onde a coluna 'Descricao' contenha 'INTEC'.
        - Exceção: Para a conta '60101010201', o filtro de descrição é ignorado e tudo é somado.
        
        Args:
            ano (int): Ano para cálculo.
            mes (int): Mês para cálculo.
            data_inicio (datetime): Data de início do período (1º dia do mês).
            data_fim (datetime): Data de fim do período (Último dia do mês às 23:59:59).
            data_gravacao (datetime): Data em que o lançamento deve ser registado na DRE.
            
        Returns:
            list[str]: Logs contendo o resumo dos registos verificados, criados ou ajustados.
        """
        config_contas = {
            '60301020290': {'destino': '60301020290B', 'descricao': 'ajuste intergrupo ( fretes Dist.)', 'titulo_origem': 'FRETE DISTRIBUIÇÃO', 'titulo_destino': 'FRETE DISTRIBUIÇÃO'},
            '60301020288': {'destino': '60301020288C', 'descricao': 'ajuste intergrupo ( fretes Aéreo)', 'titulo_origem': 'FRETES AEREO', 'titulo_destino': 'FRETES AEREO'},
            '60101010201': {'destino': '60101010201A', 'descricao': 'VLR. CFE DIARIO AUXILIAR N/ DATA (aéreo)', 'titulo_origem': 'VENDA DE FRETES', 'titulo_destino': 'VENDA DE FRETES'}
        }
        
        logs_farma = []
        
        try:
            for conta_origem, config in config_contas.items():
                # Trazemos os dados sem agrupamento (SUM/GROUP BY) para garantir que
                # a verificação da descrição seja feita linha a linha no Python.
                sql = text(f"""
                    SELECT "origem", "Descricao", "Debito", "Credito", "Item", "Filial", "Centro de Custo" as cc
                    FROM "{self.schema}"."Razao_Dados_Consolidado"
                    WHERE "Conta" = :conta AND "Data" >= :d_ini AND "Data" <= :d_fim
                    AND "origem" NOT IN ('INTEC')
                """)
                
                rows = self.session.execute(sql, {'conta': conta_origem, 'd_ini': data_inicio, 'd_fim': data_fim}).fetchall()

                # Dicionário para agrupar e somar os valores apenas das linhas válidas
                agrupado_por_origem = {}

                for row in rows:
                    r_dict = dict(row._mapping)
                    descricao_texto = str(r_dict.get('Descricao') or '').upper()
                    
                    # FILTRO DE PRECISÃO NO CÓDIGO PYTHON
                    # Se a conta for 60101010201 OU a descrição contiver 'INTEC', a linha é processada
                    if conta_origem == '60101010201' or "INTEC" in descricao_texto:
                        orig = r_dict.get('origem')
                        
                        if orig not in agrupado_por_origem:
                            agrupado_por_origem[orig] = {
                                'deb': 0.0,
                                'cred': 0.0,
                                'item': r_dict.get('Item'),
                                'filial': r_dict.get('Filial'),
                                'cc': r_dict.get('cc'),
                                'origem': orig
                            }
                        
                        # Soma os valores para essa origem
                        agrupado_por_origem[orig]['deb'] += float(r_dict.get('Debito') or 0.0)
                        agrupado_por_origem[orig]['cred'] += float(r_dict.get('Credito') or 0.0)
                        
                        # Preenche os dados mestre se por acaso o primeiro registro vier vazio
                        if not agrupado_por_origem[orig]['filial'] and r_dict.get('Filial'): 
                            agrupado_por_origem[orig]['filial'] = r_dict.get('Filial')
                        if not agrupado_por_origem[orig]['cc'] and r_dict.get('cc'): 
                            agrupado_por_origem[orig]['cc'] = r_dict.get('cc')
                        if not agrupado_por_origem[orig]['item'] and r_dict.get('Item'): 
                            agrupado_por_origem[orig]['item'] = r_dict.get('Item')

                # Geração dos lançamentos intergrupo baseada nos dados já filtrados e somados
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

                    ajuste_existente = self.session.query(AjustesRazao).filter(
                        AjustesRazao.Origem == dados['origem'],
                        AjustesRazao.Conta == config['destino'], 
                        AjustesRazao.Tipo_Operacao == 'INTERGRUPO_AUTO',
                        AjustesRazao.Data == data_gravacao
                    ).first()

                    if ajuste_existente:
                        if abs(ajuste_existente.Debito - valor_ajuste) > 0.01:
                             ajuste_existente.Debito = valor_ajuste
                             ajuste_existente.Hash_Linha_Original = h_dest

                             par_origem = self.session.query(AjustesRazao).filter(
                                 AjustesRazao.Origem == dados['origem'],
                                 AjustesRazao.Conta == conta_origem,
                                 AjustesRazao.Tipo_Operacao == 'INTERGRUPO_AUTO',
                                 AjustesRazao.Data == data_gravacao
                             ).first()
                             if par_origem: 
                                 par_origem.Credito = valor_ajuste
                                 par_origem.Hash_Linha_Original = h_orig
                             
                             logs_farma.append(f"[{mes:02d}/{ano}] {dados['origem']}: Atualizado {config['destino']} v:{valor_ajuste}")
                    else:
                        aj_origem = AjustesRazao(
                            Conta=conta_origem, Titulo_Conta=config['titulo_origem'], Data=data_gravacao,
                            Descricao=config['descricao'], Debito=0.0, Credito=valor_ajuste,
                            Filial=dados['filial'], Centro_Custo=dados['cc'], Item=dados['item'], Origem=dados['origem'],
                            Tipo_Operacao='INTERGRUPO_AUTO', Status='Aprovado', Criado_Por='SISTEMA_AUTO',
                            Hash_Linha_Original=h_orig, 
                            Data_Aprovacao=datetime.datetime.now(), Exibir_Saldo=True
                        )
                        
                        aj_destino = AjustesRazao(
                            Conta=config['destino'], Titulo_Conta=config['titulo_destino'], Data=data_gravacao,
                            Descricao=config['descricao'], Debito=valor_ajuste, Credito=0.0,
                            Filial=dados['filial'], Centro_Custo=dados['cc'], Item=dados['item'], Origem=dados['origem'],
                            Tipo_Operacao='INTERGRUPO_AUTO', Status='Aprovado', Criado_Por='SISTEMA_AUTO',
                            Hash_Linha_Original=h_dest, 
                            Data_Aprovacao=datetime.datetime.now(), Exibir_Saldo=True
                        )
                        
                        self.session.add(aj_origem)
                        self.session.add(aj_destino)
                        logs_farma.append(f"[{mes:02d}/{ano}] {dados['origem']}: Criado {conta_origem} -> {config['destino']} v:{valor_ajuste}")
            
            return logs_farma
            
        except Exception as e:
            RegistrarLog(f"Erro no ProcessarIntergrupoFarma", "ERROR", e)
            raise e

    def GerarIntergrupo(self, ano, mes):
        """
        Orquestra a geração de movimentos e fluxos intergrupo do mês.
        Atua apenas como um controlador, invocando os processadores específicos (INTEC e Farma),
        salvando as transações na base de dados e validando a integridade final.
        
        Args:
            ano (int): Ano para cálculo.
            mes (int): Mês para cálculo.
            
        Returns:
            list[str]: Logs contendo o resumo consolidado de todas as operações intergrupo.
        """
        RegistrarLog(f"Iniciando GerarIntergrupo MENSAL. {mes}/{ano}", "SYSTEM")
        
        logs_totais = []
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        data_inicio = datetime.datetime(ano, mes, 1)
        data_fim = datetime.datetime(ano, mes, ultimo_dia, 23, 59, 59)
        data_gravacao = datetime.datetime(ano, mes, ultimo_dia)

        try:
            # 1. Processa as Regras da INTEC (CSV)
            logs_intec = self.ProcessarIntergrupoIntec(ano, mes, data_gravacao)
            logs_totais.extend(logs_intec)

            # 2. Processa as Regras da Farma (Consulta a Banco / Demais Origens)
            logs_farma = self.ProcessarIntergrupoFarma(ano, mes, data_inicio, data_fim, data_gravacao)
            logs_totais.extend(logs_farma)
            
            # Efetiva as inserções e atualizações de ambos os processos no banco de dados
            self.session.commit()
            
            # --- VERIFICAÇÃO DE INTEGRIDADE (Mínimo 12 Registros) ---
            qtd_registros = self.session.query(AjustesRazao).filter(
                AjustesRazao.Tipo_Operacao == 'INTERGRUPO_AUTO',
                text(f"EXTRACT(MONTH FROM \"Data\") = {mes}"),
                text(f"EXTRACT(YEAR FROM \"Data\") = {ano}")
            ).count()

            RegistrarLog(f"GerarIntergrupo Finalizado. Total de Registros no Banco (Mês {mes}/{ano}): {qtd_registros}", "SYSTEM")
            
            if qtd_registros < 12:
                aviso = f"ATENÇÃO CRÍTICA: Processo gerou apenas {qtd_registros} registros. Esperado no mínimo 12. Verifique os dados de origem (CSV ou Banco)."
                RegistrarLog(aviso, "ERROR")
                logs_totais.append(aviso)
            else:
                logs_totais.append(f"Sucesso: {qtd_registros} registros intergrupo validados (Mínimo 12 OK).")

            return logs_totais

        except Exception as e:
            self.session.rollback() # Previne sujeira na base caso uma das etapas falhe catastroficamente
            RegistrarLog("Erro Fatal ao persistir ajustes intergrupo", "ERROR", e)
            raise e