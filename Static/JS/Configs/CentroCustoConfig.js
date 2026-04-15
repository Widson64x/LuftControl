(function () {
    const app = document.getElementById('cc-config-app');
    if (!app) {
        return;
    }

    const byId = (id) => document.getElementById(id);
    const parseJson = (id) => {
        const element = byId(id);
        if (!element) {
            return null;
        }

        try {
            return JSON.parse(element.textContent || 'null');
        } catch {
            return null;
        }
    };

    const escapeHtml = (value) => String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');

    const openModal = (id) => {
        if (typeof LuftCore !== 'undefined' && typeof LuftCore.abrirModal === 'function') {
            LuftCore.abrirModal(id);
        }
    };

    const closeModal = (id) => {
        if (typeof LuftCore !== 'undefined' && typeof LuftCore.fecharModal === 'function') {
            LuftCore.fecharModal(id);
        }
    };

    const users = (parseJson('cc-config-users') || []).map((user) => ({
        codigo_usuario: Number(user.codigo_usuario),
        nome_usuario: user.nome_usuario || `Usuário ${user.codigo_usuario}`,
        login_usuario: user.login_usuario || '',
    }));

    const centers = (parseJson('cc-config-centers') || []).map((center) => ({
        codigo: String(center.codigo),
        numero: center.numero || String(center.codigo),
        nome: center.nome || 'Sem nome',
    }));

    const userMap = new Map(users.map((user) => [user.codigo_usuario, user]));
    const centerMap = new Map(centers.map((center) => [center.codigo, center]));

    const saveBtn = byId('cc-save');
    const openManagerBtn = byId('cc-open-manager');
    const openOffBtn = byId('cc-open-off');
    const managerFilterInput = byId('cc-manager-filter');
    const managerList = byId('cc-manager-list');
    const offCompactList = byId('cc-off-list-compact');
    const managerCount = byId('cc-manager-count');
    const linkCount = byId('cc-link-count');
    const offCount = byId('cc-off-count');

    const userSearch = byId('cc-user-search');
    const userResults = byId('cc-user-results');
    const currentUserBox = byId('cc-user-current');
    const roleInput = byId('cc-role-input');
    const managerCenterSearch = byId('cc-manager-center-search');
    const managerCenterList = byId('cc-manager-center-list');
    const managerCenterSelected = byId('cc-manager-center-selected');
    const managerApplyBtn = byId('cc-manager-apply');

    const offSearch = byId('cc-off-search');
    const offList = byId('cc-off-list');
    const offSelected = byId('cc-off-selected');
    const offApplyBtn = byId('cc-off-apply');

    const sortCenters = (items) => items.sort((a, b) => `${a.numero} ${a.nome}`.localeCompare(`${b.numero} ${b.nome}`));

    const normalizeCenter = (center) => {
        const code = String(center?.codigo ?? center ?? '').trim();
        if (!code) {
            return null;
        }

        const base = centerMap.get(code);
        return {
            codigo: code,
            numero: base?.numero || String(center?.numero || code),
            nome: base?.nome || String(center?.nome || 'Sem nome'),
        };
    };

    const normalizeConfig = (config) => {
        const offSeen = new Set();
        const centersOff = sortCenters(
            (Array.isArray(config?.centros_custo_off) ? config.centros_custo_off : [])
                .map(normalizeCenter)
                .filter((center) => center && !offSeen.has(center.codigo) && offSeen.add(center.codigo))
        );

        const offCodes = new Set(centersOff.map((center) => center.codigo));
        const managers = (Array.isArray(config?.gestores) ? config.gestores : [])
            .map((manager) => {
                const userId = Number(manager.codigo_usuario);
                if (!userMap.has(userId)) {
                    return null;
                }

                const managerSeen = new Set();
                const managerCenters = sortCenters(
                    (Array.isArray(manager.centros_custo) ? manager.centros_custo : [])
                        .map(normalizeCenter)
                        .filter((center) => center && !offCodes.has(center.codigo) && !managerSeen.has(center.codigo) && managerSeen.add(center.codigo))
                );

                if (!managerCenters.length) {
                    return null;
                }

                const user = userMap.get(userId);
                return {
                    codigo_usuario: userId,
                    nome_usuario: user.nome_usuario,
                    login_usuario: user.login_usuario,
                    cargo: String(manager.cargo || '').trim() || 'Gestor',
                    centros_custo: managerCenters,
                };
            })
            .filter(Boolean)
            .sort((a, b) => a.nome_usuario.localeCompare(b.nome_usuario));

        return {
            version: Number(config?.version || 2),
            atualizado_em: config?.atualizado_em || null,
            atualizado_por: config?.atualizado_por || {},
            centros_custo_off: centersOff,
            gestores: managers,
        };
    };

    const state = {
        config: normalizeConfig(parseJson('cc-config-data') || {}),
        managerFilter: '',
        userFilter: '',
        centerFilter: '',
        offFilter: '',
        selectedUserId: null,
        selectedCenterCodes: new Set(),
        draftOffCodes: new Set(),
    };

    const getOffCodes = () => new Set(state.config.centros_custo_off.map((center) => center.codigo));
    const getSelectedUser = () => userMap.get(Number(state.selectedUserId)) || null;
    const getManager = (userId) => state.config.gestores.find((manager) => manager.codigo_usuario === Number(userId)) || null;

    const setStatus = (message, type) => {
        const notifType = type === 'error' ? 'danger' : (type || 'info');
        NotificationSystem.show(message, notifType);
    };

    const getFilteredCenters = (query, includeOff) => {
        const term = String(query || '').trim().toLowerCase();
        const offCodes = getOffCodes();
        return centers.filter((center) => {
            if (!includeOff && offCodes.has(center.codigo)) {
                return false;
            }

            if (!term) {
                return true;
            }

            return `${center.codigo} ${center.numero} ${center.nome}`.toLowerCase().includes(term);
        });
    };

    const syncOffCenters = (codes) => {
        const offCodes = new Set(codes);
        state.config.centros_custo_off = sortCenters(
            centers
                .filter((center) => offCodes.has(center.codigo))
                .map((center) => ({ codigo: center.codigo, numero: center.numero, nome: center.nome }))
        );

        state.config.gestores = state.config.gestores
            .map((manager) => ({
                ...manager,
                centros_custo: manager.centros_custo.filter((center) => !offCodes.has(center.codigo)),
            }))
            .filter((manager) => manager.centros_custo.length)
            .sort((a, b) => a.nome_usuario.localeCompare(b.nome_usuario));

        state.selectedCenterCodes.forEach((code) => {
            if (offCodes.has(code)) {
                state.selectedCenterCodes.delete(code);
            }
        });
    };

    const renderSummary = () => {
        const totalLinks = state.config.gestores.reduce((total, manager) => total + manager.centros_custo.length, 0);
        managerCount.textContent = String(state.config.gestores.length);
        linkCount.textContent = String(totalLinks);
        offCount.textContent = String(state.config.centros_custo_off.length);

    };

    const renderManagers = () => {
        const term = state.managerFilter.trim().toLowerCase();
        const visibleManagers = state.config.gestores.filter((manager) => {
            if (!term) {
                return true;
            }

            return `${manager.nome_usuario} ${manager.login_usuario} ${manager.cargo}`.toLowerCase().includes(term);
        });

        managerList.innerHTML = visibleManagers.length
            ? visibleManagers.map((manager) => `
                <article class="luft-cc-manager-card">
                    <div class="luft-cc-manager-row">
                        <div class="luft-cc-manager-main">
                            <span class="luft-cc-manager-name">${escapeHtml(manager.nome_usuario)}</span>
                            <span class="luft-cc-manager-meta">${escapeHtml(manager.login_usuario || 'Sem login')} • ${escapeHtml(manager.cargo)} • ${manager.centros_custo.length} centro${manager.centros_custo.length !== 1 ? 's' : ''}</span>
                        </div>
                        <div class="luft-cc-manager-actions">
                            <button type="button" class="luft-cc-btn luft-cc-btn-secondary luft-cc-btn-sm" data-edit-user="${escapeHtml(String(manager.codigo_usuario))}">
                                <i class="ph-bold ph-pencil-simple"></i>
                                <span>Editar</span>
                            </button>
                            <button type="button" class="luft-cc-btn luft-cc-btn-secondary luft-cc-btn-sm" data-remove-user="${escapeHtml(String(manager.codigo_usuario))}">
                                <i class="ph-bold ph-trash"></i>
                                <span>Remover</span>
                            </button>
                        </div>
                    </div>
                </article>
            `).join('')
            : '<div class="luft-cc-empty">Nenhum gestor.</div>';
    };

    const renderOffPanel = () => {
        const selectedOff = state.config.centros_custo_off;
        offCompactList.innerHTML = selectedOff.length
            ? selectedOff.map((center) => `
                <article class="luft-cc-off-card">
                    <div class="luft-cc-off-main">
                        <span class="luft-cc-off-code">${escapeHtml(center.numero)}</span>
                        <span class="luft-cc-off-name">${escapeHtml(center.nome)}</span>
                    </div>
                    <button type="button" class="luft-cc-btn luft-cc-btn-secondary luft-cc-btn-sm" data-open-off>
                        <i class="ph-bold ph-pencil-simple"></i>
                    </button>
                </article>
            `).join('')
            : '<div class="luft-cc-empty">Nenhum centro inativo.</div>';
    };

    const renderUserResults = () => {
        const term = state.userFilter.trim().toLowerCase();
        const visibleUsers = users.filter((user) => {
            if (!term) {
                return true;
            }

            return `${user.codigo_usuario} ${user.nome_usuario} ${user.login_usuario}`.toLowerCase().includes(term);
        }).slice(0, 16);

        userResults.innerHTML = visibleUsers.length
            ? visibleUsers.map((user) => `
                <button type="button" class="luft-cc-user-option ${Number(state.selectedUserId) === user.codigo_usuario ? 'is-active' : ''}" data-user="${escapeHtml(String(user.codigo_usuario))}">
                    <div>
                        <span class="luft-cc-user-name">${escapeHtml(user.nome_usuario)}</span>
                        <span class="luft-cc-user-meta">${escapeHtml(user.login_usuario || 'Sem login')} • ${escapeHtml(String(user.codigo_usuario))}</span>
                    </div>
                </button>
            `).join('')
            : '<div class="luft-cc-empty">Nenhum usuário.</div>';

        const user = getSelectedUser();
        currentUserBox.innerHTML = user
            ? `<span class="cc-info-text"><i class="ph-bold ph-user-circle"></i> ${escapeHtml(user.nome_usuario)}</span>`
            : '';
    };

    const renderManagerCenterOptions = () => {
        const visibleCenters = getFilteredCenters(state.centerFilter, false);
        managerCenterList.innerHTML = visibleCenters.length
            ? visibleCenters.map((center) => `
                <label class="luft-cc-option ${state.selectedCenterCodes.has(center.codigo) ? 'is-selected' : ''}">
                    <input type="checkbox" value="${escapeHtml(center.codigo)}" ${state.selectedCenterCodes.has(center.codigo) ? 'checked' : ''}>
                    <div>
                        <span class="luft-cc-option-code">${escapeHtml(center.numero)}</span>
                        <span class="luft-cc-option-name">${escapeHtml(center.nome)}</span>
                    </div>
                </label>
            `).join('')
            : '<div class="luft-cc-empty">Nenhum centro ativo.</div>';

        const selectedCenters = sortCenters(
            Array.from(state.selectedCenterCodes)
                .map((code) => centerMap.get(code))
                .filter(Boolean)
        );

        managerCenterSelected.innerHTML = selectedCenters.length
            ? `<span class="cc-info-text">${selectedCenters.length} centro${selectedCenters.length !== 1 ? 's' : ''}</span>`
            : '';
    };

    const renderOffOptions = () => {
        const visibleCenters = getFilteredCenters(state.offFilter, true);
        offList.innerHTML = visibleCenters.length
            ? visibleCenters.map((center) => `
                <label class="luft-cc-option ${state.draftOffCodes.has(center.codigo) ? 'is-selected' : ''}">
                    <input type="checkbox" value="${escapeHtml(center.codigo)}" ${state.draftOffCodes.has(center.codigo) ? 'checked' : ''}>
                    <div>
                        <span class="luft-cc-option-code">${escapeHtml(center.numero)}</span>
                        <span class="luft-cc-option-name">${escapeHtml(center.nome)}</span>
                    </div>
                </label>
            `).join('')
            : '<div class="luft-cc-empty">Nenhum centro.</div>';

        const selectedCenters = sortCenters(
            Array.from(state.draftOffCodes)
                .map((code) => centerMap.get(code))
                .filter(Boolean)
        );

        offSelected.innerHTML = selectedCenters.length
            ? `<span class="cc-info-text">${selectedCenters.length} inativo${selectedCenters.length !== 1 ? 's' : ''} selecionado${selectedCenters.length !== 1 ? 's' : ''}</span>`
            : '';
    };

    const renderAll = () => {
        renderSummary();
        renderManagers();
        renderOffPanel();
        renderUserResults();
        renderManagerCenterOptions();
        renderOffOptions();
    };

    const openManagerModal = (userId) => {
        const manager = getManager(userId);
        const user = manager ? userMap.get(Number(manager.codigo_usuario)) : null;

        state.selectedUserId = user ? user.codigo_usuario : null;
        state.userFilter = user ? user.nome_usuario : '';
        state.centerFilter = '';
        state.selectedCenterCodes = new Set((manager?.centros_custo || []).map((center) => center.codigo));

        userSearch.value = state.userFilter;
        roleInput.value = manager?.cargo || '';
        managerCenterSearch.value = '';

        renderUserResults();
        renderManagerCenterOptions();
        openModal('modalCentroCustoGestor');
    };

    const openOffModalDraft = () => {
        state.offFilter = '';
        state.draftOffCodes = new Set(getOffCodes());
        offSearch.value = '';
        renderOffOptions();
        openModal('modalCentroCustoOff');
    };

    const applyManager = () => {
        const user = getSelectedUser();
        const role = String(roleInput.value || '').trim();
        const selectedCenters = sortCenters(
            Array.from(state.selectedCenterCodes)
                .map((code) => centerMap.get(code))
                .filter(Boolean)
                .map((center) => ({ codigo: center.codigo, numero: center.numero, nome: center.nome }))
        );

        if (!user) {
            setStatus('Selecione um usuário.', 'error');
            return;
        }

        if (!role) {
            setStatus('Informe o cargo.', 'error');
            return;
        }

        if (!selectedCenters.length) {
            setStatus('Selecione ao menos um centro.', 'error');
            return;
        }

        state.config.gestores = state.config.gestores
            .filter((manager) => manager.codigo_usuario !== user.codigo_usuario)
            .concat({
                codigo_usuario: user.codigo_usuario,
                nome_usuario: user.nome_usuario,
                login_usuario: user.login_usuario,
                cargo: role,
                centros_custo: selectedCenters,
            })
            .sort((a, b) => a.nome_usuario.localeCompare(b.nome_usuario));

        renderAll();
        closeModal('modalCentroCustoGestor');
        setStatus(`Gestor ${user.nome_usuario} pronto para salvar.`, 'success');
    };

    const applyOffCenters = () => {
        syncOffCenters(state.draftOffCodes);
        renderAll();
        closeModal('modalCentroCustoOff');
        setStatus('Lista OFF atualizada. Falta salvar.', 'info');
    };

    const removeManager = (userId) => {
        state.config.gestores = state.config.gestores.filter((manager) => manager.codigo_usuario !== Number(userId));
        renderAll();
        setStatus('Gestor removido. Falta salvar.', 'info');
    };

    const saveConfig = async () => {
        saveBtn.disabled = true;

        try {
            const payload = {
                gestores: state.config.gestores.map((manager) => ({
                    codigo_usuario: manager.codigo_usuario,
                    cargo: manager.cargo,
                    centros_custo: manager.centros_custo.map((center) => center.codigo),
                })),
                centros_custo_off: state.config.centros_custo_off.map((center) => center.codigo),
            };

            const response = await fetch(app.dataset.saveUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });

            const data = await response.json();
            if (!response.ok || data.status !== 'success') {
                throw new Error(data.message || 'Não foi possível salvar.');
            }

            state.config = normalizeConfig(data.data?.configuracao || {});
            renderAll();
            setStatus(data.message || 'Configuração salva.', 'success');
        } catch (error) {
            setStatus(error.message || 'Não foi possível salvar.', 'error');
        } finally {
            saveBtn.disabled = false;
        }
    };

    openManagerBtn.addEventListener('click', () => openManagerModal(null));
    openOffBtn.addEventListener('click', openOffModalDraft);
    saveBtn.addEventListener('click', saveConfig);
    managerApplyBtn.addEventListener('click', applyManager);
    offApplyBtn.addEventListener('click', applyOffCenters);

    managerFilterInput.addEventListener('input', () => {
        state.managerFilter = managerFilterInput.value || '';
        renderManagers();
    });

    userSearch.addEventListener('input', () => {
        state.userFilter = userSearch.value || '';
        if (!state.userFilter.trim()) {
            state.selectedUserId = null;
        }
        renderUserResults();
    });

    userResults.addEventListener('click', (event) => {
        const button = event.target.closest('[data-user]');
        if (!button) {
            return;
        }

        state.selectedUserId = Number(button.dataset.user);
        state.userFilter = getSelectedUser()?.nome_usuario || '';
        userSearch.value = state.userFilter;

        const manager = getManager(state.selectedUserId);
        roleInput.value = manager?.cargo || roleInput.value;
        state.selectedCenterCodes = new Set((manager?.centros_custo || []).map((center) => center.codigo));
        renderUserResults();
        renderManagerCenterOptions();
    });

    managerCenterSearch.addEventListener('input', () => {
        state.centerFilter = managerCenterSearch.value || '';
        renderManagerCenterOptions();
    });

    managerCenterList.addEventListener('change', (event) => {
        const checkbox = event.target.closest('input[type="checkbox"]');
        if (!checkbox) {
            return;
        }

        if (checkbox.checked) {
            state.selectedCenterCodes.add(checkbox.value);
        } else {
            state.selectedCenterCodes.delete(checkbox.value);
        }

        renderManagerCenterOptions();
    });

    offSearch.addEventListener('input', () => {
        state.offFilter = offSearch.value || '';
        renderOffOptions();
    });

    offList.addEventListener('change', (event) => {
        const checkbox = event.target.closest('input[type="checkbox"]');
        if (!checkbox) {
            return;
        }

        if (checkbox.checked) {
            state.draftOffCodes.add(checkbox.value);
        } else {
            state.draftOffCodes.delete(checkbox.value);
        }

        renderOffOptions();
    });

    managerList.addEventListener('click', (event) => {
        const editButton = event.target.closest('[data-edit-user]');
        if (editButton) {
            openManagerModal(Number(editButton.dataset.editUser));
            return;
        }

        const removeButton = event.target.closest('[data-remove-user]');
        if (removeButton) {
            removeManager(Number(removeButton.dataset.removeUser));
        }
    });

    document.addEventListener('click', (event) => {
        if (event.target.closest('[data-open-off]')) {
            openOffModalDraft();
        }
    });

    renderAll();
})();