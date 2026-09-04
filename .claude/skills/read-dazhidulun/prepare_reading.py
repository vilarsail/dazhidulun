#!/usr/bin/env python3
"""
prepare_reading.py - 从 split/{N}.md 提取「原文-only 紧凑文本」供 LLM 生成导读与词语注释。

提取内容：
- 标题行（# 原样保留；无 # 标题时取首段首行为标题）
- 原文段落（任意非 #、非 *、非空行；多行连续合并为一段，段号 P{n} 标注首行）
- 跳过 * 译文行、空行、其他行

split/ 格式说明：
大智度论 split/{N}.md 采用「古文原文 + *斜体现代白话文翻译*」逐段交替对照格式——
- 译文段：以 * 开头（部分译文带 *译文* 包围形式，均识别）
- 原文段：直接顶格（不带头部空格），多行颂偈亦然
- 标题行：以 # 或 ## 开头
- 段间分隔：原文段与译文段紧接，以 * 区分；偶有空行

脚本统一识别：以 * 开头的是译文，以 # 开头的是标题，空行是分隔，其余行都是原文。

用法：
    python3 prepare_reading.py <N>            # 单章
    python3 prepare_reading.py <s> <e>        # 区间
"""

from __future__ import annotations
import sys
from pathlib import Path

DOCS_DIR = Path('split')
TMP_PREFIX = 'reading_{n}_orig.txt'

# 圈号 1-50（与 build_reading.py 保持一致），用于剥离上一轮残留标注
CIRCLED = ('①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'
           '㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚'
           '㉛㉜㉝㉞㉟'
           '㊱㊲㊳㊴㊵㊶㊷㊸㊹㊺㊻㊼㊽㊾㊿')
CIRCLED_SET = set(CIRCLED)


def is_translation(line: str) -> bool:
    """译文行：以 * 开头（或带前导全角空格后以 * 开头，如 '　　*译文*'）"""
    s = line.lstrip('　 \t')
    return s.startswith('*')


def is_heading(line: str) -> bool:
    """标题行：以 # 开头"""
    return line.lstrip('　 \t').startswith('#')


def is_blank(line: str) -> bool:
    """空白行"""
    return not line.strip()


def strip_circled(line: str) -> str:
    """剥离圈号字符（幂等：重跑时清除上一轮标注，避免 LLM 把圈号当原文）"""
    if not any(ch in CIRCLED_SET for ch in line):
        return line
    return ''.join(ch for ch in line if ch not in CIRCLED_SET)


def parse_md(n: int):
    """返回 (title, headings, paragraphs)。
    paragraphs 为多行字符串列表（含原行格式，多行段合并）。
    识别规则：# 行→标题；* 行→译文（跳过）；空行→分隔；其余→原文。
    """
    path = DOCS_DIR / f'{n}.md'
    if not path.exists():
        print(f'[ERROR] {path} 不存在')
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
            # 原文行
            if cur is None:
                cur = [line]
            else:
                cur.append(line)
    if cur is not None:
        paragraphs.append('\n'.join(cur))

    # 无 # 标题时，取首段首行作标题
    if not title and paragraphs:
        first_line = paragraphs[0].split('\n')[0]
        title = first_line.lstrip('　 \t').strip()
    return title, headings, paragraphs


def build_extract(title: str, headings: list[str], paragraphs: list[str]) -> str:
    out = [f'# {title}']
    for h in headings:
        s = h.lstrip('　 \t').lstrip('#').strip()
        if s != title:
            out.append(h)
    out.append('')
    for i, para in enumerate(paragraphs, 1):
        lines = para.split('\n')
        out.append(f'P{i}' + lines[0])
        out.extend(lines[1:])
    return '\n'.join(out) + '\n'


def main():
    args = sys.argv[1:]
    if not args:
        print('用法: python3 prepare_reading.py <N> | <s> <e>')
        return 2
    if len(args) == 2:
        s, e = int(args[0]), int(args[1])
        ns = list(range(s, e + 1))
    else:
        ns = [int(a) for a in args]

    print('=' * 60)
    print(f'prepare_reading: 共 {len(ns)} 章')
    print('=' * 60)
    for n in ns:
        parsed = parse_md(n)
        if parsed is None:
            return 1
        title, headings, paragraphs = parsed
        out_path = DOCS_DIR / TMP_PREFIX.format(n=n)
        out_path.write_text(build_extract(title, headings, paragraphs), encoding='utf-8')
        print(f'  [{n}] ✓ {title}: 标题={len(headings)}, 段={len(paragraphs)}'
              f' -> {out_path.name}')
    print('')
    print('LLM 输入文件: split/reading_{N}_orig.txt')
    return 0


if __name__ == '__main__':
    sys.exit(main())
