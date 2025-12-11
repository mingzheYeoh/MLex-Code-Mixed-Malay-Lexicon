from neo4j import GraphDatabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataValidator:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="mlex123456"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self.driver.close()
    
    def validate(self):
        """Execute complete data validation"""
        logger.info("="*80)
        logger.info("Neo4j Data Validation")
        logger.info("="*80)
        
        with self.driver.session() as session:
            
            # 1. Basic statistics
            logger.info("\n📊 Basic Statistics:")
            logger.info("-"*80)
            
            result = session.run("MATCH (n) RETURN count(n) as total")
            total_nodes = result.single()['total']
            logger.info(f"Total nodes: {total_nodes:,}")
            
            result = session.run("MATCH ()-[r]->() RETURN count(r) as total")
            total_rels = result.single()['total']
            logger.info(f"Total relationships: {total_rels:,}")
            
            # 2. Node type distribution
            logger.info("\n📋 Node Type Distribution:")
            logger.info("-"*80)
            
            result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as label, count(*) as count
                ORDER BY count DESC
            """)
            
            for record in result:
                label = record['label'] or 'NO_LABEL'
                count = record['count']
                logger.info(f"  {label:<15}: {count:>10,} ({count/total_nodes*100:>5.1f}%)")
            
            # 3. Word node check
            logger.info("\n📖 Word Node Check:")
            logger.info("-"*80)
            
            result = session.run("""
                MATCH (w:Word)
                RETURN count(w) as total_words,
                       count(DISTINCT w.entry) as unique_entries
            """)
            record = result.single()
            total_words = record['total_words']
            unique_entries = record['unique_entries']
            
            logger.info(f"Total Word nodes: {total_words:,}")
            logger.info(f"Unique entries: {unique_entries:,}")
            
            if total_words == unique_entries:
                logger.info("✅ No duplicate Word nodes")
            else:
                duplicates = total_words - unique_entries
                logger.warning(f"⚠️  There are {duplicates:,} duplicate Word nodes")
                
                # Show duplicate entries
                result = session.run("""
                    MATCH (w:Word)
                    WITH w.entry as entry, count(*) as cnt
                    WHERE cnt > 1
                    RETURN entry, cnt
                    ORDER BY cnt DESC
                    LIMIT 5
                """)
                
                logger.info("\n  Duplicate entry examples (top 5):")
                for record in result:
                    logger.info(f"    • {record['entry']}: {record['cnt']} nodes")
            
            # 4. Sense node check
            logger.info("\n💭 Sense Node Check:")
            logger.info("-"*80)
            
            result = session.run("""
                MATCH (s:Sense)
                RETURN count(s) as total_senses,
                       count(DISTINCT s.sense_id) as unique_senses
            """)
            record = result.single()
            total_senses = record['total_senses']
            unique_senses = record['unique_senses']
            
            logger.info(f"Total Sense nodes: {total_senses:,}")
            logger.info(f"Unique sense_ids: {unique_senses:,}")
            
            if total_senses == unique_senses:
                logger.info("✅ All Sense nodes have unique sense_ids")
            else:
                logger.error(f"❌ There are duplicate sense_ids!")
            
            # 5. Relationship integrity check
            logger.info("\n🔗 Relationship Integrity Check:")
            logger.info("-"*80)
            
            # Words without Sense
            result = session.run("""
                MATCH (w:Word)
                WHERE NOT (w)-[:HAS_SENSE]->()
                RETURN count(w) as count
            """)
            no_sense = result.single()['count']
            
            if no_sense > 0:
                logger.warning(f"⚠️  {no_sense:,} Word nodes without Sense")
            else:
                logger.info("✅ All Word nodes have Sense")
            
            # Sense without definition
            result = session.run("""
                MATCH (s:Sense)
                WHERE s.definition IS NULL OR s.definition = ''
                RETURN count(s) as count
            """)
            no_def = result.single()['count']
            
            if no_def > 0:
                logger.warning(f"⚠️  {no_def:,} Sense nodes without definition")
            else:
                logger.info("✅ All Sense nodes have definition")
            
            # 6. POS distribution
            logger.info("\n📚 POS Distribution (Top 10):")
            logger.info("-"*80)
            
            result = session.run("""
                MATCH (w:Word)
                WHERE w.pos IS NOT NULL
                RETURN w.pos as pos, count(*) as count
                ORDER BY count DESC
                LIMIT 10
            """)
            
            for record in result:
                logger.info(f"  {record['pos']:<30}: {record['count']:>6,}")
            
            # 7. Domain statistics
            logger.info("\n🏷️  Domain Statistics (Top 10):")
            logger.info("-"*80)
            
            result = session.run("""
                MATCH (d:Domain)<-[:IN_DOMAIN]-(s:Sense)
                RETURN d.name as domain, count(s) as count
                ORDER BY count DESC
                LIMIT 10
            """)
            
            domains = list(result)
            if domains:
                for record in domains:
                    logger.info(f"  {record['domain']:<30}: {record['count']:>6,}")
            else:
                logger.info("  (No Domain data)")
            
            # 8. Root statistics
            logger.info("\n🌱 Root Statistics:")
            logger.info("-"*80)
            
            result = session.run("""
                MATCH (r:Root)
                OPTIONAL MATCH (r)<-[:HAS_ROOT]-(w:Word)
                WITH r, count(w) as derived_count
                RETURN count(r) as total_roots,
                       avg(derived_count) as avg_derived,
                       max(derived_count) as max_derived
            """)
            record = result.single()
            
            if record['total_roots'] > 0:
                logger.info(f"  Total Root nodes: {record['total_roots']:,}")
                logger.info(f"  Average derived words: {record['avg_derived']:.2f}")
                logger.info(f"  Maximum derived words: {record['max_derived']:,}")
            else:
                logger.info("  (No Root data)")
            
            # 9. Example statistics
            logger.info("\n📝 Example Statistics:")
            logger.info("-"*80)
            
            result = session.run("""
                MATCH (e:Example)
                RETURN count(e) as total_examples
            """)
            total_examples = result.single()['total_examples']
            
            if total_examples > 0:
                logger.info(f"  Total Example nodes: {total_examples:,}")
                
                result = session.run("""
                    MATCH (s:Sense)-[:HAS_EXAMPLE]->(e:Example)
                    WITH s, count(e) as example_count
                    RETURN avg(example_count) as avg_examples
                """)
                avg_examples = result.single()['avg_examples']
                logger.info(f"  Average examples per Sense: {avg_examples:.2f}")
            else:
                logger.info("  (No Example data)")
            
            # 10. Final summary
            logger.info("\n" + "="*80)
            logger.info("✅ Validation Summary:")
            logger.info("="*80)
            
            issues = []
            
            if total_words != unique_entries:
                issues.append(f"There are {total_words - unique_entries:,} duplicate Word nodes")
            
            if total_senses != unique_senses:
                issues.append(f"There are duplicate Sense nodes")
            
            if no_sense > 0:
                issues.append(f"{no_sense:,} Words without Sense")
            
            if no_def > 0:
                issues.append(f"{no_def:,} Senses without definition")
            
            if issues:
                logger.warning("\nFound the following issues:")
                for issue in issues:
                    logger.warning(f"  ⚠️  {issue}")
                logger.warning("\nRecommend cleaning data and re-importing")
            else:
                logger.info("\n✅ Data integrity is good!")
                logger.info("✅ Database is ready to use")


def main():
    """Main function"""
    validator = DataValidator()
    
    try:
        validator.validate()
    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
    finally:
        validator.close()


if __name__ == "__main__":
    main()
