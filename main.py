import os
from openai_helper import OpenAIHelper
from domain_checker import check_domain_availability
from utils import load_api_key

def main():
    api_key = load_api_key()
    if not api_key:
        print("Error: OpenAI API key not found. Please add it to ~/.mingdaoai/openai.key")
        return

    openai_helper = OpenAIHelper(api_key)

    print("Welcome to the Domain Name Finder!")
    print("Share your ideas for domain names, and I'll help you find unique options.")

    while True:
        user_input = input("\nWhat's your idea for a domain name? (or type 'quit' to exit):\n")
        
        if user_input.lower() == 'quit':
            print("Thank you for using the Domain Name Finder. Goodbye!")
            break

        domain_suggestions = openai_helper.generate_domain_names(user_input)
        
        available_domains = []
        unavailable_domains = []

        for domain in domain_suggestions:
            if check_domain_availability(domain):
                available_domains.append(domain)
            else:
                unavailable_domains.append(domain)

        print("\nAvailable domains:")
        for domain in available_domains:
            print(f"- {domain}")

        print("\nUnavailable domains:")
        for domain in unavailable_domains:
            print(f"- {domain} (not available)")

        print("\nWould you like to generate more ideas based on these results?")

if __name__ == "__main__":
    main()