"""
SQL safety guardrail.

Rejects anything that is not a single read-only SELECT statement.
"""
from __future__ import annotations

import re
from typing import Tuple

# Keywords that must never appear in a user- or LLM-generated query.
FORBIDDEN_KEYWORDS = re.compile(
    r"\b(drop|delete|update|insert|alter|truncate|create|replace|attach|"
    r"detach|pragma|vacuum|grant|revoke|exec|execute|merge|call|begin|commit)\b",
    re.IGNORECASE,
)

# Query must begin with SELECT or a WITH ... SELECT CTE.
ALLOWED_PREFIX = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


def validate_sql(sql: str) -> Tuple[bool, str]:
    """
    Return (is_valid, cleaned_sql_or_error_message).

    Rules enforced:
      1. Non-empty.
      2. Single statement (no stacked `;` injections).
      3. Must start with SELECT or WITH.
      4. No forbidden keywords (DROP, DELETE, UPDATE, INSERT, ...).
    """
    if not sql or not sql.strip():
        return False, "The model returned an empty query."

    cleaned = sql.strip()
    # Strip accidental markdown fences
    cleaned = re.sub(
        r"^```(?:sql)?|```$", "", cleaned,
        flags=re.IGNORECASE | re.MULTILINE,
    ).strip()

    # Allow exactly one trailing semicolon
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()
    if ";" in cleaned:
        return False, "Multiple SQL statements are not allowed."

    if not ALLOWED_PREFIX.match(cleaned):
        return False, "Only SELECT queries are permitted."

    match = FORBIDDEN_KEYWORDS.search(cleaned)
    if match:
        return False, f"Blocked dangerous keyword: '{match.group(0)}'."

    return True, cleaned