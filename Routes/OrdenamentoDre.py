from flask import Blueprint, jsonify, request
from flask_login import login_required
from Services.OrdenamentoDreService import OrdenamentoDreService

dre_ordem_bp = Blueprint('DreOrdenamento', __name__)

@dre_ordem_bp.route('/Ordenamento/Inicializar', methods=['POST'])
@login_required
def InicializarOrdenamento():
    """Rota para popular a tabela de ordenamento."""
    try:
        limpar = request.json.get('limpar', False) if request.json else False
        
        svc = OrdenamentoDreService()
        resultado = svc.InicializarOrdenamento(limpar)
        
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dre_ordem_bp.route('/Ordenamento/GetOrdem', methods=['POST'])
@login_required
def GetOrdem():
    """Retorna a ordem de um elemento específico."""
    try:
        data = request.json
        svc = OrdenamentoDreService()
        res = svc.ObterOrdemEspecifica(
            data.get('tipo_no'), 
            data.get('id_referencia'), 
            data.get('contexto_pai', 'root')
        )
        return jsonify(res), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dre_ordem_bp.route('/Ordenamento/GetFilhosOrdenados', methods=['POST'])
@login_required
def GetFilhosOrdenados():
    """Lista filhos ordenados de um contexto."""
    try:
        contexto = request.json.get('contexto_pai', 'root')
        svc = OrdenamentoDreService()
        lista = svc.ListarFilhosOrdenados(contexto)
        return jsonify(lista), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dre_ordem_bp.route('/Ordenamento/GetArvoreOrdenada', methods=['GET'])
@login_required
def GetArvoreOrdenada():
    """Retorna a árvore completa (Cacheada/Otimizada)."""
    try:
        svc = OrdenamentoDreService()
        arvore = svc.ObterArvoreOrdenada()
        
        if arvore is None:
            return jsonify({
                "error": "Ordenamento não inicializado",
                "msg": "Execute POST /Ordenamento/Inicializar primeiro"
            }), 400
            
        return jsonify(arvore), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dre_ordem_bp.route('/Ordenamento/Mover', methods=['POST'])
@login_required
def MoverNo():
    """Move um nó de posição."""
    try:
        data = request.json
        svc = OrdenamentoDreService()
        svc.MoverNo(
            data.get('tipo_no'),
            data.get('id_referencia'),
            data.get('contexto_origem'),
            data.get('contexto_destino'),
            data.get('nova_ordem'),
            data.get('posicao_relativa'),
            data.get('id_referencia_relativo')
        )
        return jsonify({"success": True, "msg": "Elemento movido!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dre_ordem_bp.route('/Ordenamento/ReordenarLote', methods=['POST'])
@login_required
def ReordenarLote():
    """Reordena múltiplos itens de uma vez."""
    try:
        data = request.json
        svc = OrdenamentoDreService()
        qtd = svc.ReordenarLote(
            data.get('contexto_pai'),
            data.get('nova_ordem', [])
        )
        return jsonify({"success": True, "msg": f"{qtd} itens reordenados!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dre_ordem_bp.route('/Ordenamento/Normalizar', methods=['POST'])
@login_required
def NormalizarContexto():
    """Normaliza intervalos (10, 20, 30...)."""
    try:
        svc = OrdenamentoDreService()
        svc.NormalizarContexto(request.json.get('contexto_pai', 'root'))
        return jsonify({"success": True, "msg": "Contexto normalizado!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dre_ordem_bp.route('/Ordenamento/SincronizarNovo', methods=['POST'])
@login_required
def SincronizarNovoElemento():
    """Adiciona elemento novo na árvore."""
    try:
        data = request.json
        svc = OrdenamentoDreService()
        res = svc.SincronizarNovoElemento(
            data.get('tipo_no'),
            data.get('id_referencia'),
            data.get('contexto_pai'),
            data.get('posicao', 'fim')
        )
        return jsonify(res), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dre_ordem_bp.route('/Ordenamento/RemoverElemento', methods=['POST'])
@login_required
def RemoverDoOrdenamento():
    """Remove elemento da árvore."""
    try:
        data = request.json
        svc = OrdenamentoDreService()
        qtd = svc.RemoverElemento(
            data.get('tipo_no'),
            data.get('id_referencia'),
            data.get('contexto_pai')
        )
        return jsonify({"success": True, "msg": f"{qtd} registro(s) removido(s)"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dre_ordem_bp.route('/Ordenamento/ReordenarEmMassa', methods=['POST'])
@login_required
def ReordenarEmMassa():
    """Reordena grupos baseado em lista de nomes."""
    try:
        data = request.json
        if not data.get('tipo_cc') or not data.get('ordem_nomes'):
            return jsonify({'error': 'Dados incompletos'}), 400

        svc = OrdenamentoDreService()
        updates = svc.ReordenarEmMassa(
            data.get('tipo_cc'),
            data.get('ordem_nomes')
        )
        return jsonify({'success': True, 'msg': f'Ordem aplicada para {updates} pastas.'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500