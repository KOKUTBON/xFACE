"""Domain specific exceptions for xFACE."""


class XFaceException(Exception):
    """Base exception for all xFACE errors."""
    pass


class CameraException(XFaceException):
    """Raised when camera initialization or frame grabbing fails."""
    pass


class CompreFaceException(XFaceException):
    """Raised when CompreFace API fails or is unreachable."""
    pass


class HardwareException(XFaceException):
    """Raised when smart relay / Shelly communication fails."""
    pass


class SecurityException(XFaceException):
    """Raised on authentication, authorization or path traversal violations."""
    pass


class SubjectNotFoundException(XFaceException):
    """Raised when an operation targets a non-existing subject."""
    pass
