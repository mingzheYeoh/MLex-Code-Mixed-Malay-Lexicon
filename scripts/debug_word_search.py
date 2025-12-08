"""Debug script to check if word was saved to database"""
from neo4j import GraphDatabase
import sys
import codecs

# Set UTF-8 output for Windows
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# Connect to Neo4j
driver = GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=("neo4j", "mlex2025")
)

print("Checking recent words added to database...\n")

with driver.session() as session:
    # Get all words
    print("Checking all words in database...")
    result = session.run("""
        MATCH (w:Word)
        RETURN w.entry as entry,
               w.pos as pos,
               w.created_at as created_at
        ORDER BY w.entry
        LIMIT 50
    """)

    all_words = list(result)

    if all_words:
        print(f"\nFound {len(all_words)} word(s) in database:\n")
        for i, record in enumerate(all_words, 1):
            created = record.get('created_at', 'N/A')
            print(f"{i}. Entry: {record['entry']}")
            print(f"   POS: {record.get('pos', 'N/A')}")
            if created != 'N/A':
                print(f"   Created: {created}")
            print()
    else:
        print("Database is empty! No words found.")

    # Check if specific test word exists
    print("\n" + "="*50)
    print("Checking if test word 'belajar' exists...\n")

    result = session.run("""
        MATCH (w:Word {entry: $entry})
        OPTIONAL MATCH (w)-[:HAS_SENSE]->(s:Sense)
        RETURN w, collect(s) as senses
    """, entry="belajar")

    record = result.single()
    if record:
        word = record['w']
        senses = record['senses']
        print(f"✅ Found 'belajar':")
        print(f"   Entry: {word['entry']}")
        print(f"   POS: {word.get('pos', 'N/A')}")
        print(f"   Senses: {len(senses)}")
        for i, sense in enumerate(senses, 1):
            print(f"   {i}. {sense.get('definition', 'N/A')}")
    else:
        print("❌ Word 'belajar' not found")

        # Try case-insensitive search
        print("\nTrying case-insensitive search...")
        result = session.run("""
            MATCH (w:Word)
            WHERE toLower(w.entry) = toLower($entry)
            RETURN w.entry as entry
        """, entry="belajar")

        similar = list(result)
        if similar:
            print(f"Found similar entries:")
            for rec in similar:
                print(f"  - {rec['entry']}")

driver.close()
print("\nDiagnosis complete!")
