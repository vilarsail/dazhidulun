import os
import re
import difflib

def clean_chinese(text):
    return re.sub(r'[^\u4e00-\u9fa5]', '', text)

def parse_md_blocks(md_content):
    lines = md_content.split('\n')
    blocks = []

    current_block = None
    for line in lines:
        line_strip = line.strip()
        match = re.match(r'^(\d+)\.\s+(.*)$', line_strip)
        if match:
            if current_block:
                blocks.append(current_block)
            current_block = {
                'original_lines': [match.group(2)],
                'translation_lines': []
            }
        elif current_block:
            if line_strip.startswith('*') or line_strip.startswith('**('):
                current_block['translation_lines'].append(line_strip)
            elif not current_block['translation_lines'] and line_strip != '':
                current_block['original_lines'].append(line_strip)
            elif current_block['translation_lines'] and line_strip != '':
                current_block['translation_lines'].append(line_strip)

    if current_block:
        blocks.append(current_block)

    for b in blocks:
        b['original_text'] = '\n'.join(b['original_lines']).strip()
        b['clean_orig'] = clean_chinese(b['original_text'])
        b['translation_text'] = '\n'.join(b['translation_lines']).strip()

    return blocks

def rebuild_files(start_idx, end_idx):
    for file_idx in range(start_idx, end_idx + 1):
        txt_path = f"split/{file_idx}.txt"
        md_path = f"split/{file_idx}.md"

        if not os.path.exists(txt_path) or not os.path.exists(md_path):
            continue

        with open(txt_path, 'r', encoding='utf-8') as f:
            txt_content = f.read()

        # Some txt files don't use blank lines to separate paragraphs.
        # Actually, `1.txt` has 306 paragraphs if split by line, but only 246 if split by blank line!
        # If the user previously translated it line-by-line, combining them will lose mapping!
        # The ultimate source of truth for "how it was chunked" is the original MD file itself!

        # Read original MD file
        pipe = os.popen(f"git show origin/HEAD:{md_path}")
        md_content = pipe.read()
        pipe.close()

        md_blocks = parse_md_blocks(md_content)

        # If we reconstruct txt_blocks directly from txt_content, we must match the exact text.
        # Let's read txt line by line. If a sequence of lines exactly matches a block in md, we combine them.
        # Actually, it's safer to just inject missing lines from txt into md_blocks!
        pass

if __name__ == "__main__":
    rebuild_files(1, 40)
