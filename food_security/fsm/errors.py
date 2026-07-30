"""Domain error types for the Food Security module."""


class FSMError(Exception):
    """Base class for all Food Security module errors."""


class InfeasibleAllocation(FSMError):  # noqa: N818 - spec-defined public name
    """Raised when the allocator cannot satisfy the hard constraints."""


class MissingCommodityData(FSMError):  # noqa: N818 - spec-defined public name
    """Raised when a food commodity is missing required data (energy or price)."""
