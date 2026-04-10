import os
from datetime import datetime

from flask import Blueprint, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from luftcore.extensions.flask_extension import api_error, api_success, require_ajax

from Modules.BUDGET.Services.AtualizacaoDespesasFixasService import AtualizacaoDespesasFixasService
from Modules.SISTEMA.Services.PermissaoService import RequerPermissao
from Utils.Logger import RegistrarLog

atualizacao_despesas_fixas_bp = Blueprint('AtualizacaoDespesasFixas', __name__)


@atualizacao_despesas_fixas_bp.route('/despesas-fixas/atualizacao', methods=['GET'])
@login_required
@RequerPermissao('RELATORIOS.BUDGET.VISUALIZAR')
def PaginaAtualizacaoDespesasFixas():
    return render_template('Pages/Budget/AtualizacaoDespesasFixas.html')


@atualizacao_despesas_fixas_bp.route('/despesas-fixas/upload-origem', methods=['POST'])
@login_required
@RequerPermissao('RELATORIOS.BUDGET.VISUALIZAR')
@require_ajax
def UploadArquivoOrigem():
    try:
        if 'file' not in request.files:
            return api_error(message='Envie o arquivo base para continuar.', status=400)

        arquivo = request.files['file']
        svc = AtualizacaoDespesasFixasService()
        dados = svc.salvarArquivoOrigem(arquivo)

        usuario_id = current_user.get_id() if current_user else 'Anonimo'
        RegistrarLog(f'Upload do arquivo base de Budget recebido por {usuario_id}: {dados["nomeArquivo"]}', 'WEB')

        return api_success(data=dados, message='Arquivo base importado com sucesso.')
    except ValueError as e:
        return api_error(message=str(e), status=400)
    except Exception as e:
        RegistrarLog('Erro ao importar arquivo base de Budget', 'ERROR', e)
        return api_error(message='Falha ao importar o arquivo base.', details=str(e), status=500)


@atualizacao_despesas_fixas_bp.route('/despesas-fixas/upload-destino', methods=['POST'])
@login_required
@RequerPermissao('RELATORIOS.BUDGET.VISUALIZAR')
@require_ajax
def UploadArquivoDestino():
    try:
        if 'file' not in request.files:
            return api_error(message='Envie o arquivo de destino para continuar.', status=400)

        arquivo = request.files['file']
        svc = AtualizacaoDespesasFixasService()
        dados = svc.salvarArquivoDestino(arquivo)
        dados['abas'] = svc.listarAbasDestino(dados['token'])

        usuario_id = current_user.get_id() if current_user else 'Anonimo'
        RegistrarLog(f'Upload do arquivo destino de Budget recebido por {usuario_id}: {dados["nomeArquivo"]}', 'WEB')

        return api_success(data=dados, message='Arquivo de destino importado com sucesso.')
    except ValueError as e:
        return api_error(message=str(e), status=400)
    except Exception as e:
        RegistrarLog('Erro ao importar arquivo destino de Budget', 'ERROR', e)
        return api_error(message='Falha ao importar o arquivo de destino.', details=str(e), status=500)


@atualizacao_despesas_fixas_bp.route('/despesas-fixas/processar', methods=['POST'])
@login_required
@RequerPermissao('RELATORIOS.BUDGET.VISUALIZAR')
@require_ajax
def ProcessarAtualizacaoDespesasFixas():
    try:
        payload = request.get_json(silent=True) or {}
        token_origem = payload.get('tokenOrigem')
        token_destino = payload.get('tokenDestino')
        aba_destino = payload.get('abaDestino')

        svc = AtualizacaoDespesasFixasService()
        dados = svc.processarAtualizacao(token_origem, token_destino, aba_destino)
        dados['downloadUrl'] = url_for('AtualizacaoDespesasFixas.BaixarArquivoProcessado', token=dados['tokenDownload'])
        dados['processadoEm'] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

        usuario_id = current_user.get_id() if current_user else 'Anonimo'
        RegistrarLog(
            f"Atualização de despesas fixas processada por {usuario_id}. Aba: {dados['abaDestino']}. Linhas: {dados['linhasInseridas']}",
            'WEB_EXPORT'
        )

        return api_success(data=dados, message='Cópia atualizada gerada com sucesso.')
    except ValueError as e:
        return api_error(message=str(e), status=400)
    except Exception as e:
        RegistrarLog('Erro ao processar atualização de despesas fixas do Budget', 'ERROR', e)
        return api_error(message='Falha ao gerar a cópia atualizada.', details=str(e), status=500)


@atualizacao_despesas_fixas_bp.route('/despesas-fixas/download/<token>', methods=['GET'])
@login_required
@RequerPermissao('RELATORIOS.BUDGET.VISUALIZAR')
def BaixarArquivoProcessado(token):
    try:
        svc = AtualizacaoDespesasFixasService()
        caminho_arquivo = svc.obterCaminhoArquivoProcessado(token)

        usuario_id = current_user.get_id() if current_user else 'Anonimo'
        RegistrarLog(f'Download da cópia atualizada de Budget iniciado por {usuario_id}: {token}', 'WEB_EXPORT')

        extensao = '.xlsm' if caminho_arquivo.lower().endswith('.xlsm') else '.xlsx'
        mimetype = 'application/vnd.ms-excel.sheet.macroEnabled.12' if extensao == '.xlsm' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

        return send_file(
            caminho_arquivo,
            mimetype=mimetype,
            as_attachment=True,
            download_name=os.path.basename(caminho_arquivo),
        )
    except ValueError as e:
        return api_error(message=str(e), status=404)
    except Exception as e:
        RegistrarLog('Erro ao baixar cópia atualizada de Budget', 'ERROR', e)
        return api_error(message='Falha ao baixar o arquivo atualizado.', details=str(e), status=500)