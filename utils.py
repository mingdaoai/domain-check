import os
import logging

logger = logging.getLogger(__name__)

def load_api_key():
    key_path = os.path.expanduser("~/.mingdaoai/anthropic.key")
    try:
        with open(key_path, "r") as key_file:
            api_key = key_file.read().strip()
            logger.debug(f"Successfully loaded API key from {key_path}")
            return api_key
    except FileNotFoundError:
        logger.warning(f"API key file not found: {key_path}")
        return None
    except Exception as e:
        logger.error(f"Error loading API key from {key_path}: {e}", exc_info=True)
        return None