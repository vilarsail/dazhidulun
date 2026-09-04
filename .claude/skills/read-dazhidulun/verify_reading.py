#!/usr/bin/env python3
"""verify_reading.py - verify integrity of split/{N}.md / {N}.guide.md / {N}.notes.md."""

from __future__ import annotations
import re
import sys
from pathlib import Path

DOCS_DIR = Path('split')

CIRCLED = ('①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'
           '㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚'
           '㉛㉜㉝㉞㉟'
           '㊱㊲㊳㊴㊵㊶㊷㊸㊹㊺㊻㊼㊽㊾㊿')
CIRCLED_SET = set(CIRCLED)
CIRCLED_INDEX = {ch: i + 1 for i, ch in enumerate(CIRCLED)}

GUIDE_SECTIONS = ['## 一、', '## 二、', '## 三、', '## 四、', '## 五、']


def ws_strip(s: str) -> str:
    return ''.join(ch for ch in s if not ch.isspace())


def is_translation(line: str) -> bool:
    return line.lstrip('　 \t').startswith('*')


def is_heading(line: str) -> bool:
    return line.lstrip('　 \t').startswith('#')


def is_blank(line: str) -> bool:
    return not line.strip()


def strip_circled(line: str) -> str:
    if not any(ch in CIRCLED_SET for ch in line):
        return line
    return ''.join(ch for ch in line if ch not in CIRCLED_SET)


def parse_md_with_markers(n: int):
    path = DOCS_DIR / f'{n}.md'
    if not path.exists():
        return None
    text = path.read_text(encoding='utf-8')
    lines = text.split('\n')
    title = ''
    paragraphs = []
    cur = None
    for line in lines:
        if is_heading(line):
            if cur is not None:
                paragraphs.append('\n'.join(cur))
                cur = None
            stripped = line.lstrip('　 \t').lstrip('#').strip()
            if stripped and not title:
                title = stripped
        elif is_translation(line) or is_blank(line):
            if cur is not None:
                paragraphs.append('\n'.join(cur))
                cur = None
        else:
            if cur is None:
                cur = [line]
            else:
                cur.append(line)
    if cur is not None:
        paragraphs.append('\n'.join(cur))
    if not title and paragraphs:
        first_line = paragraphs[0].split('\n')[0]
        title = first_line.lstrip('　 \t').strip()
    return title, paragraphs, lines


def parse_notes_md(n: int):
    path = DOCS_DIR / f'{n}.notes.md'
    if not path.exists():
        return None
    text = path.read_text(encoding='utf-8')
    items = []
    for line in text.split('\n'):
        if not line or line.startswith('#'):
            continue
        m = re.match(r'^(\S+)\s+(\S.*?)　(.*)$', line)
        if not m:
            m2 = re.match(r'^(\S+)\s+(\S+?)\s+(.*)$', line)
            if not m2:
                continue
            marker, term, note = m2.group(1), m2.group(2), m2.group(3)
        else:
            marker, term, note = m.group(1), m.group(2), m.group(3)
        items.append((marker, term, note))
    return items


def verify_volume(n: int) -> tuple[list[str], list[str]]:
    """返回 (problems, warnings)。problems 阻断（退出码 1），warnings 仅提示。"""
    problems = []
    warnings = []

    for fname in (f'{n}.md', f'{n}.guide.md', f'{n}.notes.md'):
        p = DOCS_DIR / fname
        if not p.exists():
            problems.append(f'missing file {fname}')
            return problems
        if not p.read_text(encoding='utf-8').strip():
            problems.append(f'empty file {fname}')

    parsed = parse_md_with_markers(n)
    if parsed is None:
        problems.append(f'cannot parse {n}.md')
        return problems
    title, paragraphs, all_lines = parsed

    # 圈号越界检查：标题行/译文行不应含圈号
    for line in all_lines:
        if is_heading(line) or is_translation(line):
            for ch in line:
                if ch in CIRCLED_SET:
                    problems.append(f'marker out of bounds: {n}.md heading/translation line contains {ch}: {line[:40]}')
                    break

    # 原文圈号连续性
    seq_in_text = []
    for pi, para in enumerate(paragraphs):
        for ch in para:
            if ch in CIRCLED_SET:
                seq_in_text.append(ch)

    illegal = [ch for ch in seq_in_text if ch not in CIRCLED_INDEX]
    if illegal:
        problems.append(f'illegal markers in source: {illegal[:5]}')

    expected = list(CIRCLED[:len(seq_in_text)])
    if seq_in_text != expected:
        first_break = -1
        for i, ch in enumerate(seq_in_text):
            if i >= len(expected) or ch != expected[i]:
                first_break = i
                break
        problems.append(
            f'markers not sequential: {len(seq_in_text)} total, '
            f'first break at pos {first_break + 1}'
            f' (expected {expected[first_break] if first_break < len(expected) else "none"}, '
            f'actual {seq_in_text[first_break] if first_break < len(seq_in_text) else "none"})'
        )

    notes_items = parse_notes_md(n)
    if notes_items is None:
        problems.append(f'cannot parse {n}.notes.md')
        return problems

    notes_markers = [m for m, _, _ in notes_items]
    notes_illegal = [m for m in notes_markers if m not in CIRCLED_INDEX]
    if notes_illegal:
        problems.append(f'illegal markers in notes: {notes_illegal[:5]}')

    expected_notes = list(CIRCLED[:len(notes_markers)])
    if notes_markers != expected_notes:
        problems.append(f'notes markers not sequential: {len(notes_markers)} total')

    text_set = set(seq_in_text)
    notes_set = set(notes_markers)
    if text_set != notes_set:
        only_text = text_set - notes_set
        only_notes = notes_set - text_set
        if only_text:
            problems.append(f'markers only in source: {sorted(only_text, key=lambda c: CIRCLED_INDEX.get(c, 0))}')
        if only_notes:
            problems.append(f'markers only in notes: {sorted(only_notes, key=lambda c: CIRCLED_INDEX.get(c, 0))}')

    if len(notes_items) != len(seq_in_text):
        problems.append(f'notes {len(notes_items)} vs source {len(seq_in_text)} mismatch')

    marker_to_term = {}
    for m, term, _ in notes_items:
        if m in marker_to_term:
            problems.append(f'duplicate marker in notes: {m}')
            continue
        marker_to_term[m] = term

    for pi, para in enumerate(paragraphs):
        for ci, ch in enumerate(para):
            if ch not in CIRCLED_INDEX:
                continue
            term = marker_to_term.get(ch)
            if term is None:
                continue
            term_ws = ws_strip(term)
            left = ws_strip(para[:ci])
            if not left.endswith(term_ws):
                tail = left[-min(len(term_ws) + 5, len(left)):]
                problems.append(f'position mismatch: {n}.md para {pi + 1} marker {ch} left should be [{term}], actual [...{tail}]')

    guide_path = DOCS_DIR / f'{n}.guide.md'
    guide_text = guide_path.read_text(encoding='utf-8')
    missing_sections = [s for s in GUIDE_SECTIONS if s not in guide_text]
    if missing_sections:
        problems.append(f'guide missing sections: {missing_sections}')
    guide_body = guide_text.split('\n', 2)[-1] if '\n' in guide_text else guide_text
    glen = len(ws_strip(guide_body))
    if glen < 400:
        problems.append(f'guide too short: {glen} chars')
    elif glen > 1500:
        warnings.append(f'guide too long: {glen} chars (info only)')
    return problems, warnings


def main():
    args = sys.argv[1:]
    if len(args) != 2:
        print('usage: python3 verify_reading.py <start> <end>')
        return 2
    s, e = int(args[0]), int(args[1])
    ns = list(range(s, e + 1))
    print('=' * 60)
    print(f'verify_reading: {len(ns)} chapters ({s}-{e})')
    print('=' * 60)
    total_ok = 0
    total_issues = 0
    total_warns = 0
    for n in ns:
        problems, warnings = verify_volume(n)
        if not problems:
            tag = 'OK all pass'
            if warnings:
                tag += f' ({len(warnings)} warnings)'
            print(f'  [{n}] {tag}')
            for w in warnings:
                print(f'       - {w}')
            total_ok += 1
            total_warns += len(warnings)
        else:
            print(f'  [{n}] X {len(problems)} problems:')
            for p in problems:
                print(f'       - {p}')
            for w in warnings:
                print(f'       - {w}')
            total_issues += len(problems)
            total_warns += len(warnings)
    print('=' * 60)
    print(f'summary: {total_ok}/{len(ns)} chapters pass, {total_issues} blocking, {total_warns} warnings')
    return 0 if total_issues == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
