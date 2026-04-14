import os
import re

def check_remaining_labels(start_idx, end_idx):
    found_any = False
    for i in range(start_idx, end_idx + 1):
        file_path = f"split/{i}.md"
        if not os.path.exists(file_path):
            continue
            
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for line_num, line in enumerate(lines, 1):
            # 检查行首是否仍有 "数字. " 或 "数字.  "
            if re.match(r'^\d+\.\s+', line):
                print(f"Found label in {file_path} at line {line_num}: {line.strip()[:50]}...")
                found_any = True
                
    if not found_any:
        print(f"Check complete: No numerical labels found at the start of lines in files {start_idx}.md to {end_idx}.md.")

if __name__ == "__main__":
    check_remaining_labels(1, 40)
