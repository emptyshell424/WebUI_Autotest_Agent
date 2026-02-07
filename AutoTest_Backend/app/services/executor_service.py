# app/services/executor_service.py
import subprocess
import os
import sys

class ExecutorService:
    def __init__(self):
        # 创建一个临时目录存放生成的脚本
        self.temp_dir = "temp_scripts"
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def run_code(self, code: str) -> dict:
        """
        核心功能：保存代码 -> 运行代码 -> 捕获结果
        """
        # 1. 保存文件
        file_path = os.path.join(self.temp_dir, "generated_test.py")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
        
        print(f"🚀 [Executor] 正在运行脚本: {file_path}")

        # 2. 调用系统 python 解释器运行它
        # sys.executable 指向当前正在运行的 venv 里的 python.exe，确保环境一致
        try:
            result = subprocess.run(
                [sys.executable, file_path],
                capture_output=True, # 捕获 print 输出
                text=True,           # 以文本形式读取
                timeout=60           # 最多跑 60 秒，防止死循环
            )
            
            # 3. 整理结果
            return {
                "success": result.returncode == 0, # 0 代表运行成功
                "logs": result.stdout,            # 标准输出（print的内容）
                "error": result.stderr            # 错误输出（报错信息）
            }
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "执行超时 (Timeout)"}
        except Exception as e:
            return {"success": False, "error": f"执行异常: {str(e)}"}

executor = ExecutorService()