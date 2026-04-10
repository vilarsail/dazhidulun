import os
import re
import difflib

def clean_chinese(text):
    return re.sub(r'[^\u4e00-\u9fa5]', '', text)

def parse_md_blocks(md_content):
    lines = md_content.split('\n')
    blocks = []

    current_block = None
    for i, line in enumerate(lines):
        line_strip = line.strip()
        match = re.match(r'^(\d+)\.\s+(.*)$', line_strip)
        if match:
            if current_block:
                blocks.append(current_block)
            current_block = {
                'start_idx': i,
                'end_idx': i,
                'num': int(match.group(1)),
                'original_lines': [match.group(2)],
                'has_translation': False
            }
        elif current_block:
            if line_strip.startswith('*') or line_strip.startswith('**('):
                current_block['has_translation'] = True
            elif not current_block['has_translation'] and line_strip != '':
                current_block['original_lines'].append(line_strip)
            current_block['end_idx'] = i

    if current_block:
        blocks.append(current_block)

    for b in blocks:
        b['original_text'] = '\n'.join(b['original_lines'])
        b['clean_orig'] = clean_chinese(b['original_text'])

    return blocks, lines

def find_missing_and_fix(start_idx, end_idx):
    for file_idx in range(start_idx, end_idx + 1):
        txt_path = f"split/{file_idx}.txt"
        md_path = f"split/{file_idx}.md"

        if not os.path.exists(txt_path) or not os.path.exists(md_path):
            continue

        with open(txt_path, 'r', encoding='utf-8') as f:
            txt_lines = [line.strip() for line in f.readlines() if line.strip()]

        with open(md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()

        md_blocks, md_lines = parse_md_blocks(md_content)
        if not md_blocks:
            continue

        md_clean_full = "".join(b['clean_orig'] for b in md_blocks)

        missing_txt_indices = []
        txt_to_md_map = {}

        md_ptr = 0
        for t_idx, txt_line in enumerate(txt_lines):
            clean_t = clean_chinese(txt_line)
            if not clean_t:
                continue

            idx_in_md = md_clean_full.find(clean_t, md_ptr)
            if idx_in_md != -1:
                txt_to_md_map[t_idx] = idx_in_md
                md_ptr = idx_in_md + len(clean_t)
            else:
                # Fuzzy match window
                c_len = len(clean_t)
                best_score = 0
                best_idx = -1
                window_size = min(2000, len(md_clean_full) - md_ptr)
                for i in range(md_ptr, md_ptr + window_size - c_len + 1):
                    sim = difflib.SequenceMatcher(None, clean_t, md_clean_full[i:i+c_len], autojunk=False).ratio()
                    if sim > best_score:
                        best_score = sim
                        best_idx = i
                        if best_score > 0.95: break

                if best_score > 0.8:
                    txt_to_md_map[t_idx] = best_idx
                    md_ptr = best_idx + c_len
                else:
                    missing_txt_indices.append(t_idx)

        if not missing_txt_indices:
            print(f"{md_path}: OK")
            continue

        print(f"{md_path}: Found {len(missing_txt_indices)} missing paragraphs.")

        missing_txt_indices.sort(reverse=True)

        for t_idx in missing_txt_indices:
            txt_content = txt_lines[t_idx]
            insert_line_idx = -1

            def get_block_end_idx(char_idx):
                curr_len = 0
                for b in md_blocks:
                    curr_len += len(b['clean_orig'])
                    if char_idx < curr_len:
                        return b['end_idx']
                return md_blocks[-1]['end_idx']

            def get_block_start_idx(char_idx):
                curr_len = 0
                for b in md_blocks:
                    curr_len += len(b['clean_orig'])
                    if char_idx <= curr_len:
                        return b['start_idx']
                return md_blocks[-1]['start_idx']

            before_t_idx = t_idx - 1
            while before_t_idx >= 0 and before_t_idx not in txt_to_md_map:
                before_t_idx -= 1

            if before_t_idx >= 0:
                c_idx_before = txt_to_md_map[before_t_idx]
                insert_line_idx = get_block_end_idx(c_idx_before) + 1
            else:
                after_t_idx = t_idx + 1
                while after_t_idx < len(txt_lines) and after_t_idx not in txt_to_md_map:
                    after_t_idx += 1

                if after_t_idx < len(txt_lines):
                    c_idx_after = txt_to_md_map[after_t_idx]
                    insert_line_idx = get_block_start_idx(c_idx_after)
                else:
                    insert_line_idx = len(md_lines)

            new_block = [
                "",
                f"99999. {txt_content}",
                "",
                "**(此段需要翻译)**",
                ""
            ]
            md_lines = md_lines[:insert_line_idx] + new_block + md_lines[insert_line_idx:]

        final_lines = []
        counter = 1
        for line in md_lines:
            match = re.match(r'^(\d+)\.\s+(.*)$', line.strip())
            if match:
                final_lines.append(f"{counter}. {match.group(2)}")
                counter += 1
            else:
                final_lines.append(line)

        clean_lines = []
        for line in final_lines:
            if clean_lines and clean_lines[-1] == "" and line == "":
                continue
            clean_lines.append(line)

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(clean_lines))

find_missing_and_fix(1, 40)
