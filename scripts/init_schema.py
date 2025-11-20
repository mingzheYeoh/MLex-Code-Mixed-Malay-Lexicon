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
        """创建唯一性约束"""
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
        """创建索引以提升查询性能"""
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
        """创建全文搜索索引"""
        
        with self.driver.session() as session:
            # Word全文索引
            try:
                session.run("""
                    CREATE FULLTEXT INDEX wordFulltext IF NOT EXISTS
                    FOR (w:Word)
                    ON EACH [w.entry, w.fonetik]
                """)
                logger.info("✅ Created fulltext index: wordFulltext")
            except Exception as e:
                logger.info(f"ℹ️  Fulltext index already exists or syntax issue: {e}")
            
            # Sense全文索引
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
        """验证schema是否正确创建"""
        logger.info("\n" + "="*80)
        logger.info("验证Schema...")
        logger.info("="*80)
        
        with self.driver.session() as session:
            # 查看约束
            result = session.run("SHOW CONSTRAINTS")
            constraints = list(result)
            logger.info(f"\n约束数量: {len(constraints)}")
            for record in constraints:
                logger.info(f"  • {record.get('name', 'N/A')}")
            
            # 查看索引
            result = session.run("SHOW INDEXES")
            indexes = list(result)
            logger.info(f"\n索引数量: {len(indexes)}")
            for record in indexes:
                logger.info(f"  • {record.get('name', 'N/A')}")
        
        logger.info("\n" + "="*80)


def main():
    """主函数"""
    logger.info("="*80)
    logger.info("开始初始化Neo4j Schema")
    logger.info("="*80)
    
    initializer = SchemaInitializer()
    
    try:
        # 创建约束
        logger.info("\n1. 创建约束...")
        initializer.create_constraints()
        
        # 创建索引
        logger.info("\n2. 创建索引...")
        initializer.create_indexes()
        
        # 创建全文索引
        logger.info("\n3. 创建全文搜索索引...")
        initializer.create_fulltext_indexes()
        
        # 验证
        initializer.verify_schema()
        
        logger.info("\n✅ Schema初始化完成！")
        
    except Exception as e:
        logger.error(f"\n❌ Schema初始化失败: {e}")
    finally:
        initializer.close()


if __name__ == "__main__":
    main()
