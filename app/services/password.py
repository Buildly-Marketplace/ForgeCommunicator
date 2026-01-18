"""
Password hashing and verification using bcrypt.
"""

import bcrypt


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    # bcrypt has a 72-byte limit, truncate if needed
    password_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    password_bytes = plain_password.encode("utf-8")[:72]
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def validate_password(password: str, min_length: int = 8) -> tuple[bool, str | None]:
    """Validate password strength.
    
    Returns (is_valid, error_message).
    """
    if len(password) < min_length:
        return False, f"Password must be at least {min_length} characters"
    
    return True, None
