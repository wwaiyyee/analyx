"""Language linter blocking unjustified causal assertions per §8.8 (2)."""

from dataclasses import dataclass, field
import re

CAUSAL_PHRASES = [
    r"\bcaused\s+by\b",
    r"\bcaused\b",
    r"\bbecause\b",
    r"\bdue\s+to\b",
    r"\bled\s+to\b",
    r"\bdriven\s+by\b",
    r"\bresulted\s+in\b",
    r"\bas\s+a\s+result\s+of\b",
    r"\bresponsible\s+for\b",
]

SUGGESTED_REWRITES = {
    "driven by": "accounts for X% of the change / is concentrated in",
    "caused by": "coincides with / corresponds to",
    "caused": "is associated with / coincides with",
    "because": "coinciding with / following",
    "due to": "in parallel with / associated with",
    "led to": "preceded / coincided with",
    "resulted in": "was accompanied by",
    "as a result of": "concurrently with",
    "responsible for": "accounting for",
}


@dataclass
class LanguageLintResult:
    passed: bool
    flagged_phrases: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


def lint_language(text: str) -> LanguageLintResult:
    """Check text for ungrounded causal claims and recommend non-causal associative phrasing."""
    flagged: list[str] = []
    suggestions: list[str] = []

    for pattern in CAUSAL_PHRASES:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        for match in matches:
            norm_match = match.lower().strip()
            if norm_match not in flagged:
                flagged.append(norm_match)
                # Find matching suggestion
                sugg = SUGGESTED_REWRITES.get(norm_match, "is correlated with / coincides with")
                suggestions.append(f"Replace '{norm_match}' with '{sugg}'")

    return LanguageLintResult(
        passed=len(flagged) == 0,
        flagged_phrases=flagged,
        suggestions=suggestions,
    )
