#!/usr/bin/env python3
"""임시: DB 상태 확인 후 결과를 파일로 출력"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from utils.db import get_connection

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_status_output.txt")

with open(OUT, "w", encoding="utf-8") as f:
    conn = get_connection()
    cur = conn.cursor()

    # 1. Progress
    cur.execute('SELECT * FROM progress WHERE id = 1')
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    f.write("=== PROGRESS ===\n")
    for c, v in zip(cols, row):
        f.write(f"  {c}: {v}\n")

    # 2. Run history
    f.write("\n=== RUN HISTORY (last 5) ===\n")
    cur.execute('SELECT * FROM run_history ORDER BY id DESC LIMIT 5')
    cols = [d[0] for d in cur.description]
    for row in cur.fetchall():
        f.write(str(dict(zip(cols, row))) + "\n")

    # 3. Gaps (same logic as fill_gaps.py)
    f.write("\n=== GAPS (year/month with 0 records) ===\n")
    cur.execute("""
        SELECT collected_year, collected_month, COUNT(*) as cnt
        FROM contracts
        GROUP BY collected_year, collected_month
        ORDER BY collected_year, collected_month
    """)
    existing = {}
    for row in cur.fetchall():
        existing[(row[0], row[1])] = row[2]

    year, month = 2016, 2
    gaps = []
    while year < 2026 or (year == 2026 and month <= 2):
        if (year, month) not in existing:
            gaps.append((year, month))
        month = month + 1 if month < 12 else 1
        if month == 1:
            year += 1

    if gaps:
        f.write(f"Total gaps: {len(gaps)}\n")
        for y, m in gaps:
            f.write(f"  {y}-{m:02d}\n")
    else:
        f.write("No gaps found!\n")

    # 4. Coverage summary
    f.write("\n=== COVERAGE SUMMARY ===\n")
    cur.execute("""
        SELECT bsns_div_nm, MIN(collected_year * 100 + collected_month) as first_period,
               MAX(collected_year * 100 + collected_month) as last_period, COUNT(*) as total
        FROM contracts
        GROUP BY bsns_div_nm
        ORDER BY bsns_div_nm
    """)
    for row in cur.fetchall():
        job, first, last, total = row
        f.write(f"  {job}: {first//100}-{first%100:02d} ~ {last//100}-{last%100:02d} ({total:,}건)\n")

    cur.close()
    conn.close()

print(f"Output written to {OUT}")
