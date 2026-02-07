from openai import OpenAI
from app.core.config import settings


class LLMService:
    def __init__(self):

        self.client = OpenAI(
            api_key = settings.DEEPSEEK_API_KEY,
            base_url = settings.DEEPSEEK_BASE_URL
        )

    def chat(self, prompt: str) -> str:
        """
        基础对话方法： 输入提示词， 返回 AI 的回答
        """

        try:
            # 打印日志
            print(f"🤖 [LLM Request] Model: {settings.MODEL_NAME}")

            response = self.client.chat.completions.create(
                model = settings.MODEL_NAME,
                messages = [
                    # system prompt: 给 AI 设定人设
                    {"role": "system", "content": "你是一个资深的 Python Selenium 自动化测试专家，只输出代码，不要废话。"},

                    {"role": "user", "content": prompt},
                ],

                temperature = 0.1,
                stream = False
            )
            result = response.choices[0].message.content
            print(f"✅ [LLM Response] Length: {len(result)}")
            return result
        
        except Exception as e:
            print(f"❌ [LLM Error] {e}")

            return f"Error: {e}"
        
llm = LLMService()