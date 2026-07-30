"""Domain error types for the Food Security module."""


class FSMError(Exception):
    """Base class for all Food Security module errors."""


class InfeasibleAllocation(FSMError):
    """Raised when the allocator cannot satisfy the hard constraints."""


class MissingCommodityData(FSMError):
    """Raised when a food commodity is missing required data (energy or price)."""
