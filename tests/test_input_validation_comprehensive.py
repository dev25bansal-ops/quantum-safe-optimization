"""
Comprehensive unit tests for input validation module.

Tests cover all validation scenarios including:
- String validation with security checks
- Integer and float validation
- List and dictionary validation
- Quantum job validation
- Security pattern detection
"""

import pytest
import re
from api.security.input_validation import (
    InputValidator,
    QuantumJobValidator,
    SecurityLevel,
    ValidationError,
)


class TestStringValidation:
    """Test string input validation."""

    def test_valid_string(self):
        """Test valid string passes validation."""
        result = InputValidator.validate_string(
            "test_value",
            field_name="test_field",
            max_length=100
        )
        assert result == "test_value"

    def test_string_with_min_length(self):
        """Test string with minimum length requirement."""
        result = InputValidator.validate_string(
            "hello",
            field_name="test_field",
            min_length=3
        )
        assert result == "hello"

    def test_string_too_short(self):
        """Test string shorter than minimum raises error."""
        with pytest.raises(ValidationError) as exc_info:
            InputValidator.validate_string(
                "hi",
                field_name="test_field",
                min_length=5
            )
        assert "must be at least" in str(exc_info.value.message)

    def test_string_too_long(self):
        """Test string longer than maximum raises error."""
        with pytest.raises(ValidationError) as exc_info:
            InputValidator.validate_string(
                "a" * 101,
                field_name="test_field",
                max_length=100
            )
        assert "exceeds maximum length" in str(exc_info.value.message)

    def test_empty_string_not_allowed(self):
        """Test empty string raises error when not allowed."""
        with pytest.raises(ValidationError):
            InputValidator.validate_string(
                "",
                field_name="test_field",
                allow_empty=False
            )

    def test_empty_string_allowed(self):
        """Test empty string passes when allowed."""
        result = InputValidator.validate_string(
            "",
            field_name="test_field",
            allow_empty=True
        )
        assert result == ""

    def test_pattern_matching_valid(self):
        """Test valid string matches pattern."""
        pattern = re.compile(r"^[a-z]+$")
        result = InputValidator.validate_string(
            "hello",
            field_name="test_field",
            pattern=pattern
        )
        assert result == "hello"

    def test_pattern_matching_invalid(self):
        """Test invalid string fails pattern match."""
        pattern = re.compile(r"^[a-z]+$")
        with pytest.raises(ValidationError):
            InputValidator.validate_string(
                "Hello123",
                field_name="test_field",
                pattern=pattern
            )

    def test_sql_injection_detection_strict(self):
        """Test SQL injection pattern detection in strict mode."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1 OR 1=1",
            "SELECT * FROM users",
            "UNION SELECT password FROM users",
        ]

        for malicious in malicious_inputs:
            with pytest.raises(ValidationError) as exc_info:
                InputValidator.validate_string(
                    malicious,
                    field_name="test_field",
                    security_level=SecurityLevel.STRICT
                )
            assert "malicious" in str(exc_info.value.message).lower()

    def test_xss_detection_strict(self):
        """Test XSS pattern detection in strict mode."""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            "<img onerror='alert(1)' src=x>",
            "<iframe src='http://evil.com'></iframe>",
        ]

        for malicious in malicious_inputs:
            with pytest.raises(ValidationError) as exc_info:
                InputValidator.validate_string(
                    malicious,
                    field_name="test_field",
                    security_level=SecurityLevel.STRICT
                )
            assert "malicious" in str(exc_info.value.message).lower()

    def test_command_injection_detection(self):
        """Test command injection pattern detection."""
        malicious_inputs = [
            "test; rm -rf /",
            "test && cat /etc/passwd",
            "test | ls -la",
            "test `whoami`",
            "test $(cat /etc/passwd)",
        ]

        for malicious in malicious_inputs:
            with pytest.raises(ValidationError) as exc_info:
                InputValidator.validate_string(
                    malicious,
                    field_name="test_field",
                    security_level=SecurityLevel.STRICT
                )
            assert "malicious" in str(exc_info.value.message).lower()

    def test_sanitization(self):
        """Test string sanitization escapes HTML."""
        result = InputValidator.validate_string(
            "<script>alert('xss')</script>",
            field_name="test_field",
            sanitize=True,
            security_level=SecurityLevel.LENIENT
        )
        assert "&lt;" in result or "&gt;" in result


class TestIntegerValidation:
    """Test integer input validation."""

    def test_valid_integer(self):
        """Test valid integer passes validation."""
        result = InputValidator.validate_integer(
            42,
            field_name="test_field"
        )
        assert result == 42

    def test_string_to_integer(self):
        """Test string conversion to integer."""
        result = InputValidator.validate_integer(
            "42",
            field_name="test_field"
        )
        assert result == 42

    def test_integer_min_value(self):
        """Test integer minimum value validation."""
        result = InputValidator.validate_integer(
            5,
            field_name="test_field",
            min_value=0,
            max_value=10
        )
        assert result == 5

    def test_integer_max_value(self):
        """Test integer maximum value validation."""
        with pytest.raises(ValidationError):
            InputValidator.validate_integer(
                15,
                field_name="test_field",
                max_value=10
            )

    def test_integer_below_min(self):
        """Test integer below minimum raises error."""
        with pytest.raises(ValidationError):
            InputValidator.validate_integer(
                -5,
                field_name="test_field",
                min_value=0
            )

    def test_zero_allowed(self):
        """Test zero is allowed when permitted."""
        result = InputValidator.validate_integer(
            0,
            field_name="test_field",
            allow_zero=True
        )
        assert result == 0

    def test_zero_not_allowed(self):
        """Test zero raises error when not allowed."""
        with pytest.raises(ValidationError):
            InputValidator.validate_integer(
                0,
                field_name="test_field",
                allow_zero=False
            )

    def test_invalid_integer_type(self):
        """Test non-integer type raises error."""
        with pytest.raises(ValidationError):
            InputValidator.validate_integer(
                "not_a_number",
                field_name="test_field"
            )


class TestFloatValidation:
    """Test float input validation."""

    def test_valid_float(self):
        """Test valid float passes validation."""
        result = InputValidator.validate_float(
            3.14,
            field_name="test_field"
        )
        assert result == 3.14

    def test_string_to_float(self):
        """Test string conversion to float."""
        result = InputValidator.validate_float(
            "3.14",
            field_name="test_field"
        )
        assert result == 3.14

    def test_float_range(self):
        """Test float within range."""
        result = InputValidator.validate_float(
            5.5,
            field_name="test_field",
            min_value=0.0,
            max_value=10.0
        )
        assert result == 5.5

    def test_float_below_min(self):
        """Test float below minimum raises error."""
        with pytest.raises(ValidationError):
            InputValidator.validate_float(
                -1.5,
                field_name="test_field",
                min_value=0.0
            )

    def test_float_above_max(self):
        """Test float above maximum raises error."""
        with pytest.raises(ValidationError):
            InputValidator.validate_float(
                15.5,
                field_name="test_field",
                max_value=10.0
            )

    def test_nan_rejected(self):
        """Test NaN value raises error."""
        with pytest.raises(ValidationError):
            InputValidator.validate_float(
                float('nan'),
                field_name="test_field"
            )

    def test_infinity_rejected(self):
        """Test infinity value raises error."""
        with pytest.raises(ValidationError):
            InputValidator.validate_float(
                float('inf'),
                field_name="test_field"
            )


class TestBooleanValidation:
    """Test boolean input validation."""

    def test_valid_boolean_true(self):
        """Test boolean True passes."""
        result = InputValidator.validate_boolean(True, "test_field")
        assert result is True

    def test_valid_boolean_false(self):
        """Test boolean False passes."""
        result = InputValidator.validate_boolean(False, "test_field")
        assert result is False

    def test_string_true_variants(self):
        """Test string variants of true."""
        for true_val in ['true', 'True', 'TRUE', '1', 'yes', 'on']:
            result = InputValidator.validate_boolean(true_val, "test_field")
            assert result is True

    def test_string_false_variants(self):
        """Test string variants of false."""
        for false_val in ['false', 'False', 'FALSE', '0', 'no', 'off']:
            result = InputValidator.validate_boolean(false_val, "test_field")
            assert result is False

    def test_invalid_boolean(self):
        """Test invalid boolean raises error."""
        with pytest.raises(ValidationError):
            InputValidator.validate_boolean("maybe", "test_field")


class TestListValidation:
    """Test list input validation."""

    def test_valid_list(self):
        """Test valid list passes validation."""
        result = InputValidator.validate_list(
            [1, 2, 3],
            field_name="test_field"
        )
        assert result == [1, 2, 3]

    def test_empty_list_allowed(self):
        """Test empty list when allowed."""
        result = InputValidator.validate_list(
            [],
            field_name="test_field",
            allow_empty=True
        )
        assert result == []

    def test_empty_list_not_allowed(self):
        """Test empty list raises error when not allowed."""
        with pytest.raises(ValidationError):
            InputValidator.validate_list(
                [],
                field_name="test_field",
                allow_empty=False
            )

    def test_list_exceeds_max_length(self):
        """Test list exceeding max length raises error."""
        with pytest.raises(ValidationError):
            InputValidator.validate_list(
                list(range(1001)),
                field_name="test_field",
                max_length=1000
            )

    def test_list_with_item_validator(self):
        """Test list with item validation."""
        def int_validator(value, field):
            return InputValidator.validate_integer(value, field_name=field)

        result = InputValidator.validate_list(
            [1, 2, 3],
            field_name="test_field",
            item_validator=int_validator
        )
        assert result == [1, 2, 3]

    def test_list_with_invalid_item(self):
        """Test list with invalid item raises error."""
        def int_validator(value, field):
            return InputValidator.validate_integer(value, field_name=field)

        with pytest.raises(ValidationError):
            InputValidator.validate_list(
                [1, "not_int", 3],
                field_name="test_field",
                item_validator=int_validator
            )


class TestDictValidation:
    """Test dictionary input validation."""

    def test_valid_dict(self):
        """Test valid dictionary passes validation."""
        result = InputValidator.validate_dict(
            {"key1": "value1", "key2": "value2"},
            field_name="test_field"
        )
        assert len(result) == 2

    def test_empty_dict_allowed(self):
        """Test empty dictionary when allowed."""
        result = InputValidator.validate_dict(
            {},
            field_name="test_field",
            allow_empty=True
        )
        assert result == {}

    def test_dict_exceeds_max_keys(self):
        """Test dictionary exceeding max keys raises error."""
        large_dict = {f"key{i}": f"value{i}" for i in range(101)}
        with pytest.raises(ValidationError):
            InputValidator.validate_dict(
                large_dict,
                field_name="test_field",
                max_keys=100
            )

    def test_dict_with_validators(self):
        """Test dictionary with key and value validators."""
        def key_validator(key, field):
            return str(key).lower()

        def value_validator(value, field):
            return InputValidator.validate_string(value, field_name=field)

        result = InputValidator.validate_dict(
            {"Key1": "Value1"},
            field_name="test_field",
            key_validator=key_validator,
            value_validator=value_validator
        )
        assert "key1" in result


class TestSpecializedValidators:
    """Test specialized validators."""

    def test_uuid_validation(self):
        """Test UUID validation."""
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = InputValidator.validate_uuid(valid_uuid, "test_field")
        assert result == valid_uuid

    def test_invalid_uuid(self):
        """Test invalid UUID raises error."""
        with pytest.raises(ValidationError):
            InputValidator.validate_uuid("not-a-uuid", "test_field")

    def test_email_validation(self):
        """Test email validation."""
        valid_email = "test@example.com"
        result = InputValidator.validate_email(valid_email, "test_field")
        assert result == valid_email

    def test_invalid_email(self):
        """Test invalid email raises error."""
        with pytest.raises(ValidationError):
            InputValidator.validate_email("not-an-email", "test_field")

    def test_username_validation(self):
        """Test username validation."""
        valid_username = "test_user-123"
        result = InputValidator.validate_username(valid_username, "test_field")
        assert result == valid_username

    def test_invalid_username(self):
        """Test invalid username raises error."""
        with pytest.raises(ValidationError):
            InputValidator.validate_username("test@user!", "test_field")


class TestQuantumJobValidator:
    """Test quantum job validation."""

    def test_valid_problem_type(self):
        """Test valid problem types."""
        for problem_type in ["QAOA", "VQE", "ANNEALING"]:
            result = QuantumJobValidator.validate_problem_type(problem_type)
            assert result == problem_type.upper()

    def test_invalid_problem_type(self):
        """Test invalid problem type raises error."""
        with pytest.raises(ValidationError):
            QuantumJobValidator.validate_problem_type("INVALID_TYPE")

    def test_valid_backend(self):
        """Test valid backend selection."""
        backends = ["local_simulator", "advanced_simulator", "ibm_quantum"]
        for backend in backends:
            result = QuantumJobValidator.validate_backend(backend)
            assert result == backend

    def test_invalid_backend(self):
        """Test invalid backend raises error."""
        with pytest.raises(ValidationError):
            QuantumJobValidator.validate_backend("invalid_backend")

    def test_valid_optimizer(self):
        """Test valid optimizer selection."""
        optimizers = ["COBYLA", "SPSA", "SLSQP", "Nelder-Mead"]
        for optimizer in optimizers:
            result = QuantumJobValidator.validate_optimizer(optimizer)
            assert result == optimizer.upper()

    def test_invalid_optimizer(self):
        """Test invalid optimizer raises error."""
        with pytest.raises(ValidationError):
            QuantumJobValidator.validate_optimizer("INVALID_OPT")

    def test_valid_layers(self):
        """Test valid layers parameter."""
        result = QuantumJobValidator.validate_layers(5)
        assert result == 5

    def test_invalid_layers_negative(self):
        """Test negative layers raises error."""
        with pytest.raises(ValidationError):
            QuantumJobValidator.validate_layers(-1)

    def test_invalid_layers_too_high(self):
        """Test layers too high raises error."""
        with pytest.raises(ValidationError):
            QuantumJobValidator.validate_layers(21)

    def test_valid_shots(self):
        """Test valid shots parameter."""
        result = QuantumJobValidator.validate_shots(1000)
        assert result == 1000

    def test_invalid_shots(self):
        """Test invalid shots raises error."""
        with pytest.raises(ValidationError):
            QuantumJobValidator.validate_shots(0)

    def test_valid_priority_int(self):
        """Test valid integer priority."""
        result = QuantumJobValidator.validate_priority(5)
        assert result == 5

    def test_valid_priority_string(self):
        """Test valid string priority."""
        priority_map = {"low": 3, "normal": 5, "high": 8, "urgent": 10}
        for priority_str, expected in priority_map.items():
            result = QuantumJobValidator.validate_priority(priority_str)
            assert result == expected

    def test_valid_graph_edges(self):
        """Test valid graph edges."""
        edges = [[0, 1], [1, 2], [2, 0]]
        result = QuantumJobValidator.validate_graph_edges(edges)
        assert len(result) == 3

    def test_invalid_graph_edges(self):
        """Test invalid graph edges raises error."""
        with pytest.raises(ValidationError):
            QuantumJobValidator.validate_graph_edges([[0, 1], [1]])  # Invalid edge

    def test_valid_qubo_matrix_dict(self):
        """Test valid QUBO matrix as dictionary."""
        qubo = {(0, 0): 1.0, (0, 1): 0.5, (1, 1): 1.0}
        result = QuantumJobValidator.validate_qubo_matrix(qubo)
        assert len(result) == 3

    def test_valid_qubo_matrix_list(self):
        """Test valid QUBO matrix as list."""
        qubo = [[1.0, 0.5], [0.5, 1.0]]
        result = QuantumJobValidator.validate_qubo_matrix(qubo)
        assert len(result) > 0

    def test_complete_job_submission(self):
        """Test complete valid job submission."""
        job_data = {
            "problem_type": "QAOA",
            "backend": "local_simulator",
            "problem_config": {
                "problem": "maxcut",
                "edges": [[0, 1], [1, 2], [2, 0]]
            },
            "parameters": {
                "layers": 2,
                "shots": 1000,
                "optimizer": "COBYLA"
            },
            "priority": 5
        }

        result = QuantumJobValidator.validate_job_submission(job_data)
        assert result["problem_type"] == "QAOA"
        assert result["backend"] == "local_simulator"
        assert result["parameters"]["layers"] == 2
        assert result["parameters"]["shots"] == 1000

    def test_job_submission_with_invalid_params(self):
        """Test job submission with invalid parameters."""
        job_data = {
            "problem_type": "INVALID",
            "backend": "local_simulator",
            "problem_config": {},
            "parameters": {}
        }

        with pytest.raises(ValidationError):
            QuantumJobValidator.validate_job_submission(job_data)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])