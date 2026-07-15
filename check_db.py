import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r'c:\Users\DSP02\Desktop\feed\dsoffice\app\data\office.db')
cur = conn.cursor()

# Check the length of section names in SECTIONS
sections = [
    "ආයතන අංශය",
    "ඉඩම් අංශය",
    "පුද්ගලයින් ලියාපදංචි කිරීමේ අංශය ( හැදුනුම්පත්)",
    "රෙජිස්ටාර් අංශය",
    "විශ්‍රාම වැටුප් අංශය",
    "සමාජසේවා අංශය",
    "බෞද්ධ කටයුතු අංශය",
    "ළමා හා කාන්තා කටයුතු අංශය",
    "ක්‍රමසම්පදාන අංශය",
    "වෙනත් කේෂ්ත්‍ර කටයුතු",
]

print("Section name lengths:")
for s in sections:
    print(f"  '{s}' -> {len(s)} chars")

# Check actual feedback section values vs SECTIONS list
cur.execute("SELECT DISTINCT section FROM feedback")
fb_sections = cur.fetchall()
print("\nFeedback sections in DB:")
for s in fb_sections:
    print(f"  '{s[0]}' (len={len(s[0])})")
    if s[0] in sections:
        print(f"    -> MATCHES SECTIONS list")
    else:
        print(f"    -> NOT FOUND in SECTIONS list")

# Check all feedback entries
cur.execute("SELECT id, section, rating FROM feedback")
rows = cur.fetchall()
print(f"\nAll feedback entries ({len(rows)} total):")
for r in rows:
    print(f"  id={r[0]}, section='{r[1]}', rating='{r[2]}'")

conn.close()
