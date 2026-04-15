/**
 * ============================================================================
 * LUFT CONTROL - RELATÓRIO DE BUDGET (MÓDULO GERENCIAL)
 * Arquivo: Static/JS/Reports/RelatorioBudget.js
 * Design System: LuftCore
 * ============================================================================
 */

document.addEventListener('DOMContentLoaded', () => {
    inicializarRelatorioBudget();
});

const COLSPAN_TABELA_BUDGET = 8;
const BUDGET_FILTER_RULES = {
    singleCentroCusto: true
};
const budgetTreeState = {
    mesesAtuais: [],
    modoSaldo: 'todos_itens',
    expandedMonths: new Set(),
    expandedCentersByMonth: new Map(),
    expandedAccountsByMonthAndCenter: new Map()
};
const budgetFilterState = {
    requestToken: 0,
    syncTimer: null,
    dataTimer: null,
    filtros: {
        centrosCusto: {
            items: [],
            selectedIds: new Set(),
            loaded: false,
            allSelected: false
        },
        contasContabeis: {
            items: [],
            selectedIds: new Set(),
            loaded: false,
            allSelected: true
        }
    }
};
const BUDGET_FILTER_CONFIG = {
    centrosCusto: {
        labelId: 'labelCentroCustoBudget',
        searchInputId: 'inputBuscaCentroCustoBudget',
        listId: 'listaCentroCustoBudget',
        selectAllId: 'checkTodosCentrosBudget',
        selectAllWrapperId: 'wrapCheckTodosCentrosBudget',
        emptyId: 'emptyCentroCustoBudget',
        emptyMessage: 'Nenhum centro de custo disponível.',
        paramName: 'centro_custo',
        allowMultiple: !BUDGET_FILTER_RULES.singleCentroCusto,
        emptyMeansAll: true,
        allLabel: 'Todos os centros',
        noneLabel: 'Nenhum centro selecionado',
        multipleLabel: 'centros selecionados',
        syncReloadData: false
    },
    contasContabeis: {
        labelId: 'labelContaContabilBudget',
        searchInputId: 'inputBuscaContaContabilBudget',
        listId: 'listaContaContabilBudget',
        selectAllId: 'checkTodasContasBudget',
        selectAllWrapperId: 'wrapCheckTodasContasBudget',
        emptyId: 'emptyContaContabilBudget',
        emptyMessage: 'Nenhuma conta contábil disponível.',
        paramName: 'conta_contabil',
        allowMultiple: true,
        emptyMeansAll: false,
        allLabel: 'Todas as contas',
        noneLabel: 'Nenhuma conta selecionada',
        multipleLabel: 'contas selecionadas',
        syncReloadData: true
    }
};
const BUDGET_SELECTOR_CONFIG = {
    centrosCusto: {
        panelId: 'painelCentroCustoBudget',
        triggerId: 'btnSelectorCentroCustoBudget',
        spinnerId: 'spinnerCentroCustoBudget'
    },
    contasContabeis: {
        panelId: 'painelContaContabilBudget',
        triggerId: 'btnSelectorContaContabilBudget',
        spinnerId: 'spinnerContaContabilBudget'
    }
};
const BUDGET_API_ROUTES = window.BUDGET_API_ROUTES || {
    filtros: '/budget/filtros',
    gerencial: '/budget/gerencial'
};

function construirUrlBudget(chaveRota, params = {}) {
    const rota = BUDGET_API_ROUTES[chaveRota] || BUDGET_API_ROUTES.gerencial;
    const url = new URL(rota, window.location.origin);

    Object.entries(params).forEach(([chave, valor]) => {
        url.searchParams.set(chave, valor);
    });

    return url.toString();
}

async function obterJsonBudget(url, opcoes = {}) {
    const resposta = await fetch(url, opcoes);
    const contentType = resposta.headers.get('content-type') || '';

    if (contentType.includes('application/json')) {
        const retorno = await resposta.json();

        if (!resposta.ok) {
            throw new Error(retorno.message || retorno.msg || `Falha HTTP ${resposta.status}`);
        }

        return retorno;
    }

    throw new Error(`Resposta inválida do servidor (${resposta.status}).`);
}

/**
 * Vincula os eventos e carrega os dados primários da tela.
 */
function inicializarRelatorioBudget() {
    const inputAno = document.getElementById('inputAnoBudget');
    const selectModoSaldo = document.getElementById('selectModoSaldoBudget');
    const selectEmpresa = document.getElementById('selectEmpresaBudget');

    if (!inputAno) return;

    budgetTreeState.modoSaldo = selectModoSaldo ? selectModoSaldo.value : 'todos_itens';

    configurarControlesTabelaBudget();
    atualizarStatusArvoreBudget([]);
    configurarFiltrosBudget();

    // Triggers dos seletores dropdown
    Object.keys(BUDGET_SELECTOR_CONFIG).forEach((chave) => {
        const cfg = BUDGET_SELECTOR_CONFIG[chave];
        const trigger = document.getElementById(cfg.triggerId);
        if (trigger && !trigger.dataset.bound) {
            trigger.addEventListener('click', () => alternarPainelFiltroBudget(chave));
            trigger.dataset.bound = 'true';
        }
    });

    // Fechar painéis ao clicar fora
    document.addEventListener('click', (event) => {
        const clicouDentroDeAlgumSeletor = Object.values(BUDGET_SELECTOR_CONFIG).some((cfg) => {
            const seletor = document.getElementById(cfg.triggerId)?.closest('.luft-baf-selector');
            return seletor && seletor.contains(event.target);
        });
        if (!clicouDentroDeAlgumSeletor) {
            fecharTodosPainesFIltroBudget();
        }
    });

    if (inputAno && !inputAno.dataset.filterBound) {
        inputAno.addEventListener('change', () => agendarSincronizacaoFiltrosBudget());
        inputAno.dataset.filterBound = 'true';
    }

    if (selectEmpresa && !selectEmpresa.dataset.filterBound) {
        selectEmpresa.addEventListener('change', () => agendarSincronizacaoFiltrosBudget());
        selectEmpresa.dataset.filterBound = 'true';
    }

    if (selectModoSaldo && !selectModoSaldo.dataset.filterBound) {
        selectModoSaldo.addEventListener('change', () => {
            budgetTreeState.modoSaldo = selectModoSaldo.value;
            agendarRecarregarDadosBudget();
        });
        selectModoSaldo.dataset.filterBound = 'true';
    }

    const selectMes = document.getElementById('selectMesBudget');
    if (selectMes && !selectMes.dataset.filterBound) {
        selectMes.addEventListener('change', () => agendarRecarregarDadosBudget());
        selectMes.dataset.filterBound = 'true';
    }

    // Carrega filtros e dispara a busca inicial
    sincronizarFiltrosBudget().then(() => {
        atualizarChipsBudget();
        carregarDadosBudget();
    });
}

function abrirPainelFiltroBudget(chave) {
    const cfg = BUDGET_SELECTOR_CONFIG[chave];
    if (!cfg) return;

    const painel = document.getElementById(cfg.panelId);
    const trigger = document.getElementById(cfg.triggerId);
    if (!painel || !trigger) return;

    painel.classList.remove('d-none');
    trigger.classList.add('is-open');
    trigger.setAttribute('aria-expanded', 'true');
}

function fecharPainelFiltroBudget(chave) {
    const cfg = BUDGET_SELECTOR_CONFIG[chave];
    if (!cfg) return;

    const painel = document.getElementById(cfg.panelId);
    const trigger = document.getElementById(cfg.triggerId);
    if (!painel || !trigger) return;

    painel.classList.add('d-none');
    trigger.classList.remove('is-open');
    trigger.setAttribute('aria-expanded', 'false');
}

function fecharTodosPainesFIltroBudget() {
    Object.keys(BUDGET_SELECTOR_CONFIG).forEach((chave) => fecharPainelFiltroBudget(chave));
}

function alternarPainelFiltroBudget(chave) {
    const cfg = BUDGET_SELECTOR_CONFIG[chave];
    if (!cfg) return;

    const painel = document.getElementById(cfg.panelId);
    const aberto = painel && !painel.classList.contains('d-none');

    fecharTodosPainesFIltroBudget();

    if (!aberto) {
        abrirPainelFiltroBudget(chave);
    }
}

function definirEstadoCarregandoFiltrosBudget(carregando) {
    ['spinnerAnoBudget', 'spinnerEmpresaBudget'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.classList.toggle('d-none', !carregando);
    });

    Object.keys(BUDGET_SELECTOR_CONFIG).forEach((chave) => {
        const cfg = BUDGET_SELECTOR_CONFIG[chave];
        const trigger = document.getElementById(cfg.triggerId);
        const spinner = document.getElementById(cfg.spinnerId);
        if (trigger) trigger.classList.toggle('is-loading', carregando);
        if (spinner) spinner.classList.toggle('d-none', !carregando);
    });
}

function agendarRecarregarDadosBudget() {
    clearTimeout(budgetFilterState.dataTimer);
    budgetFilterState.dataTimer = setTimeout(() => {
        carregarDadosBudget();
    }, 400);
}

function aplicarFiltrosBudget() {
    carregarDadosBudget();
}

function configurarControlesTabelaBudget() {
    const corpoTabela = document.getElementById('corpoTabelaBudget');
    const btnExpandirTodos = document.getElementById('btnExpandirTodosBudget');
    const btnRecolherTodos = document.getElementById('btnRecolherTodosBudget');

    if (corpoTabela && !corpoTabela.dataset.treeBound) {
        corpoTabela.addEventListener('click', (event) => {
            const botaoConta = event.target.closest('[data-budget-account-toggle]');
            if (botaoConta) {
                const numeroMes = Number(botaoConta.dataset.budgetMonth);
                const centroCusto = decodeURIComponent(botaoConta.dataset.budgetCenter);
                const contaContabil = decodeURIComponent(botaoConta.dataset.budgetAccountToggle);
                alternarContaContabilBudget(numeroMes, centroCusto, contaContabil);
                return;
            }

            const botaoCentro = event.target.closest('[data-budget-center-toggle]');
            if (botaoCentro) {
                const numeroMes = Number(botaoCentro.dataset.budgetMonth);
                const centroCusto = decodeURIComponent(botaoCentro.dataset.budgetCenterToggle);
                alternarCentroCustoBudget(numeroMes, centroCusto);
                return;
            }

            const botaoMes = event.target.closest('[data-budget-month-toggle]');
            if (botaoMes) {
                alternarMesBudget(Number(botaoMes.dataset.budgetMonthToggle));
                return;
            }

            const linhaMes = event.target.closest('[data-budget-month-row]');
            if (!linhaMes) return;

            alternarMesBudget(Number(linhaMes.dataset.budgetMonthRow));
        });

        corpoTabela.dataset.treeBound = 'true';
    }

    if (btnExpandirTodos && !btnExpandirTodos.dataset.bound) {
        btnExpandirTodos.addEventListener('click', expandirArvoreBudgetEmFases);
        btnExpandirTodos.dataset.bound = 'true';
    }

    if (btnRecolherTodos && !btnRecolherTodos.dataset.bound) {
        btnRecolherTodos.addEventListener('click', recolherArvoreBudgetEmFases);
        btnRecolherTodos.dataset.bound = 'true';
    }
}

function normalizarTextoBudget(texto) {
    return String(texto ?? '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase();
}

function obterConfiguracaoFiltroBudget(chaveFiltro) {
    return BUDGET_FILTER_CONFIG[chaveFiltro];
}

function obterEstadoFiltroBudget(chaveFiltro) {
    return budgetFilterState.filtros[chaveFiltro];
}

function escaparRegexBudget(texto) {
    return String(texto || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function obterNomeContaContabilBudget(item) {
    const textoBase = String(item?.nome || item?.descricao || item?.id || '').trim();

    if (!textoBase) {
        return '';
    }

    const codigo = String(item?.codigo || '').trim();

    if (codigo) {
        const regexCodigo = new RegExp(`^\\s*${escaparRegexBudget(codigo)}\\s*-\\s*`, 'i');
        const semCodigoExplicito = textoBase.replace(regexCodigo, '').trim();

        if (semCodigoExplicito) {
            return semCodigoExplicito;
        }
    }

    const semPrefixoNumerico = textoBase.replace(/^\s*\d+(?:\.\d+)*(?:\s*-\s*)?/, '').trim();
    return semPrefixoNumerico || textoBase;
}

function formatarTextoOpcaoFiltroBudget(chaveFiltro, item) {
    if (chaveFiltro === 'contasContabeis') {
        const nomeConta = obterNomeContaContabilBudget(item);

        if (nomeConta) {
            return nomeConta;
        }

        if (item.codigo && item.descricao) {
            return `${item.codigo} - ${item.descricao}`;
        }

        return item.descricao || item.codigo || item.id;
    }

    if (item.codigo && item.nome) {
        return `${item.codigo} - ${item.nome}`;
    }

    return item.nome || item.codigo || item.id;
}


function obterTituloOpcaoFiltroBudget(chaveFiltro, item) {
    if (chaveFiltro === 'contasContabeis') {
        return obterNomeContaContabilBudget(item) || item.descricao || item.id;
    }

    return item.nome || item.id;
}

function obterCodigoOpcaoFiltroBudget(chaveFiltro, item) {
    if (chaveFiltro === 'contasContabeis') {
        return item.codigo ? `Conta ${item.codigo}` : 'Conta contábil';
    }

    return item.codigo ? `CC ${item.codigo}` : 'Centro de custo';
}

function obterMetaOpcaoFiltroBudget(chaveFiltro, item) {
    if (chaveFiltro === 'contasContabeis') {
        return item.descricao || 'Conta disponível para o contexto selecionado.';
    }

    return item.codigo
        ? `Código ${item.codigo}`
        : 'Centro disponível para o contexto selecionado.';
}

function configurarFiltrosBudget() {
    Object.keys(BUDGET_FILTER_CONFIG).forEach((chaveFiltro) => {
        configurarFiltroBudget(chaveFiltro);
    });
}

function configurarFiltroBudget(chaveFiltro) {
    const config = obterConfiguracaoFiltroBudget(chaveFiltro);
    const campoBusca = document.getElementById(config.searchInputId);
    const lista = document.getElementById(config.listId);
    const checkboxTodos = document.getElementById(config.selectAllId);

    if (campoBusca && !campoBusca.dataset.bound) {
        campoBusca.addEventListener('input', () => {
            aplicarBuscaFiltroBudget(chaveFiltro);
        });
        campoBusca.dataset.bound = 'true';
    }

    if (checkboxTodos && !checkboxTodos.dataset.bound) {
        checkboxTodos.addEventListener('change', (event) => {
            atualizarSelecaoTotalFiltroBudget(chaveFiltro, event.target.checked);
        });
        checkboxTodos.dataset.bound = 'true';
    }

    if (lista && !lista.dataset.bound) {
        lista.addEventListener('change', (event) => {
            const checkbox = event.target.closest('.luft-budget-filter-checkbox');
            if (!checkbox) return;

            atualizarSelecaoFiltroBudget(chaveFiltro, checkbox.value, checkbox.checked);
        });
        lista.dataset.bound = 'true';
    }
}

function sincronizarFiltrosBudget() {
    const inputAno = document.getElementById('inputAnoBudget');
    const selectEmpresa = document.getElementById('selectEmpresaBudget');

    if (!inputAno) {
        return Promise.resolve();
    }

    const ano = inputAno.value || new Date().getFullYear();
    const empresa = selectEmpresa ? selectEmpresa.value : 'Todos';
    const centroCusto = obterParametroFiltroBudget('centrosCusto', { ignorarVazio: true });
    const contaContabil = obterParametroFiltroBudget('contasContabeis', { ignorarVazio: true });
    const requestToken = ++budgetFilterState.requestToken;

    definirEstadoCarregandoFiltrosBudget(true);

    return obterJsonBudget(construirUrlBudget('filtros', {
        ano,
        empresa,
        centro_custo: centroCusto,
        conta_contabil: contaContabil
    }), {
        method: 'GET',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then((retorno) => {
        definirEstadoCarregandoFiltrosBudget(false);

        if (requestToken !== budgetFilterState.requestToken) {
            return;
        }

        const centroAutoSelecionado = renderizarOpcoesFiltroBudget('centrosCusto', retorno.data?.centrosCusto || []);
        renderizarOpcoesFiltroBudget('contasContabeis', retorno.data?.contasContabeis || []);

        if (centroAutoSelecionado) {
            agendarSincronizacaoFiltrosBudget();
        }
    })
    .catch((erro) => {
        definirEstadoCarregandoFiltrosBudget(false);
        console.error('Erro ao carregar os filtros:', erro);
    });
}

function renderizarOpcoesFiltroBudget(chaveFiltro, listaOpcoes) {
    const config = obterConfiguracaoFiltroBudget(chaveFiltro);
    const estado = obterEstadoFiltroBudget(chaveFiltro);
    const lista = document.getElementById(config.listId);

    if (!lista) return;

    const opcoes = (Array.isArray(listaOpcoes) ? listaOpcoes : []).map((item) => ({
        ...item,
        id: String(item.id)
    }));
    const idsDisponiveis = new Set(opcoes.map((item) => item.id));
    const selecaoAnterior = Array.from(estado.selectedIds);
    let selecionados = new Set();
    let autoSelecionado = false;

    if (opcoes.length > 0) {
        if (!estado.loaded) {
            selecionados = config.allowMultiple ? new Set(opcoes.map((item) => item.id)) : new Set();
        } else if (config.allowMultiple && estado.allSelected) {
            selecionados = new Set(opcoes.map((item) => item.id));
        } else {
            selecionados = new Set(
                Array.from(estado.selectedIds).filter((idSelecionado) => idsDisponiveis.has(idSelecionado))
            );

            if (!config.allowMultiple && selecionados.size > 1) {
                selecionados = new Set([Array.from(selecionados)[0]]);
            }
        }

        if (!config.allowMultiple && selecionados.size === 0 && opcoes.length === 1) {
            selecionados = new Set([opcoes[0].id]);
            autoSelecionado = selecaoAnterior[0] !== opcoes[0].id;
        }
    }

    estado.items = opcoes;
    estado.selectedIds = selecionados;
    estado.loaded = true;
    estado.allSelected = config.allowMultiple && opcoes.length > 0 && selecionados.size === opcoes.length;

    lista.innerHTML = opcoes.map((item) => {
        const texto = formatarTextoOpcaoFiltroBudget(chaveFiltro, item);
        const titulo = obterTituloOpcaoFiltroBudget(chaveFiltro, item);
        const codigo = obterCodigoOpcaoFiltroBudget(chaveFiltro, item);
        const meta = obterMetaOpcaoFiltroBudget(chaveFiltro, item);
        const textoBusca = normalizarTextoBudget(`${item.codigo || ''} ${item.nome || ''} ${item.descricao || ''} ${texto} ${titulo} ${meta}`);
        const marcado = estado.selectedIds.has(item.id) ? 'checked' : '';
        const classeSelecionado = estado.selectedIds.has(item.id) ? 'is-selected' : '';

        return `
            <label class="luft-budget-filter-option ${classeSelecionado}" data-search="${escaparHtml(textoBusca)}">
                <input type="checkbox" class="luft-budget-filter-checkbox" value="${escaparHtml(item.id)}" ${marcado}>
                <div class="luft-budget-filter-option-body">
                    <span class="luft-budget-filter-option-code">${escaparHtml(codigo)}</span>
                    <span class="luft-budget-filter-option-title">${escaparHtml(titulo)}</span>
                </div>
            </label>`;
    }).join('');

    atualizarResumoFiltroBudget(chaveFiltro);
    aplicarBuscaFiltroBudget(chaveFiltro);
    return autoSelecionado;
}

function atualizarSelecaoFiltroBudget(chaveFiltro, idItem, marcado) {
    const config = obterConfiguracaoFiltroBudget(chaveFiltro);
    const estado = obterEstadoFiltroBudget(chaveFiltro);
    const idNormalizado = String(idItem);

    if (config.allowMultiple) {
        if (marcado) {
            estado.selectedIds.add(idNormalizado);
        } else {
            estado.selectedIds.delete(idNormalizado);
        }
    } else {
        estado.selectedIds = marcado ? new Set([idNormalizado]) : new Set();
    }

    estado.allSelected = config.allowMultiple && estado.items.length > 0 && estado.selectedIds.size === estado.items.length;
    sincronizarMarcacaoFiltroBudget(chaveFiltro);
    atualizarResumoFiltroBudget(chaveFiltro);

    if (config.syncReloadData) {
        agendarRecarregarDadosBudget();
    } else {
        agendarSincronizacaoFiltrosBudget();
    }
}

function atualizarSelecaoTotalFiltroBudget(chaveFiltro, marcado) {
    const config = obterConfiguracaoFiltroBudget(chaveFiltro);
    const estado = obterEstadoFiltroBudget(chaveFiltro);

    if (!config.allowMultiple) {
        return;
    }

    estado.selectedIds = marcado
        ? new Set(estado.items.map((item) => item.id))
        : new Set();
    estado.allSelected = marcado && estado.items.length > 0;

    sincronizarMarcacaoFiltroBudget(chaveFiltro);

    atualizarResumoFiltroBudget(chaveFiltro);

    if (config.syncReloadData) {
        agendarRecarregarDadosBudget();
    } else {
        agendarSincronizacaoFiltrosBudget();
    }
}

function sincronizarMarcacaoFiltroBudget(chaveFiltro) {
    const config = obterConfiguracaoFiltroBudget(chaveFiltro);
    const estado = obterEstadoFiltroBudget(chaveFiltro);
    const lista = document.getElementById(config.listId);

    if (!lista) {
        return;
    }

    lista.querySelectorAll('.luft-budget-filter-checkbox').forEach((checkbox) => {
        const marcado = estado.selectedIds.has(String(checkbox.value));
        checkbox.checked = marcado;
        checkbox.closest('.luft-budget-filter-option')?.classList.toggle('is-selected', marcado);
    });
}

function aplicarBuscaFiltroBudget(chaveFiltro) {
    const config = obterConfiguracaoFiltroBudget(chaveFiltro);
    const lista = document.getElementById(config.listId);
    const campoBusca = document.getElementById(config.searchInputId);
    const mensagemVazia = document.getElementById(config.emptyId);

    if (!lista || !campoBusca || !mensagemVazia) return;

    const termo = normalizarTextoBudget(campoBusca.value);
    let totalVisivel = 0;

    lista.querySelectorAll('.luft-budget-filter-option').forEach((opcao) => {
        const corresponde = !termo || opcao.dataset.search.includes(termo);
        opcao.classList.toggle('d-none', !corresponde);
        if (corresponde) {
            totalVisivel += 1;
        }
    });

    mensagemVazia.textContent = obterEstadoFiltroBudget(chaveFiltro).items.length === 0
        ? config.emptyMessage
        : 'Nenhuma opção encontrada para a pesquisa informada.';
    mensagemVazia.classList.toggle('d-none', totalVisivel > 0);
}

function atualizarResumoFiltroBudget(chaveFiltro) {
    const config = obterConfiguracaoFiltroBudget(chaveFiltro);
    const estado = obterEstadoFiltroBudget(chaveFiltro);
    const label = document.getElementById(config.labelId);
    const checkboxTodos = document.getElementById(config.selectAllId);
    const wrapper = document.getElementById(config.selectAllWrapperId);
    const total = estado.items.length;
    const selecionados = estado.selectedIds.size;

    if (label) {
        label.textContent = obterDescricaoSelecaoFiltroBudget(chaveFiltro);
    }

    if (wrapper) {
        wrapper.classList.toggle('d-none', !config.allowMultiple || total === 0);
    }

    if (checkboxTodos) {
        checkboxTodos.checked = config.allowMultiple && total > 0 && selecionados === total;
        checkboxTodos.indeterminate = config.allowMultiple && selecionados > 0 && selecionados < total;
        checkboxTodos.disabled = !config.allowMultiple || total === 0;
    }
}

function obterDescricaoSelecaoFiltroBudget(chaveFiltro) {
    const config = obterConfiguracaoFiltroBudget(chaveFiltro);
    const estado = obterEstadoFiltroBudget(chaveFiltro);
    const total = estado.items.length;
    const selecionados = estado.selectedIds.size;

    if (total === 0) {
        return 'Sem opções';
    }

    if (config.allowMultiple && selecionados === total) {
        return config.allLabel;
    }

    if (selecionados === 0) {
        return config.emptyMeansAll ? config.allLabel : config.noneLabel;
    }

    if (selecionados === 1) {
        const selecionado = estado.items.find((item) => estado.selectedIds.has(item.id));
        return selecionado ? formatarTextoOpcaoFiltroBudget(chaveFiltro, selecionado) : config.noneLabel;
    }

    return `${selecionados} ${config.multipleLabel}`;
}

function obterParametroFiltroBudget(chaveFiltro, { ignorarVazio = false } = {}) {
    const config = obterConfiguracaoFiltroBudget(chaveFiltro);
    const estado = obterEstadoFiltroBudget(chaveFiltro);

    if (!estado.loaded) {
        return 'Todos';
    }

    if (estado.items.length === 0) {
        return config.emptyMeansAll || ignorarVazio ? 'Todos' : '-999';
    }

    if (estado.selectedIds.size === 0) {
        return config.emptyMeansAll || ignorarVazio ? 'Todos' : '-999';
    }

    if (config.allowMultiple && estado.selectedIds.size === estado.items.length) {
        return 'Todos';
    }

    return Array.from(estado.selectedIds).join(',');
}

function agendarSincronizacaoFiltrosBudget() {
    clearTimeout(budgetFilterState.syncTimer);
    budgetFilterState.syncTimer = setTimeout(async () => {
        await sincronizarFiltrosBudget();
        carregarDadosBudget();
    }, 350);
}

/**
 * Coleta os filtros e consulta a API de dados.
 */
function carregarDadosBudget() {
    const inputAno = document.getElementById('inputAnoBudget');
    const selectEmpresa = document.getElementById('selectEmpresaBudget');
    const selectModoSaldo = document.getElementById('selectModoSaldoBudget');
    const corpoTabela = document.getElementById('corpoTabelaBudget');
    
    if (!inputAno || !corpoTabela) return;

    budgetTreeState.modoSaldo = selectModoSaldo ? selectModoSaldo.value : 'todos_itens';

    const ano = inputAno.value;
    const empresa = selectEmpresa ? selectEmpresa.value : 'Todos';
    const conta = obterParametroFiltroBudget('contasContabeis');
    const ccParam = obterParametroFiltroBudget('centrosCusto');

    atualizarChipsBudget();

    limparRodapeTabelaBudget();

    corpoTabela.innerHTML = `
        <tr>
            <td colspan="${COLSPAN_TABELA_BUDGET}" class="text-center py-10">
                <div class="d-flex flex-col align-items-center justify-content-center">
                    <i class="ph-bold ph-spinner-gap luft-spin text-primary text-4xl"></i>
                    <p class="text-muted mt-3 font-medium">Processando estrutura orçamentária...</p>
                </div>
            </td>
        </tr>`;

    obterJsonBudget(construirUrlBudget('gerencial', {
        ano,
        empresa,
        centro_custo: ccParam,
        conta_contabil: conta
    }), {
        method: 'GET',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(retorno => {
        const selectMes = document.getElementById('selectMesBudget');
        const mesSelecionado = selectMes ? parseInt(selectMes.value, 10) : 0;
        const meses = Array.isArray(retorno.data?.meses) ? retorno.data.meses : [];
        const mesesFiltrados = mesSelecionado > 0 ? meses.filter(m => m.mes === mesSelecionado) : meses;
        renderizarTabelaBudget(mesesFiltrados, corpoTabela);
    })
    .catch(erro => {
        console.error('Falha ao obter dados:', erro);
        corpoTabela.innerHTML = `<tr><td colspan="${COLSPAN_TABELA_BUDGET}" class="text-center text-danger py-6 font-bold">${escaparHtml(erro.message || 'Falha na comunicação com o servidor.')}</td></tr>`;
    });
}

function atualizarChipsBudget() {
    const inputAno = document.getElementById('inputAnoBudget');
    const selectEmpresa = document.getElementById('selectEmpresaBudget');
    const selectModoSaldo = document.getElementById('selectModoSaldoBudget');
    const selectMes = document.getElementById('selectMesBudget');

    definirTextoBudget('chipAnoBudget', `Ano ${inputAno?.value || new Date().getFullYear()}`);
    definirTextoBudget('chipMesBudget', obterTextoOpcaoSelecionadaBudget(selectMes) || 'Todos os meses');
    definirTextoBudget('chipEmpresaBudget', obterTextoOpcaoSelecionadaBudget(selectEmpresa) || 'Todas as Empresas');
    definirTextoBudget('chipCentroBudget', obterDescricaoSelecaoFiltroBudget('centrosCusto'));
    definirTextoBudget('chipContaBudget', obterDescricaoSelecaoFiltroBudget('contasContabeis'));
    definirTextoBudget('chipModoSaldoBudget', obterTextoOpcaoSelecionadaBudget(selectModoSaldo) || 'Modo de saldo');
}

function definirTextoBudget(id, valor) {
    const elemento = document.getElementById(id);
    if (elemento) {
        elemento.textContent = valor;
    }
}

function obterTextoOpcaoSelecionadaBudget(select) {
    if (!select || !select.options.length) {
        return '';
    }

    return select.options[select.selectedIndex]?.textContent || '';
}

/**
 * Atualiza os indicadores superiores de performance.
 */
function atualizarKpis(listaDados) {
    let totalOrcado = 0;
    let totalGeral = 0;

    listaDados.forEach(mes => {
        totalOrcado += Number(mes.orcado) || 0;
        totalGeral += Number(mes.total) || 0;
    });

    const totalSaldo = totalOrcado - totalGeral;
    const percentualConsumo = totalOrcado > 0 ? (totalGeral / totalOrcado) * 100 : 0;

    const fmt = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

    document.getElementById('kpiOrcado').textContent = fmt.format(totalOrcado);
    document.getElementById('kpiTotal').textContent = fmt.format(totalGeral);
    
    const kpiSaldo = document.getElementById('kpiSaldo');
    const iconeSaldoCont = document.getElementById('iconeSaldoContainer');
    const iconeSaldo = document.getElementById('iconeSaldo');

    kpiSaldo.textContent = fmt.format(totalSaldo);
    
    if (totalSaldo < 0) {
        kpiSaldo.className = "text-xl font-black text-danger m-0";
        iconeSaldoCont.className = "d-flex align-items-center justify-content-center rounded-xl bg-danger-light text-danger";
        iconeSaldo.className = "ph-bold ph-warning-circle";
    } else {
        kpiSaldo.className = "text-xl font-black text-success m-0";
        iconeSaldoCont.className = "d-flex align-items-center justify-content-center rounded-xl bg-success-light text-success";
        iconeSaldo.className = "ph-bold ph-piggy-bank";
    }

    const kpiConsumo = document.getElementById('kpiConsumo');
    kpiConsumo.textContent = percentualConsumo.toFixed(1) + '%';
    kpiConsumo.className = percentualConsumo > 100 ? "text-xl font-black text-danger m-0" : "text-xl font-black text-main m-0";
}

function escaparHtml(texto) {
    return String(texto ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function obterPercentualBudget(orcado, valorExecutado) {
    return orcado > 0 ? (valorExecutado / orcado) * 100 : 0;
}

function obterContextoProgressBar(percentual) {
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

function gerarCelulaProgressoBudget(percentual) {
    const { larguraBarra, corBarra, classeTexto } = obterContextoProgressBar(percentual);

    return `
        <div class="d-flex align-items-center gap-2" title="${percentual.toFixed(2)}% consumido">
            <div class="luft-budget-progress-track">
                <div class="luft-budget-progress-fill" style="width: ${larguraBarra}%; background-color: ${corBarra};"></div>
            </div>
            <span class="text-xs font-bold ${classeTexto}" style="min-width: 40px;">${percentual.toFixed(0)}%</span>
        </div>`;
}

function gerarCelulaSaldoAcumuladoDetalhe() {
    return '<span class="text-muted font-medium">-</span>';
}

function compararTextoBudget(valorA, valorB) {
    return String(valorA || '').localeCompare(String(valorB || ''), 'pt-BR', { sensitivity: 'base' });
}

function agruparDadosPorCentroCusto(listaDados) {
    const grupos = new Map();

    listaDados.forEach(linha => {
        const centroCusto = linha.centroCusto || 'Não Classificado';
        const contaContabil = linha.contaContabil || 'Não Classificada';
        const fornecedor = linha.fornecedor || 'Sem fornecedor vinculado';
        const orcado = Number(linha.orcado) || 0;
        const emAprovacao = Number(linha.emAprovacao) || 0;
        const aprovado = Number(linha.aprovado) || 0;
        const total = Number(linha.total) || 0;

        if (!grupos.has(centroCusto)) {
            grupos.set(centroCusto, {
                centroCusto,
                orcado: 0,
                emAprovacao: 0,
                aprovado: 0,
                total: 0,
                contasMap: new Map()
            });
        }

        const grupo = grupos.get(centroCusto);
        grupo.orcado += orcado;
        grupo.emAprovacao += emAprovacao;
        grupo.aprovado += aprovado;
        grupo.total += total;

        if (!grupo.contasMap.has(contaContabil)) {
            grupo.contasMap.set(contaContabil, {
                contaContabil,
                orcado: 0,
                emAprovacao: 0,
                aprovado: 0,
                total: 0,
                fornecedoresMap: new Map()
            });
        }

        const conta = grupo.contasMap.get(contaContabil);
        conta.orcado += orcado;
        conta.emAprovacao += emAprovacao;
        conta.aprovado += aprovado;
        conta.total += total;

        if (!conta.fornecedoresMap.has(fornecedor)) {
            conta.fornecedoresMap.set(fornecedor, {
                fornecedor,
                orcado: 0,
                emAprovacao: 0,
                aprovado: 0,
                total: 0,
                saldo: 0
            });
        }

        const fornecedorAtual = conta.fornecedoresMap.get(fornecedor);
        fornecedorAtual.orcado += orcado;
        fornecedorAtual.emAprovacao += emAprovacao;
        fornecedorAtual.aprovado += aprovado;
        fornecedorAtual.total += total;
        fornecedorAtual.saldo = fornecedorAtual.orcado - fornecedorAtual.total;
        conta.saldo = conta.orcado - conta.total;
    });

    return Array.from(grupos.values())
        .map(grupo => ({
            centroCusto: grupo.centroCusto,
            orcado: grupo.orcado,
            emAprovacao: grupo.emAprovacao,
            aprovado: grupo.aprovado,
            total: grupo.total,
            saldo: grupo.orcado - grupo.total,
            contas: Array.from(grupo.contasMap.values())
                .map(conta => ({
                    contaContabil: conta.contaContabil,
                    orcado: conta.orcado,
                    emAprovacao: conta.emAprovacao,
                    aprovado: conta.aprovado,
                    total: conta.total,
                    saldo: conta.orcado - conta.total,
                    fornecedores: Array.from(conta.fornecedoresMap.values())
                        .sort((a, b) => compararTextoBudget(a.fornecedor, b.fornecedor))
                }))
                .sort((a, b) => compararTextoBudget(a.contaContabil, b.contaContabil))
        }))
        .sort((a, b) => compararTextoBudget(a.centroCusto, b.centroCusto));
}

function obterDescricaoQuantidadeContas(totalContas) {
    return totalContas === 1 ? '1 conta contábil' : `${totalContas} contas contábeis`;
}

function obterDescricaoQuantidadeFornecedores(totalFornecedores) {
    return totalFornecedores === 1 ? '1 fornecedor' : `${totalFornecedores} fornecedores`;
}

function obterDescricaoQuantidadeCentros(totalCentros) {
    return totalCentros === 1 ? '1 centro de custo' : `${totalCentros} centros de custo`;
}

function obterMapaContasExpandidasPorMes(numeroMes) {
    if (!budgetTreeState.expandedAccountsByMonthAndCenter.has(numeroMes)) {
        budgetTreeState.expandedAccountsByMonthAndCenter.set(numeroMes, new Map());
    }

    return budgetTreeState.expandedAccountsByMonthAndCenter.get(numeroMes);
}

function obterContasExpandidasPorCentro(numeroMes, centroCusto) {
    const contasPorCentro = obterMapaContasExpandidasPorMes(numeroMes);

    if (!contasPorCentro.has(centroCusto)) {
        contasPorCentro.set(centroCusto, new Set());
    }

    return contasPorCentro.get(centroCusto);
}

function obterValoresStatusLinhaBudget(linha) {
    const emAprovacaoBase = Number(linha.emAprovacao) || 0;
    const aprovadoBase = Number(linha.aprovado) || 0;
    const totalBaseInformado = Number(linha.total);
    const totalBase = Number.isFinite(totalBaseInformado)
        ? totalBaseInformado
        : emAprovacaoBase + aprovadoBase;

    const emAprovacaoComBudgetInformado = Number(linha.emAprovacaoComBudget);
    const aprovadoComBudgetInformado = Number(linha.aprovadoComBudget);
    const totalComBudgetInformado = Number(linha.totalComBudget);

    const emAprovacaoComBudget = Number.isFinite(emAprovacaoComBudgetInformado)
        ? emAprovacaoComBudgetInformado
        : emAprovacaoBase;
    const aprovadoComBudget = Number.isFinite(aprovadoComBudgetInformado)
        ? aprovadoComBudgetInformado
        : aprovadoBase;
    const totalComBudget = Number.isFinite(totalComBudgetInformado)
        ? totalComBudgetInformado
        : emAprovacaoComBudget + aprovadoComBudget;
    const usarTodosItens = budgetTreeState.modoSaldo === 'todos_itens';

    return {
        emAprovacao: usarTodosItens ? emAprovacaoBase : emAprovacaoComBudget,
        aprovado: usarTodosItens ? aprovadoBase : aprovadoComBudget,
        total: usarTodosItens ? totalBase : totalComBudget,
        emAprovacaoBase,
        aprovadoBase,
        totalBase,
        emAprovacaoComBudget,
        aprovadoComBudget,
        totalComBudget
    };
}

function prepararDetalhesMesBudget(listaDetalhes) {
    return (Array.isArray(listaDetalhes) ? listaDetalhes : [])
        .map((linha) => {
            const orcado = Number(linha.orcado) || 0;
            const {
                emAprovacao,
                aprovado,
                total,
                emAprovacaoBase,
                aprovadoBase,
                totalBase,
                emAprovacaoComBudget,
                aprovadoComBudget,
                totalComBudget
            } = obterValoresStatusLinhaBudget(linha);

            return {
                ...linha,
                orcado,
                emAprovacao,
                aprovado,
                total,
                emAprovacaoBase,
                aprovadoBase,
                totalBase,
                emAprovacaoComBudget,
                aprovadoComBudget,
                totalComBudget,
                saldo: orcado - total,
                saldoTotal: orcado - totalBase,
                saldoComBudget: orcado - totalComBudget
            };
        })
        .filter((linha) => linha.orcado !== 0 || linha.total !== 0);
}

function prepararMesesBudget(listaMeses) {
    let saldoAcumulado = 0;

    return (Array.isArray(listaMeses) ? listaMeses : [])
        .map((mesInfo) => {
            const detalhes = prepararDetalhesMesBudget(mesInfo.detalhes);
            const grupos = agruparDadosPorCentroCusto(detalhes);
            const orcado = detalhes.reduce((acumulado, linha) => acumulado + linha.orcado, 0);
            const emAprovacao = detalhes.reduce((acumulado, linha) => acumulado + linha.emAprovacao, 0);
            const aprovado = detalhes.reduce((acumulado, linha) => acumulado + linha.aprovado, 0);
            const total = detalhes.reduce((acumulado, linha) => acumulado + linha.total, 0);

            return {
                ...mesInfo,
                detalhes,
                grupos,
                orcado,
                emAprovacao,
                aprovado,
                total,
                saldo: orcado - total,
                centrosCusto: grupos.length
            };
        })
        .sort((mesA, mesB) => (Number(mesA.mes) || 0) - (Number(mesB.mes) || 0))
        .map((mesInfo) => {
            saldoAcumulado += Number(mesInfo.saldo) || 0;

            return {
                ...mesInfo,
                saldoAcumulado
            };
        });
}

function limparRodapeTabelaBudget() {
    const rodapeTabela = document.getElementById('rodapeTabelaBudget');
    if (rodapeTabela) {
        rodapeTabela.innerHTML = '';
    }
}

function renderizarRodapeTabelaBudget(mesesProcessados, fmt) {
    const rodapeTabela = document.getElementById('rodapeTabelaBudget');
    if (!rodapeTabela) return;

    if (!Array.isArray(mesesProcessados) || mesesProcessados.length === 0) {
        rodapeTabela.innerHTML = '';
        return;
    }

    const totalOrcado = mesesProcessados.reduce((acumulado, mesInfo) => acumulado + (Number(mesInfo.orcado) || 0), 0);
    const totalEmAprovacao = mesesProcessados.reduce((acumulado, mesInfo) => acumulado + (Number(mesInfo.emAprovacao) || 0), 0);
    const totalAprovado = mesesProcessados.reduce((acumulado, mesInfo) => acumulado + (Number(mesInfo.aprovado) || 0), 0);
    const totalGeral = mesesProcessados.reduce((acumulado, mesInfo) => acumulado + (Number(mesInfo.total) || 0), 0);
    const totalSaldo = totalOrcado - totalGeral;
    const saldoAcumuladoFinal = Number(mesesProcessados[mesesProcessados.length - 1]?.saldoAcumulado) || totalSaldo;
    const percentualTotal = obterPercentualBudget(totalOrcado, totalGeral);
    const classeSaldo = totalSaldo < 0 ? 'text-danger font-bold' : 'text-success font-bold';
    const classeAcumulado = saldoAcumuladoFinal < 0 ? 'text-danger font-bold' : 'text-success font-bold';

    rodapeTabela.innerHTML = `
        <tr class="luft-budget-sticky-total-row">
            <td class="luft-budget-structure-cell">
                <span class="font-black text-main">Total Geral</span>
            </td>
            <td class="text-right font-black">${fmt.format(totalOrcado)}</td>
            <td class="text-right font-black">${fmt.format(totalEmAprovacao)}</td>
            <td class="text-right font-black">${fmt.format(totalAprovado)}</td>
            <td class="text-right font-black">${fmt.format(totalGeral)}</td>
            <td>${gerarCelulaProgressoBudget(percentualTotal)}</td>
            <td class="text-right ${classeSaldo}">${fmt.format(totalSaldo)}</td>
            <td class="text-right ${classeAcumulado}">${fmt.format(saldoAcumuladoFinal)}</td>
        </tr>`;
}

function obterResumoMesBudget(mesInfo) {
    const totalCentros = Number(mesInfo.centrosCusto) || 0;

    if (totalCentros === 0) {
        return 'Sem movimentação no período';
    }

    return `${obterDescricaoQuantidadeCentros(totalCentros)} com movimentação`;
}

function obterCentrosExpandidosPorMes(numeroMes) {
    if (!budgetTreeState.expandedCentersByMonth.has(numeroMes)) {
        budgetTreeState.expandedCentersByMonth.set(numeroMes, new Set());
    }

    return budgetTreeState.expandedCentersByMonth.get(numeroMes);
}

function obterMetricasExpansaoBudget(mesesProcessados) {
    const metricas = {
        totalMeses: mesesProcessados.length,
        mesesExpandidos: 0,
        totalCentros: 0,
        centrosExpandidos: 0,
        totalContas: 0,
        contasExpandidas: 0
    };

    mesesProcessados.forEach((mesInfo) => {
        const numeroMes = Number(mesInfo.mes) || 0;

        if (budgetTreeState.expandedMonths.has(numeroMes)) {
            metricas.mesesExpandidos += 1;
        }

        const centrosExpandidos = obterCentrosExpandidosPorMes(numeroMes);

        mesInfo.grupos.forEach((grupo) => {
            metricas.totalCentros += 1;

            if (centrosExpandidos.has(grupo.centroCusto)) {
                metricas.centrosExpandidos += 1;
            }

            const contasExpandidas = obterContasExpandidasPorCentro(numeroMes, grupo.centroCusto);

            grupo.contas.forEach((conta) => {
                if (conta.fornecedores.length === 0) return;

                metricas.totalContas += 1;

                if (contasExpandidas.has(conta.contaContabil)) {
                    metricas.contasExpandidas += 1;
                }
            });
        });
    });

    return metricas;
}

function limparExpansoesInvalidasBudget(mesesProcessados) {
    const mesesDisponiveis = new Map(
        mesesProcessados.map((mesInfo) => [Number(mesInfo.mes) || 0, mesInfo])
    );

    budgetTreeState.expandedMonths.forEach((numeroMes) => {
        if (!mesesDisponiveis.has(numeroMes)) {
            budgetTreeState.expandedMonths.delete(numeroMes);
        }
    });

    budgetTreeState.expandedCentersByMonth.forEach((centrosExpandidos, numeroMes) => {
        const mesInfo = mesesDisponiveis.get(numeroMes);

        if (!mesInfo) {
            budgetTreeState.expandedCentersByMonth.delete(numeroMes);
            budgetTreeState.expandedAccountsByMonthAndCenter.delete(numeroMes);
            return;
        }

        const centrosDisponiveis = new Set(mesInfo.grupos.map((grupo) => grupo.centroCusto));
        const contasExpandidasPorMes = budgetTreeState.expandedAccountsByMonthAndCenter.get(numeroMes);

        centrosExpandidos.forEach((centroCusto) => {
            if (centrosDisponiveis.has(centroCusto)) return;

            centrosExpandidos.delete(centroCusto);

            if (contasExpandidasPorMes) {
                contasExpandidasPorMes.delete(centroCusto);
            }
        });

        if (centrosExpandidos.size === 0) {
            budgetTreeState.expandedCentersByMonth.delete(numeroMes);
        }
    });

    budgetTreeState.expandedAccountsByMonthAndCenter.forEach((contasExpandidasPorMes, numeroMes) => {
        const mesInfo = mesesDisponiveis.get(numeroMes);

        if (!mesInfo) {
            budgetTreeState.expandedAccountsByMonthAndCenter.delete(numeroMes);
            return;
        }

        const gruposPorCentro = new Map(mesInfo.grupos.map((grupo) => [grupo.centroCusto, grupo]));

        contasExpandidasPorMes.forEach((contasExpandidas, centroCusto) => {
            const grupo = gruposPorCentro.get(centroCusto);

            if (!grupo) {
                contasExpandidasPorMes.delete(centroCusto);
                return;
            }

            const contasDisponiveis = new Set(
                grupo.contas
                    .filter((conta) => conta.fornecedores.length > 0)
                    .map((conta) => conta.contaContabil)
            );

            contasExpandidas.forEach((contaContabil) => {
                if (!contasDisponiveis.has(contaContabil)) {
                    contasExpandidas.delete(contaContabil);
                }
            });

            if (contasExpandidas.size === 0) {
                contasExpandidasPorMes.delete(centroCusto);
            }
        });

        if (contasExpandidasPorMes.size === 0) {
            budgetTreeState.expandedAccountsByMonthAndCenter.delete(numeroMes);
        }
    });
}

function atualizarStatusArvoreBudget(mesesProcessados) {
    const status = document.getElementById('budgetTreeStatus');
    const btnExpandirTodos = document.getElementById('btnExpandirTodosBudget');
    const btnRecolherTodos = document.getElementById('btnRecolherTodosBudget');

    if (!status) return;

    const metricas = obterMetricasExpansaoBudget(Array.isArray(mesesProcessados) ? mesesProcessados : []);
    const centrosCompletos = metricas.totalCentros === 0 || metricas.centrosExpandidos === metricas.totalCentros;
    const contasCompletas = metricas.totalContas === 0 || metricas.contasExpandidas === metricas.totalContas;
    const tudoExpandido = metricas.totalMeses > 0
        && metricas.mesesExpandidos === metricas.totalMeses
        && centrosCompletos
        && contasCompletas;
    const tudoRecolhido = metricas.mesesExpandidos === 0
        && metricas.centrosExpandidos === 0
        && metricas.contasExpandidas === 0;

    if (metricas.totalMeses === 0) {
        status.textContent = 'Nenhum mês carregado.';
    } else if (tudoRecolhido) {
        status.textContent = 'Meses, centros e contas estão recolhidos.';
    } else if (metricas.mesesExpandidos === metricas.totalMeses && metricas.centrosExpandidos === 0) {
        status.textContent = 'Todos os meses estão abertos. Centros e contas seguem recolhidos.';
    } else if (metricas.mesesExpandidos === metricas.totalMeses && metricas.centrosExpandidos === metricas.totalCentros && metricas.contasExpandidas === 0) {
        status.textContent = 'Meses e centros estão abertos. As contas seguem recolhidas.';
    } else if (tudoExpandido) {
        status.textContent = 'Meses, centros e contas estão totalmente abertos.';
    } else {
        status.textContent = `${metricas.mesesExpandidos}/${metricas.totalMeses} mês(es), ${metricas.centrosExpandidos}/${metricas.totalCentros} centro(s) e ${metricas.contasExpandidas}/${metricas.totalContas} conta(s) abertos.`;
    }

    if (btnExpandirTodos) {
        btnExpandirTodos.disabled = metricas.totalMeses === 0 || tudoExpandido;
    }

    if (btnRecolherTodos) {
        btnRecolherTodos.disabled = metricas.totalMeses === 0 || tudoRecolhido;
    }
}

function rerenderTabelaBudget() {
    const corpoTabela = document.getElementById('corpoTabelaBudget');
    if (!corpoTabela) return;

    renderizarTabelaBudget(budgetTreeState.mesesAtuais, corpoTabela, { redefinirEstado: false });
}

function alternarMesBudget(numeroMes) {
    if (budgetTreeState.expandedMonths.has(numeroMes)) {
        budgetTreeState.expandedMonths.delete(numeroMes);
        budgetTreeState.expandedCentersByMonth.delete(numeroMes);
        budgetTreeState.expandedAccountsByMonthAndCenter.delete(numeroMes);
    } else {
        budgetTreeState.expandedMonths.add(numeroMes);
    }

    rerenderTabelaBudget();
}

function alternarCentroCustoBudget(numeroMes, centroCusto) {
    const centrosExpandidos = obterCentrosExpandidosPorMes(numeroMes);

    if (centrosExpandidos.has(centroCusto)) {
        centrosExpandidos.delete(centroCusto);
        const contasExpandidasPorMes = budgetTreeState.expandedAccountsByMonthAndCenter.get(numeroMes);
        if (contasExpandidasPorMes) {
            contasExpandidasPorMes.delete(centroCusto);
            if (contasExpandidasPorMes.size === 0) {
                budgetTreeState.expandedAccountsByMonthAndCenter.delete(numeroMes);
            }
        }
    } else {
        centrosExpandidos.add(centroCusto);
        budgetTreeState.expandedMonths.add(numeroMes);
    }

    if (centrosExpandidos.size === 0) {
        budgetTreeState.expandedCentersByMonth.delete(numeroMes);
    }

    rerenderTabelaBudget();
}

function alternarContaContabilBudget(numeroMes, centroCusto, contaContabil) {
    const centrosExpandidos = obterCentrosExpandidosPorMes(numeroMes);
    centrosExpandidos.add(centroCusto);
    budgetTreeState.expandedMonths.add(numeroMes);

    const contasExpandidas = obterContasExpandidasPorCentro(numeroMes, centroCusto);

    if (contasExpandidas.has(contaContabil)) {
        contasExpandidas.delete(contaContabil);
    } else {
        contasExpandidas.add(contaContabil);
    }

    if (contasExpandidas.size === 0) {
        const contasExpandidasPorMes = budgetTreeState.expandedAccountsByMonthAndCenter.get(numeroMes);
        if (contasExpandidasPorMes) {
            contasExpandidasPorMes.delete(centroCusto);
            if (contasExpandidasPorMes.size === 0) {
                budgetTreeState.expandedAccountsByMonthAndCenter.delete(numeroMes);
            }
        }
    }

    rerenderTabelaBudget();
}

function limparTodasContasBudget() {
    budgetTreeState.expandedAccountsByMonthAndCenter.clear();
}

function limparTodosCentrosBudget() {
    budgetTreeState.expandedCentersByMonth.clear();
    limparTodasContasBudget();
}

function expandirTodosCentrosBudget(mesesProcessados) {
    mesesProcessados.forEach((mesInfo) => {
        const numeroMes = Number(mesInfo.mes) || 0;
        const centrosExpandidos = obterCentrosExpandidosPorMes(numeroMes);

        mesInfo.grupos.forEach((grupo) => {
            centrosExpandidos.add(grupo.centroCusto);
        });
    });
}

function expandirTodasContasBudget(mesesProcessados) {
    expandirTodosCentrosBudget(mesesProcessados);

    mesesProcessados.forEach((mesInfo) => {
        const numeroMes = Number(mesInfo.mes) || 0;

        mesInfo.grupos.forEach((grupo) => {
            const contasExpandidas = obterContasExpandidasPorCentro(numeroMes, grupo.centroCusto);

            grupo.contas.forEach((conta) => {
                if (conta.fornecedores.length > 0) {
                    contasExpandidas.add(conta.contaContabil);
                }
            });
        });
    });
}

function expandirArvoreBudgetEmFases() {
    const mesesProcessados = prepararMesesBudget(budgetTreeState.mesesAtuais);
    const metricas = obterMetricasExpansaoBudget(mesesProcessados);

    if (metricas.totalMeses === 0) return;

    if (metricas.mesesExpandidos < metricas.totalMeses) {
        budgetTreeState.expandedMonths = new Set(
            mesesProcessados.map((mesInfo) => Number(mesInfo.mes) || 0)
        );
    } else if (metricas.centrosExpandidos < metricas.totalCentros) {
        expandirTodosCentrosBudget(mesesProcessados);
    } else if (metricas.contasExpandidas < metricas.totalContas) {
        expandirTodasContasBudget(mesesProcessados);
    }

    rerenderTabelaBudget();
}

function recolherArvoreBudgetEmFases() {
    const mesesProcessados = prepararMesesBudget(budgetTreeState.mesesAtuais);
    const metricas = obterMetricasExpansaoBudget(mesesProcessados);

    if (metricas.contasExpandidas > 0) {
        limparTodasContasBudget();
    } else if (metricas.centrosExpandidos > 0) {
        limparTodosCentrosBudget();
    } else if (metricas.mesesExpandidos > 0) {
        budgetTreeState.expandedMonths.clear();
        limparTodosCentrosBudget();
    }

    rerenderTabelaBudget();
}

function renderizarLinhasDetalhamentoBudget(gruposMes, numeroMes, fmt) {
    const grupos = Array.isArray(gruposMes) ? gruposMes : [];
    const centrosExpandidos = obterCentrosExpandidosPorMes(numeroMes);

    return grupos.map(grupo => {
        const grupoExpandido = centrosExpandidos.has(grupo.centroCusto);
        const percentualGrupo = obterPercentualBudget(grupo.orcado, grupo.total);
        const classeSaldoGrupo = grupo.saldo < 0 ? 'text-danger font-bold' : 'text-success font-bold';
        const classeToggle = grupoExpandido ? 'luft-budget-tree-toggle is-expanded' : 'luft-budget-tree-toggle';
        const iconeToggle = grupoExpandido ? 'ph-caret-down' : 'ph-caret-right';
        const contasExpandidas = obterContasExpandidasPorCentro(numeroMes, grupo.centroCusto);

        const linhasContas = grupoExpandido ? grupo.contas.map((conta) => {
            const possuiFornecedores = conta.fornecedores.length > 0;
            const contaExpandida = possuiFornecedores && contasExpandidas.has(conta.contaContabil);
            const percentualConta = obterPercentualBudget(conta.orcado, conta.total);
            const classeSaldoConta = conta.saldo < 0 ? 'text-danger font-bold' : 'text-main font-medium';
            const classeToggleConta = contaExpandida ? 'luft-budget-tree-toggle is-expanded' : 'luft-budget-tree-toggle';
            const iconeToggleConta = contaExpandida ? 'ph-caret-down' : 'ph-caret-right';
            const controleConta = possuiFornecedores
                ? `<button type="button" class="${classeToggleConta}" data-budget-month="${numeroMes}" data-budget-center="${encodeURIComponent(grupo.centroCusto)}" data-budget-account-toggle="${encodeURIComponent(conta.contaContabil)}" aria-expanded="${contaExpandida}" aria-label="${contaExpandida ? 'Recolher' : 'Expandir'} ${escaparHtml(conta.contaContabil)}"><i class="ph-bold ${iconeToggleConta}"></i></button>`
                : `<span class="luft-budget-tree-toggle is-static" aria-hidden="true"><i class="ph-bold ph-minus"></i></span>`;
            const linhasFornecedores = contaExpandida ? conta.fornecedores.map((fornecedor, indice) => {
                const percentualFornecedor = obterPercentualBudget(fornecedor.orcado, fornecedor.total);
                const classeSaldoFornecedor = fornecedor.saldo < 0 ? 'text-danger font-bold' : 'text-main font-medium';
                const classeLinhaFornecedor = indice === conta.fornecedores.length - 1
                    ? 'luft-budget-row-supplier luft-budget-row-supplier--last'
                    : 'luft-budget-row-supplier';

                return `
                    <tr class="${classeLinhaFornecedor}">
                        <td class="luft-budget-structure-cell">
                            <div class="luft-budget-tree-node luft-budget-tree-node--supplier">
                                <span class="luft-budget-tree-bullet" aria-hidden="true"></span>
                                <div class="luft-budget-tree-content">
                                    <span class="luft-budget-tree-title">${escaparHtml(fornecedor.fornecedor)}</span>
                                </div>
                            </div>
                        </td>
                        <td class="text-right font-medium">${fmt.format(fornecedor.orcado)}</td>
                        <td class="text-right">${fmt.format(fornecedor.emAprovacao)}</td>
                        <td class="text-right">${fmt.format(fornecedor.aprovado)}</td>
                        <td class="text-right">${fmt.format(fornecedor.total)}</td>
                        <td>${gerarCelulaProgressoBudget(percentualFornecedor)}</td>
                        <td class="text-right ${classeSaldoFornecedor}">${fmt.format(fornecedor.saldo)}</td>
                        <td class="text-right">${gerarCelulaSaldoAcumuladoDetalhe()}</td>
                    </tr>`;
            }).join('') : '';

            return `
                <tr class="luft-budget-row-account">
                    <td class="luft-budget-structure-cell">
                        <div class="luft-budget-tree-node luft-budget-tree-node--account">
                            ${controleConta}
                            <span class="luft-budget-tree-icon luft-budget-tree-icon--account" aria-hidden="true">
                                <i class="ph-bold ph-receipt"></i>
                            </span>
                            <div class="luft-budget-tree-content">
                                <span class="luft-budget-tree-title">${escaparHtml(conta.contaContabil)}</span>
                                <span class="luft-budget-tree-caption">${obterDescricaoQuantidadeFornecedores(conta.fornecedores.length)}</span>
                            </div>
                        </div>
                    </td>
                    <td class="text-right font-medium">${fmt.format(conta.orcado)}</td>
                    <td class="text-right">${fmt.format(conta.emAprovacao)}</td>
                    <td class="text-right">${fmt.format(conta.aprovado)}</td>
                    <td class="text-right">${fmt.format(conta.total)}</td>
                    <td>${gerarCelulaProgressoBudget(percentualConta)}</td>
                    <td class="text-right ${classeSaldoConta}">${fmt.format(conta.saldo)}</td>
                    <td class="text-right">${gerarCelulaSaldoAcumuladoDetalhe()}</td>
                </tr>
                ${linhasFornecedores}`;
        }).join('') : '';

        return `
            <tr class="luft-budget-row-group">
                <td class="luft-budget-structure-cell">
                    <div class="luft-budget-tree-node luft-budget-tree-node--group">
                        <button type="button" class="${classeToggle}" data-budget-month="${numeroMes}" data-budget-center-toggle="${encodeURIComponent(grupo.centroCusto)}" aria-expanded="${grupoExpandido}" aria-label="${grupoExpandido ? 'Recolher' : 'Expandir'} ${escaparHtml(grupo.centroCusto)}">
                            <i class="ph-bold ${iconeToggle}"></i>
                        </button>
                        <span class="luft-budget-tree-icon" aria-hidden="true">
                            <i class="ph-bold ph-folders"></i>
                        </span>
                        <div class="luft-budget-tree-content">
                            <span class="luft-budget-tree-title">${escaparHtml(grupo.centroCusto)}</span>
                            <span class="luft-budget-tree-caption">${obterDescricaoQuantidadeContas(grupo.contas.length)}</span>
                        </div>
                    </div>
                </td>
                <td class="text-right font-bold">${fmt.format(grupo.orcado)}</td>
                <td class="text-right font-bold">${fmt.format(grupo.emAprovacao)}</td>
                <td class="text-right font-bold">${fmt.format(grupo.aprovado)}</td>
                <td class="text-right font-bold">${fmt.format(grupo.total)}</td>
                <td>${gerarCelulaProgressoBudget(percentualGrupo)}</td>
                <td class="text-right ${classeSaldoGrupo}">${fmt.format(grupo.saldo)}</td>
                <td class="text-right">${gerarCelulaSaldoAcumuladoDetalhe()}</td>
            </tr>
            ${linhasContas}`;
    }).join('');
}

function renderizarDetalhamentoMensalBudget(mesInfo, fmt) {
    const grupos = Array.isArray(mesInfo.grupos) ? mesInfo.grupos : [];
    const numeroMes = Number(mesInfo.mes) || 0;

    if (grupos.length === 0) {
        return `
            <tr class="luft-budget-row-empty">
                <td colspan="${COLSPAN_TABELA_BUDGET}" class="text-center text-muted py-4">
                    Nenhum dado financeiro encontrado para ${escaparHtml(mesInfo.nomeMes || 'o mês selecionado')}.
                </td>
            </tr>`;
    }

    return renderizarLinhasDetalhamentoBudget(grupos, numeroMes, fmt);
}

/**
 * Renderiza a tabela anual em 12 linhas mensais com expansão do detalhamento mensal.
 */
function renderizarTabelaBudget(listaDados, elementoTabela, { redefinirEstado = true } = {}) {
    elementoTabela.innerHTML = '';

    budgetTreeState.mesesAtuais = Array.isArray(listaDados) ? listaDados : [];

    if (redefinirEstado) {
        budgetTreeState.expandedMonths.clear();
        budgetTreeState.expandedCentersByMonth.clear();
        budgetTreeState.expandedAccountsByMonthAndCenter.clear();
    }

    const meses = prepararMesesBudget(budgetTreeState.mesesAtuais);
    limparExpansoesInvalidasBudget(meses);
    atualizarKpis(meses);

    if (!listaDados || listaDados.length === 0) {
        atualizarStatusArvoreBudget([]);
        limparRodapeTabelaBudget();
        elementoTabela.innerHTML = `
            <tr>
                <td colspan="${COLSPAN_TABELA_BUDGET}" class="text-center py-10">
                    <div class="d-flex flex-col align-items-center justify-content-center text-muted">
                        <i class="ph-thin ph-file-x text-4xl mb-2"></i>
                        <p>Nenhum dado financeiro encontrado para os filtros informados.</p>
                    </div>
                </td>
            </tr>`;
        return;
    }

    const fmt = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

    elementoTabela.innerHTML = meses.map(mesInfo => {
        const numeroMes = Number(mesInfo.mes) || 0;
        const mesExpandido = budgetTreeState.expandedMonths.has(numeroMes);
        const orcado = Number(mesInfo.orcado) || 0;
        const emAprovacao = Number(mesInfo.emAprovacao) || 0;
        const aprovado = Number(mesInfo.aprovado) || 0;
        const total = Number(mesInfo.total) || 0;
        const saldo = Number.isFinite(Number(mesInfo.saldo)) ? Number(mesInfo.saldo) : (orcado - total);
        const saldoAcumulado = Number.isFinite(Number(mesInfo.saldoAcumulado)) ? Number(mesInfo.saldoAcumulado) : saldo;
        const percentualMes = obterPercentualBudget(orcado, total);
        const classeSaldoMes = saldo < 0 ? 'text-danger font-bold' : 'text-success font-bold';
        const classeSaldoAcumulado = saldoAcumulado < 0 ? 'text-danger font-bold' : 'text-success font-bold';
        const classeToggle = mesExpandido ? 'luft-budget-tree-toggle is-expanded' : 'luft-budget-tree-toggle';
        const iconeToggle = mesExpandido ? 'ph-caret-down' : 'ph-caret-right';

        return `
            <tr class="luft-budget-row-month ${mesExpandido ? 'is-expanded' : ''}" data-budget-month-row="${numeroMes}">
                <td class="luft-budget-structure-cell">
                    <div class="luft-budget-tree-node luft-budget-tree-node--month">
                        <button type="button" class="${classeToggle}" data-budget-month-toggle="${numeroMes}" aria-expanded="${mesExpandido}" aria-label="${mesExpandido ? 'Recolher' : 'Expandir'} ${escaparHtml(mesInfo.nomeMes || 'Mês')}">
                            <i class="ph-bold ${iconeToggle}"></i>
                        </button>
                        <span class="luft-budget-tree-icon luft-budget-tree-icon--month" aria-hidden="true">
                            <i class="ph-bold ph-calendar-blank"></i>
                        </span>
                        <div class="luft-budget-tree-content">
                            <span class="luft-budget-tree-title">${escaparHtml(mesInfo.nomeMes || `Mês ${numeroMes}`)}</span>
                            <span class="luft-budget-tree-caption">${escaparHtml(obterResumoMesBudget(mesInfo))}</span>
                        </div>
                    </div>
                </td>
                <td class="text-right font-bold">${fmt.format(orcado)}</td>
                <td class="text-right font-bold">${fmt.format(emAprovacao)}</td>
                <td class="text-right font-bold">${fmt.format(aprovado)}</td>
                <td class="text-right font-bold">${fmt.format(total)}</td>
                <td>${gerarCelulaProgressoBudget(percentualMes)}</td>
                <td class="text-right ${classeSaldoMes}">${fmt.format(saldo)}</td>
                <td class="text-right ${classeSaldoAcumulado}">${fmt.format(saldoAcumulado)}</td>
            </tr>
            ${mesExpandido ? renderizarDetalhamentoMensalBudget(mesInfo, fmt) : ''}`;
    }).join('');

    renderizarRodapeTabelaBudget(meses, fmt);
    atualizarStatusArvoreBudget(meses);
}