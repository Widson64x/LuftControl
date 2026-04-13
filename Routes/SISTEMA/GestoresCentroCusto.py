from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from Modules.SISTEMA.Services.GestorCentroCustoService import GestorCentroCustoService
from Modules.SISTEMA.Services.PermissaoService import RequerPermissao


gestores_cc_bp = Blueprint('GestoresCentroCusto', __name__)
servico_gestores_cc = GestorCentroCustoService()


@gestores_cc_bp.route('/configuracoes/gestores-centro-custo', methods=['GET'])
@login_required
@RequerPermissao('CONFIGURACOES.VISUALIZAR')
def VisualizarGestoresCentroCusto():
    usuarios = servico_gestores_cc.listarUsuariosDisponiveis()
    centros_custo = servico_gestores_cc.listarCentrosCustoDisponiveis()
    configuracao_atual = servico_gestores_cc.carregarConfiguracao()

    return render_template(
        'Pages/Configs/GestoresCentroCusto.html',
        UsuariosDisponiveis=usuarios,
        CentrosCustoDisponiveis=centros_custo,
        ConfiguracaoAtual=configuracao_atual,
    )


@gestores_cc_bp.route('/api/configuracoes/gestores-centro-custo', methods=['POST'])
@login_required
@RequerPermissao('CONFIGURACOES.VISUALIZAR')
def SalvarConfiguracaoGestoresCentroCusto():
    payload = request.get_json(silent=True) or {}

    try:
        configuracao = servico_gestores_cc.salvarConfiguracao(payload, current_user)
        return jsonify(
            {
                'status': 'success',
                'message': 'Configuração salva com sucesso.',
                'data': {'configuracao': configuracao},
            }
        ), 200
    except ValueError as erro:
        return jsonify({'status': 'error', 'message': str(erro)}), 400
    except Exception:
        return jsonify({'status': 'error', 'message': 'Não foi possível salvar a configuração.'}), 500