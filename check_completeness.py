import os
import sys
import json
import re

def clean_chinese(text):
    return re.sub(r'[^\u4e00-\u9fa5]', '', text)

def check_files(start_idx, end_idx):
    report = {}

    for i in range(start_idx, end_idx + 1):
        txt_path = f"split/{i}.txt"
        md_path = f"split/{i}.md"

        if not os.path.exists(txt_path) or not os.path.exists(md_path):
            continue

        with open(txt_path, 'r', encoding='utf-8') as f:
            txt_lines = [line.strip() for line in f.readlines() if line.strip()]

        with open(md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()

        md_chars_str = clean_chinese(md_content)

        missing = []
        md_ptr = 0
        for txt_idx, txt_text in enumerate(txt_lines):
            clean_txt = clean_chinese(txt_text)
            if not clean_txt:
                continue

            idx_in_md = md_chars_str.find(clean_txt, md_ptr)
            if idx_in_md != -1:
                md_ptr = idx_in_md + len(clean_txt)
            else:
                missing.append({
                    "txt_index": txt_idx + 1,
                    "original_content": txt_text
                })

        report[str(i)] = {
            "status": "incomplete" if missing else "complete",
            "total_txt_paragraphs": len(txt_lines),
            "missing_count": len(missing),
            "missing_details": missing
        }

    os.makedirs("check", exist_ok=True)
    with open("check/completeness_report.json", "w", encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return "check/completeness_report.json"

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python check_completeness.py <start> <end>")
    else:
        start = int(sys.argv[1])
        end = int(sys.argv[2])
        report_file = check_files(start, end)
        print(f"Report generated: {report_file}")
