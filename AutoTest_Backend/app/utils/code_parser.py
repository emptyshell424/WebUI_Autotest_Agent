import re

def clean_code(llm_response: str) -> str:
    """
    功能 ： 把大模型返回的 Markdown 格式 清理成纯 Python 代码
    """

    pattern = r"```python\s*(.*?)\s*```"
    match = re.search(pattern, llm_response, re.DOTALL)

    if match:
        # 如果匹配到了，就取中间那段
        return match.group(1)
    
    cleaned = llm_response.replace("```python", "").replace("```", "").strip()
    return cleaned