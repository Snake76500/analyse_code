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
    build_class_method_index,
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
        self.assertIn("fichiera_dependency.py", match_a.call_example["full_code"])

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

    def test_dependency_mixed_manual_and_autogen_strictly_selects_autogen(self):
        """
        Verify that when a _dependency.py file contains BOTH manual and autogen dependencies,
        the generated example ONLY takes the autogenerated microservice dependencies.
        """
        dep_content = """
from manual_service.service import ManualServiceClient
from autogen_service.service import AutogenApiClient

class ServiceDependencies:
    def __init__(self, token=None, api_key=None):
        self.manual_client = ManualServiceClient(api_key=api_key or "MANUAL_DEV_KEY_123")
        self.autogen_client = AutogenApiClient(token=token or "PROD_AUTH_TOKEN_XYZ")

    def get_manual_client(self) -> ManualServiceClient:
        return self.manual_client

    def get_autogen_client(self) -> AutogenApiClient:
        return self.autogen_client

manual_client = ManualServiceClient(api_key="MANUAL_DEV_KEY_123")
default_client = AutogenApiClient(token="PROD_AUTH_TOKEN_XYZ")

def get_manual_service(api_key: str = "123") -> ManualServiceClient:
    return ManualServiceClient(api_key=api_key)

def create_api_client(token: str = "XYZ") -> AutogenApiClient:
    return AutogenApiClient(token=token)
"""
        registry = build_dependency_registry_from_memory([
            {"path": "service_dependency.py", "content": dep_content}
        ])

        manual_call = EndpointCall(
            function_name="get_product_views",
            class_name="ManualServiceClient",
            file_path="service.py",
            line_number=17,
            end_line_number=22,
            kind="client_call",
            http_method="GET",
            raw_endpoint="/products/{product_id}/views/{view_id}",
            normalized_endpoint="/products/{PARAM}/views/{PARAM}",
            function_params=[
                ParameterInfo(name="product_id", type_annotation="int"),
                ParameterInfo(name="view_id", type_annotation="str")
            ]
        )

        autogen_call = EndpointCall(
            function_name="get_product_views",
            class_name="AutogenApiClient",
            file_path="service.py",
            line_number=22,
            end_line_number=25,
            kind="client_call",
            http_method="GET",
            raw_endpoint="/products/{product_id}/views/{view_id}",
            normalized_endpoint="/products/{PARAM}/views/{PARAM}",
            function_params=[
                ParameterInfo(name="product_id", type_annotation="int"),
                ParameterInfo(name="view_id", type_annotation="str")
            ]
        )

        result = match_microservices(
            manual_calls=[manual_call],
            autogen_calls=[autogen_call],
            manual_path="samples/manual_service",
            autogen_path="samples/autogen_service",
            dependency_registry=registry
        )

        self.assertEqual(len(result.matches), 1)
        match = result.matches[0]
        ex = match.call_example
        self.assertIsNotNone(ex)

        # 1. Must use AutogenApiClient, NOT ManualServiceClient
        self.assertEqual(ex["class_name"], "AutogenApiClient")
        self.assertIn("AutogenApiClient", ex["instantiation"])
        self.assertNotIn("ManualServiceClient", ex["instantiation"])

        # 2. Variable name must belong to autogen, not manual_client
        self.assertNotEqual(ex["variable_name"], "manual_client")

        # 3. Imports must contain ONLY the autogen import
        self.assertTrue(any("AutogenApiClient" in imp for imp in ex["imports"]))
        self.assertFalse(any("ManualServiceClient" in imp for imp in ex["imports"]))

        # 4. Entire full_code must not mention manual dependencies
        self.assertNotIn("ManualServiceClient", ex["full_code"])
        self.assertNotIn("manual_client", ex["full_code"])
        self.assertNotIn("get_manual_service", ex["full_code"])
        self.assertIn("AutogenApiClient", ex["full_code"])

    def test_manual_only_dependency_file_does_not_leak_to_example(self):
        """
        If a dependency file contains ONLY manual dependencies,
        the autogen example MUST NOT adopt them.
        """
        dep_content = """
from manual_service.service import ManualServiceClient
manual_client = ManualServiceClient(api_key="OLD_KEY")
"""
        registry = build_dependency_registry_from_memory([
            {"path": "service_dependency.py", "content": dep_content}
        ])

        manual_call = EndpointCall(
            function_name="get_users",
            class_name="ManualServiceClient",
            file_path="service.py",
            line_number=10,
            end_line_number=15,
            kind="client_call",
            http_method="GET",
            raw_endpoint="/users",
            normalized_endpoint="/users",
            function_params=[]
        )

        autogen_call = EndpointCall(
            function_name="get_users",
            class_name="AutogenApiClient",
            file_path="service.py",
            line_number=10,
            end_line_number=15,
            kind="client_call",
            http_method="GET",
            raw_endpoint="/users",
            normalized_endpoint="/users",
            function_params=[]
        )

        result = match_microservices(
            manual_calls=[manual_call],
            autogen_calls=[autogen_call],
            manual_path="samples/manual_service",
            autogen_path="samples/autogen_service",
            dependency_registry=registry
        )

        match = result.matches[0]
        ex = match.call_example
        self.assertIsNotNone(ex)

        # Must not have picked ManualServiceClient!
        self.assertNotIn("ManualServiceClient", ex["full_code"])
        self.assertNotIn("manual_client", ex["full_code"])
        self.assertIn("AutogenApiClient", ex["full_code"])

    def test_reverse_engineering_multiple_autogen_dependencies(self):
        """
        Test that reverse engineering starting from the autogenerated function
        correctly links to the specific dependency that defines that function,
        even when multiple autogenerated dependencies exist.
        """
        dep_content = """
from package.auth import AuthApi
from package.users import UsersApi
from package.products import ProductsApi

class Dependencies:
    def __init__(self):
        self.auth_client = AuthApi(token="AUTH_TOKEN")
        self.users_client = UsersApi(token="USERS_TOKEN")
        self.products_client = ProductsApi(token="PROD_TOKEN")

    def get_products(self) -> ProductsApi:
        return self.products_client
"""
        registry = build_dependency_registry_from_memory([
            {"path": "service_dependency.py", "content": dep_content}
        ])

        # Autogen microservice code defining the 3 classes with their respective functions
        autogen_files = [
            {
                "path": "service.py",
                "content": """
class AuthApi:
    def login(self, username: str): pass

class UsersApi:
    def get_user_profile(self, user_id: int): pass

class ProductsApi:
    def get_product_views(self, product_id: int, view_id: str): pass
"""
            }
        ]

        class_index = build_class_method_index(file_list=autogen_files)

        call_prod = EndpointCall(
            function_name="get_product_views",
            class_name="ProductsApi",
            file_path="service.py",
            line_number=9,
            end_line_number=10,
            kind="client_call",
            http_method="GET",
            raw_endpoint="/products/{product_id}/views/{view_id}",
            normalized_endpoint="/products/{PARAM}/views/{PARAM}",
            function_params=[ParameterInfo(name="product_id"), ParameterInfo(name="view_id")]
        )

        call_users = EndpointCall(
            function_name="get_user_profile",
            class_name="UsersApi",
            file_path="service.py",
            line_number=6,
            end_line_number=7,
            kind="client_call",
            http_method="GET",
            raw_endpoint="/users/{user_id}",
            normalized_endpoint="/users/{PARAM}",
            function_params=[ParameterInfo(name="user_id")]
        )

        # 1. Reverse-engineering for get_product_views must pick ProductsApi / products_client
        ctx = registry.get("service")
        ex_prod = generate_function_call_example(
            call=call_prod,
            dependency_ctx=ctx,
            class_method_index=class_index
        )
        self.assertEqual(ex_prod["class_name"], "ProductsApi")
        self.assertEqual(ex_prod["variable_name"], "products_client")
        self.assertIn("products_client.get_product_views", ex_prod["call_snippet"])
        self.assertIn("Dependencies().get_products()", ex_prod["instantiation"])

        # 2. Reverse-engineering for get_user_profile must pick UsersApi / users_client
        ex_users = generate_function_call_example(
            call=call_users,
            dependency_ctx=ctx,
            class_method_index=class_index
        )
        self.assertEqual(ex_users["class_name"], "UsersApi")
        self.assertEqual(ex_users["variable_name"], "users_client")
        self.assertIn("users_client.get_user_profile", ex_users["call_snippet"])

    def test_sync_api_client_prioritization(self):
        """
        Rule: prends les dependency contenant une référence à SyncApiClient.
        When both AsyncApiClient and SyncApiClient are declared,
        the generator MUST strictly choose the dependency referencing SyncApiClient.
        """
        dep_content = """
from client.async_client import AsyncApiClient
from client.sync_client import SyncApiClient
from client.manual import ManualClient

# Manual client (legacy)
manual = ManualClient()

# Asynchronous client
async_client = AsyncApiClient(token="ASYNC_TOKEN")

# Synchronous client (SyncApiClient)
sync_api_client = SyncApiClient(token="SYNC_TOKEN")
"""
        registry = build_dependency_registry_from_memory([
            {"path": "users_dependency.py", "content": dep_content}
        ])

        ctx = registry.get("users")
        self.assertIsNotNone(ctx)

        # Check parsed instantiations
        sync_infos = [info for info in ctx.instantiations_list if info.has_sync_api_client]
        self.assertTrue(len(sync_infos) >= 1)
        self.assertEqual(sync_infos[0].class_name, "SyncApiClient")

        call = EndpointCall(
            function_name="get_user",
            class_name="UsersApi",
            file_path="users.py",
            line_number=1,
            end_line_number=5,
            kind="client_call",
            http_method="GET",
            raw_endpoint="/users/{id}",
            normalized_endpoint="/users/{PARAM}",
            function_params=[ParameterInfo(name="id")]
        )

        ex = generate_function_call_example(call=call, dependency_ctx=ctx)
        self.assertEqual(ex["class_name"], "SyncApiClient")
        self.assertEqual(ex["variable_name"], "sync_api_client")
        self.assertIn("SyncApiClient", ex["full_code"])
        self.assertNotIn("AsyncApiClient", ex["full_code"])
        self.assertNotIn("ManualClient", ex["full_code"])

    def test_sync_api_client_inheritance_and_args(self):
        """
        Verify classes inheriting from SyncApiClient or passing SyncApiClient as argument
        are properly detected and selected.
        """
        dep_content = """
from openapi.client import SyncApiClient

class UsersSyncClient(SyncApiClient):
    def __init__(self, token: str = "DEFAULT"):
        super().__init__(token=token)

sync_service = UsersSyncClient()
"""
        registry = build_dependency_registry_from_memory([
            {"path": "service_dependency.py", "content": dep_content}
        ])
        ctx = registry.get("service")
        self.assertIsNotNone(ctx)

        call = EndpointCall(
            function_name="list_items",
            class_name="UsersSyncClient",
            file_path="service.py",
            line_number=1,
            end_line_number=5,
            kind="client_call",
            http_method="GET",
            raw_endpoint="/items",
            normalized_endpoint="/items",
            function_params=[]
        )

        ex = generate_function_call_example(call=call, dependency_ctx=ctx)
        self.assertIn("UsersSyncClient", ex["class_name"])
        self.assertIn("sync_service", ex["full_code"])

    def test_link_files_containing_same_name(self):
        """
        Rule: Relie bien les fichiers contenant le même nom.
        - Manual fichiera.py and Autogen FichierA.py / fichiera.py must match
        - Service fichiera.py links strictly to dependency_fichiera.py or fichiera_dependency.py
        - FichierA and FichierB must NEVER cross-match!
        """
        from analyzer.matcher import are_file_names_matching

        # Test matcher filename linking
        self.assertTrue(are_file_names_matching("fichiera.py", "fichiera.py"))
        self.assertTrue(are_file_names_matching("FichierA.py", "fichiera.py"))
        self.assertTrue(are_file_names_matching("controllers/fichiera.py", "api/fichiera.py"))
        self.assertTrue(are_file_names_matching("fichiera_service.py", "fichiera.py"))
        self.assertTrue(are_file_names_matching("fichiera_controller.py", "fichiera_api.py"))

        # Must NOT cross-match different names
        self.assertFalse(are_file_names_matching("fichiera.py", "fichierb.py"))
        self.assertFalse(are_file_names_matching("users.py", "orders.py"))

        # Test dependency linking
        dep_files = [
            {"path": "dependency_fichiera.py", "content": "from client import SyncApiClient\nsync_client = SyncApiClient()"},
            {"path": "fichierb_dependency.py", "content": "from client import SyncApiClient\nsync_client = SyncApiClient()"}
        ]
        registry = build_dependency_registry_from_memory(dep_files)

        ctx_a = get_homonym_dependency("fichiera.py", registry)
        ctx_b = get_homonym_dependency("fichierb.py", registry)

        self.assertIsNotNone(ctx_a)
        self.assertIsNotNone(ctx_b)
        self.assertIn("fichiera", ctx_a.file_path)
        self.assertIn("fichierb", ctx_b.file_path)

        # Confirm non-homonym does not cross
        self.assertIsNone(get_homonym_dependency("fichierc.py", registry))


if __name__ == "__main__":
    unittest.main()



