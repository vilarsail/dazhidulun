import requests
import json
import re
import os

def extract_paragraphs(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Regex to find paragraphs in the format: n. text \n\n**(此段需要翻译)**
    # It accounts for potential variations in whitespace and newlines.
    pattern = re.compile(r'(\d+)\.\s*(.*?)\s*\*\*\((?:此段需要翻译|.*)\)\*\*', re.DOTALL)
    matches = pattern.findall(content)
    
    paragraphs = []
    for num, text in matches:
        paragraphs.append((int(num), text.strip()))
    
    return paragraphs

def translate_paragraphs(target_paragraphs, context_paragraphs=None, model="gemma4:e4b"):
    url = "http://localhost:11434/api/chat"
    
    system_prompt = (
        "你是一位精通古代汉语（特别是佛经文献）和现代汉语的翻译专家。你的任务是将《大智度论》的原文段落准确、优美地翻译成现代汉语。\n"
        "### 翻译要求\n"
        "1. **风格**：保持庄重、准确，翻译应符合现代汉语表达习惯，同时保留佛经原有的深邃意蕴。\n"
        "2. **术语**：核心佛教术语（如：涅槃、比丘、如来等）通常保留原词，或根据上下文给出最贴切的解释。\n"
        "3. **格式维护**：严格保持原有的有序列表编号（如 1. 2. 3. ...）。\n"
        "4. **输出格式**：仅输出翻译后的有序列表，不要包含任何其他解释或前言。\n"
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
        "stream": False
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()['message']['content']
    except Exception as e:
        return f"Error calling Ollama API: {e}"

def main():
    file_path = 'split/41.md'
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        return

    paragraphs = extract_paragraphs(file_path)
    
    # Demo: Translate first 5 paragraphs (no context)
    target = paragraphs[25:30]
    print(f"--- 正在翻译第 1-{len(target)} 段 ---")
    translation = translate_paragraphs(target)
    print(translation)
    
    # Demo: Translate next 5 paragraphs with context
    if len(paragraphs) > 5:
        context = paragraphs[:5]
        target = paragraphs[5:10]
        print(f"\n--- 正在翻译第 6-{5+len(target)} 段 (带上文参考) ---")
        translation = translate_paragraphs(target, context_paragraphs=context)
        print(translation)

if __name__ == "__main__":
    main()
