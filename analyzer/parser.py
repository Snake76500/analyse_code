"""
Python AST parser to detect HTTP client calls and server routes in microservices.
Supports caller graph resolution: if an endpoint function is called by a parent function,
the parent function is chosen for compatibility analysis.
"""
import ast
import os
import copy
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Set, Tuple
from .models import ParameterInfo, EndpointCall
from .normalizer import normalize_endpoint, normalize_method, extract_path_params

HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}

EXCLUDED_CALL_NAMES = {
    "get", "post", "put", "delete", "patch", "head", "options", "request",
    "_request", "call_api", "_call_api", "send_request", "_send_request",
    "json", "text", "content", "headers", "status_code", "raise_for_status",
    "append", "extend", "insert", "remove", "pop", "clear", "index", "count",
    "sort", "reverse", "copy", "items", "keys", "values", "update", "split",
    "strip", "lstrip", "rstrip", "lower", "upper", "replace", "format",
    "startswith", "endswith", "join", "find", "len", "print", "range", "enumerate",
    "isinstance", "issubclass", "int", "str", "float", "bool", "dict", "list", "set",
    "tuple", "super", "open", "read", "write", "close", "run", "execute", "main",
    "load", "loads", "dump", "dumps"
}

@dataclass
class ParsedFunction:
    name: str
    class_name: Optional[str]
    file_path: str
    line_number: int
    end_line_number: int
    params: List[ParameterInfo]
    code_snippet: str
    docstring: Optional[str]
    direct_endpoints: List[EndpointCall]
    called_names: Set[str]


class CodeVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, source_code: str):
        self.file_path = file_path
        self.source_code = source_code
        self.source_lines = source_code.splitlines()
        self.endpoints: List[EndpointCall] = []
        self.parsed_functions: List[ParsedFunction] = []
        self.module_constants: Dict[str, str] = {}
        self.current_class: Optional[str] = None

    def _get_snippet(self, start_line: int, end_line: int) -> str:
        if not self.source_lines:
            return ""
        start = max(0, start_line - 1)
        end = min(len(self.source_lines), end_line)
        return "\n".join(self.source_lines[start:end])

    def _unparse_annotation(self, node: Optional[ast.AST]) -> Optional[str]:
        if node is None:
            return None
        try:
            return ast.unparse(node)
        except Exception:
            return None

    def _unparse_value(self, node: Optional[ast.AST]) -> Optional[str]:
        if node is None:
            return None
        try:
            return ast.unparse(node)
        except Exception:
            return None

    def _extract_string_or_fstring(self, node: ast.AST, local_vars: Optional[Dict[str, ast.AST]] = None) -> Optional[str]:
        """Extract a string representation from Constant, JoinedStr (f-string), BinOp (+), or Name."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        elif isinstance(node, ast.JoinedStr):
            parts = []
            for val in node.values:
                if isinstance(val, ast.Constant) and isinstance(val.value, str):
                    parts.append(val.value)
                elif isinstance(val, ast.FormattedValue):
                    var_name = self._unparse_value(val.value) or "param"
                    if local_vars and var_name in local_vars:
                        resolved = self._extract_string_or_fstring(local_vars[var_name], local_vars)
                        if resolved:
                            parts.append(resolved)
                            continue
                    elif var_name in self.module_constants:
                        parts.append(self.module_constants[var_name])
                        continue
                    parts.append(f"{{{var_name}}}")
            return "".join(parts)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = self._extract_string_or_fstring(node.left, local_vars)
            right = self._extract_string_or_fstring(node.right, local_vars)
            if left and right:
                return left + right
            return left or right
        elif isinstance(node, ast.Name):
            if local_vars and node.id in local_vars:
                return self._extract_string_or_fstring(local_vars[node.id], local_vars)
            if node.id in self.module_constants:
                return self.module_constants[node.id]
            return f"{{{node.id}}}"
        return None

    def _extract_function_params(self, node: ast.FunctionDef) -> List[ParameterInfo]:
        params = []
        args = node.args

        num_args = len(args.args)
        num_defaults = len(args.defaults)
        default_offset = num_args - num_defaults

        for idx, arg in enumerate(args.args):
            if arg.arg in ("self", "cls"):
                continue

            default_val = None
            if idx >= default_offset:
                default_node = args.defaults[idx - default_offset]
                default_val = self._unparse_value(default_node)

            param = ParameterInfo(
                name=arg.arg,
                type_annotation=self._unparse_annotation(arg.annotation),
                default_value=default_val,
                required=(default_val is None),
                kind="arg"
            )
            params.append(param)

        for idx, arg in enumerate(args.kwonlyargs):
            default_node = args.kw_defaults[idx] if idx < len(args.kw_defaults) else None
            default_val = self._unparse_value(default_node) if default_node else None

            param = ParameterInfo(
                name=arg.arg,
                type_annotation=self._unparse_annotation(arg.annotation),
                default_value=default_val,
                required=(default_val is None),
                kind="kwarg"
            )
            params.append(param)

        return params

    def _extract_dict_keys(self, node: ast.AST, local_vars: Optional[Dict[str, ast.AST]] = None) -> List[str]:
        keys = []
        if isinstance(node, ast.Dict):
            for k in node.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    keys.append(k.value)
                elif k is not None:
                    unparsed = self._unparse_value(k)
                    if unparsed:
                        keys.append(unparsed)
        elif isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg:
                    keys.append(kw.arg)
        elif isinstance(node, ast.Name):
            if local_vars and node.id in local_vars:
                return self._extract_dict_keys(local_vars[node.id], local_vars)
            keys.append(node.id)
        return keys

    def _extract_called_names(self, func_node: ast.FunctionDef) -> Set[str]:
        names = set()
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    names.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    names.add(node.func.attr)
        return names

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                str_val = self._extract_string_or_fstring(node.value)
                if str_val:
                    self.module_constants[target.id] = str_val
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def _check_server_decorators(self, node: ast.FunctionDef) -> Optional[EndpointCall]:
        for decorator in node.decorator_list:
            method = "GET"
            path = ""

            if isinstance(decorator, ast.Call):
                func = decorator.func
                if isinstance(func, ast.Attribute):
                    attr = func.attr.upper()
                    if attr in HTTP_METHODS:
                        method = attr
                    elif attr == "ROUTE":
                        for kw in decorator.keywords:
                            if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                                for elt in kw.value.elts:
                                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                        method = elt.value.upper()
                                        break

                if decorator.args:
                    extracted_path = self._extract_string_or_fstring(decorator.args[0])
                    if extracted_path:
                        path = extracted_path

                for kw in decorator.keywords:
                    if kw.arg in ("path", "rule"):
                        extracted_path = self._extract_string_or_fstring(kw.value)
                        if extracted_path:
                            path = extracted_path

            if path:
                canonical, path_params, query_params = normalize_endpoint(path)
                fn_params = self._extract_function_params(node)

                body_params = []
                for p in fn_params:
                    if p.name in path_params:
                        p.kind = "path"
                    elif p.type_annotation and any(b in p.type_annotation.lower() for b in ["model", "schema", "request", "payload", "body"]):
                        p.kind = "body"
                        body_params.append(p.name)
                    else:
                        p.kind = "query"
                        if p.name not in query_params:
                            query_params.append(p.name)

                return EndpointCall(
                    function_name=node.name,
                    file_path=self.file_path,
                    line_number=node.lineno,
                    end_line_number=getattr(node, "end_lineno", node.lineno),
                    kind="server_route",
                    http_method=normalize_method(method),
                    raw_endpoint=path,
                    normalized_endpoint=canonical,
                    function_params=fn_params,
                    path_params=path_params,
                    query_params=query_params,
                    body_params=body_params,
                    code_snippet=self._get_snippet(node.lineno, getattr(node, "end_lineno", node.lineno)),
                    docstring=ast.get_docstring(node)
                )
        return None

    def _check_client_calls_in_function(self, func_node: ast.FunctionDef) -> List[EndpointCall]:
        client_calls = []
        fn_params = self._extract_function_params(func_node)
        local_vars: Dict[str, ast.AST] = {}

        for stmt in func_node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        local_vars[target.id] = stmt.value

            for subnode in ast.walk(stmt):
                if not isinstance(subnode, ast.Call):
                    continue

                method = None
                url = None
                query_params = []
                body_params = []
                headers = []

                if isinstance(subnode.func, ast.Attribute):
                    attr_name = subnode.func.attr.upper()
                    if attr_name in HTTP_METHODS:
                        method = attr_name
                        if subnode.args:
                            url = self._extract_string_or_fstring(subnode.args[0], local_vars)
                    elif attr_name in ("REQUEST", "CALL_API", "_REQUEST", "SEND_REQUEST"):
                        if subnode.args and len(subnode.args) >= 2:
                            first_val = self._extract_string_or_fstring(subnode.args[0], local_vars)
                            second_val = self._extract_string_or_fstring(subnode.args[1], local_vars)
                            if first_val and first_val.upper() in HTTP_METHODS:
                                method = first_val.upper()
                                url = second_val
                            elif second_val and second_val.upper() in HTTP_METHODS:
                                method = second_val.upper()
                                url = first_val
                        elif subnode.args and len(subnode.args) == 1:
                            url = self._extract_string_or_fstring(subnode.args[0], local_vars)

                for kw in subnode.keywords:
                    if kw.arg == "url" and not url:
                        url = self._extract_string_or_fstring(kw.value, local_vars)
                    elif kw.arg == "method" and not method:
                        m = self._extract_string_or_fstring(kw.value, local_vars)
                        if m and m.upper() in HTTP_METHODS:
                            method = m.upper()
                    elif kw.arg == "params":
                        query_params.extend(self._extract_dict_keys(kw.value, local_vars))
                    elif kw.arg in ("json", "data"):
                        body_params.extend(self._extract_dict_keys(kw.value, local_vars))
                    elif kw.arg == "headers":
                        headers.extend(self._extract_dict_keys(kw.value, local_vars))

                if method and url:
                    canonical, path_params, extra_query = normalize_endpoint(url)
                    for q in extra_query:
                        if q not in query_params:
                            query_params.append(q)

                    call_obj = EndpointCall(
                        function_name=func_node.name,
                        file_path=self.file_path,
                        line_number=func_node.lineno,
                        end_line_number=getattr(func_node, "end_lineno", func_node.lineno),
                        kind="client_call",
                        http_method=normalize_method(method),
                        raw_endpoint=url,
                        normalized_endpoint=canonical,
                        function_params=fn_params,
                        path_params=path_params,
                        query_params=query_params,
                        body_params=body_params,
                        headers=headers,
                        code_snippet=self._get_snippet(func_node.lineno, getattr(func_node, "end_lineno", func_node.lineno)),
                        docstring=ast.get_docstring(func_node)
                    )
                    client_calls.append(call_obj)

        return client_calls

    def visit_FunctionDef(self, node: ast.FunctionDef):
        direct_eps = []
        route = self._check_server_decorators(node)
        if route:
            direct_eps.append(route)

        calls = self._check_client_calls_in_function(node)
        for c in calls:
            direct_eps.append(c)

        called_names = self._extract_called_names(node)

        parsed_fn = ParsedFunction(
            name=node.name,
            class_name=self.current_class,
            file_path=self.file_path,
            line_number=node.lineno,
            end_line_number=getattr(node, "end_lineno", node.lineno),
            params=self._extract_function_params(node),
            code_snippet=self._get_snippet(node.lineno, getattr(node, "end_lineno", node.lineno)),
            docstring=ast.get_docstring(node),
            direct_endpoints=direct_eps,
            called_names=called_names
        )
        self.parsed_functions.append(parsed_fn)
        self.endpoints.extend(direct_eps)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        direct_eps = []
        route = self._check_server_decorators(node)  # type: ignore
        if route:
            direct_eps.append(route)

        calls = self._check_client_calls_in_function(node)  # type: ignore
        for c in calls:
            direct_eps.append(c)

        called_names = self._extract_called_names(node)  # type: ignore

        parsed_fn = ParsedFunction(
            name=node.name,
            class_name=self.current_class,
            file_path=self.file_path,
            line_number=node.lineno,
            end_line_number=getattr(node, "end_lineno", node.lineno),
            params=self._extract_function_params(node),  # type: ignore
            code_snippet=self._get_snippet(node.lineno, getattr(node, "end_lineno", node.lineno)),
            docstring=ast.get_docstring(node),
            direct_endpoints=direct_eps,
            called_names=called_names
        )
        self.parsed_functions.append(parsed_fn)
        self.endpoints.extend(direct_eps)


def find_top_callers(
    target_fn: ParsedFunction, 
    all_functions: List[ParsedFunction], 
    chain: Optional[List[str]] = None
) -> List[Tuple[ParsedFunction, List[str]]]:
    """
    Recursively find top-most parent function(s) calling target_fn.
    Returns list of (top_parent_function, call_chain).
    """
    if chain is None:
        chain = [target_fn.name]

    candidates = []
    for f in all_functions:
        if f.name == target_fn.name:
            continue
        if f.name in chain:
            continue
        if target_fn.name in EXCLUDED_CALL_NAMES:
            continue
        if f.name.startswith("test_") or "test" in f.file_path.lower():
            continue
        if f.name.startswith("__") and f.name.endswith("__"):
            continue
        if target_fn.name in f.called_names:
            candidates.append(f)

    if not candidates:
        if len(chain) > 1:
            return [(target_fn, chain)]
        return []

    same_class = [c for c in candidates if c.file_path == target_fn.file_path and c.class_name == target_fn.class_name]
    same_file = [c for c in candidates if c.file_path == target_fn.file_path]

    if same_class:
        active = same_class
    elif same_file:
        active = same_file
    else:
        active = candidates

    top_callers = []
    for caller in active:
        new_chain = [caller.name] + chain
        higher = find_top_callers(caller, all_functions, new_chain)
        if higher:
            top_callers.extend(higher)
        else:
            top_callers.append((caller, new_chain))

    return top_callers


def resolve_parent_callers(all_functions: List[ParsedFunction]) -> List[EndpointCall]:
    """
    If an endpoint function is called by a parent function,
    use the parent function instead for compatibility analysis.
    """
    final_endpoints: List[EndpointCall] = []
    seen = set()

    for fn in all_functions:
        if not fn.direct_endpoints:
            continue

        top_callers = find_top_callers(fn, all_functions)
        if top_callers:
            for caller, chain in top_callers:
                for ep in fn.direct_endpoints:
                    key = (caller.name, caller.file_path, ep.http_method, ep.normalized_endpoint)
                    if key in seen:
                        continue
                    seen.add(key)

                    resolved_params = []
                    new_query = list(ep.query_params)
                    new_body = list(ep.body_params)
                    for p in caller.params:
                        p_copy = copy.copy(p)
                        if p_copy.name in ep.path_params:
                            p_copy.kind = "path"
                        elif p_copy.type_annotation and any(b in p_copy.type_annotation.lower() for b in ["model", "schema", "request", "payload", "body"]):
                            p_copy.kind = "body"
                            if p_copy.name not in new_body:
                                new_body.append(p_copy.name)
                        else:
                            p_copy.kind = "query"
                            if p_copy.name not in new_query:
                                new_query.append(p_copy.name)
                        resolved_params.append(p_copy)

                    resolved_ep = EndpointCall(
                        function_name=caller.name,
                        file_path=caller.file_path,
                        line_number=caller.line_number,
                        end_line_number=caller.end_line_number,
                        kind=ep.kind,
                        http_method=ep.http_method,
                        raw_endpoint=ep.raw_endpoint,
                        normalized_endpoint=ep.normalized_endpoint,
                        function_params=resolved_params,
                        path_params=ep.path_params,
                        query_params=new_query,
                        body_params=new_body,
                        headers=ep.headers,
                        code_snippet=caller.code_snippet,
                        docstring=caller.docstring,
                        callee_function=fn.name,
                        caller_chain=chain
                    )
                    final_endpoints.append(resolved_ep)
        else:
            for ep in fn.direct_endpoints:
                key = (fn.name, fn.file_path, ep.http_method, ep.normalized_endpoint)
                if key in seen:
                    continue
                seen.add(key)
                final_endpoints.append(ep)

    return final_endpoints


def parse_python_file(file_path: str, root_dir: str = "") -> List[EndpointCall]:
    """Parse a single Python file and resolve caller hierarchy."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            code = f.read()

        tree = ast.parse(code, filename=file_path)
        rel_path = os.path.relpath(file_path, root_dir) if root_dir else file_path
        visitor = CodeVisitor(rel_path, code)
        visitor.visit(tree)
        return resolve_parent_callers(visitor.parsed_functions)
    except Exception as e:
        print(f"Warning: Could not parse {file_path}: {e}")
        return []


def parse_service_directory(dir_path: str) -> List[EndpointCall]:
    """Recursively parse all Python files in a directory and resolve caller hierarchy."""
    if not os.path.exists(dir_path):
        return []

    if os.path.isfile(dir_path):
        return parse_python_file(dir_path, os.path.dirname(dir_path))

    all_parsed_functions: List[ParsedFunction] = []

    for root, _, files in os.walk(dir_path):
        if any(skip in root for skip in ["__pycache__", ".venv", "venv", ".git", ".pytest_cache"]):
            continue
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        code = f.read()
                    tree = ast.parse(code, filename=full_path)
                    rel_path = os.path.relpath(full_path, dir_path)
                    visitor = CodeVisitor(rel_path, code)
                    visitor.visit(tree)
                    all_parsed_functions.extend(visitor.parsed_functions)
                except Exception as e:
                    print(f"Warning: Could not parse {full_path}: {e}")

    return resolve_parent_callers(all_parsed_functions)


def parse_files_in_memory(file_list: List[Dict[str, str]]) -> List[EndpointCall]:
    """Parse a list of virtual files and resolve caller hierarchy."""
    all_parsed_functions: List[ParsedFunction] = []
    for item in file_list:
        path = item.get("path", "")
        content = item.get("content", "")
        if path.endswith(".py") and content:
            try:
                tree = ast.parse(content, filename=path)
                visitor = CodeVisitor(path, content)
                visitor.visit(tree)
                all_parsed_functions.extend(visitor.parsed_functions)
            except Exception as e:
                print(f"Warning: Could not parse in-memory file {path}: {e}")

    return resolve_parent_callers(all_parsed_functions)
