// ============================================================================
// T-Controllership | MÓDULO DE AJUSTES RAZÃO
// Versão: 2.2 - Correção Modal Histórico (Class Active)
// ============================================================================

if (typeof window.ajustesSystemInitialized === 'undefined') {
    window.ajustesSystemInitialized = true;

    class AjustesSystem {
        constructor() {
            this.table = null;
            this.modal = document.getElementById('modalAjuste');
            this.modalHistorico = document.getElementById('modalHistorico');
            this.init();
        }

        init() {
            document.addEventListener('DOMContentLoaded', () => {
                this.initTable();
                this.loadData();
            });
            
            // --- EVENTOS GERAIS ---
            
            // ESC fecha modais
            document.addEventListener('keydown', (e) => {
                if (e.key === "Escape") {
                    this.closeModal();
                    this.closeHistoryModal();
                }
            });
            
            // Click fora do modal fecha (Edição)
            document.getElementById('modalAjuste')?.addEventListener('click', (e) => {
                if (e.target.classList.contains('modal-overlay')) {
                    this.closeModal();
                }
            });

            // Click fora do modal fecha (Histórico)
            document.getElementById('modalHistorico')?.addEventListener('click', (e) => {
                if (e.target.classList.contains('modal-overlay')) {
                    this.closeHistoryModal();
                }
            });
        }

        // =====================================================================
        // UTILIDADE: Formatação de Datas
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
        // TABULATOR INIT
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
                
                rowFormatter: (row) => {
                    const d = row.getData();
                    const el = row.getElement();
                    el.classList.remove("row-inclusao", "st-pendente", "st-aprovado", "st-reprovado");
                    if (d.Tipo_Linha === "Inclusao") el.classList.add("row-inclusao");
                    if (d.Status_Ajuste) el.classList.add("st-" + d.Status_Ajuste.toLowerCase());
                },

                columns: [
                    // Ações
                    {
                        title: "Ações",
                        field: "actions",
                        frozen: true,
                        width: 140,
                        hozAlign: "center",
                        headerSort: false,
                        formatter: (cell) => {
                            const d = cell.getRow().getData();
                            let html = `
                                <i class="fas fa-pencil-alt action-btn btn-edit" 
                                   onclick="ajustesSystem.editRow('${d.Hash_ID}')" 
                                   title="Editar"></i>
                            `;
                            
                            if (d.Status_Ajuste === 'Pendente') {
                                html += `
                                    <i class="fas fa-check action-btn btn-ok" 
                                       onclick="ajustesSystem.approve('${d.Ajuste_ID}', 'Aprovar')" 
                                       title="Aprovar"></i>
                                    <i class="fas fa-times action-btn btn-no" 
                                       onclick="ajustesSystem.approve('${d.Ajuste_ID}', 'Reprovar')" 
                                       title="Reprovar"></i>
                                `;
                            }

                            if (d.Ajuste_ID) {
                                html += `
                                    <i class="fas fa-history action-btn btn-hist" 
                                       style="color: #666; margin-left: 10px;"
                                       onclick="ajustesSystem.openHistoryModal('${d.Ajuste_ID}')" 
                                       title="Ver Histórico"></i>
                                `;
                            }
                            return html;
                        }
                    },
                    {
                        title: "Status",
                        field: "Status_Ajuste",
                        frozen: true,
                        width: 120,
                        hozAlign: "center",
                        formatter: (cell) => {
                            const val = cell.getValue();
                            if (!val) return '<span class="status-badge status-original">Original</span>';
                            const cls = `status-${val.toLowerCase()}`;
                            return `<span class="status-badge ${cls}">${val}</span>`;
                        }
                    },
                    { title: "Data", field: "Data", width: 110, hozAlign: "center", sorter: "date", sorterParams: { format: "yyyy-MM-dd" }, formatter: (cell) => self.formatDateDisplay(cell.getValue()) },
                    { title: "Conta", field: "Conta", width: 130, headerFilter: "input" },
                    { title: "Título Conta", field: "Título Conta", width: 200 },
                    { title: "Número", field: "Numero", width: 140 },
                    { title: "Descrição", field: "Descricao", width: 280, headerFilter: "input" },
                    { title: "Contra Partida", field: "Contra Partida - Credito", width: 140 },
                    { title: "Filial", field: "Filial", width: 80, hozAlign: "center" },
                    { title: "C. Custo", field: "Centro de Custo", width: 130 },
                    { title: "Item", field: "Item", width: 100 },
                    { title: "Cód. Cl.", field: "Cod Cl. Valor", width: 90 },
                    {
                        title: "Débito", field: "Debito", width: 120, hozAlign: "right", formatter: "money", formatterParams: { decimal: ",", thousand: ".", precision: 2 }, bottomCalc: "sum", bottomCalcFormatter: "money", bottomCalcFormatterParams: { decimal: ",", thousand: ".", precision: 2 }
                    },
                    {
                        title: "Crédito", field: "Credito", width: 120, hozAlign: "right", formatter: "money", formatterParams: { decimal: ",", thousand: ".", precision: 2 }, bottomCalc: "sum", bottomCalcFormatter: "money", bottomCalcFormatterParams: { decimal: ",", thousand: ".", precision: 2 }
                    },
                    {
                        title: "Saldo", field: "Saldo", width: 120, hozAlign: "right", bottomCalc: "sum",
                        formatter: (cell) => {
                            const val = cell.getValue();
                            if (val == null) return '<span style="color: #999;">-</span>';
                            const num = parseFloat(val);
                            const color = num < 0 ? 'var(--ar-danger, #ef4444)' : 'var(--ar-info, #3b82f6)';
                            return `<span style="color: ${color}; font-weight: 600;">${num.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span>`;
                        },
                        bottomCalcFormatter: (cell) => {
                             const val = cell.getValue();
                             if (!val) return '-';
                             return `<span style="font-weight: 700;">${parseFloat(val).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span>`;
                        }
                    },
                    { title: "Ñ.Op", field: "NaoOperacional", width: 70, hozAlign: "center", formatter: "tickCross", formatterParams: { allowEmpty: true, tickElement: '<i class="fas fa-check" style="color: var(--ar-warning, #f59e0b);"></i>', crossElement: '' } }
                ]
            });
        }

        // =====================================================================
        // DATA LOADING
        // =====================================================================
        async loadData() {
            try {
                const res = await fetch(API_ROUTES.getDados);
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();
                data.forEach((d, i) => { if (!d.Hash_ID) d.Hash_ID = "TMP_" + i + "_" + Date.now(); });
                this.table.replaceData(data);
            } catch (e) {
                console.error('Erro ao carregar dados:', e);
                this.table.alert("Erro ao carregar dados.", "error");
            }
        }

        // =====================================================================
        // MODAL EDICAO / CRIACAO
        // =====================================================================
        showModal(show) {
            if (!this.modal) return;
            if (show) {
                this.modal.classList.add('active'); // O segredo está aqui: classe .active
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

        // =====================================================================
        // HISTÓRICO DE AUDITORIA (CORRIGIDO)
        // =====================================================================
        async openHistoryModal(idAjuste) {
            if (!this.modalHistorico) return;
            const tbody = document.getElementById('tbodyHistorico');
            
            // CORREÇÃO: Usar classList 'active' ao invés de display
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
            if (this.modalHistorico) {
                this.modalHistorico.classList.remove('active'); // CORREÇÃO
            }
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
    
    // CSS dinâmico para animações se necessário
    if (!document.getElementById('ar-styles-dyn')) {
        const style = document.createElement('style');
        style.id = 'ar-styles-dyn';
        style.textContent = `@keyframes toastSlide { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }`;
        document.head.appendChild(style);
    }
}