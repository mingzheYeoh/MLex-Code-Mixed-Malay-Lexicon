"""
MLEX - 交互式词义消歧工具
Interactive Word Sense Disambiguation Tool
"""

import os
import json
from typing import List, Dict, Optional, Tuple
import google.generativeai as genai
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WordSense:
    """词义数据结构"""
    sense_id: str
    definition: str
    examples: tuple = None
    confidence: float = 0.0


class GeminiWSDService:
    """使用Google Gemini进行Word Sense Disambiguation"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        
        if not self.api_key:
            raise ValueError(
                "需要Gemini API密钥！\n"
                "请设置: export GEMINI_API_KEY='your-key'"
            )
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        self.generation_config = {
            'temperature': 0.2,
            'top_p': 0.95,
            'top_k': 40,
            'max_output_tokens': 1024,
        }
        
        self.safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    
    def disambiguate(
        self, 
        word: str, 
        context: str, 
        candidate_senses: tuple
    ) -> List[Dict]:
        """词义消歧"""
        
        prompt = self._build_simple_prompt(word, context, candidate_senses)
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config,
                safety_settings=self.safety_settings
            )
            
            if not response or not response.candidates:
                return self._get_fallback_result(candidate_senses)
            
            candidate = response.candidates[0]
            if candidate.finish_reason != 1:
                return self._get_fallback_result(candidate_senses)
            
            try:
                response_text = response.text
            except (ValueError, AttributeError):
                return self._get_fallback_result(candidate_senses)
            
            result = self._parse_response(response_text, candidate_senses)
            return result if result else self._get_fallback_result(candidate_senses)
            
        except Exception as e:
            logger.error(f"API错误: {e}")
            return self._get_fallback_result(candidate_senses)
    
    def _build_simple_prompt(self, word: str, context: str, senses: tuple) -> str:
        """构建prompt"""
        sense_list = []
        for sense in senses:
            sense_list.append(f'{{"{sense.sense_id}": "{sense.definition}"}}')
        
        senses_json = ",\n".join(sense_list)
        
        prompt = f"""Word: {word}
Context: {context}

Senses: [{senses_json}]

Rank by relevance (0-100). Return JSON:
{{"results": [{{"id": "...", "score": 90, "reason": "..."}}]}}"""
        
        return prompt
    
    def _parse_response(self, text: str, senses: tuple) -> Optional[List[Dict]]:
        """解析响应"""
        try:
            text = text.strip()
            text = text.replace('```json', '').replace('```', '').strip()
            
            data = json.loads(text)
            results = data.get('results', data.get('rankings', []))
            
            if not results:
                return None
            
            output = []
            for r in results:
                sense_id = r.get('id', r.get('sense_id', ''))
                
                definition = ""
                for sense in senses:
                    if sense.sense_id == sense_id:
                        definition = sense.definition
                        break
                
                output.append({
                    'sense_id': sense_id,
                    'definition': definition or r.get('definition', ''),
                    'confidence': float(r.get('score', r.get('confidence', 0))),
                    'reasoning': r.get('reason', r.get('reasoning', ''))
                })
            
            total = sum(r['confidence'] for r in output)
            if total > 0:
                for r in output:
                    r['confidence'] = (r['confidence'] / total) * 100
            
            return output
            
        except Exception:
            return None
    
    def _get_fallback_result(self, senses: tuple) -> List[Dict]:
        """降级结果"""
        n = len(senses)
        confidence = 100.0 / n if n > 0 else 0
        
        return [
            {
                'sense_id': sense.sense_id,
                'definition': sense.definition,
                'confidence': confidence,
                'reasoning': '无法获取AI分析'
            }
            for sense in senses
        ]
    
    def find_common_words(self, sentence1: str, sentence2: str) -> List[str]:
        """找出两个句子中的相同词汇"""
        words1 = set(sentence1.lower().split())
        words2 = set(sentence2.lower().split())
        
        # 移除标点符号
        import string
        words1 = {w.strip(string.punctuation) for w in words1}
        words2 = {w.strip(string.punctuation) for w in words2}
        
        # 找出交集
        common = words1 & words2
        
        # 过滤掉太短的词（可能是停用词）
        common = {w for w in common if len(w) > 2}
        
        return list(common)
    
    def analyze_word_in_contexts(
        self, 
        word: str, 
        context1: str, 
        context2: str
    ) -> Dict:
        """分析同一个词在两个不同上下文中的含义"""
        
        prompt = f"""Analyze the word "{word}" in two different contexts.

Context 1: {context1}
Context 2: {context2}

Task:
1. Determine if "{word}" has different meanings in these contexts
2. If different, explain each meaning
3. Rate confidence (0-100)

Return JSON:
{{
    "word": "{word}",
    "are_different": true/false,
    "context1_meaning": "meaning description",
    "context2_meaning": "meaning description", 
    "confidence": 85,
    "explanation": "why they are different or same"
}}"""
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config,
                safety_settings=self.safety_settings
            )
            
            if not response or not response.candidates:
                return None
            
            if response.candidates[0].finish_reason != 1:
                return None
            
            text = response.text.strip()
            text = text.replace('```json', '').replace('```', '').strip()
            
            result = json.loads(text)
            return result
            
        except Exception as e:
            logger.error(f"分析失败: {e}")
            return None


# ==================== Neo4j连接 ====================

class Neo4jConnection:
    """连接Neo4j获取词义"""
    
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="mlex2025"):
        try:
            from neo4j import GraphDatabase
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.connected = True
        except Exception as e:
            logger.warning(f"⚠️  Neo4j连接失败: {e}")
            logger.warning("   将使用模拟数据")
            self.connected = False
    
    def get_word_senses(self, word: str) -> List[WordSense]:
        """从Neo4j获取词义"""
        if not self.connected:
            return self._get_mock_senses(word)
        
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (w:Word {entry: $word})-[:HAS_SENSE]->(s:Sense)
                    RETURN s.sense_id as sense_id,
                           s.definition as definition
                    ORDER BY s.sense_index
                    LIMIT 5
                """, word=word)
                
                senses = []
                for record in result:
                    senses.append(WordSense(
                        sense_id=record['sense_id'],
                        definition=record['definition']
                    ))
                
                return senses if senses else self._get_mock_senses(word)
        
        except Exception as e:
            logger.warning(f"查询失败: {e}")
            return self._get_mock_senses(word)
    
    def _get_mock_senses(self, word: str) -> List[WordSense]:
        """模拟数据（当Neo4j不可用时）"""
        mock_data = {
            'makan': [
                WordSense('makan_1', 'to eat food'),
                WordSense('makan_2', 'to consume resources'),
                WordSense('makan_3', 'to corrode or erode'),
            ],
            'main': [
                WordSense('main_1', 'to play'),
                WordSense('main_2', 'to perform or act'),
                WordSense('main_3', 'to play musical instrument'),
            ],
            'buah': [
                WordSense('buah_1', 'fruit'),
                WordSense('buah_2', 'classifier for large objects'),
            ],
            'kena': [
                WordSense('kena_1', 'must or have to'),
                WordSense('kena_2', 'to be affected by'),
                WordSense('kena_3', 'to hit or strike'),
            ]
        }
        
        if word.lower() in mock_data:
            return mock_data[word.lower()]
        else:
            return [
                WordSense(f'{word}_1', f'meaning 1 of {word}'),
                WordSense(f'{word}_2', f'meaning 2 of {word}'),
            ]
    
    def close(self):
        if self.connected:
            self.driver.close()


# ==================== 交互式界面 ====================

class InteractiveWSD:
    """交互式WSD工具"""
    
    def __init__(self):
        self.wsd_service = None
        self.neo4j = None
    
    def initialize(self):
        """初始化服务"""
        print("\n" + "="*80)
        print("🔤 MLEX - 交互式词义消歧工具")
        print("="*80)
        
        # 初始化Gemini
        try:
            self.wsd_service = GeminiWSDService()
            print("✅ Gemini服务初始化成功")
        except ValueError as e:
            print(f"\n❌ {e}")
            return False
        
        # 初始化Neo4j
        self.neo4j = Neo4jConnection()
        if self.neo4j.connected:
            print("✅ Neo4j连接成功")
        else:
            print("⚠️  Neo4j未连接，使用模拟数据")
        
        return True
    
    def show_menu(self):
        """显示菜单"""
        print("\n" + "-"*80)
        print("选择功能:")
        print("  1. 单词词义消歧 (输入词 + 句子)")
        print("  2. 句子对比分析 (找出相同词的不同含义)")
        print("  3. 退出")
        print("-"*80)
    
    def mode_single_word(self):
        """模式1: 单词WSD"""
        print("\n📍 模式1: 单词词义消歧")
        print("-"*80)
        
        word = input("\n请输入要分析的词: ").strip()
        if not word:
            print("❌ 词不能为空")
            return
        
        context = input(f"请输入包含 '{word}' 的句子: ").strip()
        if not context:
            print("❌ 句子不能为空")
            return
        
        # 检查词是否在句子中
        if word.lower() not in context.lower():
            print(f"⚠️  警告: 词 '{word}' 不在句子中")
            confirm = input("继续分析? (y/n): ").strip().lower()
            if confirm != 'y':
                return
        
        print(f"\n🔍 正在分析...")
        
        # 从Neo4j获取词义
        senses = self.neo4j.get_word_senses(word)
        
        if not senses:
            print(f"❌ 找不到词 '{word}' 的定义")
            return
        
        print(f"\n📚 找到 {len(senses)} 个词义:")
        for i, sense in enumerate(senses, 1):
            print(f"  {i}. {sense.definition}")
        
        # 执行WSD
        print(f"\n🤖 AI分析中...")
        results = self.wsd_service.disambiguate(word, context, tuple(senses))
        
        # 显示结果
        print(f"\n" + "="*80)
        print("📊 分析结果:")
        print("="*80)
        print(f"句子: {context}")
        print(f"词语: {word}\n")
        
        for i, r in enumerate(results, 1):
            conf = r['confidence']
            
            # 根据置信度选择图标
            if conf > 70:
                icon = "🟢"
            elif conf > 40:
                icon = "🟡"
            else:
                icon = "🔴"
            
            print(f"{icon} 排名 {i}: {r['definition']}")
            print(f"   置信度: {conf:.1f}%")
            print(f"   理由: {r['reasoning']}\n")
    
    def mode_sentence_comparison(self):
        """模式2: 句子对比"""
        print("\n📍 模式2: 句子对比分析")
        print("-"*80)
        
        sentence1 = input("\n请输入第一个句子: ").strip()
        if not sentence1:
            print("❌ 句子不能为空")
            return
        
        sentence2 = input("请输入第二个句子: ").strip()
        if not sentence2:
            print("❌ 句子不能为空")
            return
        
        print(f"\n🔍 寻找相同的词...")
        
        # 找出相同的词
        common_words = self.wsd_service.find_common_words(sentence1, sentence2)
        
        if not common_words:
            print("❌ 两个句子没有相同的词")
            return
        
        print(f"\n📝 找到 {len(common_words)} 个相同的词: {', '.join(common_words)}")
        
        # 分析每个相同的词
        print(f"\n🤖 分析每个词在两个句子中的含义...")
        print("="*80)
        
        for word in common_words:
            print(f"\n🔤 词: {word}")
            print("-"*80)
            
            result = self.wsd_service.analyze_word_in_contexts(
                word, sentence1, sentence2
            )
            
            if not result:
                print("❌ 分析失败")
                continue
            
            print(f"句子1: {sentence1}")
            print(f"含义: {result.get('context1_meaning', 'N/A')}\n")
            
            print(f"句子2: {sentence2}")
            print(f"含义: {result.get('context2_meaning', 'N/A')}\n")
            
            are_different = result.get('are_different', False)
            confidence = result.get('confidence', 0)
            
            if are_different:
                print(f"✅ 含义不同 (置信度: {confidence}%)")
            else:
                print(f"❌ 含义相同 (置信度: {confidence}%)")
            
            print(f"说明: {result.get('explanation', 'N/A')}")
            print("-"*80)
    
    def run(self):
        """运行主程序"""
        if not self.initialize():
            return
        
        while True:
            self.show_menu()
            
            choice = input("\n请选择 (1/2/3): ").strip()
            
            if choice == '1':
                self.mode_single_word()
            
            elif choice == '2':
                self.mode_sentence_comparison()
            
            elif choice == '3':
                print("\n👋 再见！")
                break
            
            else:
                print("❌ 无效选择，请输入 1, 2 或 3")
            
            input("\n按Enter继续...")
        
        # 清理
        if self.neo4j:
            self.neo4j.close()


# ==================== 主程序 ====================

def main():
    """主函数"""
    app = InteractiveWSD()
    
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n\n👋 程序已中断")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()