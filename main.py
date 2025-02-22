import os
import readline
import json
import time
from datetime import datetime
from openai_helper import OpenAIHelper
from domain_checker import check_domain_availability
from utils import load_api_key


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
        except (json.JSONDecodeError, KeyError):
            return []
    return []


def save_query_history(queries):
    queries_file = get_queries_file_path()
    with open(queries_file, 'w') as f:
        json.dump({'queries': queries}, f, indent=2)


def setup_readline_history():
    # Set up readline with custom history file in .cache directory
    histfile = os.path.join(get_cache_dir(), ".domain_finder_history")
    try:
        readline.read_history_file(histfile)
    except FileNotFoundError:
        pass
    
    readline.set_history_length(1000)
    
    # Load past queries into readline history
    queries = load_query_history()
    for query in queries:
        readline.add_history(query)
    
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
                return data
        except (json.JSONDecodeError, KeyError):
            # If cache file is corrupted, return empty results
            pass
    return {
        'query': query,
        'available_domains': [],
        'unavailable_domains': [],
        'searches': []
    }


def save_domains_to_cache(query, available_domains, unavailable_domains, existing_data=None):
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
    
    return cache_file


def check_domain_with_backoff(domain, base_delay=2, max_retries=3):
    """Check domain availability with exponential backoff on failure"""
    for attempt in range(max_retries):
        try:
            # Add base delay between each domain check
            time.sleep(base_delay)
            return check_domain_availability(domain)
        except Exception as e:
            if attempt < max_retries - 1:  # Don't sleep on the last attempt
                # Exponential backoff: 2s, 4s, 8s, etc.
                retry_delay = base_delay * (2 ** attempt)
                print(f"\nError checking {domain}, retrying in {retry_delay}s... ({str(e)})")
                time.sleep(retry_delay)
            else:
                print(f"\nFailed to check {domain} after {max_retries} attempts: {str(e)}")
                return False  # Assume domain is unavailable on repeated failure
    return False


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
            if check_domain_with_backoff(domain):
                available_list.append(domain)
                print(f"✓ {domain} is available!")
            else:
                unavailable_list.append(domain)
                print(f"✗ {domain} is taken or error occurred")


def display_top_domains(all_domains, limit=20):
    """Display the top shortest domains, sorted alphabetically"""
    # Deduplicate domains while preserving order
    unique_domains = list(dict.fromkeys(all_domains))
    
    # Sort domains first by length, then alphabetically
    sorted_domains = sorted(unique_domains, key=lambda x: (len(x), x))
    top_domains = sorted_domains[:limit]
    
    if not top_domains:
        print("\nNo domains to display.")
        return
    
    print(f"\nTop {min(limit, len(top_domains))} shortest domains (sorted alphabetically):")
    for rank, domain in enumerate(top_domains, 1):
        print(f"{rank:2d}. {domain} ({len(domain)} chars)")
    
    if len(unique_domains) > limit:
        print(f"\n... and {len(unique_domains) - limit} more domains")


def main():
    api_key = load_api_key()
    if not api_key:
        print("Error: OpenAI API key not found. Please add it to ~/.mingdaoai/openai.key")
        return

    openai_helper = OpenAIHelper(api_key)

    print("Welcome to the Domain Name Finder!")
    print("Share your ideas for domain names, and I'll help you find unique options.")
    print("Use UP/DOWN arrow keys to browse through your previous queries.")

    # Set up readline with history
    histfile = setup_readline_history()
    
    # Load existing query history
    queries = load_query_history()

    while True:
        print("\nWhat's your idea for a domain name? (or type 'quit' to exit):")
        user_input = input("> ")
        
        if user_input.lower() == 'quit':
            print("Thank you for using the Domain Name Finder. Goodbye!")
            break

        # Save query to history if it's new
        if user_input not in queries:
            queries.append(user_input)
            save_query_history(queries)
            readline.add_history(user_input)
        
        # Save readline history
        readline.write_history_file(histfile)

        # Load existing results for this query
        cached_data = load_cached_results(user_input)
        
        # Show existing available domains if any
        if cached_data['available_domains']:
            print("\nPreviously found available domains:")
            display_top_domains(cached_data['available_domains'])
            print("\nGenerating additional suggestions...")

        available_domains = []
        unavailable_domains = []

        while True:
            # Start with all previously known domains to avoid duplicates
            known_domains = cached_data['available_domains'] + cached_data['unavailable_domains']
            
            # Get maximum allowed domain length based on existing domains
            max_length = get_max_domain_length(known_domains)
            
            prompt = (
                f"Generate 20 unique and creative domain name suggestions, with 2 words, "
                f"based on the following idea: {user_input}. "
                f"Each domain must be no longer than {max_length} characters including '.com'."
            )
            if known_domains:
                prompt += f"\nPlease avoid these existing domains: {', '.join(known_domains)}"
            
            domain_suggestions = openai_helper.generate_domain_names(prompt)
            print("\nChecking domain availability...")
            check_domains_batch(domain_suggestions, known_domains, available_domains, unavailable_domains, max_length)

            while not available_domains:
                print("\nNo new available domains found. Generating more suggestions...")
                all_unavailable = known_domains + unavailable_domains
                new_prompt = (
                    f"{prompt}. Please avoid these already taken domains: {', '.join(all_unavailable)}. "
                    f"Remember to keep domains under {max_length} characters."
                )
                new_domain_suggestions = openai_helper.generate_domain_names(new_prompt)
                
                print("\nChecking new suggestions...")
                check_domains_batch(new_domain_suggestions, all_unavailable, available_domains, unavailable_domains, max_length)

            if available_domains:
                print("\nNewly found available domains:")
                display_top_domains(available_domains)

                print(f"\nNumber of unavailable domains in this search: {len(unavailable_domains)}")

                # Save domains to cache
                cache_file = save_domains_to_cache(user_input, available_domains, unavailable_domains, cached_data)
                print(f"\nDomain search results saved to: {cache_file}")

                # Show total available domains after this search
                all_available = cached_data['available_domains'] + available_domains
                print(f"\nTotal available domains found so far: {len(all_available)}")
                display_top_domains(all_available)

            print("\nWould you like to generate more ideas based on these results?")
            print("Enter 'y' for yes or 'n' for no:")
            user_choice = input("> ").lower()
            readline.write_history_file(histfile)
            if user_choice in ['n', 'no']:
                break


if __name__ == "__main__":
    main()
