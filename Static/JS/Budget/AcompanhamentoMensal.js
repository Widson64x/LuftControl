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
    const downloadBtn = document.getElementById('budget-track-download-btn');
    const statusBox = document.getElementById('budget-track-status');
    const resultCard = document.getElementById('budget-track-result');
    const resultGrid = document.getElementById('budget-track-result-grid');

    if (!generateBtn) {
        return;
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
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

    function renderResultado(data) {
        resultGrid.innerHTML = `
            <div class="luft-budget-track-result-item">
                <strong>Arquivo</strong>
                <span>${escapeHtml(data.nomeArquivo)}</span>
            </div>
            <div class="luft-budget-track-result-item">
                <strong>Ano</strong>
                <span>${escapeHtml(String(data.ano))}</span>
            </div>
            <div class="luft-budget-track-result-item">
                <strong>Centro de custo</strong>
                <span>${escapeHtml(`${data.centroCusto.numero} - ${data.centroCusto.nome}`)}</span>
            </div>
            <div class="luft-budget-track-result-item">
                <strong>Gerado em</strong>
                <span>${escapeHtml(data.geradoEm)}</span>
            </div>
        `;

        downloadBtn.href = data.downloadUrl;
        downloadBtn.hidden = false;
        resultCard.classList.add('is-visible');
    }

    async function gerarPlanilha() {
        const ano = yearSelect ? yearSelect.value : '';
        const codigoCentroCusto = obterCodigoCentroSelecionado();

        if (!gestor) {
            setStatus('Seu usuario nao possui configuracao de gestor para essa rotina.', 'error');
            return;
        }

        if (centrosCusto.length > 1 && !codigoCentroCusto) {
            setStatus('Selecione o centro de custo para gerar a planilha.', 'error');
            return;
        }

        generateBtn.disabled = true;
        clearStatus();
        setStatus('Gerando a planilha de acompanhamento mensal...', 'info');

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
                }),
            });

            const payload = await response.json();
            if (!response.ok || payload.status !== 'success') {
                throw new Error(payload.message || payload.error || 'Falha ao gerar a planilha.');
            }

            const data = payload.data || {};
            renderResultado(data);
            setStatus(payload.message || 'Planilha gerada com sucesso. O download sera iniciado.', 'success');
            window.location.href = data.downloadUrl;
        } catch (error) {
            setStatus(error.message || 'Falha ao gerar a planilha.', 'error');
        } finally {
            generateBtn.disabled = false;
        }
    }

    generateBtn.addEventListener('click', gerarPlanilha);
})();