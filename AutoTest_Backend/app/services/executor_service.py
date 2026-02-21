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
        file_path = os.path.join(self.temp_dir, "generated_test.py")
        out_log_path = os.path.join(self.temp_dir, "stdout.log")  # 标准输出物理文件
        err_log_path = os.path.join(self.temp_dir, "stderr.log")  # 错误输出物理文件

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
        
        print(f"🚀 [Executor] 正在运行脚本: {file_path}")

        try:
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW
            
            run_env = os.environ.copy()
            run_env["PYTHONIOENCODING"] = "utf-8"
            run_env["PYTHONUNBUFFERED"] = "1"

            # === 终极逻辑：不依赖内存管道，直接将日志强制写入物理硬盘 ===
            with open(out_log_path, "w", encoding="utf-8") as out_f, \
                 open(err_log_path, "w", encoding="utf-8") as err_f:
                
                result = subprocess.run(
                    [sys.executable, file_path],
                    stdout=out_f,   # 将正常输出重定向到硬盘文件
                    stderr=err_f,   # 将错误输出重定向到硬盘文件
                    text=True,
                    encoding='utf-8', 
                    timeout=60,
                    creationflags=creationflags,
                    env=run_env
                )
            # =============================================================
            
            # 进程结束后，从硬盘中把日志安全地读出来
            with open(out_log_path, "r", encoding="utf-8") as out_f:
                logs = out_f.read().strip() or "(无标准输出)"
            with open(err_log_path, "r", encoding="utf-8") as err_f:
                error = err_f.read().strip() or "(无错误输出)"

            if result.returncode != 0 and error == "(无错误输出)":
                 error = f"未知错误：脚本非正常退出。返回码: {result.returncode}"

            return {
                "success": result.returncode == 0,
                "logs": logs,
                "error": error
            }
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "执行超时 (Timeout)"}
        except Exception as e:
            return {"success": False, "error": f"执行器内部异常: {str(e)}"}
        
executor = ExecutorService()