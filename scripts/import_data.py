import pandas as pd
from neo4j import GraphDatabase
import logging
from datetime import datetime
from tqdm import tqdm
import sys
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Neo4jImporter:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="mlex2025"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.stats = {
            'words': 0,
            'senses': 0,
            'roots': 0,
            'domains': 0,
            'examples': 0,
            'synonyms': 0,
            'errors': 0
        }
        # Track created sense_ids to avoid duplicates
        self.created_sense_ids = set()
    
    def close(self):
        self.driver.close()
    
    def clean_text(self, text):
        """Clean text"""
        if pd.isna(text):
            return None
        text = str(text).strip()
        return text if text and text.lower() not in ['nan', 'null', ''] else None
    
    def generate_unique_sense_id(self, entry, index, row_index):
        """
        Generate unique sense_id
        Uses entry_index_number format
        If entry_index already exists, add a sequence number
        """
        base_sense_id = f"{entry}_{index}" if index else f"{entry}_0"
        
        # If base ID doesn't exist, use it directly
        if base_sense_id not in self.created_sense_ids:
            self.created_sense_ids.add(base_sense_id)
            return base_sense_id
        
        # If exists, add sequence number (use row_index to ensure uniqueness)
        unique_sense_id = f"{base_sense_id}_r{row_index}"
        self.created_sense_ids.add(unique_sense_id)
        
        logger.warning(f"Duplicate sense_id detected: {base_sense_id}, using {unique_sense_id}")
        return unique_sense_id
    
    def create_word_node(self, tx, row):
        """Create Word node (using MERGE to avoid duplicates)"""
        entry = self.clean_text(row.get('entry'))
        
        query = """
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
            w.created_at = datetime()
        ON MATCH SET
            w.updated_at = datetime()
        RETURN w
        """
        
        tx.run(query,
            entry=entry,
            rootWrd=self.clean_text(row.get('rootWrd')),
            fonetik=self.clean_text(row.get('fonetik')),
            pos=self.clean_text(row.get('pos')),
            label=self.clean_text(row.get('label')),
            asal=self.clean_text(row.get('asal')),
            passive=self.clean_text(row.get('passive')),
            diaLan=self.clean_text(row.get('diaLan')),
            domain=self.clean_text(row.get('domain')),
            references=self.clean_text(row.get('references'))
        )
    
    def create_sense_node(self, tx, entry, definition, index, row_index):
        """
        Create Sense node
        Uses unique sense_id (including row_index to avoid duplicates)
        """
        sense_id = self.generate_unique_sense_id(entry, index, row_index)
        
        # Smart handling of sense_index: supports numbers and letters
        if index:
            # If it's a number, convert to int; if it's a letter, keep as string
            try:
                sense_index_value = int(index)
            except (ValueError, TypeError):
                # Letter index: 'a'=1, 'b'=2, 'c'=3, etc.
                if isinstance(index, str) and len(index) == 1 and index.isalpha():
                    sense_index_value = ord(index.lower()) - ord('a') + 1
                else:
                    # Other cases, keep as string
                    sense_index_value = str(index)
        else:
            sense_index_value = 0
        
        query = """
        CREATE (s:Sense {
            sense_id: $sense_id,
            definition: $definition,
            sense_index: $sense_index,
            confidence: 1.0,
            created_at: datetime()
        })
        RETURN s
        """
        
        tx.run(query,
            sense_id=sense_id,
            definition=definition,
            sense_index=sense_index_value
        )
        
        return sense_id
    
    def create_word_sense_relationship(self, tx, entry, sense_id):
        """Create Word to Sense relationship"""
        query = """
        MATCH (w:Word {entry: $entry})
        MATCH (s:Sense {sense_id: $sense_id})
        MERGE (w)-[:HAS_SENSE {primary: true}]->(s)
        """
        tx.run(query, entry=entry, sense_id=sense_id)
    
    def create_root_relationship(self, tx, entry, root_word):
        """Create Root relationship"""
        if not root_word or root_word == entry:
            return
        
        query = """
        MATCH (w:Word {entry: $entry})
        MERGE (r:Root {word: $root_word})
        MERGE (w)-[:HAS_ROOT]->(r)
        """
        tx.run(query, entry=entry, root_word=root_word)
    
    def create_example_node(self, tx, sense_id, example_text):
        """Create Example node"""
        if not example_text:
            return
        
        query = """
        MATCH (s:Sense {sense_id: $sense_id})
        CREATE (e:Example {
            text: $example_text,
            created_at: datetime()
        })
        MERGE (s)-[:HAS_EXAMPLE {order: 1}]->(e)
        """
        tx.run(query, sense_id=sense_id, example_text=example_text)
    
    def create_domain_relationship(self, tx, sense_id, domain_name):
        """Create Domain relationship"""
        if not domain_name:
            return
        
        query = """
        MATCH (s:Sense {sense_id: $sense_id})
        MERGE (d:Domain {name: $domain_name})
        MERGE (s)-[:IN_DOMAIN]->(d)
        """
        tx.run(query, sense_id=sense_id, domain_name=domain_name)
    
    def create_synonym_relationships(self, tx, entry, synonyms):
        """Create synonym relationships"""
        if not synonyms:
            return
        
        # Split synonyms (assuming comma or semicolon separated)
        synonym_list = [s.strip() for s in str(synonyms).replace(';', ',').split(',')]
        
        for synonym in synonym_list:
            if synonym and synonym != entry:
                query = """
                MATCH (w1:Word {entry: $entry})
                MERGE (w2:Word {entry: $synonym})
                MERGE (w1)-[:SYNONYM {strength: 1.0}]->(w2)
                """
                tx.run(query, entry=entry, synonym=synonym)
    
    def import_row(self, session, row, row_index):
        """Import single row of data"""
        try:
            entry = self.clean_text(row.get('entry'))
            if not entry:
                return False
            
            # 1. Create Word node (MERGE, no duplicates)
            session.execute_write(self.create_word_node, row)
            self.stats['words'] += 1
            
            # 2. Create Root relationship
            root_word = self.clean_text(row.get('rootWrd'))
            if root_word:
                session.execute_write(self.create_root_relationship, entry, root_word)
                self.stats['roots'] += 1
            
            # 3. Create Sense node (using unique ID)
            definition = self.clean_text(row.get('def'))
            if definition:
                index = self.clean_text(row.get('index'))
                sense_id = session.execute_write(
                    self.create_sense_node, 
                    entry, 
                    definition, 
                    index,
                    row_index  # Pass row_index to ensure uniqueness
                )
                self.stats['senses'] += 1
                
                # 4. Create Word-Sense relationship
                session.execute_write(self.create_word_sense_relationship, entry, sense_id)
                
                # 5. Create Example node
                example = self.clean_text(row.get('exp'))
                if example:
                    session.execute_write(self.create_example_node, sense_id, example)
                    self.stats['examples'] += 1
                
                # 6. Create Domain relationship
                domain = self.clean_text(row.get('domain'))
                if domain:
                    session.execute_write(self.create_domain_relationship, sense_id, domain)
                    self.stats['domains'] += 1
            
            # 7. Create synonym relationships
            sinonim = self.clean_text(row.get('sinonim'))
            if sinonim:
                session.execute_write(self.create_synonym_relationships, entry, sinonim)
                self.stats['synonyms'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Error importing row {row_index} (entry: {entry}): {e}")
            self.stats['errors'] += 1
            return False
    
    def import_csv(self, csv_file, batch_size=1000):
        """Batch import CSV data"""
        logger.info(f"Starting data import: {csv_file}")
        
        # Read CSV
        df = pd.read_csv(csv_file)
        total_rows = len(df)
        logger.info(f"Total rows: {total_rows:,}")
        
        # Process in batches
        with self.driver.session() as session:
            for i in tqdm(range(0, total_rows, batch_size), desc="Import progress"):
                chunk = df.iloc[i:i+batch_size]
                logger.info(f"Processing chunk {i//batch_size + 1}...")
                
                for idx, row in chunk.iterrows():
                    self.import_row(session, row, idx)
        
        # Print statistics
        logger.info("\n" + "=" * 80)
        logger.info("Import completed! Statistics:")
        logger.info("=" * 80)
        logger.info(f"Word nodes created: {self.stats['words']:,}")
        logger.info(f"Sense nodes created: {self.stats['senses']:,}")
        logger.info(f"Root relationships created: {self.stats['roots']:,}")
        logger.info(f"Domain relationships created: {self.stats['domains']:,}")
        logger.info(f"Example nodes created: {self.stats['examples']:,}")
        logger.info(f"Synonym relationships created: {self.stats['synonyms']:,}")
        logger.info(f"Error count: {self.stats['errors']:,}")
        logger.info("=" * 80)


def main():
    
    CSV_FILE = "../data/final_dataset_super_cleaned.csv"  
    
    if not os.path.exists(CSV_FILE):
        logger.error(f"File does not exist: {CSV_FILE}")
        logger.info("Please modify the CSV_FILE variable to the correct path")
        sys.exit(1)
    
    # Create importer
    importer = Neo4jImporter()
    
    try:
        # Import data
        start_time = datetime.now()
        importer.import_csv(CSV_FILE, batch_size=1000)
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        logger.info(f"\nTotal time: {duration:.2f} seconds")
        logger.info(f"Average speed: {importer.stats['words']/duration:.0f} records/sec")
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        sys.exit(1)
    finally:
        importer.close()
    
    logger.info("\n✅ Data import completed!")


if __name__ == "__main__":
    main()
