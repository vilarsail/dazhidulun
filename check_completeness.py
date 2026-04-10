import os
import sys
import json
import re

def check_files(start_idx, end_idx):
    report = {}
    
    for i in range(start_idx, end_idx + 1):
        txt_path = f"split/{i}.txt"
        md_path = f"split/{i}.md"
        
        if not os.path.exists(txt_path) or not os.path.exists(md_path):
            continue
            
        # 读取原始文本并分段（过滤空行）
        with open(txt_path, 'r', encoding='utf-8') as f:
            txt_lines = [line.strip() for line in f.readlines() if line.strip()]
            
        # 读取 Markdown 并提取编号段落中的原文
        # 匹配格式如: 1. 原文内容
        with open(md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
            # 提取所有编号开头的行中的原文内容（不含序号部分）
            # 逻辑：查找形如 "n. 内容" 的行
            md_segments = re.findall(r'^\d+\.\s+(.*)$', md_content, re.MULTILINE)
            md_segments = [s.strip() for s in md_segments]

        missing = []
        # 以 txt 为基准进行比对
        # 注意：md 中的段落可能因为序号错乱或丢失而对不上
        # 我们寻找 txt 中的每一行是否按序存在于 md 中
        md_ptr = 0
        for txt_idx, txt_text in enumerate(txt_lines):
            found = False
            # 在 md 中寻找匹配（考虑到可能存在的微小格式差异，去除所有非中文字符进行对比）
            clean_txt = re.sub(r'[^\u4e00-\u9fa5]', '', txt_text)
            
            # 搜索 md 段落
            for j in range(md_ptr, len(md_segments)):
                clean_md = re.sub(r'[^\u4e00-\u9fa5]', '', md_segments[j])
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
            "found_md_segments": len(md_segments),
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
