"""Input validation utilities and canonicalization functions."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from re import Pattern
from typing import Any, TypeVar

T = TypeVar("T")

PatternType = Pattern[str]


class ValidationError(Exception):
    """Base exception for validation errors."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any | None = None,
        constraint: str | None = None,
    ):
        super().__init__(message)
        self.field = field
        self.value = value
        self.constraint = constraint


class ValidationErrors(ValidationError):
    """Collection of multiple validation errors."""

    def __init__(self, errors: list[ValidationError]):
        messages = [str(e) for e in errors]
        super().__init__("; ".join(messages))
        self.errors = errors


class SizeLimitError(ValidationError):
    """Raised when size limits are exceeded."""

    def __init__(
        self,
        message: str,
        actual_size: int,
        max_size: int,
        field: str | None = None,
    ):
        super().__init__(message, field)
        self.actual_size = actual_size
        self.max_size = max_size


class ComplexityError(ValidationError):
    """Raised when complexity limits are exceeded."""

    pass


@dataclass
class SizeLimits:
    """Size limit configuration."""

    max_string_length: int = 10_000
    max_bytes_length: int = 10 * 1024 * 1024  # 10MB
    max_list_length: int = 1_000
    max_dict_size: int = 1_000
    max_nesting_depth: int = 20
    max_key_size: int = 8192  # 8KB for cryptographic keys
    max_message_size: int = 100 * 1024 * 1024  # 100MB


DEFAULT_LIMITS = SizeLimits()


@dataclass
class ComplexityLimits:
    """Complexity limit configuration."""

    max_recursion_depth: int = 50
    max_iterations: int = 1_000_000
    max_regex_length: int = 1_000
    max_regex_groups: int = 100


DEFAULT_COMPLEXITY = ComplexityLimits()


def check_size_limits(
    value: Any,
    limits: SizeLimits | None = None,
    field: str | None = None,
) -> None:
    """
    Check value against size limits.

    Args:
        value: Value to check
        limits: Size limits to apply
        field: Field name for error messages

    Raises:
        SizeLimitError: If size limits are exceeded
    """
    if limits is None:
        limits = DEFAULT_LIMITS

    if isinstance(value, str):
        if len(value) > limits.max_string_length:
            raise SizeLimitError(
                f"String length {len(value)} exceeds maximum {limits.max_string_length}",
                actual_size=len(value),
                max_size=limits.max_string_length,
                field=field,
            )

    elif isinstance(value, (bytes, bytearray)):
        if len(value) > limits.max_bytes_length:
            raise SizeLimitError(
                f"Bytes length {len(value)} exceeds maximum {limits.max_bytes_length}",
                actual_size=len(value),
                max_size=limits.max_bytes_length,
                field=field,
            )

    elif isinstance(value, (list, tuple)):
        if len(value) > limits.max_list_length:
            raise SizeLimitError(
                f"List length {len(value)} exceeds maximum {limits.max_list_length}",
                actual_size=len(value),
                max_size=limits.max_list_length,
                field=field,
            )

    elif isinstance(value, dict):
        if len(value) > limits.max_dict_size:
            raise SizeLimitError(
                f"Dict size {len(value)} exceeds maximum {limits.max_dict_size}",
                actual_size=len(value),
                max_size=limits.max_dict_size,
                field=field,
            )


def check_nesting_depth(
    value: Any,
    max_depth: int = 20,
    current_depth: int = 0,
    field: str | None = None,
) -> None:
    """
    Check nesting depth of a data structure.

    Args:
        value: Value to check
        max_depth: Maximum allowed nesting depth
        current_depth: Current depth (used recursively)
        field: Field name for error messages

    Raises:
        ComplexityError: If nesting is too deep
    """
    if current_depth > max_depth:
        raise ComplexityError(
            f"Nesting depth {current_depth} exceeds maximum {max_depth}",
            field=field,
        )

    if isinstance(value, dict):
        for v in value.values():
            check_nesting_depth(v, max_depth, current_depth + 1, field)
    elif isinstance(value, (list, tuple)):
        for v in value:
            check_nesting_depth(v, max_depth, current_depth + 1, field)


def check_complexity(
    value: Any,
    limits: ComplexityLimits | None = None,
    field: str | None = None,
) -> None:
    """
    Check value against complexity limits.

    Args:
        value: Value to check
        limits: Complexity limits to apply
        field: Field name for error messages

    Raises:
        ComplexityError: If complexity limits are exceeded
    """
    if limits is None:
        limits = DEFAULT_COMPLEXITY

    check_nesting_depth(value, limits.max_recursion_depth, 0, field)


class NormalizationForm(Enum):
    """Unicode normalization forms."""

    NFC = "NFC"
    NFD = "NFD"
    NFKC = "NFKC"
    NFKD = "NFKD"


def canonicalize_string(
    value: str,
    form: NormalizationForm = NormalizationForm.NFC,
    strip: bool = True,
    lowercase: bool = False,
    remove_control_chars: bool = True,
) -> str:
    """
    Canonicalize a string for consistent comparison.

    Args:
        value: String to canonicalize
        form: Unicode normalization form
        strip: Whether to strip whitespace
        lowercase: Whether to convert to lowercase
        remove_control_chars: Whether to remove control characters

    Returns:
        Canonicalized string
    """
    result = unicodedata.normalize(form.value, value)

    if remove_control_chars:
        result = "".join(
            char for char in result if unicodedata.category(char) != "Cc" or char in "\n\r\t"
        )

    if strip:
        result = result.strip()

    if lowercase:
        result = result.lower()

    return result


def canonicalize_bytes(value: bytes) -> bytes:
    """
    Canonicalize bytes for consistent handling.

    Args:
        value: Bytes to canonicalize

    Returns:
        Canonicalized bytes
    """
    return bytes(value)


def canonicalize_dict(
    value: dict[str, Any],
    sort_keys: bool = True,
    normalize_strings: bool = True,
) -> dict[str, Any]:
    """
    Canonicalize a dictionary for consistent serialization.

    Args:
        value: Dictionary to canonicalize
        sort_keys: Whether to sort keys
        normalize_strings: Whether to normalize string values

    Returns:
        Canonicalized dictionary
    """

    def canonicalize_value(v: Any) -> Any:
        if isinstance(v, str):
            return canonicalize_string(v) if normalize_strings else v
        elif isinstance(v, dict):
            return canonicalize_dict(v, sort_keys, normalize_strings)
        elif isinstance(v, list):
            return [canonicalize_value(item) for item in v]
        return v

    result = {k: canonicalize_value(v) for k, v in value.items()}

    if sort_keys:
        result = dict(sorted(result.items()))

    return result


def canonicalize(
    value: Any,
    form: NormalizationForm = NormalizationForm.NFC,
) -> Any:
    """
    Canonicalize a value of any supported type.

    Args:
        value: Value to canonicalize
        form: Unicode normalization form for strings

    Returns:
        Canonicalized value
    """
    if isinstance(value, str):
        return canonicalize_string(value, form)
    elif isinstance(value, bytes):
        return canonicalize_bytes(value)
    elif isinstance(value, dict):
        return canonicalize_dict(value)
    elif isinstance(value, list):
        return [canonicalize(item, form) for item in value]
    elif isinstance(value, tuple):
        return tuple(canonicalize(item, form) for item in value)
    return value


@dataclass
class Validator:
    """Validator for a specific type or constraint."""

    name: str
    validate_fn: Callable[[Any], bool]
    error_message: str

    def validate(self, value: Any, field: str | None = None) -> None:
        if not self.validate_fn(value):
            raise ValidationError(
                self.error_message,
                field=field,
                value=value,
                constraint=self.name,
            )


IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
BASE64_PATTERN = re.compile(r"^[A-Za-z0-9+/]*={0,2}$")
HEX_PATTERN = re.compile(r"^[0-9a-fA-F]+$")
ALGORITHM_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def is_valid_identifier(value: str) -> bool:
    """Check if value is a valid identifier."""
    return bool(IDENTIFIER_PATTERN.match(value))


def is_valid_uuid(value: str) -> bool:
    """Check if value is a valid UUID."""
    return bool(UUID_PATTERN.match(value))


def is_valid_base64(value: str) -> bool:
    """Check if value is valid base64."""
    if len(value) % 4 != 0:
        return False
    return bool(BASE64_PATTERN.match(value))


def is_valid_hex(value: str) -> bool:
    """Check if value is valid hexadecimal."""
    return bool(HEX_PATTERN.match(value))


def is_valid_algorithm_name(value: str) -> bool:
    """Check if value is a valid algorithm name."""
    return bool(ALGORITHM_PATTERN.match(value)) and len(value) <= 64


VALIDATORS = {
    "identifier": Validator(
        "identifier",
        is_valid_identifier,
        "Value must be a valid identifier",
    ),
    "uuid": Validator(
        "uuid",
        is_valid_uuid,
        "Value must be a valid UUID",
    ),
    "base64": Validator(
        "base64",
        is_valid_base64,
        "Value must be valid base64",
    ),
    "hex": Validator(
        "hex",
        is_valid_hex,
        "Value must be valid hexadecimal",
    ),
    "algorithm": Validator(
        "algorithm",
        is_valid_algorithm_name,
        "Value must be a valid algorithm name",
    ),
}


def validate_input(
    value: Any,
    validators: list[str],
    field: str | None = None,
    limits: SizeLimits | None = None,
) -> Any:
    """
    Validate input against multiple validators.

    Args:
        value: Value to validate
        validators: List of validator names to apply
        field: Field name for error messages
        limits: Size limits to apply

    Returns:
        The validated value

    Raises:
        ValidationError: If validation fails
    """
    check_size_limits(value, limits, field)

    errors = []
    for validator_name in validators:
        validator = VALIDATORS.get(validator_name)
        if validator:
            try:
                validator.validate(value, field)
            except ValidationError as e:
                errors.append(e)

    if errors:
        if len(errors) == 1:
            raise errors[0]
        raise ValidationErrors(errors)

    return value


@dataclass
class InputSchema:
    """Schema for validating structured input."""

    fields: dict[str, FieldSpec] = field(default_factory=dict)

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate data against the schema.

        Args:
            data: Data to validate

        Returns:
            Validated and canonicalized data

        Raises:
            ValidationErrors: If validation fails
        """
        errors = []
        result = {}

        for field_name, spec in self.fields.items():
            if field_name not in data:
                if spec.required:
                    errors.append(
                        ValidationError(
                            f"Missing required field: {field_name}",
                            field=field_name,
                        )
                    )
                elif spec.default is not None:
                    result[field_name] = spec.default
                continue

            value = data[field_name]

            try:
                value = spec.validate(value, field_name)
                result[field_name] = value
            except ValidationError as e:
                errors.append(e)

        for field_name in data:
            if field_name not in self.fields:
                errors.append(
                    ValidationError(
                        f"Unknown field: {field_name}",
                        field=field_name,
                    )
                )

        if errors:
            raise ValidationErrors(errors)

        return result


@dataclass
class FieldSpec:
    """Specification for a single field."""

    field_type: type
    required: bool = True
    default: Any = None
    validators: list[str] = field(default_factory=list)
    min_length: int | None = None
    max_length: int | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None
    pattern: PatternType | None = None
    allowed_values: list[Any] | None = None

    def validate(self, value: Any, field_name: str) -> Any:
        """Validate a single value."""
        if not isinstance(value, self.field_type):
            raise ValidationError(
                f"Expected {self.field_type.__name__}, got {type(value).__name__}",
                field=field_name,
                value=value,
            )

        if isinstance(value, str):
            value = canonicalize_string(value)

            if self.min_length is not None and len(value) < self.min_length:
                raise ValidationError(
                    f"Length {len(value)} is less than minimum {self.min_length}",
                    field=field_name,
                    value=value,
                )

            if self.max_length is not None and len(value) > self.max_length:
                raise ValidationError(
                    f"Length {len(value)} exceeds maximum {self.max_length}",
                    field=field_name,
                    value=value,
                )

            if self.pattern is not None and not self.pattern.match(value):
                raise ValidationError(
                    "Value does not match required pattern",
                    field=field_name,
                    value=value,
                )

        if isinstance(value, (int, float)):
            if self.min_value is not None and value < self.min_value:
                raise ValidationError(
                    f"Value {value} is less than minimum {self.min_value}",
                    field=field_name,
                    value=value,
                )

            if self.max_value is not None and value > self.max_value:
                raise ValidationError(
                    f"Value {value} exceeds maximum {self.max_value}",
                    field=field_name,
                    value=value,
                )

        if self.allowed_values is not None and value not in self.allowed_values:
            raise ValidationError(
                f"Value not in allowed values: {self.allowed_values}",
                field=field_name,
                value=value,
            )

        for validator_name in self.validators:
            validator = VALIDATORS.get(validator_name)
            if validator:
                validator.validate(value, field_name)

        return value
