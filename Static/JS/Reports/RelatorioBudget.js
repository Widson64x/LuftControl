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
    documentClickBound: false,
    filtros: {
        centrosCusto: {
            items: [],
            selectedIds: new Set(),
            loaded: false,
            allSelected: true
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
        buttonId: 'btnToggleCentroCusto',
        panelId: 'panelCentroCusto',
        labelId: 'labelCentroCusto',
        searchInputId: 'inputBuscaCentroCusto',
        listId: 'listaCentrosCusto',
        selectAllId: 'checkTodosCentros',
        emptyId: 'emptyCentroCusto',
        emptyMessage: 'Nenhum centro de custo disponível.',
        paramName: 'centro_custo'
    },
    contasContabeis: {
        buttonId: 'btnToggleContaContabil',
        panelId: 'panelContaContabil',
        labelId: 'labelContaContabil',
        searchInputId: 'inputBuscaContaContabil',
        listId: 'listaContasContabeis',
        selectAllId: 'checkTodasContas',
        emptyId: 'emptyContaContabil',
        emptyMessage: 'Nenhuma conta contábil disponível.',
        paramName: 'conta_contabil'
    }
};

/**
 * Vincula os eventos e carrega os dados primários da tela.
 */
function inicializarRelatorioBudget() {
    const inputAno = document.getElementById('inputAnoBudget');
    const botaoBuscar = document.getElementById('btnBuscarBudget');
    const selectModoSaldo = document.getElementById('selectModoSaldoBudget');
    const selectEmpresa = document.getElementById('selectEmpresaBudget');
    
    if (!inputAno || !botaoBuscar) return;

    budgetTreeState.modoSaldo = selectModoSaldo ? selectModoSaldo.value : 'todos_itens';

    botaoBuscar.addEventListener('click', carregarDadosBudget);
    configurarControlesTabelaBudget();
    atualizarStatusArvoreBudget([]);

    if (selectModoSaldo && !selectModoSaldo.dataset.bound) {
        selectModoSaldo.addEventListener('change', (event) => {
            budgetTreeState.modoSaldo = event.target.value || 'todos_itens';
            rerenderTabelaBudget();
        });
        selectModoSaldo.dataset.bound = 'true';
    }
    
    configurarFiltrosBudget();

    if (inputAno && !inputAno.dataset.filterBound) {
        inputAno.addEventListener('change', () => {
            sincronizarFiltrosBudget();
        });
        inputAno.dataset.filterBound = 'true';
    }

    if (selectEmpresa && !selectEmpresa.dataset.filterBound) {
        selectEmpresa.addEventListener('change', () => {
            sincronizarFiltrosBudget();
        });
        selectEmpresa.dataset.filterBound = 'true';
    }
    
    // Carrega filtros e dispara a busca inicial
    sincronizarFiltrosBudget().then(() => {
        carregarDadosBudget();
    });
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

function formatarTextoOpcaoFiltroBudget(chaveFiltro, item) {
    if (chaveFiltro === 'contasContabeis') {
        return item.nome || `${item.codigo || ''} - ${item.descricao || ''}`;
    }

    return `${item.codigo || ''} - ${item.nome || ''}`;
}

function configurarFiltrosBudget() {
    Object.keys(BUDGET_FILTER_CONFIG).forEach((chaveFiltro) => {
        configurarFiltroBudget(chaveFiltro);
    });

    if (!budgetFilterState.documentClickBound) {
        document.addEventListener('click', (event) => {
            Object.keys(BUDGET_FILTER_CONFIG).forEach((chaveFiltro) => {
                const config = obterConfiguracaoFiltroBudget(chaveFiltro);
                const botao = document.getElementById(config.buttonId);
                const painel = document.getElementById(config.panelId);

                if (!botao || !painel) return;
                if (painel.contains(event.target) || botao.contains(event.target)) return;

                fecharPainelFiltroBudget(chaveFiltro);
            });
        });

        budgetFilterState.documentClickBound = true;
    }
}

function configurarFiltroBudget(chaveFiltro) {
    const config = obterConfiguracaoFiltroBudget(chaveFiltro);
    const botao = document.getElementById(config.buttonId);
    const campoBusca = document.getElementById(config.searchInputId);
    const lista = document.getElementById(config.listId);
    const checkboxTodos = document.getElementById(config.selectAllId);

    if (botao && !botao.dataset.bound) {
        botao.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            alternarPainelFiltroBudget(chaveFiltro);
        });
        botao.dataset.bound = 'true';
    }

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

function alternarPainelFiltroBudget(chaveFiltro) {
    const config = obterConfiguracaoFiltroBudget(chaveFiltro);
    const painel = document.getElementById(config.panelId);

    if (!painel) return;

    const estaOculto = painel.classList.contains('d-none');
    fecharTodosPaineisFiltroBudget(estaOculto ? chaveFiltro : null);

    if (estaOculto) {
        abrirPainelFiltroBudget(chaveFiltro);
    } else {
        fecharPainelFiltroBudget(chaveFiltro);
    }
}

function abrirPainelFiltroBudget(chaveFiltro) {
    const config = obterConfiguracaoFiltroBudget(chaveFiltro);
    const painel = document.getElementById(config.panelId);
    const botao = document.getElementById(config.buttonId);
    const campoBusca = document.getElementById(config.searchInputId);

    if (!painel || !botao) return;

    painel.classList.remove('d-none');
    painel.classList.add('d-flex');
    botao.classList.add('is-open');

    if (campoBusca) {
        campoBusca.focus();
        campoBusca.select();
    }
}

function fecharPainelFiltroBudget(chaveFiltro) {
    const config = obterConfiguracaoFiltroBudget(chaveFiltro);
    const painel = document.getElementById(config.panelId);
    const botao = document.getElementById(config.buttonId);

    if (!painel || !botao) return;

    painel.classList.add('d-none');
    painel.classList.remove('d-flex');
    botao.classList.remove('is-open');
}

function fecharTodosPaineisFiltroBudget(excecao = null) {
    Object.keys(BUDGET_FILTER_CONFIG).forEach((chaveFiltro) => {
        if (chaveFiltro === excecao) return;
        fecharPainelFiltroBudget(chaveFiltro);
    });
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

    return fetch(`/budget/filtros?ano=${encodeURIComponent(ano)}&empresa=${encodeURIComponent(empresa)}&centro_custo=${encodeURIComponent(centroCusto)}&conta_contabil=${encodeURIComponent(contaContabil)}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then((resposta) => resposta.json())
    .then((retorno) => {
        if (requestToken !== budgetFilterState.requestToken) {
            return;
        }

        if (retorno.status !== 'success') {
            throw new Error(retorno.message || retorno.msg || 'Falha ao carregar os filtros do Budget.');
        }

        renderizarOpcoesFiltroBudget('centrosCusto', retorno.data?.centrosCusto || []);
        renderizarOpcoesFiltroBudget('contasContabeis', retorno.data?.contasContabeis || []);
    })
    .catch((erro) => {
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
    let selecionados = new Set();

    if (opcoes.length > 0) {
        if (!estado.loaded || estado.allSelected) {
            selecionados = new Set(opcoes.map((item) => item.id));
        } else {
            selecionados = new Set(
                Array.from(estado.selectedIds).filter((idSelecionado) => idsDisponiveis.has(idSelecionado))
            );
        }
    }

    estado.items = opcoes;
    estado.selectedIds = selecionados;
    estado.loaded = true;
    estado.allSelected = opcoes.length > 0 && selecionados.size === opcoes.length;

    lista.innerHTML = opcoes.map((item) => {
        const texto = formatarTextoOpcaoFiltroBudget(chaveFiltro, item);
        const textoBusca = normalizarTextoBudget(`${item.codigo || ''} ${item.nome || ''} ${item.descricao || ''} ${texto}`);
        const marcado = estado.selectedIds.has(item.id) ? 'checked' : '';

        return `
            <label class="luft-budget-filter-option" data-search="${escaparHtml(textoBusca)}">
                <input type="checkbox" class="luft-budget-filter-checkbox" value="${escaparHtml(item.id)}" ${marcado}>
                <span>${escaparHtml(texto)}</span>
            </label>`;
    }).join('');

    atualizarResumoFiltroBudget(chaveFiltro);
    aplicarBuscaFiltroBudget(chaveFiltro);
}

function atualizarSelecaoFiltroBudget(chaveFiltro, idItem, marcado) {
    const estado = obterEstadoFiltroBudget(chaveFiltro);
    const idNormalizado = String(idItem);

    if (marcado) {
        estado.selectedIds.add(idNormalizado);
    } else {
        estado.selectedIds.delete(idNormalizado);
    }

    estado.allSelected = estado.items.length > 0 && estado.selectedIds.size === estado.items.length;
    atualizarResumoFiltroBudget(chaveFiltro);
    agendarSincronizacaoFiltrosBudget();
}

function atualizarSelecaoTotalFiltroBudget(chaveFiltro, marcado) {
    const estado = obterEstadoFiltroBudget(chaveFiltro);
    estado.selectedIds = marcado
        ? new Set(estado.items.map((item) => item.id))
        : new Set();
    estado.allSelected = marcado && estado.items.length > 0;

    const config = obterConfiguracaoFiltroBudget(chaveFiltro);
    const lista = document.getElementById(config.listId);
    if (lista) {
        lista.querySelectorAll('.luft-budget-filter-checkbox').forEach((checkbox) => {
            checkbox.checked = marcado;
        });
    }

    atualizarResumoFiltroBudget(chaveFiltro);
    agendarSincronizacaoFiltrosBudget();
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
    const botao = document.getElementById(config.buttonId);
    const total = estado.items.length;
    const selecionados = estado.selectedIds.size;

    if (label) {
        if (total === 0) {
            label.textContent = 'Sem opções';
        } else if (selecionados === total) {
            label.textContent = 'Todos Selecionados';
        } else if (selecionados === 0) {
            label.textContent = 'Nenhum selecionado';
        } else if (selecionados === 1) {
            label.textContent = '1 selecionado';
        } else {
            label.textContent = `${selecionados} selecionados`;
        }
    }

    if (checkboxTodos) {
        checkboxTodos.checked = total > 0 && selecionados === total;
        checkboxTodos.indeterminate = selecionados > 0 && selecionados < total;
    }

    if (botao) {
        botao.disabled = total === 0;
    }
}

function obterParametroFiltroBudget(chaveFiltro, { ignorarVazio = false } = {}) {
    const estado = obterEstadoFiltroBudget(chaveFiltro);

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

function agendarSincronizacaoFiltrosBudget() {
    clearTimeout(budgetFilterState.syncTimer);
    budgetFilterState.syncTimer = setTimeout(() => {
        sincronizarFiltrosBudget();
    }, 250);
}

/**
 * Coleta os filtros e consulta a API de dados.
 */
function carregarDadosBudget() {
    const inputAno = document.getElementById('inputAnoBudget');
    const selectEmpresa = document.getElementById('selectEmpresaBudget');
    const corpoTabela = document.getElementById('corpoTabelaBudget');
    
    if (!inputAno || !corpoTabela) return;

    const ano = inputAno.value;
    const empresa = selectEmpresa ? selectEmpresa.value : 'Todos';
    const conta = obterParametroFiltroBudget('contasContabeis');
    const ccParam = obterParametroFiltroBudget('centrosCusto');

    limparRodapeTabelaBudget();

    corpoTabela.innerHTML = `
        <tr>
            <td colspan="${COLSPAN_TABELA_BUDGET}" class="text-center py-10">
                <div class="d-flex flex-col align-items-center justify-content-center">
                    <i class="ph-bold ph-spinner-gap text-primary text-4xl" style="animation: spin 1s linear infinite;"></i>
                    <p class="text-muted mt-3 font-medium">Processando estrutura orçamentária...</p>
                </div>
            </td>
        </tr>`;

    fetch(`/budget/gerencial?ano=${encodeURIComponent(ano)}&empresa=${encodeURIComponent(empresa)}&centro_custo=${encodeURIComponent(ccParam)}&conta_contabil=${encodeURIComponent(conta)}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(resposta => resposta.json())
    .then(retorno => {
        if (retorno.status === 'success') {
            const meses = Array.isArray(retorno.data?.meses) ? retorno.data.meses : [];
            renderizarTabelaBudget(meses, corpoTabela);
        } else {
            corpoTabela.innerHTML = `<tr><td colspan="${COLSPAN_TABELA_BUDGET}" class="text-center text-danger py-6 font-bold">Erro: ${retorno.msg}</td></tr>`;
        }
    })
    .catch(erro => {
        console.error('Falha ao obter dados:', erro);
        corpoTabela.innerHTML = `<tr><td colspan="${COLSPAN_TABELA_BUDGET}" class="text-center text-danger py-6 font-bold">Falha na comunicação com o servidor.</td></tr>`;
    });
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
        <tr class="luft-budget-row-footer">
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