from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from Modules.SISTEMA.Services.CentroCustoConfigService import CentroCustoConfigService
from Modules.SISTEMA.Services.PermissaoService import RequerPermissao


centro_custo_config_bp = Blueprint('CentroCustoConfig', __name__)
servico_centro_custo_config = CentroCustoConfigService()


@centro_custo_config_bp.route('/configuracoes/centros-custo', methods=['GET'])
@centro_custo_config_bp.route('/configuracoes/gestores-centro-custo', methods=['GET'])
@login_required
@RequerPermissao('CONFIGURACOES.VISUALIZAR')
def VisualizarConfiguracaoCentroCusto():
    return render_template(
        'Pages/Configs/CentroCustoConfig.html',
        UsuariosDisponiveis=servico_centro_custo_config.listarUsuariosDisponiveis(),
        CentrosCustoDisponiveis=servico_centro_custo_config.listarCentrosCustoDisponiveis(),
        ConfiguracaoAtual=servico_centro_custo_config.carregarConfiguracao(),
    )


@centro_custo_config_bp.route('/api/configuracoes/centros-custo', methods=['POST'])
@centro_custo_config_bp.route('/api/configuracoes/gestores-centro-custo', methods=['POST'])
@login_required
@RequerPermissao('CONFIGURACOES.VISUALIZAR')
def SalvarConfiguracaoCentroCusto():
    payload = request.get_json(silent=True) or {}

    try:
        configuracao = servico_centro_custo_config.salvarConfiguracao(payload, current_user)
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