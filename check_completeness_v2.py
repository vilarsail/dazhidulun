import os
import sys
import json
import re

def check_files_v2(start_idx, end_idx):
    report = {}
    
    for i in range(start_idx, end_idx + 1):
        txt_path = f"split/{i}.txt"
        md_path = f"split/{i}.md"
        
        if not os.path.exists(txt_path) or not os.path.exists(md_path):
            continue
            
        # 1. 读取原始文本并分段（过滤空行，去除标号）
        with open(txt_path, 'r', encoding='utf-8') as f:
            txt_content = f.read()
            # 原始 txt 的格式是 "1. 内容\n\n2. 内容"
            txt_lines = re.findall(r'^\d+\.\s+(.*?)(?=\n\n\d+\.\s+|\Z)', txt_content, re.MULTILINE | re.DOTALL)
            txt_lines = [s.strip() for s in txt_lines]
            
        # 2. 读取 Markdown 并提取原文
        with open(md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
            
        # 提取逻辑：
        # - 排除标题 (#)
        # - 排除斜体 (*...*) -> 这是翻译
        # - 排除空行
        # - 剩下的应该就是原文
        raw_md_lines = md_content.split('\n')
        md_original_segments = []
        for line in raw_md_lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith('#'):
                continue
            if line.startswith('*') and line.endswith('*'):
                continue
            # 这里的逻辑是：如果该行不符合翻译格式且不是标题，则认为是原文
            md_original_segments.append(line)

        missing = []
        md_ptr = 0
        for txt_idx, txt_text in enumerate(txt_lines):
            found = False
            # 去除非汉字字符对比
            clean_txt = re.sub(r'[^\u4e00-\u9fa5]', '', txt_text)
            
            for j in range(md_ptr, len(md_original_segments)):
                clean_md = re.sub(r'[^\u4e00-\u9fa5]', '', md_original_segments[j])
                if clean_txt == clean_md:
                    md_ptr = j + 1
                    found = True
                    break
            
            if not found:
                missing.append({
                    "txt_index": txt_idx + 1,
                    "original_content": txt_text
                })

        report[str(i)] = {
            "status": "incomplete" if missing else "complete",
            "total_txt_paragraphs": len(txt_lines),
            "found_md_original_segments": len(md_original_segments),
            "missing_count": len(missing),
            "missing_details": missing[:20] # 仅保留前20个以防报告过大
        }
        
    os.makedirs("check", exist_ok=True)
    with open("check/completeness_report_v2.json", "w", encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    return "check/completeness_report_v2.json"

if __name__ == "__main__":
    start = 1
    end = 40
    if len(sys.argv) >= 3:
        start = int(sys.argv[1])
        end = int(sys.argv[2])
    report_file = check_files_v2(start, end)
    print(f"Report generated: {report_file}")
