import unittest
import os
import tempfile
import shutil
from analyzer.dependency_parser import (
    extract_service_stem_from_dependency_path,
    build_dependency_registry_from_directory,
    build_dependency_registry_from_memory,
    get_homonym_dependency,
    parse_dependency_content,
    generate_function_call_example,
)
from analyzer.models import EndpointCall, ParameterInfo
from analyzer.matcher import match_microservices
from analyzer.parser import parse_service_directory, parse_files_in_memory


class TestDependencyHomonymLinking(unittest.TestCase):

    def test_extract_service_stem(self):
        self.assertEqual(extract_service_stem_from_dependency_path("fichiera_dependency.py"), "fichiera")
        self.assertEqual(extract_service_stem_from_dependency_path("/path/to/fichiera_dependency.py"), "fichiera")
        self.assertEqual(extract_service_stem_from_dependency_path("services/users_dependency.py"), "users")
        self.assertEqual(extract_service_stem_from_dependency_path("service_dependency.py"), "service")
        self.assertEqual(extract_service_stem_from_dependency_path("billing_dependencies.py"), "billing")
        self.assertIsNone(extract_service_stem_from_dependency_path("fichiera.py"))
        self.assertIsNone(extract_service_stem_from_dependency_path("not_a_python_file.txt"))

    def test_strict_homonym_matching(self):
        """
        Verify that fichiera.py is linked ONLY to fichiera_dependency.py,
        and fichierb.py is NOT linked to fichiera_dependency.py.
        """
        dep_content_a = """
from package.client_a import ClientA

class ClientADependency:
    def __init__(self, api_key: str = "KEY_A"):
        self.client = ClientA(api_key=api_key)
"""
        dep_content_b = """
from package.client_b import ClientB

class ClientBDependency:
    def __init__(self, token: str = "TOKEN_B"):
        self.client = ClientB(token=token)
"""
        registry = build_dependency_registry_from_memory([
            {"path": "fichiera_dependency.py", "content": dep_content_a},
            {"path": "fichierb_dependency.py", "content": dep_content_b},
        ])

        # fichiera.py must match fichiera_dependency
        ctx_a = get_homonym_dependency("fichiera.py", registry)
        self.assertIsNotNone(ctx_a)
        self.assertEqual(os.path.basename(ctx_a.file_path), "fichiera_dependency.py")
        self.assertIn("ClientA", ctx_a.instantiations)

        # fichierb.py must match fichierb_dependency
        ctx_b = get_homonym_dependency("fichierb.py", registry)
        self.assertIsNotNone(ctx_b)
        self.assertEqual(os.path.basename(ctx_b.file_path), "fichierb_dependency.py")
        self.assertIn("ClientB", ctx_b.instantiations)

        # fichierc.py has NO homonym dependency file -> MUST return None
        ctx_c = get_homonym_dependency("fichierc.py", registry)
        self.assertIsNone(ctx_c)

    def test_single_dependency_does_not_leak_to_non_homonym(self):
        """
        If ONLY fichiera_dependency.py exists, fichierb.py MUST NOT be linked to it!
        """
        dep_content = """
from package.client_a import ClientA
client_a = ClientA(token="SECRET")
"""
        registry = build_dependency_registry_from_memory([
            {"path": "fichiera_dependency.py", "content": dep_content}
        ])

        # fichiera.py gets it
        self.assertIsNotNone(get_homonym_dependency("fichiera.py", registry))

        # fichierb.py MUST NOT get it
        self.assertIsNone(get_homonym_dependency("fichierb.py", registry))

    def test_match_microservices_with_homonyms(self):
        """
        End-to-end test with match_microservices:
        Endpoint in fichiera.py gets call_example with fichiera_dependency.
        Endpoint in fichierb.py has call_example with NO dependency file (dependency_file is None).
        """
        dep_content_a = """
from api.a import ClientA
default_client = ClientA(token="TOK_A")
"""
        registry = build_dependency_registry_from_memory([
            {"path": "fichiera_dependency.py", "content": dep_content_a}
        ])

        manual_calls = [
            EndpointCall(
                function_name="get_users",
                file_path="fichiera.py",
                line_number=10,
                end_line_number=15,
                kind="client_call",
                http_method="GET",
                raw_endpoint="/api/users",
                normalized_endpoint="/api/users",
                function_params=[ParameterInfo(name="limit", type_annotation="int")]
            ),
            EndpointCall(
                function_name="get_orders",
                file_path="fichierb.py",
                line_number=20,
                end_line_number=25,
                kind="client_call",
                http_method="GET",
                raw_endpoint="/api/orders",
                normalized_endpoint="/api/orders",
                function_params=[ParameterInfo(name="order_id", type_annotation="str")]
            )
        ]

        autogen_calls = [
            EndpointCall(
                function_name="fetch_users",
                class_name="ClientA",
                file_path="fichiera.py",
                line_number=15,
                end_line_number=20,
                kind="client_call",
                http_method="GET",
                raw_endpoint="/api/users",
                normalized_endpoint="/api/users",
                function_params=[ParameterInfo(name="limit", type_annotation="int")]
            ),
            EndpointCall(
                function_name="fetch_orders",
                class_name="ClientB",
                file_path="fichierb.py",
                line_number=25,
                end_line_number=30,
                kind="client_call",
                http_method="GET",
                raw_endpoint="/api/orders",
                normalized_endpoint="/api/orders",
                function_params=[ParameterInfo(name="order_id", type_annotation="str")]
            )
        ]

        result = match_microservices(
            manual_calls=manual_calls,
            autogen_calls=autogen_calls,
            manual_path="manual",
            autogen_path="autogen",
            dependency_registry=registry
        )

        self.assertEqual(len(result.matches), 2)

        # Match 1: fichiera.py
        match_a = next(m for m in result.matches if "users" in m.normalized_endpoint)
        self.assertIsNotNone(match_a.call_example)
        self.assertEqual(match_a.call_example["dependency_file"], "fichiera_dependency.py")
        self.assertIn("Basé sur: fichiera_dependency.py", match_a.call_example["full_code"])

        # Match 2: fichierb.py - STRICT: MUST NOT use fichiera_dependency.py!
        match_b = next(m for m in result.matches if "orders" in m.normalized_endpoint)
        self.assertIsNotNone(match_b.call_example)
        self.assertIsNone(match_b.call_example["dependency_file"])
        self.assertNotIn("fichiera_dependency.py", match_b.call_example["full_code"])

    def test_dependency_files_excluded_from_endpoint_parsing(self):
        """
        Verify that *_dependency.py files are not mistakenly parsed as endpoint sources.
        """
        files = [
            {
                "path": "service.py",
                "content": """
import requests
def get_status():
    return requests.get("http://api.local/status")
"""
            },
            {
                "path": "service_dependency.py",
                "content": """
import requests
def helper_check():
    return requests.get("http://api.local/internal/health")
"""
            }
        ]
        parsed = parse_files_in_memory(files, resolve_parents=False)
        endpoints = [p.normalized_endpoint for p in parsed]
        self.assertIn("/status", endpoints)
        self.assertNotIn("/internal/health", endpoints)


if __name__ == "__main__":
    unittest.main()
