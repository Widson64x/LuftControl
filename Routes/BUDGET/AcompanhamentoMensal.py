import os
from datetime import datetime

from flask import Blueprint, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from luftcore.extensions.flask_extension import api_error, api_success, require_ajax

from Modules.BUDGET.Services.AcompanhamentoMensalService import AcompanhamentoMensalService
from Modules.SISTEMA.Services.PermissaoService import RequerPermissao
from Utils.Logger import RegistrarLog

acompanhamento_mensal_bp = Blueprint('AcompanhamentoMensalBudget', __name__)


@acompanhamento_mensal_bp.route('/acompanhamento-mensal', methods=['GET'])
@login_required
@RequerPermissao('RELATORIOS.BUDGET.VISUALIZAR')
def PaginaAcompanhamentoMensal():
    svc = AcompanhamentoMensalService()
    contexto = svc.obterContextoGestor(current_user.get_id() if current_user else None)
    return render_template('Pages/Budget/AcompanhamentoMensal.html', **contexto)


@acompanhamento_mensal_bp.route('/acompanhamento-mensal/gerar', methods=['POST'])
@login_required
@RequerPermissao('RELATORIOS.BUDGET.VISUALIZAR')
@require_ajax
def GerarArquivoAcompanhamentoMensal():
    try:
        payload = request.get_json(silent=True) or {}
        ano = payload.get('ano')
        codigo_centro_custo = payload.get('codigoCentroCusto')

        svc = AcompanhamentoMensalService()
        dados = svc.gerarArquivo(
            codigo_usuario=current_user.get_id() if current_user else None,
            ano=ano,
            codigo_centro_custo=codigo_centro_custo,
        )
        dados['downloadUrl'] = url_for(
            'AcompanhamentoMensalBudget.BaixarArquivoAcompanhamentoMensal',
            token=dados['tokenDownload'],
        )
        dados['geradoEm'] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

        usuario_id = current_user.get_id() if current_user else 'Anonimo'
        RegistrarLog(
            f"Planilha de acompanhamento mensal do Budget gerada por {usuario_id}. Ano: {dados['ano']}. Centro: {dados['centroCusto']['codigo']}",
            'WEB_EXPORT',
        )

        return api_success(data=dados, message='Planilha de acompanhamento gerada com sucesso.')
    except ValueError as erro:
        return api_error(message=str(erro), status=400)
    except Exception as erro:
        RegistrarLog('Erro ao gerar planilha de acompanhamento mensal do Budget', 'ERROR', erro)
        return api_error(
            message='Falha ao gerar a planilha de acompanhamento mensal.',
            details=str(erro),
            status=500,
        )


@acompanhamento_mensal_bp.route('/acompanhamento-mensal/download/<token>', methods=['GET'])
@login_required
@RequerPermissao('RELATORIOS.BUDGET.VISUALIZAR')
def BaixarArquivoAcompanhamentoMensal(token):
    try:
        svc = AcompanhamentoMensalService()
        caminho_arquivo = svc.obterCaminhoArquivoGerado(token)

        usuario_id = current_user.get_id() if current_user else 'Anonimo'
        RegistrarLog(f'Download da planilha de acompanhamento do Budget iniciado por {usuario_id}: {token}', 'WEB_EXPORT')

        return send_file(
            caminho_arquivo,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=os.path.basename(caminho_arquivo),
        )
    except ValueError as erro:
        return api_error(message=str(erro), status=404)
    except Exception as erro:
        RegistrarLog('Erro ao baixar planilha de acompanhamento mensal do Budget', 'ERROR', erro)
        return api_error(
            message='Falha ao baixar a planilha de acompanhamento mensal.',
            details=str(erro),
            status=500,
        )