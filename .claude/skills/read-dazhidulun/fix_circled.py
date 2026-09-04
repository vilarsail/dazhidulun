#!/usr/bin/env python3
"""fix_circled.py - detect and fix circled number jumps in split/{N}.md / {N}.notes.md."""

from __future__ import annotations
import sys
from pathlib import Path

DOCS_DIR = Path('split')

CIRCLED = ('①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'
           '㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚'
           '㉛㉜㉝㉞㉟'
           '㊱㊲㊳㊴㊵㊶㊷㊸㊹㊺㊻㊼㊽㊾㊿')
CIRCLED_SET = set(CIRCLED)
CIRCLED_INDEX = {ch: i + 1 for i, ch in enumerate(CIRCLED)}


def is_translation(line: str) -> bool:
    return line.lstrip('　 \t').startswith('*')


def is_heading(line: str) -> bool:
    return line.lstrip('　 \t').startswith('#')


def is_blank(line: str) -> bool:
    return not line.strip()


def extract_md_sequence(n: int) -> list[str]:
    path = DOCS_DIR / f'{n}.md'
    if not path.exists():
        return []
    text = path.read_text(encoding='utf-8')
    seq = []
    for line in text.split('\n'):
        if is_heading(line) or is_translation(line) or is_blank(line):
            continue
        for ch in line:
            if ch in CIRCLED_SET:
                seq.append(ch)
    return seq


def build_fix_map(actual_seq: list[str]) -> dict[str, str]:
    fix = {}
    for i, actual in enumerate(actual_seq):
        if i >= len(CIRCLED):
            break
        expected = CIRCLED[i]
        if actual != expected:
            fix[actual] = expected
    return fix


def apply_fix(text: str, fix_map: dict[str, str]) -> str:
    if not fix_map:
        return text
    placeholder_map = {}
    for actual, expected in fix_map.items():
        ph = f'\x00CIRC{ord(expected)}\x00'
        placeholder_map[ph] = expected
        text = text.replace(actual, ph)
    for ph, expected in placeholder_map.items():
        text = text.replace(ph, expected)
    return text


def fix_volume(n: int, dry_run: bool = False) -> list[str]:
    results = []
    seq = extract_md_sequence(n)
    if not seq:
        results.append(f'[{n}] no markers or file missing, skip')
        return results
    fix_map = build_fix_map(seq)
    if not fix_map:
        return results
    results.append(f'[{n}] detected jump, {len(fix_map)} to fix:')
    for actual, expected in fix_map.items():
        results.append(f'       {actual}(pos {CIRCLED_INDEX.get(actual,"?")}) -> {expected}(pos {CIRCLED_INDEX.get(expected,"?")})')
    if dry_run:
        results.append(f'       [dry-run] no file modified')
        return results
    md_path = DOCS_DIR / f'{n}.md'
    md_text = md_path.read_text(encoding='utf-8')
    md_fixed = apply_fix(md_text, fix_map)
    if md_fixed != md_text:
        md_path.write_text(md_fixed, encoding='utf-8')
        results.append(f'       fixed {n}.md')
    notes_path = DOCS_DIR / f'{n}.notes.md'
    if notes_path.exists():
        notes_text = notes_path.read_text(encoding='utf-8')
        notes_fixed = apply_fix(notes_text, fix_map)
        if notes_fixed != notes_text:
            notes_path.write_text(notes_fixed, encoding='utf-8')
            results.append(f'       fixed {n}.notes.md')
    new_seq = extract_md_sequence(n)
    new_fix = build_fix_map(new_seq)
    if new_fix:
        results.append(f'       X still has jumps: {new_fix}')
    else:
        last = new_seq[-1] if new_seq else 'none'
        results.append(f'       OK fixed (1..{last}, total {len(new_seq)})')
    return results


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    args = [a for a in args if a != '--dry-run']
    if not args:
        print('usage: python3 fix_circled.py <N> | <start> <end> [--dry-run]')
        return 2
    if len(args) == 2:
        s, e = int(args[0]), int(args[1])
        ns = list(range(s, e + 1))
    else:
        ns = [int(a) for a in args]
    print('=' * 60)
    print(f'fix_circled: {len(ns)} chapters{" (dry-run)" if dry_run else ""}')
    print('=' * 60)
    fixed_count = 0
    for n in ns:
        results = fix_volume(n, dry_run)
        if results:
            for r in results:
                print(r)
            if not dry_run and 'OK' in results[-1]:
                fixed_count += 1
    print('=' * 60)
    if dry_run:
        problem_count = sum(1 for n in ns if build_fix_map(extract_md_sequence(n)))
        print(f'summary: {problem_count}/{len(ns)} chapters have jumps (dry-run)')
    else:
        print(f'summary: {fixed_count} chapters fixed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
