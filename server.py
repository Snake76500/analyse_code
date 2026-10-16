#!/usr/bin/env python3
"""
Web Server for Microservices Endpoint & Parameter Matrix Analyzer.
Zero external dependencies, powered by Python http.server.
"""
import os
import sys
import json
import socket
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse
from analyzer.parser import parse_service_directory, parse_files_in_memory
from analyzer.matcher import match_microservices
from analyzer.dependency_parser import (
    find_dependency_in_memory,
    build_dependency_registry_from_memory,
    build_dependency_registry_from_directory,
    build_class_method_index,
    build_class_subattributes_index
)
from analyzer.exporter import export_to_json, export_to_csv, export_to_standalone_html
from migrator.engine import CodeMigrationEngine

DEFAULT_PORT = 8080
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True

class MatrixServerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        if parsed.path == "/api/samples":
            base_dir = os.path.dirname(os.path.abspath(__file__))
            manual_dir = os.path.join(base_dir, "samples", "manual_service")
            autogen_dir = os.path.join(base_dir, "samples", "autogen_service")

            manual_calls = parse_service_directory(manual_dir, resolve_parents=False)
            autogen_calls = parse_service_directory(autogen_dir, resolve_parents=True)
            result = match_microservices(manual_calls, autogen_calls, manual_dir, autogen_dir)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(result.to_dict(), ensure_ascii=False).encode("utf-8"))
            return

        if parsed.path == "/api/migrate/demo":
            base_dir = os.path.dirname(os.path.abspath(__file__))
            demo_data = {
                "target_path": os.path.join(base_dir, "samples", "client_app"),
                "manual_path": os.path.join(base_dir, "samples", "manual_service"),
                "autogen_path": os.path.join(base_dir, "samples", "autogen_service"),
                "example_path": os.path.join(base_dir, "samples", "migration_example.py")
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(demo_data, ensure_ascii=False).encode("utf-8"))
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path in ("/api/migrate/preview", "/api/migrate/apply"):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")

            try:
                payload = json.loads(body) if body else {}
            except Exception as e:
                self._error(f"Invalid JSON payload: {e}")
                return

            target_path = payload.get("target_path", "").strip()
            manual_path = payload.get("manual_path", "").strip()
            autogen_path = payload.get("autogen_path", "").strip()
            example_path = payload.get("example_path", "").strip()
            example_content = payload.get("example_content", "").strip()
            output_dir = payload.get("output_dir", "").strip() or None
            apply_in_place = (parsed.path == "/api/migrate/apply") or payload.get("apply_in_place", False)

            if not target_path or not os.path.exists(target_path):
                self._error(f"Le dossier du code cible '{target_path}' est introuvable.")
                return
            if not manual_path or not os.path.exists(manual_path):
                self._error(f"Le microservice manuel '{manual_path}' est introuvable.")
                return
            if not autogen_path or not os.path.exists(autogen_path):
                self._error(f"Le microservice autogénéré '{autogen_path}' est introuvable.")
                return
            if not example_content and (not example_path or not os.path.exists(example_path)):
                self._error(f"Le fichier exemple '{example_path}' est introuvable.")
                return

            try:
                engine = CodeMigrationEngine(
                    manual_service_path=manual_path,
                    autogen_service_path=autogen_path,
                    example_migration_path=example_path,
                    example_content=example_content
                )
                report = engine.migrate_directory(
                    target_dir=target_path,
                    output_dir=output_dir,
                    apply_in_place=apply_in_place
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(report.to_dict(), ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self._error(f"Erreur durant la migration : {e}", 500)
            return

        if parsed.path in ("/api/analyze", "/api/export/csv", "/api/export/html", "/api/export/json"):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")

            try:
                payload = json.loads(body) if body else {}
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Invalid JSON payload: {e}"}).encode("utf-8"))
                return

            manual_path = payload.get("manual_path", "").strip()
            autogen_path = payload.get("autogen_path", "").strip()
            manual_files = payload.get("manual_files", [])
            autogen_files = payload.get("autogen_files", [])
            manual_resolve = payload.get("manual_resolve_parents", False)
            autogen_resolve = payload.get("autogen_resolve_parents", True)

            dep_registry = None
            autogen_method_index = None
            autogen_subattr_index = None
            if manual_files and autogen_files:
                manual_calls = parse_files_in_memory(manual_files, resolve_parents=manual_resolve)
                autogen_calls = parse_files_in_memory(autogen_files, resolve_parents=autogen_resolve)
                manual_label = "Fichiers manuels importés"
                autogen_label = "bp2i_airflow_library"
                dep_registry = build_dependency_registry_from_memory(autogen_files)
                autogen_method_index = build_class_method_index(file_list=autogen_files, calls=autogen_calls)
                autogen_subattr_index = build_class_subattributes_index(file_list=autogen_files, dependency_registry=dep_registry)
            elif manual_path and autogen_path:
                abs_manual = os.path.abspath(manual_path)
                abs_autogen = os.path.abspath(autogen_path)
                if not os.path.exists(abs_manual):
                    self._error(f"Le chemin manuel '{manual_path}' est introuvable sur le serveur.")
                    return
                if not os.path.exists(abs_autogen):
                    self._error(f"Le chemin autogénéré '{autogen_path}' est introuvable sur le serveur.")
                    return
                manual_calls = parse_service_directory(abs_manual, resolve_parents=manual_resolve)
                autogen_calls = parse_service_directory(abs_autogen, resolve_parents=autogen_resolve)
                manual_label = manual_path
                autogen_label = abs_autogen
                dep_registry = build_dependency_registry_from_directory(abs_autogen)
                autogen_method_index = build_class_method_index(dir_path=abs_autogen, calls=autogen_calls)
                autogen_subattr_index = build_class_subattributes_index(dir_path=abs_autogen, dependency_registry=dep_registry)
            else:
                self._error("Veuillez renseigner les chemins des deux microservices ou importer leurs fichiers.")
                return

            result = match_microservices(
                manual_calls,
                autogen_calls,
                manual_label,
                autogen_label,
                dependency_registry=dep_registry,
                class_method_index=autogen_method_index,
                class_subattributes_index=autogen_subattr_index,
                autogen_file_list=autogen_files if autogen_files else None
            )

            if parsed.path == "/api/analyze":
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(result.to_dict(), ensure_ascii=False).encode("utf-8"))
            elif parsed.path == "/api/export/csv":
                csv_data = export_to_csv(result)
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="matrice_microservices.csv"')
                self.end_headers()
                self.wfile.write(csv_data.encode("utf-8"))
            elif parsed.path == "/api/export/html":
                html_data = export_to_standalone_html(result)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="rapport_microservices.html"')
                self.end_headers()
                self.wfile.write(html_data.encode("utf-8"))
            elif parsed.path == "/api/export/json":
                json_data = export_to_json(result)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="analyse_microservices.json"')
                self.end_headers()
                self.wfile.write(json_data.encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def _error(self, message: str, code: int = 400):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}, ensure_ascii=False).encode("utf-8"))


def find_free_port(start_port: int) -> int:
    port = start_port
    while port < start_port + 50:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                port += 1
    return start_port


def run_server(port=DEFAULT_PORT, auto_open=True):
    actual_port = find_free_port(port)
    if actual_port != port:
        print(f"⚠️  Le port {port} est déjà utilisé. Utilisation du port {actual_port}.")

    server_address = ("", actual_port)
    httpd = ReusableHTTPServer(server_address, MatrixServerHandler)
    url = f"http://localhost:{actual_port}"

    print("=" * 60)
    print("⚡ Microservices Matrix Analyzer - Serveur Web")
    print("=" * 60)
    print(f"🚀 Serveur actif sur : {url}")
    print(f"📂 Répertoire web    : {WEB_DIR}")
    print("💡 Appuyez sur Ctrl+C pour arrêter le serveur.")
    print("=" * 60)

    if auto_open:
        def open_browser():
            print(f"🌐 Ouverture du navigateur sur {url} ...")
            webbrowser.open(url)
        threading.Timer(0.6, open_browser).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur. À bientôt !")
        httpd.server_close()


if __name__ == "__main__":
    requested_port = DEFAULT_PORT
    auto_open = True

    for arg in sys.argv[1:]:
        if arg == "--no-browser":
            auto_open = False
        elif arg.isdigit():
            requested_port = int(arg)

    run_server(requested_port, auto_open=auto_open)
