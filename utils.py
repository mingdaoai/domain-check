import os

def load_api_key():
    key_path = os.path.expanduser("~/.mingdaoai/openai.key")
    try:
        with open(key_path, "r") as key_file:
            return key_file.read().strip()
    except FileNotFoundError:
        return None