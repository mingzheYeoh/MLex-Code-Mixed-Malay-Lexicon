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
        # 跟踪已创建的sense_id，避免重复
        self.created_sense_ids = set()
    
    def close(self):
        self.driver.close()
    
    def clean_text(self, text):
        """清理文本"""
        if pd.isna(text):
            return None
        text = str(text).strip()
        return text if text and text.lower() not in ['nan', 'null', ''] else None
    
    def generate_unique_sense_id(self, entry, index, row_index):
        """
        生成唯一的sense_id
        使用 entry_index_序号 的格式
        如果entry_index已存在，添加序列号
        """
        base_sense_id = f"{entry}_{index}" if index else f"{entry}_0"
        
        # 如果基础ID不存在，直接使用
        if base_sense_id not in self.created_sense_ids:
            self.created_sense_ids.add(base_sense_id)
            return base_sense_id
        
        # 如果存在，添加序列号（使用row_index确保唯一性）
        unique_sense_id = f"{base_sense_id}_r{row_index}"
        self.created_sense_ids.add(unique_sense_id)
        
        logger.warning(f"Duplicate sense_id detected: {base_sense_id}, using {unique_sense_id}")
        return unique_sense_id
    
    def create_word_node(self, tx, row):
        """创建Word节点（使用MERGE避免重复）"""
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
        创建Sense节点
        使用唯一的sense_id（包含row_index以避免重复）
        """
        sense_id = self.generate_unique_sense_id(entry, index, row_index)
        
        # 智能处理 sense_index：支持数字和字母
        if index:
            # 如果是数字，转换为int；如果是字母，保持字符串
            try:
                sense_index_value = int(index)
            except (ValueError, TypeError):
                # 字母索引：'a'=1, 'b'=2, 'c'=3, 等等
                if isinstance(index, str) and len(index) == 1 and index.isalpha():
                    sense_index_value = ord(index.lower()) - ord('a') + 1
                else:
                    # 其他情况，保持为字符串
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
        """创建Word到Sense的关系"""
        query = """
        MATCH (w:Word {entry: $entry})
        MATCH (s:Sense {sense_id: $sense_id})
        MERGE (w)-[:HAS_SENSE {primary: true}]->(s)
        """
        tx.run(query, entry=entry, sense_id=sense_id)
    
    def create_root_relationship(self, tx, entry, root_word):
        """创建Root关系"""
        if not root_word or root_word == entry:
            return
        
        query = """
        MATCH (w:Word {entry: $entry})
        MERGE (r:Root {word: $root_word})
        MERGE (w)-[:HAS_ROOT]->(r)
        """
        tx.run(query, entry=entry, root_word=root_word)
    
    def create_example_node(self, tx, sense_id, example_text):
        """创建Example节点"""
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
        """创建Domain关系"""
        if not domain_name:
            return
        
        query = """
        MATCH (s:Sense {sense_id: $sense_id})
        MERGE (d:Domain {name: $domain_name})
        MERGE (s)-[:IN_DOMAIN]->(d)
        """
        tx.run(query, sense_id=sense_id, domain_name=domain_name)
    
    def create_synonym_relationships(self, tx, entry, synonyms):
        """创建同义词关系"""
        if not synonyms:
            return
        
        # 分割同义词（假设用逗号或分号分隔）
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
        """导入单行数据"""
        try:
            entry = self.clean_text(row.get('entry'))
            if not entry:
                return False
            
            # 1. 创建Word节点（MERGE，不重复）
            session.execute_write(self.create_word_node, row)
            self.stats['words'] += 1
            
            # 2. 创建Root关系
            root_word = self.clean_text(row.get('rootWrd'))
            if root_word:
                session.execute_write(self.create_root_relationship, entry, root_word)
                self.stats['roots'] += 1
            
            # 3. 创建Sense节点（使用唯一ID）
            definition = self.clean_text(row.get('def'))
            if definition:
                index = self.clean_text(row.get('index'))
                sense_id = session.execute_write(
                    self.create_sense_node, 
                    entry, 
                    definition, 
                    index,
                    row_index  # 传递row_index确保唯一性
                )
                self.stats['senses'] += 1
                
                # 4. 创建Word-Sense关系
                session.execute_write(self.create_word_sense_relationship, entry, sense_id)
                
                # 5. 创建Example节点
                example = self.clean_text(row.get('exp'))
                if example:
                    session.execute_write(self.create_example_node, sense_id, example)
                    self.stats['examples'] += 1
                
                # 6. 创建Domain关系
                domain = self.clean_text(row.get('domain'))
                if domain:
                    session.execute_write(self.create_domain_relationship, sense_id, domain)
                    self.stats['domains'] += 1
            
            # 7. 创建同义词关系
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
        """批量导入CSV数据"""
        logger.info(f"开始导入数据: {csv_file}")
        
        # 读取CSV
        df = pd.read_csv(csv_file)
        total_rows = len(df)
        logger.info(f"总行数: {total_rows:,}")
        
        # 分批处理
        with self.driver.session() as session:
            for i in tqdm(range(0, total_rows, batch_size), desc="导入进度"):
                chunk = df.iloc[i:i+batch_size]
                logger.info(f"处理chunk {i//batch_size + 1}...")
                
                for idx, row in chunk.iterrows():
                    self.import_row(session, row, idx)
        
        # 打印统计
        logger.info("\n" + "=" * 80)
        logger.info("导入完成！统计信息:")
        logger.info("=" * 80)
        logger.info(f"Word节点创建: {self.stats['words']:,}")
        logger.info(f"Sense节点创建: {self.stats['senses']:,}")
        logger.info(f"Root关系创建: {self.stats['roots']:,}")
        logger.info(f"Domain关系创建: {self.stats['domains']:,}")
        logger.info(f"Example节点创建: {self.stats['examples']:,}")
        logger.info(f"同义词关系创建: {self.stats['synonyms']:,}")
        logger.info(f"错误数量: {self.stats['errors']:,}")
        logger.info("=" * 80)


def main():
    
    CSV_FILE = "../data/final_dataset_super_cleaned.csv"  
    
    if not os.path.exists(CSV_FILE):
        logger.error(f"文件不存在: {CSV_FILE}")
        logger.info("请修改 CSV_FILE 变量为正确的路径")
        sys.exit(1)
    
    # 创建导入器
    importer = Neo4jImporter()
    
    try:
        # 导入数据
        start_time = datetime.now()
        importer.import_csv(CSV_FILE, batch_size=1000)
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        logger.info(f"\n总耗时: {duration:.2f} 秒")
        logger.info(f"平均速度: {importer.stats['words']/duration:.0f} 条/秒")
        
    except Exception as e:
        logger.error(f"导入失败: {e}")
        sys.exit(1)
    finally:
        importer.close()
    
    logger.info("\n✅ 数据导入完成！")


if __name__ == "__main__":
    main()
