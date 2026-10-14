#!/usr/bin/env python3
"""
CLI tool for Microservices Endpoint & Parameter Matrix Analyzer.
Usage:
  python3 cli.py --manual ./path/to/manual --autogen ./path/to/autogen --output report.html
"""
import argparse
import sys
import os
import webbrowser
from analyzer.parser import parse_service_directory
from analyzer.matcher import match_microservices
from analyzer.exporter import export_to_json, export_to_csv, export_to_standalone_html

def main():
    parser = argparse.ArgumentParser(
        description="Analyse et matrice de correspondance de microservices (manuel vs autogénéré)."
    )
    parser.add_argument(
        "--manual", "-m",
        required=True,
        help="Chemin vers le dossier ou fichier du microservice développé manuellement."
    )
    parser.add_argument(
        "--autogen", "-a",
        required=True,
        help="Chemin vers le dossier ou fichier du microservice autogénéré (OpenAPI/OpenAI)."
    )
    parser.add_argument(
        "--output", "-o",
        default="rapport_correspondance.html",
        help="Chemin du fichier de sortie pour le rapport HTML interactif (par défaut: rapport_correspondance.html)."
    )
    parser.add_argument(
        "--json", "-j",
        help="Chemin optionnel pour exporter les données brutes au format JSON."
    )
    parser.add_argument(
        "--csv", "-c",
        help="Chemin optionnel pour exporter la matrice au format CSV (Excel)."
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Ouvrir automatiquement le rapport HTML dans le navigateur."
    )

    args = parser.parse_args()

    if not os.path.exists(args.manual):
        print(f"Erreur : Le dossier manuel '{args.manual}' n'existe pas.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.autogen):
        print(f"Erreur : Le dossier autogénéré '{args.autogen}' n'existe pas.", file=sys.stderr)
        sys.exit(1)

    print(f"🔍 Analyse du microservice manuel : {args.manual}")
    manual_calls = parse_service_directory(args.manual)
    print(f"   ➔ {len(manual_calls)} endpoint(s) / route(s) détecté(s).")

    print(f"🔍 Analyse du microservice autogénéré : {args.autogen}")
    autogen_calls = parse_service_directory(args.autogen)
    print(f"   ➔ {len(autogen_calls)} endpoint(s) / route(s) détecté(s).")

    print("⚡ Calcul de la matrice de correspondance et analyse des paramètres...")
    result = match_microservices(manual_calls, autogen_calls, args.manual, args.autogen)

    print("\n" + "=" * 60)
    print(f"📊 RÉSULTATS DE L'ANALYSE")
    print("=" * 60)
    print(f"  • Correspondances trouvées          : {result.matched_count}")
    print(f"    - Paramètres identiques           : {result.identical_count}")
    print(f"    - Paramètres compatibles          : {result.compatible_count}")
    print(f"    - Paramètres divergents           : {result.divergent_count}")
    print(f"  • Présent uniquement dans le manuel : {result.manual_only_count}")
    print(f"  • Présent uniquement en autogénéré : {result.autogen_only_count}")
    print("=" * 60 + "\n")

    html_content = export_to_standalone_html(result)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"✅ Rapport HTML interactif généré : {os.path.abspath(args.output)}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            f.write(export_to_json(result))
        print(f"✅ Données JSON exportées : {os.path.abspath(args.json)}")

    if args.csv:
        with open(args.csv, "w", encoding="utf-8") as f:
            f.write(export_to_csv(result))
        print(f"✅ Matrice CSV exportée : {os.path.abspath(args.csv)}")

    if args.open:
        webbrowser.open(f"file://{os.path.abspath(args.output)}")

if __name__ == "__main__":
    main()
