import os
import re

def remove_number_labels(start_idx, end_idx):
    for i in range(start_idx, end_idx + 1):
        file_path = f"split/{i}.md"
        if not os.path.exists(file_path):
            print(f"Skipping {file_path}: File not found")
            continue
            
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        new_lines = []
        for line in lines:
            # 使用正则匹配行首的 "数字. " 或 "数字.  "
            # ^\d+\.\s+ 匹配行首数字、点号和随后的空白字符
            new_line = re.sub(r'^\d+\.\s+', '', line)
            new_lines.append(new_line)
            
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print(f"Processed {file_path}")

if __name__ == "__main__":
    remove_number_labels(1, 40)
