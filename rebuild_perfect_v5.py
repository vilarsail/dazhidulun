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

        raw_txt_blocks = re.split(r'\n\s*\n', txt_content)
        txt_blocks = []
        for b in raw_txt_blocks:
            clean_b = b.strip()
            if clean_b:
                txt_blocks.append({
                    'original': clean_b,
                    'clean_text': clean_chinese(clean_b),
                    'translation': None
                })

        # Read from current MD (it's reverted to master)
        with open(md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()

        title = ""
        first_line = md_content.split('\n')[0].strip()
        if first_line.startswith('#'):
            title = first_line

        md_blocks = parse_md_blocks(md_content)

        # Build mapping. Map every translation back.
        for m_block in md_blocks:
            m_clean = m_block['clean_orig']
            trans = m_block['translation_text']

            if not m_clean or not trans or "此段需要翻译" in trans:
                continue

            # Find best txt_block
            best_score = 0
            best_t_idx = -1

            for t_idx, t_block in enumerate(txt_blocks):
                t_clean = t_block['clean_text']

                if m_clean in t_clean or t_clean in m_clean:
                    cov = min(len(m_clean), len(t_clean)) / max(len(m_clean), len(t_clean))
                    if cov > best_score:
                        best_score = cov
                        best_t_idx = t_idx
                    if best_score > 0.95: break

                sim = difflib.SequenceMatcher(None, m_clean, t_clean, autojunk=False).ratio()
                if sim > best_score:
                    best_score = sim
                    best_t_idx = t_idx

            if best_score > 0.3 and best_t_idx != -1:
                # To prevent overwriting with a worse match:
                existing_trans = txt_blocks[best_t_idx]['translation']
                if not existing_trans:
                    txt_blocks[best_t_idx]['translation'] = trans

        with open(md_path, 'w', encoding='utf-8') as f:
            if title:
                f.write(title + "\n\n")

            for idx, t_block in enumerate(txt_blocks):
                orig = t_block['original']
                f.write(f"{idx + 1}. {orig}\n\n")

                trans = t_block['translation']
                if trans:
                    f.write(f"{trans}\n\n")
                else:
                    f.write("**(此段需要翻译)**\n\n")

    print(f"Rebuilt files {start_idx} to {end_idx}")

if __name__ == "__main__":
    rebuild_files(1, 40)
