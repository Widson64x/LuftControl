// ============================================================================
// Luft Control - MÓDULO: DRE GERENCIAL E RENTABILIDADE
// Arquivo: Static/JS/Reports/RelatorioDRE.js
// ============================================================================

class RelatorioDRE {
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
            columnsOrder: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez', 'Total_Ano'],            
            selectedOrigins: ['FARMA', 'FARMADIST', 'INTEC'], 
            viewMode: 'TIPO',
            scaleMode: 'dre',
            selectedCCs: ['Todos'], 
            ccFilter: 'Todos',      
            listaCCs: [], 
            showAccounts: false,
            origemFilter: null
        };
        this.debounceTimer = null;
        this.isLoading = false;        
        this.nosCalculados = [];
    }

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
        this.loadReport(this.dreState.origemFilter);
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
        this.loadReport(this.dreState.selectedOrigins.join(',')); 
    }

    renderEmptyState() {
        const emptyHtml = `
            <div class="dre-toolbar d-flex justify-content-between align-items-center p-3 border-bottom border-primary bg-tertiary">
                <div class="d-flex gap-2 align-items-center">${this.renderOrigemFilter()}</div>
            </div>
            <div class="p-4 text-center" style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;">
                <i class="fas fa-database fa-3x text-muted mb-3"></i>
                <h4 class="text-secondary">Sem dados</h4>
                <p class="text-muted">Nenhum registro encontrado para "${this.dreState.origemFilter}".</p>
            </div>`;
        this.modal.setContent(`<div style="display: flex; flex-direction: column; height: 100%;">${emptyHtml}</div>`);
    }

    async reloadDataAsync() {
        if (this.isLoading) return;
        this.isLoading = true;
        
        const container = document.getElementById('dreGridContainer');
        if (container) container.innerHTML = `<div class="loading-container" style="height: 100%;"><div class="loading-spinner"></div></div>`;

        try {
            let urlBase = (typeof API_ROUTES !== 'undefined' && API_ROUTES.getRentabilidadeData) 
                    ? API_ROUTES.getRentabilidadeData 
                    : '/Reports/RelatorioRazao/Rentabilidade';

            const origemParam = encodeURIComponent(this.dreState.selectedOrigins.join(','));
            const scaleParam = this.dreState.scaleMode;
            const ccParam = encodeURIComponent(this.dreState.selectedCCs.join(','));
            const anoParam = this.dreState.selectedYear;

            const data = await APIUtils.get(`${urlBase}?origem=${origemParam}&scale_mode=${scaleParam}&centro_custo=${ccParam}&ano=${anoParam}`);
            
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
            if (container) container.innerHTML = `<div class="p-4 text-center text-danger">Erro: ${error.message}</div>`;
        } finally {
            this.isLoading = false;
        }
    }

    updateOrigemBadge() {
        const badge = document.getElementById('dreOrigemBadge');
        if (badge) badge.textContent = `${this.rawData.length} registros`;
    }

    renderOrigemFilter() {
        const opcoes = ['FARMA', 'FARMADIST', 'INTEC'];
        return `
            <div class="origem-filter-group d-flex align-items-center gap-2">
                <div class="btn-group origem-toggle-group" role="group" aria-label="Filtro de Empresas">
                    ${opcoes.map(op => {
                        const isActive = this.dreState.selectedOrigins.includes(op);
                        const style = isActive ? 'background-color: var(--primary); color: white;' : 'background-color: var(--bg-secondary); color: var(--text-secondary);';
                        
                        return `
                        <button type="button" class="btn btn-sm ${isActive ? 'active' : ''}" 
                                style="${style} border: 1px solid var(--border-primary);"
                                onclick="relatorioSystem.dre.handleOrigemChange('${op}')">
                            ${this.getOrigemIcon(op)} ${op}
                        </button>
                        `;
                    }).join('')}
                </div>
                <span id="dreOrigemBadge" class="badge badge-secondary ms-2" title="Registros carregados">
                    ${this.rawData.length}
                </span>
            </div>`;
    }

    getOrigemIcon(origem) {
        const icons = { 'FARMA': '<i class="fas fa-pills"></i>', 'FARMADIST': '<i class="fas fa-truck"></i>', 'INTEC': '<i class="fas fa-network-wired"></i>' };
        return icons[origem] || '<i class="fas fa-building"></i>';
    }

    handleOrigemChange(empresaClicada) {
        if (this.isLoading) return;
        const currentSelection = this.dreState.selectedOrigins;
        let newSelection = [];
        if (currentSelection.includes(empresaClicada)) {
            newSelection = currentSelection.filter(e => e !== empresaClicada);
        } else {
            newSelection = [...currentSelection, empresaClicada];
        }
        this.dreState.selectedOrigins = newSelection;
        this.reloadDataAsync();
    }

    processTree() {
        const root = [];
        const map = {}; 
        const meses = this.dreState.columnsOrder;
        const labelMap = { 'Oper': 'CUSTOS', 'Adm':  'ADMINISTRATIVO', 'Coml': 'COMERCIAL' };

        const getOrCreateNode = (id, label, type, parentList) => {
            if (!map[id]) {
                const node = { 
                    id: id, label: label, type: type, children: [], values: {},
                    isVisible: true, isExpanded: this.dreState.expanded.has(id),
                    ordem: 999999, estiloCss: null 
                };
                meses.forEach(m => node.values[m] = 0);
                map[id] = node;
                parentList.push(node);
            }
            return map[id];
        };

        const sumValues = (node, row) => {
            meses.forEach(m => node.values[m] += (parseFloat(row[m]) || 0));
        };

        this.rawData.forEach((row, index) => {
            let rawOrdem = null;
            if (row.ordem_prioridade !== null && row.ordem_prioridade !== undefined) {
                rawOrdem = parseInt(row.ordem_prioridade);
            } else if (row.Ordem !== null && row.Ordem !== undefined) {
                rawOrdem = parseInt(row.Ordem);
            } else if (row.ordem !== null && row.ordem !== undefined) {
                rawOrdem = parseInt(row.ordem); 
            }

            const tipoId = `T_${row.Tipo_CC}`;
            const labelExibicao = labelMap[row.Tipo_CC] || row.Tipo_CC;
            
            const tipoNode = getOrCreateNode(tipoId, labelExibicao, 'root', root);
            if (row.Root_Virtual_Id) tipoNode.virtualId = row.Root_Virtual_Id;
            if (row.Estilo_CSS && !tipoNode.estiloCss) tipoNode.estiloCss = row.Estilo_CSS;
            
            if (rawOrdem !== null && rawOrdem > 0 && rawOrdem < 1000) {
                if (tipoNode.ordem === 999999 || rawOrdem < tipoNode.ordem) tipoNode.ordem = rawOrdem;
            }
            
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
                    
                    if (!isNaN(specificOrder) && specificOrder > 0) {
                        if (groupNode.ordem === 999999 || specificOrder < groupNode.ordem) groupNode.ordem = specificOrder;
                    }
                    sumValues(groupNode, row);
                    currentNode = groupNode;
                });
            }

            // ==========================================
            // NOVO PADRÃO: PASTA (TÍTULO) -> ARQUIVO (NÚMERO DA CONTA)
            // ==========================================
            
            // 1. Cria (ou pega) a PASTA com o nome da conta (ex: "📁 SALARIOS")
            const safeTitleName = String(row.Titulo_Conta || '').replace(/[^a-zA-Z0-9]/g, '');
            const tituloId = `TIT_${safeTitleName}_${currentId}`;
            
            // Usa 'group' para a linha ganhar o ícone de pasta e a setinha de expandir/recolher
            const tituloNode = getOrCreateNode(tituloId, row.Titulo_Conta, 'account-group', currentNode.children);
            
            let ordemContaLeaf = 999999;
            if (row.Ordem_Conta !== undefined && row.Ordem_Conta !== null) {
                ordemContaLeaf = parseInt(row.Ordem_Conta, 10);
            } else if (row.Conta && !isNaN(parseInt(row.Conta))) {
                ordemContaLeaf = parseInt(row.Conta, 10); 
            }

            // Atualiza a ordem da pasta para ser a menor ordem das contas dentro dela
            if (ordemContaLeaf < tituloNode.ordem) {
                tituloNode.ordem = ordemContaLeaf;
            }
            
            // Soma os valores do lançamento na pasta
            sumValues(tituloNode, row);

            // 2. Cria a CONTA ESPECÍFICA dentro da pasta (ex: "📄 31101")
            const contaId = `C_${row.Conta}_${tituloId}`; 
            let contaNode = tituloNode.children.find(c => c.id === contaId);

            if (!contaNode) {
                contaNode = {
                    id: contaId,
                    label: `${row.Conta}`, // Mostra apenas o número, pois o nome já está na pasta pai!
                    rawTitle: row.Titulo_Conta,
                    contaCodigo: row.Conta,   
                    tipoCC: row.Tipo_CC,      
                    type: 'account', children: [], values: {}, isVisible: true, ordem: ordemContaLeaf
                };
                
                meses.forEach(m => contaNode.values[m] = 0);
                tituloNode.children.push(contaNode);
            }

            // Acumula os valores na conta específica
            meses.forEach(m => {
                contaNode.values[m] += (parseFloat(row[m]) || 0);
            });
            // ==========================================
        });

        this.treeData = root;
        this.applyFilters();
    }

    async processTreeWithCalculated() {
        this.processTree();
        const nosCalc = await this.loadNosCalculados(); 

        if (nosCalc.length > 0) {
            const valoresAgregados = this.agregarValoresPorTipo();
            const meses = this.dreState.columnsOrder;
            
            nosCalc.forEach(noCalc => {
                if (!noCalc.formula) return;
                
                let contextoSuffix = null;
                const nomeUpper = (noCalc.nome || '').toUpperCase();
                if (nomeUpper.includes('CUSTO') || nomeUpper.includes('OPERACIONAL')) contextoSuffix = 'Oper';
                else if (nomeUpper.includes('ADMINISTRATIVO')) contextoSuffix = 'Adm';
                else if (nomeUpper.includes('COMERCIAL') || nomeUpper.includes('VENDAS')) contextoSuffix = 'Coml';

                const valores = {};
                meses.forEach(mes => {
                    valores[mes] = this.calcularValorNo(noCalc.formula, mes, valoresAgregados, contextoSuffix);
                });

                const chaveMemoria = `no_virtual_${noCalc.id}`;
                if (!valoresAgregados[chaveMemoria]) valoresAgregados[chaveMemoria] = {};
                meses.forEach(mes => valoresAgregados[chaveMemoria][mes] = valores[mes]);

                let textoTooltip = noCalc.formula_descricao;
                if (!textoTooltip && noCalc.formula) {
                    const ops = noCalc.formula.operandos || [];
                    const nomesOps = ops.map(o => o.label || o.id).join(', ');
                    textoTooltip = `Fórmula Calculada: ${nomesOps}`;
                }

                const rowBackend = this.rawData.find(r => 
                    (String(r.Root_Virtual_Id) === String(noCalc.id)) || 
                    (r.Titulo_Conta === noCalc.nome && r.Is_Calculado)
                );

                let ordemCorreta = 50;
                if (rowBackend && rowBackend.ordem_prioridade !== null) ordemCorreta = rowBackend.ordem_prioridade;
                else if (noCalc.ordem !== null && noCalc.ordem !== undefined) ordemCorreta = noCalc.ordem;
                
                let cssFinal = noCalc.estilo_css; 
                if (!cssFinal && rowBackend && rowBackend.Estilo_CSS) cssFinal = rowBackend.Estilo_CSS; 

                const nodeCalc = {
                    id: `calc_${noCalc.id}`,
                    label: `${noCalc.nome}`, 
                    rawLabel: noCalc.nome,     
                    type: 'calculated', children: [], values: valores, isVisible: true, isExpanded: false,
                    formulaDescricao: textoTooltip, estiloCss: cssFinal, tipoExibicao: noCalc.tipo_exibicao, ordem: ordemCorreta
                };
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
            nodes.forEach(node => {
                if (node.children && node.children.length > 0) sortRecursive(node.children);
            });
        };

        sortRecursive(this.treeData);
    }

    renderTable() {
        const container = document.getElementById('dreGridContainer');
        if (!container) return;

        const cols = this.dreState.columnsOrder.filter(c => !this.dreState.hiddenCols.has(c));
        const rootHeaderName = this.dreState.viewMode === 'CC' ? 'Estrutura / Centro de Custo' : 'Estrutura DRE';

        let headerHtml = `
            <thead style="position: sticky; top: 0; z-index: 20;">
                <tr>
                    <th style="min-width: 350px; left: 0; position: sticky; z-index: 30;">
                        ${rootHeaderName}
                    </th>
                    ${cols.map(c => `
                        <th class="text-end" style="min-width: 110px;">
                            <div class="d-flex flex-column">
                                <span class="mb-1 cursor-pointer text-xs font-bold" onclick="relatorioSystem.dre.sortBy('${c}')">${c}</span>
                            </div>
                        </th>
                    `).join('')}
                </tr>
            </thead>`;

        let bodyRows = '';
        const COLOR_DARK = 'color: var(--icon-structure);'; 
        const COLOR_GRAY = 'color: var(--icon-secondary);'; 
        const COLOR_FOLDER = 'color: var(--icon-folder);'; 
        const COLOR_LIGHT = 'color: var(--icon-account);';
        const showAccounts = this.dreState.showAccounts;

        const renderNode = (node, level) => {
            if (node.type === 'account' && !showAccounts) return;
            if (!node.isVisible) return;
            const padding = level * 20 + 10;
            const isGroup = node.children && node.children.length > 0 && 
                            (showAccounts || node.children.some(child => child.type !== 'account'));

            const isExpanded = this.dreState.expanded.has(node.id);             
            
            let iconClass = '';
            let iconStyle = '';

            if (node.type === 'calculated') { iconClass = 'fa-calculator'; iconStyle = COLOR_DARK; } 
            else if (node.type === 'root') {
                if (node.virtualId) { iconClass = 'fa-cube'; iconStyle = COLOR_DARK; } 
                else {
                    iconClass = 'fa-layer-group'; iconStyle = COLOR_DARK;
                    if (node.ordem < 1000 && !node.virtualId) { iconClass = 'fa-globe'; iconStyle = COLOR_GRAY; }
                }
            }
            else if (node.type === 'group') { iconClass = 'fa-folder'; iconStyle = COLOR_FOLDER; }
            
            // --- ADICIONE ESTA LINHA AQUI ---
            else if (node.type === 'account-group') { iconClass = 'fa-file-alt'; iconStyle = COLOR_LIGHT; }
            
            else if (node.type === 'account') { iconClass = 'fa-file-alt'; iconStyle = COLOR_LIGHT; }

            let iconHtml = '';
            if (isGroup) {
                iconHtml = `<i class="fas fa-caret-${isExpanded ? 'down' : 'right'} me-2 toggle-icon" onclick="event.stopPropagation(); relatorioSystem.dre.toggleNode('${node.id}')" style="width:10px; cursor: pointer; color: var(--text-tertiary);"></i>`;
                iconHtml += `<i class="fas ${iconClass} me-2" style="${iconStyle}"></i>`;
            } else {
                iconHtml = `<i class="fas ${iconClass} me-2" style="margin-left: 18px; ${iconStyle}"></i>`;
            }

            const cssString = node.estiloCss || '';
            const trStyle = cssString ? `style="${cssString}"` : '';
            
            const cellsHtml = cols.map(c => {
                const val = node.values[c];
                let colorClass = '';
                if (val < 0) colorClass = 'text-danger'; 
                else if (val === 0) colorClass = 'text-muted';
                
                let displayVal = '-';
                if (val !== 0) {
                    if (this.dreState.scaleMode === 'dre') displayVal = this.formatValue(val);
                    else displayVal = FormatUtils.formatNumber(val);
                }
                if (node.tipoExibicao === 'percentual' && val !== 0) displayVal = val.toFixed(2) + '%';
                const weight = (node.type === 'root' || node.type === 'calculated') ? 'font-weight: 600;' : '';
                return `<td class="text-end font-mono ${colorClass}" style="${weight} ${cssString}">${displayVal}</td>`;
            }).join('');

            const isMatch = this.dreState.searchMatches.includes(node.id);
            const searchClass = isMatch ? 'search-match' : '';

            bodyRows += `<tr id="row_${node.id}" class="dre-row-${node.type} ${searchClass}" ${trStyle}>
                    <td style="padding-left: ${padding}px; ${cssString}"> 
                        <div class="d-flex align-items-center cell-label">
                            ${iconHtml}<span class="text-truncate" title="${node.formulaDescricao || ''}">${node.label}</span>
                        </div>
                    </td>${cellsHtml}</tr>`;

            if (isGroup && isExpanded) node.children.forEach(child => renderNode(child, level + 1));
        };

        this.treeData.forEach(node => renderNode(node, 0));
        container.innerHTML = `<table class="table-modern w-100" style="border-collapse: separate; border-spacing: 0;">${headerHtml}<tbody>${bodyRows}</tbody></table>`;
    }
    
    async loadCCList() {
        if (this.dreState.listaCCs.length > 0) return; 
        try {
            const url = (typeof API_ROUTES !== 'undefined' && API_ROUTES.getListaCCs) ? API_ROUTES.getListaCCs : '/Reports/RelatorioRazao/ListaCentrosCusto';
            const lista = await APIUtils.get(url);
            if(lista && Array.isArray(lista)) this.dreState.listaCCs = lista;
        } catch (e) { console.error("Erro ao carregar lista de CCs:", e); }
    }

    handleCCChange(selectElement) {
        if (this.isLoading) return;
        const selectedOptions = Array.from(selectElement.selectedOptions).map(option => option.value);
        let newSelectedCCs = [];

        if (selectedOptions.includes('Todos')) newSelectedCCs = ['Todos'];
        else if (selectedOptions.length === 0) newSelectedCCs = ['Todos']; 
        else newSelectedCCs = selectedOptions.filter(v => v !== 'Todos');

        this.dreState.selectedCCs = newSelectedCCs;
        this.dreState.ccFilter = newSelectedCCs.join(',');
        this.loadReport();
    }

    openCCFilterDropdown(buttonElement) {
        if (this.isLoading) return;
        const dropdownId = 'cc-filter-dropdown';
        let dropdown = document.getElementById(dropdownId);
        
        if (dropdown) { dropdown.remove(); return; }

        dropdown = document.createElement('div');
        dropdown.id = dropdownId;
        dropdown.className = 'custom-dropdown-menu';
        
        const searchHtml = `
            <div class="dropdown-search-box">
                <i class="fas fa-search"></i>
                <input type="text" placeholder="Pesquisar Centro..." id="ccSearchInput" oninput="relatorioSystem.dre.filterCCList(this.value)">
            </div>`;
        
        const optionsHtml = this.dreState.listaCCs.map(cc => {
            const isSelected = this.dreState.selectedCCs.includes(String(cc.codigo));
            return `
                <label class="dropdown-option-label" data-name="${cc.nome.toLowerCase()}" data-code="${cc.codigo}">
                    <input type="checkbox" value="${cc.codigo}" ${isSelected ? 'checked' : ''} onchange="relatorioSystem.dre.handleCCCheckboxChange(this)">
                    <span>${cc.nome}</span>
                </label>`;
        }).join('');
        
        const isAllSelected = this.dreState.selectedCCs.includes('Todos') || this.dreState.selectedCCs.length === 0;
        const allOptionHtml = `
            <div class="dropdown-all-option">
                <label class="dropdown-option-label dropdown-select-all">
                    <input type="checkbox" value="Todos" id="chkSelectAllCC" ${isAllSelected ? 'checked' : ''} onchange="relatorioSystem.dre.handleSelectAllCC(this.checked)">
                    <span>[ Selecionar Tudo ]</span>
                </label>
            </div>`;

        dropdown.innerHTML = searchHtml + `<div class="dropdown-options-container">${allOptionHtml}${optionsHtml}</div>`;
        
        const rect = buttonElement.getBoundingClientRect();
        dropdown.style.top = `${rect.bottom + 5}px`;
        dropdown.style.right = `${window.innerWidth - rect.right}px`; 

        document.body.appendChild(dropdown);

        const closeOnOutsideClick = (event) => {
            if (dropdown && !dropdown.contains(event.target) && !buttonElement.contains(event.target)) {
                dropdown.remove();
                document.removeEventListener('click', closeOnOutsideClick);
            }
        };
        setTimeout(() => { document.addEventListener('click', closeOnOutsideClick); }, 100);
    }

    handleCCCheckboxChange(checkbox) {
        const code = checkbox.value;
        let currentCCs = this.dreState.selectedCCs.filter(v => v !== 'Todos');

        if (checkbox.checked) {
            if (!currentCCs.includes(code)) currentCCs.push(code);
        } else {
            currentCCs = currentCCs.filter(v => v !== code);
        }

        if (currentCCs.length === 0) {
             this.dreState.selectedCCs = ['Todos'];
             document.getElementById('chkSelectAllCC').checked = true;
        } else {
             this.dreState.selectedCCs = currentCCs;
             document.getElementById('chkSelectAllCC').checked = false;
        }
        
        this.updateCCButtonDisplay();
        clearTimeout(this.debounceTimer); 
        this.debounceTimer = setTimeout(() => { this.loadReport(); }, 800);
    }
    
    handleSelectAllCC(isChecked) {
         const checkboxes = document.querySelectorAll('.dropdown-options-container input[type="checkbox"]');
         if (isChecked) {
            checkboxes.forEach(chk => chk.checked = true);
            this.dreState.selectedCCs = ['Todos'];
         } else {
            checkboxes.forEach(chk => chk.checked = false);
            this.dreState.selectedCCs = []; 
         }
         this.updateCCButtonDisplay();
         clearTimeout(this.debounceTimer); 
         this.debounceTimer = setTimeout(() => { this.loadReport(); }, 800);
    }

    filterCCList(searchTerm) {
        const term = searchTerm.toLowerCase();
        const labels = document.querySelectorAll('.dropdown-options-container .dropdown-option-label');
        labels.forEach(label => {
            const name = label.getAttribute('data-name');
            const code = label.getAttribute('data-code');
            const match = name.includes(term) || code.includes(term);
            label.style.display = match ? 'flex' : 'none';
        });
    }
    
    updateCCButtonDisplay() {
        const displaySpan = document.getElementById('ccFilterDisplay');
        if (!displaySpan) return;
        
        let text;
        const button = document.getElementById('ccFilterButton');
        
        if (this.dreState.selectedCCs.includes('Todos')) {
            text = 'Todos os Centros';
            if(button) button.classList.remove('active-filter');
        } else {
            const count = this.dreState.selectedCCs.length;
            text = `${count} Centro(s) Selecionado(s)`;
            if(button) button.classList.add('active-filter'); 
        }
        displaySpan.textContent = text;
    }

    async loadReport(origemIgnorada = null) {
        if (!this.modal) this.modal = new ModalSystem('modalRelatorio');
        await this.loadCCList();

        const scaleTitle = this.dreState.scaleMode === 'dre' ? '(Em Milhares)' : '(Valor Integral)';
        const totalSelecionados = this.dreState.selectedCCs.length;
        let ccTitle = this.dreState.selectedCCs.includes('Todos') ? 'Todos os Centros' : `Filtro: ${totalSelecionados} CC(s) selecionados`;
        
        this.modal.open(`<i class="fas fa-cubes"></i> Análise Gerencial DRE <small class="modal-title">${scaleTitle} | ${ccTitle}</small>`, '');
        this.modal.showLoading('Calculando DRE...');

        try {
            const urlBase = (typeof API_ROUTES !== 'undefined' && API_ROUTES.getRentabilidadeData) ? API_ROUTES.getRentabilidadeData : '/Reports/RelatorioRazao/Rentabilidade';
            const origemParam = encodeURIComponent(this.dreState.selectedOrigins.join(','));
            const ccParam = encodeURIComponent(this.dreState.selectedCCs.join(','));
            const scaleParam = this.dreState.scaleMode; 
            const anoParam = this.dreState.selectedYear;

            const data = await APIUtils.get(`${urlBase}?origem=${origemParam}&scale_mode=${scaleParam}&centro_custo=${ccParam}&ano=${anoParam}`);
            if (!data || data.length === 0) {
                this.rawData = [];
                this.treeData = [];
                this.renderInterface();
                setTimeout(() => {
                    const container = document.getElementById('dreGridContainer');
                    if(container) {
                        container.innerHTML = `
                            <div class="p-5 text-center">
                                <i class="fas fa-filter fa-3x text-muted mb-3"></i>
                                <h4 class="text-secondary">Sem dados</h4>
                                <p class="text-muted">Verifique a seleção de empresas e centros de custo.</p>
                            </div>`;
                    }
                }, 100);
                return;
            }

            this.rawData = data;
            await this.processTreeWithCalculated();
            this.renderInterface();

        } catch (error) {
            console.error(error);
            this.modal.showError(`Erro no DRE: ${error.message}`);
        }
    }
    
    renderInterface() {
        const isDreMode = this.dreState.scaleMode === 'dre';
        const btnScaleClass = isDreMode ? 'btn-info' : 'btn-secondary';
        const btnScaleIcon = isDreMode ? 'fa-divide' : 'fa-dollar-sign';
        const btnScaleText = isDreMode ? 'Escala: Milhares (DRE)' : 'Escala: Reais';
        
        const showAccounts = this.dreState.showAccounts;
        const btnAccountClass = showAccounts ? 'btn-success' : 'btn-outline-secondary';
        const btnAccountIcon = showAccounts ? 'fa-eye' : 'fa-eye-slash';
        const btnAccountText = showAccounts ? 'Contas: Visíveis' : 'Contas: Ocultas';

        let nomeCCSelecionado = this.dreState.selectedCCs.includes('Todos') ? 'Todos' : `${this.dreState.selectedCCs.length} selecionados`;

        const toolbar = `
            <div class="dre-toolbar d-flex justify-content-between align-items-center p-3 border-bottom border-primary bg-tertiary">
                <div class="d-flex gap-2 align-items-center flex-wrap">
                    ${this.renderOrigemFilter()}
                    
                    <button id="ccFilterButton" class="btn-selector-clean" 
                            onclick="relatorioSystem.dre.openCCFilterDropdown(this)"
                            title="Filtrar por Centro de Custo">
                        <i class="fas fa-building text-muted me-2"></i>
                        <span id="ccFilterDisplay" class="selector-label">Todos os Centros</span>
                        <i class="fas fa-chevron-down ms-3 text-xs text-muted"></i>
                    </button>
                    <select class="form-select form-select-sm" style="width: auto; font-weight: 600; color: var(--primary);" 
                        onchange="relatorioSystem.dre.handleYearChange(this.value)">
                        <option value="2024" ${this.dreState.selectedYear == 2024 ? 'selected' : ''}>2024</option>
                        <option value="2025" ${this.dreState.selectedYear == 2025 ? 'selected' : ''}>2025</option>
                        <option value="2026" ${this.dreState.selectedYear == 2026 ? 'selected' : ''}>2026</option>
                    </select>
                    <div class="separator-vertical mx-2" style="height: 20px; border-left: 1px solid var(--border-secondary);"></div>

                    <button class="btn btn-sm ${btnScaleClass}" onclick="relatorioSystem.dre.toggleScaleMode()" title="Alternar Escala de Valores">
                        <i class="fas ${btnScaleIcon}"></i> ${btnScaleText}
                    </button>
                    
                    <button class="btn btn-sm ${btnAccountClass}" onclick="relatorioSystem.dre.toggleAccountVisibility()" title="Alternar Visibilidade das Contas">
                        <i class="fas ${btnAccountIcon}"></i> ${btnAccountText}
                    </button>

                    <div class="separator-vertical mx-2" style="height: 20px; border-left: 1px solid var(--border-secondary);"></div>
                    
                    <div class="input-group input-group-sm" style="width: 200px;">
                        <i class="input-group-icon fas fa-search"></i>
                        <input type="text" id="dreGlobalSearch" class="form-control" 
                            placeholder="Buscar na árvore..." value="${this.dreState.globalSearch}"
                            oninput="relatorioSystem.dre.handleGlobalSearch(this.value)"
                            onkeydown="if(event.key === 'Enter') { event.preventDefault(); relatorioSystem.dre.navigateSearchNext(); }">
                    </div>
                </div>
                <div class="d-flex gap-2 align-items-center">
                    <button class="btn btn-sm btn-outline" onclick="relatorioSystem.dre.toggleAllNodes(true)" title="Expandir Tudo"><i class="fas fa-expand-arrows-alt"></i></button>
                    <button class="btn btn-sm btn-outline" onclick="relatorioSystem.dre.toggleAllNodes(false)" title="Recolher Tudo"><i class="fas fa-compress-arrows-alt"></i></button>
                    <button class="btn btn-sm btn-outline" onclick="relatorioSystem.dre.openColumnManager()" title="Colunas"><i class="fas fa-columns"></i></button>
                </div>
            </div>`;
        
        const gridContainer = `<div id="dreGridContainer" class="table-fixed-container" style="flex: 1; overflow: auto; background: var(--bg-secondary);"></div>`;
        
        const footer = `
            <div class="dre-footer p-2 bg-tertiary border-top border-primary d-flex justify-content-between align-items-center">
                <span class="text-secondary text-xs">
                    Empresas: <strong>${this.dreState.selectedOrigins.join(', ')}</strong> | 
                    Filtro CC: <strong class="text-info">${nomeCCSelecionado}</strong> | 
                    Escala: <strong>${this.dreState.scaleMode.toUpperCase()}</strong>
                </span>
                <span class="text-muted text-xs">Atualizado: ${new Date().toLocaleTimeString('pt-BR')}</span>
            </div>`;

        this.modal.setContent(`<div style="display: flex; flex-direction: column; height: 100%;">${toolbar}${gridContainer}${footer}</div>`);
        
        this.updateCCButtonDisplay();
        this.renderTable();
    }

    applyFilters() {
        const colFilters = this.dreState.filters;
        const hasColFilters = Object.keys(colFilters).length > 0;

        const checkVisibility = (node) => {
            let matchesCols = true;
            if (hasColFilters) {
                for (const [col, filterVal] of Object.entries(colFilters)) {
                    if (!filterVal) continue;
                    const nodeVal = node.values[col];
                    let pass = false;
                    const cleanFilter = filterVal.replace(',', '.').trim();
                    if (cleanFilter.startsWith('>')) pass = nodeVal > parseFloat(cleanFilter.substring(1));
                    else if (cleanFilter.startsWith('<')) pass = nodeVal < parseFloat(cleanFilter.substring(1));
                    else pass = nodeVal.toString().includes(cleanFilter); 
                    if (!pass) { matchesCols = false; break; }
                }
            }
            let hasVisibleChildren = false;
            if (node.children) node.children.forEach(child => { if (checkVisibility(child)) hasVisibleChildren = true; });
            
            const isVisible = matchesCols || hasVisibleChildren;
            node.isVisible = isVisible;
            if (isVisible && hasColFilters) this.dreState.expanded.add(node.id); 
            return isVisible;
        };
        this.treeData.forEach(node => checkVisibility(node));
    }

    handleGlobalSearch(val) { 
        this.dreState.globalSearch = val; 
        if (!val) {
            this.dreState.searchMatches = [];
            this.dreState.searchCurrentIndex = -1;
            this.renderTable();
            return;
        }
        clearTimeout(this.debounceTimer); 
        this.debounceTimer = setTimeout(() => { this.performSearchTraversal(); }, 400); 
    }

    performSearchTraversal() {
        const term = this.dreState.globalSearch.toLowerCase();
        this.dreState.searchMatches = [];
        this.dreState.searchCurrentIndex = -1;
        if (!term) return;

        const findAndExpand = (nodes, parentIds = []) => {
            nodes.forEach(node => {
                const match = node.label.toLowerCase().includes(term);
                if (match) {
                    this.dreState.searchMatches.push(node.id);
                    parentIds.forEach(pid => this.dreState.expanded.add(pid));
                }
                if (node.children && node.children.length > 0) findAndExpand(node.children, [...parentIds, node.id]);
            });
        };
        findAndExpand(this.treeData);
        if (this.dreState.searchMatches.length > 0) {
            this.renderTable();
            setTimeout(() => this.navigateSearchNext(), 100);
        } else {
            this.renderTable();
        }
    }

    navigateSearchNext() {
        if (this.dreState.searchMatches.length === 0) return;
        this.dreState.searchCurrentIndex++;
        if (this.dreState.searchCurrentIndex >= this.dreState.searchMatches.length) {
            this.dreState.searchCurrentIndex = 0;
        }
        const nodeId = this.dreState.searchMatches[this.dreState.searchCurrentIndex];
        this.scrollToNode(nodeId);
        this.updateSearchHighlights();
    }

    scrollToNode(nodeId) {
        const row = document.getElementById(`row_${nodeId}`);
        if (row) row.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    updateSearchHighlights() {
        document.querySelectorAll('.search-current-match').forEach(el => el.classList.remove('search-current-match'));
        const currentId = this.dreState.searchMatches[this.dreState.searchCurrentIndex];
        const row = document.getElementById(`row_${currentId}`);
        if (row) row.classList.add('search-current-match');
    }

    handleColFilter(col, val) { if (!val) delete this.dreState.filters[col]; else this.dreState.filters[col] = val; this.debounceRender(); }
    debounceRender() { clearTimeout(this.debounceTimer); this.debounceTimer = setTimeout(() => { this.applyFilters(); this.renderTable(); }, 400); }
    toggleNode(id) { if (this.dreState.expanded.has(id)) this.dreState.expanded.delete(id); else this.dreState.expanded.add(id); this.renderTable(); }
    toggleAllNodes(expand) { const recurse = (nodes) => { nodes.forEach(n => { if (expand) this.dreState.expanded.add(n.id); else this.dreState.expanded.delete(n.id); if (n.children) recurse(n.children); }); }; recurse(this.treeData); this.renderTable(); }
    openColumnManager() {
        const allCols = this.dreState.columnsOrder;
        const allVisible = allCols.every(c => !this.dreState.hiddenCols.has(c));
        const modalHtml = `
            <div class="column-manager-container">
                <div class="column-manager-header">
                    <h5 class="m-0"><i class="fas fa-columns text-primary"></i> Gerenciar Colunas</h5>
                    <button class="btn btn-sm btn-outline" onclick="relatorioSystem.dre.toggleAllColumns(this)">
                        <i class="fas ${allVisible ? 'fa-check-square' : 'fa-square'}"></i> ${allVisible ? 'Desmarcar Todos' : 'Selecionar Todos'}
                    </button>
                </div>
                <div class="column-grid">
                    ${allCols.map(c => {
                        const isVisible = !this.dreState.hiddenCols.has(c);
                        return `
                        <label class="column-option ${isVisible ? 'selected' : ''}">
                            <input type="checkbox" class="column-checkbox" value="${c}" ${isVisible ? 'checked' : ''} onchange="relatorioSystem.dre.handleColumnToggle(this, '${c}')">
                            <span>${c}</span>
                        </label>`;
                    }).join('')}
                </div>
                <div class="mt-4 text-end border-top border-primary pt-3">
                    <button class="btn btn-primary-custom" style="width: auto; padding: 8px 24px;" onclick="document.querySelector('.modal-backdrop.col-mgr').remove(); relatorioSystem.dre.renderTable()">
                        <i class="fas fa-check"></i> Aplicar Alterações
                    </button>
                </div>
            </div>`;
        const colModal = document.createElement('div'); 
        colModal.className = 'modal-backdrop col-mgr active'; 
        colModal.innerHTML = `<div class="modal-window" style="max-width: 600px;">${modalHtml}</div>`;
        colModal.onclick = (e) => { if(e.target === colModal) { colModal.remove(); this.renderTable(); } }; 
        document.body.appendChild(colModal);
    }

    handleColumnToggle(checkbox, col) {
        if (checkbox.checked) { this.dreState.hiddenCols.delete(col); checkbox.closest('.column-option').classList.add('selected'); }
        else { this.dreState.hiddenCols.add(col); checkbox.closest('.column-option').classList.remove('selected'); }
        this.updateSelectAllBtnState();
    }

    toggleAllColumns(btn) {
        const checkboxes = document.querySelectorAll('.column-grid input[type="checkbox"]');
        const isCurrentlyAllChecked = btn.querySelector('i').classList.contains('fa-check-square');
        const newState = !isCurrentlyAllChecked;
        checkboxes.forEach(chk => {
            chk.checked = newState;
            const col = chk.value;
            const parent = chk.closest('.column-option');
            if (newState) { this.dreState.hiddenCols.delete(col); parent.classList.add('selected'); } 
            else { this.dreState.hiddenCols.add(col); parent.classList.remove('selected'); }
        });
        this.updateSelectAllBtnState();
    }

    updateSelectAllBtnState() {
        const btn = document.querySelector('.column-manager-header button');
        if(!btn) return;
        const allCols = this.dreState.columnsOrder;
        const allVisible = allCols.every(c => !this.dreState.hiddenCols.has(c));
        if(allVisible) btn.innerHTML = '<i class="fas fa-check-square"></i> Desmarcar Todos';
        else btn.innerHTML = '<i class="fas fa-square"></i> Selecionar Todos';
    }

    toggleColumn(col) { if (this.dreState.hiddenCols.has(col)) this.dreState.hiddenCols.delete(col); else this.dreState.hiddenCols.add(col); }
    sortBy(col) { 
        if (this.dreState.sort.col === col) this.dreState.sort.dir = this.dreState.sort.dir === 'asc' ? 'desc' : 'asc';
        else { this.dreState.sort.col = col; this.dreState.sort.dir = 'desc'; }
        const sortNodes = (nodes) => {
            nodes.sort((a, b) => { const valA = a.values[col] || 0; const valB = b.values[col] || 0; return this.dreState.sort.dir === 'asc' ? valA - valB : valB - valA; });
            nodes.forEach(n => { if (n.children) sortNodes(n.children); });
        };
        sortNodes(this.treeData); this.renderTable();
    }
    exportToCsv() { 
        let csv = "data:text/csv;charset=utf-8,";
        const visibleCols = this.dreState.columnsOrder.filter(c => !this.dreState.hiddenCols.has(c));
        csv += `# Relatório DRE - ${this.dreState.origemFilter} - ${this.dreState.viewMode}\r\nEstrutura;${visibleCols.join(";")}\r\n`;
        const processRow = (node, prefix = "") => {
            if (!node.isVisible) return;
            csv += `"${prefix}${node.label}";` + visibleCols.map(c => (node.values[c]||0).toFixed(2).replace('.',',')).join(";") + "\r\n";
            if(node.children) node.children.forEach(child => processRow(child, prefix + "  "));
        };
        this.treeData.forEach(n => processRow(n));
        const link = document.createElement("a"); link.href = encodeURI(csv); link.download = "relatorio_dre.csv"; document.body.appendChild(link); link.click(); link.remove();
    }
    
    async loadNosCalculados() { try { const r = await APIUtils.get((API_ROUTES?.getNosCalculados) || '/Configuracao/GetNosCalculados'); this.nosCalculados = r || []; return this.nosCalculados; } catch { return []; } }
    
    calcularValorNo(formula, mes, valoresAgregados, contextoSuffix = null) {
        if (!formula || !formula.operandos) return 0;
        const valores = formula.operandos.map(op => {
            const idOp = String(op.id).trim();
            const tipoOp = op.tipo;
            if (tipoOp === 'conta' && contextoSuffix) {
                const chaveEspecifica = `conta_${idOp}${contextoSuffix}`;
                if (valoresAgregados[chaveEspecifica] && valoresAgregados[chaveEspecifica][mes] !== undefined) return valoresAgregados[chaveEspecifica][mes];
            }
            return valoresAgregados[`${tipoOp}_${idOp}`]?.[mes] || 0;
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
        const agregados = {};
        const meses = this.dreState.columnsOrder;

        const initKey = (key) => {
            if (!agregados[key]) {
                agregados[key] = {};
                meses.forEach(m => agregados[key][m] = 0);
            }
        };

        const traverse = (node) => {
            if (node.type === 'root') {
                const rawId = node.id.replace('T_', '').replace('CC_', '');
                const keyTipo = `tipo_cc_${rawId}`;
                initKey(keyTipo);
                meses.forEach(m => agregados[keyTipo][m] += (node.values[m] || 0));
            }

            if (node.virtualId) {
                const keyVirt = `no_virtual_${node.virtualId}`;
                initKey(keyVirt);
                meses.forEach(m => agregados[keyVirt][m] += (node.values[m] || 0));
            }

            if (node.type === 'group') {
                const keySub = `subgrupo_${node.label}`;
                initKey(keySub);
                meses.forEach(m => agregados[keySub][m] += (node.values[m] || 0));
            }
            
            if (node.type === 'account' && node.contaCodigo) {
                const keyPura = `conta_${node.contaCodigo}`;
                initKey(keyPura);
                meses.forEach(m => agregados[keyPura][m] += (node.values[m] || 0));

                if (node.tipoCC) {
                    const tipoClean = node.tipoCC.trim();
                    if (['Coml', 'Oper', 'Adm'].includes(tipoClean)) {
                        const keyComposta = `conta_${node.contaCodigo}${tipoClean}`;
                        initKey(keyComposta);
                        meses.forEach(m => agregados[keyComposta][m] += (node.values[m] || 0));
                    }
                }
            }

            if (node.children && node.children.length > 0) node.children.forEach(child => traverse(child));
        };

        this.treeData.forEach(rootNode => traverse(rootNode));
        return agregados;
    }
}