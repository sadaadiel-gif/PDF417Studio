class MRZError(Exception):
    pass

class MRZValidationError(MRZError):
    pass

class MRZChronologyError(MRZValidationError):
    pass