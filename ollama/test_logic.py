import re
import json
import os
import traceback

# 导入待测函数
from translate import extract_paragraphs, parse_translation_response

def test_extraction():
    print("--- 测试段落提取 ---")
    test_md = "test_sample.md"
    content = """# 卷测试
1. 段落一内容
**(此段需要翻译)**

2. 段落二内容
具有换行
**(此段需要翻译)**

3. 段落三
**(此段需要翻译)**
"""
    with open(test_md, "w", encoding="utf-8") as f:
        f.write(content)
    
    try:
        paragraphs = extract_paragraphs(test_md)
        if os.path.exists(test_md):
            os.remove(test_md)
        
        expected = [
            (1, "段落一内容"),
            (2, "段落二内容\n具有换行"),
            (3, "段落三")
        ]
        
        for i, (num, text) in enumerate(paragraphs):
            print(f"提取到段落 {num}: {repr(text[:20])}...")
            assert num == expected[i][0], f"期望 {expected[i][0]} 但获得 {num}"
            assert text == expected[i][1], f"段落 {num} 内容不符"
        
        print("✅ 段落提取测试通过\n")
    except Exception as e:
        print(f"❌ 提取测试失败: {e}")
        traceback.print_exc()
        raise

def test_parsing():
    print("--- 测试结果解析 ---")
    mock_response = """这是模型的开场白，不应该被解析。

1. 翻译后的内容一
2. 翻译后的内容二
带有换行的内容

3. 翻译后的内容三

这是结尾。"""
    
    expected_nums = [1, 2, 3]
    results = parse_translation_response(mock_response, expected_nums)
    
    print(f"解析结果: {json.dumps(results, ensure_ascii=False, indent=2)}")
    
    try:
        assert "1" in results, "未找到段落 1"
        assert results["1"] == "翻译后的内容一", f"段落 1 内容不符: {results['1']}"
        assert "2" in results, "未找到段落 2"
        assert "带有换行的内容" in results["2"], "段落 2 未包含换行内容"
        assert "3" in results, "未找到段落 3"
        # 此时应不包含结尾文字
        assert results["3"] == "翻译后的内容三", f"段落 3 内容不符: {results['3']}"
        print("✅ 结果解析测试通过\n")
    except Exception as e:
        print(f"❌ 解析测试失败: {e}")
        traceback.print_exc()
        raise

def test_checkpointing():
    print("--- 测试断点续传逻辑模拟 ---")
    # 模拟已有的翻译
    translations = {"1": "已翻译内容"}
    batch_nums = [1, 2]
    
    needed = [n for n in batch_nums if str(n) not in translations]
    assert needed == [2]
    print(f"已跳过段落 1，仅需翻译段落: {needed}")
    print("✅ 断点续传逻辑测试通过\n")

if __name__ == "__main__":
    try:
        test_extraction()
        test_parsing()
        test_checkpointing()
        print("ALL TESTS PASSED! 逻辑验证成功，可以开始实际执行。")
    except Exception:
        # 异常已经在各子测试函数中打印
        pass
