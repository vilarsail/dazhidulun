#!/usr/bin/env python3
"""
build_reading.py - 由 notes_{N}.json 生成 split/{N}.guide.md（导读）与 split/{N}.notes.md（注释表），并把圈号标注写入 split/{N}.md 的原文。

LLM 已写好 notes_{N}.json：{"guide": "...", "terms": [{"term": "...", "note": "..."}, ...]}
本脚本做全部确定性工作（LLM 不做任何序号与定位）：
1. 解析 split/{N}.md → 标题 + 原文段（任意非 #/* 行，多行颂偈合并为一段）
2. 校验术语：每 term 必须出现在原文中、≤50 个、无重复、guide 非空
3. 按首次出现位置分配 ①-㊿；重叠冲突自动顺延；右向左插入
4. 圈号标注写回 split/{N}.md 原文（译文/标题/空行不动）；生成 notes.md（注释表）与 guide.md（导读）
5. 校验：字符流完整性、圈号连续性、注释表与标注一一对应

用法：
    python3 build_reading.py <N>            # 单章
    python3 build_reading.py <s> <e>        # 区间
"""

from __future__ import annotations
import json
import sys
from pathlib import Path

DOCS_DIR = Path('split')

CIRCLED = ('①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'
           '㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚'
           '㉛㉜㉝㉞㉟'
           '㊱㊲㊳㊴㊵㊶㊷㊸㊹㊺㊻㊼㊽㊾㊿')
CIRCLED_SET = set(CIRCLED)
MAX_TERMS = len(CIRCLED)


def is_translation(line: str) -> bool:
    s = line.lstrip('　 \t')
    return s.startswith('*')


def is_heading(line: str) -> bool:
    return line.lstrip('　 \t').startswith('#')


def is_blank(line: str) -> bool:
    return not line.strip()


def strip_circled(line: str) -> str:
    if not any(ch in CIRCLED_SET for ch in line):
        return line
    return ''.join(ch for ch in line if ch not in CIRCLED_SET)


def parse_md(n: int):
    path = DOCS_DIR / f'{n}.md'
    if not path.exists():
        print(f'[ERROR] {path} not found')
        return None
    text = path.read_text(encoding='utf-8')
    lines = text.split('\n')
    title = ''
    headings = []
    paragraphs = []
    cur = None
    for line in lines:
        line = strip_circled(line)
        if is_heading(line):
            if cur is not None:
                paragraphs.append('\n'.join(cur))
                cur = None
            stripped = line.lstrip('　 \t').lstrip('#').strip()
            if stripped and not title:
                title = stripped
            headings.append(line)
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
    return title, headings, paragraphs


def ws_strip(s: str) -> str:
    return ''.join(ch for ch in s if not ch.isspace())


def all_occurrences(paragraphs: list[str], term: str):
    t = ws_strip(term)
    if not t:
        return []
    res = []
    for pi, para in enumerate(paragraphs):
        nonws = [i for i, ch in enumerate(para) if not ch.isspace()]
        if len(nonws) < len(t):
            continue
        stream = ''.join(para[i] for i in nonws)
        start = 0
        while True:
            li = stream.find(t, start)
            if li == -1:
                break
            if li + len(t) <= len(nonws):
                res.append((pi, nonws[li], nonws[li + len(t) - 1]))
            start = li + 1
    return res


def assign(paragraphs: list[str], terms_notes: list[tuple[str, str]]):
    occs = []
    for term, note in terms_notes:
        occ = all_occurrences(paragraphs, term)
        if occ:
            occs.append({'term': term, 'note': note, 'occ': occ})
    occs.sort(key=lambda o: (o['occ'][0][0], o['occ'][0][1], -len(o['term'])))

    used = {}
    assigned = []
    dropped = []
    for o in occs:
        chosen = None
        for pi, s, e in o['occ']:
            spans = used.get(pi, [])
            if all(e < s2 or s > e2 for (s2, e2) in spans):
                chosen = (pi, s, e)
                break
        if chosen is None:
            dropped.append(o['term'])
            continue
        pi, s, e = chosen
        used.setdefault(pi, []).append((s, e))
        assigned.append({'pi': pi, 's': s, 'e': e,
                         'term': o['term'], 'note': o['note']})
    assigned.sort(key=lambda a: (a['pi'], a['s']))
    for i, a in enumerate(assigned):
        a['marker'] = CIRCLED[i]
    return assigned, dropped


def insert_markers(paragraphs: list[str], assigned: list[dict]) -> list[str]:
    marked = [list(p) for p in paragraphs]
    by_pi = {}
    for a in assigned:
        by_pi.setdefault(a['pi'], []).append(a)
    for pi, items in by_pi.items():
        for it in sorted(items, key=lambda x: x['e'], reverse=True):
            marked[pi].insert(it['e'] + 1, it['marker'])
    return [''.join(m) for m in marked]


def verify(original: list[str], marked: list[str], assigned: list[dict]) -> list[str]:
    problems = []

    def collapse(paras, drop_circled):
        s = ''.join(paras)
        if drop_circled:
            return ''.join(ch for ch in s if not ch.isspace() and ch not in CIRCLED_SET)
        return ''.join(ch for ch in s if not ch.isspace())

    if collapse(marked, True) != collapse(original, False):
        problems.append('字符流校验失败：标注后文本与原文不一致')

    seq = [ch for ch in ''.join(marked) if ch in CIRCLED_SET]
    expect = list(CIRCLED[:len(assigned)])
    if seq != expect:
        problems.append(f'圈号顺序不连续：正文出现 {len(seq)} 个，应为 {len(expect)} 个且递增无跳号')

    if len(assigned) != len(seq):
        problems.append(f'注释表 {len(assigned)} 条 与 正文标注 {len(seq)} 个 不一致')

    return problems


def build_notes_md(title: str, assigned: list[dict]) -> str:
    out = [f'# {title} 词语注释', '']
    for a in assigned:
        out.append(f'{a["marker"]} {a["term"]}　{a["note"]}')
    out.append('')
    return '\n'.join(out)


def rewrite_md(n: int, marked: list[str]) -> bool:
    """把带圈号的原文段写回 split/{N}.md，译文/标题/空行原样保留。"""
    path = DOCS_DIR / f'{n}.md'
    text = path.read_text(encoding='utf-8')
    lines = text.split('\n')
    out = []
    qi = 0
    cur_orig = None

    def flush():
        nonlocal qi, cur_orig
        if cur_orig is not None:
            if qi >= len(marked):
                return False
            out.append(marked[qi])
            qi += 1
            cur_orig = None
        return True

    for line in lines:
        line = strip_circled(line)
        if is_heading(line) or is_translation(line) or is_blank(line):
            if not flush():
                return False
            out.append(line)
        else:
            if cur_orig is None:
                cur_orig = []
            cur_orig.append(line)

    if not flush():
        return False

    if qi != len(marked):
        return False
    path.write_text('\n'.join(out), encoding='utf-8')
    return True


def build_guide_md(title: str, guide: str) -> str:
    head = f'# {title} 导读\n'
    return head + '\n' + guide.rstrip() + '\n'


def load_notes(n: int):
    path = DOCS_DIR / f'notes_{n}.json'
    if not path.exists():
        return '', [], [f'missing notes_{n}.json']
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception as e:
        return '', [], [f'parse failed: {e}']
    errors = []
    guide = data.get('guide') if isinstance(data, dict) else ''
    if not guide or not guide.strip():
        errors.append('guide empty')
    raw_terms = data.get('terms') if isinstance(data, dict) else None
    if not isinstance(raw_terms, list) or not raw_terms:
        errors.append('terms empty')
        return guide, [], errors
    terms_notes = []
    seen = set()
    for t in raw_terms:
        if not isinstance(t, dict) or not t.get('term') or not t.get('note'):
            errors.append(f'bad entry: {t}')
            continue
        term, note = t['term'].strip(), t['note'].strip()
        key = ws_strip(term)
        if not key:
            errors.append(f'blank: {t!r}')
            continue
        if key in seen:
            errors.append(f'dup: {term}')
            continue
        seen.add(key)
        terms_notes.append((term, note))
    if len(terms_notes) > MAX_TERMS:
        errors.append(f'too many: {len(terms_notes)} > {MAX_TERMS}')
    return guide, terms_notes, errors


def build_file(n: int):
    parsed = parse_md(n)
    if parsed is None:
        return 1
    title, _, paragraphs = parsed
    guide, terms_notes, errors = load_notes(n)
    if errors:
        for e in errors:
            print(f'  [{n}] X {e}')
        return 1
    guide = guide or ''
    terms_notes = terms_notes or []
    missing = [t for t, _ in terms_notes if not all_occurrences(paragraphs, t)]
    if missing:
        for t in missing:
            print(f'  [{n}] X term not found: [{t}]')
        return 1
    assigned, dropped = assign(paragraphs, terms_notes)
    for t in dropped:
        print(f'  [{n}] ! dropped: [{t}]')
    marked = insert_markers(paragraphs, assigned)
    problems = verify(paragraphs, marked, assigned)
    if problems:
        for p in problems:
            print(f'  [{n}] X {p}')
        return 1
    if not rewrite_md(n, marked):
        print(f'  [{n}] X rewrite failed')
        return 1
    (DOCS_DIR / f'{n}.notes.md').write_text(build_notes_md(title, assigned), encoding='utf-8')
    (DOCS_DIR / f'{n}.guide.md').write_text(build_guide_md(title, guide), encoding='utf-8')
    glen = len(ws_strip(guide))
    flag = '' if 400 <= glen <= 1500 else f' ! guide {glen} chars'
    print(f'  [{n}] OK {title}: terms={len(assigned)}, markers={len(assigned)}, guide={glen}{flag}')
    return 0


def main():
    args = sys.argv[1:]
    if not args:
        print('usage: python3 build_reading.py <N> | <s> <e>')
        return 2
    if len(args) == 2:
        s, e = int(args[0]), int(args[1])
        ns = list(range(s, e + 1))
    else:
        ns = [int(a) for a in args]
    print('=' * 60)
    print(f'build_reading: {len(ns)} chapters')
    print('=' * 60)
    code = 0
    for n in ns:
        code |= build_file(n)
    return code


if __name__ == '__main__':
    sys.exit(main())
