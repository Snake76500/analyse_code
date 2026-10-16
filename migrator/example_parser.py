"""
Parser for migration example files (Python before/after blocks or .diff/.patch files).
Extracts client class names, import changes, constructor adjustments, and method call transformations.
"""
import ast
import re
from typing import Tuple, Optional, Dict, List, Any
from .models import MigrationRule, MethodMapping

BEFORE_MARKERS = [
    r'#\s*(?:---+\s*)?(?:AVANT|BEFORE|EXEMPLE\s*AVANT|CODE\s*INITIAL|MANUEL|SOURCE|INITIAL)',
    r'\"\"\"(?:---+\s*)?(?:AVANT|BEFORE|EXEMPLE\s*AVANT|CODE\s*INITIAL|MANUEL|SOURCE|INITIAL)'
]

AFTER_MARKERS = [
    r'#\s*(?:---+\s*)?(?:APRES|APRÈS|AFTER|EXEMPLE\s*APRES|EXEMPLE\s*APRÈS|CODE\s*MIGRE|MIGRATED|AUTOGEN|CIBLE)',
    r'\"\"\"(?:---+\s*)?(?:APRES|APRÈS|AFTER|EXEMPLE\s*APRES|EXEMPLE\s*APRÈS|CODE\s*MIGRE|MIGRATED|AUTOGEN|CIBLE)'
]


class ExampleMigrationParser:
    def __init__(self, example_content: str):
        self.raw_content = example_content
        self.before_code = ""
        self.after_code = ""
        self._split_example()

    def _split_example(self):
        """Split into before and after code segments."""
        content = self.raw_content.strip()

        # 1. Check if unified diff (.diff / .patch format)
        if "@@" in content and ("---" in content or "+++" in content):
            before_lines = []
            after_lines = []
            for line in content.splitlines():
                if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
                    continue
                if line.startswith("-"):
                    before_lines.append(line[1:])
                elif line.startswith("+"):
                    after_lines.append(line[1:])
                else:
                    stripped = line[1:] if line.startswith(" ") else line
                    before_lines.append(stripped)
                    after_lines.append(stripped)
            self.before_code = "\n".join(before_lines)
            self.after_code = "\n".join(after_lines)
            return

        # 2. Check for explicit BEFORE / AFTER markers in comments
        before_pattern = re.compile("|".join(BEFORE_MARKERS), re.IGNORECASE)
        after_pattern = re.compile("|".join(AFTER_MARKERS), re.IGNORECASE)

        before_match = before_pattern.search(content)
        after_match = after_pattern.search(content)

        if before_match and after_match:
            nl_before = content.find("\n", before_match.end())
            b_start = nl_before + 1 if nl_before != -1 else before_match.end()

            a_start = after_match.start()
            line_start = content.rfind("\n", 0, a_start)
            if line_start != -1:
                a_start = line_start

            nl_after = content.find("\n", after_match.end())
            a_end = nl_after + 1 if nl_after != -1 else after_match.end()

            if b_start < a_start:
                def clean_block(code_str: str) -> str:
                    lines = []
                    for line in code_str.splitlines():
                        s = line.strip()
                        if s.startswith("# ===") or s.startswith("# ---") or s == "#":
                            continue
                        lines.append(line)
                    return "\n".join(lines).strip()

                self.before_code = clean_block(content[b_start:a_start])
                self.after_code = clean_block(content[a_end:])
                return

        # 3. Fallback: check for functions named like before_*/manual_* and after_*/autogen_*
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = node.name.lower()
                    if any(k in name for k in ["before", "avant", "manual", "initial"]):
                        self.before_code = ast.get_source_segment(content, node) or ""
                    elif any(k in name for k in ["after", "apres", "après", "autogen", "migrated"]):
                        self.after_code = ast.get_source_segment(content, node) or ""
        except Exception:
            pass

        # 4. If still not split, store entire content as reference template
        if not self.before_code and not self.after_code:
            self.before_code = content
            self.after_code = content

    def parse_rule(self) -> MigrationRule:
        rule = MigrationRule()
        if not self.before_code or not self.after_code:
            return rule

        self._extract_imports(rule)
        self._extract_classes_and_constructors(rule)
        self._extract_method_calls(rule)
        return rule

    def _extract_imports(self, rule: MigrationRule):
        """Extract import replacements (e.g. ManualServiceClient -> AutogenApiClient)."""
        b_imports = self._get_imports(self.before_code)
        a_imports = self._get_imports(self.after_code)

        for b_module, b_name, b_alias in b_imports:
            for a_module, a_name, a_alias in a_imports:
                if "client" in b_name.lower() and "client" in a_name.lower():
                    rule.manual_class_name = b_name
                    rule.autogen_class_name = a_name

                # Line replacement pattern
                b_stmt = f"from {b_module} import {b_name}" if b_module else f"import {b_name}"
                a_stmt = f"from {a_module} import {a_name}" if a_module else f"import {a_name}"
                rule.import_replacements[b_stmt] = a_stmt

    def _get_imports(self, code: str) -> List[Tuple[str, str, Optional[str]]]:
        imports = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(("", alias.name, alias.asname))
                elif isinstance(node, ast.ImportFrom) and node.module:
                    for alias in node.names:
                        imports.append((node.module, alias.name, alias.asname))
        except Exception:
            pass
        return imports

    def _extract_classes_and_constructors(self, rule: MigrationRule):
        """Extract constructor instantiation differences (e.g. api_key -> token)."""
        b_calls = self._get_constructor_calls(self.before_code)
        a_calls = self._get_constructor_calls(self.after_code)

        for b_cls, b_kw in b_calls:
            for a_cls, a_kw in a_calls:
                if b_cls != a_cls:
                    rule.manual_class_name = b_cls
                    rule.autogen_class_name = a_cls

                # Compare constructor keyword arguments
                for b_k in b_kw:
                    for a_k in a_kw:
                        if b_k != a_k:
                            rule.constructor_param_map[b_k] = a_k

    def _get_constructor_calls(self, code: str) -> List[Tuple[str, List[str]]]:
        calls = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    cls_name = ""
                    if isinstance(node.func, ast.Name):
                        cls_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        cls_name = node.func.attr

                    if cls_name and any(c.isupper() for c in cls_name) and "Client" in cls_name:
                        keywords = [kw.arg for kw in node.keywords if kw.arg]
                        calls.append((cls_name, keywords))
        except Exception:
            pass
        return calls

    def _extract_method_calls(self, rule: MigrationRule):
        """Extract method call transformations from before/after code blocks."""
        from analyzer.matcher import are_param_names_similar

        b_calls = self._get_client_method_calls(self.before_code)
        a_calls = self._get_client_method_calls(self.after_code)

        min_len = min(len(b_calls), len(a_calls))
        for i in range(min_len):
            b_method, b_args, b_kw = b_calls[i]
            a_method, a_args, a_kw = a_calls[i]

            param_map = {}
            unmatched_b = [bk for bk in b_kw if bk not in a_kw]
            unmatched_a = [ak for ak in a_kw if ak not in b_kw]

            for bk in unmatched_b:
                for ak in unmatched_a:
                    if are_param_names_similar(bk, ak):
                        param_map[bk] = ak
                        break
                if bk not in param_map and len(unmatched_b) == 1 and len(unmatched_a) == 1:
                    param_map[bk] = unmatched_a[0]

            # Positional index mapping
            pos_map = {}
            for idx, ak in enumerate(a_kw):
                if idx < len(b_args):
                    pos_map[idx] = ak

            mapping = MethodMapping(
                manual_method=b_method,
                autogen_method=a_method,
                param_map=param_map,
                positional_map=pos_map
            )
            rule.method_mappings[b_method] = mapping

    def _get_client_method_calls(self, code: str) -> List[Tuple[str, List[Any], List[str]]]:
        calls = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    # Extract attribute chain, e.g. client.views.get_product_views -> views.get_product_views
                    parts = []
                    curr = node.func
                    while isinstance(curr, ast.Attribute):
                        parts.append(curr.attr)
                        curr = curr.value
                    parts.reverse()
                    method_name = ".".join(parts)
                    if not method_name or parts[-1].startswith("_") and not parts[-1].startswith("__"):
                        continue
                    args = [ast.unparse(a) for a in node.args]
                    keywords = [kw.arg for kw in node.keywords if kw.arg]
                    calls.append((method_name, args, keywords))
        except Exception:
            pass
        return calls
