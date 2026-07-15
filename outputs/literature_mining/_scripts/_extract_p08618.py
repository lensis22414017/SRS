import fitz
import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

doc = fitz.open(r"G:/文献整理_最终/2021_Zhang T et al_Ecotoxicology_null/paper.pdf")
print(f"Total pages: {len(doc)}")

with open(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\_scripts\p08618_analysis.txt", "w", encoding="utf-8") as out:
    # Check each page for numerical data patterns
    for i, page in enumerate(doc):
        text = page.get_text()
        has_numbers = bool(re.search(r'\d+\.?\d*\s*[±]?\s*\d+\.?\d*', text))
        has_units = bool(re.search(r'mg/kg|ng/g|μg/kg|mg\s*kg', text, re.IGNORECASE))
        has_table = bool(re.search(r'Table|table', text))
        has_site = bool(re.search(r'\bS\d+\b', text))
        has_metal = bool(re.search(r'\bCd\b|\bPb\b|\bCr\b|\bAs\b|\bHg\b|\bCu\b|\bZn\b|\bNi\b|\bPAH', text))

        out.write(f"\n=== PAGE {i+1} === HasNum:{has_numbers} Units:{has_units} Table:{has_table} Site:{has_site} Metal:{has_metal}\n")
        out.write(text)
        out.write("\n---END---\n")

    # Table detection
    out.write("\n\n=== TABLE DETECTION ===\n")
    for i, page in enumerate(doc):
        tabs = page.find_tables()
        if tabs and len(tabs.tables) > 0:
            out.write(f"\nPage {i+1}: {len(tabs.tables)} tables found\n")
            for j, tab in enumerate(tabs.tables):
                out.write(f"  Table {j+1}:\n")
                df = tab.extract()
                for row in df:
                    out.write(str(row) + "\n")
print("DONE")
