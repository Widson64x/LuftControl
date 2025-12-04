# Routes/ModulesGrid.py
"""
Blueprint para o módulo Modules-Grid.
Gerencia ajustes manuais sobre a view Razao_Dados_Consolidado.

Rotas:
- GET  /                     -> Página do grid de edição
- GET  /api/dados            -> Lista dados da view + ajustes aplicados
- GET  /api/registro/<id>    -> Detalhes de um registro específico
- POST /api/alterar          -> Submeter alteração (gera pendente + log)
- GET  /api/pendentes        -> Lista alterações pendentes de aprovação
- POST /api/aprovar          -> Aprovar alteração
- POST /api/reprovar         -> Reprovar alteração
- GET  /api/logs             -> Histórico de alterações
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json

from Db.Connections import get_postgres_engine
from Models.POSTGRESS.ModulesGrid import RazaoAjusteManual, RazaoAjusteLog, RazaoAjusteAprovacao
from Helpers.Security import requires_permission

modules_grid_bp = Blueprint('modules_grid', __name__, template_folder='../Templates')


# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def get_session():
    """Cria uma sessão do banco de dados PostgreSQL."""
    engine = get_postgres_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def get_row_key(row):
    """Gera a chave única de uma linha da view."""
    return f"{row['origem']}|{row['Data']}|{row['Numero']}|{row['Conta']}|{row['Item']}"


def calculate_nao_operacional(item):
    """Calcula o valor padrão de NaoOperacional baseado no Item."""
    if item and str(item).strip() == '10190':
        return True
    return False


def merge_view_com_ajustes(view_data, ajustes_dict):
    """
    Mescla os dados da view com os ajustes manuais aprovados.

    Args:
        view_data: Lista de dicts com dados da view
        ajustes_dict: Dict com chave=chave_linha e valor=ajuste

    Returns:
        Lista de dicts com dados mesclados
    """
    resultado = []

    for row in view_data:
        # Cria cópia do registro
        registro = dict(row)

        # Calcula NaoOperacional padrão
        registro['NaoOperacional'] = calculate_nao_operacional(registro.get('Item'))
        registro['NaoOperacional_Manual'] = False
        registro['tem_ajuste'] = False

        # Gera chave única
        chave = get_row_key(registro)

        # Verifica se existe ajuste
        if chave in ajustes_dict:
            ajuste = ajustes_dict[chave]
            registro['tem_ajuste'] = True
            registro['id_ajuste'] = ajuste.Id

            # Aplica sobrescrições (apenas campos não nulos do ajuste)
            if ajuste.Titulo_Conta_Ajustado is not None:
                registro['Título Conta'] = ajuste.Titulo_Conta_Ajustado

            if ajuste.Descricao_Ajustado is not None:
                registro['Descricao'] = ajuste.Descricao_Ajustado

            if ajuste.Contra_Partida_Ajustado is not None:
                registro['Contra Partida - Credito'] = ajuste.Contra_Partida_Ajustado

            if ajuste.Filial_Ajustado is not None:
                registro['Filial'] = ajuste.Filial_Ajustado

            if ajuste.Centro_Custo_Ajustado is not None:
                registro['Centro de Custo'] = ajuste.Centro_Custo_Ajustado

            if ajuste.Item_Ajustado is not None:
                registro['Item'] = ajuste.Item_Ajustado

            if ajuste.Cod_Cl_Valor_Ajustado is not None:
                registro['Cod Cl. Valor'] = ajuste.Cod_Cl_Valor_Ajustado

            if ajuste.Debito_Ajustado is not None:
                registro['Debito'] = ajuste.Debito_Ajustado

            if ajuste.Credito_Ajustado is not None:
                registro['Credito'] = ajuste.Credito_Ajustado

            if ajuste.Saldo_Ajustado is not None:
                registro['Saldo'] = ajuste.Saldo_Ajustado

            # NaoOperacional do ajuste
            registro['NaoOperacional'] = ajuste.NaoOperacional
            registro['NaoOperacional_Manual'] = ajuste.NaoOperacional_Manual

        resultado.append(registro)

    return resultado


def serialize_row(row):
    """Serializa uma linha para JSON, tratando tipos especiais."""
    result = {}
    for key, value in row.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        elif value is None:
            result[key] = None
        else:
            result[key] = value
    return result


# =============================================================================
# ROTAS - PÁGINAS
# =============================================================================

@modules_grid_bp.route('/')
@login_required
@requires_permission('modules_grid.visualizar')
def index():
    """Página principal do grid de edição."""
    return render_template('MENUS/ModulesGrid.html')


# =============================================================================
# ROTAS - API DE DADOS
# =============================================================================

@modules_grid_bp.route('/api/dados')
@login_required
@requires_permission('modules_grid.visualizar')
def api_dados():
    """
    Lista dados da view Razao_Dados_Consolidado com ajustes aplicados.

    Query params:
        - page: número da página (default 1)
        - per_page: registros por página (default 50, max 500)
        - origem: filtro por origem (FARMA, FARMADIST)
        - conta: filtro por conta
        - mes: filtro por mês
        - data_inicio: filtro data inicial (YYYY-MM-DD)
        - data_fim: filtro data final (YYYY-MM-DD)
        - apenas_ajustados: true para mostrar apenas registros com ajustes
        - apenas_nao_operacional: true para mostrar apenas NaoOperacional=True
    """
    session = get_session()
    try:
        # Parâmetros de paginação
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 500)
        offset = (page - 1) * per_page

        # Parâmetros de filtro
        origem = request.args.get('origem')
        conta = request.args.get('conta')
        mes = request.args.get('mes')
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        apenas_ajustados = request.args.get('apenas_ajustados', 'false').lower() == 'true'
        apenas_nao_operacional = request.args.get('apenas_nao_operacional', 'false').lower() == 'true'

        # Monta query da view
        where_clauses = []
        params = {}

        if origem:
            where_clauses.append('origem = :origem')
            params['origem'] = origem

        if conta:
            where_clauses.append('"Conta" LIKE :conta')
            params['conta'] = f'%{conta}%'

        if mes:
            where_clauses.append('"Mes" = :mes')
            params['mes'] = mes

        if data_inicio:
            where_clauses.append('"Data" >= :data_inicio')
            params['data_inicio'] = data_inicio

        if data_fim:
            where_clauses.append('"Data" <= :data_fim')
            params['data_fim'] = data_fim

        where_sql = ''
        if where_clauses:
            where_sql = 'WHERE ' + ' AND '.join(where_clauses)

        # Query para contagem total
        count_sql = f'''
            SELECT COUNT(*) as total
            FROM "Dre_Schema"."Razao_Dados_Consolidado"
            {where_sql}
        '''
        total_result = session.execute(text(count_sql), params).fetchone()
        total = total_result[0] if total_result else 0

        # Query principal com paginação
        query_sql = f'''
            SELECT
                origem,
                "Conta",
                "Título Conta",
                "Data",
                "Numero",
                "Descricao",
                "Contra Partida - Credito",
                "Filial",
                "Centro de Custo",
                "Item",
                "Cod Cl. Valor",
                "Debito",
                "Credito",
                "Saldo",
                "Mes",
                "CC",
                "Nome do CC",
                "Cliente",
                "Filial Cliente"
            FROM "Dre_Schema"."Razao_Dados_Consolidado"
            {where_sql}
            ORDER BY "Data" DESC, "Conta"
            LIMIT :limit OFFSET :offset
        '''
        params['limit'] = per_page
        params['offset'] = offset

        result = session.execute(text(query_sql), params)
        view_data = [dict(row._mapping) for row in result]

        # Carrega ajustes ativos
        ajustes = session.query(RazaoAjusteManual).filter(
            RazaoAjusteManual.Ativo == True
        ).all()

        # Cria dict de ajustes por chave
        ajustes_dict = {}
        for ajuste in ajustes:
            chave = f"{ajuste.Origem}|{ajuste.Data}|{ajuste.Numero}|{ajuste.Conta}|{ajuste.Item}"
            ajustes_dict[chave] = ajuste

        # Mescla view com ajustes
        dados_mesclados = merge_view_com_ajustes(view_data, ajustes_dict)

        # Filtros pós-merge
        if apenas_ajustados:
            dados_mesclados = [d for d in dados_mesclados if d.get('tem_ajuste')]

        if apenas_nao_operacional:
            dados_mesclados = [d for d in dados_mesclados if d.get('NaoOperacional')]

        # Serializa para JSON
        dados_serializados = [serialize_row(row) for row in dados_mesclados]

        return jsonify({
            'success': True,
            'data': dados_serializados,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@modules_grid_bp.route('/api/registro/<path:chave>')
@login_required
@requires_permission('modules_grid.visualizar')
def api_registro(chave):
    """
    Retorna detalhes de um registro específico.

    A chave deve ser no formato: origem|data|numero|conta|item
    """
    session = get_session()
    try:
        # Parse da chave
        partes = chave.split('|')
        if len(partes) < 4:
            return jsonify({'error': 'Chave inválida. Formato: origem|data|numero|conta|item'}), 400

        origem = partes[0]
        data = partes[1]
        numero = partes[2]
        conta = partes[3]
        item = partes[4] if len(partes) > 4 else None

        # Busca na view
        query_sql = '''
            SELECT *
            FROM "Dre_Schema"."Razao_Dados_Consolidado"
            WHERE origem = :origem
            AND "Data" = :data
            AND "Numero" = :numero
            AND "Conta" = :conta
        '''
        params = {'origem': origem, 'data': data, 'numero': numero, 'conta': conta}

        if item:
            query_sql += ' AND "Item" = :item'
            params['item'] = item

        result = session.execute(text(query_sql), params)
        row = result.fetchone()

        if not row:
            return jsonify({'error': 'Registro não encontrado'}), 404

        registro = dict(row._mapping)

        # Busca ajuste existente
        ajuste_query = session.query(RazaoAjusteManual).filter(
            RazaoAjusteManual.Origem == origem,
            RazaoAjusteManual.Numero == numero,
            RazaoAjusteManual.Conta == conta,
            RazaoAjusteManual.Ativo == True
        )
        if item:
            ajuste_query = ajuste_query.filter(RazaoAjusteManual.Item == item)

        ajuste = ajuste_query.first()

        # Busca logs pendentes
        logs_pendentes = session.query(RazaoAjusteLog).filter(
            RazaoAjusteLog.Origem == origem,
            RazaoAjusteLog.Numero == numero,
            RazaoAjusteLog.Conta == conta,
            RazaoAjusteLog.Status == 'Pendente'
        ).all()

        # Calcula NaoOperacional padrão
        nao_operacional_padrao = calculate_nao_operacional(registro.get('Item'))

        response = {
            'success': True,
            'registro_original': serialize_row(registro),
            'nao_operacional_padrao': nao_operacional_padrao,
            'ajuste': None,
            'logs_pendentes': []
        }

        if ajuste:
            response['ajuste'] = {
                'id': ajuste.Id,
                'titulo_conta': ajuste.Titulo_Conta_Ajustado,
                'descricao': ajuste.Descricao_Ajustado,
                'contra_partida': ajuste.Contra_Partida_Ajustado,
                'filial': ajuste.Filial_Ajustado,
                'centro_custo': ajuste.Centro_Custo_Ajustado,
                'item': ajuste.Item_Ajustado,
                'cod_cl_valor': ajuste.Cod_Cl_Valor_Ajustado,
                'debito': ajuste.Debito_Ajustado,
                'credito': ajuste.Credito_Ajustado,
                'saldo': ajuste.Saldo_Ajustado,
                'nao_operacional': ajuste.NaoOperacional,
                'nao_operacional_manual': ajuste.NaoOperacional_Manual
            }

        for log in logs_pendentes:
            response['logs_pendentes'].append({
                'id': log.Id,
                'campo': log.Campo_Alterado,
                'valor_anterior': log.Valor_Anterior,
                'valor_novo': log.Valor_Novo,
                'usuario': log.Usuario_Alteracao,
                'data': log.Data_Alteracao.isoformat() if log.Data_Alteracao else None
            })

        return jsonify(response), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# =============================================================================
# ROTAS - API DE ALTERAÇÕES
# =============================================================================

@modules_grid_bp.route('/api/alterar', methods=['POST'])
@login_required
@requires_permission('modules_grid.editar')
def api_alterar():
    """
    Submete uma alteração para aprovação.

    Body JSON esperado:
    {
        "origem": "FARMA",
        "data": "2024-01-15T00:00:00",
        "numero": "12345",
        "conta": "1.1.01.001",
        "item": "10190",
        "alteracoes": {
            "campo1": {"valor_anterior": "X", "valor_novo": "Y"},
            "campo2": {"valor_anterior": "A", "valor_novo": "B"}
        }
    }

    Campos válidos para alteração:
    - titulo_conta, descricao, contra_partida, filial, centro_custo,
    - item, cod_cl_valor, debito, credito, saldo, nao_operacional
    """
    session = get_session()
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Dados não fornecidos'}), 400

        # Validação dos campos obrigatórios
        required = ['origem', 'data', 'numero', 'conta', 'alteracoes']
        for field in required:
            if field not in data:
                return jsonify({'error': f'Campo obrigatório ausente: {field}'}), 400

        origem = data['origem']
        data_registro = data['data']
        numero = data['numero']
        conta = data['conta']
        item = data.get('item')
        alteracoes = data['alteracoes']

        if not alteracoes:
            return jsonify({'error': 'Nenhuma alteração fornecida'}), 400

        usuario = current_user.login if hasattr(current_user, 'login') else str(current_user.id)

        # Parse da data
        if isinstance(data_registro, str):
            try:
                data_registro_dt = datetime.fromisoformat(data_registro.replace('Z', '+00:00'))
            except ValueError:
                data_registro_dt = datetime.strptime(data_registro[:10], '%Y-%m-%d')
        else:
            data_registro_dt = data_registro

        # Cria logs para cada alteração
        logs_criados = []
        for campo, valores in alteracoes.items():
            # Valida campo
            campos_validos = [
                'titulo_conta', 'descricao', 'contra_partida', 'filial',
                'centro_custo', 'item', 'cod_cl_valor', 'debito', 'credito',
                'saldo', 'nao_operacional'
            ]
            if campo not in campos_validos:
                continue

            valor_anterior = valores.get('valor_anterior')
            valor_novo = valores.get('valor_novo')

            # Serializa valores para armazenamento
            if valor_anterior is not None and not isinstance(valor_anterior, str):
                valor_anterior = json.dumps(valor_anterior)
            if valor_novo is not None and not isinstance(valor_novo, str):
                valor_novo = json.dumps(valor_novo)

            # Cria log
            log = RazaoAjusteLog(
                Origem=origem,
                Data_Registro=data_registro_dt,
                Numero=numero,
                Conta=conta,
                Item=item,
                Campo_Alterado=campo,
                Valor_Anterior=str(valor_anterior) if valor_anterior is not None else None,
                Valor_Novo=str(valor_novo) if valor_novo is not None else None,
                Usuario_Alteracao=usuario,
                Status='Pendente'
            )
            session.add(log)
            logs_criados.append(campo)

        session.commit()

        return jsonify({
            'success': True,
            'msg': f'{len(logs_criados)} alteração(ões) submetida(s) para aprovação',
            'campos': logs_criados
        }), 200

    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# =============================================================================
# ROTAS - API DE APROVAÇÃO
# =============================================================================

@modules_grid_bp.route('/api/pendentes')
@login_required
@requires_permission('modules_grid.aprovar')
def api_pendentes():
    """
    Lista alterações pendentes de aprovação.

    Query params:
        - page: número da página (default 1)
        - per_page: registros por página (default 50)
        - usuario: filtro por usuário que fez a alteração
    """
    session = get_session()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 200)
        offset = (page - 1) * per_page
        usuario_filtro = request.args.get('usuario')

        query = session.query(RazaoAjusteLog).filter(
            RazaoAjusteLog.Status == 'Pendente'
        )

        if usuario_filtro:
            query = query.filter(RazaoAjusteLog.Usuario_Alteracao == usuario_filtro)

        # Contagem total
        total = query.count()

        # Busca paginada
        logs = query.order_by(RazaoAjusteLog.Data_Alteracao.desc())\
                    .offset(offset)\
                    .limit(per_page)\
                    .all()

        resultado = []
        for log in logs:
            resultado.append({
                'id': log.Id,
                'origem': log.Origem,
                'data_registro': log.Data_Registro.isoformat() if log.Data_Registro else None,
                'numero': log.Numero,
                'conta': log.Conta,
                'item': log.Item,
                'campo': log.Campo_Alterado,
                'valor_anterior': log.Valor_Anterior,
                'valor_novo': log.Valor_Novo,
                'usuario': log.Usuario_Alteracao,
                'data_alteracao': log.Data_Alteracao.isoformat() if log.Data_Alteracao else None
            })

        return jsonify({
            'success': True,
            'data': resultado,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@modules_grid_bp.route('/api/aprovar', methods=['POST'])
@login_required
@requires_permission('modules_grid.aprovar')
def api_aprovar():
    """
    Aprova uma ou mais alterações pendentes.

    Body JSON esperado:
    {
        "ids": [1, 2, 3],  // IDs dos logs a aprovar
        "observacao": "Aprovado conforme solicitação..."  // opcional
    }
    """
    session = get_session()
    try:
        data = request.get_json()

        if not data or 'ids' not in data:
            return jsonify({'error': 'IDs não fornecidos'}), 400

        ids = data['ids']
        observacao = data.get('observacao', '')
        usuario = current_user.login if hasattr(current_user, 'login') else str(current_user.id)
        ip_origem = request.remote_addr

        aprovados = 0
        erros = []

        for log_id in ids:
            log = session.query(RazaoAjusteLog).filter(
                RazaoAjusteLog.Id == log_id,
                RazaoAjusteLog.Status == 'Pendente'
            ).first()

            if not log:
                erros.append(f'Log {log_id} não encontrado ou já processado')
                continue

            # Verifica se não é o próprio usuário aprovando
            if log.Usuario_Alteracao == usuario:
                erros.append(f'Log {log_id}: Usuário não pode aprovar própria alteração')
                continue

            # Atualiza status do log
            log.Status = 'Aprovado'
            log.Usuario_Aprovacao = usuario
            log.Data_Aprovacao = datetime.now()

            # Registra aprovação
            aprovacao = RazaoAjusteAprovacao(
                Id_Log=log.Id,
                Decisao='Aprovado',
                Usuario_Decisao=usuario,
                Observacao=observacao,
                IP_Origem=ip_origem
            )
            session.add(aprovacao)

            # Aplica o ajuste na tabela de ajustes manuais
            _aplicar_ajuste(session, log)

            aprovados += 1

        session.commit()

        response = {
            'success': True,
            'msg': f'{aprovados} alteração(ões) aprovada(s)',
            'aprovados': aprovados
        }
        if erros:
            response['avisos'] = erros

        return jsonify(response), 200

    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@modules_grid_bp.route('/api/reprovar', methods=['POST'])
@login_required
@requires_permission('modules_grid.aprovar')
def api_reprovar():
    """
    Reprova uma ou mais alterações pendentes.

    Body JSON esperado:
    {
        "ids": [1, 2, 3],
        "motivo": "Motivo da reprovação..."  // obrigatório
    }
    """
    session = get_session()
    try:
        data = request.get_json()

        if not data or 'ids' not in data:
            return jsonify({'error': 'IDs não fornecidos'}), 400

        if not data.get('motivo'):
            return jsonify({'error': 'Motivo da reprovação é obrigatório'}), 400

        ids = data['ids']
        motivo = data['motivo']
        usuario = current_user.login if hasattr(current_user, 'login') else str(current_user.id)
        ip_origem = request.remote_addr

        reprovados = 0
        erros = []

        for log_id in ids:
            log = session.query(RazaoAjusteLog).filter(
                RazaoAjusteLog.Id == log_id,
                RazaoAjusteLog.Status == 'Pendente'
            ).first()

            if not log:
                erros.append(f'Log {log_id} não encontrado ou já processado')
                continue

            # Atualiza status do log
            log.Status = 'Reprovado'
            log.Usuario_Aprovacao = usuario
            log.Data_Aprovacao = datetime.now()
            log.Motivo_Reprovacao = motivo

            # Registra reprovação
            aprovacao = RazaoAjusteAprovacao(
                Id_Log=log.Id,
                Decisao='Reprovado',
                Usuario_Decisao=usuario,
                Observacao=motivo,
                IP_Origem=ip_origem
            )
            session.add(aprovacao)

            reprovados += 1

        session.commit()

        response = {
            'success': True,
            'msg': f'{reprovados} alteração(ões) reprovada(s)',
            'reprovados': reprovados
        }
        if erros:
            response['avisos'] = erros

        return jsonify(response), 200

    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


def _aplicar_ajuste(session, log):
    """
    Aplica um ajuste aprovado na tabela de ajustes manuais.
    Cria ou atualiza o registro de ajuste conforme necessário.
    """
    # Busca ajuste existente
    ajuste = session.query(RazaoAjusteManual).filter(
        RazaoAjusteManual.Origem == log.Origem,
        RazaoAjusteManual.Data == log.Data_Registro,
        RazaoAjusteManual.Numero == log.Numero,
        RazaoAjusteManual.Conta == log.Conta,
        RazaoAjusteManual.Item == log.Item
    ).first()

    if not ajuste:
        # Cria novo ajuste
        ajuste = RazaoAjusteManual(
            Origem=log.Origem,
            Data=log.Data_Registro,
            Numero=log.Numero,
            Conta=log.Conta,
            Item=log.Item,
            NaoOperacional=calculate_nao_operacional(log.Item),
            NaoOperacional_Manual=False,
            Ativo=True
        )
        session.add(ajuste)
        session.flush()  # Para obter o ID

    # Atualiza referência no log
    log.Id_Ajuste = ajuste.Id

    # Mapeia campo do log para campo do ajuste
    campo_map = {
        'titulo_conta': 'Titulo_Conta_Ajustado',
        'descricao': 'Descricao_Ajustado',
        'contra_partida': 'Contra_Partida_Ajustado',
        'filial': 'Filial_Ajustado',
        'centro_custo': 'Centro_Custo_Ajustado',
        'item': 'Item_Ajustado',
        'cod_cl_valor': 'Cod_Cl_Valor_Ajustado',
        'debito': 'Debito_Ajustado',
        'credito': 'Credito_Ajustado',
        'saldo': 'Saldo_Ajustado',
        'nao_operacional': 'NaoOperacional'
    }

    campo_ajuste = campo_map.get(log.Campo_Alterado)
    if campo_ajuste:
        valor = log.Valor_Novo

        # Converte tipos conforme necessário
        if campo_ajuste in ['Debito_Ajustado', 'Credito_Ajustado', 'Saldo_Ajustado']:
            valor = float(valor) if valor else None
        elif campo_ajuste == 'NaoOperacional':
            valor = valor.lower() == 'true' if isinstance(valor, str) else bool(valor)
            ajuste.NaoOperacional_Manual = True

        setattr(ajuste, campo_ajuste, valor)

    ajuste.Data_Atualizacao = datetime.now()


# =============================================================================
# ROTAS - API DE LOGS
# =============================================================================

@modules_grid_bp.route('/api/logs')
@login_required
@requires_permission('modules_grid.visualizar')
def api_logs():
    """
    Histórico de alterações.

    Query params:
        - page: número da página (default 1)
        - per_page: registros por página (default 50)
        - origem: filtro por origem
        - conta: filtro por conta
        - status: filtro por status (Pendente, Aprovado, Reprovado, Cancelado)
        - usuario: filtro por usuário
        - data_inicio: data inicial
        - data_fim: data final
    """
    session = get_session()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 200)
        offset = (page - 1) * per_page

        origem = request.args.get('origem')
        conta = request.args.get('conta')
        status = request.args.get('status')
        usuario = request.args.get('usuario')
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')

        query = session.query(RazaoAjusteLog)

        if origem:
            query = query.filter(RazaoAjusteLog.Origem == origem)
        if conta:
            query = query.filter(RazaoAjusteLog.Conta.like(f'%{conta}%'))
        if status:
            query = query.filter(RazaoAjusteLog.Status == status)
        if usuario:
            query = query.filter(RazaoAjusteLog.Usuario_Alteracao == usuario)
        if data_inicio:
            query = query.filter(RazaoAjusteLog.Data_Alteracao >= data_inicio)
        if data_fim:
            query = query.filter(RazaoAjusteLog.Data_Alteracao <= data_fim)

        total = query.count()

        logs = query.order_by(RazaoAjusteLog.Data_Alteracao.desc())\
                    .offset(offset)\
                    .limit(per_page)\
                    .all()

        resultado = []
        for log in logs:
            resultado.append({
                'id': log.Id,
                'id_ajuste': log.Id_Ajuste,
                'origem': log.Origem,
                'data_registro': log.Data_Registro.isoformat() if log.Data_Registro else None,
                'numero': log.Numero,
                'conta': log.Conta,
                'item': log.Item,
                'campo': log.Campo_Alterado,
                'valor_anterior': log.Valor_Anterior,
                'valor_novo': log.Valor_Novo,
                'usuario_alteracao': log.Usuario_Alteracao,
                'data_alteracao': log.Data_Alteracao.isoformat() if log.Data_Alteracao else None,
                'status': log.Status,
                'usuario_aprovacao': log.Usuario_Aprovacao,
                'data_aprovacao': log.Data_Aprovacao.isoformat() if log.Data_Aprovacao else None,
                'motivo_reprovacao': log.Motivo_Reprovacao
            })

        return jsonify({
            'success': True,
            'data': resultado,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# =============================================================================
# ROTAS - ESTATÍSTICAS
# =============================================================================

@modules_grid_bp.route('/api/estatisticas')
@login_required
@requires_permission('modules_grid.visualizar')
def api_estatisticas():
    """Retorna estatísticas gerais do módulo."""
    session = get_session()
    try:
        # Total de ajustes ativos
        total_ajustes = session.query(RazaoAjusteManual).filter(
            RazaoAjusteManual.Ativo == True
        ).count()

        # Pendentes de aprovação
        pendentes = session.query(RazaoAjusteLog).filter(
            RazaoAjusteLog.Status == 'Pendente'
        ).count()

        # Aprovados hoje
        hoje = datetime.now().date()
        aprovados_hoje = session.query(RazaoAjusteLog).filter(
            RazaoAjusteLog.Status == 'Aprovado',
            RazaoAjusteLog.Data_Aprovacao >= hoje
        ).count()

        # Reprovados este mês
        primeiro_dia_mes = hoje.replace(day=1)
        reprovados_mes = session.query(RazaoAjusteLog).filter(
            RazaoAjusteLog.Status == 'Reprovado',
            RazaoAjusteLog.Data_Aprovacao >= primeiro_dia_mes
        ).count()

        return jsonify({
            'success': True,
            'estatisticas': {
                'total_ajustes': total_ajustes,
                'pendentes': pendentes,
                'aprovados_hoje': aprovados_hoje,
                'reprovados_mes': reprovados_mes
            }
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()
