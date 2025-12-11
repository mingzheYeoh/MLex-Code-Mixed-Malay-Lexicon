"""
MLEX - Malay Language Lexicon StreamLit Interface (Complete Version)
Includes word search, interactive WSD, sentence comparison, and other features
"""

import streamlit as st
from neo4j import GraphDatabase
from gemini_wsd_service import GeminiWSDService, WordSense
from ollama_service import OllamaService
from word_addition_module import render_word_addition_page
from new_wsd_module import render_unified_wsd_page
import pandas as pd
import os
import sys

# Page configuration
st.set_page_config(
    page_title="MLEX - Malay Lexicon",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== Neo4j Connection ====================

class Neo4jConnection:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="mlex2025"):
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.connected = True
        except Exception as e:
            st.warning(f"⚠️ Neo4j connection failed: {e}")
            self.connected = False
            self.driver = None

    def close(self):
        if self.driver:
            self.driver.close()

    def search_word(self, entry: str):
        """Search word (exact match)"""
        if not self.connected:
            return None

        with self.driver.session() as session:
            result = session.run("""
                MATCH (w:Word {entry: $entry})
                OPTIONAL MATCH (w)-[:HAS_SENSE]->(s:Sense)
                OPTIONAL MATCH (s)-[:HAS_EXAMPLE]->(e:Example)
                OPTIONAL MATCH (w)-[:HAS_ROOT]->(r:Root)
                OPTIONAL MATCH (w)-[:SYNONYM]->(syn:Word)
                RETURN w,
                       collect(DISTINCT s) as senses,
                       collect(DISTINCT e) as examples,
                       r,
                       collect(DISTINCT syn.entry) as synonyms
            """, entry=entry)

            return result.single()

    def search_words_containing(self, query: str, limit: int = 20):
        """Search all words containing specified text"""
        if not self.connected:
            return []

        with self.driver.session() as session:
            # Exact match first, then contains match
            result = session.run("""
                MATCH (w:Word)
                WHERE w.entry = $search_term OR w.entry CONTAINS $search_term
                WITH w,
                     CASE WHEN w.entry = $search_term THEN 0 ELSE 1 END as priority
                OPTIONAL MATCH (w)-[:HAS_SENSE]->(s:Sense)
                RETURN w.entry as entry,
                       w.pos as pos,
                       collect(s.definition)[0] as first_definition,
                       priority
                ORDER BY priority, w.entry
                LIMIT $limit
            """, search_term=query, limit=limit)

            return [dict(record) for record in result]
    
    def get_all_senses_for_word(self, entry: str):
        """Get all senses for word (for WSD)"""
        if not self.connected:
            return self._get_mock_senses(entry)

        with self.driver.session() as session:
            result = session.run("""
                MATCH (w:Word {entry: $entry})-[:HAS_SENSE]->(s:Sense)
                OPTIONAL MATCH (s)-[:HAS_EXAMPLE]->(e:Example)
                WITH s, collect(e.text) as examples
                ORDER BY s.sense_index
                RETURN s.sense_id as sense_id,
                       s.definition as definition,
                       examples
            """, entry=entry)

            senses = []
            for record in result:
                senses.append(WordSense(
                    sense_id=record['sense_id'],
                    definition=record['definition'],
                    examples=tuple(record['examples']) if record['examples'] else None
                ))

            return senses if senses else self._get_mock_senses(entry)
    
    def _get_mock_senses(self, word: str):
        """Mock data"""
        mock_data = {
            'makan': [
                WordSense('makan_1', 'to eat food'),
                WordSense('makan_2', 'to consume resources'),
                WordSense('makan_3', 'to corrode or erode'),
            ],
            'main': [
                WordSense('main_1', 'to play (games)'),
                WordSense('main_2', 'to perform or act'),
                WordSense('main_3', 'to play (musical instrument)'),
            ],
            'buah': [
                WordSense('buah_1', 'fruit'),
                WordSense('buah_2', 'classifier for large objects'),
            ],
        }
        return mock_data.get(word.lower(), [])
    
    def fuzzy_search(self, query: str, limit: int = 10):
        """Fuzzy search"""
        if not self.connected:
            return []

        with self.driver.session() as session:
            result = session.run("""
                MATCH (w:Word)
                WHERE w.entry CONTAINS $query OR w.entry STARTS WITH $query
                RETURN w.entry as entry, w.pos as pos
                LIMIT $limit
            """, query=query, limit=limit)

            return [dict(record) for record in result]

    def get_database_stats(self):
        """Get database statistics"""
        if not self.connected:
            return {'nodes': {}, 'relationships': {}, 'pos': {}}

        with self.driver.session() as session:
            stats = {}

            # Node statistics
            result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as label, count(*) as count
                ORDER BY count DESC
            """)
            stats['nodes'] = {record['label']: record['count'] for record in result}

            # Relationship statistics
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(*) as count
                ORDER BY count DESC
            """)
            stats['relationships'] = {record['type']: record['count'] for record in result}

            # POS statistics
            result = session.run("""
                MATCH (w:Word)
                WHERE w.pos IS NOT NULL
                RETURN w.pos as pos, count(*) as count
                ORDER BY count DESC
                LIMIT 10
            """)
            stats['pos'] = {record['pos']: record['count'] for record in result}

            return stats


# ==================== Initialization ====================

@st.cache_resource
def init_neo4j():
    """Initialize Neo4j connection"""
    return Neo4jConnection()

@st.cache_resource
def init_gemini():
    """Initialize Gemini service"""
    api_key = os.getenv('GEMINI_API_KEY')
    if api_key:
        try:
            return GeminiWSDService(api_key=api_key)
        except Exception as e:
            st.error(f"Gemini initialization failed: {e}")
            return None
    return None

@st.cache_resource
def init_ollama():
    """Initialize Ollama service"""
    try:
        service = OllamaService(model="sailor2:8b")
        if service.test_connection():
            return service
        return None
    except Exception as e:
        st.error(f"Ollama initialization failed: {e}")
        return None


# ==================== Sidebar ====================

def render_sidebar():
    """Render sidebar"""
    st.sidebar.title("📚 MLEX")
    st.sidebar.markdown("**Malay Lexicon System**")
    st.sidebar.markdown("---")

    # Page selection
    page = st.sidebar.radio(
        "Select Function",
        [
            "🔍 Word Search",
            "🎯 WSD",
            "📊 Statistics",
            "➕ Add Word",
            "⚙️ Settings"
        ]
    )

    st.sidebar.markdown("---")

    # API status
    st.sidebar.subheader("AI Services")

    # Ollama status
    ollama = init_ollama()
    if ollama:
        st.sidebar.success("✅ Ollama (Sailor2:8b)")
    else:
        st.sidebar.error("❌ Ollama not connected")
        st.sidebar.caption("Make sure Ollama is running")

    # Gemini status
    gemini = init_gemini()
    if gemini:
        st.sidebar.success("✅ Gemini API")
    else:
        st.sidebar.warning("⚠️ Gemini API (Optional)")
        st.sidebar.caption("Set GEMINI_API_KEY to enable")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Database")

    neo4j = init_neo4j()
    if neo4j.connected:
        st.sidebar.success("✅ Neo4j connected")
    else:
        st.sidebar.warning("⚠️ Neo4j not connected")
        st.sidebar.caption("Using mock data")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### About")
    st.sidebar.info(
        "MLEX is a Malay language lexicon system based on Neo4j graph database, "
        "using Google Gemini AI for word sense disambiguation."
    )

    return page


# ==================== Page 1: Word Search ====================

def query_word_with_ai(word, ollama_service=None):
    """
    Query word using AI (Ollama Sailor2:8b only)

    Args:
        word: The word to query
        ollama_service: Ollama service instance

    Returns:
        Word information dict or None
    """
    if not ollama_service:
        st.error("❌ Ollama service is not available")
        st.info("Please ensure Ollama is running with sailor2:8b model")
        return None

    try:
        word_info = ollama_service.query_word(word)
        if word_info and 'error' not in word_info:
            return word_info
        elif word_info and 'error' in word_info:
            # Simplified error display
            error_msg = word_info.get('error', 'Unknown error')

            if 'parse' in error_msg.lower() or 'failed to parse' in error_msg.lower():
                st.error("❌ Ollama Error: Failed to parse Ollama response")
                st.warning("⚠️ Response format issue. This is usually temporary. Please:")
                st.info("• Try again\n• If issue persists, restart Ollama service")
            elif 'not a valid' in error_msg.lower():
                st.error(f"❌ Ollama Error: {error_msg}")
            else:
                st.error(f"❌ Ollama Error: {error_msg}")
            return None
        else:
            st.error("❌ AI verification failed")
            return None
    except Exception:
        st.error(f"❌ AI verification failed")
        st.info("Please check that:\n• Ollama is running (`ollama serve`)\n• Model sailor2:8b is available (`ollama pull sailor2:8b`)")
        return None


def query_word_with_gemini(word, gemini_service):
    """Query word information using Gemini"""
    import json

    prompt = f"""You are a Malay language dictionary expert. Please provide detailed information about the Malay word "{word}".

Return a JSON with this structure:
{{
    "entry": "{word}",
    "rootWrd": "root word (same as entry if no root)",
    "fonetik": "phonetic spelling",
    "pos": "part of speech in Malay (kata nama, kata kerja, kata sifat, etc.)",
    "label": "any special label or tag (optional)",
    "definitions": [
        {{
            "index": "1",
            "definition": "first meaning in Malay",
            "example": "example sentence using this meaning"
        }},
        {{
            "index": "2",
            "definition": "second meaning in Malay",
            "example": "example sentence"
        }}
    ],
    "asal": "etymology/origin (optional)",
    "domain": "domain/field (optional)",
    "sinonim": "synonyms separated by semicolon (optional)"
}}

IMPORTANT:
- Provide all text in Malay language (except JSON keys)
- Provide at least 1-3 definitions
- If the word is not valid Malay, return {{"error": "Not a valid Malay word"}}
"""

    try:
        response = gemini_service.model.generate_content(
            prompt,
            generation_config=gemini_service.generation_config,
            safety_settings=gemini_service.safety_settings
        )

        if not response or not response.candidates:
            st.error("❌ Gemini API empty response")
            st.warning("⚠️ Possible reasons:")
            st.info("• API call limit reached (per-minute quota)\n• Network connection issue\n• Invalid or expired API key")

            # Debug information
            with st.expander("🔍 Debug info (click to view)"):
                st.code(f"Query word: {word}")
                st.code(f"Response: {response}")
                if hasattr(response, 'prompt_feedback'):
                    st.code(f"Prompt Feedback: {response.prompt_feedback}")

            return None

        if response.candidates[0].finish_reason != 1:
            st.error(f"❌ Gemini API returned abnormal status: {response.candidates[0].finish_reason}")
            st.warning("⚠️ Possible reasons:")

            # Detailed finish_reason explanation
            finish_reasons = {
                1: "STOP (completed normally)",
                2: "MAX_TOKENS (reached maximum token limit)",
                3: "SAFETY (blocked by safety filter)",
                4: "RECITATION (content repetition/citation issue)",
                5: "OTHER (other reason)"
            }

            candidate = response.candidates[0]
            reason_code = candidate.finish_reason
            reason_text = finish_reasons.get(reason_code, f"Unknown reason code: {reason_code}")

            st.info(f"**Status details:** {reason_text}")

            # Show safety ratings
            if hasattr(candidate, 'safety_ratings'):
                st.write("**Safety ratings:**")
                for rating in candidate.safety_ratings:
                    st.write(f"- {rating.category}: {rating.probability}")

            # Debug information
            with st.expander("🔍 Debug info (click to view)"):
                st.code(f"Query word: {word}")
                st.code(f"Finish Reason Code: {reason_code}")
                if hasattr(response, 'prompt_feedback'):
                    st.code(f"Prompt Feedback: {response.prompt_feedback}")

            return None

        text = response.text.strip()
        text = text.replace('```json', '').replace('```', '').strip()

        word_info = json.loads(text)

        # Check for error
        if 'error' in word_info:
            st.warning(f"⚠️ AI recognition result: {word_info.get('error', 'Unknown error')}")
            st.info(f"Word **{word}** may not be a valid Malay word, or AI cannot recognize it.")

            # Show complete AI response
            with st.expander("🔍 View complete AI response"):
                st.json(word_info)

            return None

        return word_info

    except json.JSONDecodeError as e:
        st.error(f"❌ JSON parsing failed: {e}")
        st.warning("⚠️ Possible reasons:")
        st.info("• AI returned incorrect format\n• Response content was truncated")

        # Show raw response text
        with st.expander("🔍 View raw AI response"):
            st.code(text[:1000], language='text')
            st.caption(f"Total length: {len(text)} characters")

        return None
    except Exception as e:
        error_msg = str(e).lower()
        st.error(f"❌ Gemini query failed: {e}")
        st.warning("⚠️ Possible reasons:")

        if 'quota' in error_msg or 'limit' in error_msg or 'rate' in error_msg:
            st.info("• **API call limit reached**\n• Too many requests per minute\n• Daily quota exhausted\n\nPlease try again later or upgrade API plan")
        elif 'api' in error_msg and 'key' in error_msg:
            st.info("• **Invalid API key**\n• Please check GEMINI_API_KEY configuration in settings")
        elif 'network' in error_msg or 'connection' in error_msg:
            st.info("• **Network connection issue**\n• Please check network connection\n• Confirm access to Google API services")
        else:
            st.info("• API service temporarily unavailable\n• Request format error\n• Other unknown error")

        return None


def add_word_to_database(neo4j_conn, word_info):
    """Add word to database"""

    # Check Neo4j connection
    if not neo4j_conn.connected:
        st.error("❌ Neo4j not connected, cannot add to database")
        st.info("Please ensure Neo4j database is running and check connection configuration")
        return False

    if not neo4j_conn.driver:
        st.error("❌ Neo4j driver not initialized")
        return False

    try:
        entry = word_info['entry']

        with neo4j_conn.driver.session() as session:
            # Create Word node with ALL properties
            session.run("""
                MERGE (w:Word {entry: $entry})
                SET w.rootWrd = $rootWrd,
                    w.fonetik = $fonetik,
                    w.pos = $pos,
                    w.label = $label,
                    w.asal = $asal,
                    w.domain = $domain,
                    w.sinonim = $sinonim,
                    w.created_at = datetime(),
                    w.updated_at = datetime()
            """,
                entry=entry,
                rootWrd=word_info.get('rootWrd', entry),
                fonetik=word_info.get('fonetik', ''),
                pos=word_info.get('pos', ''),
                label=word_info.get('label', ''),
                asal=word_info.get('asal', ''),
                domain=word_info.get('domain', ''),
                sinonim=word_info.get('sinonim', '')
            )

            # Create Sense nodes and relationships
            for i, def_item in enumerate(word_info.get('definitions', []), 1):
                index_str = str(def_item.get('index', i))
                sense_id = f"{entry}_{index_str}"

                session.run("""
                    MATCH (w:Word {entry: $entry})
                    CREATE (s:Sense {
                        sense_id: $sense_id,
                        definition: $definition,
                        sense_index: $sense_index,
                        created_at: datetime()
                    })
                    CREATE (w)-[:HAS_SENSE]->(s)
                """,
                    entry=entry,
                    sense_id=sense_id,
                    definition=def_item['definition'],
                    sense_index=index_str
                )

                # Create Example if exists
                if def_item.get('example'):
                    session.run("""
                        MATCH (s:Sense {sense_id: $sense_id})
                        CREATE (e:Example {text: $text, created_at: datetime()})
                        CREATE (s)-[:HAS_EXAMPLE]->(e)
                    """,
                        sense_id=sense_id,
                        text=def_item['example']
                    )

            # Create Root relationship (only if different from entry)
            root_word = word_info.get('rootWrd', '').strip()
            if root_word and root_word != entry:
                session.run("""
                    MATCH (w:Word {entry: $entry})
                    MERGE (r:Root {word: $root})
                    CREATE (w)-[:HAS_ROOT]->(r)
                """,
                    entry=entry,
                    root=root_word
                )

            # Create Synonym relationships
            synonyms_str = word_info.get('sinonim', '').strip()
            if synonyms_str:
                synonyms = [s.strip() for s in synonyms_str.split(';') if s.strip()]

                for synonym in synonyms:
                    # Check if synonym exists
                    result = session.run("""
                        OPTIONAL MATCH (syn:Word {entry: $synonym})
                        RETURN syn
                    """, synonym=synonym)

                    record = result.single()
                    if record and record['syn']:
                        # Create bidirectional synonym relationship
                        session.run("""
                            MATCH (w1:Word {entry: $entry})
                            MATCH (w2:Word {entry: $synonym})
                            MERGE (w1)-[:SYNONYM]->(w2)
                            MERGE (w2)-[:SYNONYM]->(w1)
                        """, entry=entry, synonym=synonym)

        # Successfully added, show details
        st.success(f"✅ Word '{entry}' successfully added to database!")

        # Show statistics of added data
        with st.expander("📊 View added data details"):
            st.write(f"**Word:** {entry}")
            st.write(f"**Part of Speech:** {word_info.get('pos', 'N/A')}")
            st.write(f"**Phonetic:** {word_info.get('fonetik', 'N/A')}")
            st.write(f"**Number of Definitions:** {len(word_info.get('definitions', []))}")
            st.write(f"**Root Word:** {word_info.get('rootWrd', 'N/A')}")
            st.write(f"**Synonyms:** {word_info.get('sinonim', 'N/A')}")
            st.write(f"**Etymology:** {word_info.get('asal', 'N/A')}")
            st.write(f"**Domain:** {word_info.get('domain', 'N/A')}")

        return True

    except Exception as e:
        st.error(f"❌ Failed to add to database: {e}")

        # Show debug information
        with st.expander("🔍 Error details (click to view)"):
            st.code(f"Error type: {type(e).__name__}")
            st.code(f"Error message: {str(e)}")
            st.code(f"Word data: {word_info}")

            # Show full error stack
            import traceback
            st.code(traceback.format_exc())

        st.warning("⚠️ Possible causes:")
        st.info(
            "• Neo4j database connection interrupted\n"
            "• Data format does not match database schema\n"
            "• Database permission issues\n"
            "• Network connection problems"
        )

        return False


def update_word_in_database(neo4j_conn, entry, word_info):
    """Update existing word in database with new AI data"""

    # Check Neo4j connection
    if not neo4j_conn.connected:
        st.error("❌ Neo4j not connected, cannot update database")
        st.info("Please ensure Neo4j database is running and check connection configuration")
        return False

    if not neo4j_conn.driver:
        st.error("❌ Neo4j driver not initialized")
        return False

    try:
        with neo4j_conn.driver.session() as session:
            # Step 1: Delete ALL old senses, examples, and synonym relationships
            delete_result = session.run("""
                MATCH (w:Word {entry: $entry})
                OPTIONAL MATCH (w)-[:HAS_SENSE]->(s:Sense)
                OPTIONAL MATCH (s)-[:HAS_EXAMPLE]->(e:Example)
                OPTIONAL MATCH (w)-[syn:SYNONYM]->()
                DETACH DELETE s, e
                DELETE syn
                RETURN count(s) as deleted_senses
            """, entry=entry)

            deleted = delete_result.single()
            if deleted:
                print(f"Deleted {deleted['deleted_senses']} old senses and relationships")

            # Step 2: Update ALL Word node properties
            session.run("""
                MATCH (w:Word {entry: $entry})
                SET w.rootWrd = $rootWrd,
                    w.fonetik = $fonetik,
                    w.pos = $pos,
                    w.label = $label,
                    w.asal = $asal,
                    w.domain = $domain,
                    w.sinonim = $sinonim,
                    w.updated_at = datetime()
            """,
                entry=entry,
                rootWrd=word_info.get('rootWrd', entry),
                fonetik=word_info.get('fonetik', ''),
                pos=word_info.get('pos', ''),
                label=word_info.get('label', ''),
                asal=word_info.get('asal', ''),
                domain=word_info.get('domain', ''),
                sinonim=word_info.get('sinonim', '')
            )

            # Step 3: Create NEW Sense nodes (using CREATE to ensure new nodes)
            for i, def_item in enumerate(word_info.get('definitions', []), 1):
                # Ensure index is string
                index_str = str(def_item.get('index', i))
                sense_id = f"{entry}_{index_str}"

                # Use CREATE instead of MERGE to force new node creation
                session.run("""
                    MATCH (w:Word {entry: $entry})
                    CREATE (s:Sense {
                        sense_id: $sense_id,
                        definition: $definition,
                        sense_index: $sense_index,
                        created_at: datetime()
                    })
                    CREATE (w)-[:HAS_SENSE]->(s)
                """,
                    entry=entry,
                    sense_id=sense_id,
                    definition=def_item['definition'],
                    sense_index=index_str
                )

                # Create Example if exists
                if def_item.get('example'):
                    session.run("""
                        MATCH (s:Sense {sense_id: $sense_id})
                        CREATE (e:Example {text: $text, created_at: datetime()})
                        CREATE (s)-[:HAS_EXAMPLE]->(e)
                    """,
                        sense_id=sense_id,
                        text=def_item['example']
                    )

            # Step 4: Update Root relationship (only if rootWrd is different from entry)
            root_word = word_info.get('rootWrd', '').strip()
            if root_word and root_word != entry:
                # Delete old root relationship
                session.run("""
                    MATCH (w:Word {entry: $entry})
                    OPTIONAL MATCH (w)-[r:HAS_ROOT]->()
                    DELETE r
                """, entry=entry)

                # Create new root relationship
                session.run("""
                    MATCH (w:Word {entry: $entry})
                    MERGE (root:Root {word: $root})
                    CREATE (w)-[:HAS_ROOT]->(root)
                """,
                    entry=entry,
                    root=root_word
                )
                print(f"Updated root relationship: {entry} -> {root_word}")
            else:
                # No root or root same as entry, remove any existing root relationship
                session.run("""
                    MATCH (w:Word {entry: $entry})
                    OPTIONAL MATCH (w)-[r:HAS_ROOT]->()
                    DELETE r
                """, entry=entry)

            # Step 5: Create Synonym relationships
            synonyms_str = word_info.get('sinonim', '').strip()
            if synonyms_str:
                # Parse synonyms (separated by semicolon)
                synonyms = [s.strip() for s in synonyms_str.split(';') if s.strip()]

                for synonym in synonyms:
                    # Check if synonym word exists in database
                    result = session.run("""
                        MATCH (w:Word {entry: $entry})
                        OPTIONAL MATCH (syn:Word {entry: $synonym})
                        RETURN syn
                    """, entry=entry, synonym=synonym)

                    record = result.single()
                    if record and record['syn']:
                        # Synonym exists, create bidirectional relationship
                        session.run("""
                            MATCH (w1:Word {entry: $entry})
                            MATCH (w2:Word {entry: $synonym})
                            MERGE (w1)-[:SYNONYM]->(w2)
                            MERGE (w2)-[:SYNONYM]->(w1)
                        """, entry=entry, synonym=synonym)
                        print(f"Created synonym relationship: {entry} <-> {synonym}")
                    else:
                        # Synonym doesn't exist as Word node yet, just store in sinonim property
                        print(f"Synonym '{synonym}' not in database (stored in sinonim property)")

        # Log update details for debugging
        num_defs = len(word_info.get('definitions', []))
        print(f"Successfully updated word '{entry}' with {num_defs} definitions")

        # Show detailed success message to user
        st.success("✅ Database update completed successfully!")
        st.info(f"""**Updated attributes:**
- POS: {word_info.get('pos', 'N/A')}
- Phonetic: {word_info.get('fonetik', 'N/A')}
- Root: {word_info.get('rootWrd', 'N/A')}
- Etymology: {word_info.get('asal', 'N/A')}
- Domain: {word_info.get('domain', 'N/A')}
- Synonyms: {word_info.get('sinonim', 'N/A')}
- Definitions: {num_defs} new definitions created
        """)

        return True

    except Exception as e:
        st.error(f"❌ Failed to update database: {e}")

        # Show debug information
        with st.expander("🔍 Error details (click to view)"):
            st.code(f"Error type: {type(e).__name__}")
            st.code(f"Error message: {str(e)}")

            # Show full error stack
            import traceback
            st.code(traceback.format_exc())

        return False


def display_ai_query_result(neo4j_conn, query, word_info, button_key_suffix=""):
    """Helper function to display AI query results"""
    import json

    st.success("✅ AI query successful!")

    # Display AI results
    st.markdown("---")
    st.subheader(f"📖 {word_info.get('entry', 'Unknown Word')}")

    col1, col2, col3 = st.columns(3)
    with col1:
        if word_info.get('fonetik'):
            st.metric("Phonetic", word_info['fonetik'])
    with col2:
        if word_info.get('pos'):
            st.metric("Part of Speech", word_info['pos'])
    with col3:
        if word_info.get('label'):
            st.metric("Label", word_info['label'])

    if word_info.get('rootWrd'):
        st.info(f"📌 Root: {word_info['rootWrd']}")

    if word_info.get('asal'):
        st.info(f"📚 Etymology: {word_info['asal']}")

    if word_info.get('sinonim'):
        st.info(f"🔗 Synonyms: {word_info['sinonim']}")

    st.markdown("---")
    st.subheader(f"📖 Definitions ({len(word_info.get('definitions', []))})")

    for i, def_item in enumerate(word_info.get('definitions', []), 1):
        # Safely get definition text
        definition_text = def_item.get('definition', 'No definition available')
        definition_preview = definition_text[:50] + '...' if len(definition_text) > 50 else definition_text

        with st.expander(f"Definition {i}: {definition_preview}", expanded=True):
            st.markdown(f"**Definition:** {definition_text}")
            if def_item.get('example'):
                st.markdown(f"**Example:** {def_item['example']}")

    st.markdown("---")

    # Ask if user wants to save to database
    st.subheader("💾 Save to Database")
    col1, col2 = st.columns([3, 1])

    with col1:
        st.info("Would you like to add this word to the database?")

    with col2:
        if st.button("✅ Add to Database", type="primary", key=f"add_to_db{button_key_suffix}"):
            # Check Neo4j connection first
            if not neo4j_conn.connected:
                st.error("❌ Neo4j is not running!")
                st.warning("Please start Neo4j database first:")
                st.code("docker-compose up -d neo4j\n# OR open Neo4j Desktop and start the database")
            elif add_word_to_database(neo4j_conn, word_info):
                # add_word_to_database already shows success message
                st.info("⏳ Refreshing page...")
                # Use time.sleep to let user see the success message
                import time
                time.sleep(1)
                # Trigger rerun
                st.rerun()

    # Show JSON export function
    st.markdown("---")
    st.subheader("📋 Export JSON")

    json_str = json.dumps(word_info, ensure_ascii=False, indent=2)

    # Display JSON (collapsible)
    with st.expander("🔍 View JSON data", expanded=False):
        st.code(json_str, language='json')

    # Download button
    st.download_button(
        label="📥 Download JSON file",
        data=json_str,
        file_name=f"{query}_ai.json",
        mime="application/json",
        key=f"download_ai_json{button_key_suffix}"
    )


def render_word_search_page(neo4j_conn):
    """Word search page with exact matching only"""
    st.title("🔍 Word Search")
    st.info("ℹ️ Search uses exact matching (case-sensitive). If not found in database, AI search will be triggered automatically.")

    # Check if there's an auto-search word from update
    auto_search = st.session_state.get('auto_search_word', None)
    show_success = st.session_state.get('show_update_success', False)

    if show_success and auto_search:
        st.success(f"✅ Word '{auto_search}' has been updated successfully!")
        st.info("📊 Below is the updated word data:")
        # Clear the success flag
        del st.session_state['show_update_success']

    # Search box (exact search only)
    default_value = auto_search if auto_search else ""
    query = st.text_input("Enter Malay word", value=default_value, placeholder="e.g.: makan, belajar, cantik", key="word_search_input")

    # Clear auto_search after using it
    if auto_search and 'auto_search_word' in st.session_state:
        del st.session_state['auto_search_word']

    if query:
        # Try exact matching first
        result = neo4j_conn.search_word(query)

        if result:
            # Word found in database - display it
            st.success(f"✅ Found exact match: '{query}'")
            st.markdown("---")
            display_word_details(result, neo4j_conn)
        else:
            # Word not found - use AI search automatically
            st.warning(f"⚠️ Word '{query}' not found in database")
            st.info("🤖 Triggering AI search automatically...")

            # Initialize Ollama service only
            ollama_service = init_ollama()

            if ollama_service:
                with st.spinner("Querying Ollama (Sailor2:8b)..."):
                    word_info = query_word_with_ai(query, ollama_service)

                if word_info:
                    display_ai_query_result(neo4j_conn, query, word_info)
                else:
                    st.error("❌ AI cannot recognize this word, it may not be a valid Malay word")
            else:
                st.error("❌ Ollama service is not available")
                st.info("Please ensure Ollama is running with the sailor2:8b model:")
                st.code("ollama pull sailor2:8b\nollama serve")


def display_word_details(result, neo4j_conn):
    """Display word details"""
    import json

    word = result['w']
    senses = result['senses']
    root = result['r']
    synonyms = result['synonyms']

    st.header(f"{word['entry']}")

    # Display all basic attributes
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**POS:** {word.get('pos', 'N/A')}")
        st.info(f"**Phonetic:** {word.get('fonetik', 'N/A')}")

        # Root
        if root:
            st.info(f"**Root:** {root.get('word', 'N/A')}")
        else:
            st.info(f"**Root:** {word.get('rootWrd', 'N/A')}")

    with col2:
        st.caption(f"**Etymology:** {word.get('asal') or 'N/A'}")
        st.caption(f"**Domain:** {word.get('domain') or 'N/A'}")

        # Synonyms
        if word.get('sinonim'):
            st.caption(f"**Synonyms:** {word.get('sinonim')}")
        elif synonyms and synonyms[0]:
            st.caption(f"**Synonyms:** {', '.join(filter(None, synonyms))}")
        else:
            st.caption(f"**Synonyms:** N/A")

        if word.get('label'):
            st.caption(f"**Label:** {word.get('label')}")

    st.markdown("---")

    # Display definitions with examples
    if senses:
        st.subheader(f"📖 Definitions ({len(senses)})")

        for i, sense in enumerate(senses, 1):
            with st.expander(f"Definition {i}: {sense['definition'][:50]}...", expanded=(i==1)):
                st.markdown(f"**Definition:** {sense['definition']}")

                # Get examples for this sense
                sense_examples = []
                if neo4j_conn.connected:
                    with neo4j_conn.driver.session() as session:
                        ex_result = session.run("""
                            MATCH (s:Sense {sense_id: $sense_id})-[:HAS_EXAMPLE]->(e:Example)
                            RETURN e.text as text
                        """, sense_id=sense.get('sense_id', ''))
                        sense_examples = [rec['text'] for rec in ex_result]

                if sense_examples:
                    st.markdown("**Examples:**")
                    for ex in sense_examples:
                        st.caption(f"   • {ex}")
                else:
                    st.caption("   • Example: N/A")
    else:
        st.warning("No definitions available for this word")

    # Add AI verification section
    st.markdown("---")
    st.subheader("🤖 AI Verification")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.info("💡 Not sure if the definition is correct? Use AI to verify and correct")
    with col2:
        verify_with_ai = st.button("🔍 Verify with AI", type="secondary", key=f"verify_ai_{word['entry']}")

    if verify_with_ai:
        ollama_service = init_ollama()

        if ollama_service:
            with st.spinner("🤖 Using Ollama (Sailor2:8b)..."):
                word_info = query_word_with_ai(word['entry'], ollama_service)

            if word_info:
                st.success("✅ AI verification complete!")

                # Show comprehensive comparison
                st.markdown("### 📊 Comparison: Database vs AI")

                col_db, col_ai = st.columns(2)

                with col_db:
                    st.markdown("#### 📚 Current Database")

                    # Basic info
                    st.info(f"**POS:** {word.get('pos', 'N/A')}")
                    st.info(f"**Phonetic:** {word.get('fonetik', 'N/A')}")

                    # Root
                    if root:
                        st.info(f"**Root:** {root.get('word', 'N/A')}")
                    else:
                        st.info(f"**Root:** {word.get('rootWrd', 'N/A')}")

                    # Etymology (always show)
                    st.caption(f"**Etymology:** {word.get('asal') or 'N/A'}")

                    # Domain (always show)
                    st.caption(f"**Domain:** {word.get('domain') or 'N/A'}")

                    # Synonyms (always show)
                    if word.get('sinonim') or (synonyms and synonyms[0]):
                        syn_display = word.get('sinonim') or ', '.join(filter(None, synonyms))
                        st.caption(f"**Synonyms:** {syn_display}")
                    else:
                        st.caption(f"**Synonyms:** N/A")

                    # Definitions with examples
                    st.markdown("---")
                    st.markdown(f"**Definitions ({len(senses)}):**")
                    for i, sense in enumerate(senses, 1):
                        st.markdown(f"**{i}.** {sense['definition']}")

                        # Get examples for this sense
                        sense_examples = []
                        if neo4j_conn.connected:
                            with neo4j_conn.driver.session() as session:
                                ex_result = session.run("""
                                    MATCH (s:Sense {sense_id: $sense_id})-[:HAS_EXAMPLE]->(e:Example)
                                    RETURN e.text as text
                                """, sense_id=sense.get('sense_id', ''))
                                sense_examples = [rec['text'] for rec in ex_result]

                        if sense_examples:
                            for ex in sense_examples:
                                st.caption(f"   • Example: {ex}")
                        else:
                            st.caption("   • Example: N/A")

                with col_ai:
                    st.markdown("#### 🤖 AI Result")

                    # Basic info
                    st.info(f"**POS:** {word_info.get('pos', 'N/A')}")
                    st.info(f"**Phonetic:** {word_info.get('fonetik', 'N/A')}")
                    st.info(f"**Root:** {word_info.get('rootWrd', 'N/A')}")

                    # Etymology (always show)
                    st.caption(f"**Etymology:** {word_info.get('asal') or 'N/A'}")

                    # Domain (always show)
                    st.caption(f"**Domain:** {word_info.get('domain') or 'N/A'}")

                    # Synonyms (always show)
                    st.caption(f"**Synonyms:** {word_info.get('sinonim') or 'N/A'}")

                    # Definitions with examples
                    st.markdown("---")
                    definitions = word_info.get('definitions', [])
                    st.markdown(f"**Definitions ({len(definitions)}):**")
                    for i, def_item in enumerate(definitions, 1):
                        st.markdown(f"**{i}.** {def_item['definition']}")
                        if def_item.get('example'):
                            st.caption(f"   • Example: {def_item['example']}")
                        else:
                            st.caption("   • Example: N/A")

                st.markdown("---")

                # Ask if user wants to update database
                st.warning("⚠️ Do you want to replace the database entry with AI result?")

                col_btn1, col_btn2 = st.columns(2)

                with col_btn1:
                    if st.button("✅ Yes, Update", type="primary", key=f"update_db_{word['entry']}"):
                        with st.spinner("Updating database..."):
                            success = update_word_in_database(neo4j_conn, word['entry'], word_info)

                        if success:
                            # Store the word entry in session state to auto-reload after rerun
                            st.session_state['auto_search_word'] = word['entry']
                            st.session_state['show_update_success'] = True

                            st.info("⏳ Refreshing page in 2 seconds...")
                            import time
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Update failed. Please check the error messages above.")

                with col_btn2:
                    if st.button("❌ No, Keep Current", key=f"keep_current_{word['entry']}"):
                        st.info("Database entry kept unchanged")
            else:
                st.error("❌ AI verification failed")
                st.warning("⚠️ Unable to get AI verification for this word")
                st.info("Please check that:\n- Ollama is running (`ollama serve`)\n- Model sailor2:8b is available (`ollama pull sailor2:8b`)\n- The word is a valid Malay word")
        else:
            st.error("❌ Ollama service is not available")
            st.info("Please ensure Ollama is running with sailor2:8b model:")
            st.code("ollama serve\nollama pull sailor2:8b")

    # Add JSON export function
    st.markdown("---")
    st.subheader("📋 Export JSON")

    # Build complete JSON data
    word_json = {
        "entry": word.get('entry', ''),
        "rootWrd": word.get('rootWrd', ''),
        "fonetik": word.get('fonetik', ''),
        "pos": word.get('pos', ''),
        "label": word.get('label', ''),
        "asal": word.get('asal', ''),
        "passive": word.get('passive', ''),
        "diaLan": word.get('diaLan', ''),
        "domain": word.get('domain', ''),
        "references": word.get('references', ''),
        "root": root['word'] if root else None,
        "synonyms": list(filter(None, synonyms)) if synonyms else [],
        "senses": []
    }

    # Add definition information
    if senses:
        for sense in senses:
            sense_data = {
                "sense_id": sense.get('sense_id', ''),
                "definition": sense.get('definition', ''),
                "sense_index": sense.get('sense_index', ''),
                "examples": []
            }

            # Get examples
            if neo4j_conn.connected:
                with neo4j_conn.driver.session() as session:
                    examples_result = session.run("""
                        MATCH (s:Sense {sense_id: $sense_id})-[:HAS_EXAMPLE]->(e:Example)
                        RETURN e.text as text
                    """, sense_id=sense.get('sense_id', ''))

                    for record in examples_result:
                        sense_data['examples'].append(record['text'])

            word_json['senses'].append(sense_data)

    # Format JSON
    json_str = json.dumps(word_json, ensure_ascii=False, indent=2)

    # Display JSON (collapsible)
    with st.expander("🔍 View JSON data", expanded=False):
        st.code(json_str, language='json')

    # Download and copy buttons
    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            label="📥 Download JSON file",
            data=json_str,
            file_name=f"{word['entry']}.json",
            mime="application/json",
            key=f"download_json_{word['entry']}"
        )

    with col2:
        # Use st.code to provide copyable JSON
        if st.button("📋 Copy JSON to clipboard", key=f"copy_json_{word['entry']}"):
            st.code(json_str, language='json')
            st.success("✅ JSON displayed above, you can copy it manually")


# ==================== Page2: WSD ====================

def render_wsd_page(neo4j_conn, ai_service):
    """Interactive WSDPage"""
    st.title("🎯 WSD (Word Sense Disambiguation)")

    if not ai_service:
        st.error("⚠️ No AI service available!")
        st.info("Please ensure Ollama is running or set GEMINI_API_KEY")
        return
    
    # Select Mode
    mode = st.radio(
        "Select analysis mode",
        ["Single word WSD", "Batch analysis"],
        horizontal=True
    )

    if mode == "Single word WSD":
        render_single_wsd(neo4j_conn, ai_service)
    else:
        render_batch_wsd(neo4j_conn, ai_service)


def render_single_wsd(neo4j_conn, ai_service):
    """Single word WSD mode"""
    
    st.markdown("---")
    st.markdown("### 📝 Enter Information")
    
    # Enter required info
    col1, col2 = st.columns([2, 1])
    
    with col1:
        context = st.text_input(
            "Enter Malay Sentence",
            placeholder="Example: Bateri telefon ini makan banyak kuasa",
            key="wsd_context"
        )
    
    with col2:
        target_word = st.text_input(
            "Word to Disambiguate",
            placeholder="Example: makan",
            key="wsd_word"
        )
    
    st.markdown("---")
    
    # Analyse button
    if st.button("🔍 Start Analysis", type="primary", width="stretch"):
        if not context or not target_word:
            st.error("Please enter sentence and target word")
            return
        
        # Check whether Wordis is inSentencein
        if target_word.lower() not in context.lower():
            st.warning(f"⚠️ Word '{target_word}' notinSentencein")
        
        with st.spinner("Analyzing context..."):
            senses = neo4j_conn.get_all_senses_for_word(target_word)
            
            if not senses:
                st.error(f"❌ Word '{target_word}' not in database")
                st.info("💡 Available test words: makan, main, buah")
                return
            
            if len(senses) == 1:
                st.info(f"ℹ️ Word '{target_word}' has only 1 meaning, no disambiguation needed")
                st.write(f"**Only 1 meaning:** {senses[0].definition}")
                return
            
            # Call AI for WSD
            results = ai_service.disambiguate(
                word=target_word,
                context=context,
                candidate_senses=tuple(senses)
            )
            
            # ShowResult
            st.success("✅ Analysis completed！")
            
            # Information card
            st.markdown("### 📋 Analysis Information")
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**Sentence:** {context}")
            with col2:
                st.info(f"**Target Word:** {target_word}")
            
            st.markdown("---")
            st.markdown("### 📊 Meanings Sorting Result")
            
            # Visualize Result
            for i, result in enumerate(results, 1):
                confidence = result['confidence']
                
                # Color and icon
                if confidence > 70:
                    color = "🟢"
                    badge = "success"
                elif confidence > 40:
                    color = "🟡"
                    badge = "warning"
                else:
                    color = "🔴"
                    badge = "error"
                
                with st.expander(
                    f"{color} Rank {i}: {result['definition'][:60]}... ({confidence:.1f}%)",
                    expanded=(i == 1)
                ):
                    # Confidence bar and metric
                    st.progress(confidence / 100.0)
                    st.metric("Confidence", f"{confidence:.1f}%")
                    
                    # Details
                    st.markdown(f"**Complete Definitions:** {result['definition']}")
                    st.markdown(f"**Reasoning:** {result['reasoning']}")
                    
                    # MeaningsID
                    st.caption(f"MeaningsID: {result['sense_id']}")


def render_batch_wsd(neo4j_conn, ai_service):
    """Batch analysis mode"""
    st.markdown("---")
    st.markdown("### 📝 Batch Input")
    
    st.info("💡 One test case per line, in the format: Word|Sentence")
    
    batch_input = st.text_area(
        "Enter test case",
        placeholder="makan|Saya makan nasi goreng\nmakan|Bateri makan kuasa\nmain|Kanak-kanak main\nmain|Dia main filem",
        height=150
    )
    
    if st.button("🚀 Batch analysis", type="primary"):
        if not batch_input.strip():
            st.error("Please enter the test case.")
            return
        
        lines = [line.strip() for line in batch_input.split('\n') if line.strip()]
        
        st.markdown(f"### 📊 Analysis {len(lines)} cases")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results_data = []
        
        for idx, line in enumerate(lines):
            if '|' not in line:
                st.warning(f"⚠️ Skip the formatting error line: {line}")
                continue
            
            word, context = line.split('|', 1)
            word = word.strip()
            context = context.strip()
            
            status_text.text(f"Processing: {idx+1}/{len(lines)} - {word}")
            
            # GET Meanings
            senses = neo4j_conn.get_all_senses_for_word(word)
            
            if not senses or len(senses) == 1:
                results_data.append({
                    'Word': word,
                    'Sentence': context,
                    'Result': 'No disambiguation needed' if len(senses) == 1 else 'Not found',
                    'Confidence': 'N/A'
                })
                continue
            
            wsd_results = ai_service.disambiguate(word, context, tuple(senses))
            
            top_result = wsd_results[0]
            results_data.append({
                'Word': word,
                'Sentence': context[:40] + '...',
                'Result': top_result['definition'][:40] + '...',
                'Confidence': f"{top_result['confidence']:.1f}%"
            })
            
            progress_bar.progress((idx + 1) / len(lines))
        
        status_text.text("✅ Completed！")
        
        st.markdown("### 📈 Results Summary")
        df = pd.DataFrame(results_data)
        st.dataframe(df, width="stretch")
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download Results CSV",
            csv,
            "wsd_results.csv",
            "text/csv",
            key='download-csv'
        )


# ==================== Page3: Sentence Comparison ====================
# REMOVED - Sentence Comparison feature has been disabled
# The unified WSD module now handles multi-sentence analysis


# ==================== Page4: Statistics ====================

def render_stats_page(neo4j_conn):
    """StatisticsPage"""
    st.title("📊 Database Statistics")
    
    if not neo4j_conn.connected:
        st.warning("⚠️ Neo4j not connected, cannot show statistics")
        return
    
    with st.spinner("Loading statistics..."):
        stats = neo4j_conn.get_database_stats()
    
    # Node Statistics
    st.subheader("🔵 Node Statistics")
    col1, col2, col3, col4 = st.columns(4)
    
    nodes = stats['nodes']
    
    with col1:
        st.metric("Word", f"{nodes.get('Word', 0):,}")
    with col2:
        st.metric("Sense", f"{nodes.get('Sense', 0):,}")
    with col3:
        st.metric("Root", f"{nodes.get('Root', 0):,}")
    with col4:
        st.metric("Example", f"{nodes.get('Example', 0):,}")
    
    if nodes:
        st.markdown("---")
        st.subheader("Node Type Distribution")
        df_nodes = pd.DataFrame([
            {"Type": k, "Count": v} for k, v in nodes.items()
        ])
        st.bar_chart(df_nodes.set_index("Type"))
    
    # Relationship Statistics
    st.markdown("---")
    st.subheader("🔗 Relationship Statistics")
    
    if stats['relationships']:
        df_rels = pd.DataFrame([
            {"Relationship Type": k, "Count": v} 
            for k, v in stats['relationships'].items()
        ])
        st.dataframe(df_rels, width="stretch")
    
    # POS Distribution
    st.markdown("---")
    st.subheader("📚 POS Distribution (Top 10)")
    
    if stats['pos']:
        df_pos = pd.DataFrame([
            {"POS": k, "Count": v} 
            for k, v in stats['pos'].items()
        ])
        st.bar_chart(df_pos.set_index("POS"))


# ==================== Page5: Settings ====================

def render_settings_page():
    """Settings page"""
    st.title("⚙️ Settings")

    st.subheader("🤖 AI Services")

    # Ollama
    st.markdown("#### Ollama")
    ollama = init_ollama()
    if ollama:
        st.success("✅ Ollama connected (Sailor2:8b)")
        st.info("Ollama is running at http://localhost:11434")
    else:
        st.error("❌ Ollama not connected")
        st.info("Make sure Ollama is running with: `ollama serve`")
        st.info("Model should be pulled: `ollama pull Sailor2:8b`")

    st.markdown("---")

    # Gemini API
    st.markdown("#### Gemini API (Optional)")
    current_key = os.getenv('GEMINI_API_KEY')
    if current_key:
        st.success("✅ Gemini API key configured")
        st.code(f"GEMINI_API_KEY={current_key[:10]}...{current_key[-4:]}")
    else:
        st.warning("⚠️ Gemini API not configured (optional)")
        st.info("Set environment variable: export GEMINI_API_KEY='your-key'")
        st.markdown("[Get API Key](https://ai.google.dev/)")

    st.markdown("---")

    st.subheader("🗄️ Neo4j Database")

    neo4j = init_neo4j()
    if neo4j.connected:
        st.success("✅ Neo4j connected")
    else:
        st.error("❌ Neo4j not connected")
        st.info("Using mock data for demonstration")

    st.markdown("---")

    st.subheader("ℹ️ System Information")
    st.info(f"""
    - **Project**: MLEX - Malay Lexicon System
    - **Version**: v2.1.0
    - **Database**: Neo4j Graph Database
    - **AI Models**: Ollama (Sailor2:8b) + Google Gemini (Optional)
    - **Frontend**: StreamLit
    """)


# ==================== Main program ====================

def main():
    """Main program"""

    neo4j_conn = init_neo4j()
    ollama_service = init_ollama()
    gemini_service = init_gemini()

    # Use first Ollama，if unavailable then use Gemini
    ai_service = ollama_service if ollama_service else gemini_service

    page = render_sidebar()

    if page == "🔍 Word Search":
        render_word_search_page(neo4j_conn)

    elif page == "🎯 WSD":
        render_unified_wsd_page(neo4j_conn, ai_service)

    elif page == "📊 Statistics":
        render_stats_page(neo4j_conn)

    elif page == "➕ Add Word":
        render_word_addition_page(neo4j_conn, ai_service)

    elif page == "⚙️ Settings":
        render_settings_page()


if __name__ == "__main__":
    main()