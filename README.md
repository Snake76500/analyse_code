# Microservices Matrix Analyzer ⚡

Outil d'analyse statique et de correspondance d'endpoints entre microservices développés manuellement et microservices autogénérés (à partir de fichiers `openai.json` / `openapi.json`).

L'outil analyse le code source Python (AST) des deux microservices sans exécution, réconcilie les fonctions appelant ou exposant les mêmes endpoints finaux, et met en évidence la divergence des paramètres d'appels.

---

## 🎯 Fonctionnalités Principales

- **Analyse AST Python (zero-dependency)** :
  - Détecte les **appels clients sortants** (`requests.*`, `httpx.*`, `aiohttp`, sessions, SDK clients générés `ApiClient`).
  - Détecte les **routes serveurs entrantes** (`@router.get`, `@app.post`, Flask `@app.route`, etc.).
  - Résout les f-strings, variables locales d'URL (`url = f"{BASE_URL}/..."`) et constantes de configuration.
- **Normalisation d'Endpoints Avancée** :
  - Harmonise les paramètres d'URL : `{id}`, `{user_id}`, `<int:id>`, `:id` ➔ `{PARAM}`.
  - Élimine les préfixes de versions ou de base URL (`/api/v1/users` ➔ `/users`).
- **Matrice de Correspondance & Détection des Écarts** :
  - Appariement exact et heuristique par méthode HTTP et chemin canonique.
  - Détection des endpoints orphelins (uniquement en manuel ou uniquement en autogénéré).
- **Analyse Différentielle des Paramètres d'Appels** :
  - Détection des paramètres identiques, optionnels, obligatoires.
  - Détection des **renommages** de paramètres (ex: `user_id` ➔ `id`, `quantity` ➔ `qty`, `page_size` ➔ `limit`).
  - Détection des **incompatibilités de types** (ex: `int` vs `str`, `Optional[...]`).
  - Détection des paramètres manquants ou ajoutés.
- **Interface Web Dashboard Moderne & Réactive** :
  - Dashboard interactif (KPIs animés, filtres dynamiques par méthode et statut, recherche textuelle instantanée).
  - Modal de diff avec tableau comparatif et extraits de code source côte-à-côte.
  - Support du glisser-déposer (Drag & Drop) de dossiers et sélecteur de dossiers HTML5.
  - Mode sombre / mode clair.
- **Exports Multi-formats** :
  - **HTML autonome** : Rapport interactif complet partageable (ouvrable hors ligne).
  - **CSV** : Compatible Excel / tableurs.
  - **JSON** : Intégration CI/CD et pipelines d'automatisation.
- **Mode CLI (Ligne de commande)** pour les scripts et pipelines.

---

## 🚀 Démarrage Rapide

### 1. Lancer l'Application Web

Exécutez simplement :
```bash
./run.sh
# ou
python3 server.py 8080
```
Ouvrez votre navigateur sur **[http://localhost:8080](http://localhost:8080)**.

> Le dashboard charge automatiquement un exemple complet de démonstration avec cas réels de divergences !

---

### 2. Utilisation en Ligne de Commande (CLI)

Vous pouvez également lancer des analyses directement depuis votre terminal :

```bash
python3 cli.py \
  --manual ./samples/manual_service \
  --autogen ./samples/autogen_service \
  --output rapport_correspondance.html \
  --json rapport.json \
  --csv matrice.csv \
  --open
```

#### Arguments CLI :
| Argument | Description |
|---|---|
| `--manual`, `-m` | Chemin vers le dossier du microservice manuel. |
| `--autogen`, `-a` | Chemin vers le dossier du microservice autogénéré. |
| `--output`, `-o` | Fichier de sortie du rapport HTML interactif (défaut: `rapport_correspondance.html`). |
| `--json`, `-j` | *(Optionnel)* Chemin de sortie du fichier JSON. |
| `--csv`, `-c` | *(Optionnel)* Chemin de sortie du fichier CSV. |
| `--open` | Ouvre automatiquement le rapport dans votre navigateur par défaut. |

---

## 📁 Structure du Projet

```text
AnalyseCode/
├── analyzer/                 # Moteur d'analyse statique Python
│   ├── models.py             # Dataclasses (EndpointCall, ParameterDiff, EndpointMatch)
│   ├── normalizer.py         # Normalisation d'URLs et chemins d'endpoints
│   ├── parser.py             # Visiteur AST Python (fonctions, décorateurs, appels HTTP)
│   ├── matcher.py            # Moteur de réconciliation et de diff de paramètres
│   └── exporter.py           # Génération des exports (HTML autonome, CSV, JSON)
├── samples/                  # Microservices d'exemple pour tests et démonstration
│   ├── manual_service/       # Implémentation manuelle (requests, routes FastAPI)
│   └── autogen_service/      # Implémentation autogénérée (client httpx, openapi)
├── web/                      # Interface Web Dashboard
│   ├── index.html            # Structure HTML sémantique
│   ├── styles.css            # Design moderne, Glassmorphism, Thèmes Dark/Light
│   └── app.js                # Logique frontend réactive, filtres, modal de diff
├── cli.py                    # Script d'exécution en ligne de commande
├── server.py                 # Serveur HTTP léger standard (aucun package externe requis)
├── run.sh                    # Script bash de démarrage rapide
└── README.md                 # Documentation
```
