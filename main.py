import os
import readline
import json
import time
import traceback
from datetime import datetime
from openai_helper import OpenAIHelper
from domain_checker import check_domain_availability
from utils import load_api_key
from logging_config import setup_logging

# Set up logging first
logger, log_file = setup_logging()


def get_cache_dir():
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(script_dir, '.cache')
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    return cache_dir


def get_queries_file_path():
    return os.path.join(get_cache_dir(), 'query_history.json')


def load_query_history():
    queries_file = get_queries_file_path()
    if os.path.exists(queries_file):
        try:
            with open(queries_file, 'r') as f:
                data = json.load(f)
                return data.get('queries', [])
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error loading query history from {queries_file}: {e}", exc_info=True)
            return []
    return []


def save_query_history(queries):
    queries_file = get_queries_file_path()
    try:
        with open(queries_file, 'w') as f:
            json.dump({'queries': queries}, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving query history to {queries_file}: {e}", exc_info=True)


def setup_readline_history():
    # Set up readline with custom history file in .cache directory
    histfile = os.path.join(get_cache_dir(), ".domain_finder_history")
    try:
        readline.read_history_file(histfile)
    except FileNotFoundError:
        logger.debug(f"History file {histfile} not found, creating new one")
    except Exception as e:
        logger.error(f"Error reading history file {histfile}: {e}", exc_info=True)
    
    readline.set_history_length(1000)
    
    # Load past queries into readline history
    try:
        queries = load_query_history()
        for query in queries:
            readline.add_history(query)
    except Exception as e:
        logger.error(f"Error loading queries into readline history: {e}", exc_info=True)
    
    return histfile


def get_cache_file_path(query):
    # Create a safe filename from the query
    safe_query = "".join(c for c in query if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_query = safe_query.replace(' ', '_').lower()
    if len(safe_query) > 100:  # Limit filename length
        safe_query = safe_query[:100]
    return os.path.join(get_cache_dir(), f"domains_{safe_query}.json")


def load_cached_results(query):
    cache_file = get_cache_file_path(query)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
                print("\nFound cached results from previous searches:")
                print(f"Last updated: {data['searches'][-1]['timestamp']}")
                print(f"Total searches: {len(data['searches'])}")
                print(f"Total available domains found: {len(data['available_domains'])}")
                logger.info(f"Loaded cached results from {cache_file}")
                return data
        except (json.JSONDecodeError, KeyError) as e:
            # If cache file is corrupted, return empty results
            logger.error(f"Error loading cached results from {cache_file}: {e}", exc_info=True)
    return {
        'query': query,
        'available_domains': [],
        'unavailable_domains': [],
        'searches': []
    }


def save_domains_to_cache(query, available_domains, unavailable_domains, existing_data=None):
    try:
        if existing_data is None:
            existing_data = load_cached_results(query)
        
        cache_file = get_cache_file_path(query)
        
        # Add new search results
        search_data = {
            'timestamp': datetime.now().isoformat(),
            'new_available_domains': list(set(available_domains)),  # Deduplicate new results
            'new_unavailable_domains': list(set(unavailable_domains))  # Deduplicate new results
        }
        
        # Update the main data structure
        existing_data['searches'].append(search_data)
        
        # Update available domains (avoid duplicates)
        # Convert to set and back to list to remove duplicates while preserving order
        all_available = list(dict.fromkeys(existing_data['available_domains'] + available_domains))
        all_unavailable = list(dict.fromkeys(existing_data['unavailable_domains'] + unavailable_domains))
        
        # Ensure no domain is in both lists
        available_set = set(all_available)
        unavailable_set = set(all_unavailable)
        common_domains = available_set.intersection(unavailable_set)
        
        if common_domains:
            # Remove domains that appear in both lists from the unavailable list
            # (if a domain was previously unavailable but is now available, trust the latest check)
            unavailable_set = unavailable_set - common_domains
            
        existing_data['available_domains'] = list(available_set)
        existing_data['unavailable_domains'] = list(unavailable_set)
        
        with open(cache_file, 'w') as f:
            json.dump(existing_data, f, indent=2)
        
        logger.info(f"Saved {len(available_domains)} available and {len(unavailable_domains)} unavailable domains to {cache_file}")
        return cache_file
    except Exception as e:
        logger.error(f"Error saving domains to cache: {e}", exc_info=True)
        raise


def check_domain_with_backoff(domain, base_delay=2, max_retries=3):
    """Check domain availability with exponential backoff on failure
    Returns (is_available, status) where status can be 'available', 'taken', or 'error'
    """
    for attempt in range(max_retries):
        try:
            # Add base delay between each domain check
            time.sleep(base_delay)
            is_available, status = check_domain_availability(domain)
            
            # If we got a successful result (available or taken), return it
            if status in ('available', 'taken'):
                return is_available, status
            
            # If we got an error, retry
            if status == 'error':
                if attempt < max_retries - 1:  # Don't sleep on the last attempt
                    retry_delay = base_delay * (2 ** attempt)
                    error_msg = f"Error checking {domain}, retrying in {retry_delay}s..."
                    print(f"\n{error_msg}")
                    logger.warning(f"Domain check error (attempt {attempt + 1}/{max_retries}): {error_msg}", exc_info=True)
                    time.sleep(retry_delay)
                else:
                    error_msg = f"Failed to check {domain} after {max_retries} attempts due to errors"
                    print(f"\n{error_msg}")
                    logger.error(error_msg, exc_info=True)
                    return None, 'error'
        except Exception as e:
            if attempt < max_retries - 1:  # Don't sleep on the last attempt
                # Exponential backoff: 2s, 4s, 8s, etc.
                retry_delay = base_delay * (2 ** attempt)
                error_msg = f"Error checking {domain}, retrying in {retry_delay}s... ({str(e)})"
                print(f"\n{error_msg}")
                logger.warning(f"Domain check error (attempt {attempt + 1}/{max_retries}): {error_msg}", exc_info=True)
                time.sleep(retry_delay)
            else:
                error_msg = f"Failed to check {domain} after {max_retries} attempts: {str(e)}"
                print(f"\n{error_msg}")
                logger.error(error_msg, exc_info=True)
                return None, 'error'
    
    return None, 'error'


def get_max_domain_length(cached_domains, default_max=30):
    """Get the length of the 20th longest domain, or default if less than 20 domains exist"""
    if not cached_domains:
        return default_max
    
    # Sort domains by length in descending order
    sorted_by_length = sorted(cached_domains, key=len, reverse=True)
    
    # If we have at least 20 domains, use the 20th one's length
    if len(sorted_by_length) >= 20:
        return len(sorted_by_length[19])  # 19 is the 20th index (0-based)
    
    # If we have less than 20 domains, use the longest one's length
    return len(sorted_by_length[0]) if sorted_by_length else default_max


def check_domains_batch(domains, known_domains, available_list, unavailable_list, max_length):
    """Check a batch of domains with rate limiting"""
    # Deduplicate input domains and filter by length
    unique_domains = [d.lower() for d in domains if len(d) <= max_length]
    unique_domains = list(dict.fromkeys(unique_domains))
    known_set = set(d.lower() for d in known_domains)
    
    if len(domains) > len(unique_domains):
        print(f"\nSkipping {len(domains) - len(unique_domains)} domains that exceed maximum length of {max_length} characters")
    
    for domain in unique_domains:
        if domain not in known_set:  # Only check new domains
            print(f"Checking domain: {domain}")  # Show progress
            is_available, status = check_domain_with_backoff(domain)
            
            if status == 'available' and is_available:
                available_list.append(domain)
                print(f"✓ {domain} is available!")
            elif status == 'taken':
                unavailable_list.append(domain)
                print(f"✗ {domain} is taken")
            elif status == 'error':
                # Don't add to unavailable_list for errors, just log
                print(f"⚠ {domain} - error occurred during check")
                logger.warning(f"Could not determine availability for {domain} due to errors")


def display_top_domains(all_domains, limit=20):
    """Display all domains, sorted alphabetically"""
    # Deduplicate domains while preserving order
    unique_domains = list(dict.fromkeys(all_domains))
    
    # Sort domains first by length, then alphabetically
    sorted_domains = sorted(unique_domains, key=lambda x: (len(x), x))
    
    if not sorted_domains:
        print("\nNo domains to display.")
        return
    
    # Always show all domains
    print(f"\nAll {len(sorted_domains)} domains (sorted by length, then alphabetically):")
    for rank, domain in enumerate(sorted_domains, 1):
        print(f"{rank:2d}. {domain} ({len(domain)} chars)")


def main():
    try:
        api_key = load_api_key()
        if not api_key:
            error_msg = "Error: Anthropic API key not found. Please add it to ~/.mingdaoai/anthropic.key"
            print(error_msg)
            logger.error(error_msg)
            return

        openai_helper = OpenAIHelper(api_key)
        logger.info("Anthropic API client initialized successfully")

        print("Welcome to the Domain Name Finder!")
        print("Share your ideas for domain names, and I'll help you find unique options.")
        print("Use UP/DOWN arrow keys to browse through your previous queries.")
        print(f"Logging to: {log_file}")

        # Set up readline with history
        try:
            histfile = setup_readline_history()
        except Exception as e:
            logger.error(f"Error setting up readline history: {e}", exc_info=True)
            histfile = None
        
        # Load existing query history
        try:
            queries = load_query_history()
        except Exception as e:
            logger.error(f"Error loading query history: {e}", exc_info=True)
            queries = []

        while True:
            try:
                print("\nWhat's your idea for a domain name? (or type 'quit' to exit):")
                user_input = input("> ")
                
                if user_input.lower() == 'quit':
                    print("Thank you for using the Domain Name Finder. Goodbye!")
                    logger.info("User exited the application")
                    break

                logger.info(f"Processing query: {user_input}")

                # Save query to history if it's new
                try:
                    if user_input not in queries:
                        queries.append(user_input)
                        save_query_history(queries)
                        if histfile:
                            readline.add_history(user_input)
                except Exception as e:
                    logger.error(f"Error saving query to history: {e}", exc_info=True)
                
                # Save readline history
                if histfile:
                    try:
                        readline.write_history_file(histfile)
                    except Exception as e:
                        logger.error(f"Error saving readline history: {e}", exc_info=True)

                # Load existing results for this query
                try:
                    cached_data = load_cached_results(user_input)
                except Exception as e:
                    logger.error(f"Error loading cached results: {e}", exc_info=True)
                    cached_data = {
                        'query': user_input,
                        'available_domains': [],
                        'unavailable_domains': [],
                        'searches': []
                    }
                
                # Show existing available domains if any
                if cached_data['available_domains']:
                    print("\nPreviously found available domains:")
                    display_top_domains(cached_data['available_domains'])
                    print("\nGenerating additional suggestions...")

                available_domains = []
                unavailable_domains = []

                while True:
                    try:
                        # Start with all previously known domains to avoid duplicates
                        known_domains = cached_data['available_domains'] + cached_data['unavailable_domains']
                        
                        # Get maximum allowed domain length based on existing domains
                        max_length = get_max_domain_length(known_domains)
                        
                        prompt = (
                            f"Generate 20 unique and creative domain name suggestions, with 2 words, "
                            f"based on the following idea: {user_input}. "
                            f"Each domain must be no longer than {max_length} characters including '.org'. "
                            f"Generate domains with the .org extension (e.g., example.org). "
                            f"IMPORTANT: The domain name will be HEARD by the audience (spoken aloud), not just read. "
                            f"They need to remember it for a few minutes before typing it into their browser. "
                            f"Therefore, domains must be: "
                            f"(1) Easily remembered when heard - use simple, memorable words "
                            f"(2) Easy to spell correctly - avoid complex spellings, homophones, or words that sound similar to other common words "
                            f"(3) Phonetically clear - the spelling should be obvious from how it sounds "
                            f"(4) Not easily confused - avoid domains that sound like other common words or domains "
                            f"(5) Easy to remember for non-native English speakers - use common English words, avoid idioms, slang, or culturally specific references "
                            f"(6) Avoid plural forms if possible - prefer singular nouns to make the domain simpler and easier to remember "
                            f"(7) Consider using pinyin romanization when appropriate - the audience may prefer pinyin-based words in the domain name."
                        )
                        if known_domains:
                            prompt += f"\nPlease avoid these existing domains: {', '.join(known_domains)}"
                        
                        try:
                            domain_suggestions = openai_helper.generate_domain_names(prompt)
                            logger.info(f"Generated {len(domain_suggestions)} domain suggestions")
                        except Exception as e:
                            logger.error(f"Error generating domain names: {e}", exc_info=True)
                            print(f"\nError generating domain suggestions: {e}")
                            break
                        
                        print("\nChecking domain availability...")
                        check_domains_batch(domain_suggestions, known_domains, available_domains, unavailable_domains, max_length)

                        while not available_domains:
                            print("\nNo new available domains found. Generating more suggestions...")
                            all_unavailable = known_domains + unavailable_domains
                            new_prompt = (
                                f"{prompt} Please avoid these already taken domains: {', '.join(all_unavailable)}. "
                                f"Remember to keep domains under {max_length} characters, and prioritize "
                                f"domains that are easily remembered and spelled correctly when heard, "
                                f"especially for non-native English speakers. Prefer singular forms over plural when possible. "
                                f"Consider using pinyin romanization when it would help the audience remember the domain."
                            )
                            try:
                                new_domain_suggestions = openai_helper.generate_domain_names(new_prompt)
                                logger.info(f"Generated {len(new_domain_suggestions)} additional domain suggestions")
                            except Exception as e:
                                logger.error(f"Error generating additional domain names: {e}", exc_info=True)
                                print(f"\nError generating additional suggestions: {e}")
                                break
                            
                            print("\nChecking new suggestions...")
                            check_domains_batch(new_domain_suggestions, all_unavailable, available_domains, unavailable_domains, max_length)

                        if available_domains:
                            print("\nNewly found available domains:")
                            display_top_domains(available_domains)

                            print(f"\nNumber of unavailable domains in this search: {len(unavailable_domains)}")

                            # Save domains to cache
                            try:
                                cache_file = save_domains_to_cache(user_input, available_domains, unavailable_domains, cached_data)
                                print(f"\nDomain search results saved to: {cache_file}")
                            except Exception as e:
                                logger.error(f"Error saving domains to cache: {e}", exc_info=True)

                            # Show total available domains after this search
                            all_available = cached_data['available_domains'] + available_domains
                            print(f"\nTotal available domains found so far: {len(all_available)}")
                            display_top_domains(all_available)

                        print("\nWould you like to generate more ideas based on these results?")
                        print("Enter 'y' for yes or 'n' for no:")
                        user_choice = input("> ").lower()
                        if histfile:
                            try:
                                readline.write_history_file(histfile)
                            except Exception as e:
                                logger.error(f"Error saving readline history: {e}", exc_info=True)
                        if user_choice in ['n', 'no']:
                            break
                    except KeyboardInterrupt:
                        logger.info("User interrupted with Ctrl+C")
                        raise
                    except Exception as e:
                        logger.error(f"Error in domain generation loop: {e}", exc_info=True)
                        print(f"\nAn error occurred: {e}")
                        print("Please try again or type 'quit' to exit.")
                        break
            except KeyboardInterrupt:
                print("\n\nThank you for using the Domain Name Finder. Goodbye!")
                logger.info("User interrupted with Ctrl+C")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                print(f"\nAn unexpected error occurred: {e}")
                print("Please try again or type 'quit' to exit.")
    except Exception as e:
        logger.critical(f"Fatal error in main: {e}", exc_info=True)
        print(f"\nFatal error: {e}")
        print(f"Check log file for details: {log_file}")


if __name__ == "__main__":
    main()
