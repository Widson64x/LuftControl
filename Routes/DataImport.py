from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

# Importa os serviços (agora com nomes bonitos em PascalCase)
from Services.DataImportService import (
    SaveTempFile, 
    GetFileAnalysisSample, 
    ExecuteImportTransaction, 
    GetImportHistory, 
    PerformRollback,
    GetPreviewTransformation,
    LoadLastConfig,
    ALLOWED_TABLES
)

# Cria o Blueprint com nome padronizado (primeira letra maiúscula)
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
def Index():
    """
    Tela Inicial: Mostra as opções de tabelas disponíveis para importar.
    """
    return render_template('IMPORT/Index.html', sources=ALLOWED_TABLES)

@import_bp.route('/importacao/analise', methods=['POST'])
@login_required
def Analyze():
    """
    Recebe o arquivo, salva temporariamente e analisa as colunas para o usuário mapear.
    """
    if 'file' not in request.files:
        flash('Nenhum ficheiro selecionado.', 'danger')
        return redirect(url_for('Import.Index'))
    
    file = request.files['file']
    source = request.form.get('source')

    if not source or source not in ALLOWED_TABLES:
        flash('Origem inválida.', 'danger')
        return redirect(url_for('Import.Index'))

    if file.filename == '':
        flash('Nenhum ficheiro selecionado.', 'danger')
        return redirect(url_for('Import.Index'))

    try:
        # Salva o arquivo no disco (pasta Temp)
        full_path, unique_filename = SaveTempFile(file)
        
        # 1. Analisa estrutura do Excel
        excel_cols, types, sample_row = GetFileAnalysisSample(unique_filename)
        
        # 2. Busca na memória se já existe mapeamento prévio para essa tabela
        saved_mapping, saved_transforms = LoadLastConfig(source)
        
        return render_template(
            'IMPORT/MapColumns.html', 
            filename=unique_filename,
            source=source,
            excel_columns=excel_cols,
            col_types=types,
            sample_row=sample_row,
            db_columns=DB_COLUMNS_PADRAO,
            # Injeta as configs salvas para preencher o formulário automaticamente
            saved_mapping=saved_mapping,
            saved_transforms=saved_transforms
        )

    except Exception as e:
        flash(f'Erro ao processar arquivo: {str(e)}', 'danger')
        return redirect(url_for('Import.Index'))
    
@import_bp.route('/importacao/api/preview', methods=['POST'])
@login_required
def ApiPreview():
    """
    Rota AJAX: Retorna como um valor vai ficar após a transformação, sem recarregar a tela.
    """
    data = request.json
    filename = data.get('filename')
    mapping = data.get('mapping')
    transforms = data.get('transforms')
    try:
        result = GetPreviewTransformation(filename, mapping, transforms)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@import_bp.route('/importacao/confirmar', methods=['POST'])
@login_required
def Confirm():
    """
    Processa o formulário de mapeamento e dispara a importação real.
    """
    try:
        filename = request.form.get('filename')
        source = request.form.get('source')
        mapping = {}
        transforms = {}
        
        # Varre o formulário separando o que é Mapeamento e o que é Transformação
        for key in request.form:
            if key.startswith('map_'):
                excel_col = key.replace('map-_', '')
                val = request.form.get(key)
                if val and val != 'IGNORE': mapping[excel_col] = val
            if key.startswith('trans_'):
                excel_col = key.replace('trans_', '')
                val = request.form.get(key)
                if val and val != 'none': transforms[excel_col] = val

        if not mapping:
            flash('Nenhuma coluna foi mapeada.', 'warning')
            return redirect(url_for('Import.Index'))
        
        # Executa a transação completa
        rows, comp = ExecuteImportTransaction(
            filename, mapping, source, 
            current_user.get_id() or "Usuario_Sistema",
            transformations=transforms
        )
        flash(f'Sucesso! {rows} registos importados em {source} (Competência: {comp}).', 'success')
        return redirect(url_for('Import.History'))
    except Exception as e:
        flash(f'Erro na importação: {str(e)}', 'danger')
        return redirect(url_for('Import.Index'))

@import_bp.route('/importacao/historico', methods=['GET'])
@login_required
def History():
    """
    Exibe o log de todas as importações feitas e permite Rollback.
    """
    logs = GetImportHistory()
    return render_template('IMPORT/History.html', logs=logs)

@import_bp.route('/importacao/rollback', methods=['POST'])
@login_required
def Rollback():
    """
    Ação de deletar uma importação feita erroneamente.
    """
    log_id = request.form.get('log_id')
    reason = request.form.get('reason')
    if not reason:
        flash('Motivo obrigatório.', 'warning')
        return redirect(url_for('Import.History'))
    try:
        count, table = PerformRollback(log_id, current_user.get_id(), reason)
        flash(f'Reversão concluída. {count} registros removidos de {table}.', 'warning')
    except Exception as e:
        flash(f'Falha na reversão: {str(e)}', 'danger')
    return redirect(url_for('Import.History'))