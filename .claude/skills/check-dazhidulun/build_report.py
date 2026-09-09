#!/usr/bin/env python3
"""
build_report.py — 合并各批校对 issues，生成 split/{N}.check.md 质量报告。

读取 split/pairs_{N}.json（段对）与 split/issues_{N}_batch*.json（各批问题），
按段落号排序输出问题明细与分类汇总。

JSON 容错：LLM 生成的 issues JSON 可能因值内含 ASCII 双引号/换行未转义而解析失败，
按段落号键边界切分、逐行正则提取字段修复；无法修复的批次跳过并告警。

用法：python3 build_report.py <N>
"""

from __future__ import annotations
import json, re, sys, glob
from datetime import datetime
from pathlib import Path

DOCS_DIR = Path('split')

TYPE_LABEL = {
    'MISSING': '译文缺失',
    'NEAR-COPY': '近似未翻译',
    'VERSE-NOT-TRANSLATED': '颂偈未译',
    'FORMAT': '格式问题',
    'ERROR': '翻译错误',
    'OTHER': '其它质量',
}

TYPE_ORDER = ['NEAR-COPY', 'VERSE-NOT-TRANSLATED', 'MISSING', 'ERROR', 'FORMAT', 'OTHER']


def load_issues_json(path: Path) -> dict | None:
    """读取 issues 批次 JSON，失败时尝试自动修复。

    修复策略：按段落号键边界切分，逐行提取字段——
      - type：值不含引号，用严格正则
      - problem / suggestion：值可能内含 ASCII 双引号，取行首引号后到行尾的内容
    """
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        pass

    try:
        content = path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return None

    raw = content.strip()
    if raw.startswith('{'):
        raw = raw[1:]
    if raw.endswith('}'):
        raw = raw[:-1]
    raw = raw.strip()

    entries = re_split_entries(raw)
    result: dict = {}
    for key, obj_raw in entries:
        fields = {}
        for line in obj_raw.split('\n'):
            line = line.strip()
            if line.startswith('"type"'):
                tm = re.search(r'"type"\s*:\s*"([^"]*)"', line)
                if tm:
                    fields['type'] = tm.group(1)
            elif line.startswith('"problem"'):
                fm = re.match(r'"problem"\s*:\s*"(.*)"\s*,?\s*$', line)
                if fm:
                    fields['problem'] = fm.group(1).replace('\\"', '"').replace('\\\\', '\\')
            elif line.startswith('"suggestion"'):
                fm = re.match(r'"suggestion"\s*:\s*"(.*)"\s*,?\s*$', line)
                if fm:
                    fields['suggestion'] = fm.group(1).replace('\\"', '"').replace('\\\\', '\\')
        if fields:
            result[key] = fields

    if result:
        print(f'  [repair] {path.name}: JSON 损坏，已自动修复 {len(result)} 条')
        return result
    print(f'  [WARN] {path.name}: 无法解析，跳过此批次')
    return None


def re_split_entries(raw: str) -> list[tuple[str, str]]:
    """按 "\\d+": 键边界切分为 (key, obj_raw) 列表。"""
    entries = re.split(r'\n\s*(?="\d+":)', raw)
    out = []
    for entry in entries:
        entry = entry.strip().rstrip(',')
        if not entry:
            continue
        m = re.match(r'"(\d+)":\s*', entry)
        if not m:
            continue
        out.append((m.group(1), entry[m.end():].strip()))
    return out


def main():
    if len(sys.argv) < 2:
        print('用法: python3 build_report.py <N>', file=sys.stderr)
        return 2
    n = sys.argv[1]

    pairs_path = DOCS_DIR / f'pairs_{n}.json'
    if not pairs_path.exists():
        print(f'Error: {pairs_path} 不存在。先运行 prepare_check.py。', file=sys.stderr)
        return 1

    pairs = json.loads(pairs_path.read_text(encoding='utf-8'))

    issues: dict = {}
    for path in sorted(glob.glob(str(DOCS_DIR / f'issues_{n}_batch*.json'))):
        batch = load_issues_json(Path(path))
        if batch is None:
            continue
        for key, value in batch.items():
            if key.startswith('_'):
                continue
            issues[key] = value

    def sort_key(k):
        try:
            return int(k)
        except ValueError:
            return 10 ** 9

    ordered = sorted(issues.keys(), key=sort_key)

    total = len(pairs)
    problem = len(ordered)
    pct = 100.0 * problem / total if total else 0

    by_type: dict = {t: 0 for t in TYPE_LABEL}
    for k in ordered:
        t = issues[k].get('type', 'OTHER')
        by_type.setdefault(t, 0)
        by_type[t] += 1

    lines = []
    lines.append(f'# split/{n}.md 译文校对报告')
    lines.append('')
    lines.append(f'- 段落总数：{total}')
    lines.append(f'- 问题段落数：{problem}（占 {pct:.1f}%）')
    lines.append(f'- 校对时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}')
    lines.append('')

    if problem == 0:
        lines.append('✅ 未发现译文质量问题，本卷无需修改。')
    else:
        lines.append('## 问题列表')
        lines.append('')
        for k in ordered:
            issue = issues[k]
            t = issue.get('type', 'OTHER')
            label = TYPE_LABEL.get(t, '其它质量')
            lines.append(f'### 段落 {k} 【{label}】')
            lines.append('')
            pair = pairs.get(k, {})
            orig = pair.get('orig', '')
            trans = pair.get('trans', '')
            if orig:
                lines.append(f'- **原文**：{orig}')
            if trans:
                lines.append(f'- **译文**：{trans}')
            elif t == 'MISSING':
                lines.append('- **译文**：（无）')
            lines.append(f'- **问题**：{issue.get("problem", "")}')
            if issue.get('suggestion'):
                lines.append(f'- **修改建议**：{issue["suggestion"]}')
            lines.append('')

        lines.append('## 汇总')
        lines.append('')
        for t in TYPE_ORDER:
            lines.append(f'- {TYPE_LABEL[t]}（{t}）：{by_type.get(t, 0)} 段')

    out_path = DOCS_DIR / f'{n}.check.md'
    out_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print(f'Generated {out_path}: {problem}/{total} 段有问题')
    if problem:
        for t in TYPE_ORDER:
            print(f'  {TYPE_LABEL[t]}: {by_type.get(t, 0)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
