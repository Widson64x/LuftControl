// ============================================================================
// T-Controllership | MÓDULO DE AJUSTES RAZÃO
// Versão: 2.0 - Data Fix + Improvements
// ============================================================================

if (typeof window.ajustesSystemInitialized === 'undefined') {
    window.ajustesSystemInitialized = true;

    class AjustesSystem {
        constructor() {
            this.table = null;
            this.modal = document.getElementById('modalAjuste');
            this.init();
        }

        init() {
            document.addEventListener('DOMContentLoaded', () => {
                this.initTable();
                this.loadData();
            });
            
            // ESC fecha modal
            document.addEventListener('keydown', (e) => {
                if (e.key === "Escape") this.closeModal();
            });
            
            // Click fora do modal fecha
            document.getElementById('modalAjuste')?.addEventListener('click', (e) => {
                if (e.target.classList.contains('modal-overlay')) {
                    this.closeModal();
                }
            });
        }

        // =====================================================================
        // UTILIDADE: Formatação de Datas (CORREÇÃO DEFINITIVA)
        // =====================================================================
        
        /**
         * Converte qualquer formato de data para DD/MM/YYYY (exibição)
         * Aceita: ISO strings, Date objects, timestamps, strings formatadas
         */
        formatDateDisplay(value) {
            if (!value) return '-';
            
            try {
                let dateStr = String(value);
                
                // Se já está no formato DD/MM/YYYY, retorna
                if (/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) {
                    return dateStr;
                }
                
                // Remove timezone info e horário se existir
                // Exemplos: "2025-01-02T00:00:00.000Z", "Thu, 02 Jan 2025 00:00:00 GMT"
                
                // Tenta extrair YYYY-MM-DD de strings ISO
                const isoMatch = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})/);
                if (isoMatch) {
                    return `${isoMatch[3]}/${isoMatch[2]}/${isoMatch[1]}`;
                }
                
                // Tenta parsear como Date (para formatos como "Thu, 02 Jan 2025 00:00:00 GMT")
                const parsed = new Date(dateStr);
                if (!isNaN(parsed.getTime())) {
                    const day = String(parsed.getUTCDate()).padStart(2, '0');
                    const month = String(parsed.getUTCMonth() + 1).padStart(2, '0');
                    const year = parsed.getUTCFullYear();
                    return `${day}/${month}/${year}`;
                }
                
                return dateStr; // Fallback: retorna original
            } catch (e) {
                console.warn('Erro ao formatar data:', value, e);
                return String(value);
            }
        }
        
        /**
         * Converte qualquer formato de data para YYYY-MM-DD (input type="date")
         */
        formatDateInput(value) {
            if (!value) return '';
            
            try {
                let dateStr = String(value);
                
                // Se já está no formato YYYY-MM-DD, retorna
                if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
                    return dateStr;
                }
                
                // Extrai YYYY-MM-DD de ISO string
                const isoMatch = dateStr.match(/^(\d{4}-\d{2}-\d{2})/);
                if (isoMatch) {
                    return isoMatch[1];
                }
                
                // Tenta parsear como Date
                const parsed = new Date(dateStr);
                if (!isNaN(parsed.getTime())) {
                    const year = parsed.getUTCFullYear();
                    const month = String(parsed.getUTCMonth() + 1).padStart(2, '0');
                    const day = String(parsed.getUTCDate()).padStart(2, '0');
                    return `${year}-${month}-${day}`;
                }
                
                return ''; // Fallback: vazio
            } catch (e) {
                console.warn('Erro ao converter data para input:', value, e);
                return '';
            }
        }

        // =====================================================================
        // TABULATOR INIT
        // =====================================================================
        
        initTable() {
            if (typeof Tabulator === 'undefined') {
                console.error('Tabulator não carregado');
                return;
            }

            const self = this; // Referência para usar nos formatters

            this.table = new Tabulator("#gridAjustes", {
                layout: "fitData",
                height: "100%",
                placeholder: `
                    <div style="text-align:center; padding:40px; color: var(--ar-text-muted, #6e7681);">
                        <i class="fas fa-database" style="font-size: 2rem; margin-bottom: 10px; display: block; opacity: 0.5;"></i>
                        Carregando dados...
                    </div>
                `,
                reactiveData: true,
                index: "Hash_ID",
                
                rowFormatter: (row) => {
                    const d = row.getData();
                    const el = row.getElement();
                    
                    // Remove classes anteriores
                    el.classList.remove("row-inclusao", "st-pendente", "st-aprovado", "st-reprovado");
                    
                    // Aplica classes por tipo/status
                    if (d.Tipo_Linha === "Inclusao") {
                        el.classList.add("row-inclusao");
                    }
                    if (d.Status_Ajuste) {
                        el.classList.add("st-" + d.Status_Ajuste.toLowerCase());
                    }
                },

                columns: [
                    // Ações
                    {
                        title: "Ações",
                        field: "actions",
                        frozen: true,
                        width: 110,
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
                            return html;
                        }
                    },

                    // Status
                    {
                        title: "Status",
                        field: "Status_Ajuste",
                        frozen: true,
                        width: 120,
                        hozAlign: "center",
                        formatter: (cell) => {
                            const val = cell.getValue();
                            if (!val) return '<span class="status-badge status-original">Original</span>';
                            
                            const classes = {
                                'Pendente': 'status-pendente',
                                'Aprovado': 'status-aprovado',
                                'Reprovado': 'status-reprovado'
                            };
                            
                            const cls = classes[val] || 'status-original';
                            return `<span class="status-badge ${cls}">${val}</span>`;
                        }
                    },

                    // Data (CORRIGIDO)
                    {
                        title: "Data",
                        field: "Data",
                        width: 110,
                        hozAlign: "center",
                        sorter: "date",
                        sorterParams: { format: "yyyy-MM-dd" },
                        formatter: (cell) => {
                            return self.formatDateDisplay(cell.getValue());
                        }
                    },

                    // Conta
                    {
                        title: "Conta",
                        field: "Conta",
                        width: 130,
                        headerFilter: "input"
                    },

                    // Título Conta
                    {
                        title: "Título Conta",
                        field: "Título Conta",
                        width: 200
                    },

                    // Número
                    {
                        title: "Número",
                        field: "Numero",
                        width: 140
                    },

                    // Descrição
                    {
                        title: "Descrição",
                        field: "Descricao",
                        width: 280,
                        headerFilter: "input"
                    },

                    // Contra Partida
                    {
                        title: "Contra Partida",
                        field: "Contra Partida - Credito",
                        width: 140
                    },

                    // Filial
                    {
                        title: "Filial",
                        field: "Filial",
                        width: 80,
                        hozAlign: "center"
                    },

                    // Centro de Custo
                    {
                        title: "C. Custo",
                        field: "Centro de Custo",
                        width: 130
                    },

                    // Item
                    {
                        title: "Item",
                        field: "Item",
                        width: 100
                    },

                    // Código Classificação
                    {
                        title: "Cód. Cl.",
                        field: "Cod Cl. Valor",
                        width: 90
                    },

                    // Débito
                    {
                        title: "Débito",
                        field: "Debito",
                        width: 120,
                        hozAlign: "right",
                        formatter: "money",
                        formatterParams: {
                            decimal: ",",
                            thousand: ".",
                            symbol: "",
                            precision: 2
                        },
                        bottomCalc: "sum",
                        bottomCalcFormatter: "money",
                        bottomCalcFormatterParams: {
                            decimal: ",",
                            thousand: ".",
                            symbol: "",
                            precision: 2
                        }
                    },

                    // Crédito
                    {
                        title: "Crédito",
                        field: "Credito",
                        width: 120,
                        hozAlign: "right",
                        formatter: "money",
                        formatterParams: {
                            decimal: ",",
                            thousand: ".",
                            symbol: "",
                            precision: 2
                        },
                        bottomCalc: "sum",
                        bottomCalcFormatter: "money",
                        bottomCalcFormatterParams: {
                            decimal: ",",
                            thousand: ".",
                            symbol: "",
                            precision: 2
                        }
                    },

                    // Saldo
                    {
                        title: "Saldo",
                        field: "Saldo",
                        width: 120,
                        hozAlign: "right",
                        bottomCalc: "sum",
                        formatter: (cell) => {
                            const val = cell.getValue();
                            if (val === null || val === undefined) {
                                return '<span style="color: var(--ar-text-muted, #6e7681);">-</span>';
                            }
                            
                            const num = parseFloat(val);
                            const color = num < 0 ? 'var(--ar-danger, #ef4444)' : 'var(--ar-info, #3b82f6)';
                            const formatted = num.toLocaleString('pt-BR', {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2
                            });
                            
                            return `<span style="color: ${color}; font-weight: 600;">${formatted}</span>`;
                        },
                        bottomCalcFormatter: (cell) => {
                            const val = cell.getValue();
                            if (!val) return '-';
                            const num = parseFloat(val);
                            const color = num < 0 ? 'var(--ar-danger, #ef4444)' : 'var(--ar-info, #3b82f6)';
                            return `<span style="color: ${color}; font-weight: 700;">${num.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>`;
                        }
                    },

                    // Não Operacional
                    {
                        title: "Ñ.Op",
                        field: "NaoOperacional",
                        width: 70,
                        hozAlign: "center",
                        formatter: "tickCross",
                        formatterParams: {
                            allowEmpty: true,
                            tickElement: '<i class="fas fa-check" style="color: var(--ar-warning, #f59e0b);"></i>',
                            crossElement: ''
                        }
                    }
                ]
            });
        }

        // =====================================================================
        // DATA LOADING
        // =====================================================================
        
        async loadData() {
            try {
                const res = await fetch(API_ROUTES.getDados);
                
                if (!res.ok) {
                    throw new Error(`HTTP ${res.status}`);
                }
                
                const data = await res.json();
                
                // Garante Hash_ID único
                data.forEach((d, i) => {
                    if (!d.Hash_ID) {
                        d.Hash_ID = "TMP_" + i + "_" + Date.now();
                    }
                });
                
                this.table.replaceData(data);
                
            } catch (e) {
                console.error('Erro ao carregar dados:', e);
                this.table.alert("Erro ao carregar dados. Verifique a conexão.", "error");
            }
        }

        // =====================================================================
        // MODAL HANDLING
        // =====================================================================
        
        showModal(show) {
            const modal = document.getElementById('modalAjuste');
            if (!modal) return;
            
            if (show) {
                modal.classList.add('active');
                document.body.style.overflow = 'hidden'; // Prevent scroll
                
                // Focus no primeiro input após animação
                setTimeout(() => {
                    const firstInput = modal.querySelector('input:not([type="hidden"]):not([disabled])');
                    if (firstInput) firstInput.focus();
                }, 100);
            } else {
                modal.classList.remove('active');
                document.body.style.overflow = '';
            }
        }

        closeModal() {
            this.showModal(false);
        }

        resetForm() {
            const form = document.getElementById('formAjuste');
            if (form) form.reset();
            
            document.getElementById('inpHashId').value = '';
            document.getElementById('inpAjusteId').value = '';
            document.getElementById('inpTipoOperacao').value = '';
        }

        // =====================================================================
        // EDIT ROW
        // =====================================================================
        
        editRow(hashId) {
            const d = this.table.getData().find(r => r.Hash_ID == hashId);
            if (!d) {
                console.warn('Registro não encontrado:', hashId);
                return;
            }

            const isNew = d.Tipo_Linha === 'Inclusao';
            document.getElementById('modalTitleText').innerText = isNew ? "Editar Inclusão" : "Editar Original";

            // IDs Ocultos
            document.getElementById('inpHashId').value = d.Hash_ID;
            document.getElementById('inpAjusteId').value = d.Ajuste_ID || '';
            document.getElementById('inpTipoOperacao').value = isNew ? 'INCLUSAO' : 'EDICAO';

            // Data (CORRIGIDO) - Usa função de conversão
            document.getElementById('inpData').value = this.formatDateInput(d.Data);

            // Campos de texto
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
            
            // Valores monetários
            document.getElementById('inpDebito').value = d.Debito || '';
            document.getElementById('inpCredito').value = d.Credito || '';

            // Booleans
            document.getElementById('inpNaoOperacional').checked = !!d.NaoOperacional;
            document.getElementById('inpExibirSaldo').checked = d.Exibir_Saldo !== false;

            this.showModal(true);
        }

        // =====================================================================
        // NEW ENTRY
        // =====================================================================
        
        openModalInclusao() {
            this.resetForm();
            
            document.getElementById('modalTitleText').innerText = "Novo Lançamento";
            document.getElementById('inpTipoOperacao').value = 'INCLUSAO';
            
            // Data default: hoje (formato YYYY-MM-DD)
            const today = new Date();
            const yyyy = today.getFullYear();
            const mm = String(today.getMonth() + 1).padStart(2, '0');
            const dd = String(today.getDate()).padStart(2, '0');
            document.getElementById('inpData').value = `${yyyy}-${mm}-${dd}`;
            
            // Defaults
            document.getElementById('inpOrigem').value = 'MANUAL';
            document.getElementById('inpExibirSaldo').checked = true;
            document.getElementById('inpNaoOperacional').checked = false;
            
            this.showModal(true);
        }

        // =====================================================================
        // SAVE
        // =====================================================================
        
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
                    this.showToast('Dados salvos com sucesso!', 'success');
                } else {
                    const err = await res.json().catch(() => ({}));
                    throw new Error(err.message || 'Erro ao salvar');
                }
            } catch (e) {
                console.error('Erro ao salvar:', e);
                this.showToast(e.message || 'Erro de conexão', 'error');
            } finally {
                btn.innerHTML = originalHtml;
                btn.disabled = false;
            }
        }

        // =====================================================================
        // APPROVE / REJECT
        // =====================================================================
        
        async approve(id, action) {
            if (!id) {
                console.warn('ID de ajuste não fornecido');
                return;
            }
            
            const actionText = action === 'Aprovar' ? 'aprovar' : 'reprovar';
            if (!confirm(`Deseja ${actionText} este ajuste?`)) return;

            try {
                const res = await fetch(API_ROUTES.postAprovar, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ Ajuste_ID: id, Acao: action })
                });

                if (res.ok) {
                    this.loadData();
                    this.showToast(`Ajuste ${action === 'Aprovar' ? 'aprovado' : 'reprovado'}!`, 
                                   action === 'Aprovar' ? 'success' : 'warning');
                } else {
                    throw new Error('Falha na operação');
                }
            } catch (e) {
                console.error('Erro na aprovação:', e);
                this.showToast('Erro ao processar aprovação', 'error');
            }
        }

        // =====================================================================
        // TOAST NOTIFICATIONS (bonus)
        // =====================================================================
        
        showToast(message, type = 'info') {
            // Remove toast anterior se existir
            const existing = document.querySelector('.ar-toast');
            if (existing) existing.remove();
            
            const toast = document.createElement('div');
            toast.className = `ar-toast ar-toast-${type}`;
            toast.innerHTML = `
                <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
                <span>${message}</span>
            `;
            
            // Estilos inline (ou adicione no CSS)
            Object.assign(toast.style, {
                position: 'fixed',
                bottom: '24px',
                right: '24px',
                padding: '14px 20px',
                borderRadius: '10px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                fontSize: '14px',
                fontWeight: '500',
                zIndex: '999999',
                animation: 'toastSlide 0.3s ease-out',
                background: type === 'success' ? 'var(--ar-success, #10b981)' : 
                           type === 'error' ? 'var(--ar-danger, #ef4444)' : 
                           'var(--ar-info, #3b82f6)',
                color: 'white',
                boxShadow: '0 4px 20px rgba(0,0,0,0.3)'
            });
            
            document.body.appendChild(toast);
            
            // Remove após 3s
            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(100%)';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
    }

    // Instância global
    window.ajustesSystem = new AjustesSystem();
    
    // Animação do toast (adiciona ao head)
    if (!document.getElementById('ar-toast-styles')) {
        const style = document.createElement('style');
        style.id = 'ar-toast-styles';
        style.textContent = `
            @keyframes toastSlide {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
        `;
        document.head.appendChild(style);
    }
}