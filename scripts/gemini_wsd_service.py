"""
MLEX - Interactive Word Sense Disambiguation Tool
"""

import os
import json
from typing import List, Dict, Optional, Tuple
import google.generativeai as genai
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WordSense:
    """Word sense data structure"""
    sense_id: str
    definition: str
    examples: tuple = None
    confidence: float = 0.0


class GeminiWSDService:
    """Word Sense Disambiguation using Google Gemini"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        
        if not self.api_key:
            raise ValueError(
                "Gemini API key required!\n"
                "Please set: export GEMINI_API_KEY='your-key'"
            )
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        self.generation_config = {
            'temperature': 0.2,
            'top_p': 0.95,
            'top_k': 40,
            'max_output_tokens': 1024,
        }
        
        self.safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    
    def disambiguate(
        self, 
        word: str, 
        context: str, 
        candidate_senses: tuple
    ) -> List[Dict]:
        """Word sense disambiguation"""
        
        prompt = self._build_simple_prompt(word, context, candidate_senses)
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config,
                safety_settings=self.safety_settings
            )
            
            if not response or not response.candidates:
                return self._get_fallback_result(candidate_senses)
            
            candidate = response.candidates[0]
            if candidate.finish_reason != 1:
                return self._get_fallback_result(candidate_senses)
            
            try:
                response_text = response.text
            except (ValueError, AttributeError):
                return self._get_fallback_result(candidate_senses)
            
            result = self._parse_response(response_text, candidate_senses)
            return result if result else self._get_fallback_result(candidate_senses)
            
        except Exception as e:
            logger.error(f"API error: {e}")
            return self._get_fallback_result(candidate_senses)
    
    def _build_simple_prompt(self, word: str, context: str, senses: tuple) -> str:
        """Build prompt"""
        sense_list = []
        for sense in senses:
            sense_list.append(f'{{"{sense.sense_id}": "{sense.definition}"}}')
        
        senses_json = ",\n".join(sense_list)
        
        prompt = f"""Word: {word}
Context: {context}

Senses: [{senses_json}]

Rank by relevance (0-100). Return JSON:
{{"results": [{{"id": "...", "score": 90, "reason": "..."}}]}}"""
        
        return prompt
    
    def _parse_response(self, text: str, senses: tuple) -> Optional[List[Dict]]:
        """Parse response"""
        try:
            text = text.strip()
            text = text.replace('```json', '').replace('```', '').strip()
            
            data = json.loads(text)
            results = data.get('results', data.get('rankings', []))
            
            if not results:
                return None
            
            output = []
            for r in results:
                sense_id = r.get('id', r.get('sense_id', ''))
                
                definition = ""
                for sense in senses:
                    if sense.sense_id == sense_id:
                        definition = sense.definition
                        break
                
                output.append({
                    'sense_id': sense_id,
                    'definition': definition or r.get('definition', ''),
                    'confidence': float(r.get('score', r.get('confidence', 0))),
                    'reasoning': r.get('reason', r.get('reasoning', ''))
                })
            
            total = sum(r['confidence'] for r in output)
            if total > 0:
                for r in output:
                    r['confidence'] = (r['confidence'] / total) * 100
            
            return output
            
        except Exception:
            return None
    
    def _get_fallback_result(self, senses: tuple) -> List[Dict]:
        """Fallback result"""
        n = len(senses)
        confidence = 100.0 / n if n > 0 else 0
        
        return [
            {
                'sense_id': sense.sense_id,
                'definition': sense.definition,
                'confidence': confidence,
                'reasoning': 'Unable to get AI analysis'
            }
            for sense in senses
        ]
    
    def find_common_words(self, sentence1: str, sentence2: str) -> List[str]:
        """Find common words between two sentences"""
        words1 = set(sentence1.lower().split())
        words2 = set(sentence2.lower().split())
        
        # Remove punctuation
        import string
        words1 = {w.strip(string.punctuation) for w in words1}
        words2 = {w.strip(string.punctuation) for w in words2}
        
        # Find intersection
        common = words1 & words2
        
        # Filter out words that are too short (likely stopwords)
        common = {w for w in common if len(w) > 2}
        
        return list(common)
    
    def analyze_word_in_contexts(
        self, 
        word: str, 
        context1: str, 
        context2: str
    ) -> Dict:
        """Analyze the same word in two different contexts"""
        
        prompt = f"""Analyze the word "{word}" in two different contexts.

Context 1: {context1}
Context 2: {context2}

Task:
1. Determine if "{word}" has different meanings in these contexts
2. If different, explain each meaning
3. Rate confidence (0-100)

Return JSON:
{{
    "word": "{word}",
    "are_different": true/false,
    "context1_meaning": "meaning description",
    "context2_meaning": "meaning description", 
    "confidence": 85,
    "explanation": "why they are different or same"
}}"""
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config,
                safety_settings=self.safety_settings
            )
            
            if not response or not response.candidates:
                return None
            
            if response.candidates[0].finish_reason != 1:
                return None
            
            text = response.text.strip()
            text = text.replace('```json', '').replace('```', '').strip()
            
            result = json.loads(text)
            return result
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return None


# ==================== Neo4j Connection ====================

class Neo4jConnection:
    """Connect to Neo4j to get word senses"""
    
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="mlex2025"):
        try:
            from neo4j import GraphDatabase
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.connected = True
        except Exception as e:
            logger.warning(f"⚠️  Neo4j connection failed: {e}")
            logger.warning("   Will use mock data")
            self.connected = False
    
    def get_word_senses(self, word: str) -> List[WordSense]:
        """Get word senses from Neo4j"""
        if not self.connected:
            return self._get_mock_senses(word)
        
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (w:Word {entry: $word})-[:HAS_SENSE]->(s:Sense)
                    RETURN s.sense_id as sense_id,
                           s.definition as definition
                    ORDER BY s.sense_index
                    LIMIT 5
                """, word=word)
                
                senses = []
                for record in result:
                    senses.append(WordSense(
                        sense_id=record['sense_id'],
                        definition=record['definition']
                    ))
                
                return senses if senses else self._get_mock_senses(word)
        
        except Exception as e:
            logger.warning(f"Query failed: {e}")
            return self._get_mock_senses(word)
    
    def _get_mock_senses(self, word: str) -> List[WordSense]:
        """Mock data (when Neo4j is unavailable)"""
        mock_data = {
            'makan': [
                WordSense('makan_1', 'to eat food'),
                WordSense('makan_2', 'to consume resources'),
                WordSense('makan_3', 'to corrode or erode'),
            ],
            'main': [
                WordSense('main_1', 'to play'),
                WordSense('main_2', 'to perform or act'),
                WordSense('main_3', 'to play musical instrument'),
            ],
            'buah': [
                WordSense('buah_1', 'fruit'),
                WordSense('buah_2', 'classifier for large objects'),
            ],
            'kena': [
                WordSense('kena_1', 'must or have to'),
                WordSense('kena_2', 'to be affected by'),
                WordSense('kena_3', 'to hit or strike'),
            ]
        }
        
        if word.lower() in mock_data:
            return mock_data[word.lower()]
        else:
            return [
                WordSense(f'{word}_1', f'meaning 1 of {word}'),
                WordSense(f'{word}_2', f'meaning 2 of {word}'),
            ]
    
    def close(self):
        if self.connected:
            self.driver.close()


# ==================== Interactive Interface ====================

class InteractiveWSD:
    """Interactive WSD Tool"""
    
    def __init__(self):
        self.wsd_service = None
        self.neo4j = None
    
    def initialize(self):
        """Initialize services"""
        print("\n" + "="*80)
        print("🔤 MLEX - Interactive Word Sense Disambiguation Tool")
        print("="*80)
        
        # Initialize Gemini
        try:
            self.wsd_service = GeminiWSDService()
            print("✅ Gemini service initialized successfully")
        except ValueError as e:
            print(f"\n❌ {e}")
            return False
        
        # Initialize Neo4j
        self.neo4j = Neo4jConnection()
        if self.neo4j.connected:
            print("✅ Neo4j connected successfully")
        else:
            print("⚠️  Neo4j not connected, using mock data")
        
        return True
    
    def show_menu(self):
        """Display menu"""
        print("\n" + "-"*80)
        print("Select function:")
        print("  1. Single word disambiguation (enter word + sentence)")
        print("  2. Sentence comparison analysis (find different meanings of same words)")
        print("  3. Exit")
        print("-"*80)
    
    def mode_single_word(self):
        """Mode 1: Single word WSD"""
        print("\n📍 Mode 1: Single word disambiguation")
        print("-"*80)
        
        word = input("\nPlease enter the word to analyze: ").strip()
        if not word:
            print("❌ Word cannot be empty")
            return
        
        context = input(f"Please enter a sentence containing '{word}': ").strip()
        if not context:
            print("❌ Sentence cannot be empty")
            return
        
        # Check if word is in sentence
        if word.lower() not in context.lower():
            print(f"⚠️  Warning: Word '{word}' is not in the sentence")
            confirm = input("Continue analysis? (y/n): ").strip().lower()
            if confirm != 'y':
                return
        
        print(f"\n🔍 Analyzing...")
        
        # Get senses from Neo4j
        senses = self.neo4j.get_word_senses(word)
        
        if not senses:
            print(f"❌ Cannot find definition for word '{word}'")
            return
        
        print(f"\n📚 Found {len(senses)} senses:")
        for i, sense in enumerate(senses, 1):
            print(f"  {i}. {sense.definition}")
        
        # Execute WSD
        print(f"\n🤖 AI analyzing...")
        results = self.wsd_service.disambiguate(word, context, tuple(senses))
        
        # Display results
        print(f"\n" + "="*80)
        print("📊 Analysis Results:")
        print("="*80)
        print(f"Sentence: {context}")
        print(f"Word: {word}\n")
        
        for i, r in enumerate(results, 1):
            conf = r['confidence']
            
            # Select icon based on confidence
            if conf > 70:
                icon = "🟢"
            elif conf > 40:
                icon = "🟡"
            else:
                icon = "🔴"
            
            print(f"{icon} Rank {i}: {r['definition']}")
            print(f"   Confidence: {conf:.1f}%")
            print(f"   Reason: {r['reasoning']}\n")
    
    def mode_sentence_comparison(self):
        """Mode 2: Sentence comparison"""
        print("\n📍 Mode 2: Sentence comparison analysis")
        print("-"*80)
        
        sentence1 = input("\nPlease enter the first sentence: ").strip()
        if not sentence1:
            print("❌ Sentence cannot be empty")
            return
        
        sentence2 = input("Please enter the second sentence: ").strip()
        if not sentence2:
            print("❌ Sentence cannot be empty")
            return
        
        print(f"\n🔍 Finding common words...")
        
        # Find common words
        common_words = self.wsd_service.find_common_words(sentence1, sentence2)
        
        if not common_words:
            print("❌ The two sentences have no common words")
            return
        
        print(f"\n📝 Found {len(common_words)} common words: {', '.join(common_words)}")
        
        # Analyze each common word
        print(f"\n🤖 Analyzing the meaning of each word in both sentences...")
        print("="*80)
        
        for word in common_words:
            print(f"\n🔤 Word: {word}")
            print("-"*80)
            
            result = self.wsd_service.analyze_word_in_contexts(
                word, sentence1, sentence2
            )
            
            if not result:
                print("❌ Analysis failed")
                continue
            
            print(f"Sentence 1: {sentence1}")
            print(f"Meaning: {result.get('context1_meaning', 'N/A')}\n")
            
            print(f"Sentence 2: {sentence2}")
            print(f"Meaning: {result.get('context2_meaning', 'N/A')}\n")
            
            are_different = result.get('are_different', False)
            confidence = result.get('confidence', 0)
            
            if are_different:
                print(f"✅ Different meanings (confidence: {confidence}%)")
            else:
                print(f"❌ Same meaning (confidence: {confidence}%)")
            
            print(f"Explanation: {result.get('explanation', 'N/A')}")
            print("-"*80)
    
    def run(self):
        """Run main program"""
        if not self.initialize():
            return
        
        while True:
            self.show_menu()
            
            choice = input("\nPlease select (1/2/3): ").strip()
            
            if choice == '1':
                self.mode_single_word()
            
            elif choice == '2':
                self.mode_sentence_comparison()
            
            elif choice == '3':
                print("\n👋 Goodbye!")
                break
            
            else:
                print("❌ Invalid selection, please enter 1, 2 or 3")
            
            input("\nPress Enter to continue...")
        
        # Cleanup
        if self.neo4j:
            self.neo4j.close()


# ==================== Main Program ====================

def main():
    """Main function"""
    app = InteractiveWSD()
    
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n\n👋 Program interrupted")
    except Exception as e:
        print(f"\n❌ Error occurred: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()