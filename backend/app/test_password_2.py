"""Security utilities for password hashing and verification"""
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Create password hasher instance
ph = PasswordHasher()


def hash_password(password: str) -> str:
    """
    Hash a plain text password using Argon2.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
    """
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        ph.verify(hashed_password, plain_password)
        return True
    except VerifyMismatchError:
        return False

if __name__ == "__main__":
    password = "tEsT_Passw0rD"
    hashed_pw = hash_password(password)
    print(f"hashed pw: {hashed_pw}")

