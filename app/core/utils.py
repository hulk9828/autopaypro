"""Shared utilities used across the app."""


def ensure_non_negative_amount(amount: float | None) -> float:
    """Return amount clamped to >= 0. Use for any monetary value in API responses or display."""
    return max(0.0, float(amount)) if amount is not None else 0.0
