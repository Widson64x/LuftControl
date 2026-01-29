from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

# Importa a Classe de Serviço
from Services.ImportacaoDadosService import ImportacaoDadosService

# --- Import do Logger ---
from Utils.Logger import RegistrarLog

# Cria o Blueprint
import_bp = Blueprint('Import', __name__)

# Colunas Padrão que o sistema espera receber (Meta-dados)
DB_COLUMNS_PADRAO = {
    'Conta': 'Conta Contábil',
    'Título Conta': 'Nome da Conta',
    'Data': 'Data Lançamento',
    'Numero': 'Número Docto',
    'Descricao': 'Descrição / Histórico',
    'Contra Partida - Credito': 'Contra Partida',
    'Filial': 'Filial',
    'Centro de Custo': 'Centro de Custo',
    'Item': 'Item',
    'Cod Cl. Valor': 'Cód. Classe Valor',
    'Debito': 'Valor Débito',
    'Credito': 'Valor Crédito'
}

@import_bp.route('/importacao', methods=['GET'])
@login_required
def Inicio():
    """
    Tela Inicial: Mostra as opções de tabelas disponíveis para importar.
    """
    svc = ImportacaoDadosService()
    return render_template('IMPORT/Index.html', sources=svc.TABELAS_PERMITIDAS)

@import_bp.route('/importacao/analise', methods=['POST'])
@login_required
def Analisar():
    """
    Recebe o arquivo, salva temporariamente e analisa as colunas para o usuário mapear.
    """
    if 'file' not in request.files:
        flash('Nenhum ficheiro selecionado.', 'danger')
        return redirect(url_for('Import.Inicio'))
    
    arquivo = request.files['file']
    origem = request.form.get('source')

    id_usuario = current_user.get_id() if current_user else "Anonimo"
    
    svc = ImportacaoDadosService()

    if not origem or origem not in svc.TABELAS_PERMITIDAS:
        RegistrarLog(f"Tentativa de upload para origem inválida: {origem} por {id_usuario}", "WARNING")
        flash('Origem inválida.', 'danger')
        return redirect(url_for('Import.Inicio'))

    if arquivo.filename == '':
        flash('Nenhum ficheiro selecionado.', 'danger')
        return redirect(url_for('Import.Inicio'))

    try:
        RegistrarLog(f"Recebendo arquivo {arquivo.filename} para análise ({origem}) - Usuário: {id_usuario}", "WEB")
        
        # Salva o arquivo no disco (pasta Temp) usando o serviço
        caminho_completo, nome_unico = svc.SalvarArquivoTemporario(arquivo)
        
        # 1. Analisa estrutura do Excel
        colunas_excel, tipos, linha_amostra = svc.ObterAmostraAnalise(nome_unico)
        
        # 2. Busca na memória se já existe mapeamento prévio para essa tabela
        mapeamento_salvo, transformacoes_salvas = svc.CarregarUltimaConfiguracao(origem)
        
        return render_template(
            'IMPORT/MapColumns.html', 
            filename=nome_unico,
            source=origem,
            excel_columns=colunas_excel,
            col_types=tipos,
            sample_row=linha_amostra,
            db_columns=DB_COLUMNS_PADRAO,
            saved_mapping=mapeamento_salvo,
            saved_transforms=transformacoes_salvas
        )

    except Exception as e:
        RegistrarLog(f"Erro na rota de análise para {arquivo.filename}", "ERROR", e)
        flash(f'Erro ao processar arquivo: {str(e)}', 'danger')
        return redirect(url_for('Import.Inicio'))
    
@import_bp.route('/importacao/api/preview', methods=['POST'])
@login_required
def ApiPrevia():
    """
    Rota AJAX: Retorna como um valor vai ficar após a transformação.
    """
    dados = request.json
    nome_arquivo = dados.get('filename')
    mapeamento = dados.get('mapping')
    transformacoes = dados.get('transforms')
    
    svc = ImportacaoDadosService()
    
    try:
        resultado = svc.ObterPreviaTransformacao(nome_arquivo, mapeamento, transformacoes)
        return jsonify(resultado), 200
    except Exception as e:
        RegistrarLog("Erro na API de Preview", "ERROR", e)
        return jsonify({"error": str(e)}), 500

@import_bp.route('/importacao/confirmar', methods=['POST'])
@login_required
def Confirmar():
    """
    Processa o formulário de mapeamento e dispara a importação real.
    """
    try:
        nome_arquivo = request.form.get('filename')
        origem = request.form.get('source')
        nome_usuario = current_user.get_id() or "Usuario_Sistema"
        
        RegistrarLog(f"Usuário {nome_usuario} confirmou mapeamento para {origem}", "WEB")

        mapeamento = {}
        transformacoes = {}
        
        # Varre o formulário separando o que é Mapeamento e o que é Transformação
        for key in request.form:
            if key.startswith('map_'):
                coluna_excel = key[4:] 
                val = request.form.get(key)
                if val and val != 'IGNORE': 
                    mapeamento[coluna_excel] = val
            
            if key.startswith('trans_'):
                coluna_excel = key[6:] 
                val = request.form.get(key)
                if val and val != 'none': 
                    transformacoes[coluna_excel] = val

        if not mapeamento:
            flash('Nenhuma coluna foi mapeada.', 'warning')
            return redirect(url_for('Import.Inicio'))
        
        svc = ImportacaoDadosService()
        
        # Executa a transação completa via serviço
        linhas, competencia = svc.ExecutarTransacaoImportacao(
            nome_arquivo, mapeamento, origem, 
            nome_usuario,
            transformacoes=transformacoes
        )
        flash(f'Sucesso! {linhas} registos importados em {origem} (Competência: {competencia}).', 'success')
        return redirect(url_for('Import.Historico'))
    except Exception as e:
        RegistrarLog(f"Erro fatal na rota Confirmar para {origem}", "ERROR", e)
        flash(f'Erro na importação: {str(e)}', 'danger')
        return redirect(url_for('Import.Inicio'))

@import_bp.route('/importacao/historico', methods=['GET'])
@login_required
def Historico():
    """
    Exibe o log de todas as importações feitas e permite Reversão.
    """
    svc = ImportacaoDadosService()
    logs = svc.ObterHistoricoImportacao()
    return render_template('IMPORT/History.html', logs=logs)

@import_bp.route('/importacao/reverter', methods=['POST'])
@login_required
def Reverter():
    """
    Ação de deletar uma importação feita erroneamente (Rollback).
    """
    id_log = request.form.get('log_id')
    motivo = request.form.get('reason')
    nome_usuario = current_user.get_id()

    if not motivo:
        flash('Motivo obrigatório.', 'warning')
        return redirect(url_for('Import.Historico'))
    
    svc = ImportacaoDadosService()
    
    try:
        RegistrarLog(f"Rota Reverter acionada por {nome_usuario}. ID: {id_log}", "WEB")
        qtd, tabela = svc.ExecutarReversao(id_log, nome_usuario, motivo)
        flash(f'Reversão concluída. {qtd} registros removidos de {tabela}.', 'warning')
    except Exception as e:
        RegistrarLog(f"Erro na interface de Reversão ID {id_log}", "ERROR", e)
        flash(f'Falha na reversão: {str(e)}', 'danger')
    return redirect(url_for('Import.Historico'))