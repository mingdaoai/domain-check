from openai import OpenAI

class OpenAIHelper:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)

    def generate_domain_names(self, user_input):
        prompt = f"Generate 5 unique and creative domain name suggestions based on the following idea: {user_input}. Only provide the domain names, separated by commas."

        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates creative domain name suggestions."},
                {"role": "user", "content": prompt}
            ]
        )

        domain_suggestions = response.choices[0].message.content.split(',')
        return [domain.strip() for domain in domain_suggestions]