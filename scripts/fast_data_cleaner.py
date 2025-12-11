"""
Fast Data Cleaning Script - No AI models, only Python standard library
Cleans common issues in the MLex dataset

Usage:
    python scripts/fast_data_cleaner.py

Features:
    1. Remove trailing punctuation
    2. Normalize whitespace
    3. Remove empty records
    4. Fix quote issues
    5. Remove duplicate records
    6. Validate required fields
    7. Clean text formatting
    8. Generate cleaning report
"""

import csv
import re
from datetime import datetime
from pathlib import Path
from collections import OrderedDict

class FastDataCleaner:
    def __init__(self, input_file, output_file=None):
        self.input_file = input_file
        self.output_file = output_file or input_file.replace('.csv', '_super_cleaned.csv')

        # Statistics
        self.stats = {
            'original_rows': 0,
            'final_rows': 0,
            'removed_empty': 0,
            'removed_duplicates': 0,
            'cleaned_trailing_punct': 0,
            'cleaned_whitespace': 0,
            'cleaned_quotes': 0,
            'fixed_entries': 0,
        }

        # For deduplication
        self.seen_rows = set()
        self.seen_entry_index = set()

    def clean_trailing_punctuation(self, text):
        """Remove trailing punctuation (commas, periods, semicolons, etc.)"""
        if not text or text.strip() == '':
            return text

        original = text
        # Remove trailing commas, periods, semicolons, colons
        text = re.sub(r'[,;:\.]+$', '', text.strip())

        if original != text:
            self.stats['cleaned_trailing_punct'] += 1

        return text

    def normalize_whitespace(self, text):
        """Normalize whitespace: remove extra spaces, tabs, newlines"""
        if not text:
            return text

        original = text

        # Replace all consecutive whitespace with a single space
        text = re.sub(r'\s+', ' ', text)
        # Remove leading and trailing whitespace
        text = text.strip()

        if original != text and text != '':
            self.stats['cleaned_whitespace'] += 1

        return text

    def clean_quotes(self, text):
        """Clean quote issues"""
        if not text:
            return text

        original = text

        # Remove extra quotes at the beginning and end
        text = text.strip('"\'')

        # Replace smart quotes with regular quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")

        if original != text:
            self.stats['cleaned_quotes'] += 1

        return text

    def clean_entry_field(self, entry):
        """Clean the entry field specifically"""
        if not entry:
            return entry

        # Remove trailing punctuation
        entry = self.clean_trailing_punctuation(entry)
        # Normalize whitespace
        entry = self.normalize_whitespace(entry)
        # Clean quotes
        entry = self.clean_quotes(entry)

        return entry

    def clean_definition(self, text):
        """Clean definition text"""
        if not text:
            return text

        # Normalize whitespace
        text = self.normalize_whitespace(text)

        # Remove extra periods at the end (more than 1)
        text = re.sub(r'\.{2,}$', '.', text)

        # Fix common spelling issues (without AI)
        replacements = {
            'selamalamanya': 'selama-lamanya',
            'sbg': 'sebagai',
            'spt': 'seperti',
            'thp': 'terhadap',
            'yg': 'yang',
            'tsb': 'tersebut',
            'sso': 'seseorang',
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        return text

    def clean_synonym_field(self, text):
        """Clean synonym field"""
        if not text:
            return text

        # Split synonyms (may be separated by commas or semicolons)
        synonyms = re.split(r'[,;]+', text)

        # Clean each synonym
        cleaned_synonyms = []
        for syn in synonyms:
            syn = self.normalize_whitespace(syn)
            syn = self.clean_trailing_punctuation(syn)
            if syn:  # Only keep non-empty
                cleaned_synonyms.append(syn)

        # Remove duplicates
        cleaned_synonyms = list(OrderedDict.fromkeys(cleaned_synonyms))

        return '; '.join(cleaned_synonyms) if cleaned_synonyms else ''

    def is_valid_row(self, row):
        """Check if row is valid (must have entry at minimum)"""
        entry = row.get('entry', '').strip()

        # entry must exist and be non-empty
        if not entry or entry == '':
            return False

        return True

    def is_duplicate_row(self, row):
        """Check if row is a duplicate"""
        # Method 1: Complete duplicate check (all fields)
        row_tuple = tuple(row.values())
        if row_tuple in self.seen_rows:
            return True
        self.seen_rows.add(row_tuple)

        # Method 2: Duplicate based on entry + index
        entry = row.get('entry', '').strip()
        index = row.get('index', '').strip()
        entry_index_key = f"{entry}||{index}"

        if entry_index_key in self.seen_entry_index:
            return True
        self.seen_entry_index.add(entry_index_key)

        return False

    def clean_row(self, row):
        """Clean a single row of data"""
        cleaned_row = {}

        for col, value in row.items():
            # Normalize whitespace
            value = self.normalize_whitespace(value)

            # Special handling for specific fields
            if col in ['entry', 'rootWrd']:
                value = self.clean_entry_field(value)
            elif col == 'def':
                value = self.clean_definition(value)
            elif col == 'sinonim':
                value = self.clean_synonym_field(value)

            cleaned_row[col] = value

        return cleaned_row

    def run(self):
        """Run the complete cleaning pipeline"""
        print("="*70)
        print("    MLex Dataset Fast Cleaner (No Dependencies)")
        print("="*70)

        try:
            # Read CSV
            print(f"\nReading file: {self.input_file}")
            rows = []
            fieldnames = []

            with open(self.input_file, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames

                print(f"Columns: {fieldnames}")
                print(f"\nStarting data cleaning...")

                for row in reader:
                    self.stats['original_rows'] += 1
                    rows.append(row)

            print(f"Original rows: {self.stats['original_rows']:,}")

            # Clean data
            cleaned_rows = []

            print("\n[1/4] Cleaning each row...")
            for i, row in enumerate(rows):
                if (i + 1) % 10000 == 0:
                    print(f"   Progress: {i+1:,}/{len(rows):,}")

                cleaned_row = self.clean_row(row)

                # Validate
                if not self.is_valid_row(cleaned_row):
                    self.stats['removed_empty'] += 1
                    continue

                # Check duplicates
                if self.is_duplicate_row(cleaned_row):
                    self.stats['removed_duplicates'] += 1
                    continue

                cleaned_rows.append(cleaned_row)

            self.stats['final_rows'] = len(cleaned_rows)

            print(f"\n[2/4] Cleaning completed")
            print(f"   Final rows: {self.stats['final_rows']:,}")
            print(f"   Removed empty records: {self.stats['removed_empty']:,}")
            print(f"   Removed duplicate records: {self.stats['removed_duplicates']:,}")

            # Save cleaned data
            print(f"\n[3/4] Saving cleaned data to: {self.output_file}")

            Path(self.output_file).parent.mkdir(parents=True, exist_ok=True)

            with open(self.output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
                writer.writeheader()
                writer.writerows(cleaned_rows)

            # Generate report
            print(f"\n[4/4] Generating cleaning report...")
            report = self.generate_report()
            print(report)

            print("="*70)
            print("CLEANING COMPLETED SUCCESSFULLY!")
            print("="*70)

            return cleaned_rows

        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()
            return None

    def generate_report(self):
        """Generate cleaning report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f"data/cleaning_report_{timestamp}.txt"

        retention_rate = (self.stats['final_rows']/self.stats['original_rows']*100) if self.stats['original_rows'] > 0 else 0
        removal_rate = ((self.stats['original_rows']-self.stats['final_rows'])/self.stats['original_rows']*100) if self.stats['original_rows'] > 0 else 0

        report = f"""
================================================================
               Data Cleaning Report
================================================================
Cleaning Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Input File: {self.input_file}
Output File: {self.output_file}

----------------------------------------------------------------
                     Statistics
----------------------------------------------------------------
Original Records:        {self.stats['original_rows']:,}
Final Records:           {self.stats['final_rows']:,}
Removed Empty:           {self.stats['removed_empty']:,}
Removed Duplicates:      {self.stats['removed_duplicates']:,}
Cleaned Trailing Punct:  {self.stats['cleaned_trailing_punct']:,}
Normalized Whitespace:   {self.stats['cleaned_whitespace']:,}
Cleaned Quotes:          {self.stats['cleaned_quotes']:,}

----------------------------------------------------------------
                     Rates
----------------------------------------------------------------
Data Retention Rate:     {retention_rate:.2f}%
Data Removal Rate:       {removal_rate:.2f}%

----------------------------------------------------------------
                     Cleaning Operations
----------------------------------------------------------------
- Removed trailing punctuation (commas, periods, semicolons, etc.)
- Normalized whitespace (extra spaces, tabs, newlines)
- Fixed quote issues (smart quotes, extra quotes)
- Cleaned definition text (common abbreviations expanded)
- Cleaned synonym field (deduplicated, normalized)
- Removed invalid records (no entry field)
- Removed completely duplicate records
- Removed duplicates based on entry+index

----------------------------------------------------------------
                     Abbreviation Expansions
----------------------------------------------------------------
sbg  -> sebagai
spt  -> seperti
thp  -> terhadap
yg   -> yang
tsb  -> tersebut
sso  -> seseorang

================================================================
"""

        Path(report_file).parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"\nCleaning report saved to: {report_file}")
        return report


def main():
    """Main function"""
    # File paths
    input_file = r"c:\Users\Yeoh Ming Zhe\Documents\GitHub\MLex-Code-Mixed-Malay-Lexicon\data\final_dataset_cleaned.csv"
    output_file = r"c:\Users\Yeoh Ming Zhe\Documents\GitHub\MLex-Code-Mixed-Malay-Lexicon\data\final_dataset_super_cleaned.csv"

    # Create cleaner and run
    cleaner = FastDataCleaner(input_file, output_file)
    cleaned_rows = cleaner.run()

    if cleaned_rows is not None:
        # Show sample data
        print("\nFirst 5 cleaned records:")
        for i, row in enumerate(cleaned_rows[:5]):
            print(f"\nRecord {i+1}:")
            for key, value in row.items():
                if value:  # Only show non-empty fields
                    print(f"  {key}: {value[:100]}...")

        print(f"\nDataset Information:")
        print(f"  Total Rows: {len(cleaned_rows):,}")
        if cleaned_rows:
            print(f"  Total Columns: {len(cleaned_rows[0])}")


if __name__ == "__main__":
    main()
