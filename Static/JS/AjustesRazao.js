// ============================================================================
// T-Controllership | MÓDULO DE AJUSTES RAZÃO
// Versão: 2.6 - Add: Invalidar/Validar Context Menu & Visual Opacity
// ============================================================================

if (typeof window.ajustesSystemInitialized === 'undefined') {
    window.ajustesSystemInitialized = true;

    class AjustesSystem {
        constructor() {
            this.table = null;
            this.modal = document.getElementById('modalAjuste');
            this.modalHistorico = document.getElementById('modalHistorico');
            this.contextMenu = null;
            this.init();
        }

        init() {
            // Cria o HTML do menu flutuante
            this.createContextMenu();

            document.addEventListener('DOMContentLoaded', () => {
                this.initTable();
                this.loadData();
            });
            
            // --- EVENTOS GERAIS ---
            
            // ESC fecha tudo
            document.addEventListener('keydown', (e) => {
                if (e.key === "Escape") {
                    this.closeModal();
                    this.closeHistoryModal();
                    this.hideContextMenu();
                }
            });
            
            // Fechar modais ao clicar no overlay
            document.getElementById('modalAjuste')?.addEventListener('click', (e) => {
                if (e.target.classList.contains('modal-overlay')) this.closeModal();
            });
            document.getElementById('modalHistorico')?.addEventListener('click', (e) => {
                if (e.target.classList.contains('modal-overlay')) this.closeHistoryModal();
            });

            // Click global (esquerdo) fecha o menu de contexto
            document.addEventListener('click', (e) => {
                if (this.contextMenu && !this.contextMenu.contains(e.target)) {
                    this.hideContextMenu();
                }
            });
            
            // Bloqueio geral para garantir que o menu não feche ao clicar nele mesmo
            document.addEventListener('contextmenu', (e) => {
                if (e.target.closest('#ar-context-menu')) {
                    e.preventDefault();
                }
            });
        }

        // =====================================================================
        // UTILIDADE: DATA
        // =====================================================================
        formatDateDisplay(value) {
            if (!value) return '-';
            try {
                let dateStr = String(value);
                if (/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) return dateStr;
                const isoMatch = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})/);
                if (isoMatch) return `${isoMatch[3]}/${isoMatch[2]}/${isoMatch[1]}`;
                const parsed = new Date(dateStr);
                if (!isNaN(parsed.getTime())) {
                    const day = String(parsed.getUTCDate()).padStart(2, '0');
                    const month = String(parsed.getUTCMonth() + 1).padStart(2, '0');
                    const year = parsed.getUTCFullYear();
                    return `${day}/${month}/${year}`;
                }
                return dateStr;
            } catch (e) { return String(value); }
        }
        
        formatDateInput(value) {
            if (!value) return '';
            try {
                let dateStr = String(value);
                if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return dateStr;
                const isoMatch = dateStr.match(/^(\d{4}-\d{2}-\d{2})/);
                if (isoMatch) return isoMatch[1];
                const parsed = new Date(dateStr);
                if (!isNaN(parsed.getTime())) {
                    const year = parsed.getUTCFullYear();
                    const month = String(parsed.getUTCMonth() + 1).padStart(2, '0');
                    const day = String(parsed.getUTCDate()).padStart(2, '0');
                    return `${year}-${month}-${day}`;
                }
                return ''; 
            } catch (e) { return ''; }
        }

        // =====================================================================
        // CONTEXT MENU (LÓGICA)
        // =====================================================================
        createContextMenu() {
            if (document.getElementById('ar-context-menu')) return;
            
            const menu = document.createElement('div');
            menu.id = 'ar-context-menu';
            menu.className = 'ar-context-menu';
            menu.style.display = 'none';
            document.body.appendChild(menu);
            this.contextMenu = menu;
        }

        hideContextMenu() {
            if (this.contextMenu) this.contextMenu.style.display = 'none';
        }

        handleContextMenu(e, rowComponent) {
            e.preventDefault(); // MATA O MENU DO NAVEGADOR
            e.stopPropagation();
            
            const d = rowComponent.getData();
            const status = d.Status_Ajuste || 'Original'; 
            
            let options = [];

            // === CASO 1: REGISTRO INVÁLIDO ===
            // Opção única: Validar novamente (Restaurar)
            if (status === 'Invalido') {
                options.push({
                    icon: 'fa-sync-alt', 
                    label: 'Validar / Restaurar',
                    color: '#3b82f6', // Azul
                    action: () => this.toggleInvalidStatus(d.Ajuste_ID, false) // False = remover invalidez
                });
                
                // Se quiser permitir ver histórico mesmo inválido:
                if (d.Ajuste_ID) {
                    options.push({ separator: true });
                    options.push({
                        icon: 'fa-history', label: 'Histórico',
                        action: () => this.openHistoryModal(d.Ajuste_ID)
                    });
                }
            } 
            
            // === CASO 2: REGISTROS ATIVOS (Pendente, Original, Aprovado) ===
            else {
                // Editar (Sempre disponível)
                options.push({
                    icon: 'fa-pencil-alt', label: 'Editar',
                    action: () => this.editRow(d.Hash_ID)
                });

                // Ações de fluxo (apenas para Pendente)
                if (status === 'Pendente') {
                    options.push({ separator: true });
                    options.push({
                        icon: 'fa-check', label: 'Aprovar', color: '#10b981',
                        action: () => this.approve(d.Ajuste_ID, 'Aprovar')
                    });
                    options.push({
                        icon: 'fa-times', label: 'Reprovar', color: '#ef4444',
                        action: () => this.approve(d.Ajuste_ID, 'Reprovar')
                    });
                }

                // Opção de invalidar (Para todos que não são inválidos)
                options.push({ separator: true });
                options.push({
                    icon: 'fa-ban', 
                    label: 'Invalidar Registro', 
                    color: '#dc2626', // Vermelho escuro
                    action: () => this.toggleInvalidStatus(d.Ajuste_ID, true) // True = tornar inválido
                });

                // Histórico
                if (d.Ajuste_ID) {
                    options.push({ separator: true });
                    options.push({
                        icon: 'fa-history', label: 'Histórico',
                        action: () => this.openHistoryModal(d.Ajuste_ID)
                    });
                }
            }

            this.renderContextMenu(options, e.pageX, e.pageY);
        }

        renderContextMenu(options, x, y) {
            if (!this.contextMenu) return;
            
            let html = '<ul class="ar-ctx-list">';
            options.forEach((opt, idx) => {
                if (opt.separator) {
                    html += '<li class="ar-ctx-separator"></li>';
                } else {
                    const style = opt.color ? `style="color: ${opt.color}"` : '';
                    html += `
                        <li class="ar-ctx-item" data-idx="${idx}">
                            <i class="fas ${opt.icon}" ${style}></i>
                            <span>${opt.label}</span>
                        </li>
                    `;
                }
            });
            html += '</ul>';
            
            this.contextMenu.innerHTML = html;
            
            const items = this.contextMenu.querySelectorAll('.ar-ctx-item');
            items.forEach(item => {
                item.addEventListener('click', (ev) => {
                    ev.stopPropagation();
                    const idx = item.getAttribute('data-idx');
                    options[idx].action();
                    this.hideContextMenu();
                });
            });

            this.contextMenu.style.display = 'block';
            this.contextMenu.style.left = `${x}px`;
            this.contextMenu.style.top = `${y}px`;

            const rect = this.contextMenu.getBoundingClientRect();
            if (rect.right > window.innerWidth) {
                this.contextMenu.style.left = `${window.innerWidth - rect.width - 20}px`;
            }
            if (rect.bottom > window.innerHeight) {
                this.contextMenu.style.top = `${y - rect.height}px`;
            }
        }

        // =====================================================================
        // ACTIONS (NOVO: INVALIDAR/VALIDAR)
        // =====================================================================
        
        async toggleInvalidStatus(id, makeInvalid) {
            if (!id) {
                this.showToast('Salve o registro antes de alterar o status.', 'error');
                return;
            }

            const actionText = makeInvalid ? 'INVALIDAR' : 'RESTAURAR';
            const confirmText = makeInvalid 
                ? 'Deseja marcar este registro como INVÁLIDO? (Ele ficará inativo)' 
                : 'Deseja RESTAURAR este registro para validação?';

            if(!confirm(confirmText)) return;

            try {
                // AGORA USA A ROTA ESPECÍFICA, NÃO A DE APROVAÇÃO
                const res = await fetch(API_ROUTES.postStatusInvalido, { 
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ Ajuste_ID: id, Acao: actionText })
                });

                if (res.ok) {
                    this.showToast(makeInvalid ? 'Registro invalidado!' : 'Registro restaurado!', 'success');
                    this.loadData(); // Recarrega para pegar o "Invalido: true" do banco
                } else {
                    const err = await res.json();
                    throw new Error(err.error || 'Erro ao atualizar status');
                }
            } catch (e) {
                console.error(e);
                this.showToast('Erro ao comunicar com o servidor: ' + e.message, 'error');
            }
        }

        // =====================================================================
        // TABULATOR INIT & FILTROS
        // =====================================================================
        initTable() {
            if (typeof Tabulator === 'undefined') return;
            const self = this;

            this.table = new Tabulator("#gridAjustes", {
                layout: "fitData",
                height: "100%",
                placeholder: `<div style="text-align:center; padding:40px; color: #6e7681;">Carregando...</div>`,
                reactiveData: true,
                index: "Hash_ID",
                
                // === ATIVANDO FILTROS NATIVOS EM TODAS AS COLUNAS ===
                columns: [
                    {
                        title: "Status",
                        field: "Status_Ajuste",
                        frozen: true,
                        width: 120,
                        hozAlign: "center",
                        headerFilter: "input", // Filtro no cabeçalho
                        formatter: (cell) => {
                            const val = cell.getValue();
                            if (!val) return '<span class="status-badge status-original">Original</span>';
                            if (val === 'Invalido') return `<span class="status-badge status-reprovado" style="background:#e5e7eb; color:#6b7280; border-color:#d1d5db;">Inválido</span>`;
                            const cls = `status-${val.toLowerCase()}`;
                            return `<span class="status-badge ${cls}">${val}</span>`;
                        }
                    },
                    {
                        title: "Origem", field: "origem", width: 100, hozAlign: "center", headerFilter: "input",
                        formatter: (cell) => {
                            const val = cell.getValue();
                            return val ? `<strong>${val}</strong>` : '-';
                        }
                    },
                    { title: "Data", field: "Data", width: 110, hozAlign: "center", sorter: "date", headerFilter: "input", formatter: (cell) => self.formatDateDisplay(cell.getValue()) },
                    { title: "Conta", field: "Conta", width: 130, headerFilter: "input" },
                    { title: "Título Conta", field: "Título Conta", width: 200, headerFilter: "input" },
                    { title: "Número", field: "Numero", width: 140, headerFilter: "input" },
                    { title: "Descrição", field: "Descricao", width: 280, headerFilter: "input" },
                    { title: "Contra Partida", field: "Contra Partida - Credito", width: 140, headerFilter: "input" },
                    { title: "Filial", field: "Filial", width: 80, hozAlign: "center", headerFilter: "input" },
                    { title: "C. Custo", field: "Centro de Custo", width: 130, headerFilter: "input" },
                    { title: "Item", field: "Item", width: 100, headerFilter: "input" },
                    { title: "Cód. Cl.", field: "Cod Cl. Valor", width: 90, headerFilter: "input" },
                    {
                        title: "Débito", field: "Debito", width: 120, hozAlign: "right", formatter: "money", headerFilter: "number", formatterParams: { decimal: ",", thousand: ".", precision: 2 }, bottomCalc: "sum", bottomCalcFormatter: "money", bottomCalcFormatterParams: { decimal: ",", thousand: ".", precision: 2 }
                    },
                    {
                        title: "Crédito", field: "Credito", width: 120, hozAlign: "right", formatter: "money", headerFilter: "number", formatterParams: { decimal: ",", thousand: ".", precision: 2 }, bottomCalc: "sum", bottomCalcFormatter: "money", bottomCalcFormatterParams: { decimal: ",", thousand: ".", precision: 2 }
                    },
                    {
                        title: "Saldo", field: "Saldo", width: 120, hozAlign: "right", bottomCalc: "sum", headerFilter: "number",
                        formatter: (cell) => {
                            const val = cell.getValue();
                            if (val == null) return '<span style="color: #999;">-</span>';
                            const num = parseFloat(val);
                            const color = num < 0 ? 'var(--ar-danger, #ef4444)' : 'var(--ar-info, #3b82f6)';
                            return `<span style="color: ${color}; font-weight: 600;">${num.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span>`;
                        }
                    },
                    { title: "Ñ.Op", field: "NaoOperacional", width: 70, hozAlign: "center", headerFilter: "tickCross", formatter: "tickCross" }
                ],
                
                // Formatação de Linha (Estado)
                rowFormatter: (row) => {
                    const d = row.getData();
                    const el = row.getElement();
                    el.classList.remove("row-inclusao", "st-pendente", "st-aprovado", "st-reprovado", "row-invalida");
                    
                    if (d.Tipo_Linha === "Inclusao") el.classList.add("row-inclusao");
                    if (d.Status_Ajuste && d.Status_Ajuste !== 'Invalido') el.classList.add("st-" + d.Status_Ajuste.toLowerCase());
                    
                    const isInvalid = (d.Invalido === true || d.Invalido === 'true' || d.Invalido === 't');
                    if (isInvalid) el.classList.add('row-invalida');
                }
            });

            // Context Menu Handler (Mantido)
            const gridEl = document.getElementById("gridAjustes");
            if(gridEl) {
                gridEl.addEventListener('contextmenu', (e) => {
                    const rowEl = e.target.closest('.tabulator-row');
                    if (rowEl) {
                        e.preventDefault(); e.stopPropagation();
                        const row = this.table.getRow(rowEl);
                        if (row) this.handleContextMenu(e, row);
                    }
                });
            }
        }

        // =====================================================================
        // LÓGICA DE FILTROS AVANÇADOS (NOVO)
        // =====================================================================
        
        toggleFilterPanel() {
            const panel = document.getElementById('advancedFilterPanel');
            const backdrop = document.getElementById('filterBackdrop');
            
            // Verifica se já está ativo
            const isActive = panel.classList.contains('active');
            
            if (isActive) {
                // Fechar
                panel.classList.remove('active');
                if(backdrop) backdrop.classList.remove('active');
            } else {
                // Abrir
                panel.classList.add('active');
                if(backdrop) backdrop.classList.add('active');
            }
        }

        quickSort(field, dir) {
            if(!this.table) return;
            this.table.setSort(field, dir);
            // Feedback visual
            this.showToast(`Ordenando por ${field}...`, 'info');
        }

        clearFilters() {
            // Limpar inputs de texto/data/número
            ['fDataIni', 'fDataFim', 'fMes', 'fAno', 'fOrigem', 'fValorMin', 'fBuscaGlobal']
                .forEach(id => {
                    const el = document.getElementById(id);
                    if(el) el.value = '';
                });
            
            // Limpar Select Múltiplo de Status (Importante: selectedIndex = -1 limpa tudo)
            const selStatus = document.getElementById('fStatus');
            if(selStatus) selStatus.selectedIndex = -1;

            // Limpar filtros e ordenação da tabela
            this.table.clearFilter();
            this.table.clearHeaderFilter();
            this.table.clearSort();
            
            this.showToast('Filtros limpos!', 'info');
        }

        applyAdvancedFilters() {
            // 1. Coleta Inputs
            const dtIni = document.getElementById('fDataIni').value;
            const dtFim = document.getElementById('fDataFim').value;
            const mes   = document.getElementById('fMes').value;
            const ano   = document.getElementById('fAno').value;
            const origem = document.getElementById('fOrigem').value;
            const valMin = parseFloat(document.getElementById('fValorMin').value);
            const busca = document.getElementById('fBuscaGlobal').value.toLowerCase();
            
            // Coleta Status (Array)
            const selStatus = document.getElementById('fStatus');
            const statusList = Array.from(selStatus.selectedOptions).map(o => o.value);

            // 2. Cria Filtro Customizado
            const customFilter = (data) => {
                let match = true;

                // --- A. DATA (Mês/Ano e Range) ---
                let rowDate = null;
                if (data.Data) {
                    // Tenta criar data (assumindo YYYY-MM-DD ou ISO do banco)
                    // Ajuste o timezone se necessário, mas para mês/ano 'new Date' funciona
                    rowDate = new Date(data.Data);
                }

                // A.1 Mês (1-12)
                if (match && mes && rowDate) {
                    // getUTCMonth retorna 0-11, adicionamos 1 para comparar
                    if ((rowDate.getUTCMonth() + 1) != parseInt(mes)) match = false;
                }
                // A.2 Ano
                if (match && ano && rowDate) {
                    if (rowDate.getUTCFullYear() != parseInt(ano)) match = false;
                }
                // A.3 Range (String compare funciona bem para YYYY-MM-DD)
                if (match && (dtIni || dtFim)) {
                    const rowDateStr = this.formatDateInput(data.Data);
                    if (dtIni && rowDateStr < dtIni) match = false;
                    if (dtFim && rowDateStr > dtFim) match = false;
                }

                // --- B. STATUS (Lógica Opcional) ---
                // Só filtra se statusList TIVER itens. Se vazio (length 0), ignora (match true).
                if (match && statusList.length > 0) {
                    const st = data.Status_Ajuste || 'Original';
                    if (!statusList.includes(st)) match = false;
                }

                // --- C. ORIGEM ---
                if (match && origem) {
                    if ((data.origem || '') !== origem) match = false;
                }

                // --- D. VALOR MÍNIMO (Saldo Absoluto) ---
                if (match && !isNaN(valMin)) {
                    const saldo = Math.abs(parseFloat(data.Saldo || 0));
                    if (saldo < valMin) match = false;
                }

                // --- E. BUSCA TEXTUAL ---
                if (match && busca) {
                    const textContent = [
                        data.Conta, 
                        data.Descricao, 
                        data['Título Conta'],
                        data.Numero
                    ].join(' ').toLowerCase();
                    
                    if (!textContent.includes(busca)) match = false;
                }

                return match;
            };

            // 3. Aplica no Tabulator
            this.table.setFilter(customFilter);
            this.showToast('Filtros aplicados com sucesso!', 'success');
            
            // Fecha o painel automaticamente
            this.toggleFilterPanel();
        }

        // =====================================================================
        // DATA LOADING & MODALS (Mantido)
        // =====================================================================
        async loadData() {
            try {
                // PASSO 1: Definir qual mês/ano será processado pela regra
                // Se você tiver inputs de filtro na tela, pegue o valor deles aqui via document.getElementById...
                // Vou deixar fixo como exemplo ou pegando data atual, mas ajuste conforme sua necessidade:
                const dataRef = new Date(); 
                const anoParaProcessar = 2025; // Ex: document.getElementById('filtroAno').value
                const mesParaProcessar = 1;    // Ex: document.getElementById('filtroMes').value

                // PASSO 2: Rodar a automação de Intergrupo (POST)
                // O 'await' aqui é crucial: ele trava a execução até o Python terminar de criar as linhas.
                const resIntergrupo = await fetch(API_ROUTES.getIntergrupos, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        ano: parseInt(anoParaProcessar), 
                        mes: parseInt(mesParaProcessar) 
                    })
                });

                // Opcional: Verificar se deu erro na regra de negócio antes de prosseguir
                if (!resIntergrupo.ok) {
                    console.warn("Aviso: O processamento de intergrupo retornou erro ou já estava processado.");
                }

                // PASSO 3: Carregar os dados da tabela (Fluxo normal)
                // Agora o banco já tem as linhas 'B' e os estornos criados
                const res = await fetch(API_ROUTES.getDados);
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                
                const data = await res.json();

                // Tratamento de IDs para o Tabulator (conforme seu código original)
                data.forEach((d, i) => { 
                    if (!d.Hash_ID) d.Hash_ID = "TMP_" + i + "_" + Date.now(); 
                });

                this.table.replaceData(data);

            } catch (e) {
                console.error('Erro ao carregar dados:', e);
                this.table.alert("Erro ao processar e carregar dados.", "error");
            }
        }
        showModal(show) {
            if (!this.modal) return;
            if (show) {
                this.modal.classList.add('active'); 
                document.body.style.overflow = 'hidden';
            } else {
                this.modal.classList.remove('active');
                document.body.style.overflow = '';
            }
        }

        closeModal() { this.showModal(false); }
        resetForm() {
            const form = document.getElementById('formAjuste');
            if (form) form.reset();
            document.getElementById('inpHashId').value = '';
            document.getElementById('inpAjusteId').value = '';
        }

        editRow(hashId) {
            const d = this.table.getData().find(r => r.Hash_ID == hashId);
            if (!d) return;
            const isNew = d.Tipo_Linha === 'Inclusao';
            document.getElementById('modalTitleText').innerText = isNew ? "Editar Inclusão" : "Editar Original";
            document.getElementById('inpHashId').value = d.Hash_ID;
            document.getElementById('inpAjusteId').value = d.Ajuste_ID || '';
            document.getElementById('inpTipoOperacao').value = isNew ? 'INCLUSAO' : 'EDICAO';
            document.getElementById('inpData').value = this.formatDateInput(d.Data);
            document.getElementById('inpOrigem').value = d.origem || 'MANUAL';
            document.getElementById('inpFilial').value = d.Filial || '';
            document.getElementById('inpNumero').value = d.Numero || '';
            document.getElementById('inpConta').value = d.Conta || '';
            document.getElementById('inpTituloConta').value = d['Título Conta'] || '';
            document.getElementById('inpItem').value = d.Item || '';
            document.getElementById('inpCC').value = d['Centro de Custo'] || '';
            document.getElementById('inpCodCl').value = d['Cod Cl. Valor'] || '';
            document.getElementById('inpContraPartida').value = d['Contra Partida - Credito'] || '';
            document.getElementById('inpDescricao').value = d.Descricao || '';
            document.getElementById('inpDebito').value = d.Debito || '';
            document.getElementById('inpCredito').value = d.Credito || '';
            document.getElementById('inpNaoOperacional').checked = !!d.NaoOperacional;
            document.getElementById('inpExibirSaldo').checked = d.Exibir_Saldo !== false;
            this.showModal(true);
        }

        openModalInclusao() {
            this.resetForm();
            document.getElementById('modalTitleText').innerText = "Novo Lançamento";
            document.getElementById('inpTipoOperacao').value = 'INCLUSAO';
            const today = new Date();
            document.getElementById('inpData').value = today.toISOString().split('T')[0];
            document.getElementById('inpOrigem').value = 'MANUAL';
            document.getElementById('inpExibirSaldo').checked = true;
            this.showModal(true);
        }

        async save() {
            const btn = document.getElementById('btnSalvar');
            const originalHtml = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Salvando...';
            btn.disabled = true;
            const payload = {
                Tipo_Operacao: document.getElementById('inpTipoOperacao').value,
                Hash_ID: document.getElementById('inpHashId').value,
                Ajuste_ID: document.getElementById('inpAjusteId').value,
                Dados: {
                    origem: document.getElementById('inpOrigem').value,
                    Data: document.getElementById('inpData').value,
                    Filial: document.getElementById('inpFilial').value,
                    Numero: document.getElementById('inpNumero').value,
                    Conta: document.getElementById('inpConta').value,
                    Titulo_Conta: document.getElementById('inpTituloConta').value,
                    Item: document.getElementById('inpItem').value,
                    'Centro de Custo': document.getElementById('inpCC').value,
                    Cod_Cl_Valor: document.getElementById('inpCodCl').value,
                    Contra_Partida: document.getElementById('inpContraPartida').value,
                    Descricao: document.getElementById('inpDescricao').value,
                    Debito: document.getElementById('inpDebito').value || null,
                    Credito: document.getElementById('inpCredito').value || null,
                    NaoOperacional: document.getElementById('inpNaoOperacional').checked,
                    Exibir_Saldo: document.getElementById('inpExibirSaldo').checked
                }
            };
            try {
                const res = await fetch(API_ROUTES.postSalvar, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    this.closeModal();
                    this.loadData();
                    this.showToast('Salvo com sucesso!', 'success');
                } else {
                    const err = await res.json();
                    throw new Error(err.message || 'Erro ao salvar');
                }
            } catch (e) {
                this.showToast(e.message, 'error');
            } finally {
                btn.innerHTML = originalHtml;
                btn.disabled = false;
            }
        }

        async approve(id, action) {
            if (!confirm(`Deseja ${action} este ajuste?`)) return;
            try {
                const res = await fetch(API_ROUTES.postAprovar, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ Ajuste_ID: id, Acao: action })
                });
                if (res.ok) {
                    this.loadData();
                    this.showToast(`Ajuste processado!`, 'success');
                }
            } catch (e) { this.showToast('Erro ao processar', 'error'); }
        }

        async openHistoryModal(idAjuste) {
            if (!this.modalHistorico) return;
            const tbody = document.getElementById('tbodyHistorico');
            this.modalHistorico.classList.add('active'); 
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 20px;">Carregando...</td></tr>';

            try {
                const url = API_ROUTES.getHistoricoTemplate.replace('/0', '/' + idAjuste);
                const response = await fetch(url);
                if (!response.ok) throw new Error("Erro ao buscar histórico");
                
                const logs = await response.json();
                tbody.innerHTML = '';

                if (logs.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 20px; color: #777;">Nenhum histórico encontrado.</td></tr>';
                    return;
                }

                logs.forEach(log => {
                    const tr = document.createElement('tr');
                    let label = log.Tipo;
                    if(log.Tipo === 'CRIACAO') label = '✨ Criação';
                    else if(log.Tipo === 'EDICAO') label = '✏️ Edição';
                    else if(log.Tipo === 'APROVACAO') label = '✅ Aprovação';
                    else if(log.Tipo === 'INVALIDACAO') label = '🚫 Invalidação';

                    tr.innerHTML = `
                        <td>${log.Data}</td>
                        <td>${log.Usuario || 'Sistema'}</td>
                        <td><span class="status-badge" style="font-size:0.8em; background:#eee; color:#333;">${label}</span></td>
                        <td><strong>${log.Campo}</strong></td>
                        <td><span class="val-old">${log.De}</span></td>
                        <td><span class="val-new">${log.Para}</span></td>
                    `;
                    tbody.appendChild(tr);
                });
            } catch (error) {
                tbody.innerHTML = `<tr><td colspan="6" style="color:red; text-align:center;">Erro: ${error.message}</td></tr>`;
            }
        }

        closeHistoryModal() {
            if (this.modalHistorico) this.modalHistorico.classList.remove('active');
        }

        showToast(message, type = 'info') {
            const existing = document.querySelector('.ar-toast');
            if (existing) existing.remove();
            const toast = document.createElement('div');
            toast.className = `ar-toast ar-toast-${type}`;
            toast.innerHTML = `<i class="fas fa-info-circle"></i> <span>${message}</span>`;
            Object.assign(toast.style, {
                position: 'fixed', bottom: '24px', right: '24px', padding: '14px 20px', borderRadius: '10px',
                display: 'flex', gap: '10px', zIndex: '999999', background: '#333', color: 'white',
                animation: 'toastSlide 0.3s ease-out'
            });
            if(type==='success') toast.style.background = '#10b981';
            if(type==='error') toast.style.background = '#ef4444';
            
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }
    }

    window.ajustesSystem = new AjustesSystem();
    
    // ESTILOS DINÂMICOS (Incluindo a opacidade para inválidos)
    if (!document.getElementById('ar-styles-dyn')) {
        const style = document.createElement('style');
        style.id = 'ar-styles-dyn';
        style.textContent = `
            @keyframes toastSlide { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
            
            /* Classe para linhas inválidas */
            .row-invalida {
                opacity: 0.5 !important;
                filter: grayscale(100%);
                background-color: #f9fafb !important;
                transition: opacity 0.3s;
            }
            .row-invalida:hover {
                opacity: 0.7 !important; /* Ligeiro destaque ao passar o mouse */
            }

            /* Context Menu Styles */
            .ar-context-menu {
                position: absolute;
                background: white;
                border-radius: 6px;
                box-shadow: 0 5px 20px rgba(0,0,0,0.2);
                border: 1px solid #e5e7eb;
                min-width: 190px;
                z-index: 999999 !important;
                padding: 6px 0;
                font-family: 'Segoe UI', sans-serif;
                animation: fadeIn 0.1s ease-out;
            }
            .ar-ctx-list {
                list-style: none;
                margin: 0;
                padding: 0;
            }
            .ar-ctx-item {
                padding: 10px 16px;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 12px;
                color: #374151;
                font-size: 14px;
                transition: background 0.1s;
                font-weight: 500;
            }
            .ar-ctx-item:hover {
                background-color: #f3f4f6;
                color: #111827;
            }
            .ar-ctx-item i {
                width: 16px;
                text-align: center;
                color: #6b7280;
            }
            .ar-ctx-separator {
                height: 1px;
                background: #e5e7eb;
                margin: 5px 0;
            }
            @keyframes fadeIn { from { opacity: 0; transform: scale(0.98); } to { opacity: 1; transform: scale(1); } }
        `;
        document.head.appendChild(style);
    }
}