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
        """执行完整的数据验证"""
        logger.info("="*80)
        logger.info("Neo4j 数据验证")
        logger.info("="*80)
        
        with self.driver.session() as session:
            
            # 1. 基本统计
            logger.info("\n📊 基本统计:")
            logger.info("-"*80)
            
            result = session.run("MATCH (n) RETURN count(n) as total")
            total_nodes = result.single()['total']
            logger.info(f"总节点数: {total_nodes:,}")
            
            result = session.run("MATCH ()-[r]->() RETURN count(r) as total")
            total_rels = result.single()['total']
            logger.info(f"总关系数: {total_rels:,}")
            
            # 2. 节点类型分布
            logger.info("\n📋 节点类型分布:")
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
            
            # 3. Word节点检查
            logger.info("\n📖 Word节点检查:")
            logger.info("-"*80)
            
            result = session.run("""
                MATCH (w:Word)
                RETURN count(w) as total_words,
                       count(DISTINCT w.entry) as unique_entries
            """)
            record = result.single()
            total_words = record['total_words']
            unique_entries = record['unique_entries']
            
            logger.info(f"Word节点总数: {total_words:,}")
            logger.info(f"唯一词条数: {unique_entries:,}")
            
            if total_words == unique_entries:
                logger.info("✅ 没有重复的Word节点")
            else:
                duplicates = total_words - unique_entries
                logger.warning(f"⚠️  有 {duplicates:,} 个重复的Word节点")
                
                # 显示重复的词条
                result = session.run("""
                    MATCH (w:Word)
                    WITH w.entry as entry, count(*) as cnt
                    WHERE cnt > 1
                    RETURN entry, cnt
                    ORDER BY cnt DESC
                    LIMIT 5
                """)
                
                logger.info("\n  重复词条示例（前5个）:")
                for record in result:
                    logger.info(f"    • {record['entry']}: {record['cnt']} 个节点")
            
            # 4. Sense节点检查
            logger.info("\n💭 Sense节点检查:")
            logger.info("-"*80)
            
            result = session.run("""
                MATCH (s:Sense)
                RETURN count(s) as total_senses,
                       count(DISTINCT s.sense_id) as unique_senses
            """)
            record = result.single()
            total_senses = record['total_senses']
            unique_senses = record['unique_senses']
            
            logger.info(f"Sense节点总数: {total_senses:,}")
            logger.info(f"唯一sense_id数: {unique_senses:,}")
            
            if total_senses == unique_senses:
                logger.info("✅ 所有Sense节点都有唯一的sense_id")
            else:
                logger.error(f"❌ 有重复的sense_id！")
            
            # 5. 关系完整性检查
            logger.info("\n🔗 关系完整性检查:")
            logger.info("-"*80)
            
            # Word没有Sense
            result = session.run("""
                MATCH (w:Word)
                WHERE NOT (w)-[:HAS_SENSE]->()
                RETURN count(w) as count
            """)
            no_sense = result.single()['count']
            
            if no_sense > 0:
                logger.warning(f"⚠️  {no_sense:,} 个Word节点没有Sense")
            else:
                logger.info("✅ 所有Word节点都有Sense")
            
            # Sense没有定义
            result = session.run("""
                MATCH (s:Sense)
                WHERE s.definition IS NULL OR s.definition = ''
                RETURN count(s) as count
            """)
            no_def = result.single()['count']
            
            if no_def > 0:
                logger.warning(f"⚠️  {no_def:,} 个Sense节点没有定义")
            else:
                logger.info("✅ 所有Sense节点都有定义")
            
            # 6. 词性分布
            logger.info("\n📚 词性分布 (Top 10):")
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
            
            # 7. Domain统计
            logger.info("\n🏷️  Domain统计 (Top 10):")
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
                logger.info("  (没有Domain数据)")
            
            # 8. Root统计
            logger.info("\n🌱 Root统计:")
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
                logger.info(f"  Root节点总数: {record['total_roots']:,}")
                logger.info(f"  平均派生词数: {record['avg_derived']:.2f}")
                logger.info(f"  最多派生词数: {record['max_derived']:,}")
            else:
                logger.info("  (没有Root数据)")
            
            # 9. Example统计
            logger.info("\n📝 Example统计:")
            logger.info("-"*80)
            
            result = session.run("""
                MATCH (e:Example)
                RETURN count(e) as total_examples
            """)
            total_examples = result.single()['total_examples']
            
            if total_examples > 0:
                logger.info(f"  Example节点总数: {total_examples:,}")
                
                result = session.run("""
                    MATCH (s:Sense)-[:HAS_EXAMPLE]->(e:Example)
                    WITH s, count(e) as example_count
                    RETURN avg(example_count) as avg_examples
                """)
                avg_examples = result.single()['avg_examples']
                logger.info(f"  每个Sense平均例句: {avg_examples:.2f}")
            else:
                logger.info("  (没有Example数据)")
            
            # 10. 最终判断
            logger.info("\n" + "="*80)
            logger.info("✅ 验证总结:")
            logger.info("="*80)
            
            issues = []
            
            if total_words != unique_entries:
                issues.append(f"有 {total_words - unique_entries:,} 个重复的Word节点")
            
            if total_senses != unique_senses:
                issues.append(f"有重复的Sense节点")
            
            if no_sense > 0:
                issues.append(f"{no_sense:,} 个Word没有Sense")
            
            if no_def > 0:
                issues.append(f"{no_def:,} 个Sense没有定义")
            
            if issues:
                logger.warning("\n发现以下问题:")
                for issue in issues:
                    logger.warning(f"  ⚠️  {issue}")
                logger.warning("\n建议清理后重新导入数据")
            else:
                logger.info("\n✅ 数据完整性良好！")
                logger.info("✅ 可以开始使用数据库")


def main():
    """主函数"""
    validator = DataValidator()
    
    try:
        validator.validate()
    except Exception as e:
        logger.error(f"❌ 验证失败: {e}")
    finally:
        validator.close()


if __name__ == "__main__":
    main()
