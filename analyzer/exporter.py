"""
Export utilities for Analysis Results (JSON, CSV, Standalone HTML Report).
"""
import json
import csv
import io
from typing import Dict, Any
from .models import AnalysisResult

def export_to_json(result: AnalysisResult) -> str:
    return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)

def export_to_csv(result: AnalysisResult) -> str:
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    writer.writerow([
        "ID",
        "Méthode HTTP",
        "Endpoint Normalisé",
        "Statut Correspondance",
        "Statut Paramètres",
        "Fonction Manuelle",
        "Fichier Manuel",
        "Ligne Manuel",
        "Fonction Autogénérée",
        "Fichier Autogénéré",
        "Ligne Autogénérée",
        "Nb Différences Paramètres",
        "Détail Différences",
        "Résumé"
    ])

    for match in result.matches:
        m_func = match.manual_call.function_name if match.manual_call else ""
        m_file = match.manual_call.file_path if match.manual_call else ""
        m_line = match.manual_call.line_number if match.manual_call else ""

        a_func = match.autogen_call.function_name if match.autogen_call else ""
        a_file = match.autogen_call.file_path if match.autogen_call else ""
        a_line = match.autogen_call.line_number if match.autogen_call else ""

        non_identical = [d for d in match.param_diffs if d.status != "identical"]
        diff_count = len(non_identical)
        diff_details = " | ".join([f"{d.name} ({d.status}): {d.details}" for d in non_identical])

        writer.writerow([
            match.id,
            match.http_method,
            match.normalized_endpoint,
            match.status,
            match.param_status,
            m_func,
            m_file,
            m_line,
            a_func,
            a_file,
            a_line,
            diff_count,
            diff_details,
            match.summary
        ])

    return output.getvalue()


def export_to_standalone_html(result: AnalysisResult) -> str:
    data_json = json.dumps(result.to_dict(), ensure_ascii=False)

    html_template = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rapport d'Analyse de Correspondance Microservices</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0a0e17;
            --bg-secondary: #121826;
            --bg-card: rgba(22, 30, 49, 0.7);
            --bg-card-hover: rgba(28, 38, 62, 0.9);
            --border: rgba(255, 255, 255, 0.08);
            --border-hover: rgba(99, 102, 241, 0.3);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-primary: #6366f1;
            --accent-primary-hover: #4f46e5;
            --font-main: 'Outfit', sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
            --radius-sm: 8px;
            --radius-md: 14px;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: radial-gradient(circle at top right, #1e1b4b 0%, var(--bg-primary) 50%);
            color: var(--text-primary);
            font-family: var(--font-main);
            min-height: 100vh;
            padding: 32px 24px;
            line-height: 1.5;
        }}
        .container {{ max-width: 1440px; margin: 0 auto; }}
        header {{
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 32px; padding-bottom: 24px; border-bottom: 1px solid var(--border);
        }}
        .logo-title h1 {{
            font-size: 28px; font-weight: 800;
            background: linear-gradient(135deg, #a5b4fc, #6366f1, #38bdf8);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 32px; }}
        .stat-card {{ background: var(--bg-card); backdrop-filter: blur(12px); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 20px; }}
        .stat-value {{ font-size: 32px; font-weight: 800; margin-bottom: 4px; }}
        .stat-label {{ color: var(--text-secondary); font-size: 13px; text-transform: uppercase; font-weight: 500; }}
        .filters-toolbar {{ display: flex; flex-wrap: wrap; gap: 12px; justify-content: space-between; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 16px 20px; margin-bottom: 24px; }}
        .search-box input {{ background: var(--bg-secondary); border: 1px solid var(--border); color: var(--text-primary); padding: 10px 16px; border-radius: var(--radius-sm); font-size: 14px; width: 320px; outline: none; }}
        .filter-buttons {{ display: flex; gap: 8px; flex-wrap: wrap; }}
        .filter-btn {{ background: var(--bg-secondary); border: 1px solid var(--border); color: var(--text-secondary); padding: 8px 14px; border-radius: var(--radius-sm); font-size: 13px; cursor: pointer; }}
        .filter-btn.active {{ background: var(--accent-primary); color: white; border-color: var(--accent-primary); }}
        .matrix-table-container {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md); overflow: hidden; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; text-align: left; }}
        th {{ background: rgba(18, 24, 38, 0.85); padding: 16px 20px; font-size: 12px; text-transform: uppercase; color: var(--text-secondary); border-bottom: 1px solid var(--border); }}
        td {{ padding: 16px 20px; border-bottom: 1px solid var(--border); }}
        .badge-method {{ display: inline-block; font-family: var(--font-mono); font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 6px; text-align: center; min-width: 55px; }}
        .badge-method.GET {{ background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }}
        .badge-method.POST {{ background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); }}
        .badge-method.PUT {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }}
        .badge-method.DELETE {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }}
        .badge-method.PATCH {{ background: rgba(139, 92, 246, 0.15); color: #a78bfa; border: 1px solid rgba(139, 92, 246, 0.3); }}
        .status-pill {{ padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; display: inline-block; }}
        .status-pill.MATCHED {{ background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }}
        .status-pill.DIVERGENT {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }}
        .status-pill.IDENTICAL {{ background: rgba(6, 182, 212, 0.15); color: #22d3ee; border: 1px solid rgba(6, 182, 212, 0.3); }}
        .status-pill.MANUAL_ONLY {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }}
        .status-pill.AUTOGEN_ONLY {{ background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo-title">
                <h1>Matrice de Correspondance des Microservices</h1>
                <p>Comparaison des endpoints et analyse différentielle des paramètres</p>
            </div>
        </header>

        <section class="stats-grid">
            <div class="stat-card">
                <div class="stat-value" style="color: #6366f1;">{result.manual_endpoints_count + result.autogen_only_count}</div>
                <div class="stat-label">Total Endpoints</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #10b981;">{result.matched_count}</div>
                <div class="stat-label">Correspondances</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #f59e0b;">{result.divergent_count}</div>
                <div class="stat-label">Paramètres Divergents</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #06b6d4;">{result.identical_count}</div>
                <div class="stat-label">Paramètres Identiques</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #ef4444;">{result.manual_only_count + result.autogen_only_count}</div>
                <div class="stat-label">Sans Correspondance</div>
            </div>
        </section>

        <div class="filters-toolbar">
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="Rechercher..." oninput="filterTable()">
            </div>
            <div class="filter-buttons">
                <button class="filter-btn active" onclick="setFilter('ALL', this)">Tous</button>
                <button class="filter-btn" onclick="setFilter('MATCHED', this)">Correspondances ({result.matched_count})</button>
                <button class="filter-btn" onclick="setFilter('DIVERGENT', this)">Divergents ({result.divergent_count})</button>
                <button class="filter-btn" onclick="setFilter('IDENTICAL', this)">Identiques ({result.identical_count})</button>
                <button class="filter-btn" onclick="setFilter('MANUAL_ONLY', this)">Manuel seul ({result.manual_only_count})</button>
                <button class="filter-btn" onclick="setFilter('AUTOGEN_ONLY', this)">Autogénéré seul ({result.autogen_only_count})</button>
            </div>
        </div>

        <div class="matrix-table-container">
            <table>
                <thead>
                    <tr>
                        <th>Endpoint & Méthode</th>
                        <th>Microservice Manuel</th>
                        <th>Microservice Autogénéré</th>
                        <th>Statut</th>
                        <th>Détails</th>
                    </tr>
                </thead>
                <tbody id="matrixBody"></tbody>
            </table>
        </div>
    </div>

    <script>
        const reportData = {data_json};
        let currentFilter = 'ALL';

        function renderTable() {{
            const tbody = document.getElementById('matrixBody');
            const search = document.getElementById('searchInput').value.toLowerCase();
            tbody.innerHTML = '';

            const filtered = reportData.matches.filter(m => {{
                if (currentFilter === 'MATCHED' && m.status !== 'MATCHED') return false;
                if (currentFilter === 'DIVERGENT' && !(m.status === 'MATCHED' && m.param_status === 'DIVERGENT')) return false;
                if (currentFilter === 'IDENTICAL' && !(m.status === 'MATCHED' && m.param_status === 'IDENTICAL')) return false;
                if (currentFilter === 'MANUAL_ONLY' && m.status !== 'MANUAL_ONLY') return false;
                if (currentFilter === 'AUTOGEN_ONLY' && m.status !== 'AUTOGEN_ONLY') return false;

                if (search) {{
                    const mFunc = m.manual_call ? m.manual_call.function_name.toLowerCase() : '';
                    const aFunc = m.autogen_call ? m.autogen_call.function_name.toLowerCase() : '';
                    const ep = m.normalized_endpoint.toLowerCase();
                    return mFunc.includes(search) || aFunc.includes(search) || ep.includes(search);
                }}
                return true;
            }});

            filtered.forEach(m => {{
                const tr = document.createElement('tr');
                const mFunc = m.manual_call ? `${{m.manual_call.function_name}}() <br><small style="color:#64748b">${{m.manual_call.file_path}}:${{m.manual_call.line_number}}</small>` : '<em>Non présent</em>';
                const aFunc = m.autogen_call ? `${{m.autogen_call.function_name}}() <br><small style="color:#64748b">${{m.autogen_call.file_path}}:${{m.autogen_call.line_number}}</small>` : '<em>Non généré</em>';

                let statusBadge = '';
                if (m.status === 'MATCHED') {{
                    statusBadge = m.param_status === 'IDENTICAL' ? '<span class="status-pill IDENTICAL">Identique</span>' : (m.param_status === 'COMPATIBLE' ? '<span class="status-pill MATCHED">Compatible</span>' : '<span class="status-pill DIVERGENT">Divergent</span>');
                }} else {{
                    statusBadge = m.status === 'MANUAL_ONLY' ? '<span class="status-pill MANUAL_ONLY">Manuel seul</span>' : '<span class="status-pill AUTOGEN_ONLY">Autogénéré seul</span>';
                }}

                tr.innerHTML = `
                    <td><span class="badge-method ${{m.http_method}}">${{m.http_method}}</span> <code>${{m.normalized_endpoint}}</code></td>
                    <td>${{mFunc}}</td>
                    <td>${{aFunc}}</td>
                    <td>${{statusBadge}}</td>
                    <td style="font-size:12px; color:#94a3b8">${{m.summary}}</td>
                `;
                tbody.appendChild(tr);
            }});
        }}

        function setFilter(filter, btn) {{
            currentFilter = filter;
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderTable();
        }}

        function filterTable() {{ renderTable(); }}
        renderTable();
    </script>
</body>
</html>"""
    return html_template
