from flask import Blueprint, render_template, request, jsonify, session as flask_session
from Db.Connections import get_postgres_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from Models.POSTGRESS.Ajustes import AjustesRazao
import datetime
import hashlib

ajustes_bp = Blueprint('Ajustes', __name__)

def get_session():
    engine = get_postgres_engine()
    Session = sessionmaker(bind=engine)
    return Session()

def gerar_hash(row):
    # Gera ID único para linhas da view
    raw = f"{row.get('origem')}-{row.get('Filial')}-{row.get('Numero')}-{row.get('Item')}-{row.get('Conta')}-{row.get('Data')}"
    return hashlib.md5(raw.encode('utf-8')).hexdigest()

@ajustes_bp.route('/ajustes-razao', methods=['GET'])
def index():
    return render_template('MENUS/AjustesRazao.html')

@ajustes_bp.route('/api/ajustes-razao/dados', methods=['GET'])
def get_dados():
    session_db = get_session()
    try:
        # 1. View Original
        q_view = text('SELECT * FROM "Dre_Schema"."Razao_Dados_Consolidado" LIMIT 5000')
        res_view = session_db.execute(q_view)
        rows_view = [dict(row._mapping) for row in res_view]

        # 2. Ajustes
        ajustes = session_db.query(AjustesRazao).all()
        mapa_edicao = {aj.Hash_Linha_Original: aj for aj in ajustes if aj.Tipo_Operacao == 'EDICAO'}
        inclusoes = [aj for aj in ajustes if aj.Tipo_Operacao == 'INCLUSAO']

        dados_finais = []

        # --- FUNÇÃO HELPER PARA MONTAR OBJETO ---
        def montar_linha(base, ajuste=None, is_inclusao=False):
            row = base.copy()
            
            # Defaults
            row['Exibir_Saldo'] = True 
            
            if ajuste:
                # Sobrescreve TUDO com o que está no ajuste
                row['origem'] = ajuste.Origem
                row['Conta'] = ajuste.Conta
                row['Título Conta'] = ajuste.Titulo_Conta # Mapeando para nome da View
                row['Data'] = ajuste.Data.strftime('%Y-%m-%d') if ajuste.Data else None
                row['Numero'] = ajuste.Numero
                row['Descricao'] = ajuste.Descricao
                row['Contra Partida - Credito'] = ajuste.Contra_Partida # Mapeando
                row['Filial'] = ajuste.Filial
                row['Centro de Custo'] = ajuste.Centro_Custo
                row['Item'] = ajuste.Item
                row['Cod Cl. Valor'] = ajuste.Cod_Cl_Valor # Mapeando
                row['Debito'] = ajuste.Debito
                row['Credito'] = ajuste.Credito
                row['NaoOperacional'] = ajuste.Is_Nao_Operacional
                row['Exibir_Saldo'] = ajuste.Exibir_Saldo # Lógica do Saldo
                
                row['Status_Ajuste'] = ajuste.Status
                row['Ajuste_ID'] = ajuste.Id
                
                if is_inclusao:
                    row['Hash_ID'] = f"NEW_{ajuste.Id}"
                    row['Tipo_Linha'] = 'Inclusao'
            
            # Lógica de Cálculo de Saldo
            if row['Exibir_Saldo']:
                row['Saldo'] = (row.get('Debito') or 0) - (row.get('Credito') or 0)
            else:
                row['Saldo'] = None # Ou 0, conforme preferir exibir no front

            return row

        # Processa Originais + Edições
        for row in rows_view:
            h = gerar_hash(row)
            ajuste = mapa_edicao.get(h)
            
            # Prepara linha base
            linha_final = montar_linha(row, ajuste)
            linha_final['Hash_ID'] = h
            linha_final['Tipo_Linha'] = 'Original'
            if not adjustment_exists(ajuste): # Se não tem ajuste, status original
                 linha_final['Status_Ajuste'] = 'Original'
                 # Lógica padrão NaoOperacional da View se não tiver ajuste
                 if not ajuste: 
                    linha_final['NaoOperacional'] = str(row.get('Item')) == '10190'

            dados_finais.append(linha_final)

        # Processa Inclusões
        for inc in inclusoes:
            # Cria um dict vazio simulando a estrutura da view
            base_vazia = {} 
            dados_finais.append(montar_linha(base_vazia, inc, is_inclusao=True))

        return jsonify(dados_finais)
    finally:
        session_db.close()

def adjustment_exists(aj):
    return aj is not None

@ajustes_bp.route('/api/ajustes-razao/salvar', methods=['POST'])
def salvar():
    session_db = get_session()
    try:
        dt = request.json
        d = dt['Dados']
        user = flask_session.get('user_name', 'System')
        
        ajuste = None
        if dt.get('Ajuste_ID'):
            ajuste = session_db.query(AjustesRazao).get(dt.get('Ajuste_ID'))
        
        if not ajuste:
            ajuste = AjustesRazao()
            # Evita duplicidade em edição
            if dt['Tipo_Operacao'] == 'EDICAO':
                existente = session_db.query(AjustesRazao).filter_by(Hash_Linha_Original=dt['Hash_ID']).first()
                if existente: ajuste = existente
            session_db.add(ajuste)
            ajuste.Criado_Por = user

        # Mapeamento Completo
        ajuste.Tipo_Operacao = dt['Tipo_Operacao']
        ajuste.Hash_Linha_Original = dt.get('Hash_ID')
        ajuste.Status = 'Pendente'
        
        ajuste.Origem = d.get('origem')
        ajuste.Conta = d.get('Conta')
        ajuste.Titulo_Conta = d.get('Titulo_Conta')     # Novo
        ajuste.Data = datetime.datetime.strptime(d['Data'], '%Y-%m-%d').date()
        ajuste.Numero = d.get('Numero')
        ajuste.Descricao = d.get('Descricao')
        ajuste.Contra_Partida = d.get('Contra_Partida') # Novo
        ajuste.Filial = d.get('Filial')
        ajuste.Centro_Custo = d.get('Centro de Custo')
        ajuste.Item = d.get('Item')
        ajuste.Cod_Cl_Valor = d.get('Cod_Cl_Valor')     # Novo
        
        ajuste.Debito = float(d.get('Debito') or 0)
        ajuste.Credito = float(d.get('Credito') or 0)
        
        ajuste.Is_Nao_Operacional = bool(d.get('NaoOperacional'))
        ajuste.Exibir_Saldo = bool(d.get('Exibir_Saldo')) # Novo
        
        session_db.commit()
        return jsonify({'msg': 'Salvo'})
    except Exception as e:
        session_db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session_db.close()

@ajustes_bp.route('/api/ajustes-razao/aprovar', methods=['POST'])
def aprovar():
    session_db = get_session()
    try:
        dt = request.json
        ajuste = session_db.query(AjustesRazao).get(dt['Ajuste_ID'])
        if ajuste:
            ajuste.Status = 'Aprovado' if dt['Acao'] == 'Aprovar' else 'Reprovado'
            ajuste.Aprovado_Por = flask_session.get('user_name')
            ajuste.Data_Aprovacao = datetime.datetime.now()
            session_db.commit()
        return jsonify({'msg': 'OK'})
    finally:
        session_db.close()