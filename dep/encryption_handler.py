import base64

from cryptography.fernet import Fernet

from dep.config_handler import BotConfigHandler


# Generate or load the encryption key
def generate_key() -> bytes:
    """Generates a new encryption key (raw bytes)."""
    return Fernet.generate_key()


def load_key_from_config() -> bytes:
    """
    Loads the encryption key from the bot config.
    If the key doesn't exist, generates a new one and saves it.
    """
    handler = BotConfigHandler()
    config = handler.get_config()

    encoded_key = config.get("encryption_key")

    if not encoded_key:
        # Generate and store a new key in base64 format
        new_key = generate_key()
        encoded_key = base64.urlsafe_b64encode(new_key).decode()
        handler.update_config("encryption_key", encoded_key)
        return new_key

    # Return the decoded key as bytes
    return base64.urlsafe_b64decode(encoded_key.encode())


def encrypt(data: str, key: bytes) -> str:
    """Encrypts a string using the provided key."""
    fernet = Fernet(key)
    encrypted = fernet.encrypt(data.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt(encrypted_data: str) -> str:
    """Decrypts a string using the stored key."""
    key = load_key_from_config()
    fernet = Fernet(key)
    decrypted = fernet.decrypt(base64.urlsafe_b64decode(encrypted_data.encode()))
    return decrypted.decode()
