(function () {
    const app = document.getElementById('budget-track-app');
    if (!app) {
        return;
    }

    const parseJson = (id) => {
        const element = document.getElementById(id);
        if (!element) {
            return null;
        }

        try {
            return JSON.parse(element.textContent || 'null');
        } catch (error) {
            return null;
        }
    };

    const gestor = parseJson('budget-track-gestor');
    const centrosCusto = Array.isArray(parseJson('budget-track-centros')) ? parseJson('budget-track-centros') : [];
    const yearSelect = document.getElementById('budget-track-year');
    const centerField = document.getElementById('budget-track-center');
    const generateBtn = document.getElementById('budget-track-generate-btn');
    const statusBox = document.getElementById('budget-track-status');
    const accountsField = document.getElementById('budget-track-accounts-field');
    const accountsToggle = document.getElementById('budget-track-accounts-toggle');
    const accountsLabel = document.getElementById('budget-track-accounts-label');
    const accountsPanel = document.getElementById('budget-track-accounts-panel');
    const accountsSearch = document.getElementById('budget-track-accounts-search');
    const accountsOptions = document.getElementById('budget-track-accounts-options');
    const accountsEmpty = document.getElementById('budget-track-accounts-empty');
    const accountsSelectAll = document.getElementById('budget-track-accounts-select-all');
    const accountsSelectAllWrap = document.getElementById('budget-track-accounts-select-all-wrap');
    const filtersUrl = app.dataset.filtersUrl || '';
    const generateBtnLabel = generateBtn ? generateBtn.querySelector('span') : null;
    const defaultButtonLabel = generateBtnLabel ? generateBtnLabel.textContent : '';
    const accountFilterState = {
        items: [],
        selectedIds: new Set(),
        loading: false,
        requestId: 0,
    };

    if (!generateBtn) {
        return;
    }

    function normalizarTexto(value) {
        return String(value || '')
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase();
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function setStatus(message, type) {
        statusBox.textContent = message;
        statusBox.className = 'luft-budget-track-status is-visible';
        if (type) {
            statusBox.classList.add(`is-${type}`);
        }
    }

    function clearStatus() {
        statusBox.textContent = '';
        statusBox.className = 'luft-budget-track-status';
    }

    function obterCodigoCentroSelecionado() {
        if (!centerField) {
            return '';
        }

        return centerField.value || '';
    }

    function obterNomeConta(item) {
        return String(item?.descricao || item?.nome || item?.id || '').trim();
    }

    function fecharContasContabeis() {
        if (!accountsToggle || !accountsPanel) {
            return;
        }

        accountsToggle.setAttribute('aria-expanded', 'false');
        accountsPanel.classList.add('luft-budget-track-hidden');
    }

    function atualizarResumoContas() {
        if (!accountsToggle || !accountsLabel) {
            return;
        }

        const codigoCentroCusto = obterCodigoCentroSelecionado();
        const totalContas = accountFilterState.items.length;
        const totalSelecionadas = accountFilterState.selectedIds.size;

        accountsToggle.disabled = !codigoCentroCusto || accountFilterState.loading;

        if (!codigoCentroCusto) {
            accountsLabel.textContent = 'Selecione o centro de custo';
            return;
        }

        if (accountFilterState.loading) {
            accountsLabel.textContent = 'Carregando contas...';
            return;
        }

        if (totalContas === 0) {
            accountsLabel.textContent = 'Nenhuma conta disponivel';
            return;
        }

        if (totalSelecionadas === totalContas) {
            accountsLabel.textContent = 'Todas as contas';
            return;
        }

        if (totalSelecionadas === 0) {
            accountsLabel.textContent = 'Nenhuma conta selecionada';
            return;
        }

        if (totalSelecionadas === 1) {
            const contaSelecionada = accountFilterState.items.find((item) => accountFilterState.selectedIds.has(item.id));
            accountsLabel.textContent = contaSelecionada ? obterNomeConta(contaSelecionada) : '1 conta selecionada';
            return;
        }

        accountsLabel.textContent = `${totalSelecionadas} contas selecionadas`;
    }

    function atualizarSelectAllContas() {
        if (!accountsSelectAll) {
            return;
        }

        const totalContas = accountFilterState.items.length;
        const totalSelecionadas = accountFilterState.selectedIds.size;

        accountsSelectAll.checked = totalContas > 0 && totalSelecionadas === totalContas;
        accountsSelectAll.indeterminate = totalSelecionadas > 0 && totalSelecionadas < totalContas;
        accountsSelectAll.disabled = totalContas === 0;

        if (accountsSelectAllWrap) {
            accountsSelectAllWrap.classList.toggle('luft-budget-track-hidden', totalContas === 0);
        }
    }

    function renderizarContasContabeis() {
        if (!accountsOptions || !accountsEmpty) {
            return;
        }

        const termoBusca = normalizarTexto(accountsSearch ? accountsSearch.value : '');
        const opcoes = accountFilterState.items.filter((item) => {
            const textoBusca = normalizarTexto(`${item.codigo || ''} ${item.descricao || ''} ${item.nome || ''}`);
            return !termoBusca || textoBusca.includes(termoBusca);
        });

        accountsOptions.innerHTML = opcoes.map((item) => {
            const selecionado = accountFilterState.selectedIds.has(item.id);
            return `
                <label class="luft-budget-track-multiselect-option ${selecionado ? 'is-selected' : ''}" data-id="${escapeHtml(item.id)}">
                    <input type="checkbox" value="${escapeHtml(item.id)}" ${selecionado ? 'checked' : ''}>
                    <span>${escapeHtml(obterNomeConta(item))}</span>
                </label>
            `;
        }).join('');

        if (!obterCodigoCentroSelecionado()) {
            accountsEmpty.textContent = 'Selecione o centro de custo para carregar as contas.';
            accountsEmpty.classList.remove('is-hidden');
        } else if (accountFilterState.loading) {
            accountsEmpty.textContent = 'Carregando contas contabeis...';
            accountsEmpty.classList.remove('is-hidden');
        } else if (accountFilterState.items.length === 0) {
            accountsEmpty.textContent = 'Nenhuma conta contabil disponivel para o centro selecionado.';
            accountsEmpty.classList.remove('is-hidden');
        } else if (opcoes.length === 0) {
            accountsEmpty.textContent = 'Nenhuma conta encontrada para a pesquisa informada.';
            accountsEmpty.classList.remove('is-hidden');
        } else {
            accountsEmpty.classList.add('is-hidden');
        }

        atualizarSelectAllContas();
        atualizarResumoContas();
    }

    async function carregarContasContabeis() {
        if (!accountsOptions || !filtersUrl) {
            return;
        }

        const codigoCentroCusto = obterCodigoCentroSelecionado();
        const ano = yearSelect ? yearSelect.value : '';
        const requestId = ++accountFilterState.requestId;

        if (accountsSearch) {
            accountsSearch.value = '';
        }

        fecharContasContabeis();

        if (!codigoCentroCusto) {
            accountFilterState.items = [];
            accountFilterState.selectedIds = new Set();
            accountFilterState.loading = false;
            renderizarContasContabeis();
            return;
        }

        accountFilterState.loading = true;
        renderizarContasContabeis();

        try {
            const url = new URL(filtersUrl, window.location.origin);
            url.searchParams.set('ano', ano || new Date().getFullYear());
            url.searchParams.set('empresa', 'Todos');
            url.searchParams.set('centro_custo', codigoCentroCusto);
            url.searchParams.set('conta_contabil', 'Todos');

            const response = await fetch(url.toString(), {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });

            const payload = await response.json();
            if (requestId !== accountFilterState.requestId) {
                return;
            }

            if (!response.ok || payload.status !== 'success') {
                throw new Error(payload.message || payload.error || 'Falha ao carregar as contas contabeis.');
            }

            const contas = Array.isArray(payload.data?.contasContabeis) ? payload.data.contasContabeis : [];
            accountFilterState.items = contas.map((item) => ({
                id: String(item.id),
                codigo: item.codigo,
                descricao: item.descricao || item.nome || item.id,
                nome: item.nome || item.descricao || item.id,
            }));
            accountFilterState.selectedIds = new Set(accountFilterState.items.map((item) => item.id));
        } catch (error) {
            if (requestId !== accountFilterState.requestId) {
                return;
            }

            accountFilterState.items = [];
            accountFilterState.selectedIds = new Set();
            setStatus(error.message || 'Falha ao carregar as contas contabeis.', 'error');
        } finally {
            if (requestId === accountFilterState.requestId) {
                accountFilterState.loading = false;
                renderizarContasContabeis();
            }
        }
    }

    function obterContasContabeisSelecionadas() {
        return Array.from(accountFilterState.selectedIds);
    }

    async function gerarPlanilha() {
        const ano = yearSelect ? yearSelect.value : '';
        const codigoCentroCusto = obterCodigoCentroSelecionado();
        const contasContabeis = obterContasContabeisSelecionadas();

        if (!gestor) {
            setStatus('Seu usuario nao possui configuracao de gestor para essa rotina.', 'error');
            return;
        }

        if (centrosCusto.length > 1 && !codigoCentroCusto) {
            setStatus('Selecione o centro de custo para gerar a planilha.', 'error');
            return;
        }

        if (accountFilterState.loading) {
            setStatus('Aguarde o carregamento das contas contabeis.', 'info');
            return;
        }

        if (accountFilterState.items.length > 0 && contasContabeis.length === 0) {
            setStatus('Selecione ao menos uma conta contabil para gerar a planilha.', 'error');
            return;
        }

        generateBtn.disabled = true;
        if (generateBtnLabel) {
            generateBtnLabel.textContent = 'Gerando...';
        }
        clearStatus();
        setStatus('Gerando arquivo e preparando download...', 'info');

        try {
            const response = await fetch(app.dataset.generateUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({
                    ano,
                    codigoCentroCusto,
                    contasContabeis,
                }),
            });

            const payload = await response.json();
            if (!response.ok || payload.status !== 'success') {
                throw new Error(payload.message || payload.error || 'Falha ao gerar a planilha.');
            }

            const data = payload.data || {};
            if (!data.downloadUrl) {
                throw new Error('Arquivo gerado sem link de download.');
            }

            setStatus(payload.message || 'Planilha gerada com sucesso. O download foi iniciado.', 'success');
            window.location.assign(data.downloadUrl);
        } catch (error) {
            setStatus(error.message || 'Falha ao gerar a planilha.', 'error');
        } finally {
            generateBtn.disabled = false;
            if (generateBtnLabel) {
                generateBtnLabel.textContent = defaultButtonLabel || 'Gerar planilha';
            }
        }
    }

    if (accountsToggle && accountsPanel) {
        accountsToggle.addEventListener('click', () => {
            if (accountsToggle.disabled) {
                return;
            }

            const aberto = accountsToggle.getAttribute('aria-expanded') === 'true';
            accountsToggle.setAttribute('aria-expanded', aberto ? 'false' : 'true');
            accountsPanel.classList.toggle('luft-budget-track-hidden', aberto);

            if (!aberto && accountsSearch) {
                accountsSearch.focus();
            }
        });
    }

    if (accountsSearch) {
        accountsSearch.addEventListener('input', renderizarContasContabeis);
    }

    if (accountsSelectAll) {
        accountsSelectAll.addEventListener('change', () => {
            accountFilterState.selectedIds = accountsSelectAll.checked
                ? new Set(accountFilterState.items.map((item) => item.id))
                : new Set();
            renderizarContasContabeis();
        });
    }

    if (accountsOptions) {
        accountsOptions.addEventListener('change', (event) => {
            const checkbox = event.target.closest('input[type="checkbox"]');
            if (!checkbox) {
                return;
            }

            if (checkbox.checked) {
                accountFilterState.selectedIds.add(String(checkbox.value));
            } else {
                accountFilterState.selectedIds.delete(String(checkbox.value));
            }

            renderizarContasContabeis();
        });
    }

    document.addEventListener('click', (event) => {
        if (!accountsField || accountsField.contains(event.target)) {
            return;
        }

        fecharContasContabeis();
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            fecharContasContabeis();
        }
    });

    if (yearSelect) {
        yearSelect.addEventListener('change', () => {
            clearStatus();
            carregarContasContabeis();
        });
    }

    if (centerField) {
        centerField.addEventListener('change', () => {
            clearStatus();
            carregarContasContabeis();
        });
    }

    carregarContasContabeis();
    generateBtn.addEventListener('click', gerarPlanilha);
})();