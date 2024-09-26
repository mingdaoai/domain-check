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
        print("\nWhat's your idea for a domain name? (or type 'quit' to exit):")
        user_input = input("> ")

        if user_input.lower() == 'quit':
            print("Thank you for using the Domain Name Finder. Goodbye!")
            break

        available_domains = []
        unavailable_domains = []

        while True:
            prompt = f"Generate 20 unique and creative domain name suggestions, with 2 words, based on the following idea: {user_input}."
            domain_suggestions = openai_helper.generate_domain_names(prompt)

            for domain in domain_suggestions:
                if check_domain_availability(domain):
                    available_domains.append(domain)
                else:
                    unavailable_domains.append(domain)

            while not available_domains:
                print("\nNo available domains found. Generating new suggestions...")
                unavailable_domains_str = ", ".join(unavailable_domains)
                new_prompt = f"{prompt}. Please avoid these already taken domains: {unavailable_domains_str}"
                new_domain_suggestions = openai_helper.generate_domain_names(new_prompt)

                available_domains = []
                unavailable_domains = []

                for domain in new_domain_suggestions:
                    if check_domain_availability(domain):
                        available_domains.append(domain)
                    else:
                        unavailable_domains.append(domain)

            print("\nAvailable domains:")
            #ranked_domains = openai_helper.rank_domain_names(available_domains)
            ranked_domains = sorted(available_domains, key=len)
            for rank, domain in enumerate(ranked_domains, 1):
                print(f"{rank}. {domain}")

            print(f"\nNumber of unavailable domains: {len(unavailable_domains)}")


            print("\nWould you like to generate more ideas based on these results?")
            print("Enter 'y' for yes or 'n' for no:")
            user_choice = input("> ").lower()
            if user_choice in ['n', 'no']:
                break


if __name__ == "__main__":
    main()
