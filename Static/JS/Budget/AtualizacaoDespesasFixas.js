(function () {
    const app = document.getElementById('budget-process-app');
    if (!app) {
        return;
    }

    const state = {
        tokenOrigem: null,
        nomeOrigem: null,
        tokenDestino: null,
        nomeDestino: null,
        abasDestino: [],
        abaDestino: '',
        resultado: null,
    };

    const origemInput = document.getElementById('arquivo-origem-input');
    const destinoInput = document.getElementById('arquivo-destino-input');
    const enviarOrigemBtn = document.getElementById('enviar-origem-btn');
    const enviarDestinoBtn = document.getElementById('enviar-destino-btn');
    const processarBtn = document.getElementById('processar-btn');
    const abaSelect = document.getElementById('aba-destino-select');

    const origemMeta = document.getElementById('arquivo-origem-meta');
    const destinoMeta = document.getElementById('arquivo-destino-meta');
    const statusBox = document.getElementById('budget-status');
    const resultadoCard = document.getElementById('resultado-card');
    const resultadoLista = document.getElementById('resultado-lista');
    const downloadBtn = document.getElementById('download-btn');

    const statusOrigemTag = document.getElementById('status-origem-tag');
    const statusDestinoTag = document.getElementById('status-destino-tag');
    const statusProcessamentoTag = document.getElementById('status-processamento-tag');
    const stepCards = Array.from(document.querySelectorAll('.luft-budget-progress-step'));
    const stepSections = {
        origem: document.querySelector('[data-step-card="1"]'),
        destino: document.querySelector('[data-step-card="2"]'),
        processamento: document.querySelector('[data-step-card="3"]'),
    };

    function setStatus(message, type) {
        statusBox.textContent = message;
        statusBox.className = 'luft-budget-status is-visible';
        if (type) {
            statusBox.classList.add(`is-${type}`);
        }
    }

    function clearStatus() {
        statusBox.textContent = '';
        statusBox.className = 'luft-budget-status';
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function renderFileMeta(container, fileName, detail) {
        if (!fileName) {
            container.innerHTML = '';
            return;
        }

        container.innerHTML = `
            <div class="luft-budget-pill">
                <i class="ph-bold ph-check-circle"></i>
                <div>
                    <strong>${escapeHtml(fileName)}</strong>
                    <span>${escapeHtml(detail)}</span>
                </div>
            </div>
        `;
    }

    function renderAbas() {
        abaSelect.innerHTML = '';

        if (!state.abasDestino.length) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = 'Envie o arquivo de destino para listar as abas';
            abaSelect.appendChild(option);
            abaSelect.disabled = true;
            return;
        }

        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = 'Selecione a aba que será atualizada';
        abaSelect.appendChild(placeholder);

        state.abasDestino.forEach((aba) => {
            const option = document.createElement('option');
            option.value = aba;
            option.textContent = aba;
            if (aba === state.abaDestino) {
                option.selected = true;
            }
            abaSelect.appendChild(option);
        });

        abaSelect.disabled = false;
    }

    function renderResultado() {
        if (!state.resultado) {
            resultadoCard.classList.remove('is-visible');
            resultadoLista.innerHTML = '';
            downloadBtn.href = '#';
            return;
        }

        resultadoLista.innerHTML = `
            <div class="luft-budget-result-item">
                <i class="ph-bold ph-file"></i>
                <div>
                    <strong>Arquivo gerado</strong>
                    <span>${escapeHtml(state.resultado.nomeArquivo)}</span>
                </div>
            </div>
            <div class="luft-budget-result-item">
                <i class="ph-bold ph-table"></i>
                <div>
                    <strong>Aba atualizada</strong>
                    <span>${escapeHtml(state.resultado.abaDestino)}</span>
                </div>
            </div>
            <div class="luft-budget-result-item">
                <i class="ph-bold ph-list-numbers"></i>
                <div>
                    <strong>Registros inseridos</strong>
                    <span>${escapeHtml(String(state.resultado.linhasInseridas))}</span>
                </div>
            </div>
            <div class="luft-budget-result-item">
                <i class="ph-bold ph-clock"></i>
                <div>
                    <strong>Processado em</strong>
                    <span>${escapeHtml(state.resultado.processadoEm)}</span>
                </div>
            </div>
        `;
        downloadBtn.href = state.resultado.downloadUrl;
        resultadoCard.classList.add('is-visible');
    }

    function toggleStepSection(element, visible) {
        if (!element) {
            return;
        }

        element.classList.toggle('is-hidden', !visible);
    }

    function updateStepUI() {
        const step1Complete = Boolean(state.tokenOrigem);
        const step2Complete = Boolean(state.tokenDestino);
        const step3Ready = step1Complete && step2Complete;
        const step3Complete = Boolean(state.resultado);

        stepCards.forEach((card) => {
            card.classList.remove('is-active', 'is-complete', 'is-locked');
        });

        if (stepCards[0] && step1Complete) {
            stepCards[0].classList.add('is-complete');
        } else if (stepCards[0]) {
            stepCards[0].classList.add('is-active');
        }

        if (!step1Complete && stepCards[1]) {
            stepCards[1].classList.add('is-locked');
        } else if (stepCards[1] && step2Complete) {
            stepCards[1].classList.add('is-complete');
        } else if (stepCards[1]) {
            stepCards[1].classList.add('is-active');
        }

        if (!step2Complete && stepCards[2]) {
            stepCards[2].classList.add('is-locked');
        } else if (stepCards[2] && step3Complete) {
            stepCards[2].classList.add('is-complete');
        } else if (stepCards[2] && step3Ready) {
            stepCards[2].classList.add('is-active');
        }

        toggleStepSection(stepSections.origem, true);
        toggleStepSection(stepSections.destino, step1Complete);
        toggleStepSection(stepSections.processamento, step2Complete);

        statusOrigemTag.textContent = step1Complete ? 'Importado' : 'Pendente';
        statusDestinoTag.textContent = step1Complete ? (step2Complete ? 'Importado' : 'Pendente') : 'Bloqueado';
        statusProcessamentoTag.textContent = step3Complete ? 'Concluído' : (step3Ready ? 'Pronto para gerar' : 'Bloqueado');

        statusOrigemTag.className = 'luft-budget-badge';
        statusDestinoTag.className = 'luft-budget-badge';
        statusProcessamentoTag.className = 'luft-budget-badge';

        if (step1Complete) {
            statusOrigemTag.classList.add('is-ready');
        }
        if (step2Complete) {
            statusDestinoTag.classList.add('is-ready');
        }
        if (step3Complete || step3Ready) {
            statusProcessamentoTag.classList.add('is-ready');
        }

        enviarOrigemBtn.disabled = !origemInput.files.length;
        enviarDestinoBtn.disabled = !state.tokenOrigem || !destinoInput.files.length;
        abaSelect.disabled = !state.tokenDestino || !state.abasDestino.length;
        processarBtn.disabled = !(state.tokenOrigem && state.tokenDestino && state.abaDestino);
    }

    async function uploadArquivo(file, url) {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: formData,
        });

        const payload = await response.json();
        if (!response.ok || payload.status !== 'success') {
            throw new Error(payload.message || payload.error || 'Falha ao enviar o arquivo.');
        }

        return payload.data || {};
    }

    async function processarAtualizacao() {
        const response = await fetch(app.dataset.processarUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify({
                tokenOrigem: state.tokenOrigem,
                tokenDestino: state.tokenDestino,
                abaDestino: state.abaDestino,
            }),
        });

        const payload = await response.json();
        if (!response.ok || payload.status !== 'success') {
            throw new Error(payload.message || payload.error || 'Falha ao processar a atualização.');
        }

        return payload.data || {};
    }

    function resetResultado() {
        state.resultado = null;
        renderResultado();
    }

    function setLoading(button, isLoading, text) {
        if (!button.dataset.originalText) {
            button.dataset.originalText = button.innerHTML;
        }

        if (isLoading) {
            button.disabled = true;
            button.innerHTML = `<i class="ph-bold ph-spinner-gap"></i><span>${escapeHtml(text)}</span>`;
            return;
        }

        button.innerHTML = button.dataset.originalText;
    }

    origemInput.addEventListener('change', () => {
        resetResultado();
        clearStatus();
        renderFileMeta(origemMeta, origemInput.files[0]?.name || '', 'Arquivo pronto para upload.');
        updateStepUI();
    });

    destinoInput.addEventListener('change', () => {
        resetResultado();
        clearStatus();
        renderFileMeta(destinoMeta, destinoInput.files[0]?.name || '', 'Arquivo pronto para upload.');
        updateStepUI();
    });

    abaSelect.addEventListener('change', () => {
        state.abaDestino = abaSelect.value;
        resetResultado();
        updateStepUI();
    });

    enviarOrigemBtn.addEventListener('click', async () => {
        if (!origemInput.files.length) {
            return;
        }

        try {
            clearStatus();
            setLoading(enviarOrigemBtn, true, 'Importando...');
            const data = await uploadArquivo(origemInput.files[0], app.dataset.uploadOrigemUrl);
            state.tokenOrigem = data.token;
            state.nomeOrigem = data.nomeArquivo;
            state.tokenDestino = null;
            state.nomeDestino = null;
            state.abasDestino = [];
            state.abaDestino = '';
            destinoInput.value = '';
            renderFileMeta(origemMeta, data.nomeArquivo, 'Arquivo base carregado no processo.');
            renderFileMeta(destinoMeta, '', '');
            renderAbas();
            setStatus('Arquivo base importado. Agora envie o arquivo macro de destino.', 'success');
            updateStepUI();
            stepSections.destino?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } catch (error) {
            setStatus(error.message, 'error');
        } finally {
            setLoading(enviarOrigemBtn, false, 'Importar arquivo');
            resetResultado();
            updateStepUI();
        }
    });

    enviarDestinoBtn.addEventListener('click', async () => {
        if (!destinoInput.files.length) {
            return;
        }

        try {
            clearStatus();
            setLoading(enviarDestinoBtn, true, 'Importando...');
            const data = await uploadArquivo(destinoInput.files[0], app.dataset.uploadDestinoUrl);
            state.tokenDestino = data.token;
            state.nomeDestino = data.nomeArquivo;
            state.abasDestino = Array.isArray(data.abas) ? data.abas : [];
            state.abaDestino = '';
            renderFileMeta(destinoMeta, data.nomeArquivo, `${state.abasDestino.length} aba(s) encontrada(s) para seleção.`);
            renderAbas();
            setStatus('Arquivo de destino importado. Escolha a aba que será atualizada.', 'success');
            updateStepUI();
            stepSections.processamento?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } catch (error) {
            setStatus(error.message, 'error');
        } finally {
            setLoading(enviarDestinoBtn, false, 'Importar arquivo');
            resetResultado();
            updateStepUI();
        }
    });

    processarBtn.addEventListener('click', async () => {
        if (!state.tokenOrigem || !state.tokenDestino || !state.abaDestino) {
            return;
        }

        try {
            resetResultado();
            setStatus('Processando a cópia atualizada. Isso pode levar alguns instantes.', 'info');
            setLoading(processarBtn, true, 'Processando...');
            const data = await processarAtualizacao();
            state.resultado = data;
            renderResultado();
            setStatus('Cópia atualizada gerada com sucesso. O download já está disponível.', 'success');
        } catch (error) {
            setStatus(error.message, 'error');
        } finally {
            setLoading(processarBtn, false, 'Gerar cópia atualizada');
            updateStepUI();
        }
    });

    renderAbas();
    renderResultado();
    updateStepUI();
})();