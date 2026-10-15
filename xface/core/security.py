"""Security helpers for password verification and path sanitization in xFACE."""

import re
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash
from xface.core.exceptions import SecurityException


def hash_password(password: str) -> str:
    """Generate a salted hash using scrypt/pbkdf2 via Werkzeug."""
    return generate_password_hash(password, method="scrypt")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hashed value safely."""
    if not plain_password or not hashed_password:
        return False
    return check_password_hash(hashed_password, plain_password)


def sanitize_filename(filename: str) -> str:
    """Strip dangerous characters and keep filename safe."""
    clean = re.sub(r'[/\\?%*:|"<>]', '_', filename)
    clean = clean.strip('. ')
    return clean or "unnamed_file"


def validate_path_within_directory(child_path: str | Path, parent_dir: str | Path) -> Path:
    """
    Ensure child_path resolves strictly within parent_dir to prevent path traversal attacks.
    Raises SecurityException if validation fails.
    """
    parent = Path(parent_dir).resolve()
    child = Path(child_path).resolve()

    try:
        child.relative_to(parent)
    except ValueError as e:
        raise SecurityException(
            f"Path traversal detected: {child} is not within {parent}"
        ) from e

    return child
