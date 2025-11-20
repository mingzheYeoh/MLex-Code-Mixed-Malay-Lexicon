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
        """连接到Neo4j"""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            return True
        except Exception as e:
            logger.error(f"无法连接到Neo4j: {e}")
            return False
    
    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()
    
    def get_database_info(self):
        """获取数据库信息"""
        with self.driver.session() as session:
            # 基本统计
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()['count']
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()['count']
            
            # 元数据
            labels = [r['label'] for r in session.run("CALL db.labels()")]
            prop_keys = [r['propertyKey'] for r in session.run("CALL db.propertyKeys()")]
            rel_types = [r['relationshipType'] for r in session.run("CALL db.relationshipTypes()")]
            
            # 约束和索引
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
        方法1: 使用Cypher清除（标准方法）
        会删除所有数据和约束/索引，但元数据可能保留
        """
        logger.info("\n" + "="*80)
        logger.info("方法1: Cypher清除（推荐，无需重启Neo4j）")
        logger.info("="*80)
        
        info = self.get_database_info()
        
        logger.info(f"\n当前数据库状态:")
        logger.info(f"  节点: {info['nodes']:,}")
        logger.info(f"  关系: {info['relationships']:,}")
        logger.info(f"  Labels: {len(info['labels'])}")
        logger.info(f"  Property Keys: {len(info['property_keys'])}")
        logger.info(f"  Relationship Types: {len(info['relationship_types'])}")
        logger.info(f"  约束: {len(info['constraints'])}")
        logger.info(f"  索引: {len(info['indexes'])}")
        
        confirm = input("\n确认执行清除？(yes/no): ").strip().lower()
        if confirm != 'yes':
            logger.info("❌ 操作已取消")
            return False
        
        with self.driver.session() as session:
            # 1. 删除所有数据
            logger.info("\n步骤1: 删除所有节点和关系...")
            session.run("MATCH (n) DETACH DELETE n")
            logger.info("✅ 完成")
            
            # 2. 删除约束
            logger.info("\n步骤2: 删除所有约束...")
            for constraint in info['constraints']:
                try:
                    session.run(f"DROP CONSTRAINT {constraint}")
                    logger.info(f"  ✅ 已删除: {constraint}")
                except Exception as e:
                    logger.warning(f"  ⚠️  {e}")
            
            # 3. 删除索引
            logger.info("\n步骤3: 删除所有索引...")
            for index in info['indexes']:
                try:
                    session.run(f"DROP INDEX {index}")
                    logger.info(f"  ✅ 已删除: {index}")
                except Exception as e:
                    logger.warning(f"  ⚠️  {e}")
        
        # 验证
        logger.info("\n验证清理结果...")
        info_after = self.get_database_info()
        
        logger.info(f"\n清理后状态:")
        logger.info(f"  节点: {info_after['nodes']:,}")
        logger.info(f"  关系: {info_after['relationships']:,}")
        logger.info(f"  Labels: {len(info_after['labels'])}")
        logger.info(f"  Property Keys: {len(info_after['property_keys'])}")
        logger.info(f"  Relationship Types: {len(info_after['relationship_types'])}")
        
        if info_after['labels'] or info_after['property_keys'] or info_after['relationship_types']:
            logger.warning("\n⚠️  元数据仍然存在（这是正常的）")
            logger.info("   Neo4j会缓存元数据信息")
            logger.info("   要完全清除元数据，请使用方法2")
        else:
            logger.info("\n✅ 数据库已完全清空！")
        
        return True
    
    def method_2_database_delete(self):
        """
        方法2: 删除整个数据库（需要停止Neo4j）
        这会完全清除所有数据和元数据
        """
        logger.info("\n" + "="*80)
        logger.info("方法2: 完全删除数据库（需要停止Neo4j）")
        logger.info("="*80)
        
        logger.warning("\n⚠️  警告: 这个方法需要:")
        logger.warning("  1. 停止Neo4j服务")
        logger.warning("  2. 删除数据库文件")
        logger.warning("  3. 重启Neo4j服务")
        logger.warning("  4. 这会永久删除所有数据！")
        
        # 尝试检测Neo4j安装路径
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
            logger.info(f"\n检测到Neo4j数据库路径: {neo4j_data_path}")
        else:
            logger.warning("\n无法自动检测Neo4j数据库路径")
            neo4j_data_path = input("请输入Neo4j数据库路径: ").strip()
        
        confirm = input("\n确认执行完全删除？(输入 'DELETE' 确认): ").strip()
        if confirm != 'DELETE':
            logger.info("❌ 操作已取消")
            return False
        
        try:
            # 1. 关闭当前连接
            logger.info("\n步骤1: 关闭数据库连接...")
            self.close()
            logger.info("✅ 完成")
            
            # 2. 停止Neo4j
            logger.info("\n步骤2: 停止Neo4j服务...")
            logger.info("尝试多种停止命令...")
            
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
                        logger.info(f"✅ 使用命令成功: {' '.join(cmd)}")
                        stopped = True
                        break
                except Exception as e:
                    continue
            
            if not stopped:
                logger.error("❌ 无法自动停止Neo4j")
                logger.info("请手动停止Neo4j服务，然后按Enter继续...")
                input()
            else:
                time.sleep(3)  # 等待服务完全停止
            
            # 3. 删除数据库文件
            logger.info("\n步骤3: 删除数据库文件...")
            if os.path.exists(neo4j_data_path):
                import shutil
                shutil.rmtree(neo4j_data_path)
                logger.info(f"✅ 已删除: {neo4j_data_path}")
            else:
                logger.warning(f"⚠️  路径不存在: {neo4j_data_path}")
            
            # 4. 重启Neo4j
            logger.info("\n步骤4: 重启Neo4j服务...")
            
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
                        logger.info(f"✅ 使用命令成功: {' '.join(cmd)}")
                        started = True
                        break
                except Exception as e:
                    continue
            
            if not started:
                logger.error("❌ 无法自动启动Neo4j")
                logger.info("请手动启动Neo4j服务")
                return False
            
            # 5. 等待服务启动
            logger.info("\n步骤5: 等待Neo4j服务启动...")
            time.sleep(5)
            
            # 6. 重新连接并验证
            logger.info("\n步骤6: 验证数据库...")
            if self.connect():
                info = self.get_database_info()
                logger.info(f"\n新数据库状态:")
                logger.info(f"  节点: {info['nodes']}")
                logger.info(f"  关系: {info['relationships']}")
                logger.info(f"  Labels: {len(info['labels'])}")
                logger.info(f"  Property Keys: {len(info['property_keys'])}")
                logger.info(f"  Relationship Types: {len(info['relationship_types'])}")
                
                if info['nodes'] == 0 and len(info['labels']) == 0:
                    logger.info("\n✅ 数据库已完全重置！所有元数据已清除！")
                    return True
                else:
                    logger.warning("\n⚠️  数据库可能未完全清空")
                    return False
            else:
                logger.error("❌ 无法连接到新数据库")
                return False
                
        except Exception as e:
            logger.error(f"❌ 删除过程出错: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """主函数"""
    print("\n" + "="*80)
    print("Neo4j 完全清除工具")
    print("="*80)
    
    print("\n选择清除方法:")
    print("  1. Cypher清除（推荐，无需重启）")
    print("     - 删除所有节点、关系、约束、索引")
    print("     - 元数据（labels/property keys）可能保留")
    print("     - 不影响服务运行")
    print()
    print("  2. 完全删除（需要停止和重启Neo4j）")
    print("     - 删除整个数据库文件")
    print("     - 完全清除所有元数据")
    print("     - 需要root权限或Neo4j管理员权限")
    print()
    
    choice = input("请选择 (1/2) [默认: 1]: ").strip() or "1"
    
    wiper = CompleteNeo4jWiper()
    
    try:
        if choice == "1":
            if wiper.connect():
                wiper.method_1_cypher_wipe()
        elif choice == "2":
            if wiper.connect():
                wiper.method_2_database_delete()
        else:
            logger.error("❌ 无效选择")
    except Exception as e:
        logger.error(f"❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        wiper.close()


if __name__ == "__main__":
    main()