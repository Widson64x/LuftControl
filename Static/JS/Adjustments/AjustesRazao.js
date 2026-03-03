/**
 * EXCEL GRID ENGINE - VERSÃO FINAL (CORREÇÃO DE DATA -1 DIA)
 * Autor: Widson Araújo (Adaptado)
 * - Filtros combinados (Texto + Checkbox)
 * - Memória de seleção (Lembram o que foi marcado)
 * - Árvore de Datas (Ano > Mês > Dia)
 * - FIX CRÍTICO: Correção do bug de data (GMT vs Local Time)
 */

const ExcelGrid = {
    // --- ESTADO ---
    rawData: [],        // Dados originais
    viewData: [],       // Dados exibidos
    filters: {},        // Filtros de texto (inputs do header)
    excelFilters: {},   // Filtros de checkbox { key: ['val1', 'val2'] }
    sort: { key: null, asc: true },
    isEditing: false, 
    ctxIndex: -1,

    // --- CONFIGURAÇÃO DAS COLUNAS ---
    columns: [
        { key: 'Status_Ajuste', title: 'St', width: 40, type: 'status', readonly: true },
        { key: 'Data', title: 'Data', width: 90, type: 'date', align: 'center' },
        { key: 'origem', title: 'Origem', width: 80, type: 'text' },
        { key: 'Filial', title: 'Filial', width: 60, type: 'text', align: 'center' },
        { key: 'Conta', title: 'Conta', width: 100, type: 'text', class: 'text-bold' },
        { key: 'Título Conta', title: 'Título Conta', width: 200, type: 'text' }, 
        { key: 'Descricao', title: 'Descrição', width: 350, type: 'text' },
        { key: 'Centro_Custo', title: 'CC', width: 80, type: 'text', align: 'center' },
        { key: 'Item', title: 'Item', width: 80, type: 'text', align: 'center' },
        { key: 'Contra Partida - Credito', title: 'Contra-Partida', width: 120, type: 'text' },
        { key: 'Debito', title: 'Débito', width: 110, type: 'money' },
        { key: 'Credito', title: 'Crédito', width: 110, type: 'money' },
        { key: 'Saldo', title: 'Saldo', width: 110, type: 'money', readonly: true, formula: true },
        { key: 'NaoOperacional', title: 'N.Op', width: 50, type: 'bool', align: 'center' }
    ],

    // --- INICIALIZAÇÃO ---
    init: function() {
        this.cacheDOM();
        this.bindEvents();
        this.renderHeader(); 
        
        const now = new Date();
        if(!this.dom.tbAno.value) this.dom.tbAno.value = now.getFullYear();
        if(!this.dom.tbMes.value) this.dom.tbMes.value = now.getMonth() + 1;
        
        this.loadData();
    },

    cacheDOM: function() {
        this.dom = {
            tableHead: document.getElementById('headerRow'),
            tableBody: document.getElementById('tableBody'),
            tableFoot: document.getElementById('tableFoot'),
            ctxMenu: document.getElementById('contextMenu'),
            loader: document.getElementById('loader'),
            status: document.getElementById('lblStatus'),
            tbAno: document.getElementById('tbAno'),
            tbMes: document.getElementById('tbMes'),
            btnLoad: document.getElementById('btnLoad'),
            btnAdd: document.getElementById('btnAdd'),
            btnCsv: document.getElementById('btnCsv'),
            btnInter: document.getElementById('btnIntergrupo')
        };
    },

    bindEvents: function() {
        this.dom.tableBody.addEventListener('click', (e) => this.handleGridClick(e));
        this.dom.tableBody.addEventListener('contextmenu', (e) => this.handleContextMenu(e));
        
        this.dom.tableHead.addEventListener('input', (e) => {
            if(e.target.classList.contains('filter-input')) this.handleFilterInput(e.target);
        });

        this.dom.btnLoad.onclick = () => this.loadData();
        this.dom.btnAdd.onclick = () => this.addNewRow();
        this.dom.btnCsv.onclick = () => this.exportCSV();
        if(this.dom.btnInter) this.dom.btnInter.onclick = () => this.gerarIntergrupo();

        const container = document.querySelector('.grid-container');
        container.addEventListener('scroll', () => requestAnimationFrame(() => this.renderBody()));
        
        document.addEventListener('click', (e) => {
            if(!this.dom.ctxMenu.contains(e.target)) this.dom.ctxMenu.style.display = 'none';
        });
        
        this.dom.ctxMenu.addEventListener('click', (e) => {
            const li = e.target.closest('li');
            if(li && li.dataset.action) {
                this.executeContextAction(li.dataset.action);
                this.dom.ctxMenu.style.display = 'none';
            }
        });
    },

    // --- CARREGAMENTO ---
    loadData: async function() {
        this.toggleLoader(true);
        try {
            const ano = this.dom.tbAno.value;
            const mes = this.dom.tbMes.value;
            const res = await fetch(`${API.getDados}?ano=${ano}&mes=${mes}`);
            const json = await res.json();
            if(json.error) throw new Error(json.error);

            this.rawData = json;
            this.excelFilters = {}; 
            this.filters = {};
            document.querySelectorAll('.filter-input').forEach(i => i.value = '');
            
            this.applyFilters(); 
            this.updateStatus(`${this.rawData.length} registros carregados.`);
        } catch (e) {
            alert("Erro: " + e.message);
        } finally {
            this.toggleLoader(false);
        }
    },

    renderHeader: function() {
        let html = '<th class="col-index">#</th>';
        this.columns.forEach(col => {
            const iconFilter = `<i class="fas fa-filter filter-btn" onclick="ExcelGrid.openFilter('${col.key}', event)"></i>`;
            html += `
                <th style="width:${col.width}px">
                    <div class="header-content">${col.title} ${iconFilter}</div>
                    <div class="filter-container">
                        <input type="text" class="filter-input" data-key="${col.key}" placeholder="...">
                    </div>
                </th>`;
        });
        this.dom.tableHead.innerHTML = html;
    },

    // =========================================================================
    //  SISTEMA DE FILTRO E DATA (CORRIGIDO)
    // =========================================================================

    /**
     * CORREÇÃO DO BUG DE DATA (-1 DIA)
     * Interpreta a string de data ignorando o timezone do navegador.
     * Se vier "2025-01-01...", garante que o objeto Date seja Dia 01, não 31.
     */
    parseDateSafe: function(val) {
        if (!val) return null;
        let dateStr = String(val);

        // Se for formato GMT/UTC string do navegador (ex: "Mon, 01 Jan...")
        // ou formato ISO com Z, usamos UTC methods para extrair a data visual
        if (dateStr.includes('GMT') || dateStr.includes('Z')) {
            const d = new Date(val);
            if (isNaN(d.getTime())) return null;
            // TRUQUE: Cria data local usando os valores UTC da string original
            return new Date(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
        }

        // Limpeza de hora (T ou Espaço)
        if (dateStr.includes('T')) dateStr = dateStr.split('T')[0];
        if (dateStr.includes(' ') && dateStr.match(/^\d{4}-\d{2}-\d{2}/)) {
            dateStr = dateStr.split(' ')[0];
        }

        // Se sobrou YYYY-MM-DD limpo
        if (dateStr.match(/^\d{4}-\d{2}-\d{2}$/)) {
            const parts = dateStr.split('-');
            // new Date(y, m, d) cria data LOCAL à meia-noite (Seguro)
            return new Date(parts[0], parts[1] - 1, parts[2]);
        }

        // Fallback
        const d = new Date(val);
        return isNaN(d.getTime()) ? null : d;
    },

    openFilter: function(key, e) {
        e.stopPropagation();
        
        const existing = document.querySelector('.excel-filter-menu');
        if(existing) existing.remove();

        const colDef = this.columns.find(c => c.key === key);
        const menu = document.createElement('div');
        menu.className = 'excel-filter-menu';

        let left = e.clientX;
        if (left + 260 > window.innerWidth) left = window.innerWidth - 270;
        menu.style.top = (e.clientY + 15) + 'px';
        menu.style.left = left + 'px';

        const activeFilter = this.excelFilters[key]; 
        let listHtml = '';
        
        // --- ÁRVORE DE DATAS ---
        if (colDef.type === 'date') {
            const tree = {};
            const mesesPT = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];

            this.rawData.forEach(row => {
                // Aqui usamos a função corrigida
                const dataObj = this.parseDateSafe(row[key]);
                if (!dataObj) return;

                const ano = dataObj.getFullYear();
                const mesIdx = dataObj.getMonth();
                const dia = dataObj.getDate();

                if (!tree[ano]) tree[ano] = {};
                if (!tree[ano][mesIdx]) tree[ano][mesIdx] = [];
                if (!tree[ano][mesIdx].includes(dia)) tree[ano][mesIdx].push(dia);
            });

            Object.keys(tree).sort((a,b) => b - a).forEach(year => {
                listHtml += `
                    <li class="tree-node">
                        <span class="caret" onclick="ExcelGrid.toggleTree(this)">▶</span> 
                        <input type="checkbox" class="chk-filter" data-type="year" value="${year}" onclick="ExcelGrid.handleCheckboxClick(this)"> 
                        <b>${year}</b>
                    </li>
                    <ul id="group-${year}" style="display:none;">`;

                Object.keys(tree[year]).sort((a,b) => a - b).forEach(mesIdx => {
                    const nomeMes = mesesPT[mesIdx];
                    const valMes = `${year}-${parseInt(mesIdx)+1}`;

                    listHtml += `
                        <li class="tree-node">
                            <span class="caret" onclick="ExcelGrid.toggleTree(this)">▶</span> 
                            <input type="checkbox" class="chk-filter" data-type="month" data-parent="${year}" value="${valMes}" onclick="ExcelGrid.handleCheckboxClick(this)"> 
                            ${nomeMes}
                        </li>
                        <ul id="group-${valMes}" style="display:none;">`;

                    tree[year][mesIdx].sort((a,b) => a - b).forEach(dia => {
                        const strDia = dia < 10 ? '0' + dia : dia;
                        const strMes = (parseInt(mesIdx)+1) < 10 ? '0' + (parseInt(mesIdx)+1) : (parseInt(mesIdx)+1);
                        const fullDate = `${year}-${strMes}-${strDia}`; 
                        
                        const isChecked = !activeFilter || activeFilter.includes(fullDate);
                        const checkedAttr = isChecked ? 'checked' : '';

                        listHtml += `
                            <li class="tree-leaf">
                                <input type="checkbox" class="chk-filter leaf" data-type="day" data-parent="${valMes}" data-root="${year}" value="${fullDate}" ${checkedAttr} onclick="ExcelGrid.handleCheckboxClick(this)"> 
                                ${strDia}
                            </li>`;
                    });
                    listHtml += `</ul>`;
                });
                listHtml += `</ul>`;
            });

        } 
        // --- TEXTO NORMAL ---
        else {
            const uniqueValues = [...new Set(this.rawData.map(r => r[key]))].filter(v => v !== null && v !== undefined).sort();
            const allSelected = !activeFilter || uniqueValues.every(v => activeFilter.includes(String(v)));
            const allCheckedAttr = allSelected ? 'checked' : '';

            listHtml += `<li><input type="checkbox" id="chk-all" ${allCheckedAttr} onclick="ExcelGrid.toggleAll(this)"> <b>(Selecionar Tudo)</b></li>`;
            
            uniqueValues.forEach(v => {
                const strVal = String(v);
                const isChecked = !activeFilter || activeFilter.includes(strVal);
                const checkedAttr = isChecked ? 'checked' : '';
                
                listHtml += `<li><input type="checkbox" class="chk-filter leaf simple" value="${strVal}" ${checkedAttr} onclick="ExcelGrid.handleSingleCheck(this)"> ${v}</li>`;
            });
        }

        menu.innerHTML = `
            <div class="filter-menu-header">
                <input type="text" class="filter-search" placeholder="Pesquisar..." onkeyup="ExcelGrid.filterList(this)">
            </div>
            <ul class="filter-menu-list">${listHtml}</ul>
            <div class="filter-menu-footer">
                <button class="btn-ok" onclick="ExcelGrid.applyExcelFilter('${key}', '${colDef.type}')">OK</button>
                <button class="btn-cancel" onclick="this.closest('.excel-filter-menu').remove()">Cancelar</button>
            </div>
        `;

        document.body.appendChild(menu);
        this.updateMenuState(menu);

        setTimeout(() => {
            document.addEventListener('click', function closeMenu(ev) {
                if(!menu.contains(ev.target) && ev.target !== e.target && !ev.target.classList.contains('filter-btn')) {
                    menu.remove();
                    document.removeEventListener('click', closeMenu);
                }
            });
        }, 100);
    },

    updateMenuState: function(menu) {
        menu.querySelectorAll('input[data-type="month"]').forEach(cb => this.updateParentState(cb.value, menu));
        menu.querySelectorAll('input[data-type="year"]').forEach(cb => this.updateParentState(cb.value, menu));
        const chkAll = menu.querySelector('#chk-all');
        if(chkAll) {
            const siblings = Array.from(menu.querySelectorAll('.chk-filter.simple'));
            const all = siblings.every(c => c.checked);
            const some = siblings.some(c => c.checked);
            chkAll.checked = some; 
            chkAll.indeterminate = some && !all;
        }
    },

    handleCheckboxClick: function(cb) {
        const type = cb.dataset.type;
        const val = cb.value;
        const menu = cb.closest('.excel-filter-menu');

        if (type === 'year') {
            const children = menu.querySelectorAll(`input[data-parent^="${val}"], input[data-root="${val}"]`);
            children.forEach(c => c.checked = cb.checked);
        }
        else if (type === 'month') {
            const children = menu.querySelectorAll(`input[data-parent="${val}"]`);
            children.forEach(c => c.checked = cb.checked);
            this.updateParentState(cb.dataset.parent, menu);
        }
        else if (type === 'day') {
            this.updateParentState(cb.dataset.parent, menu);
            const parentMonth = menu.querySelector(`input[value="${cb.dataset.parent}"]`);
            if(parentMonth) this.updateParentState(parentMonth.dataset.parent, menu);
        }
    },

    updateParentState: function(parentVal, menu) {
        const parentCb = menu.querySelector(`input[value="${parentVal}"]`);
        if(!parentCb) return;
        const siblings = Array.from(menu.querySelectorAll(`input[data-parent="${parentVal}"]`));
        const someChecked = siblings.some(c => c.checked);
        const allChecked = siblings.every(c => c.checked);
        parentCb.checked = someChecked; 
        parentCb.indeterminate = someChecked && !allChecked;
    },

    toggleTree: function(caret) {
        const ul = caret.parentElement.nextElementSibling;
        if(ul) {
            const isHidden = ul.style.display === 'none';
            ul.style.display = isHidden ? 'block' : 'none';
            caret.innerText = isHidden ? '▼' : '▶';
        }
    },

    filterList: function(input) {
        const term = input.value.toLowerCase();
        input.closest('.excel-filter-menu').querySelectorAll('li').forEach(li => {
            li.style.display = li.innerText.toLowerCase().includes(term) ? 'flex' : 'none';
        });
    },

    applyExcelFilter: function(key, type) {
        const menu = document.querySelector('.excel-filter-menu');
        if(!menu) return;
        const checkedValues = Array.from(menu.querySelectorAll('.chk-filter.leaf:checked')).map(c => c.value);
        this.excelFilters[key] = checkedValues;
        this.applyFilters(); 
        menu.remove();
    },

    handleFilterInput: function(input) {
        const key = input.dataset.key;
        const val = input.value.toLowerCase();
        if (this.filterTimeout) clearTimeout(this.filterTimeout);
        this.filterTimeout = setTimeout(() => {
            if (!val) delete this.filters[key];
            else this.filters[key] = val;
            this.applyFilters();
        }, 300);
    },

    applyFilters: function() {
        if (Object.keys(this.filters).length === 0 && Object.keys(this.excelFilters).length === 0) {
            this.viewData = [...this.rawData];
        } else {
            this.viewData = this.rawData.filter(row => {
                const textMatch = Object.keys(this.filters).every(k => {
                    const cellVal = String(row[k] || '').toLowerCase();
                    return cellVal.includes(this.filters[k]);
                });
                if(!textMatch) return false;

                const excelMatch = Object.keys(this.excelFilters).every(k => {
                    const allowedValues = this.excelFilters[k];
                    if(!allowedValues) return true;

                    const colDef = this.columns.find(c => c.key === k);
                    let rowVal = row[k];

                    if(colDef.type === 'date') {
                        // AQUI TAMBÉM USAMOS A FUNÇÃO SEGURA
                        const d = this.parseDateSafe(rowVal);
                        if(!d) return false;
                        const y = d.getFullYear();
                        const m = (d.getMonth()+1).toString().padStart(2, '0');
                        const day = d.getDate().toString().padStart(2, '0');
                        rowVal = `${y}-${m}-${day}`;
                    } else {
                        rowVal = String(rowVal);
                    }
                    
                    return allowedValues.includes(rowVal);
                });
                return excelMatch;
            });
        }

        this.renderBody();
        this.updateStatus(`${this.viewData.length} linhas exibidas.`);
    },

    toggleAll: function(cb) {
        cb.closest('.excel-filter-menu').querySelectorAll('.chk-filter.simple').forEach(c => c.checked = cb.checked);
    },
    
    handleSingleCheck: function(cb) {
        const menu = cb.closest('.excel-filter-menu');
        const siblings = Array.from(menu.querySelectorAll('.chk-filter.simple'));
        const allCb = menu.querySelector('#chk-all');
        allCb.checked = siblings.some(c => c.checked);
        allCb.indeterminate = siblings.some(c => c.checked) && !siblings.every(c => c.checked);
    },

    // --- RENDER BODY ---
    rowHeight: 22,

    renderBody: function() {
        const container = document.querySelector('.grid-container');
        const scrollTop = container.scrollTop;
        const viewportHeight = container.clientHeight;
        
        const startIndex = Math.floor(scrollTop / this.rowHeight);
        const endIndex = Math.min(this.viewData.length - 1, Math.ceil((scrollTop + viewportHeight) / this.rowHeight));

        const paddingTop = startIndex * this.rowHeight;
        const paddingBottom = (this.viewData.length - endIndex - 1) * this.rowHeight;

        let html = '';
        let tDeb = 0, tCred = 0;

        for (let i = startIndex; i <= endIndex; i++) {
            const row = this.viewData[i];
            const rowClass = row.Invalido ? 'row-invalido' : '';
            
            html += `<tr data-idx="${i}" class="${rowClass}" style="height: ${this.rowHeight}px">`;
            html += `<td class="col-index">${i + 1}</td>`;

            this.columns.forEach(col => {
                const val = row[col.key];
                const display = this.formatValue(val, col.type);
                const cls = `td-relative ${col.class || ''} ${col.align ? 'text-'+col.align : ''} ${col.type==='money'?'text-money':''}`;
                const statusColorClass = (col.key === 'Status_Ajuste') ? `status-${String(val).toLowerCase()}` : '';

                html += `<td class="${cls} ${statusColorClass}" data-key="${col.key}">${display}</td>`;
            });
            html += '</tr>';
        }

        this.dom.tableBody.innerHTML = `
            <tr style="height: ${paddingTop}px"><td colspan="${this.columns.length + 1}" style="border:none"></td></tr>
            ${html}
            <tr style="height: ${paddingBottom}px"><td colspan="${this.columns.length + 1}" style="border:none"></td></tr>
        `;

        this.viewData.forEach(r => {
            tDeb += parseFloat(r.Debito || 0);
            tCred += parseFloat(r.Credito || 0);
        });
        
        this.renderFooter(tDeb, tCred);
    },

    renderFooter: function(deb, cred) {
        const saldo = deb - cred;
        const color = saldo < 0 ? 'red' : 'blue';
        let html = '<tr><td class="col-index">Σ</td>';
        this.columns.forEach(col => {
            if(col.key === 'Debito') html += `<td class="text-right text-money">${this.formatMoney(deb)}</td>`;
            else if(col.key === 'Credito') html += `<td class="text-right text-money">${this.formatMoney(cred)}</td>`;
            else if(col.key === 'Saldo') html += `<td class="text-right text-money" style="color:${color}">${this.formatMoney(saldo)}</td>`;
            else html += '<td></td>';
        });
        html += '</tr>';
        this.dom.tableFoot.innerHTML = html;
    },

    // --- EDIÇÃO ---
    handleGridClick: function(e) {
        if (this.isEditing) return;
        const td = e.target.closest('td');
        if (!td || td.classList.contains('col-index')) return;

        const tr = td.parentElement;
        const idx = parseInt(tr.dataset.idx);
        const key = td.dataset.key;
        const rowData = this.viewData[idx];

        if (rowData.Invalido) return;
        
        const colDef = this.columns.find(c => c.key === key);
        if (!colDef || colDef.readonly) return;

        if (colDef.type === 'bool') {
            rowData[key] = !rowData[key];
            this.saveRow(rowData);
            return;
        }

        this.startEditing(td, idx, key, colDef);
    },

    startEditing: function(td, idx, key, colDef) {
        this.isEditing = true;
        const row = this.viewData[idx];
        const val = row[key];

        const input = document.createElement('input');
        input.className = 'cell-editor';
        // Ajuste no value do editor também
        const dateSafe = this.parseDateSafe(val);
        const valFormatado = dateSafe ? dateSafe.toISOString().split('T')[0] : '';
        
        input.value = (colDef.type === 'date') ? valFormatado : (val === undefined ? '' : val);
        if (colDef.type === 'money') input.type = 'number';
        
        const oldHtml = td.innerHTML;
        td.innerHTML = '';
        td.appendChild(input);
        input.focus();

        const finish = (save) => {
            if (!this.isEditing) return;
            this.isEditing = false;
            
            if (!save) {
                td.innerHTML = oldHtml;
                return;
            }

            let newVal = input.value;
            if (colDef.type === 'money') newVal = parseFloat(newVal) || 0;

            if (row[key] != newVal) {
                row[key] = newVal;
                if(key === 'Debito' || key === 'Credito') {
                    row.Saldo = (parseFloat(row.Debito||0) - parseFloat(row.Credito||0));
                }
                td.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                this.saveRow(row);
            } else {
                td.innerHTML = oldHtml;
            }
        };

        input.addEventListener('blur', () => finish(true));
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { input.blur(); } 
            else if (e.key === 'Escape') finish(false);
        });
    },

saveRow: async function(row) {
        try {
            const payload = { ...row };
            
            // Lógica de Decisão: É Criação ou Edição?
            // É Inclusão SE: Tipo_Linha for 'Inclusao' E ainda não tiver ID gerado pelo banco.
            const isCriacao = (row.Tipo_Linha === 'Inclusao' && !row.Ajuste_ID);
            
            let url = isCriacao ? API.criar : API.salvar;
            
            // Se for criação, limpamos o Ajuste_ID do payload para não confundir o back
            if (isCriacao) {
                delete payload.Ajuste_ID;
            }

            const res = await fetch(url, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ 
                    Tipo_Operacao: isCriacao ? 'INCLUSAO' : 'EDICAO', 
                    Dados: payload 
                })
            });
            const json = await res.json();

            if (json.id) {
                // Atualiza o ID na linha da tabela visualmente
                row.Ajuste_ID = json.id;
                
                // Se era Inclusão, agora deixa de ser "novo" para o sistema, 
                // para que futuras edições usem a rota de 'Salvar' (UPDATE)
                if (row.Status_Ajuste === 'Original' || !row.Status_Ajuste) {
                    row.Status_Ajuste = 'Pendente';
                }
                
                this.updateStatus(isCriacao ? "Criado com sucesso!" : "Salvo com sucesso!");
            } else {
                alert("Erro backend: " + (json.error || JSON.stringify(json)));
            }
        } catch (e) {
            console.error(e);
            alert("Erro de conexão ao salvar.");
        } finally {
            this.renderBody();
        }
    },

    // --- CONTEXT MENU ---
    handleContextMenu: function(e) {
        e.preventDefault();
        const tr = e.target.closest('tr');
        if (!tr) return;

        const idx = parseInt(tr.dataset.idx);
        this.ctxIndex = idx;
        
        document.querySelectorAll('tr.selected').forEach(r => r.classList.remove('selected'));
        tr.classList.add('selected');

        const menu = this.dom.ctxMenu;
        menu.style.display = 'block';
        
        let top = e.pageY;
        let left = e.pageX;
        if (top + menu.offsetHeight > window.innerHeight) top -= menu.offsetHeight;
        if (left + menu.offsetWidth > window.innerWidth) left -= menu.offsetWidth;
        menu.style.top = top + 'px';
        menu.style.left = left + 'px';
    },

    executeContextAction: async function(action) {
        if (this.ctxIndex < 0) return;
        const row = this.viewData[this.ctxIndex];

        if (action === 'HISTORICO') {
            this.openHistory(row.Ajuste_ID);
            return;
        }

        if (!row.Ajuste_ID) {
            alert("Salve a linha primeiro!");
            return;
        }

        this.toggleLoader(true);
        try {
            let url = API.aprovar;
            let body = { Ajuste_ID: row.Ajuste_ID };

            if (action === 'APROVAR') body.Acao = 'Aprovar';
            else if (action === 'REPROVAR') body.Acao = 'Reprovar';
            else if (action === 'INVALIDAR' || action === 'RESTAURAR') {
                url = API.statusInvalido;
                body.Acao = action;
            }

            const res = await fetch(url, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            });
            const json = await res.json();

            if (json.msg === 'OK') {
                if (action === 'APROVAR') row.Status_Ajuste = 'Aprovado';
                if (action === 'REPROVAR') row.Status_Ajuste = 'Reprovado';
                if (action === 'INVALIDAR') { row.Invalido = true; row.Status_Ajuste = 'Invalido'; }
                if (action === 'RESTAURAR') { row.Invalido = false; row.Status_Ajuste = 'Pendente'; }
                
                this.renderBody();
                this.updateStatus(`Ação ${action} realizada.`);
            } else {
                alert("Erro: " + (json.error || "Desconhecido"));
            }
        } catch (e) {
            alert("Erro API: " + e.message);
        } finally {
            this.toggleLoader(false);
        }
    },

    // --- UTILS ---
    addNewRow: function() {
        const newRow = {
            origem: 'MANUAL',
            Data: new Date().toISOString().split('T')[0],
            Filial: '', Conta: '', Descricao: 'NOVO LANÇAMENTO',
            Debito: 0, Credito: 0, Saldo: 0,
            Status_Ajuste: 'Pendente',
            Tipo_Linha: 'Inclusao',
            NaoOperacional: false
        };
        this.rawData.unshift(newRow);
        this.applyFilters();
        document.querySelector('.grid-container').scrollTop = 0;
    },

    gerarIntergrupo: async function() {
        const ano = this.dom.tbAno.value;
        const mes = this.dom.tbMes.value;
        if (!ano || !mes) return alert("Preencha Ano e Mês.");
        if(!confirm(`Gerar ajustes intergrupo para ${mes}/${ano}?`)) return;

        this.toggleLoader(true);
        try {
            const res = await fetch('/LuftControl/Adjustments/api/gerar-intergrupo', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({ ano: parseInt(ano), mes: parseInt(mes) })
            });
            const json = await res.json();
            if(json.error) throw new Error(json.error);
            alert("Logs gerados: " + (json.logs ? json.logs.length : 0));
            this.loadData();
        } catch(e) { alert("Erro: " + e.message); } finally { this.toggleLoader(false); }
    },

    openHistory: async function(id) {
        if (!id) return;
        const res = await fetch(API.historico.replace('/0', '/' + id));
        const data = await res.json();
        
        const tbody = document.getElementById('historyBody');
        tbody.innerHTML = data.map(l => `
            <tr>
                <td>${l.Data}</td><td>${l.Usuario}</td><td>${l.Campo}</td>
                <td style="color:red">${l.De}</td><td style="color:green">${l.Para}</td>
            </tr>
        `).join('');
        document.getElementById('modalHistory').classList.add('show');
    },

    formatValue: function(val, type) {
        if (val === null || val === undefined) return '';
        if (type === 'money') return parseFloat(val).toLocaleString('pt-BR', {minimumFractionDigits: 2});
        
        if (type === 'date') {
            // Usa a função segura para exibir
            const d = this.parseDateSafe(val);
            if (!d) return val;
            return d.toLocaleDateString('pt-BR');
        }

        if (type === 'bool') return val ? 'Sim' : '';
        if (type === 'status') {
             if (val === 'Aprovado') return '<i class="fas fa-check" style="color:green"></i>';
             if (val === 'Reprovado') return '<i class="fas fa-times" style="color:red"></i>';
             if (val === 'Pendente') return '<i class="fas fa-exclamation-triangle" style="color:orange"></i>';
             if (val === 'Invalido') return '<i class="fas fa-ban" style="color:gray"></i>';
             return val;
        }
        return val;
    },
    
    formatMoney: (v) => parseFloat(v).toLocaleString('pt-BR', {minimumFractionDigits: 2}),

    toggleLoader: function(show) { this.dom.loader.style.display = show ? 'flex' : 'none'; },
    updateStatus: function(msg) { this.dom.status.textContent = msg; },

    exportCSV: function() {
        // 1. Log estratégico: Mostra as chaves do primeiro objeto para você comparar com as colunas
        if (this.viewData && this.viewData.length > 0) {
            console.log("--- Mapeamento de Colunas (Primeira Linha) ---");
            console.table(this.viewData[0]); 
            // O console.table cria uma tabela visual fácil de ler com Chave/Valor
        }

        let csv = 'Conta;Titulo Conta;Data;Descricao;Contra Partida;Filial;Centro de Custo;Item;Cod Cl. Valor;Debito;Credito;Origem\n';
        
        this.viewData.forEach(r => {
            const dataFormatada = r.Data ? this.parseDateSafe(r.Data).toLocaleDateString('pt-BR') : '';
            
            // os nomes r['Título Conta'] ou r.Centro_Custo 
            csv += `${r.Conta};${r['Título Conta']};${dataFormatada};${r.Descricao};${r['Contra Partida - Credito']};${r.Filial};${r['Centro de Custo']};${r.Item};${r['Cod Cl. Valor']};${r.Debito};${r.Credito};${r.origem}\n`;
        });

        const blob = new Blob([csv], {type: 'text/csv'});
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = 'Razao.csv'; a.click();
    }
};

document.addEventListener('DOMContentLoaded', () => ExcelGrid.init());