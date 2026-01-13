// ============================================================================
// T-Controllership - SISTEMA DE RELATÓRIOS FINANCEIROS & BI NATIVO
// Arquivo: Static/JS/Relatorios.js
// ============================================================================

if (typeof window.relatorioSystemInitialized === 'undefined') {
    window.relatorioSystemInitialized = true;

    class RelatorioSystem {
        constructor() {
            this.modal = null;
            
            // Estado do Razão
            this.razaoData = null;
            this.razaoSummary = null; 
            this.razaoPage = 1;
            this.razaoTotalPages = 1;
            this.razaoSearch = '';
            this.razaoSearchTimer = null;
            this.razaoViewType = 'original'; 

            // Estado do BI (DRE)
            this.biRawData = [];      
            this.biTreeData = [];     
            this.biState = {
                    expanded: new Set(['root']), 
                    hiddenCols: new Set(),       
                    filters: {},                 
                    globalSearch: '',
                    searchMatches: [],      
                    searchCurrentIndex: -1,             
                    sort: { col: null, dir: 'asc' }, 
                    columnsOrder: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez', 'Total_Ano'],            
                    
                    // --- ALTERADO: SUPORTE A MULTI-SELEÇÃO INTEC/FARMA/DIST ---
                    selectedOrigins: ['FARMA', 'FARMADIST', 'INTEC'], // Padrão: Tudo selecionado
                    
                    viewMode: 'TIPO',
                    scaleMode: 'dre',
                    
                    // --- ALTERADO: Agora é um array de códigos de CC selecionados ---
                    selectedCCs: ['Todos'], // Padrão
                    ccFilter: 'Todos',      // Mantido como fallback, mas usaremos selectedCCs
                    listaCCs: [], 
                    showAccounts: true,
                };
            this.biDebounceTimer = null;
            this.biIsLoading = false;        
            this.nosCalculados = [];

            this.init();
        }
        init() {
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => this.setupSystem());
            } else {
                this.setupSystem();
            }
        }

        toggleAccountVisibility() {
            if (this.biIsLoading) return;
            this.biState.showAccounts = !this.biState.showAccounts;
            
            // Re-renderiza a interface (para atualizar o botão) e a tabela
            this.renderBiInterface();
            this.renderBiTable();
        }
        
        setupSystem() {
            const modalElement = document.getElementById('modalRelatorio');
            if (modalElement) {
                this.modal = new ModalSystem('modalRelatorio');
            }
        }

        // ====================================================================
        // --- MÓDULO 1: RAZÃO CONTÁBIL ---
        // ====================================================================

        async loadRazaoReport(page = 1) {
            if (!this.modal) this.modal = new ModalSystem('modalRelatorio');         
            this.razaoPage = page;
            
            const titleSuffix = this.razaoViewType === 'adjusted' ? '(VISÃO AJUSTADA)' : '(ORIGINAL)';
            const title = this.razaoSearch 
                ? `📈 Razão Contábil ${titleSuffix} - Buscando: "${this.razaoSearch}"` 
                : `📈 Relatório de Razão ${titleSuffix}`;

            if (page === 1 && !document.querySelector('#razaoTableContainer')) {
                this.modal.open(title);
                this.modal.showLoading('Carregando lançamentos contábeis...');
            }

            try {
                const urlData = (API_ROUTES?.getRazaoData) || '/Reports/RelatorioRazao/Dados'; 
                const urlSummary = (API_ROUTES?.getRazaoResumo) || '/Reports/RelatorioRazao/Resumo';

                const term = encodeURIComponent(this.razaoSearch);
                const viewType = this.razaoViewType;
                
                const [respData, respSummary] = await Promise.all([
                    APIUtils.get(`${urlData}?page=${page}&search=${term}&view_type=${viewType}`),
                    APIUtils.get(`${urlSummary}?view_type=${viewType}`)
                ]);

                this.razaoData = respData.dados || [];
                this.razaoTotalPages = respData.total_paginas || 1;
                this.razaoSummary = respSummary;

                this.renderRazaoView(respData, respSummary);
            } catch (error) {
                console.error(error);
                this.modal.showError(`Erro ao carregar Razão: ${error.message}`);
            }
        }

        // --- CORREÇÃO: ADICIONADA A FUNÇÃO QUE FALTAVA ---
        toggleRazaoView(isChecked) {
            // Atualiza o estado
            this.razaoViewType = isChecked ? 'adjusted' : 'original';
            // Recarrega o relatório na página 1
            this.loadRazaoReport(1);
        }

        renderRazaoView(metaData, summaryData) {
            // 1. Resumo HTML (Cards superiores)
            const summaryHtml = `
                <div class="summary-grid mb-3">
                    <div class="summary-card">
                        <div class="summary-label">Total Registros</div>
                        <div class="summary-value">${FormatUtils.formatNumber(summaryData.total_registros)}</div>
                    </div>
                </div>`;

            // 2. Barra de Controle
            const controlsHtml = `
                <div class="d-flex justify-content-between align-items-center mb-2 p-2 bg-tertiary rounded flex-wrap gap-2">
                    <div class="d-flex align-items-center gap-3" style="flex: 1;">
                        <div class="input-group" style="max-width: 300px;">
                            <i class="input-group-icon fas fa-search"></i>
                            <input type="text" id="razaoSearchInput" class="form-control" 
                                placeholder="Busca Global (Server-side)..." value="${this.razaoSearch}">
                        </div>
                        
                        <div class="form-check form-switch d-flex align-items-center gap-2 m-0 cursor-pointer">
                            <input class="form-check-input cursor-pointer" type="checkbox" role="switch" id="chkViewTypeRazao" 
                                ${this.razaoViewType === 'adjusted' ? 'checked' : ''}
                                onchange="relatorioSystem.toggleRazaoView(this.checked)">
                            <label class="form-check-label text-white cursor-pointer select-none" for="chkViewTypeRazao">
                                Modo Ajustado (Inclusões/Edições)
                            </label>
                        </div>
                    </div>

                    <div class="d-flex align-items-center gap-2">
                        <button class="btn btn-sm btn-success" onclick="relatorioSystem.downloadRazaoFull()" title="Excel">
                            <i class="fas fa-file-excel"></i> Exportar
                        </button>
                        <div class="separator-vertical mx-2"></div>
                        <small class="text-secondary me-2">Página ${this.razaoPage} de ${this.razaoTotalPages}</small>
                        <div class="btn-group">
                            <button class="btn btn-sm btn-secondary" onclick="relatorioSystem.loadRazaoReport(${this.razaoPage - 1})" ${this.razaoPage <= 1 ? 'disabled' : ''}><i class="fas fa-chevron-left"></i></button>
                            <button class="btn btn-sm btn-secondary" onclick="relatorioSystem.loadRazaoReport(${this.razaoPage + 1})" ${this.razaoPage >= this.razaoTotalPages ? 'disabled' : ''}><i class="fas fa-chevron-right"></i></button>
                        </div>
                    </div>
                </div>
                
                <div id="razaoTabulator" style="height: 60vh; width: 100%; border-radius: 8px; overflow: hidden;"></div>
                <div class="text-end mt-1"><small class="text-muted text-xs">* Filtros nas colunas aplicam-se à página atual.</small></div>
            `;

            // 3. Renderiza o Layout Básico
            this.modal.setContent(`<div style="padding: 1.5rem; height: 100%; display: flex; flex-direction: column;">${summaryHtml}${controlsHtml}</div>`);

            // 4. Configuração do Evento de Busca Global
            const input = document.getElementById('razaoSearchInput');
            if (input) {
                input.focus();
                // Coloca o cursor no final do texto
                const val = input.value;
                input.value = '';
                input.value = val;
                
                input.addEventListener('input', (e) => {
                    clearTimeout(this.razaoSearchTimer);
                    this.razaoSearchTimer = setTimeout(() => {
                        this.razaoSearch = e.target.value;
                        this.loadRazaoReport(1);
                    }, 600);
                });
            }

            // 5. Inicialização do Tabulator
            this.initTabulator();
        }

        initTabulator() {
            // Definição de Formatadores
            const moneyFormatter = (cell) => {
                const val = cell.getValue();
                const color = val < 0 ? "text-danger" : (val > 0 ? "text-success" : "text-muted");
                return `<span class="${color}">${FormatUtils.formatCurrency(val)}</span>`;
            };

            const origemFormatter = (cell) => {
                const val = cell.getValue();
                const row = cell.getRow().getData();
                if (row.is_ajustado) {
                    // Verifica se é Inclusão ou Edição para dar dica visual
                    const isNew = val.includes('(NOVO)');
                    const icon = isNew ? 'fa-plus' : 'fa-pen';
                    const colorClass = isNew ? 'badge-success' : 'badge-warning';
                    return `<span class="badge ${colorClass} text-xs"><i class="fas ${icon}"></i> ${val}</span>`;
                }
                return `<span class="badge badge-secondary text-xs">${val}</span>`;
            };

            // Instancia Tabulator
            this.table = new Tabulator("#razaoTabulator", {
                data: this.razaoData,
                layout: "fitColumns",
                height: "100%",
                placeholder: "Sem dados para exibir",
                movableColumns: true,
                columns: [
                    {title:"Origem", field:"origem", width: 140, formatter: origemFormatter, headerFilter:"input"},
                    {title:"Conta", field:"conta", width: 130, headerFilter:"input"},
                    {title:"Título", field:"titulo_conta", minWidth: 200, headerFilter:"input"},
                    {title:"Data", field:"data", width: 110, headerFilter:"input", formatter: (cell) => FormatUtils.formatDate(cell.getValue())},
                    {title:"Doc", field:"numero", width: 100, headerFilter:"input"},
                    {title:"Histórico", field:"descricao", minWidth: 250, headerFilter:"input"},
                    
                    // Colunas Novas
                    {title:"CC", field:"centro_custo", width: 100, headerFilter:"input"},
                    {title:"Filial", field:"filial", width: 80, headerFilter:"input"},
                    {title:"Item", field:"item", width: 80, headerFilter:"input"},

                    // Valores
                    {title:"Débito", field:"debito", width: 120, hozAlign:"right", formatter: moneyFormatter, bottomCalc:"sum", bottomCalcFormatter: moneyFormatter},
                    {title:"Crédito", field:"credito", width: 120, hozAlign:"right", formatter: moneyFormatter, bottomCalc:"sum", bottomCalcFormatter: moneyFormatter},
                    {title:"Saldo", field:"saldo", width: 120, hozAlign:"right", formatter: moneyFormatter, bottomCalc:"sum", bottomCalcFormatter: moneyFormatter},
                ],
                rowFormatter: function(row){
                    const data = row.getData();
                    if(data.is_ajustado){
                        const origem = data.origem || "";
                        if (origem.includes("(NOVO)")) {
                             row.getElement().style.backgroundColor = "rgba(40, 167, 69, 0.1)"; // Verde suave para novos
                        } else {
                             row.getElement().style.backgroundColor = "rgba(255, 193, 7, 0.1)"; // Amarelo suave para edições
                        }
                    }
                },
            });
        }

        // ====================================================================
        // --- MÓDULO 2: RENTABILIDADE (BI) ---
        // ====================================================================

        toggleScaleMode() {
            if (this.biIsLoading) return;
            this.biState.scaleMode = (this.biState.scaleMode === 'dre') ? 'normal' : 'dre';
            this.loadRentabilidadeReport(this.biState.origemFilter);
        }

        formatDREValue(value) {
            if (value === 0 || value === null) return '-';
            const isNegative = value < 0;
            const absValue = Math.abs(value);
            const formatted = absValue.toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
            return isNegative ? `(${formatted})` : formatted;
        }

        async loadRentabilidadeReport(origem = null) {
            if (!this.modal) this.modal = new ModalSystem('modalRelatorio');
            if (origem !== null) this.biState.origemFilter = origem;
            
            const viewTitle = this.biState.viewMode === 'CC' ? 'por Centro de Custo' : 'por Tipo';
            const scaleTitle = this.biState.scaleMode === 'dre' ? '(Em Milhares)' : '(Valor Integral)';
            
            this.modal.open(`<i class="fas fa-cubes"></i> Análise Gerencial ${viewTitle} <small class="modal-title">${scaleTitle}</small>`, '');
            this.modal.showLoading('Construindo cubo de dados...');

            try {
                let urlBase;
                if (this.biState.viewMode === 'CC') {
                    urlBase = (API_ROUTES?.getRentabilidadeDataCC) || '/Reports/RelatorioRazao/RentabilidadePorCC';
                } else {
                    urlBase = (API_ROUTES?.getRentabilidadeData) || '/Reports/RelatorioRazao/Rentabilidade';
                }

                const origemParam = encodeURIComponent(this.biState.origemFilter);
                const scaleParam = this.biState.scaleMode; 
                
                const rawData = await APIUtils.get(`${urlBase}?origem=${origemParam}&scale_mode=${scaleParam}`);
                
                if (!rawData || rawData.length === 0) {
                    this.renderBiEmptyState();
                    return;
                }

                this.biRawData = rawData;
                await this.processBiTreeWithCalculated();
                this.renderBiInterface();

            } catch (error) {
                console.error(error);
                this.modal.showError(`Erro no BI: ${error.message}`);
            }
        }

        toggleViewMode() {
            if (this.biIsLoading) return;
            this.biState.viewMode = (this.biState.viewMode === 'TIPO') ? 'CC' : 'TIPO';
            // Usa o primeiro elemento do array como filtro de origem (Embora a origem agora suporte múltiplos)
            this.loadRentabilidadeReport(this.biState.selectedOrigins.join(',')); 
        }

        renderBiEmptyState() {
            const emptyHtml = `
                <div class="bi-toolbar d-flex justify-content-between align-items-center p-3 border-bottom border-primary bg-tertiary">
                    <div class="d-flex gap-2 align-items-center">${this.renderOrigemFilter()}</div>
                </div>
                <div class="p-4 text-center" style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;">
                    <i class="fas fa-database fa-3x text-muted mb-3"></i>
                    <h4 class="text-secondary">Sem dados</h4>
                    <p class="text-muted">Nenhum registro encontrado para "${this.biState.origemFilter}".</p>
                </div>`;
            this.modal.setContent(`<div style="display: flex; flex-direction: column; height: 100%;">${emptyHtml}</div>`);
        }

        async reloadBiDataAsync() {
            if (this.biIsLoading) return;
            this.biIsLoading = true;
            
            // Monta string separada por vírgula para enviar ao backend
            const origemParam = encodeURIComponent(this.biState.selectedOrigins.join(','));
            
            const container = document.getElementById('biGridContainer');
            if (container) container.innerHTML = `<div class="loading-container" style="height: 100%;"><div class="loading-spinner"></div></div>`;

            // Renderiza a toolbar novamente para refletir os botões ativos/inativos
            // (Isso é opcional se quiser atualizar só as classes, mas renderizar tudo garante consistência)
            const toolbarDiv = document.querySelector('.bi-toolbar');
            if (toolbarDiv) {
                // Atualiza apenas a parte dos botões se possível, ou redesenha toolbar na próxima etapa
                // Para simplificar, vamos deixar o renderBiInterface atualizar tudo no final ou manipular classes aqui:
                document.querySelectorAll('.origem-toggle-group button').forEach(btn => {
                    const txt = btn.textContent.trim();
                    // Lógica simples de atualização visual
                });
            }

            try {
                let urlBase = (this.biState.viewMode === 'CC') 
                    ? (typeof API_ROUTES !== 'undefined' && API_ROUTES.getRentabilidadeDataCC ? API_ROUTES.getRentabilidadeDataCC : '/Reports/RelatorioRazao/RentabilidadePorCC')
                    : (typeof API_ROUTES !== 'undefined' && API_ROUTES.getRentabilidadeData ? API_ROUTES.getRentabilidadeData : '/Reports/RelatorioRazao/Rentabilidade');
                
                // Usa a rota única se o backend suportar o parametro viewMode na mesma rota, mas mantendo a lógica original:
                // O código original usava rotas diferentes ou lógica interna.
                // Vamos focar na chamada principal:
                
                urlBase = (typeof API_ROUTES !== 'undefined' && API_ROUTES.getRentabilidadeData) 
                        ? API_ROUTES.getRentabilidadeData 
                        : '/Reports/RelatorioRazao/Rentabilidade';

                const scaleParam = this.biState.scaleMode;
                const ccParam = encodeURIComponent(this.biState.ccFilter);

                const rawData = await APIUtils.get(`${urlBase}?origem=${origemParam}&scale_mode=${scaleParam}&centro_custo=${ccParam}`);
                
                if (!rawData || rawData.length === 0) {
                    this.biRawData = [];
                    this.biTreeData = [];
                    if (container) container.innerHTML = '<div class="p-4 text-center text-muted">Vazio (Nenhuma empresa selecionada ou sem dados)</div>';
                } else {
                    this.biRawData = rawData;
                    await this.processBiTreeWithCalculated();
                    this.renderBiTable();
                }
                // Re-renderiza a interface completa para atualizar os botões corretamente
                this.renderBiInterface();
                
            } catch (error) {
                console.error(error);
                if (container) container.innerHTML = `<div class="p-4 text-center text-danger">Erro: ${error.message}</div>`;
            } finally {
                this.biIsLoading = false;
            }
        }

        updateOrigemBadge() {
            const badge = document.getElementById('biOrigemBadge');
            if (badge) badge.textContent = `${this.biRawData.length} registros`;
        }

        renderOrigemFilter() {
            // Opções disponíveis
            const opcoes = ['FARMA', 'FARMADIST', 'INTEC'];
            
            return `
                <div class="origem-filter-group d-flex align-items-center gap-2">
                    <div class="btn-group origem-toggle-group" role="group" aria-label="Filtro de Empresas">
                        ${opcoes.map(op => {
                            const isActive = this.biState.selectedOrigins.includes(op);
                            const btnClass = isActive ? 'btn-primary active' : 'btn-outline-secondary';
                            const style = isActive ? 'background-color: var(--primary); color: white;' : 'background-color: var(--bg-secondary); color: var(--text-secondary);';
                            
                            return `
                            <button type="button" class="btn btn-sm ${isActive ? 'active' : ''}" 
                                    style="${style} border: 1px solid var(--border-primary);"
                                    onclick="relatorioSystem.handleOrigemChange('${op}')">
                                ${this.getOrigemIcon(op)} ${op}
                            </button>
                            `;
                        }).join('')}
                    </div>
                    <span id="biOrigemBadge" class="badge badge-secondary ms-2" title="Registros carregados">
                        ${this.biRawData.length}
                    </span>
                </div>`;
        }

        getOrigemIcon(origem) {
            const icons = {
                'FARMA': '<i class="fas fa-pills"></i>', 
                'FARMADIST': '<i class="fas fa-truck"></i>',
                'INTEC': '<i class="fas fa-network-wired"></i>' // Ícone para INTEC
            };
            return icons[origem] || '<i class="fas fa-building"></i>';
        }

        handleOrigemChange(empresaClicada) {
            if (this.biIsLoading) return;

            const currentSelection = this.biState.selectedOrigins;
            let newSelection = [];

            if (currentSelection.includes(empresaClicada)) {
                // Se já tem, remove (mas impede de ficar vazio, se desejar. Aqui permitimos vazio = 0 dados)
                newSelection = currentSelection.filter(e => e !== empresaClicada);
            } else {
                // Se não tem, adiciona
                newSelection = [...currentSelection, empresaClicada];
            }

            // Atualiza estado visual imediatamente
            this.biState.selectedOrigins = newSelection;
            
            // Recarrega dados
            this.reloadBiDataAsync();
        }

        processBiTree() {
            const root = [];
            const map = {}; 
            const meses = this.biState.columnsOrder;

            // Mapa de tradução visual
            const labelMap = {
                'Oper': 'CUSTOS',
                'Adm':  'ADMINISTRATIVO',
                'Coml': 'COMERCIAL'
            };

            const getOrCreateNode = (id, label, type, parentList) => {
                if (!map[id]) {
                    const node = { 
                        id: id, 
                        label: label, 
                        type: type, 
                        children: [], 
                        values: {},
                        isVisible: true,
                        isExpanded: this.biState.expanded.has(id),
                        ordem: 999999,
                        estiloCss: null // <--- Inicializa o campo de CSS
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

            // === CONTADOR DE DEBUG ===
            let debugCounter = 0; 
            const contaAlvoDebug = '60301020102'; // ID da conta "HORAS EXTRAS" do seu print
            // =========================

            this.biRawData.forEach((row, index) => {
                
                // ==========================================================================================
                // [DEBUGGER] - INSERIDO PARA RASTREAR O VALOR -33MM
                // ==========================================================================================
                // Verifica se é a conta problemática (ou similar)
                if ((String(row.Conta) === contaAlvoDebug) && debugCounter < 5) {
                    console.group(`%c[DEBUG ERRO -33MM] Exemplo ${debugCounter + 1}`, 'color: yellow; background: #333; padding: 4px;');
                    console.log(`📂 Conta:`, row.Conta, row.Titulo_Conta);
                    console.log(`🏷️ Tipo_CC (Vindo do Backend):`, `%c"${row.Tipo_CC}"`, 'color: cyan; font-weight: bold;');
                    console.log(`💰 Valor Jan:`, row.Jan);
                    console.log(`🏭 Centro de Custo Original:`, row.Nome_CC || row['Centro de Custo']); 
                    
                    // AQUI ESTÁ O PULO DO GATO:
                    // Se o Tipo_CC for 'Oper' (ou vazio que vira Oper), o JS vai somar no Custo Operacional.
                    // Se o Backend mandou 'Adm', ele deveria ir para Administrativo.
                    console.log(`👉 Para onde o JS vai mandar:`, labelMap[row.Tipo_CC] || row.Tipo_CC);
                    
                    console.log(`📄 Linha completa:`, row);
                    console.groupEnd();
                    debugCounter++;
                }
                // ==========================================================================================

                let rawOrdem = null;
                if (row.ordem_prioridade !== null && row.ordem_prioridade !== undefined) {
                    rawOrdem = parseInt(row.ordem_prioridade);
                } else if (row.Ordem !== null && row.Ordem !== undefined) {
                    rawOrdem = parseInt(row.Ordem);
                } else if (row.ordem !== null && row.ordem !== undefined) {
                    rawOrdem = parseInt(row.ordem); 
                }

                // --- 1. NÓ RAIZ (Tipo) ---
                const tipoId = `T_${row.Tipo_CC}`;
                const labelExibicao = labelMap[row.Tipo_CC] || row.Tipo_CC;
                
                const tipoNode = getOrCreateNode(tipoId, labelExibicao, 'root', root);
                if (row.Root_Virtual_Id) tipoNode.virtualId = row.Root_Virtual_Id;
                
                // === ALTERAÇÃO AQUI: Aplica o CSS vindo do backend se o nó ainda não tiver ===
                if (row.Estilo_CSS && !tipoNode.estiloCss) {
                    tipoNode.estiloCss = row.Estilo_CSS;
                }
                // ============================================================================
                
                if (rawOrdem !== null && rawOrdem > 0 && rawOrdem < 1000) {
                    if (tipoNode.ordem === 999999 || rawOrdem < tipoNode.ordem) {
                        tipoNode.ordem = rawOrdem;
                    }
                }
                
                sumValues(tipoNode, row);

                let currentNode = tipoNode;
                let currentId = tipoId;

                // --- 2. CENTRO DE CUSTO (Modo CC) ---
                if (this.biState.viewMode === 'CC' && row.Nome_CC) {
                    const safeCCName = String(row.Nome_CC).replace(/[^a-zA-Z0-9]/g, '');
                    currentId += `_CC_${safeCCName}`;
                    const ccNode = getOrCreateNode(currentId, row.Nome_CC, 'group', currentNode.children);
                    sumValues(ccNode, row);
                    currentNode = ccNode;
                }

                // --- 3. SUBGRUPOS ---
                if (row.Caminho_Subgrupos && row.Caminho_Subgrupos !== 'Não Classificado' && row.Caminho_Subgrupos !== 'Direto' && row.Caminho_Subgrupos !== 'Calculado') {
                    const groups = row.Caminho_Subgrupos.split('||');
                    
                    groups.forEach((gName, idx) => {
                        const safeGName = gName.replace(/[^a-zA-Z0-9]/g, '');
                        currentId += `_G${idx}_${safeGName}`; 
                        
                        const groupNode = getOrCreateNode(currentId, gName, 'group', currentNode.children);
                        
                        const isLastGroup = idx === groups.length - 1;
                        if (isLastGroup && rawOrdem !== null && rawOrdem > 0) {
                            if (groupNode.ordem === 999999 || rawOrdem < groupNode.ordem) {
                                groupNode.ordem = rawOrdem;
                            }
                        }
                        
                        sumValues(groupNode, row);
                        currentNode = groupNode;
                    });
                }

                // --- 4. CONTA (Folha) ---
                const contaId = `C_${row.Conta}_${currentId}`; 
                const contaNode = {
                    id: contaId,
                    label: `📄 ${row.Conta} - ${row.Titulo_Conta}`,
                    rawTitle: row.Titulo_Conta,
                    
                    contaCodigo: row.Conta,   
                    tipoCC: row.Tipo_CC,      

                    type: 'account',
                    children: [],
                    values: {},
                    isVisible: true,
                    ordem: parseInt(row.Conta) || 999999
                };
                meses.forEach(m => contaNode.values[m] = parseFloat(row[m]) || 0);
                currentNode.children.push(contaNode);
            });

            this.biTreeData = root;
            this.applyBiFilters();
        }

        async processBiTreeWithCalculated() {
            this.processBiTree();
            const nosCalc = await this.loadNosCalculados(); 

            if (nosCalc.length > 0) {
                const valoresAgregados = this.agregarValoresPorTipo();
                const meses = this.biState.columnsOrder;
                
                nosCalc.forEach(noCalc => {
                    if (!noCalc.formula) return;
                    
                    // Lógica de Contexto (Operacional, Adm, Coml)
                    let contextoSuffix = null;
                    const nomeUpper = (noCalc.nome || '').toUpperCase();
                    if (nomeUpper.includes('CUSTO') || nomeUpper.includes('OPERACIONAL')) contextoSuffix = 'Oper';
                    else if (nomeUpper.includes('ADMINISTRATIVO')) contextoSuffix = 'Adm';
                    else if (nomeUpper.includes('COMERCIAL') || nomeUpper.includes('VENDAS')) contextoSuffix = 'Coml';

                    const valores = {};
                    meses.forEach(mes => {
                        valores[mes] = this.calcularValorNo(noCalc.formula, mes, valoresAgregados, contextoSuffix);
                    });

                    // Salva memória
                    const chaveMemoria = `no_virtual_${noCalc.id}`;
                    if (!valoresAgregados[chaveMemoria]) valoresAgregados[chaveMemoria] = {};
                    meses.forEach(mes => valoresAgregados[chaveMemoria][mes] = valores[mes]);

                    // Tooltip
                    let textoTooltip = noCalc.formula_descricao;
                    if (!textoTooltip && noCalc.formula) {
                        const ops = noCalc.formula.operandos || [];
                        const nomesOps = ops.map(o => o.label || o.id).join(', ');
                        textoTooltip = `Fórmula Calculada: ${nomesOps}`;
                    }

                    // Tenta encontrar a linha "física" que veio do Backend (Python)
                    // O Python manda 'Root_Virtual_Id' igual ao ID do nó
                    const rowBackend = this.biRawData.find(r => 
                        (String(r.Root_Virtual_Id) === String(noCalc.id)) || 
                        (r.Titulo_Conta === noCalc.nome && r.Is_Calculado)
                    );

                    let ordemCorreta = 50;
                    if (rowBackend && rowBackend.ordem_prioridade !== null) ordemCorreta = rowBackend.ordem_prioridade;
                    else if (noCalc.ordem !== null && noCalc.ordem !== undefined) ordemCorreta = noCalc.ordem;
                    
                    // === DEBUG CORRIGIDO ===
                    let cssFinal = noCalc.estilo_css; // Tenta pegar da configuração
                    
                    if (!cssFinal && rowBackend && rowBackend.Estilo_CSS) {
                        cssFinal = rowBackend.Estilo_CSS; // Se falhar, pega do dado bruto do Python
                    }

                    // Log de Debug para ver no F12
                    if (noCalc.nome.toUpperCase().includes('EBITDA')) {
                        console.log('--- DEBUG EBITDA ---');
                        console.log('Dados Config (noCalc):', noCalc);
                        console.log('Dados Backend (rowBackend):', rowBackend);
                        console.log('CSS Final Aplicado:', cssFinal);
                    }
                    // =======================

                    const nodeCalc = {
                        id: `calc_${noCalc.id}`,
                        label: `${noCalc.nome}`, 
                        rawLabel: noCalc.nome,     
                        type: 'calculated',
                        children: [],
                        values: valores,
                        isVisible: true,
                        isExpanded: false,
                        formulaDescricao: textoTooltip,
                        estiloCss: cssFinal, // <--- Aplica aqui
                        tipoExibicao: noCalc.tipo_exibicao,
                        ordem: ordemCorreta
                    };
                    this.biTreeData.push(nodeCalc);
                });
            }

            // Filtros de duplicatas e ordenação
            const nomesCalculados = new Set(this.biTreeData.filter(n => n.type === 'calculated').map(n => (n.rawLabel || n.label.replace('📊 ', '')).toUpperCase().trim()));
            this.biTreeData = this.biTreeData.filter(node => {
                if (node.type === 'root') {
                    const labelPadrao = node.label.toUpperCase().trim();
                    if (nomesCalculados.has(labelPadrao)) return false; 
                }
                return true;
            });

            const sortRecursive = (nodes) => {
                if (!nodes || nodes.length === 0) return;
                nodes.sort((a, b) => {
                    const ordA = (a.ordem !== undefined && a.ordem !== null) ? a.ordem : 99999;
                    const ordB = (b.ordem !== undefined && b.ordem !== null) ? b.ordem : 99999;
                    return ordA - ordB;
                });
                nodes.forEach(node => {
                    if (node.children && node.children.length > 0) sortRecursive(node.children);
                });
            };

            sortRecursive(this.biTreeData);
        }

        renderBiTable() {
            const container = document.getElementById('biGridContainer');
            if (!container) return;

            const cols = this.biState.columnsOrder.filter(c => !this.biState.hiddenCols.has(c));
            const rootHeaderName = this.biState.viewMode === 'CC' ? 'Estrutura / Centro de Custo' : 'Estrutura DRE';

            let headerHtml = `
                <thead style="position: sticky; top: 0; z-index: 20;">
                    <tr>
                        <th style="min-width: 350px; left: 0; position: sticky; z-index: 30;">
                            ${rootHeaderName}
                        </th>
                        ${cols.map(c => `
                            <th class="text-end" style="min-width: 110px;">
                                <div class="d-flex flex-column">
                                    <span class="mb-1 cursor-pointer text-xs font-bold" onclick="relatorioSystem.sortBiBy('${c}')">${c}</span>
                                </div>
                            </th>
                        `).join('')}
                    </tr>
                </thead>`;

            let bodyRows = '';
            
            const COLOR_DARK   = 'color: var(--icon-structure);'; 
            const COLOR_GRAY   = 'color: var(--icon-secondary);'; 
            const COLOR_FOLDER = 'color: var(--icon-folder);'; 
            const COLOR_LIGHT  = 'color: var(--icon-account);';
            
            const showAccounts = this.biState.showAccounts;

            const renderNode = (node, level) => {
                
                if (node.type === 'account' && !showAccounts) return;
                
                if (!node.isVisible) return;
                const padding = level * 20 + 10;
                const isGroup = node.children && node.children.length > 0;
                const isExpanded = this.biState.expanded.has(node.id);
                
                let iconClass = '';
                let iconStyle = '';

                if (node.type === 'calculated') {
                    iconClass = 'fa-calculator';
                    iconStyle = COLOR_DARK;
                } 
                else if (node.type === 'root') {
                    if (node.virtualId) {
                        iconClass = 'fa-cube';
                        iconStyle = COLOR_DARK;
                    } else {
                        iconClass = 'fa-layer-group';
                        iconStyle = COLOR_DARK;
                        if (node.ordem < 1000 && !node.virtualId) {
                            iconClass = 'fa-globe';
                            iconStyle = COLOR_GRAY;
                        }
                    }
                }
                else if (node.type === 'group') {
                    iconClass = 'fa-folder';
                    iconStyle = COLOR_FOLDER;
                }
                else if (node.type === 'account') {
                    iconClass = 'fa-file-alt';
                    iconStyle = COLOR_LIGHT;
                }

                let iconHtml = '';
                if (isGroup) {
                    iconHtml = `<i class="fas fa-caret-${isExpanded ? 'down' : 'right'} me-2 toggle-icon" onclick="event.stopPropagation(); relatorioSystem.toggleNode('${node.id}')" style="width:10px; cursor: pointer; color: var(--text-tertiary);"></i>`;
                    iconHtml += `<i class="fas ${iconClass} me-2" style="${iconStyle}"></i>`;
                } else {
                    iconHtml = `<i class="fas ${iconClass} me-2" style="margin-left: 18px; ${iconStyle}"></i>`;
                }

                let labelStyle = ''; 
                
                // === CORREÇÃO: Prepara a string de CSS ===
                // Se houver estilo no nó, usamos ele. Se não, string vazia.
                const cssString = node.estiloCss || '';
                const trStyle = cssString ? `style="${cssString}"` : '';
                // ==========================================
                
                const cellsHtml = cols.map(c => {
                    const val = node.values[c];
                    let colorClass = '';
                    if (val < 0) colorClass = 'text-danger'; 
                    else if (val === 0) colorClass = 'text-muted';
                    
                    let displayVal = '-';
                    if (val !== 0) {
                        if (this.biState.scaleMode === 'dre') displayVal = this.formatDREValue(val);
                        else displayVal = FormatUtils.formatNumber(val);
                    }
                    if (node.tipoExibicao === 'percentual' && val !== 0) displayVal = val.toFixed(2) + '%';
                    
                    const weight = (node.type === 'root' || node.type === 'calculated') ? 'font-weight: 600;' : '';
                    
                    // === CORREÇÃO: INJETA O CSS AQUI TAMBÉM ===
                    // style recebe "font-weight: 600; background-color: #xxx;"
                    return `<td class="text-end font-mono ${colorClass}" style="${weight} ${cssString}">${displayVal}</td>`;
                    // ==========================================
                }).join('');

                const isMatch = this.biState.searchMatches.includes(node.id);
                const searchClass = isMatch ? 'search-match' : '';

                // === CORREÇÃO: INJETA O CSS NA PRIMEIRA TD TAMBÉM ===
                bodyRows += `<tr id="row_${node.id}" class="bi-row-${node.type} ${searchClass}" ${trStyle}>
                        <td style="padding-left: ${padding}px; ${cssString}"> 
                            <div class="d-flex align-items-center cell-label" style="${labelStyle}">
                                ${iconHtml}<span class="text-truncate" title="${node.formulaDescricao || ''}">${node.label}</span>
                            </div>
                        </td>${cellsHtml}</tr>`;
                // ====================================================

                if (isGroup && isExpanded) node.children.forEach(child => renderNode(child, level + 1));
            };

            this.biTreeData.forEach(node => renderNode(node, 0));
            container.innerHTML = `<table class="table-modern w-100" style="border-collapse: separate; border-spacing: 0;">${headerHtml}<tbody>${bodyRows}</tbody></table>`;
        }
        
        // --- NOVO MÉTODO: Carrega a lista de CCs para o Select ---
        async loadCCList() {
            if (this.biState.listaCCs.length > 0) return; // Cache simples
            
            try {
                // Tenta pegar a rota do objeto global ou usa string fixa como fallback
                const url = (typeof API_ROUTES !== 'undefined' && API_ROUTES.getListaCCs) 
                    ? API_ROUTES.getListaCCs 
                    : '/Reports/RelatorioRazao/ListaCentrosCusto'; // Fallback se não definido no HTML
                
                const lista = await APIUtils.get(url);
                if(lista && Array.isArray(lista)) {
                    this.biState.listaCCs = lista;
                }
            } catch (e) {
                console.error("Erro ao carregar lista de CCs:", e);
            }
        }

        // --- NOVO MÉTODO: Handler para mudança no Dropdown Multi-Select ---
        handleCCChange(selectElement) {
            if (this.biIsLoading) return;
            
            const selectedOptions = Array.from(selectElement.selectedOptions).map(option => option.value);
            
            let newSelectedCCs = [];

            if (selectedOptions.includes('Todos')) {
                // Se 'Todos' foi selecionado, ele anula os outros
                newSelectedCCs = ['Todos'];
            } else if (selectedOptions.length === 0) {
                 // Impedir de ficar vazio, se nada for selecionado, volta para "Todos"
                 newSelectedCCs = ['Todos']; 
            } else {
                // Remove 'Todos' se outros foram selecionados
                newSelectedCCs = selectedOptions.filter(v => v !== 'Todos');
            }

            // Atualiza o estado
            this.biState.selectedCCs = newSelectedCCs;
            this.biState.ccFilter = newSelectedCCs.join(','); // Mantém ccFilter para compatibilidade de visualização

            // Recarrega o relatório aplicando o novo filtro
            this.loadRentabilidadeReport();
        }

        // --- NOVO MÉTODO: Abre o Dropdown customizado de CC ---
        openCCFilterDropdown(buttonElement) {
            if (this.biIsLoading) return;

            const dropdownId = 'cc-filter-dropdown';
            let dropdown = document.getElementById(dropdownId);
            
            // Se já estiver aberto, fecha
            if (dropdown) {
                dropdown.remove();
                return;
            }

            // Cria o elemento dropdown container
            dropdown = document.createElement('div');
            dropdown.id = dropdownId;
            dropdown.className = 'custom-dropdown-menu';
            
            // 1. Barra de Pesquisa (Opcional, mas útil para filtros grandes)
            // Não vamos implementar a lógica de filtro real agora, apenas o campo.
            const searchHtml = `
                <div class="dropdown-search-box">
                    <i class="fas fa-search"></i>
                    <input type="text" placeholder="Pesquisar Centro..." id="ccSearchInput" oninput="relatorioSystem.filterCCList(this.value)">
                </div>`;
            
            // 2. Opções de Checkbox
            const optionsHtml = this.biState.listaCCs.map(cc => {
                const isSelected = this.biState.selectedCCs.includes(String(cc.codigo));
                const uniqueId = `cc_chk_${cc.codigo}`;
                
                return `
                    <label class="dropdown-option-label" data-name="${cc.nome.toLowerCase()}" data-code="${cc.codigo}">
                        <input type="checkbox" value="${cc.codigo}" 
                            ${isSelected ? 'checked' : ''} 
                            onchange="relatorioSystem.handleCCCheckboxChange(this)">
                        <span>${cc.nome}</span>
                    </label>`;
            }).join('');
            
            // Opção "Todos" separada
            const isAllSelected = this.biState.selectedCCs.includes('Todos') || this.biState.selectedCCs.length === 0;
            const allOptionHtml = `
                <div class="dropdown-all-option">
                    <label class="dropdown-option-label dropdown-select-all">
                        <input type="checkbox" value="Todos" id="chkSelectAllCC" 
                            ${isAllSelected ? 'checked' : ''} 
                            onchange="relatorioSystem.handleSelectAllCC(this.checked)">
                        <span>[ Selecionar Tudo ]</span>
                    </label>
                </div>`;


            dropdown.innerHTML = searchHtml + `<div class="dropdown-options-container">${allOptionHtml}${optionsHtml}</div>`;
            
            // Posicionamento do dropdown
            const rect = buttonElement.getBoundingClientRect();
            dropdown.style.top = `${rect.bottom + 5}px`;
            // Alinha o lado direito do dropdown com o lado direito do botão
            dropdown.style.right = `${window.innerWidth - rect.right}px`; 

            document.body.appendChild(dropdown);

            // Adiciona listener para fechar ao clicar fora
            const closeOnOutsideClick = (event) => {
                if (dropdown && !dropdown.contains(event.target) && !buttonElement.contains(event.target)) {
                    dropdown.remove();
                    document.removeEventListener('click', closeOnOutsideClick);
                }
            };
            setTimeout(() => { // Timeout para evitar o fechamento imediato
                document.addEventListener('click', closeOnOutsideClick);
            }, 100);
        }

        // --- NOVO MÉTODO: Lógica de Checagem Individual ---
        handleCCCheckboxChange(checkbox) {
            const code = checkbox.value;
            let currentCCs = this.biState.selectedCCs.filter(v => v !== 'Todos');

            if (checkbox.checked) {
                // Adiciona e remove 'Todos' se for o caso
                if (!currentCCs.includes(code)) currentCCs.push(code);
            } else {
                // Remove
                currentCCs = currentCCs.filter(v => v !== code);
            }

            // Se nada for selecionado, volta para 'Todos'
            if (currentCCs.length === 0) {
                 this.biState.selectedCCs = ['Todos'];
                 document.getElementById('chkSelectAllCC').checked = true;
            } else {
                 this.biState.selectedCCs = currentCCs;
                 document.getElementById('chkSelectAllCC').checked = false;
            }
            
            this.updateCCButtonDisplay();
            
            // Recarrega o relatório com um debounce para evitar chamadas excessivas
            clearTimeout(this.biDebounceTimer); 
            this.biDebounceTimer = setTimeout(() => { this.loadRentabilidadeReport(); }, 800);
        }
        
        // --- NOVO MÉTODO: Lógica de Selecionar Tudo ---
        handleSelectAllCC(isChecked) {
             const checkboxes = document.querySelectorAll('.dropdown-options-container input[type="checkbox"]');
             
             if (isChecked) {
                // Seleciona tudo e atualiza o estado
                checkboxes.forEach(chk => chk.checked = true);
                this.biState.selectedCCs = ['Todos'];
             } else {
                // Desmarca todos e o estado voltará a ser ['Todos'] ou o primeiro item marcado
                checkboxes.forEach(chk => chk.checked = false);
                this.biState.selectedCCs = []; // Deixa vazio, o handleCCCheckboxChange vai forçar para ['Todos']
             }
             
             // Atualiza o display do botão imediatamente
             this.updateCCButtonDisplay();

             // Recarrega o relatório
             clearTimeout(this.biDebounceTimer); 
             this.biDebounceTimer = setTimeout(() => { this.loadRentabilidadeReport(); }, 800);
        }

        // --- NOVO MÉTODO: Filtragem visual (apenas no dropdown) ---
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
        
        // --- NOVO MÉTODO: Atualiza o texto do botão de filtro CC ---
        updateCCButtonDisplay() {
            const displaySpan = document.getElementById('ccFilterDisplay');
            if (!displaySpan) return;
            
            let text;
            const button = document.getElementById('ccFilterButton');
            
            if (this.biState.selectedCCs.includes('Todos')) {
                text = 'Todos os Centros';
                if(button) button.classList.remove('active-filter');
            } else {
                const count = this.biState.selectedCCs.length;
                text = `${count} Centro(s) Selecionado(s)`;
                if(button) button.classList.add('active-filter'); // Vamos usar isso no CSS para destacar
            }
            displaySpan.textContent = text;
        }

        async loadRentabilidadeReport(origemIgnorada = null) {
            if (!this.modal) this.modal = new ModalSystem('modalRelatorio');
            
            // Carrega lista de CCs
            await this.loadCCList();

            const scaleTitle = this.biState.scaleMode === 'dre' ? '(Em Milhares)' : '(Valor Integral)';
            
            // NOVO: Exibe quantos CCs estão selecionados
            const totalSelecionados = this.biState.selectedCCs.length;
            let ccTitle;
            if (this.biState.selectedCCs.includes('Todos')) {
                ccTitle = 'Todos os Centros';
            } else {
                ccTitle = `Filtro: ${totalSelecionados} CC(s) selecionados`;
            }
            
            this.modal.open(`<i class="fas fa-cubes"></i> Análise Gerencial <small class="modal-title">${scaleTitle} | ${ccTitle}</small>`, '');
            this.modal.showLoading('Calculando DRE...');

            try {
                const urlBase = (typeof API_ROUTES !== 'undefined' && API_ROUTES.getRentabilidadeData) 
                    ? API_ROUTES.getRentabilidadeData 
                    : '/Reports/RelatorioRazao/Rentabilidade';

                // ENVIA O ARRAY JOINADO de origens (empresas)
                const origemParam = encodeURIComponent(this.biState.selectedOrigins.join(','));
                
                // ENVIA O ARRAY JOINADO de centros de custo (múltiplos filtros)
                const ccParam = encodeURIComponent(this.biState.selectedCCs.join(','));

                const scaleParam = this.biState.scaleMode; 

                const rawData = await APIUtils.get(`${urlBase}?origem=${origemParam}&scale_mode=${scaleParam}&centro_custo=${ccParam}`);
                
                if (!rawData || rawData.length === 0) {
                    this.biRawData = [];
                    this.biTreeData = [];
                    this.renderBiInterface();
                    setTimeout(() => {
                        const container = document.getElementById('biGridContainer');
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

                this.biRawData = rawData;
                await this.processBiTreeWithCalculated();
                this.renderBiInterface();

            } catch (error) {
                console.error(error);
                this.modal.showError(`Erro no BI: ${error.message}`);
            }
        }
        
        renderBiInterface() {
            const isDreMode = this.biState.scaleMode === 'dre';
            const btnScaleClass = isDreMode ? 'btn-info' : 'btn-secondary';
            const btnScaleIcon = isDreMode ? 'fa-divide' : 'fa-dollar-sign';
            const btnScaleText = isDreMode ? 'Escala: Milhares (DRE)' : 'Escala: Reais';
            
            const showAccounts = this.biState.showAccounts;
            const btnAccountClass = showAccounts ? 'btn-success' : 'btn-outline-secondary';
            const btnAccountIcon = showAccounts ? 'fa-eye' : 'fa-eye-slash';
            const btnAccountText = showAccounts ? 'Contas: Visíveis' : 'Contas: Ocultas';

            // Tenta criar o nome do filtro para exibir no rodapé
            let nomeCCSelecionado;
            if (this.biState.selectedCCs.includes('Todos')) {
                nomeCCSelecionado = 'Todos';
            } else {
                 nomeCCSelecionado = `${this.biState.selectedCCs.length} selecionados`;
            }

            const toolbar = `
                <div class="bi-toolbar d-flex justify-content-between align-items-center p-3 border-bottom border-primary bg-tertiary">
                    <div class="d-flex gap-2 align-items-center flex-wrap">
                        ${this.renderOrigemFilter()}
                        
                        <button id="ccFilterButton" class="btn-selector-clean" 
                                onclick="relatorioSystem.openCCFilterDropdown(this)"
                                title="Filtrar por Centro de Custo">
                            <i class="fas fa-building text-muted me-2"></i>
                            <span id="ccFilterDisplay" class="selector-label">Todos os Centros</span>
                            <i class="fas fa-chevron-down ms-3 text-xs text-muted"></i>
                        </button>
                        <div class="separator-vertical mx-2" style="height: 20px; border-left: 1px solid var(--border-secondary);"></div>

                        <button class="btn btn-sm ${btnScaleClass}" onclick="relatorioSystem.toggleScaleMode()" title="Alternar Escala de Valores">
                            <i class="fas ${btnScaleIcon}"></i> ${btnScaleText}
                        </button>
                        
                        <button class="btn btn-sm ${btnAccountClass}" onclick="relatorioSystem.toggleAccountVisibility()" title="Alternar Visibilidade das Contas">
                            <i class="fas ${btnAccountIcon}"></i> ${btnAccountText}
                        </button>

                        <div class="separator-vertical mx-2" style="height: 20px; border-left: 1px solid var(--border-secondary);"></div>
                        
                        <div class="input-group input-group-sm" style="width: 200px;">
                            <i class="input-group-icon fas fa-search"></i>
                            <input type="text" id="biGlobalSearch" class="form-control" 
                                placeholder="Buscar na árvore..." value="${this.biState.globalSearch}"
                                oninput="relatorioSystem.handleBiGlobalSearch(this.value)"
                                onkeydown="if(event.key === 'Enter') { event.preventDefault(); relatorioSystem.navigateSearchNext(); }">
                        </div>
                    </div>
                    <div class="d-flex gap-2 align-items-center">
                        <button class="btn btn-sm btn-outline" onclick="relatorioSystem.toggleAllNodes(true)" title="Expandir Tudo"><i class="fas fa-expand-arrows-alt"></i></button>
                        <button class="btn btn-sm btn-outline" onclick="relatorioSystem.toggleAllNodes(false)" title="Recolher Tudo"><i class="fas fa-compress-arrows-alt"></i></button>
                        <button class="btn btn-sm btn-outline" onclick="relatorioSystem.openColumnManager()" title="Colunas"><i class="fas fa-columns"></i></button>
                    </div>
                </div>`;
            
            const gridContainer = `<div id="biGridContainer" class="table-fixed-container" style="flex: 1; overflow: auto; background: var(--bg-secondary);"></div>`;
            
            const footer = `
                <div class="bi-footer p-2 bg-tertiary border-top border-primary d-flex justify-content-between align-items-center">
                    <span class="text-secondary text-xs">
                        Empresas: <strong>${this.biState.selectedOrigins.join(', ')}</strong> | 
                        Filtro CC: <strong class="text-info">${nomeCCSelecionado}</strong> | 
                        Escala: <strong>${this.biState.scaleMode.toUpperCase()}</strong>
                    </span>
                    <span class="text-muted text-xs">Atualizado: ${new Date().toLocaleTimeString('pt-BR')}</span>
                </div>`;

            this.modal.setContent(`<div style="display: flex; flex-direction: column; height: 100%;">${toolbar}${gridContainer}${footer}</div>`);
            
            this.updateCCButtonDisplay();
            this.renderBiTable();
        }

        // --- MÉTODOS AUXILIARES ---
        applyBiFilters() {
            const colFilters = this.biState.filters;
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
                if (isVisible && hasColFilters) this.biState.expanded.add(node.id); 
                return isVisible;
            };
            this.biTreeData.forEach(node => checkVisibility(node));
        }
        handleBiGlobalSearch(val) { 
            this.biState.globalSearch = val; 
            if (!val) {
                this.biState.searchMatches = [];
                this.biState.searchCurrentIndex = -1;
                this.renderBiTable();
                return;
            }
            clearTimeout(this.biDebounceTimer); 
            this.biDebounceTimer = setTimeout(() => { this.performSearchTraversal(); }, 400); 
        }

        performSearchTraversal() {
            const term = this.biState.globalSearch.toLowerCase();
            this.biState.searchMatches = [];
            this.biState.searchCurrentIndex = -1;
            if (!term) return;

            const findAndExpand = (nodes, parentIds = []) => {
                nodes.forEach(node => {
                    const match = node.label.toLowerCase().includes(term);
                    if (match) {
                        this.biState.searchMatches.push(node.id);
                        parentIds.forEach(pid => this.biState.expanded.add(pid));
                    }
                    if (node.children && node.children.length > 0) findAndExpand(node.children, [...parentIds, node.id]);
                });
            };
            findAndExpand(this.biTreeData);
            if (this.biState.searchMatches.length > 0) {
                this.renderBiTable();
                setTimeout(() => this.navigateSearchNext(), 100);
            } else {
                this.renderBiTable();
            }
        }

        navigateSearchNext() {
            if (this.biState.searchMatches.length === 0) return;
            this.biState.searchCurrentIndex++;
            if (this.biState.searchCurrentIndex >= this.biState.searchMatches.length) {
                this.biState.searchCurrentIndex = 0;
            }
            const nodeId = this.biState.searchMatches[this.biState.searchCurrentIndex];
            this.scrollToNode(nodeId);
            this.updateSearchHighlights();
        }

        scrollToNode(nodeId) {
            const row = document.getElementById(`row_${nodeId}`);
            if (row) row.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }

        updateSearchHighlights() {
            document.querySelectorAll('.search-current-match').forEach(el => el.classList.remove('search-current-match'));
            const currentId = this.biState.searchMatches[this.biState.searchCurrentIndex];
            const row = document.getElementById(`row_${currentId}`);
            if (row) row.classList.add('search-current-match');
        }

        handleBiColFilter(col, val) { if (!val) delete this.biState.filters[col]; else this.biState.filters[col] = val; this.debounceRender(); }
        debounceRender() { clearTimeout(this.biDebounceTimer); this.biDebounceTimer = setTimeout(() => { this.applyBiFilters(); this.renderBiTable(); }, 400); }
        toggleNode(id) { if (this.biState.expanded.has(id)) this.biState.expanded.delete(id); else this.biState.expanded.add(id); this.renderBiTable(); }
        toggleAllNodes(expand) { const recurse = (nodes) => { nodes.forEach(n => { if (expand) this.biState.expanded.add(n.id); else this.biState.expanded.delete(n.id); if (n.children) recurse(n.children); }); }; recurse(this.biTreeData); this.renderBiTable(); }
        openColumnManager() {
            const allCols = this.biState.columnsOrder;
            const allVisible = allCols.every(c => !this.biState.hiddenCols.has(c));
            const modalHtml = `
                <div class="column-manager-container">
                    <div class="column-manager-header">
                        <h5 class="m-0"><i class="fas fa-columns text-primary"></i> Gerenciar Colunas</h5>
                        <button class="btn btn-sm btn-outline" onclick="relatorioSystem.toggleAllColumns(this)">
                            <i class="fas ${allVisible ? 'fa-check-square' : 'fa-square'}"></i> ${allVisible ? 'Desmarcar Todos' : 'Selecionar Todos'}
                        </button>
                    </div>
                    <div class="column-grid">
                        ${allCols.map(c => {
                            const isVisible = !this.biState.hiddenCols.has(c);
                            return `
                            <label class="column-option ${isVisible ? 'selected' : ''}">
                                <input type="checkbox" class="column-checkbox" value="${c}" ${isVisible ? 'checked' : ''} onchange="relatorioSystem.handleColumnToggle(this, '${c}')">
                                <span>${c}</span>
                            </label>`;
                        }).join('')}
                    </div>
                    <div class="mt-4 text-end border-top border-primary pt-3">
                        <button class="btn btn-primary-custom" style="width: auto; padding: 8px 24px;" onclick="document.querySelector('.modal-backdrop').remove(); relatorioSystem.renderBiTable()">
                            <i class="fas fa-check"></i> Aplicar Alterações
                        </button>
                    </div>
                </div>`;
            const colModal = document.createElement('div'); 
            colModal.className = 'modal-backdrop active'; 
            colModal.innerHTML = `<div class="modal-window" style="max-width: 600px;">${modalHtml}</div>`;
            colModal.onclick = (e) => { if(e.target === colModal) { colModal.remove(); this.renderBiTable(); } }; 
            document.body.appendChild(colModal);
        }

        handleColumnToggle(checkbox, col) {
            if (checkbox.checked) { this.biState.hiddenCols.delete(col); checkbox.closest('.column-option').classList.add('selected'); }
            else { this.biState.hiddenCols.add(col); checkbox.closest('.column-option').classList.remove('selected'); }
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
                if (newState) { this.biState.hiddenCols.delete(col); parent.classList.add('selected'); } 
                else { this.biState.hiddenCols.add(col); parent.classList.remove('selected'); }
            });
            this.updateSelectAllBtnState();
        }

        updateSelectAllBtnState() {
            const btn = document.querySelector('.column-manager-header button');
            if(!btn) return;
            const allCols = this.biState.columnsOrder;
            const allVisible = allCols.every(c => !this.biState.hiddenCols.has(c));
            if(allVisible) btn.innerHTML = '<i class="fas fa-check-square"></i> Desmarcar Todos';
            else btn.innerHTML = '<i class="fas fa-square"></i> Selecionar Todos';
        }

        toggleBiColumn(col) { if (this.biState.hiddenCols.has(col)) this.biState.hiddenCols.delete(col); else this.biState.hiddenCols.add(col); }
        sortBiBy(col) { 
            if (this.biState.sort.col === col) this.biState.sort.dir = this.biState.sort.dir === 'asc' ? 'desc' : 'asc';
            else { this.biState.sort.col = col; this.biState.sort.dir = 'desc'; }
            const sortNodes = (nodes) => {
                nodes.sort((a, b) => { const valA = a.values[col] || 0; const valB = b.values[col] || 0; return this.biState.sort.dir === 'asc' ? valA - valB : valB - valA; });
                nodes.forEach(n => { if (n.children) sortNodes(n.children); });
            };
            sortNodes(this.biTreeData); this.renderBiTable();
        }
        exportBiToCsv() { 
            let csv = "data:text/csv;charset=utf-8,";
            const visibleCols = this.biState.columnsOrder.filter(c => !this.biState.hiddenCols.has(c));
            csv += `# BI DRE - ${this.biState.origemFilter} - ${this.biState.viewMode}\r\nEstrutura;${visibleCols.join(";")}\r\n`;
            const processRow = (node, prefix = "") => {
                if (!node.isVisible) return;
                csv += `"${prefix}${node.label}";` + visibleCols.map(c => (node.values[c]||0).toFixed(2).replace('.',',')).join(";") + "\r\n";
                if(node.children) node.children.forEach(child => processRow(child, prefix + "  "));
            };
            this.biTreeData.forEach(n => processRow(n));
            const link = document.createElement("a"); link.href = encodeURI(csv); link.download = "bi_dre.csv"; document.body.appendChild(link); link.click(); link.remove();
        }
        async loadNosCalculados() { try { const r = await APIUtils.get((API_ROUTES?.getNosCalculados) || '/Configuracao/GetNosCalculados'); this.nosCalculados = r || []; return this.nosCalculados; } catch { return []; } }
        
        calcularValorNo(formula, mes, valoresAgregados, contextoSuffix = null) {
            if (!formula || !formula.operandos) return 0;
            
            const valores = formula.operandos.map(op => {
                const idOp = String(op.id).trim();
                const tipoOp = op.tipo;
                
                // Lógica de Prioridade (Igual ao Python)
                if (tipoOp === 'conta' && contextoSuffix) {
                    const chaveEspecifica = `conta_${idOp}${contextoSuffix}`;
                    if (valoresAgregados[chaveEspecifica] && valoresAgregados[chaveEspecifica][mes] !== undefined) {
                        return valoresAgregados[chaveEspecifica][mes];
                    }
                }
                
                // Fallback genérico
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
            const meses = this.biState.columnsOrder;

            const initKey = (key) => {
                if (!agregados[key]) {
                    agregados[key] = {};
                    meses.forEach(m => agregados[key][m] = 0);
                }
            };

            const traverse = (node) => {
                // 1. Agregação por TIPO (Raiz)
                if (node.type === 'root') {
                    const rawId = node.id.replace('T_', '').replace('CC_', '');
                    const keyTipo = `tipo_cc_${rawId}`;
                    initKey(keyTipo);
                    meses.forEach(m => agregados[keyTipo][m] += (node.values[m] || 0));
                }

                // 2. Agregação por NÓ VIRTUAL
                if (node.virtualId) {
                    const keyVirt = `no_virtual_${node.virtualId}`;
                    initKey(keyVirt);
                    meses.forEach(m => agregados[keyVirt][m] += (node.values[m] || 0));
                }

                // 3. Agregação por SUBGRUPO
                if (node.type === 'group') {
                    const keySub = `subgrupo_${node.label}`;
                    initKey(keySub);
                    meses.forEach(m => agregados[keySub][m] += (node.values[m] || 0));
                }
                
                // 4. Agregação por CONTA (Folha)
                // É aqui que garantimos a chave composta
                if (node.type === 'account' && node.contaCodigo) {
                    
                    // A. Chave Pura (ex: conta_60301020101)
                    const keyPura = `conta_${node.contaCodigo}`;
                    initKey(keyPura);
                    meses.forEach(m => agregados[keyPura][m] += (node.values[m] || 0));

                    // B. Chave Composta (ex: conta_60301020101Oper)
                    // Verifica se temos o tipoCC limpo
                    if (node.tipoCC) {
                        const tipoClean = node.tipoCC.trim();
                        // Lista segura de tipos para evitar criação de chaves inválidas
                        if (['Coml', 'Oper', 'Adm'].includes(tipoClean)) {
                            const keyComposta = `conta_${node.contaCodigo}${tipoClean}`;
                            
                            initKey(keyComposta);
                            meses.forEach(m => agregados[keyComposta][m] += (node.values[m] || 0));
                            
                            // DEBUG TEMPORÁRIO NO CONSOLE DO BROWSER
                            if (node.contaCodigo === '60301020101') {
                                // console.log(`[JS DEBUG] Chave Gerada: ${keyComposta} | Valor Jan: ${node.values['Jan']}`);
                            }
                        }
                    }
                }

                if (node.children && node.children.length > 0) {
                    node.children.forEach(child => traverse(child));
                }
            };

            this.biTreeData.forEach(rootNode => traverse(rootNode));
            
            return agregados;
        }

        downloadRazaoFull() {
            const searchTerm = encodeURIComponent(this.razaoSearch || '');
            const viewType = this.razaoViewType; 
            const baseUrl = API_ROUTES.getRazaoDownload;
            if (!baseUrl) { alert("Erro de configuração: Rota de download não encontrada."); return; }
            const finalUrl = `${baseUrl}?search=${searchTerm}&view_type=${viewType}`;
            const btnIcon = document.getElementById('iconDownload');
            if(btnIcon) btnIcon.className = "fas fa-spinner fa-spin";
            window.location.href = finalUrl;
            setTimeout(() => { if(btnIcon) btnIcon.className = "fas fa-file-excel"; }, 3000);
        }
    }

    window.relatorioSystem = new RelatorioSystem();
    window.fecharModal = function() { if (window.relatorioSystem && window.relatorioSystem.modal) window.relatorioSystem.modal.close(); };
}