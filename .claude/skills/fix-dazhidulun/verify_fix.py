#!/usr/bin/env python3
"""
verify_fix.py — 校验 split/{N}.md 的修复是否已正确应用。

校验项（纯文本匹配，不调用 LLM）：
1. 每个 N 都有对应的 .check.md 和 .fix.md
2. .fix.md 头部「成立并修复」数 与 正文「✅ 已修复」段落数一致
3. .fix.md 中每个「✅ 已修复」段落的「新译文」内容必须出现在 split/{N}.md 中

用法：
    python3 verify_fix.py              # 校验 1-100
    python3 verify_fix.py 85 86 87     # 校验指定卷（支持 0-1 等非数字卷号）
"""

from __future__ import annotations
import re, sys
from pathlib import Path

DOCS_DIR = Path('split')


def parse_fix_md(path: Path):
    """解析 .fix.md，返回 (header_stats, applied_entries)。

    applied_entries: list[(para_num_str, new_trans_str)]，「✅ 已修复」段落
    """
    text = path.read_text(encoding='utf-8')

    header_stats = {
        'total': 0, 'applied': 0, 'rejected': 0,
        'validation_failed': 0, 'application_failed': 0, 'batch_failed': 0,
    }
    for key, pat in [
        ('total', r'校对问题数：(\d+)'),
        ('applied', r'成立并修复：(\d+)'),
        ('rejected', r'不成立：(\d+)'),
        ('validation_failed', r'校验失败：(\d+)'),
        ('application_failed', r'应用失败：(\d+)'),
        ('batch_failed', r'批次解析失败：(\d+)'),
    ]:
        m = re.search(pat, text)
        if m:
            header_stats[key] = int(m.group(1))

    applied_entries = []
    parts = re.split(r'^### 段落 (\d+) 【', text, flags=re.MULTILINE)
    for i in range(1, len(parts), 2):
        para_num = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ''
        first_line = body.split('\n', 1)[0]
        if '✅ 已修复' not in first_line:
            continue
        m = re.search(
            r'- \*\*新译文\*\*：(.*?)(?=\n- \*\*|\n### |\n## |\Z)',
            body, flags=re.DOTALL,
        )
        if m:
            applied_entries.append((para_num, m.group(1).rstrip()))
        else:
            applied_entries.append((para_num, None))

    return header_stats, applied_entries


def verify_file(n: str):
    """校验单个卷，返回 (issues, summary)。"""
    issues = []
    summary = {
        'total': 0, 'applied_header': 0, 'applied_parsed': 0,
        'verified': 0, 'missing': 0,
    }

    check_md = DOCS_DIR / f'{n}.check.md'
    fix_md = DOCS_DIR / f'{n}.fix.md'
    md = DOCS_DIR / f'{n}.md'

    if not check_md.exists():
        issues.append(f'缺少 {check_md.name}')
    if not fix_md.exists():
        issues.append(f'缺少 {fix_md.name}')
        return issues, summary
    if not md.exists():
        issues.append(f'缺少 {md.name}')
        return issues, summary

    header_stats, applied_entries = parse_fix_md(fix_md)
    summary['total'] = header_stats['total']
    summary['applied_header'] = header_stats['applied']
    summary['applied_parsed'] = len(applied_entries)

    if header_stats['applied'] != len(applied_entries):
        issues.append(
            f'头部「成立并修复」={header_stats["applied"]}，'
            f'正文「✅ 已修复」段落数={len(applied_entries)}，不一致'
        )

    md_text = md.read_text(encoding='utf-8')
    for para_num, new_trans in applied_entries:
        if new_trans is None:
            issues.append(f'段落 {para_num} 标记已修复但缺少「新译文」字段')
            summary['missing'] += 1
            continue
        if new_trans in md_text:
            summary['verified'] += 1
        else:
            summary['missing'] += 1
            issues.append(f'段落 {para_num} 的新译文未在 {md.name} 中找到')

    return issues, summary


def main():
    args = sys.argv[1:]
    if args:
        files = args
    else:
        files = [p.stem for p in sorted(DOCS_DIR.glob('*.md'))
                 if p.stem.isdigit() and 1 <= int(p.stem) <= 100]
    files = sorted(set(files), key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else 0, x))

    total_files = len(files)
    files_ok = 0
    files_with_issues = 0
    total_applied = 0
    total_verified = 0
    total_missing = 0
    failed_files = []

    print(f'校验 {total_files} 个文件\n')

    for n in files:
        issues, summary = verify_file(n)
        total_applied += summary['applied_parsed']
        total_verified += summary['verified']
        total_missing += summary['missing']

        if issues:
            files_with_issues += 1
            failed_files.append((n, issues))
            print(f'  [{n}] ❌ 已修复={summary["applied_parsed"]} 已验证={summary["verified"]} 缺失={summary["missing"]}')
            for issue in issues:
                print(f'      - {issue}')
        else:
            files_ok += 1
            if summary['applied_parsed']:
                print(f'  [{n}] ✅ 已修复={summary["verified"]}')

    print('')
    print('汇总：')
    print(f'  文件总数：  {total_files}')
    print(f'  通过文件：  {files_ok}')
    print(f'  有问题文件：{files_with_issues}')
    print(f'  已修复条目：{total_applied}')
    print(f'  已验证条目：{total_verified}')
    print(f'  缺失条目：  {total_missing}')

    return 0 if not failed_files else 1


if __name__ == '__main__':
    sys.exit(main())
