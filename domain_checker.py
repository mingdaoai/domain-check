import logging
import whois

logger = logging.getLogger(__name__)

def check_domain_availability(domain):
    """
    Check domain availability and return (is_available, status)
    status can be: 'available', 'taken', or 'error'
    """
    try:
        logger.debug(f"Checking domain availability: {domain}")
        domain_info = whois.whois(domain)
        
        # Check if domain is registered by looking at domain_name field
        if domain_info.domain_name:
            # Domain is registered/taken
            logger.debug(f"Domain {domain} is taken (registered)")
            return False, 'taken'
        else:
            # Domain is available
            logger.debug(f"Domain {domain} is available")
            return True, 'available'
    except whois.parser.PywhoisError as e:
        # Domain is likely available if whois lookup fails with PywhoisError
        # (typically means domain not found in registry)
        logger.debug(f"PywhoisError for {domain} (likely available): {e}")
        return True, 'available'
    except Exception as e:
        # Unexpected error occurred during check
        logger.error(f"Unexpected error checking domain {domain}: {e}", exc_info=True)
        return None, 'error'