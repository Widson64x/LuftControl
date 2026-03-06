// ============================================================================
// Luft Control - MÓDULO: DRE POR OPERAÇÃO
// Arquivo: Static/JS/Reports/RelatorioDreOperacao.js
// ============================================================================

class RelatorioDreOperacao {
    constructor(modalSystem) {
        this.modal = modalSystem;
        this.rawData = [];      
        this.treeData = [];     
        this.dreState = {
            expanded: new Set(['root']), 
            hiddenCols: new Set(),       
            filters: {},                 
            globalSearch: '',
            searchMatches: [],      
            searchCurrentIndex: -1, 
            selectedYear: new Date().getFullYear(),            
            sort: { col: null, dir: 'asc' }, 
            // COLUNAS TEMPORÁRIAS DO DRE OPERAÇÃO
            columnsOrder: [
                'TRANSPORTE', 
                'ARMAZENAGEM', 
                'POLO_SC', 
                'CONSOLIDADO_OP', 
                'JANDIRA_CABREUVA', 
                'INTERGRUPO', 
                'NAO_OPERACIONAL', 
                'CONSOLIDADO'
            ],            
            viewMode: 'TIPO',
            scaleMode: 'dre',
            selectedCCs: ['Todos'], 
            ccFilter: 'Todos',      
            listaCCs: [], 
            showAccounts: false
        };
        this.debounceTimer = null;
        this.isLoading = false;        
        this.nosCalculados = [];
    }

    // --- COPIA EXATA DOS MÉTODOS DO RelatorioDreConsolidado.js ---

    toggleAccountVisibility() {
        if (this.isLoading) return;
        this.dreState.showAccounts = !this.dreState.showAccounts;
        this.renderInterface();
        this.renderTable();
    }

    handleYearChange(year) {
        if (this.isLoading) return;
        this.dreState.selectedYear = year;
        this.loadReport(); 
    }

    toggleScaleMode() {
        if (this.isLoading) return;
        this.dreState.scaleMode = (this.dreState.scaleMode === 'dre') ? 'normal' : 'dre';
        this.loadReport();
    }

    formatValue(value) {
        if (value === 0 || value === null) return '-';
        const isNegative = value < 0;
        const absValue = Math.abs(value);
        const formatted = absValue.toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
        return isNegative ? `(${formatted})` : formatted;
    }

    toggleViewMode() {
        if (this.isLoading) return;
        this.dreState.viewMode = (this.dreState.viewMode === 'TIPO') ? 'CC' : 'TIPO';
        this.loadReport(); 
    }

    getColDisplayName(col) {
        const names = {
            'TRANSPORTE': 'TRANSPORTE',
            'ARMAZENAGEM': 'ARMAZENAGEM',
            'POLO_SC': 'POLO SC',
            'CONSOLIDADO_OP': 'CONSOLIDADO - OPERACIONAL',
            'JANDIRA_CABREUVA': 'JANDIRA / CABREÚVA',
            'INTERGRUPO': 'INTERGRUPO',
            'NAO_OPERACIONAL': 'NÃO OPERACIONAL',
            'CONSOLIDADO': 'CONSOLIDADO'
        };
        return names[col] || col;
    }

    renderEmptyState() {
        const emptyHtml = `
            <div class="luft-hub-empty" style="flex: 1; border-radius: 0; border: none; border-top: 1px solid var(--luft-border);">
                <i class="fas fa-folder-open mb-3" style="font-size: 3rem; color: var(--luft-border-dark);"></i>
                <h4 style="color: var(--luft-text-main); font-weight: 700;">Sem dados contábeis</h4>
                <p style="color: var(--luft-text-muted);">Nenhum registro encontrado para este ano.</p>
            </div>`;
        this.modal.setContent(`<div style="display: flex; flex-direction: column; height: 100%;">${emptyHtml}</div>`);
    }

    async reloadDataAsync() {
        if (this.isLoading) return;
        this.isLoading = true;
        
        const container = document.getElementById('dreGridContainer');
        if (container) container.innerHTML = `<div class="luft-hub-loading" style="height: 100%;"><div class="luft-spinner"></div></div>`;

        try {
            // ATENÇÃO À ROTA NOVA!
            let urlBase = (typeof API_ROUTES !== 'undefined' && API_ROUTES.getDreOperacaoData) 
                    ? API_ROUTES.getDreOperacaoData 
                    : '/Relatorios/RelatorioRazao/DreOperacao';

            const scaleParam = this.dreState.scaleMode;
            const ccParam = encodeURIComponent(this.dreState.selectedCCs.join(','));
            const anoParam = this.dreState.selectedYear;

            const data = await APIUtils.get(`${urlBase}?scale_mode=${scaleParam}&centro_custo=${ccParam}&ano=${anoParam}`);
            
            if (!data || data.length === 0) {
                this.rawData = [];
                this.treeData = [];
                if (container) container.innerHTML = '<div class="p-4 text-center text-muted">Vazio (Nenhuma empresa selecionada ou sem dados para este ano)</div>';
            } else {
                this.rawData = data;
                await this.processTreeWithCalculated();
                this.renderTable();
            }
            this.renderInterface();
            
        } catch (error) {
            console.error(error);
            const isAuth = String(error).includes('403');
            if (container) {
                container.innerHTML = `
                    <div class="d-flex flex-column align-items-center justify-content-center p-5 text-center h-100">
                        <i class="fas ${isAuth ? 'fa-lock text-warning' : 'fa-exclamation-triangle text-danger'} mb-3" style="font-size: 3rem;"></i>
                        <h5 class="text-main font-bold">${isAuth ? 'Acesso Revogado' : 'Erro ao atualizar dados'}</h5>
                        <span class="text-muted text-sm mt-1">${isAuth ? 'Você não tem permissão para carregar estes filtros.' : error.message}</span>
                    </div>`;
            }
        } finally {
            this.isLoading = false;
        }
    }

    // TODO O RESTO DOS MÉTODOS SÃO IGUAIS AO DreConsolidado.js
    // Substitui `relatorioSystem.dreConsolidado` por `relatorioSystem.dreOperacao` no HTML inline gerado.
    
    processTree() {
        const root = [];
        const map = {}; 
        const colunas = this.dreState.columnsOrder;
        const labelMap = { 'Oper': 'CUSTOS', 'Adm':  'ADMINISTRATIVO', 'Coml': 'COMERCIAL' };

        const getOrCreateNode = (id, label, type, parentList) => {
            if (!map[id]) {
                const node = { id: id, label: label, type: type, children: [], values: {}, isVisible: true, isExpanded: this.dreState.expanded.has(id), ordem: 999999, estiloCss: null };
                colunas.forEach(c => node.values[c] = 0);
                map[id] = node;
                parentList.push(node);
            }
            return map[id];
        };

        const sumValues = (node, row) => { colunas.forEach(c => node.values[c] += (parseFloat(row[c]) || 0)); };

        this.rawData.forEach((row, index) => {
            let rawOrdem = null;
            if (row.ordem_prioridade !== null && row.ordem_prioridade !== undefined) rawOrdem = parseInt(row.ordem_prioridade);
            else if (row.Ordem !== null && row.Ordem !== undefined) rawOrdem = parseInt(row.Ordem);
            else if (row.ordem !== null && row.ordem !== undefined) rawOrdem = parseInt(row.ordem); 

            const tipoId = `T_${row.Tipo_CC}`;
            const labelExibicao = labelMap[row.Tipo_CC] || row.Tipo_CC;
            const tipoNode = getOrCreateNode(tipoId, labelExibicao, 'root', root);
            if (row.Root_Virtual_Id) tipoNode.virtualId = row.Root_Virtual_Id;
            if (row.Estilo_CSS && !tipoNode.estiloCss) tipoNode.estiloCss = row.Estilo_CSS;
            if (rawOrdem !== null && rawOrdem > 0 && rawOrdem < 1000) { if (tipoNode.ordem === 999999 || rawOrdem < tipoNode.ordem) tipoNode.ordem = rawOrdem; }
            sumValues(tipoNode, row);

            let currentNode = tipoNode;
            let currentId = tipoId;

            if (this.dreState.viewMode === 'CC' && row.Nome_CC) {
                const safeCCName = String(row.Nome_CC).replace(/[^a-zA-Z0-9]/g, '');
                currentId += `_CC_${safeCCName}`;
                const ccNode = getOrCreateNode(currentId, row.Nome_CC, 'group', currentNode.children);
                sumValues(ccNode, row);
                currentNode = ccNode;
            }

            if (row.Caminho_Subgrupos && row.Caminho_Subgrupos !== 'Não Classificado' && row.Caminho_Subgrupos !== 'Direto' && row.Caminho_Subgrupos !== 'Calculado') {
                const groups = row.Caminho_Subgrupos.split('||');
                const orders = row.Caminho_Ordem ? String(row.Caminho_Ordem).split('||') : [];
                groups.forEach((gName, idx) => {
                    const safeGName = gName.replace(/[^a-zA-Z0-9]/g, '');
                    currentId += `_G${idx}_${safeGName}`; 
                    const groupNode = getOrCreateNode(currentId, gName, 'group', currentNode.children);
                    let specificOrder = 999999;
                    if (orders[idx]) specificOrder = parseInt(orders[idx], 10);
                    if (!isNaN(specificOrder) && specificOrder > 0) { if (groupNode.ordem === 999999 || specificOrder < groupNode.ordem) groupNode.ordem = specificOrder; }
                    sumValues(groupNode, row);
                    currentNode = groupNode;
                });
            }

            const safeTitleName = String(row.Titulo_Conta || '').replace(/[^a-zA-Z0-9]/g, '');
            const tituloId = `TIT_${safeTitleName}_${currentId}`;
            const tituloNode = getOrCreateNode(tituloId, row.Titulo_Conta, 'account-group', currentNode.children);
            let ordemContaLeaf = 999999;
            if (row.Ordem_Conta !== undefined && row.Ordem_Conta !== null) ordemContaLeaf = parseInt(row.Ordem_Conta, 10);
            else if (row.Conta && !isNaN(parseInt(row.Conta))) ordemContaLeaf = parseInt(row.Conta, 10); 

            if (ordemContaLeaf < tituloNode.ordem) tituloNode.ordem = ordemContaLeaf;
            sumValues(tituloNode, row);

            const contaId = `C_${row.Conta}_${tituloId}`; 
            let contaNode = tituloNode.children.find(c => c.id === contaId);

            if (!contaNode) {
                contaNode = { id: contaId, label: `${row.Conta}`, rawTitle: row.Titulo_Conta, contaCodigo: row.Conta, tipoCC: row.Tipo_CC, type: 'account', children: [], values: {}, isVisible: true, ordem: ordemContaLeaf };
                colunas.forEach(c => contaNode.values[c] = 0);
                tituloNode.children.push(contaNode);
            }
            colunas.forEach(c => { contaNode.values[c] += (parseFloat(row[c]) || 0); });
        });

        this.treeData = root;
        this.applyFilters();
    }

    async processTreeWithCalculated() {
        this.processTree();
        const nosCalc = await this.loadNosCalculados(); 
        if (nosCalc.length > 0) {
            const valoresAgregados = this.agregarValoresPorTipo();
            const colunas = this.dreState.columnsOrder;
            
            nosCalc.forEach(noCalc => {
                if (!noCalc.formula) return;
                let contextoSuffix = null;
                const nomeUpper = (noCalc.nome || '').toUpperCase();
                if (nomeUpper.includes('CUSTO') || nomeUpper.includes('OPERACIONAL')) contextoSuffix = 'Oper';
                else if (nomeUpper.includes('ADMINISTRATIVO')) contextoSuffix = 'Adm';
                else if (nomeUpper.includes('COMERCIAL') || nomeUpper.includes('VENDAS')) contextoSuffix = 'Coml';

                const valores = {};
                colunas.forEach(col => { valores[col] = this.calcularValorNo(noCalc.formula, col, valoresAgregados, contextoSuffix); });

                const chaveMemoria = `no_virtual_${noCalc.id}`;
                if (!valoresAgregados[chaveMemoria]) valoresAgregados[chaveMemoria] = {};
                colunas.forEach(col => valoresAgregados[chaveMemoria][col] = valores[col]);

                let textoTooltip = noCalc.formula_descricao;
                if (!textoTooltip && noCalc.formula) {
                    const ops = noCalc.formula.operandos || [];
                    textoTooltip = `Fórmula Calculada: ${ops.map(o => o.label || o.id).join(', ')}`;
                }

                const rowBackend = this.rawData.find(r => (String(r.Root_Virtual_Id) === String(noCalc.id)) || (r.Titulo_Conta === noCalc.nome && r.Is_Calculado));
                let ordemCorreta = 50;
                if (rowBackend && rowBackend.ordem_prioridade !== null) ordemCorreta = rowBackend.ordem_prioridade;
                else if (noCalc.ordem !== null && noCalc.ordem !== undefined) ordemCorreta = noCalc.ordem;
                let cssFinal = noCalc.estilo_css; 
                if (!cssFinal && rowBackend && rowBackend.Estilo_CSS) cssFinal = rowBackend.Estilo_CSS; 

                const nodeCalc = { id: `calc_${noCalc.id}`, label: `${noCalc.nome}`, rawLabel: noCalc.nome, type: 'calculated', children: [], values: valores, isVisible: true, isExpanded: false, formulaDescricao: textoTooltip, estiloCss: cssFinal, tipoExibicao: noCalc.tipo_exibicao, ordem: ordemCorreta };
                this.treeData.push(nodeCalc);
            });
        }

        const nomesCalculados = new Set(this.treeData.filter(n => n.type === 'calculated').map(n => (n.rawLabel || n.label.replace('📊 ', '')).toUpperCase().trim()));
        this.treeData = this.treeData.filter(node => {
            if (node.type === 'root') {
                const labelPadrao = node.label.toUpperCase().trim();
                if (nomesCalculados.has(labelPadrao)) return false; 
            }
            return true;
        });

        const sortRecursive = (nodes) => {
            if (!nodes || nodes.length === 0) return;
            nodes.sort((a, b) => {
                const ordA = (a.ordem !== undefined && a.ordem !== null) ? a.ordem : 999999;
                const ordB = (b.ordem !== undefined && b.ordem !== null) ? b.ordem : 999999;
                if (ordA !== ordB) return ordA - ordB;
                const labelA = (a.rawLabel || a.label || '').replace(/<[^>]*>?/gm, '').trim();
                const labelB = (b.rawLabel || b.label || '').replace(/<[^>]*>?/gm, '').trim();
                return labelA.localeCompare(labelB);
            });
            nodes.forEach(node => { if (node.children && node.children.length > 0) sortRecursive(node.children); });
        };
        sortRecursive(this.treeData);
    }
    
    // 1. Adiciona esta variável para definirmos qual linha será o "100%" do AV
    // Geralmente é o nó da Receita Líquida ou Receita Bruta. 
    // Por enquanto, vamos assumir que o sistema vai procurar a linha de maior valor, ou podes forçar um ID aqui.
    getReferenciaAV(coluna) {
        // Tenta encontrar a Receita (geralmente o primeiro nó Root ou um Cálculo específico)
        // Se já souberes o ID da Receita (ex: 'calc_10'), podes colocar aqui.
        // Neste exemplo, vamos procurar o maior valor na coluna na raiz (para simular a Receita)
        let maxRef = 0;
        this.treeData.forEach(node => {
            if (node.type === 'root' || node.type === 'calculated') {
                if (node.values[coluna] > maxRef) maxRef = node.values[coluna];
            }
        });
        return maxRef === 0 ? 1 : maxRef; // Evita divisão por zero
    }

    renderTable() {
        const container = document.getElementById('dreGridContainer');
        if (!container) return;

        const cols = this.dreState.columnsOrder.filter(c => !this.dreState.hiddenCols.has(c));
        const rootHeaderName = this.dreState.viewMode === 'CC' ? 'Estrutura / Centro de Custo' : 'Estrutura DRE Operação';
        const anoAtual = this.dreState.selectedYear;

        // CABEÇALHO DUPLO: Uma linha para o nome da Operação, outra para Real e AV%
        let headerHtml = `
            <thead>
                <tr>
                    <th rowspan="2" style="vertical-align: middle; min-width: 300px;">
                        ${rootHeaderName}
                    </th>
                    ${cols.map(c => `
                        <th colspan="2" class="text-center" style="border-bottom: 1px solid var(--luft-border);">
                            <span class="cursor-pointer font-bold" onclick="relatorioSystem.dreOperacao.sortBy('${c}')">
                                ${this.getColDisplayName(c)}
                            </span>
                        </th>
                    `).join('')}
                </tr>
                <tr>
                    ${cols.map(c => `
                        <th class="text-end" style="min-width: 110px; font-size: 0.8rem; background: var(--luft-bg-panel);">Real ${anoAtual}</th>
                        <th class="text-end" style="min-width: 70px; font-size: 0.8rem; background: var(--luft-bg-panel); color: var(--luft-primary-600);">AV%</th>
                    `).join('')}
                </tr>
            </thead>`;

        let bodyRows = '';
        const showAccounts = this.dreState.showAccounts;

        // Calcula a referência (100%) para cada coluna antes de renderizar
        const referenciasAV = {};
        cols.forEach(c => { referenciasAV[c] = this.getReferenciaAV(c); });

        const renderNode = (node, level) => {
            if (node.type === 'account' && !showAccounts) return;
            if (!node.isVisible) return;
            const padding = level * 20 + 10;
            const isGroup = node.children && node.children.length > 0 && (showAccounts || node.children.some(child => child.type !== 'account'));
            const isExpanded = this.dreState.expanded.has(node.id);             
            
            let iconClass = '', iconStyle = '';
            if (node.type === 'calculated') { iconClass = 'fa-calculator'; iconStyle = 'color: var(--luft-warning-600);'; } 
            else if (node.type === 'root') {
                if (node.virtualId) { iconClass = 'fa-cube'; iconStyle = 'color: var(--luft-primary-600);'; } 
                else { iconClass = 'fa-layer-group'; iconStyle = 'color: var(--luft-primary-600);'; if (node.ordem < 1000 && !node.virtualId) { iconClass = 'fa-globe'; iconStyle = 'color: var(--luft-text-muted);'; } }
            }
            else if (node.type === 'group') { iconClass = 'fa-folder'; iconStyle = 'color: var(--luft-info-500);'; }
            else if (node.type === 'account-group') { iconClass = 'fa-file-invoice'; iconStyle = 'color: var(--luft-text-light);'; }
            else if (node.type === 'account') { iconClass = 'fa-file-alt'; iconStyle = 'color: var(--luft-text-light);'; }

            let iconHtml = '';
            if (isGroup) {
                iconHtml = `<div class="luft-toggle-icon" style="margin-right: 8px;" onclick="event.stopPropagation(); relatorioSystem.dreOperacao.toggleNode('${node.id}')"><i class="fas fa-chevron-${isExpanded ? 'down' : 'right'}"></i></div><i class="fas ${iconClass}" style="${iconStyle}; margin-right: 12px;"></i>`;
            } else {
                iconHtml = `<i class="fas ${iconClass}" style="margin-left: 32px; margin-right: 12px; ${iconStyle}"></i>`;
            }

            const cssString = node.estiloCss || '';
            const trStyle = cssString ? `style="${cssString}"` : '';
            
            const cellsHtml = cols.map(c => {
                const val = node.values[c] || 0;
                
                // Lógica de Cor do Valor Real
                let colorClass = '';
                if (val < 0) colorClass = 'text-danger'; 
                else if (val === 0) colorClass = 'text-muted';
                
                // Formatação do Valor Real
                let displayVal = '-';
                if (val !== 0) {
                    if (this.dreState.scaleMode === 'dre') displayVal = this.formatValue(val);
                    else displayVal = FormatUtils.formatNumber(val);
                }
                if (node.tipoExibicao === 'percentual' && val !== 0) displayVal = val.toFixed(2) + '%';
                
                // --- CÁLCULO DA ANÁLISE VERTICAL (AV%) ---
                let displayAV = '-';
                let colorClassAV = 'text-muted';
                if (val !== 0 && node.tipoExibicao !== 'percentual') {
                    const av = (val / referenciasAV[c]) * 100;
                    displayAV = av.toFixed(1) + '%';
                    
                    // Colore o AV% de forma suave dependendo se é despesa/receita
                    if (av < 0) colorClassAV = 'text-danger';
                    else if (av > 0) colorClassAV = 'text-primary';
                }

                return `
                    <td class="text-end ${colorClass}" style="font-family: monospace; ${cssString}">
                        ${displayVal}
                    </td>
                    <td class="text-end ${colorClassAV}" style="font-family: monospace; font-size: 0.85em; background: rgba(0,0,0,0.01); border-right: 1px solid var(--luft-border-light); ${cssString}">
                        ${displayAV}
                    </td>
                `;
            }).join('');

            const searchClass = this.dreState.searchMatches.includes(node.id) ? 'luft-search-match' : '';

            bodyRows += `<tr id="row_${node.id}" class="luft-dre-row-${node.type} ${searchClass}" ${trStyle}>
                    <td style="padding-left: ${padding}px; ${cssString}"> 
                        <div class="d-flex align-items-center" style="gap: 4px;">
                            ${iconHtml}
                            <span class="text-truncate" style="margin-left: 6px;" title="${node.formulaDescricao || ''}">${node.label}</span>
                        </div>
                    </td>${cellsHtml}</tr>`;

            if (isGroup && isExpanded) node.children.forEach(child => renderNode(child, level + 1));
        };

        this.treeData.forEach(node => renderNode(node, 0));
        container.innerHTML = `<table class="luft-table-modern"> ${headerHtml}<tbody>${bodyRows}</tbody></table>`;
    }
    
    // TODAS AS OUTRAS FUNÇÕES COM AS REFERÊNCIAS ALTERADAS PARA dreOperacao
    async loadCCList() {
        if (this.dreState.listaCCs.length > 0) return; 
        try {
            const url = (typeof API_ROUTES !== 'undefined' && API_ROUTES.getListaCCs) ? API_ROUTES.getListaCCs : '/Relatorios/RelatorioRazao/ListaCentrosCusto';
            const lista = await APIUtils.get(url);
            if(lista && Array.isArray(lista)) this.dreState.listaCCs = lista;
        } catch (e) { console.error("Erro ao carregar lista de CCs:", e); }
    }

    handleCCChange(selectElement) {
        if (this.isLoading) return;
        const selectedOptions = Array.from(selectElement.selectedOptions).map(option => option.value);
        let newSelectedCCs = [];

        if (selectedOptions.includes('Todos') || selectedOptions.length === 0) newSelectedCCs = ['Todos'];
        else newSelectedCCs = selectedOptions.filter(v => v !== 'Todos');

        this.dreState.selectedCCs = newSelectedCCs;
        this.dreState.ccFilter = newSelectedCCs.join(',');
        this.loadReport();
    }

    openCCFilterDropdown(buttonElement) {
        if (this.isLoading) return;
        const dropdownId = 'luft-cc-dropdown';
        let dropdown = document.getElementById(dropdownId);
        if (dropdown) { dropdown.remove(); return; }

        dropdown = document.createElement('div');
        dropdown.id = dropdownId;
        dropdown.className = 'luft-dropdown-menu'; 
        
        const searchHtml = `<div class="luft-dropdown-search"><i class="fas fa-search"></i><input type="text" placeholder="Pesquisar Centro..." id="ccSearchInput" oninput="relatorioSystem.dreOperacao.filterCCList(this.value)"></div>`;
        const optionsHtml = this.dreState.listaCCs.map(cc => {
            const isSelected = this.dreState.selectedCCs.includes(String(cc.codigo));
            return `<label class="luft-dropdown-option" data-name="${cc.nome.toLowerCase()}" data-code="${cc.codigo}"><input type="checkbox" class="luft-checkbox" value="${cc.codigo}" ${isSelected ? 'checked' : ''} onchange="relatorioSystem.dreOperacao.handleCCCheckboxChange(this)"><span>${cc.nome}</span></label>`;
        }).join('');
        const isAllSelected = this.dreState.selectedCCs.includes('Todos') || this.dreState.selectedCCs.length === 0;
        const allOptionHtml = `<div class="luft-dropdown-all"><label class="luft-dropdown-option" style="color: var(--luft-primary-700); font-weight: 700;"><input type="checkbox" class="luft-checkbox" value="Todos" id="chkSelectAllCC" ${isAllSelected ? 'checked' : ''} onchange="relatorioSystem.dreOperacao.handleSelectAllCC(this.checked)"><span>[ Selecionar Todos ]</span></label></div>`;

        dropdown.innerHTML = searchHtml + `<div class="luft-dropdown-list">${allOptionHtml}${optionsHtml}</div>`;
        const rect = buttonElement.getBoundingClientRect();
        dropdown.style.top = `${rect.bottom + 6}px`; dropdown.style.left = `${rect.left}px`; 

        document.body.appendChild(dropdown);
        setTimeout(() => { const searchInput = document.getElementById('ccSearchInput'); if (searchInput) searchInput.focus(); }, 50);

        const closeOnOutsideClick = (event) => {
            if (dropdown && !dropdown.contains(event.target) && !buttonElement.contains(event.target)) {
                dropdown.remove(); document.removeEventListener('click', closeOnOutsideClick);
            }
        };
        setTimeout(() => { document.addEventListener('click', closeOnOutsideClick); }, 100);
    }

    handleCCCheckboxChange(checkbox) {
        const code = checkbox.value;
        let currentCCs = this.dreState.selectedCCs.filter(v => v !== 'Todos');
        if (checkbox.checked) { if (!currentCCs.includes(code)) currentCCs.push(code); } else { currentCCs = currentCCs.filter(v => v !== code); }
        if (currentCCs.length === 0) { this.dreState.selectedCCs = ['Todos']; document.getElementById('chkSelectAllCC').checked = true; } else { this.dreState.selectedCCs = currentCCs; document.getElementById('chkSelectAllCC').checked = false; }
        this.updateCCButtonDisplay();
        clearTimeout(this.debounceTimer); this.debounceTimer = setTimeout(() => { this.loadReport(); }, 800);
    }
    
    handleSelectAllCC(isChecked) {
         const checkboxes = document.querySelectorAll('.luft-dropdown-list input[type="checkbox"]');
         if (isChecked) { checkboxes.forEach(chk => chk.checked = true); this.dreState.selectedCCs = ['Todos']; } else { checkboxes.forEach(chk => chk.checked = false); this.dreState.selectedCCs = []; }
         this.updateCCButtonDisplay();
         clearTimeout(this.debounceTimer); this.debounceTimer = setTimeout(() => { this.loadReport(); }, 800);
    }

    filterCCList(searchTerm) {
        const term = searchTerm.toLowerCase();
        document.querySelectorAll('.luft-dropdown-list .luft-dropdown-option:not(.luft-dropdown-all label)').forEach(label => {
            label.style.display = (label.getAttribute('data-name').includes(term) || label.getAttribute('data-code').includes(term)) ? 'flex' : 'none';
        });
    }
    
    updateCCButtonDisplay() {
        const displaySpan = document.getElementById('ccFilterDisplay');
        const button = document.getElementById('ccFilterButton');
        if (!displaySpan) return;
        if (this.dreState.selectedCCs.includes('Todos')) { displaySpan.textContent = 'Todos os Centros'; if(button) button.classList.remove('has-filter'); } 
        else { displaySpan.textContent = `${this.dreState.selectedCCs.length} Centro(s) Selecionado(s)`; if(button) button.classList.add('has-filter'); }
    }

    async loadReport() {
        if (!this.modal) this.modal = new LuftModalWrapper('modalRelatorio');
        await this.loadCCList();

        const scaleTitle = this.dreState.scaleMode === 'dre' ? '(Em Milhares)' : '(Valor Integral)';
        const totalSelecionados = this.dreState.selectedCCs.length;
        let ccTitle = this.dreState.selectedCCs.includes('Todos') ? 'Todos os Centros' : `Filtro: ${totalSelecionados} CC(s) selecionados`;
        
        this.modal.open(`<i class="fas fa-layer-group text-info"></i> DRE por Operação`, `${scaleTitle} | ${ccTitle}`);
        this.modal.showLoading('Calculando DRE Operação...');

        try {
            const urlBase = (typeof API_ROUTES !== 'undefined' && API_ROUTES.getDreOperacaoData) ? API_ROUTES.getDreOperacaoData : '/Relatorios/RelatorioRazao/DreOperacao';
            const ccParam = encodeURIComponent(this.dreState.selectedCCs.join(','));
            const data = await APIUtils.get(`${urlBase}?scale_mode=${this.dreState.scaleMode}&centro_custo=${ccParam}&ano=${this.dreState.selectedYear}`);
            if (!data || data.length === 0) {
                this.rawData = []; this.treeData = []; this.renderInterface();
                setTimeout(() => { const container = document.getElementById('dreGridContainer'); if(container) { container.innerHTML = `<div class="luft-hub-empty" style="flex: 1; border: none; border-radius: 0;"><i class="fas fa-filter text-muted mb-3" style="font-size: 3rem;"></i><h4 class="text-main font-bold">Sem dados para exibição</h4><p class="text-muted">Verifique a seleção do ano e centros de custo.</p></div>`; } }, 100);
                return;
            }
            this.rawData = data; await this.processTreeWithCalculated(); this.renderInterface();
        } catch (error) { console.error(error); this.modal.showError(error); }
    }
    
    renderInterface() {
        const isDreMode = this.dreState.scaleMode === 'dre';
        const showAccounts = this.dreState.showAccounts;
        let nomeCCSelecionado = this.dreState.selectedCCs.includes('Todos') ? 'Todos' : `${this.dreState.selectedCCs.length} selecionados`;

        const toolbar = `
            <div class="luft-dre-toolbar">
                <div class="d-flex gap-2 align-items-center flex-wrap">
                    <button id="ccFilterButton" class="luft-cc-selector" onclick="relatorioSystem.dreOperacao.openCCFilterDropdown(this)" title="Filtrar por Centro de Custo">
                        <i class="fas fa-building text-muted"></i> <span id="ccFilterDisplay" class="luft-cc-display">Todos os Centros</span> <i class="fas fa-chevron-down text-xs text-muted"></i>
                    </button>
                    <select class="luft-year-selector" onchange="relatorioSystem.dreOperacao.handleYearChange(this.value)">
                        <option value="2025" ${this.dreState.selectedYear == 2025 ? 'selected' : ''}>2025</option>
                        <option value="2026" ${this.dreState.selectedYear == 2026 ? 'selected' : ''}>2026</option>
                    </select>
                    <div class="luft-separator-vertical"></div>
                    <button class="luft-dre-btn ${isDreMode ? 'luft-dre-btn-active' : ''}" onclick="relatorioSystem.dreOperacao.toggleScaleMode()">
                        <i class="fas ${isDreMode ? 'fa-divide' : 'fa-dollar-sign'}"></i> ${isDreMode ? 'Milhares (DRE)' : 'Reais'}
                    </button>
                    <button class="luft-dre-btn ${showAccounts ? 'luft-dre-btn-active' : ''}" onclick="relatorioSystem.dreOperacao.toggleAccountVisibility()">
                        <i class="fas ${showAccounts ? 'fa-eye' : 'fa-eye-slash'}"></i> ${showAccounts ? 'Contas' : 'Ocultar Contas'}
                    </button>
                    <div class="luft-separator-vertical"></div>
                    <div class="luft-hub-search" style="max-width: 250px;">
                        <i class="fas fa-search luft-hub-search-icon"></i>
                        <input type="text" id="dreGlobalSearch" class="luft-hub-search-input" style="padding-top: 8px; padding-bottom: 8px;" placeholder="Buscar na árvore..." value="${this.dreState.globalSearch}" oninput="relatorioSystem.dreOperacao.handleGlobalSearch(this.value)" onkeydown="if(event.key === 'Enter') { event.preventDefault(); relatorioSystem.dreOperacao.navigateSearchNext(); }">
                    </div>
                </div>
                <div class="d-flex gap-2 align-items-center">
                    <button class="luft-dre-btn" onclick="relatorioSystem.dreOperacao.toggleAllNodes(true)" title="Expandir Tudo"><i class="fas fa-expand-arrows-alt"></i></button>
                    <button class="luft-dre-btn" onclick="relatorioSystem.dreOperacao.toggleAllNodes(false)" title="Recolher Tudo"><i class="fas fa-compress-arrows-alt"></i></button>
                    <button class="luft-dre-btn" onclick="relatorioSystem.dreOperacao.openColumnManager()" title="Gerenciar Colunas"><i class="fas fa-columns"></i></button>
                </div>
            </div>`;
        
        const gridContainer = `<div id="dreGridContainer" class="luft-table-container" style="flex: 1;"></div>`;
        const footer = `<div class="luft-dre-footer"><span>Visão: <strong>Por Operação</strong> | Filtro CC: <strong>${nomeCCSelecionado}</strong> | Escala: <strong>${this.dreState.scaleMode.toUpperCase()}</strong></span><span>Atualizado: ${new Date().toLocaleTimeString('pt-BR')}</span></div>`;

        this.modal.setContent(`<div style="display: flex; flex-direction: column; height: 100%;">${toolbar}${gridContainer}${footer}</div>`);
        this.updateCCButtonDisplay(); this.renderTable();
    }

    applyFilters() { /* idêntico */
        const colFilters = this.dreState.filters; const hasColFilters = Object.keys(colFilters).length > 0;
        const checkVisibility = (node) => {
            let matchesCols = true;
            if (hasColFilters) {
                for (const [col, filterVal] of Object.entries(colFilters)) {
                    if (!filterVal) continue;
                    const nodeVal = node.values[col]; let pass = false; const cleanFilter = filterVal.replace(',', '.').trim();
                    if (cleanFilter.startsWith('>')) pass = nodeVal > parseFloat(cleanFilter.substring(1));
                    else if (cleanFilter.startsWith('<')) pass = nodeVal < parseFloat(cleanFilter.substring(1));
                    else pass = nodeVal.toString().includes(cleanFilter); 
                    if (!pass) { matchesCols = false; break; }
                }
            }
            let hasVisibleChildren = false;
            if (node.children) node.children.forEach(child => { if (checkVisibility(child)) hasVisibleChildren = true; });
            const isVisible = matchesCols || hasVisibleChildren; node.isVisible = isVisible;
            if (isVisible && hasColFilters) this.dreState.expanded.add(node.id); 
            return isVisible;
        };
        this.treeData.forEach(node => checkVisibility(node));
    }

    handleGlobalSearch(val) { this.dreState.globalSearch = val; if (!val) { this.dreState.searchMatches = []; this.dreState.searchCurrentIndex = -1; this.renderTable(); return; } clearTimeout(this.debounceTimer); this.debounceTimer = setTimeout(() => { this.performSearchTraversal(); }, 400); }
    performSearchTraversal() {
        const term = this.dreState.globalSearch.toLowerCase(); this.dreState.searchMatches = []; this.dreState.searchCurrentIndex = -1; if (!term) return;
        const findAndExpand = (nodes, parentIds = []) => { nodes.forEach(node => { const match = node.label.toLowerCase().includes(term); if (match) { this.dreState.searchMatches.push(node.id); parentIds.forEach(pid => this.dreState.expanded.add(pid)); } if (node.children && node.children.length > 0) findAndExpand(node.children, [...parentIds, node.id]); }); };
        findAndExpand(this.treeData);
        if (this.dreState.searchMatches.length > 0) { this.renderTable(); setTimeout(() => this.navigateSearchNext(), 100); } else { this.renderTable(); }
    }
    navigateSearchNext() { if (this.dreState.searchMatches.length === 0) return; this.dreState.searchCurrentIndex++; if (this.dreState.searchCurrentIndex >= this.dreState.searchMatches.length) { this.dreState.searchCurrentIndex = 0; } this.scrollToNode(this.dreState.searchMatches[this.dreState.searchCurrentIndex]); this.updateSearchHighlights(); }
    scrollToNode(nodeId) { const row = document.getElementById(`row_${nodeId}`); if (row) row.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
    updateSearchHighlights() { document.querySelectorAll('.luft-search-current-match').forEach(el => el.classList.remove('luft-search-current-match')); const currentId = this.dreState.searchMatches[this.dreState.searchCurrentIndex]; const row = document.getElementById(`row_${currentId}`); if (row) row.classList.add('luft-search-current-match'); }

    handleColFilter(col, val) { if (!val) delete this.dreState.filters[col]; else this.dreState.filters[col] = val; this.debounceRender(); }
    debounceRender() { clearTimeout(this.debounceTimer); this.debounceTimer = setTimeout(() => { this.applyFilters(); this.renderTable(); }, 400); }
    toggleNode(id) { if (this.dreState.expanded.has(id)) this.dreState.expanded.delete(id); else this.dreState.expanded.add(id); this.renderTable(); }
    toggleAllNodes(expand) { const recurse = (nodes) => { nodes.forEach(n => { if (expand) this.dreState.expanded.add(n.id); else this.dreState.expanded.delete(n.id); if (n.children) recurse(n.children); }); }; recurse(this.treeData); this.renderTable(); }
    
    openColumnManager() {
        const allCols = this.dreState.columnsOrder; const allVisible = allCols.every(c => !this.dreState.hiddenCols.has(c));
        const modalHtml = `
            <div style="display: flex; flex-direction: column; height: 100%;">
                <div class="luft-col-mgr-header">
                    <h5><i class="fas fa-columns text-primary me-3"></i> Gerenciar Colunas</h5>
                    <button class="luft-dre-btn" onclick="relatorioSystem.dreOperacao.toggleAllColumns(this)" style="border-radius: var(--luft-radius-full);"><i class="fas ${allVisible ? 'fa-check-circle' : 'fa-circle'}"></i> ${allVisible ? 'Desmarcar Todos' : 'Selecionar Todos'}</button>
                </div>
                <div class="luft-col-mgr-grid">
                    ${allCols.map(c => { const isVisible = !this.dreState.hiddenCols.has(c); return `<label class="luft-col-option ${isVisible ? 'selected' : ''}"><input type="checkbox" class="luft-col-checkbox" value="${c}" ${isVisible ? 'checked' : ''} onchange="relatorioSystem.dreOperacao.handleColumnToggle(this, '${c}')"><span>${this.getColDisplayName(c)}</span></label>`; }).join('')}
                </div>
                <div class="luft-col-mgr-footer"><button class="btn btn-primary d-flex align-items-center gap-2" onclick="document.querySelector('.luft-col-mgr-backdrop').remove(); relatorioSystem.dreOperacao.renderTable()"><i class="fas fa-check"></i> Aplicar Alterações</button></div>
            </div>`;
        const colModal = document.createElement('div'); colModal.className = 'luft-col-mgr-backdrop active'; colModal.innerHTML = `<div class="luft-col-mgr-window">${modalHtml}</div>`;
        colModal.onclick = (e) => { if(e.target === colModal) { colModal.remove(); this.renderTable(); } }; document.body.appendChild(colModal);
    }
    handleColumnToggle(checkbox, col) { if (checkbox.checked) { this.dreState.hiddenCols.delete(col); checkbox.closest('.luft-col-option').classList.add('selected'); } else { this.dreState.hiddenCols.add(col); checkbox.closest('.luft-col-option').classList.remove('selected'); } this.updateSelectAllBtnState(); }
    toggleAllColumns(btn) { const checkboxes = document.querySelectorAll('.luft-col-mgr-grid input[type="checkbox"]'); const isCurrentlyAllChecked = btn.querySelector('i').classList.contains('fa-check-circle'); const newState = !isCurrentlyAllChecked; checkboxes.forEach(chk => { chk.checked = newState; const col = chk.value; const parent = chk.closest('.luft-col-option'); if (newState) { this.dreState.hiddenCols.delete(col); parent.classList.add('selected'); } else { this.dreState.hiddenCols.add(col); parent.classList.remove('selected'); } }); this.updateSelectAllBtnState(); }
    updateSelectAllBtnState() { const btn = document.querySelector('.luft-col-mgr-header button'); if(!btn) return; const allCols = this.dreState.columnsOrder; const allVisible = allCols.every(c => !this.dreState.hiddenCols.has(c)); if(allVisible) btn.innerHTML = '<i class="fas fa-check-circle"></i> Desmarcar Todos'; else btn.innerHTML = '<i class="fas fa-circle"></i> Selecionar Todos'; }
    toggleColumn(col) { if (this.dreState.hiddenCols.has(col)) this.dreState.hiddenCols.delete(col); else this.dreState.hiddenCols.add(col); }
    sortBy(col) { if (this.dreState.sort.col === col) this.dreState.sort.dir = this.dreState.sort.dir === 'asc' ? 'desc' : 'asc'; else { this.dreState.sort.col = col; this.dreState.sort.dir = 'desc'; } const sortNodes = (nodes) => { nodes.sort((a, b) => { const valA = a.values[col] || 0; const valB = b.values[col] || 0; return this.dreState.sort.dir === 'asc' ? valA - valB : valB - valA; }); nodes.forEach(n => { if (n.children) sortNodes(n.children); }); }; sortNodes(this.treeData); this.renderTable(); }
    exportToCsv() { let csv = "data:text/csv;charset=utf-8,"; const visibleCols = this.dreState.columnsOrder.filter(c => !this.dreState.hiddenCols.has(c)); csv += `# Relatório DRE Operação\r\nEstrutura;${visibleCols.map(c => this.getColDisplayName(c)).join(";")}\r\n`; const processRow = (node, prefix = "") => { if (!node.isVisible) return; csv += `"${prefix}${node.label}";` + visibleCols.map(c => (node.values[c]||0).toFixed(2).replace('.',',')).join(";") + "\r\n"; if(node.children) node.children.forEach(child => processRow(child, prefix + "  ")); }; this.treeData.forEach(n => processRow(n)); const link = document.createElement("a"); link.href = encodeURI(csv); link.download = "dre_operacao.csv"; document.body.appendChild(link); link.click(); link.remove(); }
    
    async loadNosCalculados() { try { const r = await APIUtils.get((API_ROUTES?.getNosCalculados) || '/Configuracao/GetNosCalculados'); this.nosCalculados = r || []; return this.nosCalculados; } catch { return []; } }
    
    calcularValorNo(formula, mes_ou_coluna, valoresAgregados, contextoSuffix = null) {
        if (!formula || !formula.operandos) return 0;
        const valores = formula.operandos.map(op => {
            const idOp = String(op.id).trim(); const tipoOp = op.tipo;
            if (tipoOp === 'conta' && contextoSuffix) { const chaveEspecifica = `conta_${idOp}${contextoSuffix}`; if (valoresAgregados[chaveEspecifica] && valoresAgregados[chaveEspecifica][mes_ou_coluna] !== undefined) return valoresAgregados[chaveEspecifica][mes_ou_coluna]; }
            return valoresAgregados[`${tipoOp}_${idOp}`]?.[mes_ou_coluna] || 0;
        });
        let res = 0;
        if (formula.operacao === 'soma') res = valores.reduce((a, b) => a + b, 0);
        else if (formula.operacao === 'subtracao') res = valores[0] - valores.slice(1).reduce((a, b) => a + b, 0);
        else if (formula.operacao === 'multiplicacao') res = valores.reduce((a, b) => a * b, 1);
        else if (formula.operacao === 'divisao') res = valores[1] !== 0 ? valores[0] / valores[1] : 0;
        if (formula.multiplicador) res *= formula.multiplicador;
        return res;
    }

    agregarValoresPorTipo() {
        const agregados = {}; const colunas = this.dreState.columnsOrder;
        const initKey = (key) => { if (!agregados[key]) { agregados[key] = {}; colunas.forEach(c => agregados[key][c] = 0); } };
        const traverse = (node) => {
            if (node.type === 'root') { const rawId = node.id.replace('T_', '').replace('CC_', ''); const keyTipo = `tipo_cc_${rawId}`; initKey(keyTipo); colunas.forEach(c => agregados[keyTipo][c] += (node.values[c] || 0)); }
            if (node.virtualId) { const keyVirt = `no_virtual_${node.virtualId}`; initKey(keyVirt); colunas.forEach(c => agregados[keyVirt][c] += (node.values[c] || 0)); }
            if (node.type === 'group') { const keySub = `subgrupo_${node.label}`; initKey(keySub); colunas.forEach(c => agregados[keySub][c] += (node.values[c] || 0)); }
            if (node.type === 'account' && node.contaCodigo) {
                const keyPura = `conta_${node.contaCodigo}`; initKey(keyPura); colunas.forEach(c => agregados[keyPura][c] += (node.values[c] || 0));
                if (node.tipoCC) { const tipoClean = node.tipoCC.trim(); if (['Coml', 'Oper', 'Adm'].includes(tipoClean)) { const keyComposta = `conta_${node.contaCodigo}${tipoClean}`; initKey(keyComposta); colunas.forEach(c => agregados[keyComposta][c] += (node.values[c] || 0)); } }
            }
            if (node.children && node.children.length > 0) node.children.forEach(child => traverse(child));
        };
        this.treeData.forEach(rootNode => traverse(rootNode)); return agregados;
    }
}