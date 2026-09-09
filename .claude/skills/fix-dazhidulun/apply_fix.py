#!/usr/bin/env python3
"""
apply_fix.py — 合并各批修复判断，对 split/{N}.md 应用 ACCEPT 的修复，
生成 split/{N}.fix.md 修复记录。

读取：
- split/fix_{N}_pairs.json（全部问题 + 原文 + 当前译文，由 prepare_fix.py 生成）
- split/fix_{N}_batch*.verdict.json（子 Agent 判断结果：verdict / reason / new_trans）

输出：
- 更新 split/{N}.md（用 new_trans 替换 ACCEPT 的译文段；MISSING 情况在原文段后插入）
- 生成 split/{N}.fix.md（格式化修复记录）

替换策略：按段落号定位原文段，找到其后紧跟的译文块，整体替换为 new_trans。
MISSING 情况（无译文块）在原文段后插入 new_trans。从后往前处理以避免行索引偏移。

用法：python3 apply_fix.py <N>
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

STATUS_LABEL = {
    'applied': '✅ 已修复',
    'rejected': '❌ 不成立，未修复',
    'validation_failed': '⚠️ 校验失败，未修复',
    'application_failed': '⚠️ 应用失败',
    'batch_failed': '⚠️ 批次解析失败',
}


def is_heading(line: str) -> bool:
    return line.lstrip('　 \t').startswith('#')


def is_trans(line: str) -> bool:
    return line.lstrip('　 \t').startswith('*')


def load_verdicts_json(path: Path) -> dict | None:
    """读取子 Agent 判断 JSON，失败时尝试自动修复（三段策略）。

    1. 直接 json.load
    2. 按段落号键切分，对每个对象单独 json.loads
    3. 字段级正则提取（兜底）
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

    entries = re.split(r'\n\s*(?="\d+":)', raw)
    result: dict = {}
    for entry in entries:
        entry = entry.strip().rstrip(',')
        if not entry:
            continue
        m = re.match(r'"(\d+)":\s*', entry)
        if not m:
            continue
        key = m.group(1)
        obj_raw = entry[m.end():].strip()

        try:
            result[key] = json.loads(obj_raw)
            continue
        except (json.JSONDecodeError, ValueError):
            pass

        fields = {}
        vm = re.search(r'"verdict"\s*:\s*"([^"]*)"', obj_raw)
        if vm:
            fields['verdict'] = vm.group(1)
        rm = re.search(r'"reason"\s*:\s*"((?:[^"\\]|\\.)*)"', obj_raw, flags=re.DOTALL)
        if rm:
            fields['reason'] = rm.group(1).replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n')
        ntm = re.search(r'"new_trans"\s*:\s*"((?:[^"\\]|\\.)*)"', obj_raw, flags=re.DOTALL)
        if ntm:
            fields['new_trans'] = ntm.group(1).replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n')
        if fields:
            result[key] = fields

    if result:
        print(f'  [repair] {path.name}: JSON 损坏，已自动修复 {len(result)} 条')
        return result
    print(f'  [WARN] {path.name}: 无法解析，跳过此批次')
    return None


def validate_new_trans(new_trans: str, orig_trans: str) -> tuple[bool, str]:
    """校验 new_trans 格式。

    1. 非空且以 * 开头、以 * 结尾
    2. 原译文为单行 *…* 时，new_trans 不得含换行（单行是本项目主格式，跨行破坏下游解析）
    3. 原译文为跨行格式B时，new_trans 同样首行 * 开头、末行 * 结尾（由 1 保证）
    """
    if not new_trans or len(new_trans) < 2:
        return False, 'new_trans 为空或过短'
    if not new_trans.startswith('*'):
        return False, 'new_trans 未以 * 开头'
    if not new_trans.endswith('*'):
        return False, 'new_trans 未以 * 结尾'
    if '\n' in new_trans and '\n' not in (orig_trans or ''):
        return False, '原译文为单行 *…*，新译文不得跨行（本项目译文须单行）'
    return True, ''


def locate_paragraph_block(lines: list[str], para_num: int):
    """定位第 para_num 个原文段 + 译文块的行索引范围（0-based，含端点）。

    遍历逻辑与 prepare_fix.extract_pairs 完全一致，保证段落号体系一致。
    返回 (orig_start, orig_end, trans_start, trans_end)；译文块不存在（MISSING）时
    trans_start = trans_end = -1。找不到段落返回 None。
    """
    i, n = 0, len(lines)
    idx = 0
    while i < n:
        line = lines[i]
        if line.strip() == '' or is_heading(line) or is_trans(line):
            i += 1
            continue
        orig_start = i
        i += 1
        while i < n:
            l = lines[i]
            if l.strip() == '' or is_heading(l) or is_trans(l):
                break
            i += 1
        orig_end = i - 1
        while i < n and lines[i].strip() == '':
            i += 1
        first = None
        while i < n and is_trans(lines[i]):
            if first is None:
                first = i
            i += 1
        trans_start = trans_end = -1
        if first is not None:
            trans_start = first
            trans_end = i - 1
            # 格式B：末 * 行未闭合，吞并跨行续行直到以 * 结尾的行
            if not lines[trans_end].rstrip().endswith('*'):
                while i < n:
                    l = lines[i]
                    if l.strip() == '' or is_heading(l) or is_trans(l):
                        break
                    trans_end = i
                    i += 1
                    if l.rstrip().endswith('*'):
                        break
        idx += 1
        if idx == para_num:
            return orig_start, orig_end, trans_start, trans_end
    return None


def insert_trans_block(lines: list[str], orig_end: int, new_trans: str) -> list[str]:
    """在原文段后插入新译文块（MISSING 情况）：原文 / 空行 / 新译文 / 空行。"""
    n = len(lines)
    j = orig_end + 1
    while j < n and lines[j].strip() == '':
        j += 1
    return lines[:orig_end + 1] + [''] + new_trans.split('\n') + [''] + lines[j:]


def main():
    if len(sys.argv) < 2:
        print('用法: python3 apply_fix.py <N>', file=sys.stderr)
        return 2
    n = sys.argv[1]

    pairs_path = DOCS_DIR / f'fix_{n}_pairs.json'
    if not pairs_path.exists():
        print(f'Error: {pairs_path} 不存在。先运行 prepare_fix.py。', file=sys.stderr)
        return 1

    pairs = json.loads(pairs_path.read_text(encoding='utf-8'))
    if not pairs:
        out_path = DOCS_DIR / f'{n}.fix.md'
        out_path.write_text(
            f'# split/{n}.md 译文修复报告\n\n'
            f'- 修复时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}\n'
            f'- 校对问题数：0\n\n'
            f'✅ 校对报告未发现问题，本卷无需修复。\n',
            encoding='utf-8')
        print(f'No issues. Generated {out_path}')
        return 0

    # 合并各批 verdicts
    verdicts: dict = {}
    batch_files_failed = []
    for path in sorted(glob.glob(str(DOCS_DIR / f'fix_{n}_batch*.verdict.json'))):
        batch = load_verdicts_json(Path(path))
        if batch is None:
            batch_files_failed.append(Path(path).name)
            continue
        for key, value in batch.items():
            if key.startswith('_'):
                continue
            verdicts[key] = value

    md_path = DOCS_DIR / f'{n}.md'
    lines = md_path.read_text(encoding='utf-8').split('\n')

    def sort_key(k):
        try:
            return int(k)
        except ValueError:
            return 10 ** 9

    all_keys = sorted(pairs.keys(), key=sort_key)

    # 第一遍：确定每条状态
    status = {}
    to_apply = []
    for k in all_keys:
        t = pairs.get(k, {}).get('type', 'OTHER')
        if k not in verdicts:
            status[k] = ('batch_failed', t, '批次解析失败：该段所在批次文件无法解析')
            continue
        v = verdicts[k]
        verdict = v.get('verdict', '').upper()
        new_trans = v.get('new_trans', '').strip()
        reason = v.get('reason', '')
        if verdict != 'ACCEPT':
            status[k] = ('rejected', t, reason)
        elif not new_trans:
            status[k] = ('validation_failed', t, 'ACCEPT 但 new_trans 为空')
        else:
            is_valid, val_reason = validate_new_trans(new_trans, pairs[k].get('trans', ''))
            if not is_valid:
                status[k] = ('validation_failed', t, val_reason)
            else:
                to_apply.append(k)
                status[k] = ('pending', t, reason)

    # 第二遍：从后往前应用
    for k in sorted(to_apply, key=sort_key, reverse=True):
        try:
            para_num = int(k)
        except ValueError:
            status[k] = ('application_failed', status[k][1], '段落号无效')
            continue
        result = locate_paragraph_block(lines, para_num)
        if result is None:
            status[k] = ('application_failed', status[k][1], '段落未在 .md 中找到')
            continue
        _, orig_end, trans_start, trans_end = result
        new_trans = verdicts[k].get('new_trans', '').strip()
        if trans_start == -1:
            lines = insert_trans_block(lines, orig_end, new_trans)
        else:
            lines = lines[:trans_start] + new_trans.split('\n') + lines[trans_end + 1:]
        status[k] = ('applied', status[k][1], status[k][2])

    md_path.write_text('\n'.join(lines), encoding='utf-8')

    total = len(all_keys)
    counts = {s: 0 for s in STATUS_LABEL}
    for k, (st, _, _) in status.items():
        counts[st] = counts.get(st, 0) + 1
    applied_count = counts['applied']
    pct = 100.0 * applied_count / total if total else 0

    by_type: dict = {}
    for k, (st, t, _) in status.items():
        by_type.setdefault(t, {s: 0 for s in STATUS_LABEL})
        by_type[t][st] += 1

    L = []
    L.append(f'# split/{n}.md 译文修复报告')
    L.append('')
    L.append(f'- 修复时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}')
    L.append(f'- 校对问题数：{total}')
    L.append(f'- 成立并修复：{applied_count}（占 {pct:.1f}%）')
    L.append(f'- 不成立：{counts["rejected"]}')
    L.append(f'- 校验失败：{counts["validation_failed"]}')
    L.append(f'- 应用失败：{counts["application_failed"]}')
    L.append(f'- 批次解析失败：{counts["batch_failed"]}')
    if batch_files_failed:
        L.append(f'- 解析失败批次文件：{", ".join(batch_files_failed)}')
    L.append('')

    if total == 0:
        L.append('✅ 无校对问题，本卷无需修复。')
    else:
        L.append('## 修复记录')
        L.append('')
        for k in all_keys:
            pair = pairs.get(k, {})
            t = pair.get('type', 'OTHER')
            label = TYPE_LABEL.get(t, '其它质量')
            st_code, _, detail = status[k]
            st_label = STATUS_LABEL.get(st_code, st_code)

            L.append(f'### 段落 {k} 【{label}】 {st_label}')
            L.append('')
            orig = pair.get('orig', '')
            old_trans = pair.get('trans', '')
            problem = pair.get('problem', '')
            suggestion = pair.get('suggestion', '')

            if orig:
                L.append(f'- **原文**：{orig}')
            if old_trans:
                L.append(f'- **原译文**：{old_trans}')
            elif t == 'MISSING':
                L.append('- **原译文**：（无）')
            if problem:
                L.append(f'- **校对问题**：{problem}')
            if suggestion:
                L.append(f'- **修改建议**：{suggestion}')

            v = verdicts.get(k, {})
            reason = v.get('reason', '')
            new_trans = v.get('new_trans', '').strip()

            if st_code == 'applied':
                if reason:
                    L.append(f'- **判断依据**：{reason}')
                if new_trans:
                    L.append(f'- **新译文**：{new_trans}')
            elif st_code == 'rejected':
                if reason:
                    L.append(f'- **判断依据**：{reason}')
            elif st_code == 'validation_failed':
                if reason:
                    L.append(f'- **判断依据**：{reason}')
                L.append(f'- **校验失败原因**：{detail}')
            elif st_code == 'application_failed':
                if reason:
                    L.append(f'- **判断依据**：{reason}')
                L.append(f'- **应用失败原因**：{detail}')
            elif st_code == 'batch_failed':
                L.append(f'- **批次失败说明**：{detail}')
            L.append('')

        L.append('## 汇总')
        L.append('')
        L.append(f'- 总问题数：{total}')
        L.append(f'- 已修复：{applied_count}')
        L.append(f'- 不成立：{counts["rejected"]}')
        L.append(f'- 校验失败：{counts["validation_failed"]}')
        L.append(f'- 应用失败：{counts["application_failed"]}')
        L.append(f'- 批次解析失败：{counts["batch_failed"]}')
        L.append('')
        L.append('按问题类型统计：')
        for t in TYPE_ORDER:
            if t not in by_type:
                continue
            stats = by_type[t]
            parts = []
            for s in ['applied', 'rejected', 'validation_failed', 'application_failed', 'batch_failed']:
                if stats.get(s, 0) > 0:
                    parts.append(f'{STATUS_LABEL[s]} {stats[s]}')
            if parts:
                L.append(f'- {TYPE_LABEL[t]}（{t}）：{" / ".join(parts)}')

    out_path = DOCS_DIR / f'{n}.fix.md'
    out_path.write_text('\n'.join(L) + '\n', encoding='utf-8')

    print(f'Applied {applied_count}/{total} fixes to {md_path}')
    print(f'Generated {out_path}')
    if counts['validation_failed']:
        print(f"  Validation failed: {counts['validation_failed']}")
    if counts['application_failed']:
        print(f"  Application failed: {counts['application_failed']}")
    if counts['batch_failed']:
        print(f"  Batch parse failed: {counts['batch_failed']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
