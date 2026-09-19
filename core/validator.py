"""Input validation for tool parameters dispatched by the LLM.

Each action can define a VALIDATOR dict mapping parameter names to a list of
validation rules.  The dispatcher calls `validate_params()` before invoking the
action, and rejects malformed calls early.

Example in an action module:
    TOOL = {
        "name": "send_whatsapp",
        "description": "...",
        "parameters": {...},
    }
    VALIDATOR = {
        "receiver": [{"type": str, "max_len": 100, "required": True}],
        "message":  [{"type": str, "max_len": 4000, "required": True}],
    }
"""
from __future__ import annotations
import re
from typing import Any


class ValidationError(Exception):
    """Raised when tool parameters fail validation."""


def validate_params(params: dict[str, Any], rules: dict[str, list[dict]],
                    tool_name: str = "unknown") -> dict[str, Any]:
    """Validate and sanitise parameters against a rule set.

    Returns the cleaned parameter dict on success.
    Raises ValidationError with a human-readable message on failure.
    """
    if not rules:
        return params  # no validation defined — pass through

    cleaned: dict[str, Any] = {}
    errors: list[str] = []

    for param_name, param_rules in rules.items():
        value = params.get(param_name)

        for rule in param_rules:
            # required check
            if rule.get("required") and (value is None or value == ""):
                errors.append(f"'{param_name}' is required")
                break

            if value is None or value == "":
                cleaned[param_name] = rule.get("default")
                continue

            # type check
            expected_type = rule.get("type")
            if expected_type and not isinstance(value, expected_type):
                # allow int where float is expected
                if expected_type is float and isinstance(value, int):
                    value = float(value)
                elif expected_type is str and not isinstance(value, str):
                    value = str(value)
                else:
                    errors.append(f"'{param_name}' must be {expected_type.__name__}, got {type(value).__name__}")
                    break

            # string validations
            if isinstance(value, str):
                max_len = rule.get("max_len")
                if max_len and len(value) > max_len:
                    errors.append(f"'{param_name}' exceeds max length {max_len}")
                    break

                min_len = rule.get("min_len")
                if min_len and len(value) < min_len:
                    errors.append(f"'{param_name}' below min length {min_len}")
                    break

                pattern = rule.get("pattern")
                if pattern and not re.match(pattern, value):
                    errors.append(f"'{param_name}' doesn't match required pattern")
                    break

                # strip injection attempts in shell commands
                if rule.get("no_shell"):
                    dangerous = re.compile(r'[;&|`$(){}!\n]')
                    if dangerous.search(value):
                        errors.append(f"'{param_name}' contains disallowed characters")
                        break

                # trim whitespace
                value = value.strip()

            # numeric validations
            if isinstance(value, (int, float)):
                min_val = rule.get("min")
                if min_val is not None and value < min_val:
                    errors.append(f"'{param_name}' must be >= {min_val}")
                    break

                max_val = rule.get("max")
                if max_val is not None and value > max_val:
                    errors.append(f"'{param_name}' must be <= {max_val}")
                    break

                value = rule.get("type", type(value))(value)

            # enum check
            allowed = rule.get("enum")
            if allowed and value not in allowed:
                errors.append(f"'{param_name}' must be one of {allowed}")
                break

            # url check
            if rule.get("url") and isinstance(value, str):
                if not re.match(r'^https?://', value):
                    errors.append(f"'{param_name}' must be a valid URL")
                    break

            # path check — prevent directory traversal
            if rule.get("safe_path") and isinstance(value, str):
                if ".." in value or value.startswith("/"):
                    errors.append(f"'{param_name}' contains unsafe path")
                    break

            cleaned[param_name] = value
            break  # first matching rule wins
        else:
            # no rules matched — include as-is
            cleaned[param_name] = value

    # include any params not in rules as-is (pass-through)
    for k, v in params.items():
        if k not in rules:
            cleaned[k] = v

    if errors:
        msg = f"Validation failed for '{tool_name}': {'; '.join(errors)}"
        raise ValidationError(msg)

    return cleaned
