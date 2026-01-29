/**
 * EXCEL GRID ENGINE - OTIMIZADO
 * Autor: Widson Araújo (Adaptado)
 * Foco: Performance (Event Delegation), Filtros Dinâmicos e Usabilidade
 */

const ExcelGrid = {
    // --- ESTADO ---
    rawData: [],      // Dados originais do servidor
    viewData: [],     // Dados filtrados exibidos
    filters: {},      // Estado atual dos filtros { chave: 'valor' }
    sort: { key: null, asc: true },
    isEditing: false, // Bloqueio durante edição
    ctxIndex: -1,     // Índice da linha clicada com botão direito

    // --- CONFIGURAÇÃO DAS COLUNAS ---
    columns: [
        { key: 'Status_Ajuste', title: 'St', width: 40, type: 'status', readonly: true },
        { key: 'Data', title: 'Data', width: 90, type: 'date', align: 'center' },
        { key: 'origem', title: 'Origem', width: 80, type: 'text' },
        { key: 'Filial', title: 'Filial', width: 60, type: 'text', align: 'center' },
        { key: 'Conta', title: 'Conta', width: 100, type: 'text', class: 'text-bold' },
        { key: 'Descricao', title: 'Descrição', width: 350, type: 'text' },
        { key: 'Centro_Custo', title: 'CC', width: 80, type: 'text', align: 'center' },
        { key: 'Item', title: 'Item', width: 80, type: 'text', align: 'center' },
        { key: 'Contra_Partida', title: 'Contra-Partida', width: 100, type: 'text' },
        { key: 'Debito', title: 'Débito', width: 110, type: 'money' },
        { key: 'Credito', title: 'Crédito', width: 110, type: 'money' },
        { key: 'Saldo', title: 'Saldo', width: 110, type: 'money', readonly: true, formula: true },
        { key: 'NaoOperacional', title: 'N.Op', width: 50, type: 'bool', align: 'center' }
    ],

    // --- INICIALIZAÇÃO ---
    init: function() {
        this.cacheDOM();
        this.bindEvents();
        this.renderHeader(); // Renderiza header uma vez só
        
        // Seta data atual
        const now = new Date();
        this.dom.tbAno.value = now.getFullYear();
        this.dom.tbMes.value = now.getMonth() + 1;
        
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
        // Event Delegation no TBODY (Performance Extrema)
        // Um único listener controla cliques em milhares de células
        this.dom.tableBody.addEventListener('click', (e) => this.handleGridClick(e));
        this.dom.tableBody.addEventListener('contextmenu', (e) => this.handleContextMenu(e));
        
        // Filtros (Debounce)
        this.dom.tableHead.addEventListener('input', (e) => {
            if(e.target.classList.contains('filter-input')) {
                this.handleFilterInput(e.target);
            }
        });

        // Botões
        this.dom.btnLoad.onclick = () => this.loadData();
        this.dom.btnAdd.onclick = () => this.addNewRow();
        this.dom.btnCsv.onclick = () => this.exportCSV();
        this.dom.btnInter.onclick = () => this.gerarIntergrupo();

        const container = document.querySelector('.grid-container');
        container.addEventListener('scroll', () => {
            // RequestAnimationFrame garante que o render acompanhe a atualização da tela
            requestAnimationFrame(() => this.renderBody());
        });
        
        // Fechar Context Menu ao clicar fora
        document.addEventListener('click', (e) => {
            if(!this.dom.ctxMenu.contains(e.target)) this.dom.ctxMenu.style.display = 'none';
        });
        
        // Menu Actions
        this.dom.ctxMenu.addEventListener('click', (e) => {
            const li = e.target.closest('li');
            if(li && li.dataset.action) {
                this.executeContextAction(li.dataset.action);
                this.dom.ctxMenu.style.display = 'none';
            }
        });
    },

    // --- API ---
    loadData: async function() {
        this.toggleLoader(true);
        try {
            const ano = this.dom.tbAno.value;
            const mes = this.dom.tbMes.value;
            const res = await fetch(`${API.getDados}?ano=${ano}&mes=${mes}`);
            const json = await res.json();

            if(json.error) throw new Error(json.error);

            this.rawData = json;
            this.applyFilters(); // Isso chamará o render
            this.updateStatus(`${this.rawData.length} registros carregados.`);
        } catch (e) {
            alert("Erro: " + e.message);
            this.updateStatus("Erro ao carregar");
        } finally {
            this.toggleLoader(false);
        }
    },

    // --- RENDERIZAÇÃO ---
    renderHeader: function() {
        let html = '<th class="col-index">#</th>';
        this.columns.forEach(col => {
            html += `
                <th style="width:${col.width}px">
                    <div class="header-content">${col.title}</div>
                    <div class="filter-container">
                        <input type="text" class="filter-input" data-key="${col.key}" placeholder="...">
                    </div>
                </th>`;
        });
        this.dom.tableHead.innerHTML = html;
    },

    // --- RENDERIZAÇÃO OTIMIZADA (Virtual Scrolling) ---
    rowHeight: 22, // Definido no CSS (height: 22px)

    renderBody: function() {
        const container = document.querySelector('.grid-container');
        const scrollTop = container.scrollTop;
        const viewportHeight = container.clientHeight;
        
        // Calcula quais linhas estão visíveis
        const startIndex = Math.floor(scrollTop / this.rowHeight);
        const endIndex = Math.min(this.viewData.length - 1, Math.ceil((scrollTop + viewportHeight) / this.rowHeight));

        // Espaçadores para manter o scrollbar proporcional ao tamanho real dos dados
        const paddingTop = startIndex * this.rowHeight;
        const paddingBottom = (this.viewData.length - endIndex - 1) * this.rowHeight;

        let html = '';
        let tDeb = 0, tCred = 0;

        // Renderiza apenas o pedaço visível
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

        // Aplica o HTML com os paddings de compensação
        this.dom.tableBody.innerHTML = `
            <tr style="height: ${paddingTop}px"><td colspan="${this.columns.length + 1}" style="border:none"></td></tr>
            ${html}
            <tr style="height: ${paddingBottom}px"><td colspan="${this.columns.length + 1}" style="border:none"></td></tr>
        `;

        // Totais sempre calculam sobre o viewData completo (rápido, pois é só math)
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

    // --- FILTRAGEM ---
    handleFilterInput: function(input) {
        const key = input.dataset.key;
        const val = input.value.toLowerCase();
        
        // Debounce: Limpa timeout anterior
        if (this.filterTimeout) clearTimeout(this.filterTimeout);
        
        this.filterTimeout = setTimeout(() => {
            if (!val) delete this.filters[key];
            else this.filters[key] = val;
            
            this.applyFilters();
        }, 300); // Espera 300ms após parar de digitar
    },

    applyFilters: function() {
        const keys = Object.keys(this.filters);
        if (keys.length === 0) {
            this.viewData = [...this.rawData]; // Cópia rasa
        } else {
            this.viewData = this.rawData.filter(row => {
                return keys.every(k => {
                    const cellVal = String(row[k] || '').toLowerCase();
                    return cellVal.includes(this.filters[k]);
                });
            });
        }
        this.renderBody();
        this.updateStatus(`${this.viewData.length} linhas exibidas.`);
    },

    // --- EDIÇÃO (Core Logic) ---
    handleGridClick: function(e) {
        if (this.isEditing) return;

        const td = e.target.closest('td');
        if (!td || td.classList.contains('col-index')) return;

        const tr = td.parentElement;
        const idx = parseInt(tr.dataset.idx);
        const key = td.dataset.key;
        const rowData = this.viewData[idx];

        // Regras de bloqueio
        if (rowData.Invalido) return;
        
        const colDef = this.columns.find(c => c.key === key);
        if (!colDef || colDef.readonly) return;

        // Toggle Booleano direto
        if (colDef.type === 'bool') {
            rowData[key] = !rowData[key];
            this.saveRow(rowData);
            return; // render será chamado no save
        }

        // Entra no modo edição
        this.startEditing(td, idx, key, colDef);
    },

    startEditing: function(td, idx, key, colDef) {
        this.isEditing = true;
        const row = this.viewData[idx];
        const val = row[key];

        // Cria Input
        const input = document.createElement('input');
        input.className = 'cell-editor';
        input.value = (colDef.type === 'date' && val) ? val.split('T')[0] : (val === undefined ? '' : val);
        if (colDef.type === 'money') input.type = 'number';
        
        // Salva HTML anterior para restaurar no ESC
        const oldHtml = td.innerHTML;
        td.innerHTML = '';
        td.appendChild(input);
        input.focus();

        const finish = (save) => {
            if (!this.isEditing) return; // Evita disparo duplo (blur + enter)
            this.isEditing = false;
            
            if (!save) {
                td.innerHTML = oldHtml;
                return;
            }

            let newVal = input.value;
            if (colDef.type === 'money') newVal = parseFloat(newVal) || 0;

            // Se mudou, atualiza e salva
            if (row[key] != newVal) {
                row[key] = newVal;
                // Recalcula saldo na linha localmente para feedback visual rápido
                if(key === 'Debito' || key === 'Credito') {
                    row.Saldo = (parseFloat(row.Debito||0) - parseFloat(row.Credito||0));
                }
                td.innerHTML = '<i class="fas fa-spinner fa-spin"></i>'; // Loading icon na celula
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
            // Payload
            const payload = { ...row }; // Clone
            
            // Define Operação
            let op = 'EDICAO';
            if (row.Tipo_Linha === 'Inclusao' && !row.Ajuste_ID) op = 'INCLUSAO';
            
            const res = await fetch(API.salvar, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    Tipo_Operacao: op,
                    Dados: payload
                })
            });
            const json = await res.json();

            if (json.id) {
                row.Ajuste_ID = json.id;
                if(row.Status_Ajuste === 'Original') row.Status_Ajuste = 'Pendente';
                this.updateStatus("Salvo com sucesso!");
            } else {
                alert("Erro backend: " + JSON.stringify(json));
            }
        } catch (e) {
            console.error(e);
            alert("Erro de conexão ao salvar.");
        } finally {
            this.renderBody(); // Re-renderiza para limpar inputs e atualizar cores
        }
    },

    // --- CONTEXT MENU ---
    handleContextMenu: function(e) {
        e.preventDefault();
        const tr = e.target.closest('tr');
        if (!tr) return;

        const idx = parseInt(tr.dataset.idx);
        this.ctxIndex = idx;
        const row = this.viewData[idx];

        // Seleciona visualmente
        document.querySelectorAll('tr.selected').forEach(r => r.classList.remove('selected'));
        tr.classList.add('selected');

        // Posiciona Menu
        const menu = this.dom.ctxMenu;
        menu.style.display = 'block';
        
        // Ajuste para não sair da tela
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
                // Atualiza Modelo Local
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
        // Adiciona ao início
        this.rawData.unshift(newRow);
        this.applyFilters(); // Re-renderiza
        
        // Scroll para o topo
        document.querySelector('.grid-container').scrollTop = 0;
    },

    gerarIntergrupo: async function() {
        if(!confirm("Deseja gerar os lançamentos intergrupo automaticamente?")) return;
        this.toggleLoader(true);
        try {
            const res = await fetch(API.intergrupo, {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({ ano: this.dom.tbAno.value })
            });
            const json = await res.json();
            alert("Processo concluído! Logs: \n" + json.logs);
            this.loadData();
        } catch(e) { alert("Erro: " + e.message); }
        finally { this.toggleLoader(false); }
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
            try { return new Date(val).toLocaleDateString('pt-BR'); } catch { return val; }
        }
        if (type === 'bool') return val ? 'Sim' : '';
        if (type === 'status') {
             // Retorna ícone baseado no texto
             if (val === 'Aprovado') return '<i class="fas fa-check"></i>';
             if (val === 'Reprovado') return '<i class="fas fa-times"></i>';
             if (val === 'Pendente') return '<i class="fas fa-exclamation"></i>';
             if (val === 'Invalido') return '<i class="fas fa-ban"></i>';
        }
        return val;
    },
    
    formatMoney: (v) => parseFloat(v).toLocaleString('pt-BR', {minimumFractionDigits: 2}),

    toggleLoader: function(show) {
        this.dom.loader.style.display = show ? 'flex' : 'none';
    },

    updateStatus: function(msg) {
        this.dom.status.textContent = msg;
    },

    exportCSV: function() {
        let csv = 'Data;Conta;Descricao;Debito;Credito\n';
        this.viewData.forEach(r => {
            csv += `${r.Data};${r.Conta};${r.Descricao};${r.Debito};${r.Credito}\n`;
        });
        const blob = new Blob([csv], {type: 'text/csv'});
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = 'Razao.csv'; a.click();
    }
};

document.addEventListener('DOMContentLoaded', () => ExcelGrid.init());