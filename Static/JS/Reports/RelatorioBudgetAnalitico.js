document.addEventListener('DOMContentLoaded', () => {
    inicializarBudgetAnalitico();
});

const BUDGET_ANALITICO_API = window.BUDGET_ANALITICO_API_ROUTES || {
    filtros: '/budget/analitico/filtros',
    dados: '/budget/analitico/dados'
};

const BUDGET_ANALITICO_DEFAULTS = window.BUDGET_ANALITICO_DEFAULTS || {
    ano: new Date().getFullYear(),
    mes: new Date().getMonth() + 1
};

const BUDGET_ANALITICO_FILTER_CONFIG = {
    meses: {
        buttonId: 'btnToggleMesBudgetAnalitico',
        panelId: 'panelMesBudgetAnalitico',
        labelId: 'labelMesBudgetAnalitico',
        searchInputId: 'inputBuscaMesBudgetAnalitico',
        listId: 'listaMesBudgetAnalitico',
        selectAllId: 'checkTodosMesesBudgetAnalitico',
        emptyId: 'emptyMesBudgetAnalitico',
        emptyMessage: 'Nenhum mês disponível.',
        allLabel: 'Todos os meses',
        noneLabel: 'Nenhum mês selecionado',
        multipleLabel: 'meses selecionados',
        requireSelection: true,
        defaultMode: 'default-month',
        syncOnChange: false
    },
    centrosCusto: {
        buttonId: 'btnToggleCentroCustoBudgetAnalitico',
        panelId: 'panelCentroCustoBudgetAnalitico',
        labelId: 'labelCentroCustoBudgetAnalitico',
        searchInputId: 'inputBuscaCentroCustoBudgetAnalitico',
        listId: 'listaCentroCustoBudgetAnalitico',
        selectAllId: 'checkTodosCentrosBudgetAnalitico',
        emptyId: 'emptyCentroCustoBudgetAnalitico',
        emptyMessage: 'Nenhum centro de custo disponível.',
        allLabel: 'Todos os centros',
        noneLabel: 'Nenhum centro selecionado',
        multipleLabel: 'centros selecionados',
        requireSelection: false,
        defaultMode: 'all',
        syncOnChange: true
    }
};

const budgetAnaliticoState = {
    data: null,
    renderData: {
        grupos: [],
        resumo: criarResumoVazioBudgetAnalitico()
    },
    expandedGroups: new Set(),
    expansionInitialized: false,
    modoSaldo: 'todos_itens',
    requestToken: 0,
    syncTimer: null,
    documentClickBound: false,
    filtros: {
        meses: {
            items: [],
            selectedIds: new Set(),
            loaded: false,
            allSelected: false
        },
        centrosCusto: {
            items: [],
            selectedIds: new Set(),
            loaded: false,
            allSelected: true
        }
    }
};

function criarResumoVazioBudgetAnalitico() {
    return {
        orcado: 0,
        realizado: 0,
        diferenca: 0,
        consumoPercentual: null,
        quantidadeGrupos: 0,
        quantidadeContas: 0
    };
}

function inicializarBudgetAnalitico() {
    const inputAno = document.getElementById('inputAnoBudgetAnalitico');
    const selectModoSaldo = document.getElementById('selectModoSaldoBudgetAnalitico');

    if (!inputAno) {
        return;
    }

    inputAno.value = BUDGET_ANALITICO_DEFAULTS.ano;
    budgetAnaliticoState.modoSaldo = selectModoSaldo?.value || 'todos_itens';

    configurarEventosBudgetAnalitico();
    configurarFiltrosBudgetAnalitico();

    carregarFiltrosBudgetAnalitico()
        .then(() => carregarDadosBudgetAnalitico())
        .catch((erro) => {
            console.error('Erro na inicialização do Budget Analítico:', erro);
            budgetAnaliticoState.data = null;
            budgetAnaliticoState.renderData = {
                grupos: [],
                resumo: criarResumoVazioBudgetAnalitico()
            };
            atualizarKpisBudgetAnalitico();
            renderizarErroBudgetAnalitico('Não foi possível inicializar o relatório analítico.');
        });
}

function configurarEventosBudgetAnalitico() {
    const btnBuscar = document.getElementById('btnBuscarBudgetAnalitico');
    const inputAno = document.getElementById('inputAnoBudgetAnalitico');
    const selectEmpresa = document.getElementById('selectEmpresaBudgetAnalitico');
    const selectFilial = document.getElementById('selectFilialBudgetAnalitico');
    const selectModoSaldo = document.getElementById('selectModoSaldoBudgetAnalitico');
    const corpoTabela = document.getElementById('corpoTabelaBudgetAnalitico');
    const btnExpandir = document.getElementById('btnExpandirGruposBudgetAnalitico');
    const btnRecolher = document.getElementById('btnRecolherGruposBudgetAnalitico');

    if (btnBuscar) {
        btnBuscar.addEventListener('click', () => carregarDadosBudgetAnalitico());
    }

    if (inputAno) {
        inputAno.addEventListener('change', () => {
            carregarFiltrosBudgetAnalitico();
        });
    }

    if (selectEmpresa) {
        selectEmpresa.addEventListener('change', () => {
            carregarFiltrosBudgetAnalitico();
        });
    }

    if (selectFilial) {
        selectFilial.addEventListener('change', () => {
            atualizarChipsBudgetAnalitico();
        });
    }

    if (selectModoSaldo) {
        selectModoSaldo.addEventListener('change', (event) => {
            budgetAnaliticoState.modoSaldo = event.target.value || 'todos_itens';
            atualizarApresentacaoBudgetAnalitico();
        });
    }

    if (corpoTabela) {
        corpoTabela.addEventListener('click', (event) => {
            const alvo = event.target.closest('[data-budget-analytic-group]');
            if (!alvo) {
                return;
            }

            const groupId = decodeURIComponent(alvo.dataset.budgetAnalyticGroup || '');
            alternarGrupoBudgetAnalitico(groupId);
        });
    }

    if (btnExpandir) {
        btnExpandir.addEventListener('click', () => {
            const grupos = budgetAnaliticoState.renderData?.grupos || [];
            budgetAnaliticoState.expandedGroups = new Set(grupos.map((grupo) => grupo.id));
            renderizarTabelaBudgetAnalitico();
        });
    }

    if (btnRecolher) {
        btnRecolher.addEventListener('click', () => {
            budgetAnaliticoState.expandedGroups.clear();
            renderizarTabelaBudgetAnalitico();
        });
    }
}

function configurarFiltrosBudgetAnalitico() {
    Object.keys(BUDGET_ANALITICO_FILTER_CONFIG).forEach((chaveFiltro) => {
        configurarFiltroBudgetAnalitico(chaveFiltro);
    });

    if (!budgetAnaliticoState.documentClickBound) {
        document.addEventListener('click', (event) => {
            Object.keys(BUDGET_ANALITICO_FILTER_CONFIG).forEach((chaveFiltro) => {
                const config = obterConfiguracaoFiltroBudgetAnalitico(chaveFiltro);
                const botao = document.getElementById(config.buttonId);
                const painel = document.getElementById(config.panelId);

                if (!botao || !painel) {
                    return;
                }

                if (painel.contains(event.target) || botao.contains(event.target)) {
                    return;
                }

                fecharPainelFiltroBudgetAnalitico(chaveFiltro);
            });
        });

        budgetAnaliticoState.documentClickBound = true;
    }
}

function configurarFiltroBudgetAnalitico(chaveFiltro) {
    const config = obterConfiguracaoFiltroBudgetAnalitico(chaveFiltro);
    const botao = document.getElementById(config.buttonId);
    const campoBusca = document.getElementById(config.searchInputId);
    const lista = document.getElementById(config.listId);
    const checkboxTodos = document.getElementById(config.selectAllId);

    if (botao && !botao.dataset.bound) {
        botao.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            alternarPainelFiltroBudgetAnalitico(chaveFiltro);
        });
        botao.dataset.bound = 'true';
    }

    if (campoBusca && !campoBusca.dataset.bound) {
        campoBusca.addEventListener('input', () => {
            aplicarBuscaFiltroBudgetAnalitico(chaveFiltro);
        });
        campoBusca.dataset.bound = 'true';
    }

    if (checkboxTodos && !checkboxTodos.dataset.bound) {
        checkboxTodos.addEventListener('change', () => {
            atualizarSelecaoTotalFiltroBudgetAnalitico(chaveFiltro, checkboxTodos);
        });
        checkboxTodos.dataset.bound = 'true';
    }

    if (lista && !lista.dataset.bound) {
        lista.addEventListener('change', (event) => {
            const checkbox = event.target.closest('.luft-budget-filter-checkbox');
            if (!checkbox) {
                return;
            }

            atualizarSelecaoFiltroBudgetAnalitico(chaveFiltro, checkbox);
        });
        lista.dataset.bound = 'true';
    }
}

function obterConfiguracaoFiltroBudgetAnalitico(chaveFiltro) {
    return BUDGET_ANALITICO_FILTER_CONFIG[chaveFiltro];
}

function obterEstadoFiltroBudgetAnalitico(chaveFiltro) {
    return budgetAnaliticoState.filtros[chaveFiltro];
}

function alternarPainelFiltroBudgetAnalitico(chaveFiltro) {
    const config = obterConfiguracaoFiltroBudgetAnalitico(chaveFiltro);
    const painel = document.getElementById(config.panelId);

    if (!painel) {
        return;
    }

    const estaOculto = painel.classList.contains('d-none');
    fecharTodosPaineisFiltroBudgetAnalitico(estaOculto ? chaveFiltro : null);

    if (estaOculto) {
        abrirPainelFiltroBudgetAnalitico(chaveFiltro);
        return;
    }

    fecharPainelFiltroBudgetAnalitico(chaveFiltro);
}

function abrirPainelFiltroBudgetAnalitico(chaveFiltro) {
    const config = obterConfiguracaoFiltroBudgetAnalitico(chaveFiltro);
    const painel = document.getElementById(config.panelId);
    const botao = document.getElementById(config.buttonId);
    const campoBusca = document.getElementById(config.searchInputId);

    if (!painel || !botao) {
        return;
    }

    painel.classList.remove('d-none');
    botao.classList.add('is-open');

    if (campoBusca) {
        campoBusca.focus();
        campoBusca.select();
    }
}

function fecharPainelFiltroBudgetAnalitico(chaveFiltro) {
    const config = obterConfiguracaoFiltroBudgetAnalitico(chaveFiltro);
    const painel = document.getElementById(config.panelId);
    const botao = document.getElementById(config.buttonId);

    if (!painel || !botao) {
        return;
    }

    painel.classList.add('d-none');
    botao.classList.remove('is-open');
}

function fecharTodosPaineisFiltroBudgetAnalitico(excecao = null) {
    Object.keys(BUDGET_ANALITICO_FILTER_CONFIG).forEach((chaveFiltro) => {
        if (chaveFiltro === excecao) {
            return;
        }

        fecharPainelFiltroBudgetAnalitico(chaveFiltro);
    });
}

function construirUrlBudgetAnalitico(chave, parametros = {}) {
    const rota = BUDGET_ANALITICO_API[chave] || BUDGET_ANALITICO_API.dados;
    const url = new URL(rota, window.location.origin);

    Object.entries(parametros).forEach(([nome, valor]) => {
        url.searchParams.set(nome, valor);
    });

    return url.toString();
}

async function obterJsonBudgetAnalitico(url) {
    const resposta = await fetch(url, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
    });
    const payload = await resposta.json();

    if (!resposta.ok) {
        throw new Error(payload.message || payload.msg || `Falha HTTP ${resposta.status}`);
    }

    return payload;
}

async function carregarFiltrosBudgetAnalitico() {
    const inputAno = document.getElementById('inputAnoBudgetAnalitico');
    const selectEmpresa = document.getElementById('selectEmpresaBudgetAnalitico');
    const selectFilial = document.getElementById('selectFilialBudgetAnalitico');

    const ano = inputAno?.value || BUDGET_ANALITICO_DEFAULTS.ano;
    const empresaAtual = selectEmpresa?.value || 'Todos';
    const filialAtual = selectFilial?.value || 'Todos';
    const centroAtual = obterParametroFiltroBudgetAnalitico('centrosCusto', { ignorarVazio: true });
    const requestToken = ++budgetAnaliticoState.requestToken;

    if (selectFilial) {
        selectFilial.disabled = true;
        selectFilial.innerHTML = '<option value="Todos">Atualizando filiais...</option>';
    }

    const retorno = await obterJsonBudgetAnalitico(construirUrlBudgetAnalitico('filtros', {
        ano,
        empresa: empresaAtual,
        centro_custo: centroAtual
    }));

    if (requestToken !== budgetAnaliticoState.requestToken) {
        return;
    }

    const dados = retorno.data || {};

    preencherSelectBudgetAnalitico(
        selectEmpresa,
        dados.empresas || [],
        empresaAtual,
        'Todos',
        'Todas as Empresas',
        (item) => ({ value: item.id, label: item.nome })
    );

    renderizarOpcoesFiltroBudgetAnalitico('meses', dados.meses || []);
    renderizarOpcoesFiltroBudgetAnalitico('centrosCusto', dados.centrosCusto || []);

    preencherSelectBudgetAnalitico(
        selectFilial,
        dados.filiais || [],
        filialAtual,
        'Todos',
        'Todas as Filiais',
        (item) => ({ value: item.id, label: item.nome })
    );

    atualizarChipsBudgetAnalitico();
}

function preencherSelectBudgetAnalitico(select, itens, valorAtual, valorPadrao, labelPadrao, mapearItem) {
    if (!select) {
        return;
    }

    const opcoes = [`<option value="${escapeHtml(valorPadrao)}">${escapeHtml(labelPadrao)}</option>`];
    const valoresDisponiveis = new Set([valorPadrao]);

    (Array.isArray(itens) ? itens : []).forEach((item) => {
        const opcao = mapearItem(item);
        valoresDisponiveis.add(String(opcao.value));
        opcoes.push(`<option value="${escapeHtml(String(opcao.value))}">${escapeHtml(opcao.label)}</option>`);
    });

    select.innerHTML = opcoes.join('');
    select.disabled = false;

    const proximoValor = valoresDisponiveis.has(String(valorAtual)) ? String(valorAtual) : valorPadrao;
    select.value = proximoValor;
}

function renderizarOpcoesFiltroBudgetAnalitico(chaveFiltro, listaOpcoes) {
    const config = obterConfiguracaoFiltroBudgetAnalitico(chaveFiltro);
    const estado = obterEstadoFiltroBudgetAnalitico(chaveFiltro);
    const lista = document.getElementById(config.listId);

    if (!lista) {
        return;
    }

    const opcoes = (Array.isArray(listaOpcoes) ? listaOpcoes : []).map((item) => ({
        ...item,
        id: String(item.id)
    }));
    const idsDisponiveis = new Set(opcoes.map((item) => item.id));
    let selecionados = new Set();

    if (opcoes.length > 0) {
        if (!estado.loaded) {
            selecionados = obterSelecaoInicialFiltroBudgetAnalitico(chaveFiltro, opcoes);
        } else if (estado.allSelected) {
            selecionados = new Set(opcoes.map((item) => item.id));
        } else {
            selecionados = new Set(
                Array.from(estado.selectedIds).filter((idSelecionado) => idsDisponiveis.has(idSelecionado))
            );

            if (selecionados.size === 0) {
                selecionados = obterSelecaoInicialFiltroBudgetAnalitico(chaveFiltro, opcoes);
            }
        }
    }

    estado.items = opcoes;
    estado.selectedIds = selecionados;
    estado.loaded = true;
    estado.allSelected = opcoes.length > 0 && selecionados.size === opcoes.length;

    lista.innerHTML = opcoes.map((item) => {
        const texto = formatarTextoOpcaoFiltroBudgetAnalitico(chaveFiltro, item);
        const textoBusca = normalizarTextoBudgetAnalitico(`${item.id} ${item.nome || ''} ${item.codigo || ''} ${texto}`);
        const marcado = estado.selectedIds.has(item.id) ? 'checked' : '';

        return `
            <label class="luft-budget-filter-option" data-search="${escapeHtml(textoBusca)}">
                <input type="checkbox" class="luft-budget-filter-checkbox" value="${escapeHtml(item.id)}" ${marcado}>
                <span>${escapeHtml(texto)}</span>
            </label>`;
    }).join('');

    atualizarResumoFiltroBudgetAnalitico(chaveFiltro);
    aplicarBuscaFiltroBudgetAnalitico(chaveFiltro);
}

function obterSelecaoInicialFiltroBudgetAnalitico(chaveFiltro, opcoes) {
    const config = obterConfiguracaoFiltroBudgetAnalitico(chaveFiltro);

    if (!opcoes.length) {
        return new Set();
    }

    if (config.defaultMode === 'default-month') {
        const mesPadrao = String(BUDGET_ANALITICO_DEFAULTS.mes);
        const existeMesPadrao = opcoes.some((item) => item.id === mesPadrao);
        return new Set([existeMesPadrao ? mesPadrao : opcoes[0].id]);
    }

    return new Set(opcoes.map((item) => item.id));
}

function formatarTextoOpcaoFiltroBudgetAnalitico(chaveFiltro, item) {
    if (chaveFiltro === 'meses') {
        return item.nome || item.id;
    }

    if (item.codigo && item.nome) {
        return `${item.codigo} - ${item.nome}`;
    }

    return item.nome || item.id;
}

function normalizarTextoBudgetAnalitico(texto) {
    return String(texto ?? '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase();
}

function atualizarSelecaoFiltroBudgetAnalitico(chaveFiltro, checkbox) {
    const config = obterConfiguracaoFiltroBudgetAnalitico(chaveFiltro);
    const estado = obterEstadoFiltroBudgetAnalitico(chaveFiltro);
    const idItem = String(checkbox.value);

    if (!checkbox.checked && config.requireSelection && estado.selectedIds.size === 1 && estado.selectedIds.has(idItem)) {
        checkbox.checked = true;
        return;
    }

    if (checkbox.checked) {
        estado.selectedIds.add(idItem);
    } else {
        estado.selectedIds.delete(idItem);
    }

    estado.allSelected = estado.items.length > 0 && estado.selectedIds.size === estado.items.length;
    atualizarResumoFiltroBudgetAnalitico(chaveFiltro);

    if (config.syncOnChange) {
        agendarSincronizacaoFiltrosBudgetAnalitico();
    }
}

function atualizarSelecaoTotalFiltroBudgetAnalitico(chaveFiltro, checkboxTodos) {
    const config = obterConfiguracaoFiltroBudgetAnalitico(chaveFiltro);
    const estado = obterEstadoFiltroBudgetAnalitico(chaveFiltro);

    if (!checkboxTodos.checked && config.requireSelection) {
        checkboxTodos.checked = true;
        checkboxTodos.indeterminate = false;
        return;
    }

    estado.selectedIds = checkboxTodos.checked
        ? new Set(estado.items.map((item) => item.id))
        : new Set();
    estado.allSelected = checkboxTodos.checked && estado.items.length > 0;

    const lista = document.getElementById(config.listId);
    if (lista) {
        lista.querySelectorAll('.luft-budget-filter-checkbox').forEach((checkbox) => {
            checkbox.checked = checkboxTodos.checked;
        });
    }

    atualizarResumoFiltroBudgetAnalitico(chaveFiltro);

    if (config.syncOnChange) {
        agendarSincronizacaoFiltrosBudgetAnalitico();
    }
}

function aplicarBuscaFiltroBudgetAnalitico(chaveFiltro) {
    const config = obterConfiguracaoFiltroBudgetAnalitico(chaveFiltro);
    const lista = document.getElementById(config.listId);
    const campoBusca = document.getElementById(config.searchInputId);
    const mensagemVazia = document.getElementById(config.emptyId);

    if (!lista || !campoBusca || !mensagemVazia) {
        return;
    }

    const termo = normalizarTextoBudgetAnalitico(campoBusca.value);
    let totalVisivel = 0;

    lista.querySelectorAll('.luft-budget-filter-option').forEach((opcao) => {
        const corresponde = !termo || (opcao.dataset.search || '').includes(termo);
        opcao.classList.toggle('d-none', !corresponde);

        if (corresponde) {
            totalVisivel += 1;
        }
    });

    mensagemVazia.textContent = obterEstadoFiltroBudgetAnalitico(chaveFiltro).items.length === 0
        ? config.emptyMessage
        : 'Nenhuma opção encontrada para a pesquisa informada.';
    mensagemVazia.classList.toggle('d-none', totalVisivel > 0);
}

function atualizarResumoFiltroBudgetAnalitico(chaveFiltro) {
    const config = obterConfiguracaoFiltroBudgetAnalitico(chaveFiltro);
    const estado = obterEstadoFiltroBudgetAnalitico(chaveFiltro);
    const label = document.getElementById(config.labelId);
    const checkboxTodos = document.getElementById(config.selectAllId);
    const botao = document.getElementById(config.buttonId);
    const total = estado.items.length;
    const selecionados = estado.selectedIds.size;

    if (label) {
        label.textContent = obterDescricaoSelecaoFiltroBudgetAnalitico(chaveFiltro);
    }

    if (checkboxTodos) {
        checkboxTodos.checked = total > 0 && selecionados === total;
        checkboxTodos.indeterminate = selecionados > 0 && selecionados < total;
    }

    if (botao) {
        botao.disabled = total === 0;
    }

    atualizarChipsBudgetAnalitico();
}

function obterDescricaoSelecaoFiltroBudgetAnalitico(chaveFiltro) {
    const config = obterConfiguracaoFiltroBudgetAnalitico(chaveFiltro);
    const estado = obterEstadoFiltroBudgetAnalitico(chaveFiltro);
    const total = estado.items.length;
    const selecionados = estado.selectedIds.size;

    if (total === 0) {
        return 'Sem opções';
    }

    if (selecionados === total) {
        return config.allLabel;
    }

    if (selecionados === 0) {
        return config.noneLabel;
    }

    if (selecionados === 1) {
        const selecionado = estado.items.find((item) => estado.selectedIds.has(item.id));
        return selecionado ? formatarTextoOpcaoFiltroBudgetAnalitico(chaveFiltro, selecionado) : config.noneLabel;
    }

    return `${selecionados} ${config.multipleLabel}`;
}

function obterParametroFiltroBudgetAnalitico(chaveFiltro, { ignorarVazio = false } = {}) {
    const estado = obterEstadoFiltroBudgetAnalitico(chaveFiltro);

    if (!estado.loaded) {
        return 'Todos';
    }

    if (estado.items.length === 0) {
        return '-999';
    }

    if (estado.selectedIds.size === 0) {
        return ignorarVazio ? 'Todos' : '-999';
    }

    if (estado.selectedIds.size === estado.items.length) {
        return 'Todos';
    }

    return Array.from(estado.selectedIds).join(',');
}

function agendarSincronizacaoFiltrosBudgetAnalitico() {
    clearTimeout(budgetAnaliticoState.syncTimer);
    budgetAnaliticoState.syncTimer = setTimeout(() => {
        carregarFiltrosBudgetAnalitico();
    }, 250);
}

async function carregarDadosBudgetAnalitico() {
    const inputAno = document.getElementById('inputAnoBudgetAnalitico');
    const selectEmpresa = document.getElementById('selectEmpresaBudgetAnalitico');
    const selectFilial = document.getElementById('selectFilialBudgetAnalitico');

    renderizarLoadingBudgetAnalitico();

    try {
        const retorno = await obterJsonBudgetAnalitico(construirUrlBudgetAnalitico('dados', {
            ano: inputAno?.value || BUDGET_ANALITICO_DEFAULTS.ano,
            mes: obterParametroFiltroBudgetAnalitico('meses'),
            empresa: selectEmpresa?.value || 'Todos',
            centro_custo: obterParametroFiltroBudgetAnalitico('centrosCusto'),
            filial: selectFilial?.value || 'Todos'
        }));

        budgetAnaliticoState.data = retorno.data || null;
        atualizarApresentacaoBudgetAnalitico();
    } catch (erro) {
        console.error('Erro ao carregar o Budget Analítico:', erro);
        budgetAnaliticoState.data = null;
        budgetAnaliticoState.renderData = {
            grupos: [],
            resumo: criarResumoVazioBudgetAnalitico()
        };
        atualizarKpisBudgetAnalitico();
        renderizarErroBudgetAnalitico(erro.message || 'Falha ao carregar os dados analíticos.');
    }
}

function atualizarApresentacaoBudgetAnalitico() {
    recalcularApresentacaoBudgetAnalitico();
    atualizarKpisBudgetAnalitico();
    atualizarCabecalhoBudgetAnalitico();
    atualizarChipsBudgetAnalitico();
    renderizarTabelaBudgetAnalitico();
}

function recalcularApresentacaoBudgetAnalitico() {
    const gruposRenderizados = (budgetAnaliticoState.data?.grupos || [])
        .map((grupo) => prepararGrupoRenderBudgetAnalitico(grupo))
        .filter(Boolean)
        .sort((grupoA, grupoB) => String(grupoA.grupo || '').localeCompare(String(grupoB.grupo || ''), 'pt-BR'));

    const resumo = gruposRenderizados.reduce((acumulado, grupo) => {
        acumulado.orcado += grupo.orcado;
        acumulado.realizado += grupo.realizado;
        acumulado.quantidadeGrupos += 1;
        acumulado.quantidadeContas += grupo.quantidadeContas;
        return acumulado;
    }, criarResumoVazioBudgetAnalitico());

    resumo.diferenca = resumo.orcado - resumo.realizado;
    resumo.consumoPercentual = resumo.orcado > 0 ? (resumo.realizado / resumo.orcado) * 100 : null;

    budgetAnaliticoState.renderData = {
        grupos: gruposRenderizados,
        resumo
    };

    sincronizarExpansaoGruposBudgetAnalitico();
}

function prepararGrupoRenderBudgetAnalitico(grupo) {
    const contas = (Array.isArray(grupo?.contas) ? grupo.contas : [])
        .map((conta) => prepararContaRenderBudgetAnalitico(conta))
        .filter((conta) => conta.orcado !== 0 || conta.realizado !== 0)
        .sort((contaA, contaB) => {
            const numeroA = String(contaA.numeroContaContabil || '');
            const numeroB = String(contaB.numeroContaContabil || '');
            if (numeroA !== numeroB) {
                return numeroA.localeCompare(numeroB, 'pt-BR', { numeric: true });
            }

            return String(contaA.descricaoContaContabil || '').localeCompare(String(contaB.descricaoContaContabil || ''), 'pt-BR');
        });

    if (!contas.length) {
        return null;
    }

    const orcado = contas.reduce((acumulado, conta) => acumulado + conta.orcado, 0);
    const realizado = contas.reduce((acumulado, conta) => acumulado + conta.realizado, 0);
    const diferenca = orcado - realizado;
    const consumoPercentual = orcado > 0 ? (realizado / orcado) * 100 : null;

    return {
        id: grupo.id,
        grupo: grupo.grupo,
        quantidadeContas: contas.length,
        contas,
        orcado,
        realizado,
        diferenca,
        consumoPercentual
    };
}

function prepararContaRenderBudgetAnalitico(conta) {
    const valores = obterValoresLinhaBudgetAnalitico(conta);

    return {
        ...conta,
        ...valores,
        filiais: Array.isArray(conta?.filiais) ? conta.filiais : []
    };
}

function obterValoresLinhaBudgetAnalitico(linha) {
    const orcado = Number(linha?.orcado) || 0;
    const realizadoTotal = Number(linha?.realizadoTotal) || 0;
    const realizadoComBudgetInformado = Number(linha?.realizadoComBudget);
    const realizadoComBudget = Number.isFinite(realizadoComBudgetInformado)
        ? realizadoComBudgetInformado
        : realizadoTotal;
    const usarTodosItens = budgetAnaliticoState.modoSaldo === 'todos_itens';
    const realizado = usarTodosItens ? realizadoTotal : realizadoComBudget;

    return {
        orcado,
        realizado,
        realizadoTotal,
        realizadoComBudget,
        diferenca: orcado - realizado,
        consumoPercentual: orcado > 0 ? (realizado / orcado) * 100 : null
    };
}

function sincronizarExpansaoGruposBudgetAnalitico() {
    const grupos = budgetAnaliticoState.renderData?.grupos || [];
    const ids = grupos.map((grupo) => grupo.id);

    if (!budgetAnaliticoState.expansionInitialized) {
        budgetAnaliticoState.expandedGroups = new Set(ids);
        budgetAnaliticoState.expansionInitialized = true;
        return;
    }

    const novasExpansoes = new Set();
    ids.forEach((id) => {
        if (budgetAnaliticoState.expandedGroups.has(id)) {
            novasExpansoes.add(id);
        }
    });

    budgetAnaliticoState.expandedGroups = novasExpansoes;
}

function alternarGrupoBudgetAnalitico(groupId) {
    if (!groupId) {
        return;
    }

    if (budgetAnaliticoState.expandedGroups.has(groupId)) {
        budgetAnaliticoState.expandedGroups.delete(groupId);
    } else {
        budgetAnaliticoState.expandedGroups.add(groupId);
    }

    renderizarTabelaBudgetAnalitico();
}

function atualizarKpisBudgetAnalitico() {
    const resumo = budgetAnaliticoState.renderData?.resumo || criarResumoVazioBudgetAnalitico();
    const diferenca = Number(resumo.diferenca || 0);
    const icone = document.getElementById('kpiBudgetAnaliticoDiferencaIcon');

    definirTexto('kpiBudgetAnaliticoRealizado', formatarMoedaBudgetAnalitico(resumo.realizado || 0));
    definirTexto('kpiBudgetAnaliticoOrcado', formatarMoedaBudgetAnalitico(resumo.orcado || 0));
    definirTexto('kpiBudgetAnaliticoDiferenca', formatarMoedaBudgetAnalitico(diferenca));
    definirTexto('kpiBudgetAnaliticoConsumo', formatarPercentualBudgetAnalitico(resumo.consumoPercentual));

    if (icone) {
        icone.classList.toggle('is-negative', diferenca < 0);
    }
}

function atualizarCabecalhoBudgetAnalitico() {
    const referencia = budgetAnaliticoState.data?.referencia || {};
    const resumo = budgetAnaliticoState.renderData?.resumo || criarResumoVazioBudgetAnalitico();
    const descricaoMeses = referencia.descricaoMeses || 'seleção atual';
    const titulo = referencia.ano
        ? `Comparativo analítico de ${descricaoMeses} / ${referencia.ano}`
        : 'Comparativo analítico por grupo e conta';
    const status = resumo.quantidadeGrupos
        ? `${resumo.quantidadeGrupos} grupos e ${resumo.quantidadeContas} contas contábeis consolidadas no modo atual.`
        : 'Nenhum lançamento ou budget encontrado para os filtros selecionados.';

    definirTexto('budgetAnaliticoTituloTabela', titulo);
    definirTexto('budgetAnaliticoStatusTabela', status);
}

function atualizarChipsBudgetAnalitico() {
    const selectEmpresa = document.getElementById('selectEmpresaBudgetAnalitico');
    const selectFilial = document.getElementById('selectFilialBudgetAnalitico');
    const selectModoSaldo = document.getElementById('selectModoSaldoBudgetAnalitico');
    const inputAno = document.getElementById('inputAnoBudgetAnalitico');
    const ano = inputAno?.value || BUDGET_ANALITICO_DEFAULTS.ano;

    definirTexto('chipCompetenciaBudgetAnalitico', `${obterDescricaoSelecaoFiltroBudgetAnalitico('meses')} / ${ano}`);
    definirTexto('chipEmpresaBudgetAnalitico', obterTextoOpcaoSelecionada(selectEmpresa) || 'Empresa');
    definirTexto('chipCentroBudgetAnalitico', obterDescricaoSelecaoFiltroBudgetAnalitico('centrosCusto'));
    definirTexto('chipFilialBudgetAnalitico', obterTextoOpcaoSelecionada(selectFilial) || 'Todas as Filiais');
    definirTexto('chipModoSaldoBudgetAnalitico', obterTextoOpcaoSelecionada(selectModoSaldo) || 'Modo de saldo');
}

function renderizarTabelaBudgetAnalitico() {
    const corpo = document.getElementById('corpoTabelaBudgetAnalitico');
    const rodape = document.getElementById('rodapeTabelaBudgetAnalitico');
    const grupos = budgetAnaliticoState.renderData?.grupos || [];
    const resumo = budgetAnaliticoState.renderData?.resumo || criarResumoVazioBudgetAnalitico();

    if (!corpo || !rodape) {
        return;
    }

    if (!grupos.length) {
        corpo.innerHTML = `
            <tr>
                <td colspan="5" class="luft-budget-analytic-empty">
                    Nenhum dado disponível para a seleção atual.
                </td>
            </tr>
        `;
        rodape.innerHTML = '';
        return;
    }

    let html = '';

    grupos.forEach((grupo) => {
        const expandido = budgetAnaliticoState.expandedGroups.has(grupo.id);
        html += renderizarLinhaGrupoBudgetAnalitico(grupo, expandido);

        if (expandido) {
            grupo.contas.forEach((conta) => {
                html += renderizarLinhaContaBudgetAnalitico(conta);
            });
        }
    });

    corpo.innerHTML = html;
    rodape.innerHTML = `
        <tr class="luft-budget-analytic-total-row">
            <td>Total consolidado</td>
            <td class="text-right">${formatarMoedaBudgetAnalitico(resumo.realizado || 0)}</td>
            <td class="text-right">${formatarMoedaBudgetAnalitico(resumo.orcado || 0)}</td>
            <td class="text-right">${renderizarDiferencaBudgetAnalitico(resumo.diferenca || 0)}</td>
            <td>${renderizarConsumoBudgetAnalitico(resumo.consumoPercentual)}</td>
        </tr>
    `;
}

function renderizarLinhaGrupoBudgetAnalitico(grupo, expandido) {
    const groupId = encodeURIComponent(grupo.id);
    const groupLabel = escapeHtml(grupo.grupo || 'grupo');
    const toggleIcon = expandido ? 'ph-caret-down' : 'ph-caret-right';
    const classeToggle = expandido ? 'luft-budget-tree-toggle is-expanded' : 'luft-budget-tree-toggle';
    const contasTexto = grupo.quantidadeContas === 1 ? '1 conta' : `${grupo.quantidadeContas} contas`;

    return `
        <tr class="luft-budget-analytic-group-row" data-budget-analytic-group="${groupId}">
            <td class="luft-budget-structure-cell">
                <div class="luft-budget-tree-node luft-budget-tree-node--group">
                    <button type="button" class="${classeToggle}" data-budget-analytic-group="${groupId}" aria-expanded="${expandido}" aria-label="${expandido ? 'Recolher' : 'Expandir'} ${groupLabel}">
                        <i class="ph-bold ${toggleIcon}"></i>
                    </button>
                    <span class="luft-budget-tree-icon" aria-hidden="true">
                        <i class="ph-bold ph-folders"></i>
                    </span>
                    <div class="luft-budget-tree-content">
                        <span class="luft-budget-tree-title">${groupLabel}</span>
                        <span class="luft-budget-tree-caption">${escapeHtml(contasTexto)}</span>
                    </div>
                </div>
            </td>
            <td class="text-right">${formatarMoedaBudgetAnalitico(grupo.realizado || 0)}</td>
            <td class="text-right">${formatarMoedaBudgetAnalitico(grupo.orcado || 0)}</td>
            <td class="text-right">${renderizarDiferencaBudgetAnalitico(grupo.diferenca || 0)}</td>
            <td>${renderizarConsumoBudgetAnalitico(grupo.consumoPercentual, grupo.orcado, grupo.realizado)}</td>
        </tr>
    `;
}

function renderizarLinhaContaBudgetAnalitico(conta) {
    const codigo = conta.numeroContaContabil ? `Conta ${escapeHtml(conta.numeroContaContabil)}` : 'Conta contábil';
    const quantidadeCentros = Number(conta.quantidadeCentrosCusto || 0);
    const centrosTexto = quantidadeCentros > 1
        ? `${quantidadeCentros} CCs agregados`
        : quantidadeCentros === 1
            ? '1 CC agregado'
            : 'Sem CC vinculado';
    const filiais = Array.isArray(conta.filiais) ? conta.filiais.filter(Boolean) : [];
    const filiaisTexto = filiais.length === 0
        ? ''
        : filiais.length <= 2
            ? filiais.join(', ')
            : `${filiais.length} filiais agregadas`;
    const meta = [codigo, centrosTexto, filiaisTexto].filter(Boolean).join(' • ');
    const contaLabel = escapeHtml(conta.contaContabil || conta.descricaoContaContabil || 'Conta contábil');

    return `
        <tr class="luft-budget-analytic-account-row">
            <td class="luft-budget-structure-cell">
                <div class="luft-budget-tree-node luft-budget-tree-node--account">
                    <span class="luft-budget-tree-toggle is-static" aria-hidden="true">
                        <i class="ph-bold ph-minus"></i>
                    </span>
                    <span class="luft-budget-tree-icon luft-budget-tree-icon--account" aria-hidden="true">
                        <i class="ph-bold ph-receipt"></i>
                    </span>
                    <div class="luft-budget-tree-content">
                        <span class="luft-budget-tree-title">${contaLabel}</span>
                        <span class="luft-budget-tree-caption">${escapeHtml(meta)}</span>
                    </div>
                </div>
            </td>
            <td class="text-right">${formatarMoedaBudgetAnalitico(conta.realizado || 0)}</td>
            <td class="text-right">${formatarMoedaBudgetAnalitico(conta.orcado || 0)}</td>
            <td class="text-right">${renderizarDiferencaBudgetAnalitico(conta.diferenca || 0)}</td>
            <td>${renderizarConsumoBudgetAnalitico(conta.consumoPercentual, conta.orcado, conta.realizado)}</td>
        </tr>
    `;
}

function renderizarDiferencaBudgetAnalitico(valor) {
    const classe = valor < 0 ? 'is-negative' : 'is-positive';
    return `<span class="luft-budget-analytic-difference ${classe}">${formatarMoedaBudgetAnalitico(valor)}</span>`;
}

function obterPercentualBudgetAnalitico(orcado, valorExecutado) {
    return orcado > 0 ? (valorExecutado / orcado) * 100 : 0;
}

function obterContextoProgressBarBudgetAnalitico(percentual) {
    let corBarra = 'var(--luft-success-500)';
    let classeTexto = 'text-success';

    if (percentual >= 80 && percentual <= 100) {
        corBarra = 'var(--luft-warning-500)';
        classeTexto = 'text-warning';
    } else if (percentual > 100) {
        corBarra = 'var(--luft-danger-500)';
        classeTexto = 'text-danger';
    }

    return {
        larguraBarra: Math.min(percentual, 100),
        corBarra,
        classeTexto
    };
}

function renderizarConsumoBudgetAnalitico(valor, orcado = 0, valorExecutado = 0) {
    if ((valor === null || typeof valor === 'undefined') && Number(orcado || 0) <= 0) {
        return '<span class="luft-budget-analytic-consumption-empty">-</span>';
    }

    const percentualBase = valor === null || typeof valor === 'undefined'
        ? obterPercentualBudgetAnalitico(Number(orcado || 0), Number(valorExecutado || 0))
        : Number(valor || 0);
    const percentual = Math.max(0, percentualBase);
    const { larguraBarra, corBarra, classeTexto } = obterContextoProgressBarBudgetAnalitico(percentual);

    return `
        <div class="d-flex align-items-center gap-2" title="${percentual.toFixed(2)}% consumido">
            <div class="luft-budget-progress-track">
                <div class="luft-budget-progress-fill" style="width: ${larguraBarra}%; background-color: ${corBarra};"></div>
            </div>
            <span class="text-xs font-bold ${classeTexto}" style="min-width: 40px;">${percentual.toFixed(0)}%</span>
        </div>
    `;
}

function renderizarLoadingBudgetAnalitico() {
    const corpo = document.getElementById('corpoTabelaBudgetAnalitico');
    const rodape = document.getElementById('rodapeTabelaBudgetAnalitico');

    if (corpo) {
        corpo.innerHTML = `
            <tr>
                <td colspan="5" class="luft-budget-analytic-loading">Carregando dados analíticos...</td>
            </tr>
        `;
    }

    if (rodape) {
        rodape.innerHTML = '';
    }

    definirTexto('budgetAnaliticoStatusTabela', 'Atualizando dados do relatório analítico.');
}

function renderizarErroBudgetAnalitico(mensagem) {
    const corpo = document.getElementById('corpoTabelaBudgetAnalitico');
    const rodape = document.getElementById('rodapeTabelaBudgetAnalitico');

    if (corpo) {
        corpo.innerHTML = `
            <tr>
                <td colspan="5" class="luft-budget-analytic-empty">${escapeHtml(mensagem)}</td>
            </tr>
        `;
    }

    if (rodape) {
        rodape.innerHTML = '';
    }

    definirTexto('budgetAnaliticoStatusTabela', mensagem);
}

function definirTexto(id, valor) {
    const elemento = document.getElementById(id);
    if (elemento) {
        elemento.textContent = valor;
    }
}

function obterTextoOpcaoSelecionada(select) {
    if (!select || !select.options.length) {
        return '';
    }

    return select.options[select.selectedIndex]?.textContent || '';
}

function formatarMoedaBudgetAnalitico(valor) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    }).format(Number(valor || 0));
}

function formatarPercentualBudgetAnalitico(valor) {
    if (valor === null || typeof valor === 'undefined') {
        return '-';
    }
    // Aqui a porcetagem é formatada com no máximo 1 casa decimal para evitar poluição visual, já que o valor é apresentado em um badge pequeno ao lado da barra de consumo
    // EX: 75.3% ao invés de 75.34567%
    return `${new Intl.NumberFormat('pt-BR', {
        maximumFractionDigits: 1
    }).format(Number(valor || 0))}%`;
}

/*  
    Função para escapar caracteres especiais em HTML, prevenindo vulnerabilidades XSS e garantindo a 
    correta exibição de textos que possam conter caracteres como <, >, &, etc.
*/
 function escapeHtml(valor) {
    return String(valor ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}