"""
Data models for Microservices Endpoint & Parameter Matrix Analyzer.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

@dataclass
class ParameterInfo:
    name: str
    type_annotation: Optional[str] = None
    default_value: Optional[str] = None
    required: bool = True
    kind: str = "arg"  # arg, path, query, body, header
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EndpointCall:
    function_name: str
    file_path: str
    line_number: int
    end_line_number: int
    kind: str  # 'client_call' or 'server_route'
    http_method: str  # GET, POST, PUT, DELETE, PATCH, etc.
    raw_endpoint: str
    normalized_endpoint: str
    function_params: List[ParameterInfo] = field(default_factory=list)
    path_params: List[str] = field(default_factory=list)
    query_params: List[str] = field(default_factory=list)
    body_params: List[str] = field(default_factory=list)
    headers: List[str] = field(default_factory=list)
    code_snippet: str = ""
    docstring: Optional[str] = None
    callee_function: Optional[str] = None
    caller_chain: List[str] = field(default_factory=list)
    class_name: Optional[str] = None
    origin_class: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "function_name": self.function_name,
            "class_name": self.class_name,
            "origin_class": self.origin_class or self.class_name,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "end_line_number": self.end_line_number,
            "kind": self.kind,
            "http_method": self.http_method,
            "raw_endpoint": self.raw_endpoint,
            "normalized_endpoint": self.normalized_endpoint,
            "function_params": [p.to_dict() for p in self.function_params],
            "path_params": self.path_params,
            "query_params": self.query_params,
            "body_params": self.body_params,
            "headers": self.headers,
            "code_snippet": self.code_snippet,
            "docstring": self.docstring,
            "callee_function": self.callee_function,
            "caller_chain": self.caller_chain
        }


@dataclass
class ParameterDiff:
    name: str
    status: str  # 'identical', 'type_mismatch', 'default_mismatch', 'manual_only', 'autogen_only', 'renamed_candidate'
    manual_param: Optional[ParameterInfo] = None
    autogen_param: Optional[ParameterInfo] = None
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "manual_param": self.manual_param.to_dict() if self.manual_param else None,
            "autogen_param": self.autogen_param.to_dict() if self.autogen_param else None,
            "details": self.details
        }


@dataclass
class EndpointMatch:
    id: str
    http_method: str
    normalized_endpoint: str
    raw_endpoint_manual: Optional[str] = None
    raw_endpoint_autogen: Optional[str] = None
    status: str = "MATCHED"  # MATCHED, MANUAL_ONLY, AUTOGEN_ONLY
    param_status: str = "IDENTICAL"  # IDENTICAL, COMPATIBLE, DIVERGENT, N/A
    manual_call: Optional[EndpointCall] = None
    autogen_call: Optional[EndpointCall] = None
    param_diffs: List[ParameterDiff] = field(default_factory=list)
    summary: str = ""
    call_example: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "http_method": self.http_method,
            "normalized_endpoint": self.normalized_endpoint,
            "raw_endpoint_manual": self.raw_endpoint_manual,
            "raw_endpoint_autogen": self.raw_endpoint_autogen,
            "status": self.status,
            "param_status": self.param_status,
            "manual_call": self.manual_call.to_dict() if self.manual_call else None,
            "autogen_call": self.autogen_call.to_dict() if self.autogen_call else None,
            "param_diffs": [d.to_dict() for d in self.param_diffs],
            "summary": self.summary,
            "call_example": self.call_example
        }


@dataclass
class AnalysisResult:
    manual_service_path: str
    autogen_service_path: str
    manual_endpoints_count: int
    autogen_endpoints_count: int
    matched_count: int
    manual_only_count: int
    autogen_only_count: int
    divergent_count: int
    identical_count: int
    compatible_count: int
    dependency_file: Optional[str] = None
    matches: List[EndpointMatch] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manual_service_path": self.manual_service_path,
            "autogen_service_path": self.autogen_service_path,
            "manual_endpoints_count": self.manual_endpoints_count,
            "autogen_endpoints_count": self.autogen_endpoints_count,
            "matched_count": self.matched_count,
            "manual_only_count": self.manual_only_count,
            "autogen_only_count": self.autogen_only_count,
            "divergent_count": self.divergent_count,
            "identical_count": self.identical_count,
            "compatible_count": self.compatible_count,
            "dependency_file": self.dependency_file,
            "matches": [m.to_dict() for m in self.matches]
        }
