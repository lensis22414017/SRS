#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import fitz
import sys
sys.stdout.reconfigure(encoding='utf-8')

doc = fitz.open(r'G:\文献整理_最终\2022_Liu Q et al_EnvironPollut_null_1\paper.pdf')
print(f'Total pages: {doc.page_count}')
print(f'File metadata: {doc.metadata}')

for i in range(doc.page_count):
    page = doc[i]
    text = page.get_text('text')
    print(f'\n=== PAGE {i+1} ({len(text)} chars) ===')
    print(text)

    # Also extract tables using find_tables
    try:
        tabs = page.find_tables()
        if tabs and tabs.tables:
            for j, tab in enumerate(tabs.tables):
                print(f'\n--- TABLE {j+1} ---')
                for row in tab.extract():
                    print(row)
    except Exception as e:
        print(f'Table extraction error: {e}')
