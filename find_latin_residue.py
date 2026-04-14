import os
import re
import json

def find_latin_in_chinese(start_idx, end_idx):
    results = {}
    
    # 匹配连续的英文字母，且两端（或一端）紧邻中文或中文标点的模式
    # 这里我们索性扫描所有英文字母序列，再根据上下文判断
    pattern = re.compile(r'[a-zA-Z]+')
    
    # 常见合法词汇白名单（如果发现太多可以加入）
    whitelist = {'md', 'txt', 'CBETA', 'Kala', 'Kala'} 

    for i in range(start_idx, end_idx + 1):
        file_path = f"split/{i}.md"
        if not os.path.exists(file_path):
            continue
            
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        found_in_file = []
        for match in pattern.finditer(content):
            word = match.group()
            if word in whitelist:
                continue
                
            start, end = match.span()
            # 获取上下文
            ctx_start = max(0, start - 10)
            ctx_end = min(len(content), end + 10)
            context = content[ctx_start:ctx_end].replace("\n", "\\n")
            
            found_in_file.append({
                "word": word,
                "context": context,
                "index": start
            })
            
        if found_in_file:
            results[f"{i}.md"] = found_in_file
            
    return results

if __name__ == "__main__":
    res = find_latin_in_chinese(1, 40)
    with open("check/latin_residue.json", "w", encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    
    print(f"Scan complete. Found Latin sequences in {len(res)} files.")
    print("Check check/latin_residue.json for details.")
