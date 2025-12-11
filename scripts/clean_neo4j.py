from neo4j import GraphDatabase
import logging
import subprocess
import time
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CompleteNeo4jWiper:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="mlex2025"):
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None
    
    def connect(self):
        """Connect to Neo4j"""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            return True
        except Exception as e:
            logger.error(f"Unable to connect to Neo4j: {e}")
            return False
    
    def close(self):
        """Close connection"""
        if self.driver:
            self.driver.close()
    
    def get_database_info(self):
        """Get database information"""
        with self.driver.session() as session:
            # Basic statistics
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()['count']
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()['count']
            
            # Metadata
            labels = [r['label'] for r in session.run("CALL db.labels()")]
            prop_keys = [r['propertyKey'] for r in session.run("CALL db.propertyKeys()")]
            rel_types = [r['relationshipType'] for r in session.run("CALL db.relationshipTypes()")]
            
            # Constraints and indexes
            constraints = [r['name'] for r in session.run("SHOW CONSTRAINTS")]
            indexes = [r['name'] for r in session.run("SHOW INDEXES") 
                      if r.get('type') != 'LOOKUP']
            
            return {
                'nodes': node_count,
                'relationships': rel_count,
                'labels': labels,
                'property_keys': prop_keys,
                'relationship_types': rel_types,
                'constraints': constraints,
                'indexes': indexes
            }
    
    def method_1_cypher_wipe(self):
        """
        Method 1: Clear using Cypher (standard method)
        Will delete all data and constraints/indexes, but metadata may remain
        """
        logger.info("\n" + "="*80)
        logger.info("Method 1: Cypher clear (recommended, no need to restart Neo4j)")
        logger.info("="*80)
        
        info = self.get_database_info()
        
        logger.info(f"\nCurrent database status:")
        logger.info(f"  Nodes: {info['nodes']:,}")
        logger.info(f"  Relationships: {info['relationships']:,}")
        logger.info(f"  Labels: {len(info['labels'])}")
        logger.info(f"  Property Keys: {len(info['property_keys'])}")
        logger.info(f"  Relationship Types: {len(info['relationship_types'])}")
        logger.info(f"  Constraints: {len(info['constraints'])}")
        logger.info(f"  Indexes: {len(info['indexes'])}")
        
        confirm = input("\nConfirm execution of clear? (yes/no): ").strip().lower()
        if confirm != 'yes':
            logger.info("❌ Operation cancelled")
            return False
        
        with self.driver.session() as session:
            # 1. Delete all data
            logger.info("\nStep 1: Deleting all nodes and relationships...")
            session.run("MATCH (n) DETACH DELETE n")
            logger.info("✅ Complete")
            
            # 2. Delete constraints
            logger.info("\nStep 2: Deleting all constraints...")
            for constraint in info['constraints']:
                try:
                    session.run(f"DROP CONSTRAINT {constraint}")
                    logger.info(f"  ✅ Deleted: {constraint}")
                except Exception as e:
                    logger.warning(f"  ⚠️  {e}")
            
            # 3. Delete indexes
            logger.info("\nStep 3: Deleting all indexes...")
            for index in info['indexes']:
                try:
                    session.run(f"DROP INDEX {index}")
                    logger.info(f"  ✅ Deleted: {index}")
                except Exception as e:
                    logger.warning(f"  ⚠️  {e}")
        
        # Verify
        logger.info("\nVerifying cleanup results...")
        info_after = self.get_database_info()
        
        logger.info(f"\nStatus after cleanup:")
        logger.info(f"  Nodes: {info_after['nodes']:,}")
        logger.info(f"  Relationships: {info_after['relationships']:,}")
        logger.info(f"  Labels: {len(info_after['labels'])}")
        logger.info(f"  Property Keys: {len(info_after['property_keys'])}")
        logger.info(f"  Relationship Types: {len(info_after['relationship_types'])}")
        
        if info_after['labels'] or info_after['property_keys'] or info_after['relationship_types']:
            logger.warning("\n⚠️  Metadata still exists (this is normal)")
            logger.info("   Neo4j caches metadata information")
            logger.info("   To completely clear metadata, use Method 2")
        else:
            logger.info("\n✅ Database completely cleared!")
        
        return True
    
    def method_2_database_delete(self):
        """
        Method 2: Delete entire database (requires stopping Neo4j)
        This will completely clear all data and metadata
        """
        logger.info("\n" + "="*80)
        logger.info("Method 2: Complete database deletion (requires stopping Neo4j)")
        logger.info("="*80)
        
        logger.warning("\n⚠️  Warning: This method requires:")
        logger.warning("  1. Stop Neo4j service")
        logger.warning("  2. Delete database files")
        logger.warning("  3. Restart Neo4j service")
        logger.warning("  4. This will permanently delete all data!")
        
        # Try to detect Neo4j installation path
        possible_paths = [
            "/var/lib/neo4j/data/databases/neo4j",
            "/var/lib/neo4j/data/databases/graph.db",
            os.path.expanduser("~/neo4j/data/databases/neo4j"),
            "/usr/local/var/neo4j/data/databases/neo4j"
        ]
        
        neo4j_data_path = None
        for path in possible_paths:
            if os.path.exists(path):
                neo4j_data_path = path
                break
        
        if neo4j_data_path:
            logger.info(f"\nDetected Neo4j database path: {neo4j_data_path}")
        else:
            logger.warning("\nUnable to auto-detect Neo4j database path")
            neo4j_data_path = input("Please enter Neo4j database path: ").strip()
        
        confirm = input("\nConfirm complete deletion? (type 'DELETE' to confirm): ").strip()
        if confirm != 'DELETE':
            logger.info("❌ Operation cancelled")
            return False
        
        try:
            # 1. Close current connection
            logger.info("\nStep 1: Closing database connection...")
            self.close()
            logger.info("✅ Complete")
            
            # 2. Stop Neo4j
            logger.info("\nStep 2: Stopping Neo4j service...")
            logger.info("Trying multiple stop commands...")
            
            stop_commands = [
                ["systemctl", "stop", "neo4j"],
                ["service", "neo4j", "stop"],
                ["neo4j", "stop"],
                ["/usr/bin/neo4j", "stop"]
            ]
            
            stopped = False
            for cmd in stop_commands:
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        logger.info(f"✅ Command succeeded: {' '.join(cmd)}")
                        stopped = True
                        break
                except Exception as e:
                    continue
            
            if not stopped:
                logger.error("❌ Unable to auto-stop Neo4j")
                logger.info("Please manually stop Neo4j service, then press Enter to continue...")
                input()
            else:
                time.sleep(3)  # Wait for service to fully stop
            
            # 3. Delete database files
            logger.info("\nStep 3: Deleting database files...")
            if os.path.exists(neo4j_data_path):
                import shutil
                shutil.rmtree(neo4j_data_path)
                logger.info(f"✅ Deleted: {neo4j_data_path}")
            else:
                logger.warning(f"⚠️  Path does not exist: {neo4j_data_path}")
            
            # 4. Restart Neo4j
            logger.info("\nStep 4: Restarting Neo4j service...")
            
            start_commands = [
                ["systemctl", "start", "neo4j"],
                ["service", "neo4j", "start"],
                ["neo4j", "start"],
                ["/usr/bin/neo4j", "start"]
            ]
            
            started = False
            for cmd in start_commands:
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        logger.info(f"✅ Command succeeded: {' '.join(cmd)}")
                        started = True
                        break
                except Exception as e:
                    continue
            
            if not started:
                logger.error("❌ Unable to auto-start Neo4j")
                logger.info("Please manually start Neo4j service")
                return False
            
            # 5. Wait for service to start
            logger.info("\nStep 5: Waiting for Neo4j service to start...")
            time.sleep(5)
            
            # 6. Reconnect and verify
            logger.info("\nStep 6: Verifying database...")
            if self.connect():
                info = self.get_database_info()
                logger.info(f"\nNew database status:")
                logger.info(f"  Nodes: {info['nodes']}")
                logger.info(f"  Relationships: {info['relationships']}")
                logger.info(f"  Labels: {len(info['labels'])}")
                logger.info(f"  Property Keys: {len(info['property_keys'])}")
                logger.info(f"  Relationship Types: {len(info['relationship_types'])}")
                
                if info['nodes'] == 0 and len(info['labels']) == 0:
                    logger.info("\n✅ Database completely reset! All metadata cleared!")
                    return True
                else:
                    logger.warning("\n⚠️  Database may not be completely cleared")
                    return False
            else:
                logger.error("❌ Unable to connect to new database")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error during deletion: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Main function"""
    print("\n" + "="*80)
    print("Neo4j Complete Wipe Tool")
    print("="*80)
    
    print("\nSelect clear method:")
    print("  1. Cypher clear (recommended, no restart needed)")
    print("     - Delete all nodes, relationships, constraints, indexes")
    print("     - Metadata (labels/property keys) may remain")
    print("     - Does not affect service operation")
    print()
    print("  2. Complete deletion (requires stopping and restarting Neo4j)")
    print("     - Delete entire database files")
    print("     - Completely clear all metadata")
    print("     - Requires root or Neo4j admin privileges")
    print()
    
    choice = input("Please select (1/2) [default: 1]: ").strip() or "1"
    
    wiper = CompleteNeo4jWiper()
    
    try:
        if choice == "1":
            if wiper.connect():
                wiper.method_1_cypher_wipe()
        elif choice == "2":
            if wiper.connect():
                wiper.method_2_database_delete()
        else:
            logger.error("❌ Invalid selection")
    except Exception as e:
        logger.error(f"❌ Execution failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        wiper.close()


if __name__ == "__main__":
    main()