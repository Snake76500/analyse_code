"""
Matching and Parameter Diff Engine for Microservices.
"""
import re
from typing import List, Dict, Tuple, Optional, Set
from .models import EndpointCall, EndpointMatch, ParameterDiff, ParameterInfo, AnalysisResult
from .normalizer import endpoints_match

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


def match_microservices(manual_calls: List[EndpointCall], autogen_calls: List[EndpointCall],
                        manual_path: str = "", autogen_path: str = "") -> AnalysisResult:
    matches: List[EndpointMatch] = []
    used_autogen_indices: Set[int] = set()

    for m_idx, m_call in enumerate(manual_calls):
        matched_a_idx = None
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
                if m_call.http_method == a_call.http_method and endpoints_match(m_call.raw_endpoint, a_call.raw_endpoint):
                    matched_a_idx = a_idx
                    break

        if matched_a_idx is not None:
            used_autogen_indices.add(matched_a_idx)
            a_call = autogen_calls[matched_a_idx]

            diffs, param_status = compare_parameters(m_call.function_params, a_call.function_params)
            diff_count = len([d for d in diffs if d.status != "identical"])
            summary = f"{diff_count} différence(s) de paramètre(s)" if diff_count > 0 else "Paramètres strictement identiques"

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
                summary=summary
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
                summary="Endpoint présent uniquement dans le microservice manuel"
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
                summary="Endpoint présent uniquement dans le microservice autogénéré"
            )
            matches.append(match_obj)

    matched_count = len([m for m in matches if m.status == "MATCHED"])
    manual_only_count = len([m for m in matches if m.status == "MANUAL_ONLY"])
    autogen_only_count = len([m for m in matches if m.status == "AUTOGEN_ONLY"])
    divergent_count = len([m for m in matches if m.status == "MATCHED" and m.param_status == "DIVERGENT"])
    compatible_count = len([m for m in matches if m.status == "MATCHED" and m.param_status == "COMPATIBLE"])
    identical_count = len([m for m in matches if m.status == "MATCHED" and m.param_status == "IDENTICAL"])

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
        matches=matches
    )
