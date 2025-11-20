# MLex: Malay Lexicon (Code-Mixed)

一个基于Neo4j图数据库的马来语词典系统，支持词义消歧、同义词/反义词关系、以及自动和手动词典改进。

## 项目特性

- 📚 **150,230+ 马来语词条** - 完整的马来语词典数据
- 🔍 **词义消歧 (Word Sense Disambiguation)** - 支持多词义识别和上下文匹配
- 🔗 **语义关系** - 同义词、反义词关系网络
- 🏷️ **词性标注 (POS Tagging)** - 完整的词性信息
- 📝 **例句支持** - 每个词义包含使用例句
- 🤖 **自动改进** - 支持机器学习模型集成
- ✏️ **手动改进** - 支持人工验证和编辑
- 🌐 **API支持** - RESTful API接口（开发中）
- 💻 **Web界面** - Streamlit用户界面（开发中）

## 技术栈

- **数据库**: Neo4j (图数据库)
- **容器化**: Docker & Docker Compose
- **编程语言**: Python 3.8+
- **主要库**: neo4j-driver, python-dotenv

## 快速开始

### 1. 环境要求

- Docker & Docker Compose
- Python 3.8+
- pip

### 2. 启动Neo4j数据库

```bash
# 启动Neo4j容器
docker-compose up -d

# 检查容器状态
docker-compose ps

# 访问Neo4j Browser: http://localhost:7474
# 默认用户名: neo4j
# 默认密码: 需要在docker-compose.yml或环境变量中设置
```

### 3. 安装Python依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

创建 `.env` 文件：

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here
CSV_FILE_PATH=data/final_dataset.csv
```

### 5. 初始化数据库

```bash
python scripts/init_database.py
```

这将创建所有必要的约束和索引。

### 6. 导入数据

```bash
python scripts/import_data.py
```

导入150,230条记录可能需要10-30分钟，取决于硬件配置。

### 7. 测试查询

```bash
python scripts/query_examples.py
```

## 项目结构

```
MLex-Code-Mixed-Malay-Lexicon/
├── data/
│   └── final_dataset.csv          # 词典数据文件
├── docs/
│   └── NEO4J_DESIGN.md            # Neo4j数据库设计文档
├── scripts/
│   ├── init_database.py           # 数据库初始化脚本
│   ├── import_data.py             # 数据导入脚本
│   ├── query_examples.py          # 查询示例脚本
│   └── README.md                  # 脚本使用说明
├── neo4j_db/                      # Neo4j数据目录
│   ├── data/                      # 数据库文件
│   ├── logs/                      # 日志文件
│   ├── import/                    # 导入目录
│   └── plugins/                   # Neo4j插件
├── docker-compose.yml             # Docker Compose配置
├── requirements.txt               # Python依赖
└── README.md                      # 项目说明
```

## 数据库设计

### 节点类型

1. **Word** - 词条节点
   - 属性: entry, rootWrd, fonetik, asal, passive, diaLan, domain

2. **Sense** - 词义节点
   - 属性: sense_id, index, pos, label, definition, confidence_score

3. **Example** - 例句节点
   - 属性: example_id, text, source

### 关系类型

- `HAS_SENSE` - Word → Sense (词有多个词义)
- `HAS_EXAMPLE` - Sense → Example (词义有例句)
- `SYNONYM` - Sense ↔ Sense (同义词关系)
- `ANTONYM` - Sense ↔ Sense (反义词关系)

详细设计请参考 [NEO4J_DESIGN.md](docs/NEO4J_DESIGN.md)

## 使用示例

### 查询词的所有词义

```python
from scripts.query_examples import LexiconQueries

queries = LexiconQueries(uri, user, password)
senses = queries.get_word_senses("abad")
for sense in senses:
    print(f"Sense {sense['sense_index']}: {sense['definition']}")
```

### 词义消歧

```python
# 基于上下文识别正确的词义
results = queries.word_sense_disambiguation("abad", "seratus tahun")
```

### 查找同义词

```python
synonyms = queries.get_synonyms("abad", sense_index=1)
```

## 开发计划

- [x] Neo4j数据库设计和初始化
- [x] 数据导入脚本
- [x] 基础查询功能
- [ ] RESTful API开发
- [ ] Streamlit用户界面
- [ ] 词义消歧模型集成
- [ ] 自动词典改进功能
- [ ] 用户反馈系统

## 贡献

欢迎提交Issue和Pull Request！

## 作者

Yeoh Ming Zhe