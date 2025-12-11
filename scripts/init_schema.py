from neo4j import GraphDatabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SchemaInitializer:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="mlex2025"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self.driver.close()
    
    def create_constraints(self):
        """Create uniqueness constraints"""
        constraints = [
            "CREATE CONSTRAINT word_entry_unique IF NOT EXISTS FOR (w:Word) REQUIRE w.entry IS UNIQUE",
            "CREATE CONSTRAINT sense_id_unique IF NOT EXISTS FOR (s:Sense) REQUIRE s.sense_id IS UNIQUE",
            "CREATE CONSTRAINT root_word_unique IF NOT EXISTS FOR (r:Root) REQUIRE r.word IS UNIQUE",
            "CREATE CONSTRAINT domain_name_unique IF NOT EXISTS FOR (d:Domain) REQUIRE d.name IS UNIQUE"
        ]
        
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                    logger.info(f"✅ Created constraint: {constraint.split('FOR')[1].split('REQUIRE')[0].strip()}")
                except Exception as e:
                    if "already exists" in str(e).lower() or "equivalent" in str(e).lower():
                        logger.info(f"ℹ️  Constraint already exists (skipping)")
                    else:
                        logger.warning(f"⚠️  {e}")
    
    def create_indexes(self):
        """Create indexes to improve query performance"""
        indexes = [
            "CREATE INDEX word_pos_idx IF NOT EXISTS FOR (w:Word) ON (w.pos)",
            "CREATE INDEX word_rootWrd_idx IF NOT EXISTS FOR (w:Word) ON (w.rootWrd)",
            "CREATE INDEX sense_definition_idx IF NOT EXISTS FOR (s:Sense) ON (s.definition)",
            "CREATE INDEX sense_index_idx IF NOT EXISTS FOR (s:Sense) ON (s.sense_index)"
        ]
        
        with self.driver.session() as session:
            for index in indexes:
                try:
                    session.run(index)
                    logger.info(f"✅ Created index: {index.split('FOR')[1].split('ON')[0].strip()}")
                except Exception as e:
                    if "already exists" in str(e).lower() or "equivalent" in str(e).lower():
                        logger.info(f"ℹ️  Index already exists (skipping)")
                    else:
                        logger.warning(f"⚠️  {e}")
    
    def create_fulltext_indexes(self):
        """Create fulltext search indexes"""
        
        with self.driver.session() as session:
            # Word fulltext index
            try:
                session.run("""
                    CREATE FULLTEXT INDEX wordFulltext IF NOT EXISTS
                    FOR (w:Word)
                    ON EACH [w.entry, w.fonetik]
                """)
                logger.info("✅ Created fulltext index: wordFulltext")
            except Exception as e:
                logger.info(f"ℹ️  Fulltext index already exists or syntax issue: {e}")
            
            # Sense fulltext index
            try:
                session.run("""
                    CREATE FULLTEXT INDEX senseFulltext IF NOT EXISTS
                    FOR (s:Sense)
                    ON EACH [s.definition]
                """)
                logger.info("✅ Created fulltext index: senseFulltext")
            except Exception as e:
                logger.info(f"ℹ️  Fulltext index already exists or syntax issue: {e}")
    
    def verify_schema(self):
        """Verify schema is correctly created"""
        logger.info("\n" + "="*80)
        logger.info("Verifying Schema...")
        logger.info("="*80)
        
        with self.driver.session() as session:
            # View constraints
            result = session.run("SHOW CONSTRAINTS")
            constraints = list(result)
            logger.info(f"\nNumber of constraints: {len(constraints)}")
            for record in constraints:
                logger.info(f"  • {record.get('name', 'N/A')}")
            
            # View indexes
            result = session.run("SHOW INDEXES")
            indexes = list(result)
            logger.info(f"\nNumber of indexes: {len(indexes)}")
            for record in indexes:
                logger.info(f"  • {record.get('name', 'N/A')}")
        
        logger.info("\n" + "="*80)


def main():
    """Main function"""
    logger.info("="*80)
    logger.info("Starting Neo4j Schema Initialization")
    logger.info("="*80)
    
    initializer = SchemaInitializer()
    
    try:
        # Create constraints
        logger.info("\n1. Creating constraints...")
        initializer.create_constraints()
        
        # Create indexes
        logger.info("\n2. Creating indexes...")
        initializer.create_indexes()
        
        # Create fulltext indexes
        logger.info("\n3. Creating fulltext search indexes...")
        initializer.create_fulltext_indexes()
        
        # Verify
        initializer.verify_schema()
        
        logger.info("\n✅ Schema initialization completed!")
        
    except Exception as e:
        logger.error(f"\n❌ Schema initialization failed: {e}")
    finally:
        initializer.close()


if __name__ == "__main__":
    main()
