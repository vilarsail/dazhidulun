#!/usr/bin/env python3
"""
prepare_check.py — 校对前置：从 split/{N}.md 提取「原文段 → 译文段」对，生成批次 chunk 文件。

仅做机械工作（段对提取、分批切块），不做任何质量判断。
质量判断全部由 LLM 在读取 chunk 全量信息后完成。

split/{N}.md 格式：古文原文 + *斜体白话译文* 逐段交替。
识别规则：以 * 开头（允许前导全角/半角空格）的行是译文；以 # 开头的是标题；
空行是分隔；其余行都是原文（连续原文行合并为一段，偈颂多行亦然）。
译文通常单行 *…*；跨行格式B块（首行 * 开头、末行 * 结尾、中间行无 *）也支持。

输出（均在 split/ 下）：
- pairs_{N}.json：所有段对 {"1": {"orig": "...", "trans": "..."}, ...}
- check_{N}_batch{b}.json：每批最多 BATCH 个段对，含前 2 段上下文，供子 Agent 逐段判断

用法：
    python3 prepare_check.py <N>            # 单卷，N 可为 1、0-1 等
    python3 prepare_check.py <s> <e>        # 区间
"""

from __future__ import annotations
import json, sys
from pathlib import Path

DOCS_DIR = Path('split')
BATCH = 20  # 每批段对数。校对需逐段对比原文与译文，认知负荷高，取 20


def is_heading(line: str) -> bool:
    return line.lstrip('　 \t').startswith('#')


def is_trans(line: str) -> bool:
    return line.lstrip('　 \t').startswith('*')


def extract_pairs(filepath: Path) -> dict[str, dict]:
    """提取 原文段→译文段 对。连续原文行合并为一段；连续 * 行合并为译文块；
    译文块末行未以 * 结尾时，继续吞并后续非空/非标题/非译文行直到以 * 结尾（格式B跨行块）。"""
    lines = filepath.read_text(encoding='utf-8').split('\n')

    pairs: dict[str, dict] = {}
    idx = 0
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if line.strip() == '' or is_heading(line) or is_trans(line):
            i += 1
            continue
        # 原文段：连续非空、非标题、非译文行
        orig_lines = [line]
        i += 1
        while i < n:
            l = lines[i]
            if l.strip() == '' or is_heading(l) or is_trans(l):
                break
            orig_lines.append(l)
            i += 1
        # 跳过空行
        while i < n and lines[i].strip() == '':
            i += 1
        # 译文块：连续 * 开头的行
        trans_lines: list[str] = []
        while i < n and is_trans(lines[i]):
            trans_lines.append(lines[i].rstrip())
            i += 1
        # 格式B：末 * 行未闭合（不以 * 结尾），吞并跨行续行直到以 * 结尾的行
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


def build_batches(pairs: dict[str, dict]) -> list[dict]:
    """按每批 BATCH 段切块，每批注入前 2 段作为上下文参考。"""
    keys = sorted(pairs.keys(), key=lambda k: int(k) if k.isdigit() else 10 ** 9)
    total = len(keys)
    batches = []
    for start in range(0, total, BATCH):
        end = min(start + BATCH, total)
        batch_keys = keys[start:end]
        ctx_start = max(0, start - 2)
        ctx_keys = keys[ctx_start:start]
        batch = {
            '_batch_info': {
                'start': batch_keys[0] if batch_keys else '',
                'end': batch_keys[-1] if batch_keys else '',
                'count': len(batch_keys),
                'total': total,
            },
            '_context': {k: pairs[k] for k in ctx_keys},
            'paragraphs': {k: pairs[k] for k in batch_keys},
        }
        batches.append(batch)
    return batches


def main():
    args = sys.argv[1:]
    if not args:
        print('用法: python3 prepare_check.py <N> | <s> <e>', file=sys.stderr)
        return 2
    if len(args) == 2 and args[0].isdigit() and args[1].isdigit():
        ns = [str(x) for x in range(int(args[0]), int(args[1]) + 1)]
    else:
        ns = args

    print('=' * 60)
    print(f'prepare_check: 共 {len(ns)} 卷')
    print('=' * 60)
    for n in ns:
        src = DOCS_DIR / f'{n}.md'
        if not src.exists():
            print(f'[ERROR] {src} 不存在')
            return 1
        pairs = extract_pairs(src)
        (DOCS_DIR / f'pairs_{n}.json').write_text(
            json.dumps(pairs, ensure_ascii=False, indent=2), encoding='utf-8')
        batches = build_batches(pairs)
        for b, batch in enumerate(batches, 1):
            (DOCS_DIR / f'check_{n}_batch{b}.json').write_text(
                json.dumps(batch, ensure_ascii=False, indent=2), encoding='utf-8')
        missing = sum(1 for p in pairs.values() if not p['trans'])
        print(f'  [{n}] ✓ 段对={len(pairs)}, 批次={len(batches)}, 译文缺失={missing}')
        for b, batch in enumerate(batches, 1):
            info = batch['_batch_info']
            print(f'      Batch {b}: 段落 {info["start"]}-{info["end"]} ({info["count"]} 对)')
    print('')
    print('子 Agent 输入: split/check_{N}_batch*.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
