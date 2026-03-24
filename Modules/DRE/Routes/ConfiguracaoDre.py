"""
Módulo de Rotas para Configuração da Árvore DRE (Demonstração do Resultado do Exercício)
Provê as interfaces de rede (endpoints) para comunicação com o frontend, 
despachando toda a lógica de negócio para a respectiva classe de serviço.
"""

from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required

# Assumindo o caminho padrão para os seus decoradores customizados
from luftcore.extensions.flask_extension import require_ajax
from Modules.DRE.Services.PermissaoService import RequerPermissao
from Modules.DRE.Services.ConfiguracaoDreService import ConfiguracaoDreService

configuracao_dre_bp = Blueprint('ConfiguracaoDre', __name__)
servicoConfiguracao = ConfiguracaoDreService()

# ============================================================
# SEÇÃO 1: ROTAS DE VISUALIZAÇÃO (VIEWS/TEMPLATES)
# ============================================================

@configuracao_dre_bp.route('/configuracao/arvore', methods=['GET'])
@login_required
@RequerPermissao('CONFIG_DRE.VISUALIZAR')
def VisualizarArvore():
    """
    Renderiza o template HTML raiz para a configuração visual da DRE.

    Parâmetros:
        Nenhum.

    Retornos:
        str: Conteúdo HTML renderizado para o navegador cliente.
    """
    return render_template('Pages/Configs/DreConfigs.html')

# ============================================================
# SEÇÃO 2: ROTAS DE CONSULTA
# ============================================================

@configuracao_dre_bp.route('/configuracao/dados-arvore', methods=['GET'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.VISUALIZAR')
def ObterDadosArvore():
    """
    Entrega a estrutura hierárquica completa da DRE para renderização da árvore.

    Parâmetros:
        Nenhum.

    Retornos:
        Response: Objeto JSON serializado com a topologia dos nós e código de status HTTP.
    """
    resposta, codigoStatus = servicoConfiguracao.obterDadosArvore()
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/contas-disponiveis', methods=['GET'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.VISUALIZAR')
def ObterContasDisponiveis():
    """
    Recupera o conjunto de contas contábeis advindas da visão consolidada do ERP.

    Parâmetros:
        Nenhum.

    Retornos:
        Response: Lista de dicionários em JSON e código de status HTTP correspondente.
    """
    resposta, codigoStatus = servicoConfiguracao.obterContasDisponiveis()
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/contas-subgrupo', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.VISUALIZAR')
def ObterContasSubgrupo():
    """
    Lista os identificadores de contas contábeis contidos dentro de um subgrupo específico.

    Parâmetros:
        request.json (dict): Objeto contendo o identificador do subgrupo alvo.

    Retornos:
        Response: Matriz de strings (IDs das contas) em JSON e código de status HTTP.
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.obterContasSubgrupo(cargaDados)
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/subgrupos-tipo', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.VISUALIZAR')
def ObterSubgruposPorTipo():
    """
    Filtra subgrupos hierárquicos vinculados a uma classificação específica de Centro de Custo.

    Parâmetros:
        request.json (dict): Objeto contendo o tipo do Centro de Custo.

    Retornos:
        Response: Matriz de identificadores estruturais e código de status HTTP.
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.obterSubgruposPorTipo(cargaDados)
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/contas-grupo-massa', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.VISUALIZAR')
def ObterContasGrupoMassa():
    """
    Recupera contas base e personalizadas indexadas a um modelo macro de grupo.

    Parâmetros:
        request.json (dict): Objeto contendo a lista de grupos para consulta.

    Retornos:
        Response: Objeto JSON composto pelos relacionamentos em lote e código HTTP.
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.obterContasGrupoMassa(cargaDados)
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/nos-calculados', methods=['GET'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.VISUALIZAR')
def ObterNosCalculados():
    """
    Fornece as matrizes lógicas e aritméticas configuradas para nós dependentes.

    Parâmetros:
        Nenhum.

    Retornos:
        Response: JSON contendo fórmulas abstraídas, estilos e metadados, com código HTTP.
    """
    resposta, codigoStatus = servicoConfiguracao.obterNosCalculados()
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/operandos-disponiveis', methods=['GET'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.VISUALIZAR')
def ObterOperandosDisponiveis():
    """
    Relaciona instâncias utilizáveis como variáveis de cálculo na construção de fórmulas visuais.

    Parâmetros:
        Nenhum.

    Retornos:
        Response: JSON mapeando raízes, tipos e nós virtuais para a interface de edição.
    """
    resposta, codigoStatus = servicoConfiguracao.obterOperandosDisponiveis()
    return jsonify(resposta), codigoStatus

# ============================================================
# SEÇÃO 3: ROTAS DE CRIAÇÃO (ADD)
# ============================================================

@configuracao_dre_bp.route('/configuracao/adicionar-subgrupo', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.CRIAR')
def AdicionarSubgrupo():
    """
    Processa a inserção unitária de um novo braço hierárquico na topologia da DRE.

    Parâmetros:
        request.json (dict): Objeto contendo dados do novo subgrupo (nome, nó pai, etc).

    Retornos:
        Response: Confirmação transacional contendo a chave primária criada (ID).
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.adicionarSubgrupo(cargaDados)
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/adicionar-sistematico', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.CRIAR')
def AdicionarSubgrupoSistematico():
    """
    Gera ramificações homônimas em múltiplos Centros de Custo que compartilhem a mesma tipologia.

    Parâmetros:
        request.json (dict): Objeto contendo regras para criação sistemática de nós.

    Retornos:
        Response: Sumário da injeção massiva com código HTTP de resolução.
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.adicionarSubgrupoSistematico(cargaDados)
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/adicionar-no-virtual', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.CRIAR')
def AdicionarNoVirtual():
    """
    Cria a entidade raiz para abrigar classificadores que não emanam de fluxos do ERP.

    Parâmetros:
        request.json (dict): Objeto contendo o nome e especificações do nó virtual.

    Retornos:
        Response: Identificador base gerado para o novo nó virtual.
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.adicionarNoVirtual(cargaDados)
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/adicionar-calculado', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.CRIAR')
def AdicionarNoCalculado():
    """
    Valida e arquiva equações customizadas que inferem valores através da interseção de outras contas.

    Parâmetros:
        request.json (dict): Objeto contendo os dados matemáticos e hierarquia do nó calculado.

    Retornos:
        Response: Sinalizador de sucesso no cadastro da expressão matemática.
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.adicionarNoCalculado(cargaDados)
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/vincular-conta', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.EDITAR')
def VincularConta():
    """
    Associa deterministicamente o fluxo financeiro de uma conta contábil a um subgrupo específico.

    Parâmetros:
        request.json (dict): Objeto contendo a identificação da conta e do subgrupo destino.

    Retornos:
        Response: Validação da integridade relacional entre os nós.
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.vincularConta(cargaDados)
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/vincular-detalhe', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.EDITAR')
def VincularContaDetalhe():
    """
    Parametriza uma conta contábil com terminologias personalizadas exigidas por diretrizes gerenciais.

    Parâmetros:
        request.json (dict): Objeto contendo nomenclaturas personalizadas e identificadores.

    Retornos:
        Response: Confirmação em formato JSON e código de status.
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.vincularContaDetalhe(cargaDados)
    return jsonify(resposta), codigoStatus

# ============================================================
# SEÇÃO 4: ROTAS DE ATUALIZAÇÃO (UPDATE/RENAME)
# ============================================================

@configuracao_dre_bp.route('/configuracao/renomear-virtual', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.EDITAR')
def RenomearNoVirtual():
    """
    Executa alteração estritamente textual sobre o rótulo de um nó de natureza virtual.

    Parâmetros:
        request.json (dict): Objeto contendo a chave do nó virtual e a nova string.

    Retornos:
        Response: Feedback lógico do impacto no banco de dados.
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.renomearNoVirtual(cargaDados)
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/renomear-subgrupo', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.EDITAR')
def RenomearSubgrupo():
    """
    Atualiza a string referencial do agrupamento interno sem romper chaves estrangeiras.

    Parâmetros:
        request.json (dict): Objeto contendo a chave do subgrupo e o novo nome.

    Retornos:
        Response: Sucesso ou indicativo de falha semântica.
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.renomearSubgrupo(cargaDados)
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/renomear-personalizada', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.EDITAR')
def RenomearContaPersonalizada():
    """
    Reescreve os apelidos definidos pelo controlador para submissão nos balanços da DRE.

    Parâmetros:
        request.json (dict): Objeto contendo a referência da conta e a nova nomenclatura.

    Retornos:
        Response: Dicionário contendo a situação final da atualização.
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.renomearContaPersonalizada(cargaDados)
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/atualizar-calculado', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.EDITAR')
def AtualizarNoCalculado():
    """
    Realiza o processamento de modificações supervenientes sobre lógicas matemáticas pré-existentes.

    Parâmetros:
        request.json (dict): Objeto detalhando os novos cálculos de um nó existente.

    Retornos:
        Response: Validação dos parâmetros alterados.
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.atualizarNoCalculado(cargaDados)
    return jsonify(resposta), codigoStatus

# ============================================================
# SEÇÃO 5: ROTAS DE EXCLUSÃO (DELETE)
# ============================================================

@configuracao_dre_bp.route('/configuracao/excluir-subgrupo', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.DELETAR')
def ExcluirSubgrupo():
    """
    Extingue um nó estrutural e força a deleção de toda descendência conectada a ele.

    Parâmetros:
        request.json (dict): Objeto contendo a chave primária do subgrupo alvo.

    Retornos:
        Response: Confirmação da remoção em cascata e deleção dos históricos de ordem.
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.excluirSubgrupo(cargaDados)
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/desvincular-conta', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.EDITAR')
def DesvincularConta():
    """
    Destrói a relação entre a base contábil bruta e o modelo estruturado na interface.

    Parâmetros:
        request.json (dict): Objeto contendo chaves cruzadas da conta e subgrupo.

    Retornos:
        Response: Booleano atestando a limpeza da chave relacional.
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.desvincularConta(cargaDados)
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/excluir-no-virtual', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.DELETAR')
def ExcluirNoVirtual():
    """
    Aniquila o container abstrato designado para métricas isoladas e suas referências.

    Parâmetros:
        request.json (dict): Objeto contendo o identificador base do nó virtual.

    Retornos:
        Response: Status da fragmentação controlada via serviço.
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.excluirNoVirtual(cargaDados)
    return jsonify(resposta), codigoStatus

# ============================================================
# SEÇÃO 6: ROTAS DE OPERAÇÕES EM MASSA
# ============================================================

@configuracao_dre_bp.route('/configuracao/vincular-massa', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.EDITAR')
def VincularContaEmMassa():
    """
    Expande simultaneamente a relação de uma mesma conta contábil a variadas posições mapeadas.

    Parâmetros:
        request.json (dict): Objeto mapeando conjuntos de contas e subgrupos de destino.

    Retornos:
        Response: Consolidação com número de incidências inseridas no banco.
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.vincularContaEmMassa(cargaDados)
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/desvincular-massa', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.EDITAR')
def DesvincularContaEmMassa():
    """
    Dispara um gatilho unificado para a quebra de relacionamentos cruzados sobre determinado escopo.

    Parâmetros:
        request.json (dict): Objeto especificando os lotes de relacionamentos a serem desfeitos.

    Retornos:
        Response: Recibo quantitativo das quebras executadas.
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.desvincularContaEmMassa(cargaDados)
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/excluir-subgrupo-massa', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.DELETAR')
def ExcluirSubgrupoEmMassa():
    """
    Localiza subgrupos repetitivos baseando-se no cruzamento de nomenclatura e destrói suas incidências.

    Parâmetros:
        request.json (dict): Objeto com identificadores e escopos dos subgrupos iterativos.

    Retornos:
        Response: Quantia processada eliminada dos registros contábeis customizados.
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.excluirSubgrupoEmMassa(cargaDados)
    return jsonify(resposta), codigoStatus

# ============================================================
# SEÇÃO 7: ROTAS DE REPLICAÇÃO E SINCRONIZAÇÃO
# ============================================================

@configuracao_dre_bp.route('/configuracao/replicar-estrutura', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.CRIAR')
def ReplicarEstrutura():
    """
    Método provisório ou Stub arquitetônico para o trânsito de transferência da interface.

    Parâmetros:
        Nenhum.

    Retornos:
        Response: Mensagem estática pontuando reestruturação momentânea.
    """
    resposta, codigoStatus = servicoConfiguracao.replicarEstrutura()
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/colar-estrutura', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.CRIAR')
def ColarEstrutura():
    """
    Método provisório ou Stub arquitetônico para o trânsito de transferência da interface.

    Parâmetros:
        Nenhum.

    Retornos:
        Response: Mensagem estática pontuando reestruturação momentânea.
    """
    resposta, codigoStatus = servicoConfiguracao.colarEstrutura()
    return jsonify(resposta), codigoStatus

@configuracao_dre_bp.route('/configuracao/replicar-tipo-integral', methods=['POST'])
@login_required
@require_ajax
@RequerPermissao('CONFIG_DRE.SINCRONIZAR')
def ReplicarTipoIntegral():
    """
    Aciona serviço pesado de reconstrução por espelhamento a fim de clonar o layout de um Tipo de CC para outro.

    Parâmetros:
        request.json (dict): Objeto especificando as origens e destinos da cópia integral.

    Retornos:
        Response: Parecer da transação integral processada no servidor do banco de dados.
    """
    cargaDados = request.json
    resposta, codigoStatus = servicoConfiguracao.replicarTipoIntegral(cargaDados)
    return jsonify(resposta), codigoStatus