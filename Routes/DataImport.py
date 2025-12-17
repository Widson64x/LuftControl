from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from Services.ImportService import (
    save_temp_file, 
    get_file_analysis_sample, 
    execute_import_transaction, 
    get_import_history, 
    perform_rollback,
    get_preview_transformation,
    load_last_config,
    ALLOWED_TABLES
)
import_bp = Blueprint('import_data', __name__)

# Colunas Padrão do Banco de Dados
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

@import_bp.route('/Importacao', methods=['GET'])
@login_required
def index():
    """Tela Inicial"""
    return render_template('IMPORT/Index.html', sources=ALLOWED_TABLES)

@import_bp.route('/Importacao/Analise', methods=['POST'])
@login_required
def analyze():
    if 'file' not in request.files:
        flash('Nenhum ficheiro selecionado.', 'danger')
        return redirect(url_for('import_data.index'))
    
    file = request.files['file']
    source = request.form.get('source')

    if not source or source not in ALLOWED_TABLES:
        flash('Origem inválida.', 'danger')
        return redirect(url_for('import_data.index'))

    if file.filename == '':
        flash('Nenhum ficheiro selecionado.', 'danger')
        return redirect(url_for('import_data.index'))

    try:
        full_path, unique_filename = save_temp_file(file)
        
        # 1. Analisa Arquivo
        excel_cols, types, sample_row = get_file_analysis_sample(unique_filename)
        
        # 2. Carrega Configuração Salva (Cache)
        saved_mapping, saved_transforms = load_last_config(source)
        
        return render_template(
            'IMPORT/MapColumns.html', 
            filename=unique_filename,
            source=source,
            excel_columns=excel_cols,
            col_types=types,
            sample_row=sample_row,
            db_columns=DB_COLUMNS_PADRAO,
            # Passamos as configurações salvas para o Template
            saved_mapping=saved_mapping,
            saved_transforms=saved_transforms
        )

    except Exception as e:
        flash(f'Erro ao processar arquivo: {str(e)}', 'danger')
        return redirect(url_for('import_data.index'))
    
@import_bp.route('/Importacao/API/Preview', methods=['POST'])
@login_required
def api_preview():
    data = request.json
    filename = data.get('filename')
    mapping = data.get('mapping')
    transforms = data.get('transforms')
    try:
        result = get_preview_transformation(filename, mapping, transforms)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@import_bp.route('/Importacao/Confirmar', methods=['POST'])
@login_required
def confirm():
    try:
        filename = request.form.get('filename')
        source = request.form.get('source')
        mapping = {}
        transforms = {}
        for key in request.form:
            if key.startswith('map_'):
                excel_col = key.replace('map_', '')
                val = request.form.get(key)
                if val and val != 'IGNORE': mapping[excel_col] = val
            if key.startswith('trans_'):
                excel_col = key.replace('trans_', '')
                val = request.form.get(key)
                if val and val != 'none': transforms[excel_col] = val

        if not mapping:
            flash('Nenhuma coluna foi mapeada.', 'warning')
            return redirect(url_for('import_data.index'))
        
        rows, comp = execute_import_transaction(
            filename, mapping, source, 
            current_user.get_id() or "Usuario_Sistema",
            transformations=transforms
        )
        flash(f'Sucesso! {rows} registos importados em {source} (Competência: {comp}).', 'success')
        return redirect(url_for('import_data.history'))
    except Exception as e:
        flash(f'Erro na importação: {str(e)}', 'danger')
        return redirect(url_for('import_data.index'))

@import_bp.route('/Importacao/Historico', methods=['GET'])
@login_required
def history():
    logs = get_import_history()
    return render_template('IMPORT/History.html', logs=logs)

@import_bp.route('/Importacao/Rollback', methods=['POST'])
@login_required
def rollback():
    log_id = request.form.get('log_id')
    reason = request.form.get('reason')
    if not reason:
        flash('Motivo obrigatório.', 'warning')
        return redirect(url_for('import_data.history'))
    try:
        count, table = perform_rollback(log_id, current_user.get_id(), reason)
        flash(f'Reversão concluída. {count} registros removidos de {table}.', 'warning')
    except Exception as e:
        flash(f'Falha na reversão: {str(e)}', 'danger')
    return redirect(url_for('import_data.history'))