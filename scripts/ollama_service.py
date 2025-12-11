"""
Ollama Service for MLEX
Provides word query and WSD functionality using Ollama (Sailor2:20b)
"""

import requests
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class WordSense:
    """Represents a single word sense"""
    sense_id: str
    definition: str
    examples: Optional[Tuple[str, ...]] = None


class OllamaService:
    """Service for interacting with Ollama API"""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "sailor2:8b"):
        """
        Initialize Ollama service

        Args:
            base_url: Ollama API base URL
            model: Model name to use (default: sailor2:20b)
        """
        self.base_url = base_url
        self.model = model
        self.api_url = f"{base_url}/api/generate"

    def _generate(self, prompt: str, temperature: float = 0.7) -> Optional[str]:
        """
        Generate text using Ollama API

        Args:
            prompt: The prompt to send to the model
            temperature: Temperature for generation (0.0 to 1.0)

        Returns:
            Generated text or None if failed
        """
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "temperature": temperature,
                "options": {
                    "num_predict": 2000
                }
            }

            response = requests.post(
                self.api_url,
                json=payload,
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                print(f"Error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"Ollama API error: {e}")
            return None

    def query_word(self, word: str) -> Optional[Dict]:
        """
        Query word information using Ollama

        Args:
            word: The Malay word to query

        Returns:
            Dictionary with word information or None if failed
        """
        prompt = f"""Provide Malay dictionary information for "{word}" in STRICT JSON format.

Return ONLY this JSON structure with NO comments, NO explanations, NO extra text:

{{"entry":"{word}","rootWrd":"","fonetik":"","pos":"","label":"","definitions":[{{"index":"1","definition":"","example":""}}],"asal":"","domain":"","sinonim":""}}

Rules:
- Use ONLY the exact keys shown above
- ALL values must be strings (use "" for empty)
- For definitions array: provide 1-3 items with index as string "1", "2", "3"
- Use ONLY Malay language for values (NOT English, NOT Chinese)
- Do NOT add comments like (kata dasar), (base form), etc.
- Do NOT add extra punctuation at end of values
- For sinonim: use semicolon separator like "kata1; kata2; kata3"
- If not a valid Malay word: {{"error":"Not a valid Malay word"}}

Return the JSON object ONLY, nothing else."""

        # Try with retry logic (max 2 attempts)
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                # Use lower temperature for more consistent output
                response_text = self._generate(prompt, temperature=0.1)

                if not response_text:
                    print(f"[ERROR] No response from Ollama (attempt {attempt + 1})")
                    if attempt == max_attempts - 1:
                        return {"error": "No response from Ollama service"}
                    continue

                # Clean up the response
                response_text = response_text.strip()

                # Remove markdown code blocks if present
                if '```json' in response_text:
                    response_text = response_text.split('```json')[1].split('```')[0].strip()
                elif '```' in response_text:
                    response_text = response_text.split('```')[1].split('```')[0].strip()

                # Try to find JSON object in the response
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}')

                if start_idx != -1 and end_idx != -1:
                    json_str = response_text[start_idx:end_idx+1]

                    # Comprehensive JSON cleaning
                    import re

                    # 1. Convert numeric index to string: "index": 1 -> "index": "1"
                    json_str = re.sub(r'"index":\s*(\d+)', r'"index": "\1"', json_str)

                    # 2. Remove ALL parenthetical content FIRST (most aggressive)
                    #    Removes: (kata dasar), (base form), (Chinese), etc.
                    json_str = re.sub(r'\([^)]*\)', '', json_str)

                    # 3. Remove inline comments after quotes: "value" // comment
                    json_str = re.sub(r'"\s*//[^\n]*', '"', json_str)

                    # 4. Fix trailing semicolons: "value;" -> "value"
                    json_str = re.sub(r';+\s*"', '"', json_str)

                    # 5. Fix trailing periods/commas inside quotes: "value." -> "value"
                    json_str = re.sub(r'\.+\s*"(\s*[,}\]])', r'"\1', json_str)

                    # 6. Remove extra whitespace inside strings
                    json_str = re.sub(r'"\s+', '"', json_str)
                    json_str = re.sub(r'\s+"', '"', json_str)

                    # 7. Fix extra commas before closing braces/brackets
                    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

                    # 8. Fix any double commas
                    json_str = re.sub(r',\s*,+', ',', json_str)

                    # 9. Fix missing commas between objects
                    json_str = re.sub(r'}\s*{', '},{', json_str)

                    # 10. Remove newlines and extra spaces
                    json_str = ' '.join(json_str.split())

                    word_info = json.loads(json_str)

                    # Success! Return the result
                    if attempt > 0:
                        print(f"[SUCCESS] Parsed on attempt {attempt + 1}")
                    return word_info
                else:
                    print(f"[ERROR] No JSON found in response (attempt {attempt + 1})")
                    if attempt == max_attempts - 1:
                        return {"error": "Invalid response format from Ollama"}

            except json.JSONDecodeError as e:
                # JSON parsing failed
                error_msg = f"JSON decode error at position {e.pos}: {e.msg}"
                print(f"[ERROR] {error_msg} (attempt {attempt + 1}/{max_attempts})")

                try:
                    if 'response_text' in locals():
                        print(f"[ERROR] Response length: {len(response_text)} chars")

                    # Save failed JSON for debugging (only on last attempt)
                    if attempt == max_attempts - 1 and 'json_str' in locals():
                        try:
                            with open("ollama_failed.txt", "w", encoding="utf-8") as f:
                                f.write(json_str)
                            print(f"[DEBUG] Failed JSON saved to ollama_failed.txt")
                        except:
                            pass
                except:
                    pass

                # If this was the last attempt, return error
                if attempt == max_attempts - 1:
                    return {"error": "Failed to parse Ollama response"}

                # Otherwise, retry
                print(f"[INFO] Retrying...")
                continue

            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}"
                print(f"[ERROR] {error_msg} (attempt {attempt + 1})")

                if attempt == max_attempts - 1:
                    return {"error": f"Ollama query failed: {error_msg}"}

                print(f"[INFO] Retrying...")
                continue

        # Should not reach here, but just in case
        return {"error": "Unexpected error in query_word"}

    def disambiguate(
        self,
        word: str,
        context: str,
        candidate_senses: Tuple[WordSense, ...]
    ) -> List[Dict]:
        """
        Perform Word Sense Disambiguation

        Args:
            word: The target word to disambiguate
            context: The sentence/context containing the word
            candidate_senses: Tuple of possible word senses

        Returns:
            List of sense results sorted by confidence
        """
        # Build the prompt with all candidate senses
        senses_text = "\n".join([
            f"Sense {i+1} (ID: {sense.sense_id}): {sense.definition}"
            for i, sense in enumerate(candidate_senses)
        ])

        prompt = f"""You are a Malay language expert. Analyze which meaning of the word "{word}" is used in this context.

Context: {context}

Candidate meanings:
{senses_text}

Task: Rank all meanings by relevance to the context. For each meaning, provide:
1. The sense ID
2. A confidence score (0-100)
3. A brief reasoning

Return ONLY a valid JSON array with this structure (no markdown, no explanation):
[
    {{
        "sense_id": "the_sense_id",
        "definition": "the definition text",
        "confidence": 85,
        "reasoning": "why this meaning fits the context"
    }}
]

Return all candidate meanings ranked from most to least relevant."""

        try:
            response_text = self._generate(prompt, temperature=0.2)

            if not response_text:
                # Return default ranking if API fails
                return self._default_ranking(candidate_senses)

            # Clean up the response
            response_text = response_text.strip()

            # Remove markdown code blocks if present
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()

            # Try to find JSON array in the response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']')

            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx+1]

                # Clean JSON string
                json_str = self._clean_json_for_wsd(json_str)

                results = json.loads(json_str)

                # Validate and sort by confidence
                valid_results = []
                for result in results:
                    if 'sense_id' in result and 'confidence' in result:
                        # Ensure definition is present
                        if 'definition' not in result:
                            result['definition'] = "No definition provided"
                        if 'reasoning' not in result:
                            result['reasoning'] = "No reasoning provided"
                        valid_results.append(result)

                valid_results.sort(key=lambda x: x['confidence'], reverse=True)
                return valid_results if valid_results else self._default_ranking(candidate_senses)
            else:
                print(f"No JSON array found in response: {response_text[:200]}")
                return self._default_ranking(candidate_senses)

        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Response text: {response_text[:500]}")
            return self._default_ranking(candidate_senses)
        except Exception as e:
            print(f"Error in WSD: {e}")
            return self._default_ranking(candidate_senses)

    def _clean_json_for_wsd(self, json_str: str) -> str:
        """
        Clean JSON string to fix common issues from LLM responses

        Args:
            json_str: Raw JSON string

        Returns:
            Cleaned JSON string
        """
        import re

        # Remove any trailing commas before closing braces or brackets
        # This fixes: {"key": "value",} -> {"key": "value"}
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

        # Fix incomplete objects at the end by closing them properly
        # Count opening and closing braces/brackets
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        open_brackets = json_str.count('[')
        close_brackets = json_str.count(']')

        # If there are unclosed objects, try to close them
        if open_braces > close_braces:
            json_str += '}' * (open_braces - close_braces)
        if open_brackets > close_brackets:
            json_str += ']' * (open_brackets - close_brackets)

        # Remove incomplete JSON objects at the end
        # Look for incomplete objects after the last complete object
        last_complete = -1
        bracket_count = 0
        brace_count = 0
        in_string = False
        escape_next = False

        for i, char in enumerate(json_str):
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue

            if char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
            elif char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1

            # If we're back to balanced, mark this as last complete position
            if bracket_count == 0 and brace_count == 0 and i > 0:
                last_complete = i

        # Truncate to last complete structure if we found one
        if last_complete > 0 and last_complete < len(json_str) - 1:
            json_str = json_str[:last_complete + 1]

        # Remove any trailing non-JSON characters
        json_str = re.sub(r'[^}\]]*$', '', json_str)

        return json_str

    def _default_ranking(self, candidate_senses: Tuple[WordSense, ...]) -> List[Dict]:
        """Return default ranking when API fails"""
        return [
            {
                "sense_id": sense.sense_id,
                "definition": sense.definition,
                "confidence": 50.0,
                "reasoning": "Default ranking (API unavailable)"
            }
            for sense in candidate_senses
        ]

    def test_connection(self) -> bool:
        """
        Test if Ollama service is available

        Returns:
            True if service is accessible, False otherwise
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False


# Test function
if __name__ == "__main__":
    service = OllamaService()

    print("Testing Ollama connection...")
    if service.test_connection():
        print("[OK] Connected to Ollama")

        print("\nTesting word query...")
        result = service.query_word("makan")
        if result:
            print("[OK] Word query successful!")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("[ERROR] Word query failed")
    else:
        print("[ERROR] Cannot connect to Ollama. Make sure it's running.")
