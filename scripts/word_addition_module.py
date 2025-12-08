"""
User word addition feature module
Supports form input, AI verification, database storage
"""

import streamlit as st
import google.generativeai as genai
from neo4j import GraphDatabase
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WordAdditionService:
    """wordaddservice"""
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str, gemini_api_key: Optional[str] = None):
        """
        initializeservice
        
        Args:
            neo4j_uri: Neo4j connectionURI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            gemini_api_key: Gemini API Key（optional）
        """
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        
        # initialize Gemini
        self.gemini_enabled = False
        if gemini_api_key:
            try:
                genai.configure(api_key=gemini_api_key)
                self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
                self.gemini_enabled = True
                logger.info("✅ Gemini API initializesuccessfully")
            except Exception as e:
                logger.warning(f"⚠️ Gemini API Initialization failed: {e}")
    
    def close(self):
        """Closeconnection"""
        if self.driver:
            self.driver.close()
    
    def validate_word_with_ai(self, word_data: Dict) -> Tuple[bool, List[str], List[str]]:
        """
        use AI Verificationworddata
        
        Args:
            word_data: worddatadictionary
            
        Returns:
            (is_valid, warnings, suggestions) - (whethervalid, Warninglist, Suggestion list)
        """
        if not self.gemini_enabled:
            return True, [], ["AI Verificationnot enabled,skipVerification"]
        
        try:
            # Build verification prompt
            prompt = f"""is an expert. Please verify the following word entry for correctness and reasonableness.

Word Information：
- Entry (Entry): {word_data.get('entry', 'N/A')}
- Definition (Definition): {word_data.get('definition', 'N/A')}
- POS (Part of Speech): {word_data.get('pos', 'N/A')}
- Root Word (Root): {word_data.get('root_word', 'N/A')}
- Example (Example): {word_data.get('example', 'N/A')}
- Domain (Domain): {word_data.get('domain', 'N/A')}
- Synonyms (Sinonim): {word_data.get('synonyms', 'N/A')}
- Antonyms (Antonim): {word_data.get('antonyms', 'N/A')}

Please check the following aspects：
1. **Entry whetherasvalidMalay word**（notisphrase、sentenceorirrelevantword）
2. **Definition whetherreasonable**（Definitionwhetherclear、accurate）
3. **POS (Part of Speech) whether correct** (e.g., kata nama, kata kerja, etc.)
4. **Example whether appropriate** (whether example uses the word, whether conforms to Malay grammar)
5. **Synonyms whether valid** (if provided, check if they are actual synonyms in Malay)
6. **Antonyms whether valid** (if provided, check if they are actual antonyms in Malay)
7. **Overall consistency**（between fieldswhethermatch）

Please return JSON format：
{{
  "is_valid": true/false,          // overallwhethervalid
  "warnings": [                     // Warning list (need attention but not prevent save)
    "Warning1",
    "Warning2"
  ],
  "suggestions": [                  // Suggestion list（improvementSuggestions）
    "Suggestions1",
    "Suggestions2"
  ],
  "explanation": "brief explanation"      // overall assessment
}}

Judgment criteria：
- ✅ is_valid = true: Entry is single Malay word, Definition reasonable, no major errors
- ❌ is_valid = false: Entryisphrase/sentence,orDefinitioncompletelyerror,orcontains non-Malay content

Please return JSON only, no other text.
"""
            
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Clean response text
            if response_text.startswith('```'):
                response_text = re.sub(r'^```json\s*\n?', '', response_text)
                response_text = re.sub(r'\n?```$', '', response_text)
            
            # Parse JSON
            result = json.loads(response_text)
            
            is_valid = result.get('is_valid', True)
            warnings = result.get('warnings', [])
            suggestions = result.get('suggestions', [])
            explanation = result.get('explanation', '')
            
            # addoverall assessmenttoSuggestions
            if explanation:
                suggestions.insert(0, f"📝 overall assessment: {explanation}")
            
            return is_valid, warnings, suggestions
            
        except Exception as e:
            logger.error(f"AI Verificationfailed: {e}")
            return True, [], [f"⚠️ AI Verification error occurred: {str(e)}, but does not prevent save"]
    
    def check_word_exists(self, entry: str, index: Optional[str] = None) -> bool:
        """
        check whether word already exists
        
        Args:
            entry: Entry
            index: Sense number（optional）
            
        Returns:
            bool: whetherexists
        """
        with self.driver.session() as session:
            if index:
                # Check specific sense
                query = """
                MATCH (w:Word {entry: $entry})-[:HAS_SENSE]->(s:Sense)
                WHERE s.sense_index = $index
                RETURN count(s) > 0 as exists
                """
                result = session.run(query, entry=entry, index=index)
            else:
                # check word whetherexists
                query = """
                MATCH (w:Word {entry: $entry})
                RETURN count(w) > 0 as exists
                """
                result = session.run(query, entry=entry)
            
            record = result.single()
            return record['exists'] if record else False
    
    def get_next_sense_index(self, entry: str) -> int:
        """
        Get next available sense_index
        
        Args:
            entry: Entry
            
        Returns:
            int: Next index number
        """
        with self.driver.session() as session:
            query = """
            MATCH (w:Word {entry: $entry})-[:HAS_SENSE]->(s:Sense)
            RETURN max(s.sense_index) as max_index
            """
            result = session.run(query, entry=entry)
            record = result.single()
            
            max_index = record['max_index'] if record and record['max_index'] is not None else 0
            
            # if max_index is string (e.g., 'a'), convert to number
            if isinstance(max_index, str):
                return 1  # start from 1
            
            return max_index + 1
    
    def add_word_to_database(self, word_data: Dict) -> Tuple[bool, str]:
        """
        Add Wordtodatabase
        
        Args:
            word_data: worddata
            
        Returns:
            (success, message) - (whethersuccessfully, Message)
        """
        try:
            entry = word_data['entry']
            definition = word_data['definition']
            
            with self.driver.session() as session:
                # checkwhetherneedauto-generate sense_index
                if 'sense_index' not in word_data or word_data['sense_index'] is None:
                    word_data['sense_index'] = self.get_next_sense_index(entry)
                
                sense_index = word_data['sense_index']
                
                # Generate sense_id
                sense_id = f"{entry}_{sense_index}"
                
                # 1. Merge Word node
                word_query = """
                MERGE (w:Word {entry: $entry})
                ON CREATE SET
                    w.rootWrd = $rootWrd,
                    w.fonetik = $fonetik,
                    w.pos = $pos,
                    w.label = $label,
                    w.asal = $asal,
                    w.passive = $passive,
                    w.diaLan = $diaLan,
                    w.domain = $domain,
                    w.references = $references,
                    w.created_at = datetime(),
                    w.created_by = 'user_addition'
                ON MATCH SET
                    w.updated_at = datetime()
                RETURN w
                """
                
                session.run(word_query,
                    entry=entry,
                    rootWrd=word_data.get('root_word'),
                    fonetik=word_data.get('fonetik'),
                    pos=word_data.get('pos'),
                    label=word_data.get('label'),
                    asal=word_data.get('asal'),
                    passive=word_data.get('passive'),
                    diaLan=word_data.get('diaLan'),
                    domain=word_data.get('domain'),
                    references=word_data.get('references')
                )
                
                # 2. Create Sense node
                sense_query = """
                MATCH (w:Word {entry: $entry})
                CREATE (s:Sense {
                    sense_id: $sense_id,
                    definition: $definition,
                    sense_index: $sense_index,
                    confidence: 1.0,
                    created_at: datetime(),
                    created_by: 'user_addition'
                })
                MERGE (w)-[:HAS_SENSE {primary: true}]->(s)
                RETURN s
                """
                
                session.run(sense_query,
                    entry=entry,
                    sense_id=sense_id,
                    definition=definition,
                    sense_index=sense_index
                )
                
                # 3. Create Example node（ifhas）
                if word_data.get('example'):
                    example_query = """
                    MATCH (s:Sense {sense_id: $sense_id})
                    CREATE (e:Example {
                        text: $example_text,
                        created_at: datetime(),
                        created_by: 'user_addition'
                    })
                    MERGE (s)-[:HAS_EXAMPLE {order: 1}]->(e)
                    """
                    session.run(example_query,
                        sense_id=sense_id,
                        example_text=word_data['example']
                    )
                
                # 4. Create Root relationship（ifhas）
                if word_data.get('root_word') and word_data['root_word'] != entry:
                    root_query = """
                    MATCH (w:Word {entry: $entry})
                    MERGE (r:Root {word: $root_word})
                    MERGE (w)-[:HAS_ROOT]->(r)
                    """
                    session.run(root_query,
                        entry=entry,
                        root_word=word_data['root_word']
                    )
                
                # 5. Create Domain relationship（ifhas）
                if word_data.get('domain'):
                    domain_query = """
                    MATCH (s:Sense {sense_id: $sense_id})
                    MERGE (d:Domain {name: $domain_name})
                    MERGE (s)-[:IN_DOMAIN]->(d)
                    """
                    session.run(domain_query,
                        sense_id=sense_id,
                        domain_name=word_data['domain']
                    )

                # 6. Create Synonym relationships (if has)
                if word_data.get('synonyms'):
                    # Split by semicolon and clean
                    synonym_list = [s.strip() for s in word_data['synonyms'].split(';') if s.strip()]
                    for synonym in synonym_list:
                        synonym_query = """
                        MATCH (w1:Word {entry: $entry})
                        MERGE (w2:Word {entry: $synonym})
                        ON CREATE SET
                            w2.created_at = datetime(),
                            w2.created_by = 'synonym_link'
                        MERGE (w1)-[:SYNONYM]-(w2)
                        """
                        session.run(synonym_query,
                            entry=entry,
                            synonym=synonym
                        )

                # 7. Create Antonym relationships (if has)
                if word_data.get('antonyms'):
                    # Split by semicolon and clean
                    antonym_list = [a.strip() for a in word_data['antonyms'].split(';') if a.strip()]
                    for antonym in antonym_list:
                        antonym_query = """
                        MATCH (w1:Word {entry: $entry})
                        MERGE (w2:Word {entry: $antonym})
                        ON CREATE SET
                            w2.created_at = datetime(),
                            w2.created_by = 'antonym_link'
                        MERGE (w1)-[:ANTONYM]-(w2)
                        """
                        session.run(antonym_query,
                            entry=entry,
                            antonym=antonym
                        )

                return True, f"✅ Word successfully added!\nEntry: {entry}\nSense ID: {sense_id}"
                
        except Exception as e:
            logger.error(f"Failed to add word: {e}")
            return False, f"❌ Addition failed: {str(e)}"
    
    def get_word_info(self, entry: str) -> Optional[Dict]:
        """
        Get existing word information
        
        Args:
            entry: Entry
            
        Returns:
            Dict or None
        """
        with self.driver.session() as session:
            query = """
            MATCH (w:Word {entry: $entry})
            OPTIONAL MATCH (w)-[:HAS_SENSE]->(s:Sense)
            RETURN w, collect(s) as senses
            """
            result = session.run(query, entry=entry)
            record = result.single()
            
            if not record:
                return None
            
            word_node = record['w']
            senses = record['senses']
            
            return {
                'entry': word_node.get('entry'),
                'pos': word_node.get('pos'),
                'rootWrd': word_node.get('rootWrd'),
                'fonetik': word_node.get('fonetik'),
                'existing_senses': len(senses),
                'senses': [
                    {
                        'sense_id': s.get('sense_id'),
                        'sense_index': s.get('sense_index'),
                        'definition': s.get('definition')
                    }
                    for s in senses
                ]
            }


def render_word_addition_page(neo4j_conn, gemini_service):
    """
    Render word addition page
    
    Args:
        neo4j_conn: Neo4j connectionobject
        gemini_service: Gemini serviceobject（optional）
    """
    st.title("➕ Add New Word")
    
    st.markdown("""
    ### Description
    - Fill in basic word information
    - AI will automatically verify data validity
    - If verification passes, can save directly to database
    """)
    
    # Initialize word addition service
    gemini_api_key = None
    if gemini_service and hasattr(gemini_service, 'api_key'):
        gemini_api_key = gemini_service.api_key

    word_service = WordAdditionService(
        neo4j_uri=neo4j_conn.uri if hasattr(neo4j_conn, 'uri') else "bolt://localhost:7687",
        neo4j_user=neo4j_conn.user if hasattr(neo4j_conn, 'user') else "neo4j",
        neo4j_password=neo4j_conn.password if hasattr(neo4j_conn, 'password') else "mlex2025",
        gemini_api_key=gemini_api_key
    )
    
    st.markdown("---")
    
    # Create form
    with st.form("add_word_form", clear_on_submit=False):
        st.subheader("📝 Word Information")
        
        # Required fields
        st.markdown("**Required fields** *")
        
        col1, col2 = st.columns(2)
        
        with col1:
            entry = st.text_input(
                "Entry (Entry) *",
                placeholder="Example: makan",
                help="Malay word（notisphraseorsentence）"
            )
        
        with col2:
            pos = st.selectbox(
                "Part of Speech (POS) *",
                options=[
                    "",
                    "kata nama",           # Noun
                    "kata kerja",          # Verb
                    "kata adjektif",       # Adjective
                    "kata adverba",        # Adverb
                    "kata bilangan",       # Numeral
                    "kata ganti nama",     # Pronoun
                    "kata sendi nama",     # Preposition
                    "kata hubung",         # Conjunction
                    "kata seru",           # Interjection
                    "kata penegas",        # Emphatic particle
                    "kata pemeri",         # Determiner
                ],
                help="selectPart of Speech"
            )
        
        definition = st.text_area(
            "Definition (Definition) *",
            placeholder="Example: eat、consume food",
            help="conciseclearChineseDefinition",
            height=100
        )
        
        # optionalfields
        st.markdown("---")
        st.markdown("**optionalfields**")
        
        col3, col4 = st.columns(2)
        
        with col3:
            root_word = st.text_input(
                "Root (Root Word)",
                placeholder="Example: makan",
                help="the wordRootform"
            )
        
        with col4:
            fonetik = st.text_input(
                "Phonetic (Fonetik)",
                placeholder="Example: ma.kan",
                help="Phonetic notation"
            )
        
        example = st.text_area(
            "Example (Example)",
            placeholder="Example: Saya makan nasi goreng untuk makan malam.",
            help="Example sentence using this word in Malay",
            height=80
        )
        
        col5, col6 = st.columns(2)

        with col5:
            domain = st.text_input(
                "Domain (Domain)",
                placeholder="Example: daily usage",
                help="wordbelongs toprofessionalDomain"
            )

        with col6:
            label = st.text_input(
                "Label (Label)",
                placeholder="Example: common word",
                help="classificationLabel"
            )

        col7, col8 = st.columns(2)

        with col7:
            synonyms = st.text_input(
                "Synonyms (Sinonim)",
                placeholder="Example: makan; santap; jamah",
                help="Synonyms separated by semicolon (;)"
            )

        with col8:
            antonyms = st.text_input(
                "Antonyms (Antonim)",
                placeholder="Example: puasa; lapar",
                help="Antonyms separated by semicolon (;)"
            )
        
        # Advanced options (collapsible)
        with st.expander("🔧 Advanced options"):
            sense_index = st.number_input(
                "Sense number (Sense Index)",
                min_value=0,
                value=0,
                help="Leave blank for auto-generation. If the word already exists, will auto-increment"
            )
            
            asal = st.text_input(
                "Source (Asal)",
                placeholder="Example: Arabic",
                help="loanwordSourcelanguage"
            )
            
            passive = st.text_input(
                "Passive form (Passive)",
                placeholder="Example: dimakan",
                help="Passive voice form"
            )
            
            diaLan = st.text_input(
                "Dialect (DiaLan)",
                placeholder="Example: Standard Malay",
                help="Dialectorlanguagevariant"
            )
            
            references = st.text_input(
                "References (References)",
                placeholder="Example: Kamus Dewan",
                help="referenceSource"
            )
        
        st.markdown("---")
        
        # Submit buttons
        col_submit1, col_submit2, col_submit3 = st.columns([1, 1, 1])
        
        with col_submit1:
            submit_validate = st.form_submit_button(
                "🤖 AI Verification",
                help="firstVerificationdatawhetherreasonable",
                type="secondary",
                use_container_width=True
            )
        
        with col_submit2:
            submit_direct = st.form_submit_button(
                "💾 directlySave",
                help="skipVerification,directlySave",
                type="primary",
                use_container_width=True
            )
        
        with col_submit3:
            submit_clear = st.form_submit_button(
                "🗑️ Clear",
                help="Clearform",
                use_container_width=True
            )
    
    # Handle form submission
    if submit_clear:
        st.rerun()
    
    # VerificationRequired fields
    if (submit_validate or submit_direct):
        if not entry or not definition or not pos:
            st.error("❌ Please fill in all required fields (Entry, Definition, Part of Speech)")
            return
        
        # prepareworddata
        word_data = {
            'entry': entry.strip(),
            'definition': definition.strip(),
            'pos': pos,
            'root_word': root_word.strip() if root_word else entry.strip(),
            'fonetik': fonetik.strip() if fonetik else None,
            'example': example.strip() if example else None,
            'domain': domain.strip() if domain else None,
            'label': label.strip() if label else None,
            'synonyms': synonyms.strip() if synonyms else None,
            'antonyms': antonyms.strip() if antonyms else None,
            'sense_index': sense_index if sense_index > 0 else None,
            'asal': asal.strip() if asal else None,
            'passive': passive.strip() if passive else None,
            'diaLan': diaLan.strip() if diaLan else None,
            'references': references.strip() if references else None,
        }
        
        # check whether word already exists
        existing_info = word_service.get_word_info(entry)
        if existing_info:
            st.info(f"ℹ️ Entry '{entry}' already exists with {existing_info['existing_senses']} senses")
            
            with st.expander("📖 viewexistingSense"):
                for sense in existing_info['senses']:
                    st.markdown(f"**Sense {sense['sense_index']}**: {sense['definition']}")
        
        # AI Verification
        if submit_validate:
            st.markdown("---")
            st.subheader("🤖 AI VerificationResult")
            
            with st.spinner("currentlyVerification..."):
                is_valid, warnings, suggestions = word_service.validate_word_with_ai(word_data)
            
            if is_valid:
                st.success("✅ Verificationpass！dataappearsnoproblems.")
            else:
                st.error("❌ Verificationnotpass！Found some serious issues.")
            
            # displayWarning
            if warnings:
                st.warning("⚠️ **Warning**")
                for warning in warnings:
                    st.markdown(f"- {warning}")
            
            # displaySuggestions
            if suggestions:
                st.info("💡 **Suggestions**")
                for suggestion in suggestions:
                    st.markdown(f"- {suggestion}")
            
            # ifVerificationpass,displaySavebuttons
            if is_valid:
                st.markdown("---")
                st.success("✅ Validation passed! Saving to database...")

                # Automatically save after validation passes
                success, message = word_service.add_word_to_database(word_data)

                if success:
                    st.success(message)
                    st.balloons()

                    # Display database link (if needed)
                    st.markdown("---")
                    st.markdown("### Next steps")
                    st.info("🔍 You can search the newly added word in [Word Search](/) page")
                else:
                    st.error(message)
            else:
                st.warning("⚠️ Suggestion: Modify and resubmit, or select 'Save directly' (not recommended)")
        
        # directlySave
        elif submit_direct:
            st.markdown("---")
            st.warning("⚠️ You selected direct save (skipping AI Verification)")
            st.info("Saving to database...")

            # Automatically save when direct save is selected
            success, message = word_service.add_word_to_database(word_data)

            if success:
                st.success(message)
                st.balloons()
                st.markdown("---")
                st.markdown("### Next steps")
                st.info("🔍 You can search the newly added word in [Word Search](/) page")
            else:
                st.error(message)
    
    # Closeservice
    word_service.close()


# Standalone test run
if __name__ == "__main__":
    st.set_page_config(page_title="Add Word", page_icon="➕", layout="wide")
    
    # Mock Neo4j and Gemini connection
    class MockNeo4jConn:
        uri = "bolt://localhost:7687"
        user = "neo4j"
        password = "mlex2025"
    
    class MockGeminiService:
        api_key = None  # Set your API Key
    
    render_word_addition_page(MockNeo4jConn(), MockGeminiService())