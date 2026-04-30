"""
Comprehensive input validation and sanitization module.

Provides secure input validation for all API endpoints to prevent
injection attacks, DoS vulnerabilities, and other security issues.
"""

import re
import html
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: str = None, value: Any = None):
        self.message = message
        self.field = field
        self.value = value
        super().__init__(self.message)


class SecurityLevel(Enum):
    """Security levels for validation."""
    STRICT = "strict"
    MODERATE = "moderate"
    LENIENT = "lenient"


class InputValidator:
    """Comprehensive input validator."""
    
    # Common patterns
    SQL_INJECTION_PATTERN = re.compile(
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)|"
        r"(--|;|\/\*|\*\/|'|\"|xp_|sp_)",
        re.IGNORECASE
    )
    
    XSS_PATTERN = re.compile(
        r"<script[^>]*>.*?</script>|"
        r"javascript:|"
        r"on\w+\s*=|"
        r"<iframe|<object|<embed",
        re.IGNORECASE
    )
    
    PATH_TRAVERSAL_PATTERN = re.compile(r"\.\.[\\/]")
    
    COMMAND_INJECTION_PATTERN = re.compile(
        r"[;&|`$(){}[\]<>]|&&|\|\||\|\||>>|<<",
        re.IGNORECASE
    )
    
    # Size limits
    MAX_STRING_LENGTH = 10000
    MAX_JSON_DEPTH = 20
    MAX_ARRAY_LENGTH = 1000
    MAX_DICT_KEYS = 100
    
    # Allowed characters for different fields
    USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,50}$")
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    
    @classmethod
    def validate_string(
        cls,
        value: Any,
        field_name: str = "field",
        max_length: int = MAX_STRING_LENGTH,
        min_length: int = 0,
        pattern: Optional[re.Pattern] = None,
        allow_empty: bool = False,
        sanitize: bool = True,
        security_level: SecurityLevel = SecurityLevel.MODERATE
    ) -> str:
        """Validate and sanitize string input."""
        
        # Check type
        if not isinstance(value, str):
            raise ValidationError(
                f"{field_name} must be a string",
                field=field_name,
                value=value
            )
        
        # Check empty
        if not value and not allow_empty:
            raise ValidationError(
                f"{field_name} cannot be empty",
                field=field_name,
                value=value
            )
        
        # Check length
        if len(value) > max_length:
            raise ValidationError(
                f"{field_name} exceeds maximum length of {max_length}",
                field=field_name,
                value=value
            )
        
        if len(value) < min_length:
            raise ValidationError(
                f"{field_name} must be at least {min_length} characters",
                field=field_name,
                value=value
            )
        
        # Check pattern
        if pattern and not pattern.match(value):
            raise ValidationError(
                f"{field_name} does not match required pattern",
                field=field_name,
                value=value
            )
        
        # Security checks based on level
        if security_level == SecurityLevel.STRICT:
            cls._check_sql_injection(value, field_name)
            cls._check_xss(value, field_name)
            cls._check_command_injection(value, field_name)
        elif security_level == SecurityLevel.MODERATE:
            cls._check_sql_injection(value, field_name)
            cls._check_xss(value, field_name)
        
        # Sanitize if requested
        if sanitize:
            return cls._sanitize_string(value)
        
        return value
    
    @classmethod
    def validate_integer(
        cls,
        value: Any,
        field_name: str = "field",
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        allow_zero: bool = True
    ) -> int:
        """Validate integer input."""
        
        # Try to convert to int
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            raise ValidationError(
                f"{field_name} must be an integer",
                field=field_name,
                value=value
            )
        
        # Check range
        if min_value is not None and int_value < min_value:
            raise ValidationError(
                f"{field_name} must be at least {min_value}",
                field=field_name,
                value=value
            )
        
        if max_value is not None and int_value > max_value:
            raise ValidationError(
                f"{field_name} must be at most {max_value}",
                field=field_name,
                value=value
            )
        
        if not allow_zero and int_value == 0:
            raise ValidationError(
                f"{field_name} cannot be zero",
                field=field_name,
                value=value
            )
        
        return int_value
    
    @classmethod
    def validate_float(
        cls,
        value: Any,
        field_name: str = "field",
        min_value: Optional[float] = None,
        max_value: Optional[float] = None
    ) -> float:
        """Validate float input."""
        
        # Try to convert to float
        try:
            float_value = float(value)
        except (ValueError, TypeError):
            raise ValidationError(
                f"{field_name} must be a number",
                field=field_name,
                value=value
            )
        
        # Check for NaN/Inf
        if not (float_value == float_value):  # NaN check
            raise ValidationError(
                f"{field_name} cannot be NaN",
                field=field_name,
                value=value
            )
        
        if float_value in (float('inf'), float('-inf')):
            raise ValidationError(
                f"{field_name} cannot be infinite",
                field=field_name,
                value=value
            )
        
        # Check range
        if min_value is not None and float_value < min_value:
            raise ValidationError(
                f"{field_name} must be at least {min_value}",
                field=field_name,
                value=value
            )
        
        if max_value is not None and float_value > max_value:
            raise ValidationError(
                f"{field_name} must be at most {max_value}",
                field=field_name,
                value=value
            )
        
        return float_value
    
    @classmethod
    def validate_boolean(cls, value: Any, field_name: str = "field") -> bool:
        """Validate boolean input."""
        
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            if value.lower() in ('true', '1', 'yes', 'on'):
                return True
            if value.lower() in ('false', '0', 'no', 'off'):
                return False
        
        raise ValidationError(
            f"{field_name} must be a boolean",
            field=field_name,
            value=value
        )
    
    @classmethod
    def validate_list(
        cls,
        value: Any,
        field_name: str = "field",
        max_length: int = MAX_ARRAY_LENGTH,
        item_validator: Optional[callable] = None,
        allow_empty: bool = True
    ) -> List[Any]:
        """Validate list input."""
        
        # Check type
        if not isinstance(value, (list, tuple)):
            raise ValidationError(
                f"{field_name} must be a list",
                field=field_name,
                value=value
            )
        
        # Check empty
        if not value and not allow_empty:
            raise ValidationError(
                f"{field_name} cannot be empty",
                field=field_name,
                value=value
            )
        
        # Check length
        if len(value) > max_length:
            raise ValidationError(
                f"{field_name} exceeds maximum length of {max_length}",
                field=field_name,
                value=value
            )
        
        # Validate items if validator provided
        if item_validator:
            validated_items = []
            for i, item in enumerate(value):
                try:
                    validated_item = item_validator(item, f"{field_name}[{i}]")
                    validated_items.append(validated_item)
                except ValidationError as e:
                    raise ValidationError(
                        f"{field_name}[{i}]: {e.message}",
                        field=f"{field_name}[{i}]",
                        value=item
                    )
            return validated_items
        
        return list(value)
    
    @classmethod
    def validate_dict(
        cls,
        value: Any,
        field_name: str = "field",
        max_keys: int = MAX_DICT_KEYS,
        key_validator: Optional[callable] = None,
        value_validator: Optional[callable] = None,
        allow_empty: bool = True
    ) -> Dict[str, Any]:
        """Validate dictionary input."""
        
        # Check type
        if not isinstance(value, dict):
            raise ValidationError(
                f"{field_name} must be a dictionary",
                field=field_name,
                value=value
            )
        
        # Check empty
        if not value and not allow_empty:
            raise ValidationError(
                f"{field_name} cannot be empty",
                field=field_name,
                value=value
            )
        
        # Check number of keys
        if len(value) > max_keys:
            raise ValidationError(
                f"{field_name} exceeds maximum number of keys ({max_keys})",
                field=field_name,
                value=value
            )
        
        # Validate keys and values if validators provided
        validated_dict = {}
        for key, val in value.items():
            # Validate key
            if key_validator:
                try:
                    validated_key = key_validator(key, f"{field_name}.{key}")
                except ValidationError as e:
                    raise ValidationError(
                        f"{field_name} key '{key}': {e.message}",
                        field=f"{field_name}.{key}",
                        value=key
                    )
            else:
                validated_key = key
            
            # Validate value
            if value_validator:
                try:
                    validated_value = value_validator(val, f"{field_name}.{key}")
                except ValidationError as e:
                    raise ValidationError(
                        f"{field_name}['{key}']: {e.message}",
                        field=f"{field_name}.{key}",
                        value=val
                    )
            else:
                validated_value = val
            
            validated_dict[validated_key] = validated_value
        
        return validated_dict
    
    @classmethod
    def validate_uuid(cls, value: Any, field_name: str = "field") -> str:
        """Validate UUID string."""
        return cls.validate_string(
            value,
            field_name=field_name,
            pattern=cls.UUID_PATTERN,
            security_level=SecurityLevel.LENIENT
        )
    
    @classmethod
    def validate_email(cls, value: Any, field_name: str = "field") -> str:
        """Validate email address."""
        return cls.validate_string(
            value,
            field_name=field_name,
            pattern=cls.EMAIL_PATTERN,
            security_level=SecurityLevel.LENIENT
        )
    
    @classmethod
    def validate_username(cls, value: Any, field_name: str = "field") -> str:
        """Validate username."""
        return cls.validate_string(
            value,
            field_name=field_name,
            pattern=cls.USERNAME_PATTERN,
            security_level=SecurityLevel.LENIENT
        )
    
    @classmethod
    def validate_datetime(
        cls,
        value: Any,
        field_name: str = "field",
        format_string: str = "%Y-%m-%dT%H:%M:%S.%fZ"
    ) -> datetime:
        """Validate datetime string."""
        
        if isinstance(value, datetime):
            return value
        
        if not isinstance(value, str):
            raise ValidationError(
                f"{field_name} must be a datetime string",
                field=field_name,
                value=value
            )
        
        try:
            return datetime.strptime(value, format_string)
        except ValueError:
            try:
                # Try ISO format
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                raise ValidationError(
                    f"{field_name} must be a valid datetime",
                    field=field_name,
                    value=value
                )
    
    @classmethod
    def validate_json(
        cls,
        value: Any,
        field_name: str = "field",
        max_depth: int = MAX_JSON_DEPTH
    ) -> Dict[str, Any]:
        """Validate JSON structure."""
        
        if not isinstance(value, dict):
            raise ValidationError(
                f"{field_name} must be a JSON object",
                field=field_name,
                value=value
            )
        
        # Check depth
        def check_depth(obj, current_depth=0):
            if current_depth > max_depth:
                raise ValidationError(
                    f"{field_name} exceeds maximum depth of {max_depth}",
                    field=field_name,
                    value=value
                )
            
            if isinstance(obj, dict):
                for v in obj.values():
                    check_depth(v, current_depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    check_depth(item, current_depth + 1)
        
        check_depth(value)
        
        return value
    
    @classmethod
    def _check_sql_injection(cls, value: str, field_name: str):
        """Check for SQL injection patterns."""
        if cls.SQL_INJECTION_PATTERN.search(value):
            logger.warning(f"SQL injection attempt detected in {field_name}: {value[:100]}")
            raise ValidationError(
                f"{field_name} contains potentially malicious content",
                field=field_name,
                value=value
            )
    
    @classmethod
    def _check_xss(cls, value: str, field_name: str):
        """Check for XSS patterns."""
        if cls.XSS_PATTERN.search(value):
            logger.warning(f"XSS attempt detected in {field_name}: {value[:100]}")
            raise ValidationError(
                f"{field_name} contains potentially malicious content",
                field=field_name,
                value=value
            )
    
    @classmethod
    def _check_command_injection(cls, value: str, field_name: str):
        """Check for command injection patterns."""
        if cls.COMMAND_INJECTION_PATTERN.search(value):
            logger.warning(f"Command injection attempt detected in {field_name}: {value[:100]}")
            raise ValidationError(
                f"{field_name} contains potentially malicious content",
                field=field_name,
                value=value
            )
    
    @classmethod
    def _sanitize_string(cls, value: str) -> str:
        """Sanitize string by escaping HTML entities."""
        return html.escape(value, quote=True)


class QuantumJobValidator:
    """Validator for quantum optimization job submissions."""
    
    ALLOWED_PROBLEM_TYPES = {"QAOA", "VQE", "ANNEALING"}
    ALLOWED_BACKENDS = {
        "local_simulator",
        "advanced_simulator",
        "ibm_quantum",
        "aws_braket",
        "azure_quantum",
        "dwave"
    }
    ALLOWED_OPTIMIZERS = {
        "COBYLA",
        "SPSA",
        "SLSQP",
        "Nelder-Mead",
        "BFGS",
        "L-BFGS-B",
        "TNC"
    }
    
    @classmethod
    def validate_problem_type(cls, value: Any) -> str:
        """Validate problem type."""
        problem_type = InputValidator.validate_string(
            value,
            field_name="problem_type",
            max_length=50
        ).upper()
        
        if problem_type not in cls.ALLOWED_PROBLEM_TYPES:
            raise ValidationError(
                f"Invalid problem type. Must be one of: {', '.join(cls.ALLOWED_PROBLEM_TYPES)}",
                field="problem_type",
                value=value
            )
        
        return problem_type
    
    @classmethod
    def validate_backend(cls, value: Any) -> str:
        """Validate backend selection."""
        backend = InputValidator.validate_string(
            value,
            field_name="backend",
            max_length=100
        ).lower()
        
        if backend not in cls.ALLOWED_BACKENDS:
            raise ValidationError(
                f"Invalid backend. Must be one of: {', '.join(cls.ALLOWED_BACKENDS)}",
                field="backend",
                value=value
            )
        
        return backend
    
    @classmethod
    def validate_optimizer(cls, value: Any) -> str:
        """Validate optimizer selection."""
        optimizer = InputValidator.validate_string(
            value,
            field_name="optimizer",
            max_length=50
        ).upper()
        
        if optimizer not in cls.ALLOWED_OPTIMIZERS:
            raise ValidationError(
                f"Invalid optimizer. Must be one of: {', '.join(cls.ALLOWED_OPTIMIZERS)}",
                field="optimizer",
                value=value
            )
        
        return optimizer
    
    @classmethod
    def validate_layers(cls, value: Any) -> int:
        """Validate QAOA layers parameter."""
        return InputValidator.validate_integer(
            value,
            field_name="layers",
            min_value=1,
            max_value=20
        )
    
    @classmethod
    def validate_shots(cls, value: Any) -> int:
        """Validate shots parameter."""
        return InputValidator.validate_integer(
            value,
            field_name="shots",
            min_value=1,
            max_value=100000
        )
    
    @classmethod
    def validate_priority(cls, value: Any) -> int:
        """Validate job priority."""
        if isinstance(value, str):
            priority_map = {"low": 3, "normal": 5, "high": 8, "urgent": 10}
            priority = priority_map.get(value.lower(), 5)
        else:
            priority = InputValidator.validate_integer(
                value,
                field_name="priority",
                min_value=1,
                max_value=10
            )
        
        return priority
    
    @classmethod
    def validate_graph_edges(cls, value: Any) -> List[tuple]:
        """Validate graph edges for MaxCut problem."""
        edges = InputValidator.validate_list(
            value,
            field_name="edges",
            max_length=1000,
            allow_empty=False
        )
        
        validated_edges = []
        for i, edge in enumerate(edges):
            if not isinstance(edge, (list, tuple)) or len(edge) < 2:
                raise ValidationError(
                    f"Edge {i} must be a list/tuple with at least 2 elements",
                    field="edges",
                    value=edge
                )
            
            try:
                node1 = int(edge[0])
                node2 = int(edge[1])
                weight = float(edge[2]) if len(edge) > 2 else 1.0
                
                if node1 < 0 or node2 < 0:
                    raise ValidationError(
                        f"Edge {i}: Node indices must be non-negative",
                        field="edges",
                        value=edge
                    )
                
                validated_edges.append((node1, node2, weight))
            except (ValueError, TypeError) as e:
                raise ValidationError(
                    f"Edge {i}: Invalid edge format - {e}",
                    field="edges",
                    value=edge
                )
        
        return validated_edges
    
    @classmethod
    def validate_qubo_matrix(cls, value: Any) -> Dict[tuple, float]:
        """Validate QUBO matrix for annealing problems."""
        if isinstance(value, dict):
            # Already in dict format
            validated_matrix = {}
            for key, val in value.items():
                if isinstance(key, str):
                    # Parse string tuple like "(0, 1)" or "0,1"
                    key = key.strip("()[] ")
                    parts = [int(x.strip()) for x in key.split(",")]
                    if len(parts) != 2:
                        raise ValidationError(
                            f"Invalid QUBO key format: {key}",
                            field="qubo_matrix",
                            value=key
                        )
                    key_tuple = tuple(parts)
                elif isinstance(key, (list, tuple)) and len(key) == 2:
                    key_tuple = (int(key[0]), int(key[1]))
                else:
                    raise ValidationError(
                        f"Invalid QUBO key: {key}",
                        field="qubo_matrix",
                        value=key
                    )
                
                try:
                    validated_matrix[key_tuple] = float(val)
                except (ValueError, TypeError):
                    raise ValidationError(
                        f"Invalid QUBO value: {val}",
                        field="qubo_matrix",
                        value=val
                    )
            
            return validated_matrix
        
        elif isinstance(value, list):
            # Convert from list format
            if not value:
                raise ValidationError(
                    "QUBO matrix cannot be empty",
                    field="qubo_matrix",
                    value=value
                )
            
            # Check if it's a 2D matrix
            if isinstance(value[0], list):
                # Validate square matrix
                size = len(value)
                for row in value:
                    if len(row) != size:
                        raise ValidationError(
                            "QUBO matrix must be square",
                            field="qubo_matrix",
                            value=value
                        )
                
                # Convert to dict format
                matrix_dict = {}
                for i in range(size):
                    for j in range(i, size):
                        val = float(value[i][j])
                        if val != 0:
                            matrix_dict[(i, j)] = val
                
                return matrix_dict
            
            else:
                # Edge list format: [[i, j, weight], ...]
                validated_matrix = {}
                for item in value:
                    if not isinstance(item, (list, tuple)) or len(item) < 2:
                        raise ValidationError(
                            f"Invalid QUBO edge format: {item}",
                            field="qubo_matrix",
                            value=item
                        )
                    
                    try:
                        i = int(item[0])
                        j = int(item[1])
                        weight = float(item[2]) if len(item) > 2 else 1.0
                        
                        if i <= j:
                            validated_matrix[(i, j)] = weight
                        else:
                            validated_matrix[(j, i)] = weight
                    except (ValueError, TypeError) as e:
                        raise ValidationError(
                            f"Invalid QUBO edge: {e}",
                            field="qubo_matrix",
                            value=item
                        )
                
                return validated_matrix
        
        else:
            raise ValidationError(
                "QUBO matrix must be a dict or list",
                field="qubo_matrix",
                value=value
            )
    
    @classmethod
    def validate_job_submission(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate complete job submission."""
        validated = {}
        
        # Validate problem type
        validated["problem_type"] = cls.validate_problem_type(data.get("problem_type"))
        
        # Validate backend
        validated["backend"] = cls.validate_backend(data.get("backend", "local_simulator"))
        
        # Validate problem config
        problem_config = data.get("problem_config", {})
        if not isinstance(problem_config, dict):
            raise ValidationError(
                "problem_config must be a dictionary",
                field="problem_config",
                value=problem_config
            )
        
        validated["problem_config"] = problem_config
        
        # Validate parameters
        parameters = data.get("parameters", {})
        if not isinstance(parameters, dict):
            raise ValidationError(
                "parameters must be a dictionary",
                field="parameters",
                value=parameters
            )
        
        validated_parameters = {}
        if "layers" in parameters:
            validated_parameters["layers"] = cls.validate_layers(parameters["layers"])
        if "shots" in parameters:
            validated_parameters["shots"] = cls.validate_shots(parameters["shots"])
        if "optimizer" in parameters:
            validated_parameters["optimizer"] = cls.validate_optimizer(parameters["optimizer"])
        
        validated["parameters"] = validated_parameters
        
        # Validate priority
        validated["priority"] = cls.validate_priority(data.get("priority", 5))
        
        # Validate callback URL if provided
        if "callback_url" in data and data["callback_url"]:
            validated["callback_url"] = InputValidator.validate_string(
                data["callback_url"],
                field_name="callback_url",
                max_length=500,
                security_level=SecurityLevel.LENIENT
            )
        
        # Validate encryption flags
        validated["encrypt_result"] = InputValidator.validate_boolean(
            data.get("encrypt_result", False),
            field_name="encrypt_result"
        )
        
        return validated