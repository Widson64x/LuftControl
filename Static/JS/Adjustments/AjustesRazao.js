/**
 * LUFTCORE EXCEL GRID ENGINE
 * Design Premium, Filtros Combinados, Arvore de Datas e Context Menu
 */

const ExcelGrid = {
    rawData: [], viewData: [], filters: {}, excelFilters: {}, sort: { key: null, asc: true },
    isEditing: false, ctxIndex: -1,
    
    // Aumentei a altura da linha para um visual mais Premium/Limpo
    rowHeight: 32, 

    columns: [
        { key: 'Status_Ajuste', title: 'St', width: 45, type: 'status', readonly: true },
        { key: 'Data', title: 'Data', width: 95, type: 'date', align: 'center' },
        { key: 'origem', title: 'Origem', width: 90, type: 'text' },
        { key: 'Filial', title: 'Filial', width: 70, type: 'text', align: 'center' },
        { key: 'Conta', title: 'Conta', width: 110, type: 'text', class: 'text-bold' },
        { key: 'Título Conta', title: 'Título Conta', width: 220, type: 'text' }, 
        { key: 'Descricao', title: 'Descrição', width: 380, type: 'text' },
        { key: 'Centro_Custo', title: 'CC', width: 90, type: 'text', align: 'center' },
        { key: 'Item', title: 'Item', width: 80, type: 'text', align: 'center' },
        { key: 'Contra Partida - Credito', title: 'Contra-Partida', width: 130, type: 'text' },
        { key: 'Debito', title: 'Débito', width: 120, type: 'money' },
        { key: 'Credito', title: 'Crédito', width: 120, type: 'money' },
        { key: 'Saldo', title: 'Saldo', width: 120, type: 'money', readonly: true, formula: true },
        { key: 'NaoOperacional', title: 'N.Op', width: 60, type: 'bool', align: 'center' }
    ],

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
            if(e.target.classList.contains('luft-filter-input')) this.handleFilterInput(e.target);
        });

        this.dom.btnLoad.onclick = () => this.loadData();
        this.dom.btnAdd.onclick = () => this.addNewRow();
        this.dom.btnCsv.onclick = () => this.exportCSV();
        if(this.dom.btnInter) this.dom.btnInter.onclick = () => this.gerarIntergrupo();

        const container = document.querySelector('.luft-grid-container');
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
            document.querySelectorAll('.luft-filter-input').forEach(i => i.value = '');
            
            this.applyFilters(); 
            this.updateStatus(`${this.rawData.length} registros carregados.`);
        } catch (e) { alert("Erro: " + e.message); } 
        finally { this.toggleLoader(false); }
    },

    renderHeader: function() {
        let html = '<th class="luft-col-index">#</th>';
        this.columns.forEach(col => {
            const iconFilter = `<i class="fas fa-filter luft-filter-icon" onclick="ExcelGrid.openFilter('${col.key}', event)"></i>`;
            html += `
                <th style="width:${col.width}px">
                    <div class="luft-header-content">${col.title} ${iconFilter}</div>
                    <div class="luft-filter-container">
                        <input type="text" class="luft-filter-input" data-key="${col.key}" placeholder="Filtro...">
                    </div>
                </th>`;
        });
        this.dom.tableHead.innerHTML = html;
    },

    parseDateSafe: function(val) {
        if (!val) return null;
        let dateStr = String(val);
        if (dateStr.includes('GMT') || dateStr.includes('Z')) {
            const d = new Date(val);
            if (isNaN(d.getTime())) return null;
            return new Date(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
        }
        if (dateStr.includes('T')) dateStr = dateStr.split('T')[0];
        if (dateStr.includes(' ') && dateStr.match(/^\d{4}-\d{2}-\d{2}/)) dateStr = dateStr.split(' ')[0];
        if (dateStr.match(/^\d{4}-\d{2}-\d{2}$/)) {
            const parts = dateStr.split('-');
            return new Date(parts[0], parts[1] - 1, parts[2]);
        }
        const d = new Date(val);
        return isNaN(d.getTime()) ? null : d;
    },

    openFilter: function(key, e) {
        e.stopPropagation();
        const existing = document.querySelector('.luft-excel-filter-menu');
        if(existing) existing.remove();

        const colDef = this.columns.find(c => c.key === key);
        const menu = document.createElement('div');
        menu.className = 'luft-excel-filter-menu';

        let left = e.clientX;
        if (left + 260 > window.innerWidth) left = window.innerWidth - 270;
        menu.style.top = (e.clientY + 15) + 'px';
        menu.style.left = left + 'px';

        const activeFilter = this.excelFilters[key]; 
        let listHtml = '';
        
        if (colDef.type === 'date') {
            const tree = {};
            const mesesPT = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
            this.rawData.forEach(row => {
                const dataObj = this.parseDateSafe(row[key]);
                if (!dataObj) return;
                const ano = dataObj.getFullYear(), mesIdx = dataObj.getMonth(), dia = dataObj.getDate();
                if (!tree[ano]) tree[ano] = {};
                if (!tree[ano][mesIdx]) tree[ano][mesIdx] = [];
                if (!tree[ano][mesIdx].includes(dia)) tree[ano][mesIdx].push(dia);
            });

            Object.keys(tree).sort((a,b) => b - a).forEach(year => {
                listHtml += `
                    <li class="tree-node"><span class="luft-caret" onclick="ExcelGrid.toggleTree(this)">▶</span> 
                    <input type="checkbox" class="luft-chk" data-type="year" value="${year}" onclick="ExcelGrid.handleCheckboxClick(this)"> <b>${year}</b></li><ul id="group-${year}">`;
                Object.keys(tree[year]).sort((a,b) => a - b).forEach(mesIdx => {
                    const valMes = `${year}-${parseInt(mesIdx)+1}`;
                    listHtml += `
                        <li class="tree-node"><span class="luft-caret" onclick="ExcelGrid.toggleTree(this)">▶</span> 
                        <input type="checkbox" class="luft-chk" data-type="month" data-parent="${year}" value="${valMes}" onclick="ExcelGrid.handleCheckboxClick(this)"> ${mesesPT[mesIdx]}</li><ul id="group-${valMes}">`;
                    tree[year][mesIdx].sort((a,b) => a - b).forEach(dia => {
                        const strDia = dia < 10 ? '0' + dia : dia; const strMes = (parseInt(mesIdx)+1) < 10 ? '0' + (parseInt(mesIdx)+1) : (parseInt(mesIdx)+1);
                        const fullDate = `${year}-${strMes}-${strDia}`; 
                        const checkedAttr = (!activeFilter || activeFilter.includes(fullDate)) ? 'checked' : '';
                        listHtml += `<li class="tree-leaf"><input type="checkbox" class="luft-chk leaf" data-type="day" data-parent="${valMes}" data-root="${year}" value="${fullDate}" ${checkedAttr} onclick="ExcelGrid.handleCheckboxClick(this)"> ${strDia}</li>`;
                    });
                    listHtml += `</ul>`;
                });
                listHtml += `</ul>`;
            });
        } else {
            const uniqueValues = [...new Set(this.rawData.map(r => r[key]))].filter(v => v !== null && v !== undefined).sort();
            const allSelected = !activeFilter || uniqueValues.every(v => activeFilter.includes(String(v)));
            listHtml += `<li><input type="checkbox" class="luft-chk" id="chk-all" ${allSelected ? 'checked' : ''} onclick="ExcelGrid.toggleAll(this)"> <b>(Selecionar Tudo)</b></li>`;
            uniqueValues.forEach(v => {
                const strVal = String(v);
                const checkedAttr = (!activeFilter || activeFilter.includes(strVal)) ? 'checked' : '';
                listHtml += `<li><input type="checkbox" class="luft-chk leaf simple" value="${strVal}" ${checkedAttr} onclick="ExcelGrid.handleSingleCheck(this)"> ${v}</li>`;
            });
        }

        menu.innerHTML = `
            <div class="luft-filter-header"><input type="text" class="luft-filter-search" placeholder="Pesquisar..." onkeyup="ExcelGrid.filterList(this)"></div>
            <ul class="luft-filter-list">${listHtml}</ul>
            <div class="luft-filter-footer">
                <button class="luft-btn-cancel" onclick="this.closest('.luft-excel-filter-menu').remove()">Cancelar</button>
                <button class="luft-btn-ok" onclick="ExcelGrid.applyExcelFilter('${key}', '${colDef.type}')">Aplicar</button>
            </div>
        `;

        document.body.appendChild(menu);
        this.updateMenuState(menu);

        setTimeout(() => {
            document.addEventListener('click', function closeMenu(ev) {
                if(!menu.contains(ev.target) && ev.target !== e.target && !ev.target.classList.contains('luft-filter-icon')) {
                    menu.remove(); document.removeEventListener('click', closeMenu);
                }
            });
        }, 100);
    },

    updateMenuState: function(menu) {
        menu.querySelectorAll('input[data-type="month"]').forEach(cb => this.updateParentState(cb.value, menu));
        menu.querySelectorAll('input[data-type="year"]').forEach(cb => this.updateParentState(cb.value, menu));
        const chkAll = menu.querySelector('#chk-all');
        if(chkAll) {
            const siblings = Array.from(menu.querySelectorAll('.luft-chk.simple'));
            const some = siblings.some(c => c.checked);
            chkAll.checked = some; chkAll.indeterminate = some && !siblings.every(c => c.checked);
        }
    },

    handleCheckboxClick: function(cb) {
        const type = cb.dataset.type, val = cb.value, menu = cb.closest('.luft-excel-filter-menu');
        if (type === 'year') menu.querySelectorAll(`input[data-parent^="${val}"], input[data-root="${val}"]`).forEach(c => c.checked = cb.checked);
        else if (type === 'month') { menu.querySelectorAll(`input[data-parent="${val}"]`).forEach(c => c.checked = cb.checked); this.updateParentState(cb.dataset.parent, menu); }
        else if (type === 'day') { this.updateParentState(cb.dataset.parent, menu); const pm = menu.querySelector(`input[value="${cb.dataset.parent}"]`); if(pm) this.updateParentState(pm.dataset.parent, menu); }
    },

    updateParentState: function(parentVal, menu) {
        const parentCb = menu.querySelector(`input[value="${parentVal}"]`);
        if(!parentCb) return;
        const siblings = Array.from(menu.querySelectorAll(`input[data-parent="${parentVal}"]`));
        const someChecked = siblings.some(c => c.checked);
        parentCb.checked = someChecked; parentCb.indeterminate = someChecked && !siblings.every(c => c.checked);
    },

    toggleTree: function(caret) {
        const ul = caret.parentElement.nextElementSibling;
        if(ul) { const isHidden = ul.style.display === 'none'; ul.style.display = isHidden ? 'block' : 'none'; caret.innerText = isHidden ? '▼' : '▶'; }
    },

    filterList: function(input) {
        const term = input.value.toLowerCase();
        input.closest('.luft-excel-filter-menu').querySelectorAll('li').forEach(li => { li.style.display = li.innerText.toLowerCase().includes(term) ? 'flex' : 'none'; });
    },

    applyExcelFilter: function(key) {
        const menu = document.querySelector('.luft-excel-filter-menu');
        if(!menu) return;
        this.excelFilters[key] = Array.from(menu.querySelectorAll('.luft-chk.leaf:checked')).map(c => c.value);
        this.applyFilters(); menu.remove();
    },

    handleFilterInput: function(input) {
        const key = input.dataset.key, val = input.value.toLowerCase();
        if (this.filterTimeout) clearTimeout(this.filterTimeout);
        this.filterTimeout = setTimeout(() => { if (!val) delete this.filters[key]; else this.filters[key] = val; this.applyFilters(); }, 300);
    },

    applyFilters: function() {
        if (Object.keys(this.filters).length === 0 && Object.keys(this.excelFilters).length === 0) this.viewData = [...this.rawData];
        else {
            this.viewData = this.rawData.filter(row => {
                const textMatch = Object.keys(this.filters).every(k => String(row[k] || '').toLowerCase().includes(this.filters[k]));
                if(!textMatch) return false;
                return Object.keys(this.excelFilters).every(k => {
                    const allowedValues = this.excelFilters[k];
                    if(!allowedValues) return true;
                    const colDef = this.columns.find(c => c.key === k);
                    let rowVal = row[k];
                    if(colDef.type === 'date') {
                        const d = this.parseDateSafe(rowVal);
                        if(!d) return false;
                        rowVal = `${d.getFullYear()}-${(d.getMonth()+1).toString().padStart(2, '0')}-${d.getDate().toString().padStart(2, '0')}`;
                    } else rowVal = String(rowVal);
                    return allowedValues.includes(rowVal);
                });
            });
        }
        this.renderBody(); this.updateStatus(`${this.viewData.length} linhas exibidas.`);
    },

    toggleAll: function(cb) { cb.closest('.luft-excel-filter-menu').querySelectorAll('.luft-chk.simple').forEach(c => c.checked = cb.checked); },
    handleSingleCheck: function(cb) {
        const menu = cb.closest('.luft-excel-filter-menu'), siblings = Array.from(menu.querySelectorAll('.luft-chk.simple')), allCb = menu.querySelector('#chk-all');
        allCb.checked = siblings.some(c => c.checked); allCb.indeterminate = siblings.some(c => c.checked) && !siblings.every(c => c.checked);
    },

    renderBody: function() {
        const container = document.querySelector('.luft-grid-container');
        const scrollTop = container.scrollTop, viewportHeight = container.clientHeight;
        const startIndex = Math.floor(scrollTop / this.rowHeight);
        const endIndex = Math.min(this.viewData.length - 1, Math.ceil((scrollTop + viewportHeight) / this.rowHeight));

        const paddingTop = startIndex * this.rowHeight;
        const paddingBottom = (this.viewData.length - endIndex - 1) * this.rowHeight;

        let html = '', tDeb = 0, tCred = 0;
        for (let i = startIndex; i <= endIndex; i++) {
            const row = this.viewData[i];
            html += `<tr data-idx="${i}" class="${row.Invalido ? 'row-invalido' : ''}" style="height: ${this.rowHeight}px">`;
            html += `<td class="luft-col-index">${i + 1}</td>`;
            this.columns.forEach(col => {
                const val = row[col.key];
                const cls = `td-relative ${col.class || ''} ${col.align ? 'text-'+col.align : ''} ${col.type==='money'?'text-money':''}`;
                const stCls = (col.key === 'Status_Ajuste') ? `status-${String(val).toLowerCase()}` : '';
                html += `<td class="${cls} ${stCls}" data-key="${col.key}">${this.formatValue(val, col.type)}</td>`;
            });
            html += '</tr>';
        }

        this.dom.tableBody.innerHTML = `
            <tr style="height: ${paddingTop}px"><td colspan="${this.columns.length + 1}" style="border:none"></td></tr>
            ${html}
            <tr style="height: ${paddingBottom}px"><td colspan="${this.columns.length + 1}" style="border:none"></td></tr>
        `;

        this.viewData.forEach(r => { tDeb += parseFloat(r.Debito || 0); tCred += parseFloat(r.Credito || 0); });
        this.renderFooter(tDeb, tCred);
    },

    renderFooter: function(deb, cred) {
        const saldo = deb - cred;
        const color = saldo < 0 ? 'var(--luft-danger-600)' : 'var(--luft-primary-600)';
        let html = '<tr><td class="luft-col-index">Σ</td>';
        this.columns.forEach(col => {
            if(col.key === 'Debito') html += `<td class="text-right text-money">${this.formatMoney(deb)}</td>`;
            else if(col.key === 'Credito') html += `<td class="text-right text-money">${this.formatMoney(cred)}</td>`;
            else if(col.key === 'Saldo') html += `<td class="text-right text-money" style="color:${color}">${this.formatMoney(saldo)}</td>`;
            else html += '<td></td>';
        });
        html += '</tr>';
        this.dom.tableFoot.innerHTML = html;
    },

    handleGridClick: function(e) {
        if (this.isEditing) return;
        const td = e.target.closest('td');
        if (!td || td.classList.contains('luft-col-index')) return;

        const tr = td.parentElement, idx = parseInt(tr.dataset.idx), key = td.dataset.key;
        const rowData = this.viewData[idx];
        if (rowData.Invalido) return;
        
        const colDef = this.columns.find(c => c.key === key);
        if (!colDef || colDef.readonly) return;

        if (colDef.type === 'bool') { rowData[key] = !rowData[key]; this.saveRow(rowData); return; }
        this.startEditing(td, idx, key, colDef);
    },

    startEditing: function(td, idx, key, colDef) {
        this.isEditing = true; const row = this.viewData[idx], val = row[key];
        const input = document.createElement('input'); input.className = 'luft-cell-editor';
        const dateSafe = this.parseDateSafe(val);
        input.value = (colDef.type === 'date') ? (dateSafe ? dateSafe.toISOString().split('T')[0] : '') : (val === undefined ? '' : val);
        if (colDef.type === 'money') input.type = 'number';
        
        const oldHtml = td.innerHTML; td.innerHTML = ''; td.appendChild(input); input.focus();

        const finish = (save) => {
            if (!this.isEditing) return;
            this.isEditing = false;
            if (!save) { td.innerHTML = oldHtml; return; }
            let newVal = input.value; if (colDef.type === 'money') newVal = parseFloat(newVal) || 0;
            if (row[key] != newVal) {
                row[key] = newVal;
                if(key === 'Debito' || key === 'Credito') row.Saldo = (parseFloat(row.Debito||0) - parseFloat(row.Credito||0));
                td.innerHTML = '<i class="fas fa-spinner fa-spin text-primary"></i>';
                this.saveRow(row);
            } else td.innerHTML = oldHtml;
        };

        input.addEventListener('blur', () => finish(true));
        input.addEventListener('keydown', (e) => { if (e.key === 'Enter') input.blur(); else if (e.key === 'Escape') finish(false); });
    },

    handleContextMenu: function(e) {
        e.preventDefault(); const tr = e.target.closest('tr'); if (!tr) return;
        this.ctxIndex = parseInt(tr.dataset.idx);
        document.querySelectorAll('tr.selected').forEach(r => r.classList.remove('selected')); tr.classList.add('selected');
        const menu = this.dom.ctxMenu; menu.style.display = 'block';
        let top = e.pageY, left = e.pageX;
        if (top + menu.offsetHeight > window.innerHeight) top -= menu.offsetHeight;
        if (left + menu.offsetWidth > window.innerWidth) left -= menu.offsetWidth;
        menu.style.top = top + 'px'; menu.style.left = left + 'px';
    },

    executeContextAction: async function(action) {
        if (this.ctxIndex < 0) return;
        const row = this.viewData[this.ctxIndex], id = row.Id, fonte = row.Fonte;
        if (action === 'HISTORICO') { this.openHistory(id, fonte); return; }
        if (!id || !fonte) return alert("Salve a linha primeiro!");

        this.toggleLoader(true);
        try {
            let url = API.aprovar, body = { Id: id, Fonte: fonte };
            if (action === 'APROVAR') body.Acao = 'Aprovar'; else if (action === 'REPROVAR') body.Acao = 'Reprovar';
            else if (action === 'INVALIDAR' || action === 'RESTAURAR') { url = API.statusInvalido; body.Acao = action; }
            const res = await fetch(url, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
            const json = await res.json();
            if (json.msg === 'OK' || json.msg.includes('sucesso')) { this.loadData(); this.updateStatus(`Ação concluída.`); }
            else alert("Erro: " + (json.error || "Desconhecido"));
        } catch (e) { alert("Erro API: " + e.message); } finally { this.toggleLoader(false); }
    },

    addNewRow: function() {
        this.rawData.unshift({ origem: 'MANUAL', Fonte: 'MANUAL', Data: new Date().toISOString().split('T')[0], Filial: '', Conta: '', Descricao: 'NOVO LANÇAMENTO', Debito: 0, Credito: 0, Saldo: 0, Status_Ajuste: 'Pendente', Tipo_Linha: 'Inclusao', NaoOperacional: false });
        this.applyFilters(); document.querySelector('.luft-grid-container').scrollTop = 0;
    },

    saveRow: async function(row) {
        try {
            const isCriacao = (row.Tipo_Linha === 'Inclusao' && !row.Id);
            const payload = { ...row }; if (isCriacao) delete payload.Id;
            const res = await fetch(isCriacao ? API.criar : API.salvar, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ Tipo_Operacao: isCriacao ? 'INCLUSAO' : 'EDICAO', Dados: payload, Id: row.Id, Fonte: row.Fonte }) });
            const json = await res.json();
            if (json.id) { row.Id = json.id; if (row.Status_Ajuste === 'Original' || !row.Status_Ajuste) row.Status_Ajuste = 'Pendente'; this.updateStatus(isCriacao ? "Criado!" : "Salvo!"); }
            else alert("Erro: " + (json.error || JSON.stringify(json)));
        } catch (e) { alert("Erro ao salvar."); } finally { this.renderBody(); }
    },

    gerarIntergrupo: async function() {
        const ano = this.dom.tbAno.value, mes = this.dom.tbMes.value;
        if (!ano || !mes) return alert("Preencha Ano e Mês.");
        if(!confirm(`Gerar ajustes intergrupo para ${mes}/${ano}?`)) return;
        this.toggleLoader(true);
        try {
            const res = await fetch('/LuftControl/Adjustments/api/gerar-intergrupo', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ ano: parseInt(ano), mes: parseInt(mes) }) });
            const json = await res.json();
            if(json.error) throw new Error(json.error);
            alert("Logs gerados: " + (json.logs ? json.logs.length : 0)); this.loadData();
        } catch(e) { alert("Erro: " + e.message); } finally { this.toggleLoader(false); }
    },

    openHistory: async function(id, fonte) {
        if (!id || !fonte) return;
        const res = await fetch(`${API.historico}?id=${id}&fonte=${fonte}`); const data = await res.json();
        if (data.error) return alert("Erro: " + data.error);
        document.getElementById('historyBody').innerHTML = data.map(l => `<tr><td>${l.Data}</td><td>${l.Usuario}</td><td>${l.Campo}</td><td class="text-danger">${l.De}</td><td class="text-success font-bold">${l.Para}</td></tr>`).join('');
        document.getElementById('modalHistory').classList.add('show');
    },

    formatValue: function(val, type) {
        if (val === null || val === undefined) return '';
        if (type === 'money') return parseFloat(val).toLocaleString('pt-BR', {minimumFractionDigits: 2});
        if (type === 'date') { const d = this.parseDateSafe(val); return d ? d.toLocaleDateString('pt-BR') : val; }
        if (type === 'bool') return val ? '<i class="fas fa-check text-primary"></i>' : '';
        if (type === 'status') {
             if (val === 'Aprovado') return '<i class="fas fa-check-circle text-success" title="Aprovado"></i>';
             if (val === 'Reprovado') return '<i class="fas fa-times-circle text-danger" title="Reprovado"></i>';
             if (val === 'Pendente') return '<i class="fas fa-clock text-warning" title="Pendente"></i>';
             if (val === 'Invalido') return '<i class="fas fa-ban text-muted" title="Inválido"></i>';
             return val;
        }
        return val;
    },
    
    formatMoney: (v) => parseFloat(v).toLocaleString('pt-BR', {minimumFractionDigits: 2}),
    toggleLoader: function(show) { this.dom.loader.style.display = show ? 'flex' : 'none'; },
    updateStatus: function(msg) { this.dom.status.textContent = msg; },

    exportCSV: function() {
        let csv = 'Conta;Titulo Conta;Data;Descricao;Contra Partida;Filial;Centro de Custo;Item;Cod Cl. Valor;Debito;Credito;Origem\n';
        this.viewData.forEach(r => {
            const dataFormatada = r.Data ? this.parseDateSafe(r.Data).toLocaleDateString('pt-BR') : '';
            csv += `${r.Conta};${r['Título Conta']};${dataFormatada};${r.Descricao};${r['Contra Partida - Credito']};${r.Filial};${r['Centro de Custo']};${r.Item};${r['Cod Cl. Valor']};${r.Debito};${r.Credito};${r.origem}\n`;
        });
        const a = document.createElement('a'); a.href = window.URL.createObjectURL(new Blob([csv], {type: 'text/csv'})); a.download = 'Razao.csv'; a.click();
    }
};

document.addEventListener('DOMContentLoaded', () => ExcelGrid.init());