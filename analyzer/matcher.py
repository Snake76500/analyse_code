"""
Matching and Parameter Diff Engine for Microservices.
"""
import os
import re
from typing import List, Dict, Tuple, Optional, Set
from .models import EndpointCall, EndpointMatch, ParameterDiff, ParameterInfo, AnalysisResult
from .normalizer import endpoints_match
from .dependency_parser import (
    find_dependency_file,
    parse_dependency_file,
    parse_dependency_content,
    build_dependency_registry_from_directory,
    build_dependency_registry_from_memory,
    get_homonym_dependency,
    extract_service_stem_from_dependency_path,
    generate_function_call_example,
    build_class_method_index,
    build_class_subattributes_index,
    get_sync_api_client_variable_map,
    DependencyContext
)
from .parser import get_function_origin_class_map

def to_snake_case(name: str) -> str:
    """Convert camelCase or PascalCase to snake_case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

def are_param_names_similar(p1: str, p2: str) -> bool:
    """Check if parameter names are semantically equivalent."""
    s1 = to_snake_case(p1)
    s2 = to_snake_case(p2)
    if s1 == s2:
        return True

    synonyms = [
        {"id", "user_id", "userid"},
        {"id", "item_id", "itemid"},
        {"id", "order_id", "orderid"},
        {"id", "payment_id", "paymentid"},
        {"quantity", "qty", "count", "stock", "stock_count"},
        {"limit", "page_size", "pagesize", "count", "max_results"},
        {"offset", "skip", "page", "page_num"},
        {"payload", "body", "data", "request"},
        {"q", "query", "search", "keyword"},
        {"token", "key", "api_key", "apikey"},
    ]
    for syn_set in synonyms:
        if s1 in syn_set and s2 in syn_set:
            return True

    return False

def compare_types(t1: Optional[str], t2: Optional[str]) -> Tuple[bool, str]:
    """Compare type annotations."""
    if not t1 and not t2:
        return True, "Types non spécifiés"
    if not t1 or not t2:
        return False, f"Type partiel: '{t1 or 'Any'}' vs '{t2 or 'Any'}'"

    clean1 = t1.replace("typing.", "").replace(" ", "")
    clean2 = t2.replace("typing.", "").replace(" ", "")

    if clean1 == clean2:
        return True, f"Identique ({t1})"

    if clean1.replace("Optional[", "").rstrip("]") == clean2.replace("Optional[", "").rstrip("]"):
        return True, f"Compatible (Optionnel): '{t1}' vs '{t2}'"

    return False, f"Différence de type: '{t1}' vs '{t2}'"

def compare_parameters(manual_params: List[ParameterInfo], autogen_params: List[ParameterInfo]) -> Tuple[List[ParameterDiff], str]:
    diffs: List[ParameterDiff] = []
    has_incompatible = False
    has_minor_diff = False

    manual_dict: Dict[str, ParameterInfo] = {p.name: p for p in manual_params}
    autogen_dict: Dict[str, ParameterInfo] = {p.name: p for p in autogen_params}

    matched_autogen_keys: Set[str] = set()

    for m_name, m_param in manual_dict.items():
        if m_name in autogen_dict:
            a_param = autogen_dict[m_name]
            matched_autogen_keys.add(m_name)

            type_match, type_desc = compare_types(m_param.type_annotation, a_param.type_annotation)
            default_match = (m_param.default_value == a_param.default_value)
            req_match = (m_param.required == a_param.required)

            if type_match and default_match and req_match:
                diffs.append(ParameterDiff(
                    name=m_name,
                    status="identical",
                    manual_param=m_param,
                    autogen_param=a_param,
                    details=f"Paramètre identique ({m_param.type_annotation or 'Any'})"
                ))
            else:
                status = "type_mismatch" if not type_match else "default_mismatch"
                details_parts = []
                if not type_match:
                    details_parts.append(type_desc)
                    has_minor_diff = True
                if not default_match:
                    details_parts.append(f"Défaut: '{m_param.default_value}' vs '{a_param.default_value}'")
                    has_minor_diff = True
                if not req_match:
                    details_parts.append(f"Requis: {m_param.required} vs {a_param.required}")
                    if m_param.required and not a_param.required:
                        has_minor_diff = True
                    else:
                        has_incompatible = True

                diffs.append(ParameterDiff(
                    name=m_name,
                    status=status,
                    manual_param=m_param,
                    autogen_param=a_param,
                    details=", ".join(details_parts)
                ))
        else:
            found_candidate = None
            for a_name, a_param in autogen_dict.items():
                if a_name not in matched_autogen_keys and are_param_names_similar(m_name, a_name):
                    found_candidate = (a_name, a_param)
                    break

            if found_candidate:
                a_name, a_param = found_candidate
                matched_autogen_keys.add(a_name)
                type_match, type_desc = compare_types(m_param.type_annotation, a_param.type_annotation)
                diffs.append(ParameterDiff(
                    name=f"{m_name} ➔ {a_name}",
                    status="renamed_candidate",
                    manual_param=m_param,
                    autogen_param=a_param,
                    details=f"Renommé ({m_name} dans manuel, {a_name} dans autogénéré). {type_desc}"
                ))
                has_minor_diff = True
            else:
                status = "manual_only"
                is_req = m_param.required
                if is_req:
                    has_incompatible = True
                else:
                    has_minor_diff = True
                diffs.append(ParameterDiff(
                    name=m_name,
                    status=status,
                    manual_param=m_param,
                    autogen_param=None,
                    details=f"Uniquement dans le code manuel ({'Requis' if is_req else 'Optionnel'})"
                ))

    for a_name, a_param in autogen_dict.items():
        if a_name not in matched_autogen_keys:
            is_req = a_param.required
            if is_req:
                has_incompatible = True
            else:
                has_minor_diff = True
            diffs.append(ParameterDiff(
                name=a_name,
                status="autogen_only",
                manual_param=None,
                autogen_param=a_param,
                details=f"Uniquement dans le code autogénéré ({'Requis' if is_req else 'Optionnel'})"
            ))

    if has_incompatible:
        overall_status = "DIVERGENT"
    elif has_minor_diff:
        overall_status = "COMPATIBLE"
    else:
        overall_status = "IDENTICAL"

    return diffs, overall_status


def are_paths_exact_match(p1: str, p2: str) -> bool:
    """Check if two file paths have the exact same normalized relative path."""
    if not p1 and not p2:
        return True
    if not p1 or not p2:
        return False
    norm1 = os.path.normpath(p1).replace("\\", "/").lstrip("./")
    norm2 = os.path.normpath(p2).replace("\\", "/").lstrip("./")
    return norm1 == norm2


def are_file_names_matching(p1: str, p2: str) -> bool:
    """
    Check if two file paths correspond to the same file or files containing the same name.
    Rule: Relie bien les fichiers contenant le même nom (case-insensitive, stem and basename).
    Endpoints from files with the same name are linked; files with different names are not crossed.
    """
    if not p1 and not p2:
        return True
    if not p1 or not p2:
        return False
    if are_paths_exact_match(p1, p2):
        return True

    base1 = os.path.basename(os.path.normpath(p1).replace("\\", "/")).lower()
    base2 = os.path.basename(os.path.normpath(p2).replace("\\", "/")).lower()
    if base1 == base2:
        return True

    stem1 = os.path.splitext(base1)[0]
    stem2 = os.path.splitext(base2)[0]
    if stem1 == stem2:
        return True

    clean1 = re.sub(r'(_service|_controller|_api|_client|_router|_view)$', '', stem1)
    clean2 = re.sub(r'(_service|_controller|_api|_client|_router|_view)$', '', stem2)
    if clean1 and clean2 and clean1 == clean2:
        return True

    # Check if files contain the same name (for significant stems >= 3 chars)
    if len(clean1) >= 3 and len(clean2) >= 3:
        if clean1 in clean2 or clean2 in clean1:
            return True

    return False


def should_enforce_same_filename(
    manual_calls: List[EndpointCall],
    autogen_calls: List[EndpointCall],
    manual_path: str = "",
    autogen_path: str = ""
) -> bool:
    """
    Determine if comparison should be strictly constrained to files with the same name.
    Rule: When the source is a directory with multiple files or if either source is a directory,
    files with different names must never be crossed.
    """
    is_m_file = bool(manual_path and os.path.isfile(manual_path))
    is_a_file = bool(autogen_path and os.path.isfile(autogen_path))

    m_files = {os.path.basename(c.file_path) for c in manual_calls if c.file_path}
    a_files = {os.path.basename(c.file_path) for c in autogen_calls if c.file_path}

    # Only when both paths are explicitly single files on disk with at most 1 file each:
    if is_m_file and is_a_file and len(m_files) <= 1 and len(a_files) <= 1:
        return False

    # In all other cases (directories, multi-file sources, web uploads), enforce same filename
    return True


def match_microservices(manual_calls: List[EndpointCall], autogen_calls: List[EndpointCall],
                        manual_path: str = "", autogen_path: str = "",
                        strict_file_matching: Optional[bool] = None,
                        dependency_content: Optional[str] = None,
                        dependency_file_path: Optional[str] = None,
                        dependency_registry: Optional[Dict[str, DependencyContext]] = None,
                        class_method_index: Optional[Dict[str, Set[str]]] = None,
                        class_subattributes_index: Optional[Dict[str, Dict[str, str]]] = None) -> AnalysisResult:
    """
    Match HTTP endpoints and compare parameters between manual and autogenerated microservices.
    When sources are directories containing multiple files, comparison is strictly restricted
    to files with the same name (no cross-matching between different files).
    Understands *_dependency.py declaration files to generate function call examples and imports.
    Rule: fichiera.py is linked ONLY to its homonym fichiera_dependency.py.
    """
    matches: List[EndpointMatch] = []
    used_autogen_indices: Set[int] = set()

    # Build or resolve dependency registry mapping homonym stems to DependencyContext
    dep_registry: Dict[str, DependencyContext] = {}
    if dependency_registry:
        dep_registry = dependency_registry
    elif dependency_content and dependency_file_path:
        ctx = parse_dependency_content(dependency_content, dependency_file_path)
        stem = extract_service_stem_from_dependency_path(dependency_file_path)
        if stem:
            dep_registry[stem.lower()] = ctx
    elif dependency_file_path and os.path.exists(dependency_file_path):
        ctx = parse_dependency_file(dependency_file_path)
        if ctx:
            stem = extract_service_stem_from_dependency_path(dependency_file_path)
            if stem:
                dep_registry[stem.lower()] = ctx
    elif autogen_path and os.path.exists(autogen_path):
        dep_registry = build_dependency_registry_from_directory(autogen_path)

    if strict_file_matching is not None:
        enforce_same_filename = strict_file_matching
    else:
        enforce_same_filename = should_enforce_same_filename(
            manual_calls, autogen_calls, manual_path, autogen_path
        )

    known_manual_classes: Set[str] = {m.class_name for m in manual_calls if m.class_name}
    known_autogen_classes: Set[str] = {a.class_name for a in autogen_calls if a.class_name}

    if class_method_index is None:
        class_method_index = build_class_method_index(dir_path=autogen_path, calls=autogen_calls)

    if class_subattributes_index is None:
        class_subattributes_index = build_class_subattributes_index(
            dir_path=autogen_path,
            dependency_registry=dep_registry
        )

    sync_api_client_vars = get_sync_api_client_variable_map(
        dir_path=autogen_path,
        dependency_registry=dep_registry
    )

    function_origin_map = get_function_origin_class_map(
        dir_path=autogen_path
    )

    for m_idx, m_call in enumerate(manual_calls):
        matched_a_idx = None

        # Level 1: Exact endpoint match AND exact path match
        for a_idx, a_call in enumerate(autogen_calls):
            if a_idx in used_autogen_indices:
                continue
            if not are_paths_exact_match(m_call.file_path, a_call.file_path):
                continue
            if m_call.http_method == a_call.http_method and m_call.normalized_endpoint == a_call.normalized_endpoint:
                matched_a_idx = a_idx
                break

        # Level 2: Exact endpoint match AND matching file name (same basename)
        if matched_a_idx is None:
            for a_idx, a_call in enumerate(autogen_calls):
                if a_idx in used_autogen_indices:
                    continue
                if enforce_same_filename and not are_file_names_matching(m_call.file_path, a_call.file_path):
                    continue
                if m_call.http_method == a_call.http_method and m_call.normalized_endpoint == a_call.normalized_endpoint:
                    matched_a_idx = a_idx
                    break

        # Level 3: Fuzzy endpoint match AND exact path match
        if matched_a_idx is None:
            for a_idx, a_call in enumerate(autogen_calls):
                if a_idx in used_autogen_indices:
                    continue
                if not are_paths_exact_match(m_call.file_path, a_call.file_path):
                    continue
                if m_call.http_method == a_call.http_method and (
                    endpoints_match(m_call.raw_endpoint, a_call.raw_endpoint) or
                    endpoints_match(m_call.normalized_endpoint, a_call.normalized_endpoint)
                ):
                    matched_a_idx = a_idx
                    break

        # Level 4: Fuzzy endpoint match AND matching file name (same basename)
        if matched_a_idx is None:
            for a_idx, a_call in enumerate(autogen_calls):
                if a_idx in used_autogen_indices:
                    continue
                if enforce_same_filename and not are_file_names_matching(m_call.file_path, a_call.file_path):
                    continue
                if m_call.http_method == a_call.http_method and (
                    endpoints_match(m_call.raw_endpoint, a_call.raw_endpoint) or
                    endpoints_match(m_call.normalized_endpoint, a_call.normalized_endpoint)
                ):
                    matched_a_idx = a_idx
                    break

        # Levels 5 & 6: Only if not enforcing same filename (e.g. 2 single files with different names)
        if matched_a_idx is None and not enforce_same_filename:
            for a_idx, a_call in enumerate(autogen_calls):
                if a_idx in used_autogen_indices:
                    continue
                if m_call.http_method == a_call.http_method and m_call.normalized_endpoint == a_call.normalized_endpoint:
                    matched_a_idx = a_idx
                    break

            if matched_a_idx is None:
                for a_idx, a_call in enumerate(autogen_calls):
                    if a_idx in used_autogen_indices:
                        continue
                    if m_call.http_method == a_call.http_method and (
                        endpoints_match(m_call.raw_endpoint, a_call.raw_endpoint) or
                        endpoints_match(m_call.normalized_endpoint, a_call.normalized_endpoint)
                    ):
                        matched_a_idx = a_idx
                        break

        if matched_a_idx is not None:
            used_autogen_indices.add(matched_a_idx)
            a_call = autogen_calls[matched_a_idx]

            diffs, param_status = compare_parameters(m_call.function_params, a_call.function_params)
            diff_count = len([d for d in diffs if d.status != "identical"])
            summary = f"{diff_count} différence(s) de paramètre(s)" if diff_count > 0 else "Paramètres strictement identiques"

            call_dep_ctx = get_homonym_dependency(a_call.file_path, dep_registry)

            match_obj = EndpointMatch(
                id=f"match_{len(matches) + 1}",
                http_method=m_call.http_method,
                normalized_endpoint=m_call.normalized_endpoint,
                raw_endpoint_manual=m_call.raw_endpoint,
                raw_endpoint_autogen=a_call.raw_endpoint,
                status="MATCHED",
                param_status=param_status,
                manual_call=m_call,
                autogen_call=a_call,
                param_diffs=diffs,
                summary=summary,
                call_example=generate_function_call_example(
                    a_call,
                    dependency_ctx=call_dep_ctx,
                    service_root_path=autogen_path,
                    manual_service_path=manual_path,
                    known_manual_classes=known_manual_classes,
                    known_autogen_classes=known_autogen_classes,
                    class_method_index=class_method_index,
                    class_subattributes_index=class_subattributes_index,
                    sync_api_client_vars=sync_api_client_vars,
                    function_origin_map=function_origin_map
                )
            )
            matches.append(match_obj)
        else:
            diffs = [ParameterDiff(
                name=p.name,
                status="manual_only",
                manual_param=p,
                autogen_param=None,
                details=f"Paramètre du code manuel ({p.type_annotation or 'Any'})"
            ) for p in m_call.function_params]

            file_info = f" ({m_call.file_path})" if m_call.file_path else ""
            match_obj = EndpointMatch(
                id=f"match_{len(matches) + 1}",
                http_method=m_call.http_method,
                normalized_endpoint=m_call.normalized_endpoint,
                raw_endpoint_manual=m_call.raw_endpoint,
                raw_endpoint_autogen=None,
                status="MANUAL_ONLY",
                param_status="N/A",
                manual_call=m_call,
                autogen_call=None,
                param_diffs=diffs,
                summary=f"Endpoint présent uniquement dans le microservice manuel{file_info}"
            )
            matches.append(match_obj)

    for a_idx, a_call in enumerate(autogen_calls):
        if a_idx not in used_autogen_indices:
            diffs = [ParameterDiff(
                name=p.name,
                status="autogen_only",
                manual_param=None,
                autogen_param=p,
                details=f"Paramètre du code autogénéré ({p.type_annotation or 'Any'})"
            ) for p in a_call.function_params]

            file_info = f" ({a_call.file_path})" if a_call.file_path else ""
            call_dep_ctx = get_homonym_dependency(a_call.file_path, dep_registry)

            match_obj = EndpointMatch(
                id=f"match_{len(matches) + 1}",
                http_method=a_call.http_method,
                normalized_endpoint=a_call.normalized_endpoint,
                raw_endpoint_manual=None,
                raw_endpoint_autogen=a_call.raw_endpoint,
                status="AUTOGEN_ONLY",
                param_status="N/A",
                manual_call=None,
                autogen_call=a_call,
                param_diffs=diffs,
                summary=f"Endpoint présent uniquement dans le microservice autogénéré{file_info}",
                call_example=generate_function_call_example(
                    a_call,
                    dependency_ctx=call_dep_ctx,
                    service_root_path=autogen_path,
                    manual_service_path=manual_path,
                    known_manual_classes=known_manual_classes,
                    known_autogen_classes=known_autogen_classes,
                    class_method_index=class_method_index,
                    class_subattributes_index=class_subattributes_index,
                    sync_api_client_vars=sync_api_client_vars,
                    function_origin_map=function_origin_map
                )
            )
            matches.append(match_obj)

    matched_count = len([m for m in matches if m.status == "MATCHED"])
    manual_only_count = len([m for m in matches if m.status == "MANUAL_ONLY"])
    autogen_only_count = len([m for m in matches if m.status == "AUTOGEN_ONLY"])
    divergent_count = len([m for m in matches if m.status == "MATCHED" and m.param_status == "DIVERGENT"])
    compatible_count = len([m for m in matches if m.status == "MATCHED" and m.param_status == "COMPATIBLE"])
    identical_count = len([m for m in matches if m.status == "MATCHED" and m.param_status == "IDENTICAL"])

    dep_files = [ctx.file_path for ctx in dep_registry.values() if ctx and ctx.file_path]
    unique_dep_files = sorted(set(os.path.basename(f) for f in dep_files if f))
    dep_summary = ", ".join(unique_dep_files) if unique_dep_files else None

    return AnalysisResult(
        manual_service_path=manual_path,
        autogen_service_path=autogen_path,
        manual_endpoints_count=len(manual_calls),
        autogen_endpoints_count=len(autogen_calls),
        matched_count=matched_count,
        manual_only_count=manual_only_count,
        autogen_only_count=autogen_only_count,
        divergent_count=divergent_count,
        identical_count=identical_count,
        compatible_count=compatible_count,
        dependency_file=dep_summary,
        matches=matches
    )
