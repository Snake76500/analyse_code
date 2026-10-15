"""
Data models for the Code Migration Engine.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any

@dataclass
class MethodMapping:
    manual_method: str
    autogen_method: str
    param_map: Dict[str, str] = field(default_factory=dict)  # manual_param_name -> autogen_param_name
    positional_map: Dict[int, str] = field(default_factory=dict)  # arg index -> autogen param name
    deprecated_params: List[str] = field(default_factory=list)  # manual params not in autogen
    added_params: Dict[str, Any] = field(default_factory=dict)  # autogen params with default values
    response_transformation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MigrationRule:
    manual_class_name: str = "ManualServiceClient"
    autogen_class_name: str = "AutogenApiClient"
    import_replacements: Dict[str, str] = field(default_factory=dict)  # old_import -> new_import
    constructor_param_map: Dict[str, str] = field(default_factory=dict)  # old_ctor_arg -> new_ctor_arg
    method_mappings: Dict[str, MethodMapping] = field(default_factory=dict)  # manual_method -> MethodMapping
    custom_snippets: Dict[str, str] = field(default_factory=dict)  # before_snippet -> after_snippet

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manual_class_name": self.manual_class_name,
            "autogen_class_name": self.autogen_class_name,
            "import_replacements": self.import_replacements,
            "constructor_param_map": self.constructor_param_map,
            "method_mappings": {k: v.to_dict() for k, v in self.method_mappings.items()},
            "custom_snippets": self.custom_snippets
        }


@dataclass
class FileMigrationResult:
    file_path: str
    original_content: str
    migrated_content: str
    diff: str
    changes_count: int
    applied_rules: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "original_content": self.original_content,
            "migrated_content": self.migrated_content,
            "diff": self.diff,
            "changes_count": self.changes_count,
            "applied_rules": self.applied_rules,
            "warnings": self.warnings
        }


@dataclass
class MigrationReport:
    target_dir: str
    manual_ref: str
    autogen_ref: str
    example_ref: str
    total_files_scanned: int
    files_modified_count: int
    total_calls_migrated: int
    file_results: List[FileMigrationResult] = field(default_factory=list)
    unmapped_calls: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_dir": self.target_dir,
            "manual_ref": self.manual_ref,
            "autogen_ref": self.autogen_ref,
            "example_ref": self.example_ref,
            "total_files_scanned": self.total_files_scanned,
            "files_modified_count": self.files_modified_count,
            "total_calls_migrated": self.total_calls_migrated,
            "file_results": [f.to_dict() for f in self.file_results],
            "unmapped_calls": self.unmapped_calls
        }
