from flask import Blueprint, render_template, request, jsonify, session as flask_session
from flask_login import current_user
from Db.Connections import get_postgres_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from Models.POSTGRESS.Ajustes import AjustesRazao, AjustesLog
import datetime
import hashlib

ajustes_bp = Blueprint('Ajustes', __name__)

def get_session():
    engine = get_postgres_engine()
    Session = sessionmaker(bind=engine)
    return Session()

# --- FUNÇÃO HELPER: Hash Padronizado e Robusto ---
def gerar_hash(row):
    """
    Gera um hash único para a linha.
    Padronização: Remove espaços (strip), converte 'None' string para 'None' texto,
    e formata data estritamente como YYYY-MM-DD.
    """
    def clean(val):
        if val is None: return 'None'
        s = str(val).strip()
        return 'None' if s == '' or s.lower() == 'none' else s

    # Tratamento específico para Data
    dt_val = row.get('Data')
    dt_str = 'None'
    
    if dt_val:
        # Se for objeto datetime/date
        if hasattr(dt_val, 'strftime'):
            dt_str = dt_val.strftime('%Y-%m-%d')
        # Se for string (ex: '2025-11-26 00:00:00')
        else:
            s_dt = str(dt_val).strip()
            if ' ' in s_dt: s_dt = s_dt.split(' ')[0] # Pega só a data
            if 'T' in s_dt: s_dt = s_dt.split('T')[0]
            dt_str = s_dt

    # Monta a string crua exatamente como o SQL fará
    raw = f"{clean(row.get('origem'))}-{clean(row.get('Filial'))}-{clean(row.get('Numero'))}-{clean(row.get('Item'))}-{clean(row.get('Conta'))}-{dt_str}"
    
    return hashlib.md5(raw.encode('utf-8')).hexdigest()

def parse_bool(value):
    if isinstance(value, bool): return value
    if isinstance(value, str): return value.lower() in ('true', '1', 't', 's', 'sim')
    return bool(value)

def registrar_log_alteracoes(session_db, ajuste_antigo, dados_novos, usuario, id_ajuste):
    campos_mapeados = {
        'origem': 'Origem', 'Conta': 'Conta', 'Titulo_Conta': 'Titulo_Conta',
        'Numero': 'Numero', 'Descricao': 'Descricao', 'Contra_Partida': 'Contra_Partida',
        'Filial': 'Filial', 'Centro de Custo': 'Centro_Custo', 'Item': 'Item',
        'Cod_Cl_Valor': 'Cod_Cl_Valor', 'Debito': 'Debito', 'Credito': 'Credito',
        'NaoOperacional': 'Is_Nao_Operacional', 'Exibir_Saldo': 'Exibir_Saldo', 'Data': 'Data', 'Invalido': 'Invalido'
    }
    
    logs = []
    for json_key, model_attr in campos_mapeados.items():
        valor_novo_raw = dados_novos.get(json_key)
        valor_antigo_raw = getattr(ajuste_antigo, model_attr)

        val_antigo = str(valor_antigo_raw) if valor_antigo_raw is not None else ''
        val_novo = str(valor_novo_raw) if valor_novo_raw is not None else ''
        
        if model_attr == 'Data' and valor_antigo_raw:
            val_antigo = valor_antigo_raw.strftime('%Y-%m-%d')
            if val_novo and 'T' in val_novo: val_novo = val_novo.split('T')[0]
            
        if model_attr in ['Debito', 'Credito']:
            try:
                f_antigo = float(valor_antigo_raw or 0)
                f_novo = float(valor_novo_raw or 0)
                if abs(f_antigo - f_novo) < 0.001: continue
                val_antigo, val_novo = str(f_antigo), str(f_novo)
            except: pass
            
        if model_attr in ['Is_Nao_Operacional', 'Exibir_Saldo', 'Invalido']:
            val_antigo = 'Sim' if parse_bool(valor_antigo_raw) else 'Não'
            val_novo = 'Sim' if parse_bool(valor_novo_raw) else 'Não'

        if val_antigo != val_novo:
            logs.append({'campo': model_attr, 'antigo': val_antigo, 'novo': val_novo})

    for l in logs:
        novo_log = AjustesLog(
            Id_Ajuste=id_ajuste, Campo_Alterado=l['campo'], Valor_Antigo=l['antigo'],
            Valor_Novo=l['novo'], Usuario_Acao=usuario, Data_Acao=datetime.datetime.now(),
            Tipo_Acao='EDICAO'
        )
        session_db.add(novo_log)

@ajustes_bp.route('/ajustes-razao', methods=['GET'])
def index():
    return render_template('MENUS/AjustesRazao.html')

@ajustes_bp.route('/api/ajustes-razao/dados', methods=['GET'])
def get_dados():
    session_db = get_session()
    try:
        # 1. Carrega dados da View
        q_view = text('SELECT * FROM "Dre_Schema"."Razao_Dados_Consolidado" LIMIT 100000')
        res_view = session_db.execute(q_view)
        rows_view = [dict(row._mapping) for row in res_view]

        # 2. Carrega Ajustes Existentes
        ajustes = session_db.query(AjustesRazao).all()
        
        # Mapa de verificação rápida (Hash -> Ajuste)
        mapa_existentes = {aj.Hash_Linha_Original: aj for aj in ajustes}
        
        # ==============================================================================
        # REGRA DE NEGÓCIO AUTOMÁTICA: ITEM 10190 -> JÁ SOBE APROVADO
        # ==============================================================================
        novos_ajustes_auto = []
        
        for row in rows_view:
            # Verifica se é o item da regra
            if str(row.get('Item')).strip() == '10190':
                h = gerar_hash(row)
                
                # Se NÃO existe ajuste para esta linha, cria agora
                if h not in mapa_existentes:
                    now = datetime.datetime.now()
                    
                    novo_ajuste = AjustesRazao(
                        Hash_Linha_Original=h,
                        Tipo_Operacao='EDICAO',
                        
                        # --- MUDANÇA AQUI: JÁ NASCE APROVADO ---
                        Status='Aprovado', 
                        
                        # Copia dados originais da linha
                        Origem=row.get('origem'),
                        Conta=row.get('Conta'),
                        Titulo_Conta=row.get('Título Conta'),
                        Data=row.get('Data'),
                        Numero=row.get('Numero'),
                        Descricao=row.get('Descricao'),
                        Contra_Partida=row.get('Contra Partida - Credito'),
                        Filial=str(row.get('Filial')) if row.get('Filial') else None,
                        Centro_Custo=str(row.get('Centro de Custo')) if row.get('Centro de Custo') else None,
                        Item=str(row.get('Item')),
                        Cod_Cl_Valor=str(row.get('Cod Cl. Valor')) if row.get('Cod Cl. Valor') else None,
                        
                        # Valores
                        Debito=float(row.get('Debito') or 0),
                        Credito=float(row.get('Credito') or 0),
                        
                        # APLICA A REGRA DE NEGÓCIO
                        Is_Nao_Operacional=True, 
                        Exibir_Saldo=True,
                        Invalido=False,
                        
                        # Auditoria de Criação
                        Criado_Por='Sistema (Auto 10190)',
                        Data_Criacao=now,
                        
                        # Auditoria de Aprovação (Já preenche pois nasce aprovado)
                        Aprovado_Por='Sistema (Auto 10190)',
                        Data_Aprovacao=now
                    )
                    novos_ajustes_auto.append(novo_ajuste)
                    # Adiciona ao mapa temporário para evitar duplicidade no loop
                    mapa_existentes[h] = novo_ajuste

        # Se houve criações automáticas, salva no banco agora
        if novos_ajustes_auto:
            try:
                session_db.bulk_save_objects(novos_ajustes_auto)
                session_db.commit()
                # Recarrega a lista de ajustes para garantir IDs atualizados
                ajustes = session_db.query(AjustesRazao).all()
            except Exception as e:
                print(f"Erro ao aplicar regra automática 10190: {e}")
                session_db.rollback()

        # ==============================================================================
        # PREPARA RETORNO PARA O FRONT
        # ==============================================================================

        mapa_edicao = {aj.Hash_Linha_Original: aj for aj in ajustes if aj.Tipo_Operacao == 'EDICAO'}
        inclusoes = [aj for aj in ajustes if aj.Tipo_Operacao == 'INCLUSAO']

        dados_finais = []

        def montar_linha(base, ajuste=None, is_inclusao=False):
            row = base.copy()
            row['Exibir_Saldo'] = True 
            
            if ajuste:
                row.update({
                    'origem': ajuste.Origem, 'Conta': ajuste.Conta, 'Título Conta': ajuste.Titulo_Conta,
                    'Data': ajuste.Data.strftime('%Y-%m-%d') if ajuste.Data else None,
                    'Numero': ajuste.Numero, 'Descricao': ajuste.Descricao,
                    'Contra Partida - Credito': ajuste.Contra_Partida, 'Filial': ajuste.Filial,
                    'Centro de Custo': ajuste.Centro_Custo, 'Item': ajuste.Item,
                    'Cod Cl. Valor': ajuste.Cod_Cl_Valor, 'Debito': ajuste.Debito,
                    'Credito': ajuste.Credito, 'NaoOperacional': ajuste.Is_Nao_Operacional,
                    'Exibir_Saldo': ajuste.Exibir_Saldo, 'Invalido': ajuste.Invalido, 'Status_Ajuste': ajuste.Status,
                    'Ajuste_ID': ajuste.Id, 'Criado_Por': ajuste.Criado_Por 
                })
                if is_inclusao:
                    row['Hash_ID'] = f"NEW_{ajuste.Id}"
                    row['Tipo_Linha'] = 'Inclusao'
            
            if row.get('Exibir_Saldo'):
                row['Saldo'] = (float(row.get('Debito') or 0) - float(row.get('Credito') or 0))
            else:
                row['Saldo'] = 0.0

            return row

        for row in rows_view:
            h = gerar_hash(row)
            ajuste = mapa_edicao.get(h)
            linha = montar_linha(row, ajuste)
            linha['Hash_ID'] = h
            linha['Tipo_Linha'] = 'Original'
            
            # Fallback visual apenas se não tiver ajuste (agora raro, pois criamos acima)
            if not ajuste: 
                linha['Status_Ajuste'] = 'Original'

            dados_finais.append(linha)

        for inc in inclusoes:
            dados_finais.append(montar_linha({}, inc, is_inclusao=True))

        return jsonify(dados_finais)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session_db.close()

@ajustes_bp.route('/api/ajustes-razao/salvar', methods=['POST'])
def salvar():
    session_db = get_session()
    try:
        dt = request.json
        d = dt['Dados']
        user = current_user.nome if current_user.is_authenticated else 'System'
        
        ajuste = None
        is_novo = False
        if dt.get('Ajuste_ID'):
            ajuste = session_db.query(AjustesRazao).get(dt.get('Ajuste_ID'))
        
        if not ajuste and dt['Tipo_Operacao'] == 'EDICAO':
            existente = session_db.query(AjustesRazao).filter_by(Hash_Linha_Original=dt['Hash_ID']).first()
            if existente: ajuste = existente
        
        if not ajuste:
            ajuste = AjustesRazao()
            is_novo = True
            ajuste.Criado_Por = user
            ajuste.Data_Criacao = datetime.datetime.now()
            session_db.add(ajuste)
        else:
            registrar_log_alteracoes(session_db, ajuste, d, user, ajuste.Id)

        ajuste.Tipo_Operacao = dt['Tipo_Operacao']
        ajuste.Hash_Linha_Original = dt.get('Hash_ID')
        ajuste.Status = 'Pendente'
        
        ajuste.Origem = d.get('origem')
        ajuste.Conta = d.get('Conta')
        ajuste.Titulo_Conta = d.get('Titulo_Conta')
        
        if d.get('Data'):
            ajuste.Data = datetime.datetime.strptime(d['Data'], '%Y-%m-%d')
        
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
        
        session_db.flush() 

        if is_novo:
            log = AjustesLog(Id_Ajuste=ajuste.Id, Campo_Alterado='TODOS', Valor_Antigo='-', 
                             Valor_Novo='CRIADO', Usuario_Acao=user, Data_Acao=datetime.datetime.now(), Tipo_Acao='CRIACAO')
            session_db.add(log)
        
        session_db.commit()
        return jsonify({'msg': 'Salvo', 'id': ajuste.Id})
    except Exception as e:
        session_db.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session_db.close()

@ajustes_bp.route('/api/ajustes-razao/aprovar', methods=['POST'])
def aprovar():
    session_db = get_session()
    try:
        dt = request.json
        ajuste = session_db.query(AjustesRazao).get(dt['Ajuste_ID'])
        user = current_user.nome if current_user.is_authenticated else 'System'
        
        if ajuste:
            novo_status = 'Aprovado' if dt['Acao'] == 'Aprovar' else 'Reprovado'
            log = AjustesLog(Id_Ajuste=ajuste.Id, Campo_Alterado='Status', Valor_Antigo=ajuste.Status, 
                             Valor_Novo=novo_status, Usuario_Acao=user, Data_Acao=datetime.datetime.now(), Tipo_Acao='APROVACAO')
            session_db.add(log)

            ajuste.Status = novo_status
            ajuste.Aprovado_Por = user
            ajuste.Data_Aprovacao = datetime.datetime.now()
            session_db.commit()
        return jsonify({'msg': 'OK'})
    finally:
        session_db.close()

@ajustes_bp.route('/api/ajustes-razao/status-invalido', methods=['POST'])
def alterar_status_invalido():
    session_db = get_session()
    try:
        dt = request.json
        id_ajuste = dt.get('Ajuste_ID')
        acao = dt.get('Acao') # Espera 'INVALIDAR' ou 'RESTAURAR'
        
        ajuste = session_db.query(AjustesRazao).get(id_ajuste)
        user = current_user.nome if current_user.is_authenticated else 'System'
        
        if not ajuste:
            return jsonify({'error': 'Ajuste não encontrado'}), 404

        # Define se é True (Inválido) ou False (Válido/Restaurado)
        novo_estado_invalido = (acao == 'INVALIDAR')
        
        # Log de Auditoria
        log = AjustesLog(
            Id_Ajuste=ajuste.Id,
            Campo_Alterado='Invalido',
            Valor_Antigo=str(ajuste.Invalido),
            Valor_Novo=str(novo_estado_invalido),
            Usuario_Acao=user,
            Data_Acao=datetime.datetime.now(),
            Tipo_Acao='INVALIDACAO' if novo_estado_invalido else 'RESTAURACAO'
        )
        session_db.add(log)

        # Atualiza o registro
        ajuste.Invalido = novo_estado_invalido
        
        # Atualiza o Status visual para refletir a realidade
        if novo_estado_invalido:
            ajuste.Status = 'Invalido'
        else:
            # Se restaurar, volta para Pendente para ser reavaliado
            ajuste.Status = 'Pendente'

        session_db.commit()
        return jsonify({'msg': 'Status atualizado com sucesso'})
        
    except Exception as e:
        session_db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session_db.close()
        
@ajustes_bp.route('/api/ajustes-razao/historico/<int:id_ajuste>', methods=['GET'])
def get_historico(id_ajuste):
    session_db = get_session()
    try:
        logs = session_db.query(AjustesLog).filter(AjustesLog.Id_Ajuste == id_ajuste).order_by(AjustesLog.Data_Acao.desc()).all()
        return jsonify([{
            'Id_Log': l.Id_Log, 'Campo': l.Campo_Alterado, 'De': l.Valor_Antigo, 'Para': l.Valor_Novo,
            'Usuario': l.Usuario_Acao, 'Data': l.Data_Acao.strftime('%d/%m/%Y %H:%M:%S'), 'Tipo': l.Tipo_Acao
        } for l in logs])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session_db.close()