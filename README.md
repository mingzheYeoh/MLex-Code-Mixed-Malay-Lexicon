R# MLex: Malay Lexicon System (Code-Mixed)

A comprehensive Malay dictionary system built with Neo4j graph database, featuring AI-powered word sense disambiguation, semantic relationship networks, and an interactive web interface powered by Streamlit.

## ✨ Features

### Core Features
- 📚 **150,230+ Malay Entries** - Comprehensive Malay dictionary database
- 🔍 **Word Search** - Fast exact-match search with AI fallback
- 🎯 **Word Sense Disambiguation (WSD)** - Multi-sentence context analysis using AI
- 🔗 **Semantic Networks** - Synonym and antonym relationship graphs
- ➕ **Add New Words** - User-friendly interface for dictionary expansion
- 📊 **Database Statistics** - Real-time insights into lexicon data

### Technical Features
- 🤖 **AI Integration** - Ollama (Sailor2:8b) for Malay language processing
- 🏷️ **POS Tagging** - Complete part-of-speech information
- 📝 **Example Sentences** - Usage examples for each word sense
- 🔄 **Root Word Tracking** - Morphological relationships
- 🌐 **Etymology Information** - Word origin and domain classification
- 💻 **Interactive UI** - Modern Streamlit web interface
- 📥 **JSON Export** - Download analysis results

## 🚀 Tech Stack

- **Database**: Neo4j 5.x (Graph Database)
- **AI Model**: Ollama (Sailor2:8b) - Local AI inference
- **Frontend**: Streamlit - Interactive web interface
- **Backend**: Python 3.11+
- **Containerization**: Docker & Docker Compose
- **Key Libraries**:
  - neo4j-driver - Database connectivity
  - streamlit - Web UI framework
  - requests - Ollama API integration
  - pandas - Data processing
  - tqdm - Progress bar utilities
  - google-generativeai - Gemini AI integration (optional)

## 📋 Prerequisites

Before starting, ensure you have:

- **Docker & Docker Compose** - For Neo4j database
- **Python 3.11+** - For running the application
- **Ollama** - For AI features (optional)
- **Git** - For cloning the repository

## 🛠️ Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/MingZheYeoh/MLex-Code-Mixed-Malay-Lexicon.git
cd MLex-Code-Mixed-Malay-Lexicon
```

### 2. Start Neo4j Database

```bash
# Start Neo4j container
docker-compose up -d

# Verify container is running
docker-compose ps

# Access Neo4j Browser at: http://localhost:7474
# Default credentials:
#   Username: neo4j
#   Password: mlex2025
```

### 3. Set Up Python Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Configure Environment (Optional)

Create a `.env` file if you want custom configurations:

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=mlex2025
GEMINI_API_KEY=your_key_here  # Optional: For Gemini AI
```

### 5. Import Dictionary Data

```bash
# Initialize database constraints and indexes
python scripts/init_schema.py

# Import dictionary data (may take 10-30 minutes)
python scripts/import_data.py
```

### 6. Install and Configure Ollama (Recommended)

```bash
# Install Ollama from https://ollama.ai/

# Pull the Sailor2:8b model for Malay language
ollama pull sailor2:8b

# Start Ollama service
ollama serve
```

### 7. Launch the Application

```bash
# Start Streamlit application
streamlit run scripts/streamlit_app.py

# Application will open at: http://localhost:8501
```

## 📁 Project Structure

```
MLex-Code-Mixed-Malay-Lexicon/
├── .venv/                          # Python virtual environment
├── data/
│   └── final_dataset_super_cleaned.csv  # Dictionary data
├── docs/
│   └── NEO4J_DESIGN.md            # Database design documentation
├── scripts/
│   ├── streamlit_app.py           # Main Streamlit application
│   ├── new_wsd_module.py          # Unified WSD module
│   ├── word_addition_module.py    # Add word functionality
│   ├── ollama_service.py          # Ollama AI integration
│   ├── gemini_wsd_service.py      # Gemini AI integration (optional)
│   ├── import_data.py             # Data import script
│   ├── init_database.py           # Database initialization
│   └── debug_word_search.py       # Database diagnostic tool
├── neo4j_db/                      # Neo4j data directory (ignored by git)
│   ├── data/                      # Database files
│   ├── logs/                      # Log files
│   └── import/                    # Import directory
├── docker-compose.yml             # Docker Compose configuration
├── requirements.txt               # Python dependencies
├── .gitignore                     # Git ignore rules
└── README.md                      # This file
```

## 🎨 User Interface Features

### 1. 🔍 Word Search
- Exact-match search for Malay words
- Automatic AI fallback for words not in database
- Display complete word information:
  - Part of Speech (POS)
  - Phonetic transcription
  - Root word
  - Etymology
  - Domain
  - Synonyms
  - Multiple definitions with examples

### 2. 🎯 WSD (Word Sense Disambiguation)
- Analyze one word across multiple sentences
- Minimum 2 sentences required
- AI-powered context analysis
- Features:
  - Confidence scoring for each meaning
  - Detailed reasoning from AI
  - Visual ranking of candidate meanings
  - JSON export for results
  - Summary table view

### 3. ➕ Add Word
- User-friendly form for adding new dictionary entries
- Required fields:
  - Entry (Malay word)
  - Definition
  - Part of Speech
- Optional fields:
  - Root word, Phonetic, Example sentence
  - Domain, Label, Synonyms, Antonyms
  - Etymology, Passive form, Dialect
  - References
- AI validation before saving
- Direct save option (skip validation)

### 4. 📊 Statistics
- Real-time database statistics
- Node counts (Words, Senses, Roots, Examples)
- Relationship statistics
- POS distribution visualization
- Interactive charts

### 5. ⚙️ Settings
- System information display
- Neo4j connection status
- AI service status (Ollama/Gemini)
- Configuration options

## 🗄️ Database Design

### Node Types

1. **Word** - Word entry node
   - `entry`: Word text (unique)
   - `rootWrd`: Root word
   - `fonetik`: Phonetic transcription
   - `pos`: Part of speech
   - `label`: Classification label
   - `asal`: Etymology
   - `passive`: Passive form
   - `diaLan`: Dialect information
   - `domain`: Subject domain
   - `references`: Source references

2. **Sense** - Word sense node
   - `sense_id`: Unique identifier
   - `definition`: Meaning definition
   - `sense_index`: Ordering index
   - `confidence`: Confidence score

3. **Example** - Example sentence node
   - `text`: Example sentence

4. **Root** - Root word node
   - `word`: Root word text

5. **Domain** - Subject domain node
   - `name`: Domain name

### Relationship Types

- `HAS_SENSE` - Word → Sense (word has multiple senses)
- `HAS_EXAMPLE` - Sense → Example (sense has examples)
- `HAS_ROOT` - Word → Root (word derives from root)
- `SYNONYM` - Word ↔ Word (synonym relationship, bidirectional)
- `ANTONYM` - Word ↔ Word (antonym relationship, bidirectional)
- `IN_DOMAIN` - Sense → Domain (sense belongs to domain)

For detailed design documentation, see [NEO4J_DESIGN.md](docs/NEO4J_DESIGN.md)

## 💡 Usage Examples

### Basic Word Search

```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "mlex2025"))

with driver.session() as session:
    result = session.run("""
        MATCH (w:Word {entry: $word})-[:HAS_SENSE]->(s:Sense)
        RETURN w, s
    """, word="makan")

    for record in result:
        print(record['s']['definition'])
```

### WSD Analysis via UI

1. Navigate to **WSD** page
2. Enter multiple sentences (one per line):
   ```
   Saya makan nasi goreng
   Bateri makan kuasa
   ```
3. Enter target word: `makan`
4. Click **Analyze**
5. View ranked meanings with confidence scores
6. Download results as JSON

### Adding New Words

1. Navigate to **Add Word** page
2. Fill in required information
3. Optionally add synonyms: `word1; word2; word3`
4. Click **AI Verification** for validation
5. Word is automatically saved if validation passes

## 🧪 Testing

### Run Database Diagnostics

```bash
python scripts/debug_word_search.py
```

### Test WSD Feature

Use these test cases in the WSD interface:

**Case 1: "makan" (multiple meanings)**
```
Saya makan nasi goreng
Bateri makan kuasa
Karat makan besi
```

**Case 2: "main" (play)**
```
Kanak-kanak main bola di padang
Dia main piano dengan baik
```

## 🔧 Troubleshooting

### Neo4j Connection Issues

```bash
# Check if Neo4j is running
docker-compose ps

# Restart Neo4j
docker-compose restart neo4j

# View Neo4j logs
docker-compose logs neo4j
```

### Ollama Issues

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Restart Ollama
ollama serve

# Verify model is installed
ollama list
```

### Application Errors

```bash
# Check if virtual environment is activated
# Windows:
.venv\Scripts\activate

# Verify all dependencies are installed
pip install -r requirements.txt

# Clear Streamlit cache
streamlit cache clear
```

## 📊 Development Roadmap

- [x] Neo4j database design and initialization
- [x] Data import scripts (150K+ entries)
- [x] Streamlit web interface
- [x] Word search with AI fallback
- [x] Unified WSD module (multi-sentence analysis)
- [x] Add Word functionality with AI validation
- [x] Synonym and antonym relationships
- [x] Database statistics visualization
- [x] Ollama AI integration (Sailor2:8b)
- [x] JSON export for WSD results
- [ ] RESTful API development
- [ ] User authentication system
- [ ] Word editing functionality
- [ ] Batch import interface
- [ ] Advanced search filters
- [ ] Mobile-responsive design

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

### How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is open source. Please check the license file for more details.

## 👤 Author

**Yeoh Ming Zhe**

- GitHub: [@MingZheYeoh](https://github.com/MingZheYeoh)
- Email: yeohmingzhe@example.com

## 🙏 Acknowledgments

- Neo4j for the powerful graph database
- Ollama and Sailor2 team for the Malay language model
- Streamlit for the excellent UI framework
- The Malay language community

## 📚 Citation

If you use this lexicon in your research, please cite:

```bibtex
@misc{mlex2025,
  title={MLex: Code-Mixed Malay Lexicon System},
  author={Yeoh, Ming Zhe},
  year={2025},
  publisher={GitHub},
  howpublished={\url{https://github.com/MingZheYeoh/MLex-Code-Mixed-Malay-Lexicon}},
  note={A comprehensive Malay dictionary system with AI-powered word sense disambiguation}
}
```

## 📞 Support

For questions or support, please:
- Open an issue on GitHub
- Check existing issues for solutions
- Review the documentation in `/docs`

---

**Note**: This project requires Python 3.11+, Neo4j 5.x, and optionally Ollama for AI features. Make sure all prerequisites are installed before starting.
