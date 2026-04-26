import logging
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_last_aws_call_time = 0.0

def _rate_limit_aws_calls(min_interval: float = 1.0) -> None:
    """Ensure at least min_interval seconds between AWS Route 53 API calls."""
    global _last_aws_call_time
    now = time.time()
    elapsed = now - _last_aws_call_time
    if elapsed < min_interval:
        sleep_time = min_interval - elapsed
        logger.debug(f"Rate limiting AWS API calls: sleeping {sleep_time:.2f}s")
        time.sleep(sleep_time)
    _last_aws_call_time = time.time()


def check_dns_records(domain: str, timeout: float = 5.0) -> Tuple[Optional[bool], str]:
    """
    Check if a domain has any DNS records.
    
    Returns:
        Tuple[is_available, status]
        is_available: True if domain has no DNS records (likely available),
                     False if DNS records exist,
                     None if error
        status: 'available', 'taken', or 'error'
    """
    try:
        import dns.resolver
        from dns.resolver import NXDOMAIN, NoAnswer, NoNameservers, LifetimeTimeout
    except ImportError:
        logger.warning("dnspython library not installed. DNS checking disabled.")
        return None, 'error'
    
    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = timeout
        resolver.lifetime = timeout
        resolver.nameservers = ['8.8.8.8', '1.1.1.1', '9.9.9.9']
        
        record_types = ["A", "AAAA", "MX", "NS", "CNAME", "TXT", "SOA"]
        
        for record_type in record_types:
            try:
                answers = resolver.resolve(domain, record_type, raise_on_no_answer=False)
                if len(answers) > 0:
                    logger.debug(f"Domain {domain} has {record_type} DNS records")
                    return False, 'taken'
            except NXDOMAIN:
                logger.debug(f"Domain {domain} has no DNS records (NXDOMAIN)")
                return True, 'available'
            except NoAnswer:
                continue
            except (NoNameservers, LifetimeTimeout) as e:
                logger.warning(f"DNS check failed for {domain}: {e}")
                return None, 'error'
        
        logger.debug(f"Domain {domain} has no DNS records across all checked types")
        return True, 'available'
        
    except Exception as e:
        logger.error(f"Unexpected error in DNS check for {domain}: {e}", exc_info=True)
        return None, 'error'


def check_aws_route53(domain: str, max_retries: int = 3) -> Tuple[Optional[bool], str]:
    """
    Check domain availability using AWS Route 53 Domains API.
    
    Returns:
        Tuple[is_available, status]
        is_available: True if domain is available,
                     False if domain is not available,
                     None if error or unknown
        status: 'available', 'taken', or 'error'
    """
    try:
        import boto3
        from botocore.exceptions import ClientError, BotoCoreError
    except ImportError:
        logger.warning("boto3 library not installed. AWS Route 53 checking disabled.")
        return None, 'error'
    
    region = 'us-east-1'
    
    for attempt in range(max_retries):
        try:
            client = boto3.client('route53domains', region_name=region)
            _rate_limit_aws_calls()
            response = client.check_domain_availability(DomainName=domain)
            availability = response.get('Availability', 'DONT_KNOW')
            
            if availability in ['AVAILABLE', 'AVAILABLE_RESERVED', 'AVAILABLE_PREORDER']:
                logger.debug(f"AWS Route 53: Domain {domain} is available ({availability})")
                return True, 'available'
            elif availability in ['UNAVAILABLE', 'UNAVAILABLE_PREMIUM', 
                                  'UNAVAILABLE_RESTRICTED', 'RESERVED']:
                logger.debug(f"AWS Route 53: Domain {domain} is not available ({availability})")
                return False, 'taken'
            elif availability == 'PENDING':
                logger.debug(f"AWS Route 53: Domain {domain} status is PENDING, retrying...")
                time.sleep(0.5)
                continue
            else:
                logger.debug(f"AWS Route 53: Domain {domain} status is {availability}")
                return None, 'error'
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            
            if error_code in ['ThrottlingException', 'RequestLimitExceeded'] and attempt < max_retries - 1:
                wait_time = (2 ** attempt) + 0.1
                logger.warning(f"AWS error for {domain} (attempt {attempt+1}/{max_retries}): "
                              f"{error_code}, retrying in {wait_time:.1f}s")
                time.sleep(wait_time)
                continue
            
            logger.error(f"AWS ClientError checking {domain}: {error_code} - {error_msg}")
            return None, 'error'
            
        except BotoCoreError as e:
            logger.error(f"AWS BotoCoreError checking {domain}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None, 'error'
            
        except Exception as e:
            logger.error(f"Unexpected error in AWS check for {domain}: {e}", exc_info=True)
            return None, 'error'
    
    return None, 'error'


def check_whois_fallback(domain: str) -> Tuple[Optional[bool], str]:
    """
    Fallback to WHOIS checking if DNS and AWS checks fail.
    
    Returns:
        Tuple[is_available, status]
        is_available: True if domain is available,
                     False if domain is taken,
                     None if error
        status: 'available', 'taken', or 'error'
    """
    try:
        import whois
        from whois import WhoisError
    except ImportError:
        logger.warning("python-whois library not installed. WHOIS fallback disabled.")
        return None, 'error'
    
    try:
        logger.debug(f"WHOIS fallback checking: {domain}")
        domain_info = whois.whois(domain)
        
        if domain_info.get('domain_name'):
            logger.debug(f"WHOIS: Domain {domain} is taken (registered)")
            return False, 'taken'
        else:
            logger.debug(f"WHOIS: Domain {domain} is available")
            return True, 'available'
            
    except WhoisError as e:
        logger.debug(f"WHOIS error for {domain} (likely available): {e}")
        return True, 'available'
        
    except Exception as e:
        logger.error(f"Unexpected error in WHOIS check for {domain}: {e}", exc_info=True)
        return None, 'error'


def check_domain_availability(domain: str) -> Tuple[Optional[bool], str]:
    """
    Check domain availability with the following flow:
    1. DNS check first - if domain has DNS records, it's taken
    2. If no DNS records, check AWS Route 53 Domains API
    3. If AWS fails, fallback to WHOIS
    
    Returns:
        Tuple[is_available, status]
        is_available: True if domain is available,
                     False if domain is taken,
                     None if error
        status: 'available', 'taken', or 'error'
    """
    logger.debug(f"Starting domain availability check for: {domain}")
    
    dns_available, dns_status = check_dns_records(domain)
    
    if dns_status == 'taken':
        logger.info(f"Domain {domain} is taken (DNS records found)")
        return False, 'taken'
    
    if dns_status == 'available':
        logger.debug(f"Domain {domain} has no DNS records, checking AWS Route 53...")
        
        aws_available, aws_status = check_aws_route53(domain)
        
        if aws_status == 'available':
            logger.info(f"Domain {domain} is available (AWS Route 53 confirmed)")
            return True, 'available'
        
        if aws_status == 'taken':
            logger.info(f"Domain {domain} is taken (AWS Route 53 confirmed)")
            return False, 'taken'
        
        logger.debug(f"AWS check for {domain} failed or inconclusive ({aws_status}), "
                    f"falling back to WHOIS")
        
        whois_available, whois_status = check_whois_fallback(domain)
        
        if whois_status in ['available', 'taken']:
            logger.info(f"Domain {domain} is {'available' if whois_available else 'taken'} "
                       f"(WHOIS fallback)")
            return whois_available, whois_status
        
        logger.error(f"All domain checking methods failed for {domain}")
        return None, 'error'
    
    logger.debug(f"DNS check for {domain} failed ({dns_status}), checking AWS directly...")
    
    aws_available, aws_status = check_aws_route53(domain)
    
    if aws_status in ['available', 'taken']:
        logger.info(f"Domain {domain} is {'available' if aws_available else 'taken'} "
                   f"(AWS check, DNS failed)")
        return aws_available, aws_status
    
    logger.debug(f"AWS check for {domain} also failed, trying WHOIS fallback...")
    whois_available, whois_status = check_whois_fallback(domain)
    
    if whois_status in ['available', 'taken']:
        logger.info(f"Domain {domain} is {'available' if whois_available else 'taken'} "
                   f"(WHOIS fallback, DNS/AWS failed)")
        return whois_available, whois_status
    
    logger.error(f"All domain checking methods failed for {domain}")
    return None, 'error'