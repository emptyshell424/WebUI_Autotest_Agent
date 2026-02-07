from fastapi import FastAPI
from pydantic import BaseModel
from app.services.llm_service import llm
from app.services.rag_service import rag
from app.utils.code_parser import clean_code      # 导入清洗工具
from app.services.executor_service import executor # 导入执行器



app = FastAPI(title = "Web UI AutoTest")


#  1. 定义请求的数据结构 (Schema)
class ChatRequest(BaseModel):
    prompt: str
    run: bool = False

# 2. 编写接口
@app.post("/api/debug/chat")
async def debug_chat(request: ChatRequest):
    # 1. RAG 检索
    context = rag.search(request.prompt)
    
    # 2. 组装 Prompt
    augmented_prompt = f"""
    【背景知识】
    {context}
    
    【用户需求】
    {request.prompt}
    
    请编写完整的 Python Selenium 代码。
    要求：
    1. 使用 webdriver.Chrome()。
    2. 执行完操作后，打印 "Test Completed"。
    3. 不要使用 Markdown 格式。
    """
    
    # 3. LLM 生成
    raw_response = llm.chat(augmented_prompt)
    
    # === 新增逻辑开始 ===
    
    # 4. 清洗代码
    cleaned_code = clean_code(raw_response)
    
    execution_result = None
    if request.run:
        print("⚡️ 用户要求立即运行代码...")
        execution_result = executor.run_code(cleaned_code)
    
    # === 新增逻辑结束 ===

    return {
        "status": "success",
        "rag_context": context,
        "raw_output": raw_response,
        "cleaned_code": cleaned_code, # 返回清洗后的代码给前端看
        "execution_result": execution_result # 返回运行结果
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)