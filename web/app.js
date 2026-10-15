/**
 * Microservices Matrix Analyzer - Frontend Logic
 */

let appState = {
    result: null,
    manualFiles: [],
    autogenFiles: [],
    filters: {
        search: '',
        method: 'ALL',
        status: 'ALL'
    }
};

const elements = {
    themeToggle: document.getElementById('btnThemeToggle'),
    loadDemoBtn: document.getElementById('btnLoadDemo'),
    analyzeBtn: document.getElementById('btnAnalyze'),
    analyzeSpinner: document.getElementById('analyzeSpinner'),
    errorBanner: document.getElementById('errorBanner'),
    resultsSection: document.getElementById('resultsSection'),

    manualPathInput: document.getElementById('manualPathInput'),
    autogenPathInput: document.getElementById('autogenPathInput'),
    manualFolderInput: document.getElementById('manualFolderInput'),
    autogenFolderInput: document.getElementById('autogenFolderInput'),
    manualDropzone: document.getElementById('manualDropzone'),
    autogenDropzone: document.getElementById('autogenDropzone'),
    manualStatus: document.getElementById('manualStatus'),
    autogenStatus: document.getElementById('autogenStatus'),
    manualFileCount: document.getElementById('manualFileCount'),
    autogenFileCount: document.getElementById('autogenFileCount'),

    statTotal: document.getElementById('statTotal'),
    statMatched: document.getElementById('statMatched'),
    statMatchedPercent: document.getElementById('statMatchedPercent'),
    statDivergent: document.getElementById('statDivergent'),
    statIdentical: document.getElementById('statIdentical'),
    statOrphans: document.getElementById('statOrphans'),
    statManualOnly: document.getElementById('statManualOnly'),
    statAutogenOnly: document.getElementById('statAutogenOnly'),

    matrixSearch: document.getElementById('matrixSearch'),
    methodFilterPills: document.getElementById('methodFilterPills'),
    statusFilterPills: document.getElementById('statusFilterPills'),
    matrixTableBody: document.getElementById('matrixTableBody'),

    btnExportCSV: document.getElementById('btnExportCSV'),
    btnExportJSON: document.getElementById('btnExportJSON'),
    btnExportHTML: document.getElementById('btnExportHTML'),

    diffModal: document.getElementById('paramDiffModal'),
    modalCloseBtn: document.getElementById('modalCloseBtn'),
    modalEndpointBadge: document.getElementById('modalEndpointBadge'),
    modalHeading: document.getElementById('modalHeading'),
    modalSummaryBanner: document.getElementById('modalSummaryBanner'),
    modalParamTableBody: document.getElementById('modalParamTableBody'),
    modalManualLoc: document.getElementById('modalManualLoc'),
    modalAutogenLoc: document.getElementById('modalAutogenLoc'),
    modalManualCode: document.getElementById('modalManualCode'),
    modalAutogenCode: document.getElementById('modalAutogenCode'),

    // Example Code & Dependency Modal
    callExampleModal: document.getElementById('callExampleModal'),
    exampleModalCloseBtn: document.getElementById('exampleModalCloseBtn'),
    exampleModalEndpointBadge: document.getElementById('exampleModalEndpointBadge'),
    exampleModalHeading: document.getElementById('exampleModalHeading'),
    exampleModalBanner: document.getElementById('exampleModalBanner'),
    exampleModalDepFile: document.getElementById('exampleModalDepFile'),
    exampleModalImports: document.getElementById('exampleModalImports'),
    exampleModalInstantiation: document.getElementById('exampleModalInstantiation'),
    exampleModalCall: document.getElementById('exampleModalCall'),
    exampleModalFullCode: document.getElementById('exampleModalFullCode'),
    btnCopyExampleCode: document.getElementById('btnCopyExampleCode'),

    // Tabs
    tabMatrix: document.getElementById('tabMatrix'),
    tabMigrate: document.getElementById('tabMigrate'),
    viewMatrix: document.getElementById('viewMatrix'),
    viewMigrate: document.getElementById('viewMigrate'),

    // Migration View Elements
    migTargetInput: document.getElementById('migTargetInput'),
    migManualInput: document.getElementById('migManualInput'),
    migAutogenInput: document.getElementById('migAutogenInput'),
    migExampleInput: document.getElementById('migExampleInput'),
    btnMigrateLoadDemo: document.getElementById('btnMigrateLoadDemo'),
    btnMigratePreview: document.getElementById('btnMigratePreview'),
    btnMigrateApply: document.getElementById('btnMigrateApply'),
    migPreviewSpinner: document.getElementById('migPreviewSpinner'),
    migApplySpinner: document.getElementById('migApplySpinner'),
    migErrorBanner: document.getElementById('migErrorBanner'),
    migResultsSection: document.getElementById('migResultsSection'),
    migStatScanned: document.getElementById('migStatScanned'),
    migStatModified: document.getElementById('migStatModified'),
    migStatCalls: document.getElementById('migStatCalls'),
    migFilesContainer: document.getElementById('migFilesContainer')
};

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    setupTabs();
    setupEventListeners();
    setupDragAndDrop();
    setupMigrationListeners();
    loadDemoData();
});

function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);

    elements.themeToggle.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', nextTheme);
        localStorage.setItem('theme', nextTheme);
        updateThemeIcon(nextTheme);
    });
}

function updateThemeIcon(theme) {
    elements.themeToggle.querySelector('.theme-icon').textContent = theme === 'dark' ? '🌙' : '☀️';
}

function setupEventListeners() {
    elements.loadDemoBtn.addEventListener('click', loadDemoData);
    elements.analyzeBtn.addEventListener('click', executeAnalysis);

    elements.matrixSearch.addEventListener('input', (e) => {
        appState.filters.search = e.target.value.toLowerCase().trim();
        renderMatrixTable();
    });

    elements.methodFilterPills.addEventListener('click', (e) => {
        if (e.target.classList.contains('pill')) {
            elements.methodFilterPills.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
            e.target.classList.add('active');
            appState.filters.method = e.target.getAttribute('data-method');
            renderMatrixTable();
        }
    });

    elements.statusFilterPills.addEventListener('click', (e) => {
        if (e.target.classList.contains('pill')) {
            elements.statusFilterPills.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
            e.target.classList.add('active');
            appState.filters.status = e.target.getAttribute('data-status');
            renderMatrixTable();
        }
    });

    elements.btnExportCSV.addEventListener('click', exportCSV);
    elements.btnExportJSON.addEventListener('click', exportJSON);
    elements.btnExportHTML.addEventListener('click', exportHTML);

    elements.modalCloseBtn.addEventListener('click', () => {
        elements.diffModal.close();
    });

    elements.diffModal.addEventListener('click', (e) => {
        if (e.target === elements.diffModal) {
            elements.diffModal.close();
        }
    });

    if (elements.exampleModalCloseBtn) {
        elements.exampleModalCloseBtn.addEventListener('click', () => {
            elements.callExampleModal.close();
        });
    }

    if (elements.callExampleModal) {
        elements.callExampleModal.addEventListener('click', (e) => {
            if (e.target === elements.callExampleModal) {
                elements.callExampleModal.close();
            }
        });
    }

    elements.manualFolderInput.addEventListener('change', (e) => handleFileSelection(e, 'manual'));
    elements.autogenFolderInput.addEventListener('change', (e) => handleFileSelection(e, 'autogen'));
}

function setupDragAndDrop() {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        elements.manualDropzone.addEventListener(eventName, preventDefaults, false);
        elements.autogenDropzone.addEventListener(eventName, preventDefaults, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        elements.manualDropzone.addEventListener(eventName, () => elements.manualDropzone.classList.add('dragover'), false);
        elements.autogenDropzone.addEventListener(eventName, () => elements.autogenDropzone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        elements.manualDropzone.addEventListener(eventName, () => elements.manualDropzone.classList.remove('dragover'), false);
        elements.autogenDropzone.addEventListener(eventName, () => elements.autogenDropzone.classList.remove('dragover'), false);
    });

    elements.manualDropzone.addEventListener('drop', (e) => handleDrop(e, 'manual'), false);
    elements.autogenDropzone.addEventListener('drop', (e) => handleDrop(e, 'autogen'), false);
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

async function handleFileSelection(e, type) {
    const files = Array.from(e.target.files);
    await processFiles(files, type);
}

async function handleDrop(e, type) {
    const dt = e.dataTransfer;
    const files = Array.from(dt.files);
    await processFiles(files, type);
}

async function processFiles(files, type) {
    const pyFiles = files.filter(f => f.name.endsWith('.py'));
    const fileList = [];

    for (const file of pyFiles) {
        const content = await file.text();
        const relPath = file.webkitRelativePath || file.name;
        fileList.push({ path: relPath, content: content });
    }

    if (type === 'manual') {
        appState.manualFiles = fileList;
        elements.manualStatus.textContent = `Prêt (${fileList.length} fichier(s))`;
        elements.manualFileCount.textContent = `✓ ${fileList.length} fichiers .py chargés`;
    } else {
        appState.autogenFiles = fileList;
        elements.autogenStatus.textContent = `Prêt (${fileList.length} fichier(s))`;
        elements.autogenFileCount.textContent = `✓ ${fileList.length} fichiers .py chargés`;
    }
}

async function loadDemoData() {
    setLoading(true);
    clearError();

    try {
        const response = await fetch('/api/samples');
        if (!response.ok) {
            throw new Error(`Erreur lors du chargement de la démo: ${response.statusText}`);
        }
        const data = await response.json();
        appState.result = data;
        displayResults(data);
    } catch (err) {
        showError(`Impossible de charger l'exemple démo : ${err.message}`);
    } finally {
        setLoading(false);
    }
}

async function executeAnalysis() {
    setLoading(true);
    clearError();

    const payload = {};
    if (appState.manualFiles.length > 0 && appState.autogenFiles.length > 0) {
        payload.manual_files = appState.manualFiles;
        payload.autogen_files = appState.autogenFiles;
    } else {
        payload.manual_path = elements.manualPathInput.value.trim();
        payload.autogen_path = elements.autogenPathInput.value.trim();
    }

    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Erreur lors de l\'analyse');
        }

        appState.result = data;
        displayResults(data);
    } catch (err) {
        showError(err.message);
    } finally {
        setLoading(false);
    }
}

function displayResults(data) {
    elements.resultsSection.hidden = false;

    const totalEndpoints = (data.manual_endpoints_count || 0) + (data.autogen_only_count || 0);
    animateCounter(elements.statTotal, totalEndpoints);
    animateCounter(elements.statMatched, data.matched_count);

    const matchRate = totalEndpoints > 0 ? Math.round((data.matched_count / totalEndpoints) * 100) : 0;
    elements.statMatchedPercent.textContent = `${matchRate}%`;

    animateCounter(elements.statDivergent, data.divergent_count);
    animateCounter(elements.statIdentical, data.identical_count);
    animateCounter(elements.statOrphans, data.manual_only_count + data.autogen_only_count);

    elements.statManualOnly.textContent = `${data.manual_only_count} manuel`;
    elements.statAutogenOnly.textContent = `${data.autogen_only_count} autogénéré`;

    renderMatrixTable();
    elements.resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderMatrixTable() {
    if (!appState.result || !appState.result.matches) return;

    const tbody = elements.matrixTableBody;
    tbody.innerHTML = '';

    const { search, method, status } = appState.filters;

    const filtered = appState.result.matches.filter(m => {
        if (method !== 'ALL' && m.http_method !== method) return false;

        if (status === 'MATCHED' && m.status !== 'MATCHED') return false;
        if (status === 'DIVERGENT' && !(m.status === 'MATCHED' && m.param_status === 'DIVERGENT')) return false;
        if (status === 'IDENTICAL' && !(m.status === 'MATCHED' && m.param_status === 'IDENTICAL')) return false;
        if (status === 'MANUAL_ONLY' && m.status !== 'MANUAL_ONLY') return false;
        if (status === 'AUTOGEN_ONLY' && m.status !== 'AUTOGEN_ONLY') return false;

        if (search) {
            const mFunc = m.manual_call ? m.manual_call.function_name.toLowerCase() : '';
            const mFile = m.manual_call ? m.manual_call.file_path.toLowerCase() : '';
            const aFunc = m.autogen_call ? m.autogen_call.function_name.toLowerCase() : '';
            const aFile = m.autogen_call ? m.autogen_call.file_path.toLowerCase() : '';
            const ep = m.normalized_endpoint.toLowerCase();
            const rawM = m.raw_endpoint_manual ? m.raw_endpoint_manual.toLowerCase() : '';
            const rawA = m.raw_endpoint_autogen ? m.raw_endpoint_autogen.toLowerCase() : '';
            const diffs = (m.param_diffs || []).map(d => d.name.toLowerCase()).join(' ');

            return mFunc.includes(search) || mFile.includes(search) ||
                   aFunc.includes(search) || aFile.includes(search) ||
                   ep.includes(search) || rawM.includes(search) ||
                   rawA.includes(search) || diffs.includes(search);
        }

        return true;
    });

    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align:center; padding: 48px; color: var(--text-dim);">
                    Aucun endpoint ne correspond aux critères de filtre sélectionnés.
                </td>
            </tr>
        `;
        return;
    }

    filtered.forEach(m => {
        const tr = document.createElement('tr');

        const epHtml = `
            <div class="endpoint-cell">
                <span class="badge-method ${m.http_method}">${m.http_method}</span>
                <div>
                    <div class="endpoint-canonical" title="${m.normalized_endpoint}">${m.normalized_endpoint}</div>
                    <div class="endpoint-raw">${m.raw_endpoint_manual || m.raw_endpoint_autogen || ''}</div>
                </div>
            </div>
        `;

        let manualHtml = '';
        if (m.manual_call) {
            const kindBadge = m.manual_call.kind === 'client_call' ? 'Client' : 'Route';
            const calleeBadge = m.manual_call.callee_function ? 
                `<span class="func-meta-badge" style="color:#c084fc; background:rgba(168,85,247,0.12);" title="Fonction parente appelant ${escapeHtml(m.manual_call.callee_function)}()">via ${escapeHtml(m.manual_call.callee_function)}()</span>` : '';
            manualHtml = `
                <div class="func-cell">
                    <span class="func-signature">${escapeHtml(m.manual_call.function_name)}()</span>
                    <div class="func-meta">
                        <span class="func-meta-badge">${kindBadge}</span>
                        ${calleeBadge}
                        <span>${escapeHtml(m.manual_call.file_path)}:${m.manual_call.line_number}</span>
                    </div>
                </div>
            `;
        } else {
            manualHtml = '<span style="color: var(--text-dim); font-style: italic;">Non présent</span>';
        }

        let autogenHtml = '';
        if (m.autogen_call) {
            const kindBadge = m.autogen_call.kind === 'client_call' ? 'Client' : 'Route';
            const calleeBadge = m.autogen_call.callee_function ? 
                `<span class="func-meta-badge" style="color:#c084fc; background:rgba(168,85,247,0.12);" title="Fonction parente appelant ${escapeHtml(m.autogen_call.callee_function)}()">via ${escapeHtml(m.autogen_call.callee_function)}()</span>` : '';
            autogenHtml = `
                <div class="func-cell">
                    <span class="func-signature">${escapeHtml(m.autogen_call.function_name)}()</span>
                    <div class="func-meta">
                        <span class="func-meta-badge">${kindBadge}</span>
                        ${calleeBadge}
                        <span>${escapeHtml(m.autogen_call.file_path)}:${m.autogen_call.line_number}</span>
                    </div>
                </div>
            `;
        } else {
            autogenHtml = '<span style="color: var(--text-dim); font-style: italic;">Non généré</span>';
        }

        let statusHtml = '';
        let chipsHtml = '';

        if (m.status === 'MATCHED') {
            if (m.param_status === 'IDENTICAL') {
                statusHtml = `<span class="status-pill MATCHED-IDENTICAL">✓ 100% Identique</span>`;
            } else if (m.param_status === 'COMPATIBLE') {
                statusHtml = `<span class="status-pill MATCHED-COMPATIBLE">✓ Compatible</span>`;
            } else {
                statusHtml = `<span class="status-pill MATCHED-DIVERGENT">⚠️ Divergent</span>`;
            }

            const diffs = (m.param_diffs || []).filter(d => d.status !== 'identical');
            if (diffs.length > 0) {
                chipsHtml = '<div class="diff-preview-chips">' + diffs.slice(0, 3).map(d => {
                    let chipClass = 'type';
                    if (d.status === 'renamed_candidate') chipClass = 'renamed';
                    else if (d.status === 'manual_only') chipClass = 'missing';
                    else if (d.status === 'autogen_only') chipClass = 'added';
                    return `<span class="diff-chip ${chipClass}">${escapeHtml(d.name)}</span>`;
                }).join('') + (diffs.length > 3 ? `<span class="diff-chip">+${diffs.length - 3}</span>` : '') + '</div>';
            }
        } else if (m.status === 'MANUAL_ONLY') {
            statusHtml = `<span class="status-pill MANUAL_ONLY">Manuel seul</span>`;
        } else {
            statusHtml = `<span class="status-pill AUTOGEN_ONLY">Autogénéré seul</span>`;
        }

        const hasAutogen = !!m.autogen_call && !!m.call_example;
        const codeBtnHtml = hasAutogen ? `
            <button class="btn btn-outline btn-sm btn-example-code" onclick="openExampleModal('${m.id}')" title="Exemple d'appel & imports (selon _dependency)">
                ⚡ Code
            </button>
        ` : '';

        const actionHtml = `
            <div class="action-buttons-group">
                <button class="btn btn-outline btn-sm" onclick="openDiffModal('${m.id}')" title="Voir les différences de paramètres">
                    Diff
                </button>
                ${codeBtnHtml}
            </div>
        `;

        tr.innerHTML = `
            <td>${epHtml}</td>
            <td>${manualHtml}</td>
            <td>${autogenHtml}</td>
            <td>${statusHtml}${chipsHtml}</td>
            <td style="text-align: center;">${actionHtml}</td>
        `;

        tbody.appendChild(tr);
    });
}

window.openDiffModal = function(matchId) {
    if (!appState.result) return;
    const match = appState.result.matches.find(m => m.id === matchId);
    if (!match) return;

    elements.modalEndpointBadge.innerHTML = `
        <span class="badge-method ${match.http_method}">${match.http_method}</span>
        <span style="font-family: var(--font-mono); font-weight: 600; margin-left: 8px;">${match.normalized_endpoint}</span>
    `;

    let bannerClass = match.param_status;
    let bannerText = match.summary;
    if (match.status !== 'MATCHED') {
        bannerClass = 'DIVERGENT';
    }
    elements.modalSummaryBanner.className = `diff-summary-banner ${bannerClass}`;
    elements.modalSummaryBanner.textContent = bannerText;

    const pBody = elements.modalParamTableBody;
    pBody.innerHTML = '';

    if (match.param_diffs && match.param_diffs.length > 0) {
        match.param_diffs.forEach(d => {
            const tr = document.createElement('tr');
            tr.className = `param-row ${d.status}`;

            const mInfo = d.manual_param ? 
                `<code>${escapeHtml(d.manual_param.name)}: ${escapeHtml(d.manual_param.type_annotation || 'Any')}</code> ${d.manual_param.required ? '<b style="color:var(--danger)">*</b>' : '<span style="color:var(--text-dim)">opt</span>'}` 
                : '<span style="color:var(--text-dim)">-</span>';

            const aInfo = d.autogen_param ? 
                `<code>${escapeHtml(d.autogen_param.name)}: ${escapeHtml(d.autogen_param.type_annotation || 'Any')}</code> ${d.autogen_param.required ? '<b style="color:var(--danger)">*</b>' : '<span style="color:var(--text-dim)">opt</span>'}` 
                : '<span style="color:var(--text-dim)">-</span>';

            let statusLabel = '';
            if (d.status === 'identical') statusLabel = '<span style="color:var(--success); font-weight:600;">✓ Identique</span>';
            else if (d.status === 'type_mismatch') statusLabel = '<span style="color:var(--warning); font-weight:600;">⚠️ Type mismatch</span>';
            else if (d.status === 'default_mismatch') statusLabel = '<span style="color:var(--info); font-weight:600;">Valeur défaut</span>';
            else if (d.status === 'renamed_candidate') statusLabel = '<span style="color:var(--purple); font-weight:600;">Renommé</span>';
            else if (d.status === 'manual_only') statusLabel = '<span style="color:var(--danger); font-weight:600;">Manuel seul</span>';
            else statusLabel = '<span style="color:#ec4899; font-weight:600;">Autogénéré seul</span>';

            tr.innerHTML = `
                <td><b>${escapeHtml(d.name)}</b></td>
                <td>${mInfo}</td>
                <td>${aInfo}</td>
                <td>${statusLabel}</td>
                <td style="color: var(--text-muted);">${escapeHtml(d.details)}</td>
            `;
            pBody.appendChild(tr);
        });
    } else {
        pBody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 20px; color: var(--text-dim);">Aucun paramètre détecté pour cet endpoint.</td></tr>';
    }

    elements.modalManualLoc.innerHTML = match.manual_call ? 
        `${escapeHtml(match.manual_call.file_path)}:${match.manual_call.line_number}` + (match.manual_call.callee_function ? ` <span style="color:#c084fc; font-weight:600;">(appelle ${escapeHtml(match.manual_call.callee_function)}())</span>` : '') 
        : 'N/A';
    elements.modalAutogenLoc.innerHTML = match.autogen_call ? 
        `${escapeHtml(match.autogen_call.file_path)}:${match.autogen_call.line_number}` + (match.autogen_call.callee_function ? ` <span style="color:#c084fc; font-weight:600;">(appelle ${escapeHtml(match.autogen_call.callee_function)}())</span>` : '') 
        : 'N/A';

    elements.modalManualCode.textContent = match.manual_call ? match.manual_call.code_snippet : '# Aucun code manuel disponible pour cet endpoint';
    elements.modalAutogenCode.textContent = match.autogen_call ? match.autogen_call.code_snippet : '# Aucun code autogénéré disponible pour cet endpoint';

    elements.diffModal.showModal();
};

window.openExampleModal = function(matchId) {
    if (!appState.result) return;
    const match = appState.result.matches.find(m => m.id === matchId);
    if (!match || !match.call_example) return;

    const ex = match.call_example;

    elements.exampleModalEndpointBadge.innerHTML = `
        <span class="badge-method ${match.http_method}">${match.http_method}</span>
        <span style="font-family: var(--font-mono); font-weight: 600; margin-left: 8px;">${escapeHtml(match.normalized_endpoint)}</span>
    `;

    const funcName = match.autogen_call ? match.autogen_call.function_name : ex.function_name;
    elements.exampleModalHeading.textContent = `Exemple d'appel : ${funcName}()`;

    const depFile = ex.dependency_file || (appState.result.dependency_file ? escapeHtml(appState.result.dependency_file) : null);
    if (depFile) {
        elements.exampleModalDepFile.textContent = `📦 Fichier source: ${depFile}`;
        elements.exampleModalDepFile.style.display = 'inline-block';
    } else {
        elements.exampleModalDepFile.textContent = `⚙️ Déclaration par défaut`;
        elements.exampleModalDepFile.style.display = 'inline-block';
    }

    elements.exampleModalBanner.className = 'diff-summary-banner COMPATIBLE';
    elements.exampleModalBanner.innerHTML = `Fonction autogénérée <code>${escapeHtml(funcName)}()</code> prête à l'emploi avec instanciation de la classe <code>${escapeHtml(ex.class_name)}</code>.`;

    elements.exampleModalImports.textContent = (ex.imports || []).join('\n');
    elements.exampleModalInstantiation.textContent = ex.instantiation || '';
    elements.exampleModalCall.textContent = ex.call_snippet || '';
    elements.exampleModalFullCode.textContent = ex.full_code || '';

    elements.btnCopyExampleCode.onclick = () => {
        navigator.clipboard.writeText(ex.full_code || '').then(() => {
            const originalText = elements.btnCopyExampleCode.innerHTML;
            elements.btnCopyExampleCode.innerHTML = '✓ Code copié !';
            elements.btnCopyExampleCode.style.background = '#10b981';
            setTimeout(() => {
                elements.btnCopyExampleCode.innerHTML = originalText;
                elements.btnCopyExampleCode.style.background = '';
            }, 2000);
        }).catch(err => {
            console.error('Erreur lors de la copie:', err);
        });
    };

    elements.callExampleModal.showModal();
};

async function exportCSV() {
    if (!appState.result) return;
    try {
        const res = await fetch('/api/export/csv', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(getExportPayload())
        });
        const blob = await res.blob();
        downloadBlob(blob, 'matrice_microservices.csv');
    } catch (err) {
        showError(`Erreur export CSV: ${err.message}`);
    }
}

async function exportJSON() {
    if (!appState.result) return;
    try {
        const res = await fetch('/api/export/json', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(getExportPayload())
        });
        const blob = await res.blob();
        downloadBlob(blob, 'matrice_microservices.json');
    } catch (err) {
        showError(`Erreur export JSON: ${err.message}`);
    }
}

async function exportHTML() {
    if (!appState.result) return;
    try {
        const res = await fetch('/api/export/html', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(getExportPayload())
        });
        const blob = await res.blob();
        downloadBlob(blob, 'rapport_correspondance.html');
    } catch (err) {
        showError(`Erreur export HTML: ${err.message}`);
    }
}

function getExportPayload() {
    if (appState.manualFiles.length > 0 && appState.autogenFiles.length > 0) {
        return {
            manual_files: appState.manualFiles,
            autogen_files: appState.autogenFiles
        };
    }
    return {
        manual_path: elements.manualPathInput.value.trim(),
        autogen_path: elements.autogenPathInput.value.trim()
    };
}

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function setLoading(isLoading) {
    elements.analyzeSpinner.hidden = !isLoading;
    elements.analyzeBtn.disabled = isLoading;
}

function showError(msg) {
    elements.errorBanner.textContent = msg;
    elements.errorBanner.hidden = false;
}

function clearError() {
    elements.errorBanner.hidden = true;
    elements.errorBanner.textContent = '';
}

function animateCounter(el, target) {
    let current = 0;
    const duration = 600;
    const stepTime = 20;
    const steps = duration / stepTime;
    const increment = target / steps;

    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            el.textContent = target;
            clearInterval(timer);
        } else {
            el.textContent = Math.round(current);
        }
    }, stepTime);
}

function escapeHtml(str) {
    if (!str) return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

/* Tab Navigation */
function setupTabs() {
    elements.tabMatrix.addEventListener('click', () => switchTab('matrix'));
    elements.tabMigrate.addEventListener('click', () => switchTab('migrate'));
}

function switchTab(tab) {
    if (tab === 'matrix') {
        elements.tabMatrix.classList.add('active');
        elements.tabMigrate.classList.remove('active');
        elements.viewMatrix.hidden = false;
        elements.viewMigrate.hidden = true;
    } else {
        elements.tabMigrate.classList.add('active');
        elements.tabMatrix.classList.remove('active');
        elements.viewMigrate.hidden = false;
        elements.viewMatrix.hidden = true;
    }
}

/* Migration View Logic */
function setupMigrationListeners() {
    elements.btnMigrateLoadDemo.addEventListener('click', loadMigrationDemo);
    elements.btnMigratePreview.addEventListener('click', () => runMigration(false));
    elements.btnMigrateApply.addEventListener('click', () => {
        if (confirm("Confirmez-vous l'application en place des modifications sur le code source ? (Des sauvegardes .bak seront créées)")) {
            runMigration(true);
        }
    });
}

async function loadMigrationDemo() {
    try {
        const res = await fetch('/api/migrate/demo');
        const data = await res.json();
        elements.migTargetInput.value = data.target_path;
        elements.migManualInput.value = data.manual_path;
        elements.migAutogenInput.value = data.autogen_path;
        elements.migExampleInput.value = data.example_path;
        runMigration(false);
    } catch (err) {
        showMigError(`Impossible de charger la démo de migration : ${err.message}`);
    }
}

async function runMigration(applyInPlace = false) {
    clearMigError();
    const spinner = applyInPlace ? elements.migApplySpinner : elements.migPreviewSpinner;
    const btn = applyInPlace ? elements.btnMigrateApply : elements.btnMigratePreview;
    spinner.hidden = false;
    btn.disabled = true;

    const payload = {
        target_path: elements.migTargetInput.value.trim(),
        manual_path: elements.migManualInput.value.trim(),
        autogen_path: elements.migAutogenInput.value.trim(),
        example_path: elements.migExampleInput.value.trim(),
        apply_in_place: applyInPlace
    };

    const endpoint = applyInPlace ? '/api/migrate/apply' : '/api/migrate/preview';

    try {
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.error || 'Erreur lors de la migration');
        }
        displayMigrationResults(data, applyInPlace);
    } catch (err) {
        showMigError(err.message);
    } finally {
        spinner.hidden = true;
        btn.disabled = false;
    }
}

function displayMigrationResults(report, applyInPlace) {
    elements.migResultsSection.hidden = false;
    animateCounter(elements.migStatScanned, report.total_files_scanned);
    animateCounter(elements.migStatModified, report.files_modified_count);
    animateCounter(elements.migStatCalls, report.total_calls_migrated);

    const container = elements.migFilesContainer;
    container.innerHTML = '';

    const modified = (report.file_results || []).filter(f => f.changes_count > 0);
    if (modified.length === 0) {
        container.innerHTML = `
            <div style="text-align:center; padding: 48px; background:var(--bg-card); border-radius:var(--radius-md); border:1px solid var(--border);">
                <span style="font-size:36px;">🎉</span>
                <h3 style="margin-top:12px; font-weight:700;">Aucun appel à migrer</h3>
                <p style="color:var(--text-muted); font-size:14px; margin-top:4px;">Aucun fichier du répertoire ne contient d'appel au microservice manuel.</p>
            </div>
        `;
        return;
    }

    modified.forEach(f => {
        const card = document.createElement('div');
        card.className = 'mig-file-card';

        let diffHtml = '';
        if (f.diff) {
            diffHtml = f.diff.split('\n').map(line => {
                const escaped = escapeHtml(line);
                if (line.startsWith('+') && !line.startsWith('+++')) {
                    return `<span class="diff-line-add">${escaped}</span>`;
                } else if (line.startsWith('-') && !line.startsWith('---')) {
                    return `<span class="diff-line-del">${escaped}</span>`;
                } else if (line.startsWith('@@') || line.startsWith('---') || line.startsWith('+++')) {
                    return `<span class="diff-line-hdr">${escaped}</span>`;
                } else {
                    return `<span>${escaped}</span>\n`;
                }
            }).join('');
        }

        const rulesHtml = (f.applied_rules || []).map(r => `
            <div class="mig-rule-item">
                <span class="mig-rule-icon">✓</span>
                <span>${escapeHtml(r)}</span>
            </div>
        `).join('');

        const warningsHtml = (f.warnings || []).map(w => `
            <div class="mig-warning-item">
                <span>⚠️</span>
                <span>${escapeHtml(w)}</span>
            </div>
        `).join('');

        card.innerHTML = `
            <div class="mig-file-header">
                <span class="mig-file-title">
                    <span>📄</span>
                    <code>${escapeHtml(f.file_path)}</code>
                </span>
                <span class="status-pill MATCHED-IDENTICAL">${f.changes_count} modification(s)</span>
            </div>
            ${rulesHtml || warningsHtml ? `<div class="mig-rules-list">${rulesHtml}${warningsHtml}</div>` : ''}
            <div class="mig-diff-view">${diffHtml}</div>
        `;
        container.appendChild(card);
    });

    elements.migResultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function showMigError(msg) {
    elements.migErrorBanner.textContent = msg;
    elements.migErrorBanner.hidden = false;
}

function clearMigError() {
    elements.migErrorBanner.hidden = true;
    elements.migErrorBanner.textContent = '';
}
