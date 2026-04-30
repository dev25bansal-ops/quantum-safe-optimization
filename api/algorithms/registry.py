"""
Custom Algorithm Upload and Management.

Allows users to upload and execute custom quantum algorithms.
"""

import ast
import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class AlgorithmStatus(str, Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    APPROVED = "approved"
    REJECTED = "rejected"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AlgorithmLanguage(str, Enum):
    PYTHON = "python"
    QISKIT = "qiskit"
    CIRQ = "cirq"
    PENNYLANE = "pennylane"
    QASM = "qasm"
    QUBO = "qubo"


@dataclass
class AlgorithmMetadata:
    algorithm_id: str
    name: str
    version: str
    author_id: str
    language: AlgorithmLanguage
    status: AlgorithmStatus
    description: str
    entry_point: str
    parameters: dict[str, Any]
    requirements: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    num_qubits: int = 0
    estimated_runtime_ms: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    checksum: str = ""
    source_file: str = ""
    validation_errors: list[str] = field(default_factory=list)


class AlgorithmUpload(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    language: AlgorithmLanguage
    description: str = Field(..., min_length=10, max_length=2000)
    entry_point: str = Field(default="main")
    parameters: dict[str, Any] = Field(default_factory=dict)
    requirements: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class AlgorithmUploadResponse(BaseModel):
    algorithm_id: str
    upload_url: str
    checksum_required: str
    max_size_bytes: int = 10485760  # 10MB


class AlgorithmValidator:
    """Validates uploaded algorithms for safety and correctness."""

    FORBIDDEN_IMPORTS = {
        "os.system",
        "subprocess",
        "eval",
        "exec",
        "compile",
        "importlib",
        "__import__",
        "pickle",
        "marshal",
        "shelve",
        "shutil",
        "socket",
        "requests",
        "urllib",
        "http",
        "ftplib",
        "telnetlib",
        "smtplib",
    }

    FORBIDDEN_FUNCTIONS = {
        "eval",
        "exec",
        "compile",
        "open",
        "input",
        "breakpoint",
        "exit",
        "quit",
    }

    def __init__(self):
        self.errors: list[str] = []

    def validate_source(self, source_code: str, language: AlgorithmLanguage) -> tuple[bool, list[str]]:
        """Validate source code for safety."""
        self.errors = []

        if language == AlgorithmLanguage.PYTHON or language in (
            AlgorithmLanguage.QISKIT,
            AlgorithmLanguage.CIRQ,
            AlgorithmLanguage.PENNYLANE,
        ):
            self._validate_python(source_code)
        elif language == AlgorithmLanguage.QASM:
            self._validate_qasm(source_code)
        elif language == AlgorithmLanguage.QUBO:
            self._validate_qubo(source_code)

        return len(self.errors) == 0, self.errors

    def _validate_python(self, source_code: str) -> None:
        """Validate Python source code."""
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            self.errors.append(f"Syntax error: {e}")
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split(".")[0]
                    if module in self.FORBIDDEN_IMPORTS:
                        self.errors.append(f"Forbidden import: {alias.name}")

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module = node.module.split(".")[0]
                    if module in self.FORBIDDEN_IMPORTS:
                        self.errors.append(f"Forbidden import from: {node.module}")

            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.FORBIDDEN_FUNCTIONS:
                        self.errors.append(f"Forbidden function call: {node.func.id}")

                elif isinstance(node.func, ast.Attribute):
                    attr_chain = self._get_attribute_chain(node.func)
                    if any(forbidden in attr_chain for forbidden in self.FORBIDDEN_IMPORTS):
                        self.errors.append(f"Forbidden attribute access: {attr_chain}")

            elif isinstance(node, (ast.Exec, ast.Eval)):
                self.errors.append(f"Forbidden construct: {type(node).__name__}")

    def _get_attribute_chain(self, node: ast.Attribute) -> str:
        """Get full attribute chain from AST node."""
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))

    def _validate_qasm(self, source_code: str) -> None:
        """Validate QASM source code."""
        forbidden_patterns = [
            r"include\s+['\"]stdgates\.inc['\"]",
            r"creg\s+\w+\s*\[\s*\d+\s*\]",
            r"measure\s+",
        ]

        for pattern in forbidden_patterns:
            if re.search(pattern, source_code, re.IGNORECASE):
                self.errors.append(f"Potentially unsafe QASM pattern: {pattern}")

        valid_gates = {"h", "x", "y", "z", "cx", "cz", "swap", "rx", "ry", "rz", "u", "measure"}

        gate_pattern = r"(\w+)\s+"
        for match in re.finditer(gate_pattern, source_code):
            gate = match.group(1).lower()
            if gate not in valid_gates and gate not in {"qreg", "creg", "include", "barrier"}:
                logger.warning("unknown_gate_in_qasm", gate=gate)

    def _validate_qubo(self, source_code: str) -> None:
        """Validate QUBO matrix definition using safe parsing."""
        import json
        
        data = None
        try:
            data = json.loads(source_code)
        except json.JSONDecodeError:
            try:
                import ast
                parsed = ast.parse(source_code, mode='eval')
                for node in ast.walk(parsed):
                    if isinstance(node, (ast.Call, ast.Import, ast.ImportFrom)):
                        self.errors.append("QUBO must be a simple data structure, not code")
                        return
                data = ast.literal_eval(source_code)
            except (ValueError, SyntaxError) as e:
                self.errors.append(f"Invalid QUBO format: {e}")
                return

        if data is not None:
            if not isinstance(data, (list, dict)):
                self.errors.append("QUBO must be a list or dict")

            if isinstance(data, list):
                for row in data:
                    if not isinstance(row, list):
                        self.errors.append("QUBO matrix rows must be lists")


class AlgorithmRegistry:
    """Registry for custom algorithms."""

    def __init__(self, storage_path: str = "algorithms"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._algorithms: dict[str, AlgorithmMetadata] = {}
        self.validator = AlgorithmValidator()

    def _calculate_checksum(self, content: bytes) -> str:
        """Calculate SHA256 checksum."""
        return hashlib.sha256(content).hexdigest()

    def register_algorithm(
        self,
        upload_request: AlgorithmUpload,
        source_code: bytes,
        author_id: str,
    ) -> AlgorithmMetadata:
        """Register a new algorithm."""
        algorithm_id = f"algo_{uuid4().hex[:12]}"

        checksum = self._calculate_checksum(source_code)

        language = upload_request.language
        if isinstance(language, str):
            language = AlgorithmLanguage(language)

        metadata = AlgorithmMetadata(
            algorithm_id=algorithm_id,
            name=upload_request.name,
            version=upload_request.version,
            author_id=author_id,
            language=language,
            status=AlgorithmStatus.VALIDATING,
            description=upload_request.description,
            entry_point=upload_request.entry_point,
            parameters=upload_request.parameters,
            requirements=upload_request.requirements,
            tags=upload_request.tags,
            checksum=checksum,
        )

        is_valid, errors = self.validator.validate_source(
            source_code.decode("utf-8"), language
        )

        if not is_valid:
            metadata.status = AlgorithmStatus.REJECTED
            metadata.validation_errors = errors
            self._algorithms[algorithm_id] = metadata
            return metadata

        source_file = self.storage_path / f"{algorithm_id}.py"
        with open(source_file, "wb") as f:
            f.write(source_code)

        metadata.source_file = str(source_file)
        metadata.status = AlgorithmStatus.APPROVED
        metadata.updated_at = datetime.now(UTC)

        self._algorithms[algorithm_id] = metadata

        logger.info(
            "algorithm_registered",
            algorithm_id=algorithm_id,
            name=metadata.name,
            author=author_id,
        )

        return metadata

    def get_algorithm(self, algorithm_id: str) -> AlgorithmMetadata | None:
        """Get algorithm metadata."""
        return self._algorithms.get(algorithm_id)

    def list_algorithms(
        self,
        author_id: str | None = None,
        status: AlgorithmStatus | None = None,
        language: AlgorithmLanguage | None = None,
    ) -> list[AlgorithmMetadata]:
        """List algorithms with filters."""
        algorithms = list(self._algorithms.values())

        if author_id:
            algorithms = [a for a in algorithms if a.author_id == author_id]

        if status:
            algorithms = [a for a in algorithms if a.status == status]

        if language:
            algorithms = [a for a in algorithms if a.language == language]

        return sorted(algorithms, key=lambda a: a.created_at, reverse=True)

    def _create_sandboxed_namespace(self) -> dict[str, Any]:
        """Create a restricted namespace for algorithm execution."""
        import math
        import cmath
        
        safe_builtins = {
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "enumerate": enumerate,
            "filter": filter,
            "float": float,
            "frozenset": frozenset,
            "int": int,
            "isinstance": isinstance,
            "len": len,
            "list": list,
            "map": map,
            "max": max,
            "min": min,
            "print": print,
            "range": range,
            "reversed": reversed,
            "round": round,
            "set": set,
            "slice": slice,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "zip": zip,
            "True": True,
            "False": False,
            "None": None,
        }
        
        safe_math = {
            "pi": math.pi,
            "e": math.e,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "exp": math.exp,
            "log": math.log,
            "sqrt": math.sqrt,
            "floor": math.floor,
            "ceil": math.ceil,
            "pow": pow,
        }
        
        return {
            "__builtins__": safe_builtins,
            "math": type('Module', (), safe_math)(),
            "cmath": cmath,
        }

    def execute_algorithm(
        self,
        algorithm_id: str,
        parameters: dict[str, Any],
        user_id: str,
    ) -> dict[str, Any]:
        """Execute a registered algorithm in a sandboxed environment."""
        metadata = self._algorithms.get(algorithm_id)

        if not metadata:
            raise ValueError(f"Algorithm {algorithm_id} not found")

        if metadata.status != AlgorithmStatus.APPROVED:
            raise ValueError(f"Algorithm {algorithm_id} is not approved for execution")

        source_path = Path(metadata.source_file)
        if not source_path.exists():
            raise ValueError(f"Algorithm source file not found: {metadata.source_file}")

        metadata.status = AlgorithmStatus.RUNNING

        try:
            namespace = self._create_sandboxed_namespace()

            with open(source_path) as f:
                source_code = f.read()

            code_obj = compile(source_code, str(source_path), "exec")
            
            for const in code_obj.co_consts:
                if isinstance(const, type(code_obj)):
                    if any(name in const.co_names for name in ('eval', 'exec', 'compile', '__import__', 'open')):
                        raise ValueError("Code contains forbidden operations")

            exec(code_obj, namespace)

            entry_point = namespace.get(metadata.entry_point)
            if not entry_point or not callable(entry_point):
                raise ValueError(f"Entry point '{metadata.entry_point}' not found")

            result = entry_point(**parameters)

            metadata.status = AlgorithmStatus.COMPLETED
            metadata.updated_at = datetime.now(UTC)

            return {
                "algorithm_id": algorithm_id,
                "status": "completed",
                "result": result,
                "executed_at": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            metadata.status = AlgorithmStatus.FAILED
            metadata.validation_errors = [str(e)]
            metadata.updated_at = datetime.now(UTC)

            logger.error(
                "algorithm_execution_failed",
                algorithm_id=algorithm_id,
                error=str(e),
            )

            raise

    def delete_algorithm(self, algorithm_id: str, user_id: str) -> bool:
        """Delete an algorithm."""
        metadata = self._algorithms.get(algorithm_id)

        if not metadata:
            return False

        if metadata.author_id != user_id:
            raise PermissionError("Only the author can delete this algorithm")

        source_path = Path(metadata.source_file)
        if source_path.exists():
            source_path.unlink()

        del self._algorithms[algorithm_id]

        logger.info("algorithm_deleted", algorithm_id=algorithm_id, user=user_id)

        return True


registry = AlgorithmRegistry()

