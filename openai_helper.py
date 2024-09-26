from openai import OpenAI

class OpenAIHelper:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)

    def generate_domain_names(self, user_input):
        assert "domain" in user_input, "User input must contain the word 'domain'"
        print("Generating domain names...")
        prompt = (f"{user_input}."
                  f" Provide the domain names in a JSON format, with a key 'domain_names' and value of an array"
                  f" and each suggestion as a string in the array.")

        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates creative domain name suggestions in JSON format."},
                {"role": "user", "content": prompt}
            ]
        )

        import json
        import re

        message_content = response.choices[0].message.content
        #print("Debug - Message content:", message_content)

        message_content = message_content.strip().replace("\n", "")
        
        # Use regex to find the JSON part enclosed in curly braces
        json_match = re.search(r'\{.*\}', message_content, re.DOTALL)
        if json_match:
            json_content = json_match.group()
            domain_suggestions = json.loads(json_content)
        else:
            domain_suggestions = {"domain_names": []}  # Fallback to empty list if no JSON found
        
        return domain_suggestions['domain_names']

    def rank_domain_names(self, domain_names):
        prompt = (f"Rank these domain names from easiest to hardest to remember, providing a brief explanation for each: {', '.join(domain_names)}"
                  f" Provide the rankings in a JSON format, with a key 'rankings' and value of an array"
                  f" and each suggestion as a string in the array.")

        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that ranks domain names based on memorability."},
                {"role": "user", "content": prompt}
            ]
        )

        rankings = response.choices[0].message.content
        import json
        import re

        # Strip whitespace and remove newlines from the response
        rankings_content = rankings.strip().replace("\n", "")
        
        # Use regex to find the JSON part enclosed in curly braces
        json_match = re.search(r'\{.*\}', rankings_content, re.DOTALL)
        if json_match:
            json_content = json_match.group()
            rankings_dict = json.loads(json_content)
        else:
            rankings_dict = {"rankings": []}  # Fallback to empty list if no JSON found
        
        rankings = rankings_dict['rankings']
        return rankings 
