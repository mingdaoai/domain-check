#!/usr/bin/env uv run --script
"""
Check domain availability for given domain(s).

Usage:
    ./check_domain.py example.com
    echo "example.com" | ./check_domain.py
    ./check_domain.py < domains.txt
"""

import sys
import argparse
import time
import logging
from typing import Optional, Tuple, List

from domain_checker import check_domain_availability
from logging_config import setup_logging


logger = logging.getLogger(__name__)


def check_domain_with_backoff(domain: str, base_delay: float = 0, max_retries: int = 3) -> Tuple[Optional[bool], str]:
    """Check domain availability with exponential backoff on failure.
    
    The base_delay parameter is only used for exponential backoff between retries
    when errors occur. There is no delay between successful domain checks.
    AWS Route 53 API calls have a separate 1-second rate limit.
    
    Returns (is_available, status) where status can be 'available', 'taken', or 'error'
    """
    for attempt in range(max_retries):
        try:

            is_available, status = check_domain_availability(domain)
            

            if status in ('available', 'taken'):
                return is_available, status
            

            if status == 'error':
                if attempt < max_retries - 1:  # Don't sleep on the last attempt
                    retry_delay = base_delay * (2 ** attempt)
                    error_msg = f"Error checking {domain}, retrying in {retry_delay}s..."
                    print(f"\n{error_msg}")
                    logger.warning(f"Domain check error (attempt {attempt + 1}/{max_retries}): {error_msg}")
                    time.sleep(retry_delay)
                else:
                    error_msg = f"Failed to check {domain} after {max_retries} attempts due to errors"
                    print(f"\n{error_msg}")
                    logger.error(error_msg)
                    return None, 'error'
        except Exception as e:
            if attempt < max_retries - 1:  # Don't sleep on the last attempt
                # Exponential backoff: 2s, 4s, 8s, etc.
                retry_delay = base_delay * (2 ** attempt)
                error_msg = f"Error checking {domain}, retrying in {retry_delay}s... ({str(e)})"
                print(f"\n{error_msg}")
                logger.warning(f"Domain check error (attempt {attempt + 1}/{max_retries}): {error_msg}")
                time.sleep(retry_delay)
            else:
                error_msg = f"Failed to check {domain} after {max_retries} attempts: {str(e)}"
                print(f"\n{error_msg}")
                logger.error(error_msg)
                return None, 'error'
    
    return None, 'error'


def check_domains(domains: List[str], base_delay: float = 0, max_retries: int = 3) -> dict:
    """Check multiple domains and return results.
    
    The base_delay parameter is passed to check_domain_with_backoff and is only
    used for exponential backoff between retries when errors occur.
    There is no delay between successful domain checks.
    AWS Route 53 API calls have a separate 1-second rate limit.
    """
    results = {}
    for domain in domains:
        domain = domain.strip().lower()
        if not domain:
            continue
        print(f"Checking {domain}...", file=sys.stderr)
        is_available, status = check_domain_with_backoff(domain, base_delay, max_retries)
        results[domain] = {
            'available': is_available,
            'status': status
        }
        if status == 'available':
            print(f"{domain}: available")
        elif status == 'taken':
            print(f"{domain}: taken")
        else:
            print(f"{domain}: error")
    return results


def main() -> int:
    """Main entry point."""

    try:
        logger_instance, log_file = setup_logging()
        logger.info(f"Logging to {log_file}")
    except Exception as e:
        print(f"Warning: Failed to set up logging: {e}", file=sys.stderr)
        logger_instance = logging.getLogger()
        logger_instance.setLevel(logging.WARNING)
    
    parser = argparse.ArgumentParser(description='Check domain availability.')
    parser.add_argument('domains', nargs='*', help='Domain(s) to check')
    parser.add_argument('--delay', type=float, default=0.0, help='Base delay for retries (not used for initial checks) in seconds')
    parser.add_argument('--retries', type=int, default=3, help='Maximum retries on error')
    args = parser.parse_args()
    
    domains = args.domains
    if not domains:

        domains = [line.strip() for line in sys.stdin if line.strip()]
    
    if not domains:
        print("No domains provided.", file=sys.stderr)
        parser.print_help()
        return 1
    

    unique_domains = list(dict.fromkeys(domains))
    if len(domains) != len(unique_domains):
        print(f"Note: Removed {len(domains) - len(unique_domains)} duplicate domains.", file=sys.stderr)
    
    logger.info(f"Checking {len(unique_domains)} domain(s)")
    try:
        results = check_domains(unique_domains, args.delay, args.retries)
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130

    available = [d for d, r in results.items() if r['status'] == 'available']
    taken = [d for d, r in results.items() if r['status'] == 'taken']
    errors = [d for d, r in results.items() if r['status'] == 'error']
    
    print("\n=== Summary ===", file=sys.stderr)
    print(f"Available: {len(available)}", file=sys.stderr)
    print(f"Taken: {len(taken)}", file=sys.stderr)
    print(f"Errors: {len(errors)}", file=sys.stderr)
    
    if errors:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())