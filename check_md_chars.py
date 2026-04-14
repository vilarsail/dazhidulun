import re
import os
import json
from collections import defaultdict

def classify_char(ch):
    code = ord(ch)

    # Unicode Private Use Area (PUA)
    if 0xE000 <= code <= 0xF8FF:
        return "PUA(私有区-疑似CBETA缺字)"
    
    # Unicode Extension blocks
    elif 0x20000 <= code <= 0x2A6DF:
        return "Unicode扩展区B"
    elif 0x2A700 <= code <= 0x2B73F:
        return "Unicode扩展区C"
    elif 0x2B740 <= code <= 0x2B81F:
        return "Unicode扩展区D"
    elif 0x2B820 <= code <= 0x2CEAF:
        return "Unicode扩展区E"
    elif 0x2CEB0 <= code <= 0x2EBEF:
        return "Unicode扩展区F"
    elif 0x30000 <= code <= 0x3134F:
        return "Unicode扩展区G"
    elif 0x31350 <= code <= 0x323AF:
        return "Unicode扩展区H"
    elif code >= 0x20000:
        return "Unicode扩展区(其他)"
    
    # Specials and problematic characters
    elif ch == "\uFFFD":
        return "乱码替换符"
    elif code < 32 and ch not in ['\n', '\t', '\r']:
        return "不可见控制字符"
    elif 127 <= code <= 159:
        return "C1控制字符"
    elif '\u2FF0' <= ch <= '\u2FFF':
        return "组合字结构符(IDS)"
    elif ch.isspace() and ch not in [' ', '\n', '\r', '\t', '\u3000']:
        return "其他空白字符"

    # 非中文、非 ASCII、非标准 CJK 标点的其他字符
    # 允许范围：
    # 1. CJK 基本区: \u4e00-\u9fff
    # 2. ASCII 可打印字符 (Markdown 语法及西文字符): \u0020-\u007e
    # 3. 常见 CJK 标点: \u3000-\u303f, \uff00-\uffef
    is_cjk = '\u4e00' <= ch <= '\u9fff'
    is_ascii_printable = '\u0020' <= ch <= '\u007e'
    is_cjk_punct = '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef'
    is_newline = ch in ['\n', '\r', '\t']

    if not (is_cjk or is_ascii_printable or is_cjk_punct or is_newline):
        return f"其他特殊字符(可能非中文)"

    return None

def analyze_md_files(directory_path, start_idx, end_idx, context_window=15):
    stats = {}

    for i in range(start_idx, end_idx + 1):
        filename = f"{i}.md"
        filepath = os.path.join(directory_path, filename)
        if not os.path.exists(filepath):
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        for pos, ch in enumerate(text):
            category = classify_char(ch)
            if category:
                hex_code = f"U+{ord(ch):04X}"
                key = f"{ch} ({hex_code})"

                if key not in stats:
                    stats[key] = {
                        "char": ch,
                        "hex": hex_code,
                        "type": category,
                        "count": 0,
                        "occurrences": []
                    }

                stats[key]["count"] += 1

                if len(stats[key]["occurrences"]) < 5:
                    start = max(0, pos - context_window)
                    end = min(len(text), pos + context_window + 1)
                    snippet = text[start:end].replace("\n", "\\n").replace("\r", "\\r")
                    stats[key]["occurrences"].append({
                        "file": filename,
                        "index": pos,
                        "context": snippet
                    })

    return stats

if __name__ == "__main__":
    split_dir = 'split/'
    output_json = 'check/md-encode-check.json'
    os.makedirs('check', exist_ok=True)

    print(f"Analyzing .md files in {split_dir} (1-40)...")
    results = analyze_md_files(split_dir, 1, 40)

    sorted_results = dict(sorted(results.items(), key=lambda x: (x[1]['type'], x[1]['hex'])))

    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(sorted_results, f, ensure_ascii=False, indent=2)

    print(f"Analysis complete. Results saved to {output_json}")
    print(f"Found {len(results)} unique problematic or special characters.")
