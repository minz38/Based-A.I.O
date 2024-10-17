from cryptography.fernet import Fernet
import base64
import json

# Path to the bot configuration file
BOT_CONFIG_PATH: str = 'configs/bot_config.json'


# Generate or load the encryption key
def generate_key() -> bytes:
    """Generates a new encryption key."""
    return Fernet.generate_key()


def load_key_from_config() -> bytes:
    """
    Loads the encryption key from the bot configuration JSON file.
    If the key doesn't exist, it generates a new one and saves it.
    """
    # Load the config file
    with open(BOT_CONFIG_PATH, 'r') as config_file:
        config = json.load(config_file)

    # Check if the key is already in the config
    if 'encryption_key' not in config or not config['encryption_key']:
        # Generate a new key and store it in the config
        key = generate_key()
        config['encryption_key'] = base64.urlsafe_b64encode(key).decode()  # Store key in base64 encoded format
        with open(BOT_CONFIG_PATH, 'w') as config_file:
            json.dump(config, config_file, indent=4)
    else:
        # Load the existing key from the config (decode it from base64)
        key: bytes = base64.urlsafe_b64decode(config['encryption_key'].encode())

    return key


# Encrypt the data
def encrypt(data: str, key: bytes) -> str:
    """Encrypts a string using the provided key."""
    fernet = Fernet(key)
    encrypted_data = fernet.encrypt(data.encode())  # Encode the string to bytes before encrypting
    return base64.urlsafe_b64encode(encrypted_data).decode()  # Return the encrypted string


# Decrypt the data
def decrypt(encrypted_data: str) -> str:
    """Decrypts an encrypted string using the provided key."""
    key = load_key_from_config()  # Load the encryption key (if it doesn't exist, generate a new one)
    fernet = Fernet(key)
    decrypted_data = fernet.decrypt(
        base64.urlsafe_b64decode(encrypted_data.encode()))  # Decode the string before decrypting
    return decrypted_data.decode()  # Return the decrypted string
