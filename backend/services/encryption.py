import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionService:
    """Application-level encryption for sensitive data like API keys"""
    
    def __init__(self):
        # Get encryption key from environment or generate one
        secret_key = os.environ.get('ENCRYPTION_SECRET_KEY')
        if not secret_key:
            # Use a default key for development (should be set in production)
            secret_key = 'jarlpm-default-secret-key-change-in-production'
        
        # Derive a Fernet key from the secret
        salt = b'jarlpm_salt_v1'  # Static salt for deterministic key derivation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
        self.fernet = Fernet(key)
    
    def encrypt(self, plain_text: str) -> str:
        """Encrypt a string and return base64-encoded ciphertext"""
        encrypted = self.fernet.encrypt(plain_text.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_text: str) -> str:
        """Decrypt base64-encoded ciphertext and return plain text"""
        encrypted = base64.urlsafe_b64decode(encrypted_text.encode())
        decrypted = self.fernet.decrypt(encrypted)
        return decrypted.decode()


# Singleton instance
_encryption_service = None

def get_encryption_service() -> EncryptionService:
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
