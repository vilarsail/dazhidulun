#!/usr/bin/env python3
"""
prepare_fix.py — 修复前置：从 split/{N}.check.md 解析问题列表，从 split/{N}.md
提取「原文段 → 译文段」对，合并为 split/fix_{N}_pairs.json，并按批切块生成
split/fix_{N}_batch*.json，供子 Agent 逐条判断「修改意见是否成立」。

仅做机械工作（解析 + 提取 + 切块），不做任何质量判断。
判断与改写全部由 LLM 子 Agent 完成。

段对提取逻辑与 check-dazhidulun/prepare_check.py 完全一致（同一序号体系）。

用法：python3 prepare_fix.py <N>
"""

from __future__ import annotations
import json, re, sys
from pathlib import Path

DOCS_DIR = Path('split')
BATCH = 10  # 每批问题数。修复判断需逐条对照原文/译文/建议改写，认知负荷高，取 10


def is_heading(line: str) -> bool:
    return line.lstrip('　 \t').startswith('#')


def is_trans(line: str) -> bool:
    return line.lstrip('　 \t').startswith('*')


def extract_pairs(filepath: Path) -> dict[str, dict]:
    """与 check-dazhidulun/prepare_check.py 完全相同的提取逻辑。"""
    lines = filepath.read_text(encoding='utf-8').split('\n')

    pairs: dict[str, dict] = {}
    idx = 0
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if line.strip() == '' or is_heading(line) or is_trans(line):
            i += 1
            continue
        orig_lines = [line]
        i += 1
        while i < n:
            l = lines[i]
            if l.strip() == '' or is_heading(l) or is_trans(l):
                break
            orig_lines.append(l)
            i += 1
        while i < n and lines[i].strip() == '':
            i += 1
        trans_lines: list[str] = []
        while i < n and is_trans(lines[i]):
            trans_lines.append(lines[i].rstrip())
            i += 1
        if trans_lines and not trans_lines[-1].rstrip().endswith('*'):
            while i < n:
                l = lines[i]
                if l.strip() == '' or is_heading(l) or is_trans(l):
                    break
                trans_lines.append(l.rstrip())
                i += 1
                if l.rstrip().endswith('*'):
                    break
        idx += 1
        pairs[str(idx)] = {
            'orig': '\n'.join(orig_lines),
            'trans': '\n'.join(trans_lines),
        }
    return pairs


def parse_check_md(path: Path) -> dict[str, dict]:
    """解析 split/{N}.check.md，提取问题列表。

    格式：
      ### 段落 {N} 【{label}】
      - **原文**：...
      - **译文**：...
      - **问题**：...
      - **修改建议**：...

    返回 {"段落号": {"type": ..., "problem": ..., "suggestion": ...}}
    """
    content = path.read_text(encoding='utf-8')

    TYPE_REVERSE = {
        '译文缺失': 'MISSING',
        '近似未翻译': 'NEAR-COPY',
        '颂偈未译': 'VERSE-NOT-TRANSLATED',
        '格式问题': 'FORMAT',
        '翻译错误': 'ERROR',
        '其它质量': 'OTHER',
    }

    issues: dict[str, dict] = {}
    sections = re.split(r'\n### 段落\s+', content)
    for sec in sections[1:]:
        m = re.match(r'(\d+)\s*【([^】]+)】', sec)
        if not m:
            continue
        para = m.group(1)
        label = m.group(2).strip()
        type_code = TYPE_REVERSE.get(label, 'OTHER')

        body = sec[m.end():]
        fields = {}
        # 仅提取 问题/修改建议；原文/译文从 .md 文件提取（更可靠）
        for field in ('问题', '修改建议'):
            pm = re.search(
                rf'- \*\*{field}\*\*[：:]\s*(.*?)(?=\n- \*\*(?:原文|译文|问题|修改建议)\*\*|\n##|\Z)',
                body, flags=re.DOTALL)
            if pm:
                fields[field] = pm.group(1).rstrip()
        issues[para] = {
            'type': type_code,
            'problem': fields.get('问题', '').strip(),
            'suggestion': fields.get('修改建议', '').strip(),
        }
    return issues


def build_batches(pairs: dict[str, dict], issues: dict[str, dict]) -> list[dict]:
    """按每批 BATCH 个问题切块，每条注入完整上下文（原文 + 当前译文 + 问题 + 建议 + 前后段原文）。"""
    keys = sorted(issues.keys(), key=lambda k: int(k) if k.isdigit() else 10 ** 9)
    batches = []
    total = len(keys)
    for start in range(0, total, BATCH):
        end = min(start + BATCH, total)
        batch_keys = keys[start:end]
        items = {}
        for k in batch_keys:
            issue = issues[k]
            pair = pairs.get(k, {})
            ctx = {}
            try:
                k_int = int(k)
                if str(k_int - 1) in pairs:
                    ctx['prev_orig'] = pairs[str(k_int - 1)]['orig']
                if str(k_int + 1) in pairs:
                    ctx['next_orig'] = pairs[str(k_int + 1)]['orig']
            except ValueError:
                pass
            items[k] = {
                'type': issue['type'],
                'problem': issue['problem'],
                'suggestion': issue['suggestion'],
                'orig': pair.get('orig', ''),
                'trans': pair.get('trans', ''),
                'context': ctx,
            }
        batches.append({
            '_batch_info': {
                'start': batch_keys[0] if batch_keys else '',
                'end': batch_keys[-1] if batch_keys else '',
                'count': len(batch_keys),
                'total': total,
            },
            'issues': items,
        })
    return batches


def main():
    if len(sys.argv) < 2:
        print('用法: python3 prepare_fix.py <N>', file=sys.stderr)
        return 2
    n = sys.argv[1]
    check_path = DOCS_DIR / f'{n}.check.md'
    md_path = DOCS_DIR / f'{n}.md'

    if not check_path.exists():
        print(f'Error: {check_path} 不存在。先运行 check-dazhidulun。', file=sys.stderr)
        return 1
    if not md_path.exists():
        print(f'Error: {md_path} 不存在。', file=sys.stderr)
        return 1

    pairs = extract_pairs(md_path)
    issues = parse_check_md(check_path)

    if not issues:
        (DOCS_DIR / f'fix_{n}_pairs.json').write_text('{}', encoding='utf-8')
        print(f'No issues in {check_path}. Nothing to fix.')
        return 0

    merged = {}
    for k, issue in issues.items():
        pair = pairs.get(k, {})
        merged[k] = {
            'type': issue['type'],
            'problem': issue['problem'],
            'suggestion': issue['suggestion'],
            'orig': pair.get('orig', ''),
            'trans': pair.get('trans', ''),
        }
    (DOCS_DIR / f'fix_{n}_pairs.json').write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8')

    batches = build_batches(pairs, issues)
    for b, batch in enumerate(batches, 1):
        (DOCS_DIR / f'fix_{n}_batch{b}.json').write_text(
            json.dumps(batch, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'Parsed {len(issues)} issues from {check_path}')
    print(f'Extracted {len(pairs)} paragraph pairs from {md_path}')
    print(f'Generated {len(batches)} batches -> split/fix_{n}_batch*.json')
    for b, batch in enumerate(batches, 1):
        info = batch['_batch_info']
        print(f'  Batch {b}: paragraphs {info["start"]}-{info["end"]} ({info["count"]} issues)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
