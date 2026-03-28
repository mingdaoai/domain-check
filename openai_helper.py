import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

class OpenAIHelper:
    def __init__(self, api_key):
        try:
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com"
            )
            logger.info("DeepSeek client initialized")
        except Exception as e:
            logger.error(f"Error initializing DeepSeek client: {e}", exc_info=True)
            raise

    def generate_domain_names(self, user_input):
        try:
            assert "domain" in user_input, "User input must contain the word 'domain'"
            print("Generating domain names...")
            logger.debug(f"Generating domain names with prompt length: {len(user_input)}")
            prompt = (f"{user_input}."
                      f" Provide the domain names in a JSON format, with a key 'domain_names' and value of an array"
                      f" and each suggestion as a string in the array."
                      f" Include the .com extension in each domain name (e.g., example.com).")

            try:
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    max_tokens=4096,
                    temperature=0.7,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that generates creative domain name suggestions in JSON format. "
                           "When generating domains, prioritize names that are easy to remember and spell correctly "
                           "when heard by an audience, as they need to recall the domain name after hearing it spoken. "
                           "Consider international audiences - use simple, common English words that are accessible "
                           "to non-native English speakers. Prefer singular forms over plural when possible to make "
                           "domains simpler and easier to remember. The audience may prefer pinyin romanization in domain names, "
                           "so consider incorporating pinyin-based words when appropriate."},
                        {"role": "user", "content": prompt}
                    ]
                )
                logger.debug("Received response from DeepSeek API")
            except Exception as e:
                logger.error(f"Error calling DeepSeek API: {e}", exc_info=True)
                raise

            import json
            import re

            try:
                message_content = response.choices[0].message.content
                if message_content is None:
                    message_content = ""
                logger.debug(f"Response content length: {len(message_content)}")
            except (IndexError, AttributeError) as e:
                logger.error(f"Error accessing response content: {e}. Response structure: {response}", exc_info=True)
                raise

            message_content = message_content.strip().replace("\n", "")
            
            # Use regex to find the JSON part enclosed in curly braces
            json_match = re.search(r'\{.*\}', message_content, re.DOTALL)
            if json_match:
                json_content = json_match.group()
                try:
                    domain_suggestions = json.loads(json_content)
                    logger.debug(f"Successfully parsed JSON with {len(domain_suggestions.get('domain_names', []))} domains")
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON from response: {e}. Content: {message_content[:500]}", exc_info=True)
                    domain_suggestions = {"domain_names": []}
            else:
                logger.warning(f"No JSON pattern found in response. Content: {message_content[:500]}")
                domain_suggestions = {"domain_names": []}  # Fallback to empty list if no JSON found
            
            result = domain_suggestions.get('domain_names', [])
            logger.info(f"Generated {len(result)} domain suggestions")
            return result
        except Exception as e:
            logger.error(f"Error in generate_domain_names: {e}", exc_info=True)
            raise

    def rank_domain_names(self, domain_names):
        try:
            logger.debug(f"Ranking {len(domain_names)} domain names")
            prompt = (f"Rank these domain names from easiest to hardest to remember, providing a brief explanation for each: {', '.join(domain_names)}"
                      f" Provide the rankings in a JSON format, with a key 'rankings' and value of an array"
                      f" and each suggestion as a string in the array.")

            try:
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    max_tokens=4096,
                    temperature=0.7,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that ranks domain names based on memorability."},
                        {"role": "user", "content": prompt}
                    ]
                )
            except Exception as e:
                logger.error(f"Error calling DeepSeek API for ranking: {e}", exc_info=True)
                raise

            try:
                rankings = response.choices[0].message.content
                if rankings is None:
                    rankings = ""
                logger.debug(f"Ranking response length: {len(rankings)}")
            except (IndexError, AttributeError) as e:
                logger.error(f"Error accessing ranking response content: {e}. Response: {response}", exc_info=True)
                raise

            import json
            import re

            # Strip whitespace and remove newlines from the response
            rankings_content = rankings.strip().replace("\n", "")
            
            # Use regex to find the JSON part enclosed in curly braces
            json_match = re.search(r'\{.*\}', rankings_content, re.DOTALL)
            if json_match:
                json_content = json_match.group()
                try:
                    rankings_dict = json.loads(json_content)
                    logger.debug(f"Successfully parsed ranking JSON")
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing ranking JSON: {e}. Content: {rankings_content[:500]}", exc_info=True)
                    rankings_dict = {"rankings": []}
            else:
                logger.warning(f"No JSON pattern found in ranking response. Content: {rankings_content[:500]}")
                rankings_dict = {"rankings": []}  # Fallback to empty list if no JSON found
            
            result = rankings_dict.get('rankings', [])
            logger.info(f"Ranked {len(result)} domain names")
            return result
        except Exception as e:
            logger.error(f"Error in rank_domain_names: {e}", exc_info=True)
            raise 
