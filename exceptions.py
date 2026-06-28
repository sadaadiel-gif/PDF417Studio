class MRZError(Exception):
    """Base domain exception for all MRZ library errors."""
    pass

class MRZValidationError(MRZError):
    """Raised when an asset fails structural, character, or format validation."""
    pass

class MRZChronologyError(MRZValidationError):
    """Raised specifically for logical date or time sequence violations."""
    pass