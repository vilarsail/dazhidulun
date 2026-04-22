import requests
import json
import re
import os
import glob
import time
import sys

def extract_paragraphs(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    blocks = re.split(r'\s*\*\*\((?:此段需要翻译|.*)\)\*\*\s*', content)
    paragraphs = []
    for block in blocks:
        match = re.search(r'(\d+)\.\s*(.*)', block, re.DOTALL)
        if match:
            num = int(match.group(1))
            text = match.group(2).strip()
            if text:
                paragraphs.append((num, text))
    return paragraphs

def translate_batch(target_paragraphs, context_paragraphs=None, model="gemma4:e4b"):
    url = "http://localhost:11434/api/chat"
    system_prompt = (
        "你是一位精通古代汉语（特别是佛经文献）和现代汉语的翻译专家。你的任务是将《大智度论》的原文段落准确、优美地翻译成现代汉语。\n"
        "### 翻译要求\n"
        "1. **风格**：保持庄重、准确，翻译应符合现代汉语表达习惯。\n"
        "2. **格式维护**：严格保持原有的有序列表编号（如 1. 2. 3. ...）。不要输出任何额外的解释、开场白或结束语。\n"
    )
    user_content = ""
    if context_paragraphs:
        user_content += "### 上文参考（无需翻译）：\n"
        for num, text in context_paragraphs:
            user_content += f"{num}. {text}\n"
        user_content += "\n"
    user_content += "### 目标翻译段落：\n"
    for num, text in target_paragraphs:
        user_content += f"{num}. {text}\n"
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "options": {"temperature": 0.3, "num_predict": 2048},
        "stream": False
    }

    print("\n" + "="*30 + f" API CALL ({len(target_paragraphs)} segments) " + "="*30)
    print(f"TARGET: {[p[0] for p in target_paragraphs]}")
    
    try:
        response = requests.post(url, json=payload, timeout=180)
        response.raise_for_status()
        return response.json()['message']['content']
    except Exception as e:
        print(f"  [Error] API调用失败: {e}")
        return None

def parse_translation_response(content, expected_nums):
    results = {}
    pattern = re.compile(r'(?:^|\n)(\d+)\.\s*(.*?)(?=\n\s*\d+\.|\n\s*\n|\Z)', re.DOTALL)
    matches = pattern.findall(content)
    for num_str, text in matches:
        num = int(num_str)
        if num in expected_nums:
            results[str(num)] = text.strip()
    return results

def is_valid_translation(text):
    if not text: return False
    text = text.strip()
    if len(text) < 2: return False
    if "此段需要翻译" in text: return False
    return True

def process_file(file_path, output_dir, model="gemma4:e4b"):
    file_name = os.path.basename(file_path)
    base_name = os.path.splitext(file_name)[0]
    output_path = os.path.join(output_dir, f"{base_name}.json")
    
    paragraphs = extract_paragraphs(file_path)
    if not paragraphs: return

    translations = {}
    if os.path.exists(output_path):
        with open(output_path, 'r', encoding='utf-8') as f:
            try: translations = json.load(f)
            except: translations = {}

    # 预先清理无效翻译
    translations = {k: v for k, v in translations.items() if is_valid_translation(v)}

    p_idx = 0
    total = len(paragraphs)
    
    while p_idx < total:
        # 寻找下一个未翻译的起始点
        if str(paragraphs[p_idx][0]) in translations:
            p_idx += 1
            continue
        
        # 尝试翻译 5 段
        batch = paragraphs[p_idx : p_idx + 5]
        expected_nums = [p[0] for p in batch]
        context = paragraphs[max(0, p_idx - 5) : p_idx]
        
        print(f"\n>>> 正在处理批次: {expected_nums}")
        response = translate_batch(batch, context, model)
        
        if response:
            batch_results = parse_translation_response(response, expected_nums)
            received_nums = sorted([int(k) for k in batch_results.keys()])
            
            # 情况1：全部拿到了
            if all(str(n) in batch_results for n in expected_nums):
                print(f"  [Success] 完整翻译 5 段")
                translations.update(batch_results)
                p_idx += 5
            
            # 情况2：部分拿到
            elif received_nums:
                # 确定断点。假设收到的最后一个段落 received_nums[-1] 是不完整的
                breakpoint_num = received_nums[-1]
                # 保存断点之前的段落（它们是完整的）
                for n in received_nums[:-1]:
                    translations[str(n)] = batch_results[str(n)]
                
                print(f"  [Partial] 仅收到 {received_nums}，认为 {breakpoint_num} 不完整。启动救援...")
                
                # 救援模式：尝试翻译 [断点, 下一段]
                # 找到断点在 paragraphs 中的索引
                b_idx = -1
                for i, p in enumerate(paragraphs):
                    if p[0] == breakpoint_num:
                        b_idx = i; break
                
                if b_idx != -1 and b_idx + 1 < total:
                    rescue_batch = paragraphs[b_idx : b_idx + 2]
                    rescue_nums = [p[0] for p in rescue_batch]
                    rescue_context = paragraphs[max(0, b_idx - 3) : b_idx]
                    
                    rescue_success = False
                    for retry in range(2):
                        print(f"  [Rescue] 尝试救援段落 {rescue_nums} (第 {retry+1} 次)")
                        r_response = translate_batch(rescue_batch, rescue_context, model)
                        if r_response:
                            r_results = parse_translation_response(r_response, rescue_nums)
                            if str(breakpoint_num) in r_results:
                                print(f"  [Success] 救援成功，已补全 {breakpoint_num}")
                                translations[str(breakpoint_num)] = r_results[str(breakpoint_num)]
                                rescue_success = True
                                break
                    
                    if not rescue_success:
                        print(f"  [Fail] 救援失败，标记 {breakpoint_num} 为错误。")
                        translations[str(breakpoint_num)] = f"[ERROR: Translation Incomplete for segment {breakpoint_num}]"
                    
                    # 无论救援是否完全成功，下一次都从 breakpoint_num + 1 开始
                    p_idx = b_idx + 1
                else:
                    # 如果断点就是最后一段，无法通过下一段救援，直接标记
                    translations[str(breakpoint_num)] = batch_results[str(breakpoint_num)]
                    p_idx = total
            else:
                print(f"  [Error] 批次返回为空，重试整个批次...")
                time.sleep(2)
        else:
            print(f"  [Error] API 无响应，等待重试...")
            time.sleep(5)

        # 每次循环结束保存一次
        sorted_trans = dict(sorted(translations.items(), key=lambda x: int(x[0])))
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(sorted_trans, f, ensure_ascii=False, indent=2)

def main():
    split_dir = "split"
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    
    files = sorted(glob.glob(os.path.join(split_dir, "*.md")), 
                   key=lambda x: int(re.search(r'(\d+)', os.path.basename(x)).group(1)) if re.search(r'(\d+)', os.path.basename(x)) else 0)
    
    for f in [f for f in files if int(re.search(r'(\d+)', os.path.basename(f)).group(1)) >= 41]:
        process_file(f, output_dir)

if __name__ == "__main__":
    main()
