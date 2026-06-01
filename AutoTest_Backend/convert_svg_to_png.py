import os
import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions

SVG_CODE = """<svg viewBox="0 0 960 580" width="100%" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <!-- 全局学术级字体样式声明：英文用 Times New Roman，中文用宋体 -->
    <style>
      text {
        font-family: "Times New Roman", SimSun, "Songti SC", "STSong", serif;
      }
    </style>

    <!-- 渐变定义：前端蓝 -->
    <linearGradient id="blueGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#E3F2FD"/>
      <stop offset="100%" stop-color="#BBDEFB"/>
    </linearGradient>
    
    <!-- 渐变定义：网关褐 -->
    <linearGradient id="brownGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#F5EFEF"/>
      <stop offset="100%" stop-color="#E0D5D5"/>
    </linearGradient>

    <!-- 渐变定义：检索蓝 -->
    <linearGradient id="indigoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#E8EFFF"/>
      <stop offset="100%" stop-color="#C5CAE9"/>
    </linearGradient>

    <!-- 渐变定义：自愈绿 -->
    <linearGradient id="greenGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#E8F5E9"/>
      <stop offset="100%" stop-color="#C8E6C9"/>
    </linearGradient>

    <!-- 渐变定义：持久化橙 -->
    <linearGradient id="orangeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FFF3E0"/>
      <stop offset="100%" stop-color="#FFE0B2"/>
    </linearGradient>

    <!-- 阴影滤镜 -->
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="4" stdDeviation="4" flood-color="#1E293B" flood-opacity="0.06"/>
    </filter>
    <filter id="boxShadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#000000" flood-opacity="0.03"/>
    </filter>

    <!-- 箭头定义 -->
    <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="#334155"/>
    </marker>
  </defs>

  <!-- ==================== BACKGROUND BOXES (SUBGRAPHS) ==================== -->
  
  <!-- 前端框架 Subgraph -->
  <rect x="20" y="20" width="220" height="240" rx="8" fill="#F8FAFC" stroke="#3B82F6" stroke-width="1.5" stroke-dasharray="5 5" filter="url(#boxShadow)"/>
  
  <!-- 后端核心业务服务 Subgraph -->
  <rect x="280" y="20" width="320" height="480" rx="8" fill="#FFFDF5" stroke="#F59E0B" stroke-width="1.5" stroke-dasharray="5 5" filter="url(#boxShadow)"/>
  <text x="440" y="52" text-anchor="middle" font-size="16" font-weight="bold" fill="#78350F">后端核心业务服务</text>

  <!-- 数据持久化层 Subgraph -->
  <rect x="640" y="20" width="280" height="480" rx="8" fill="#F4FBF7" stroke="#10B981" stroke-width="1.5" stroke-dasharray="5 5" filter="url(#boxShadow)"/>
  <text x="780" y="52" text-anchor="middle" font-size="16" font-weight="bold" fill="#065F46">数据持久化层</text>

  <!-- ==================== COMPONENTS & NODES ==================== -->

  <!-- 前端框架卡片 -->
  <g filter="url(#shadow)">
    <rect x="40" y="45" width="180" height="185" rx="6" fill="url(#blueGrad)" stroke="#1E88E5" stroke-width="1.5"/>
    <text x="130" y="80" text-anchor="middle" font-size="18" font-weight="bold" fill="#0D47A1">前端框架</text>
    <text x="130" y="120" text-anchor="middle" font-size="14" fill="#1E3A8A">工作台</text>
    <text x="130" y="155" text-anchor="middle" font-size="14" fill="#1E3A8A">历史记录</text>
    <text x="130" y="190" text-anchor="middle" font-size="14" fill="#1E3A8A">指标看板</text>
  </g>

  <!-- 接口网关 -->
  <g filter="url(#shadow)">
    <rect x="40" y="290" width="180" height="80" rx="6" fill="url(#brownGrad)" stroke="#8D6E63" stroke-width="1.5"/>
    <text x="130" y="325" text-anchor="middle" font-size="15" font-weight="bold" fill="#4E342E">接口网关</text>
    <text x="130" y="350" text-anchor="middle" font-size="12" fill="#6D4C41">HTTP API &amp; SSE 事件流</text>
  </g>

  <!-- 检索服务 -->
  <g filter="url(#shadow)">
    <rect x="340" y="100" width="200" height="50" rx="6" fill="url(#indigoGrad)" stroke="#3F51B5" stroke-width="1.5"/>
    <text x="440" y="130" text-anchor="middle" font-size="14" font-weight="bold" fill="#1A237E">检索服务</text>
  </g>

  <!-- 生成服务 -->
  <g filter="url(#shadow)">
    <rect x="340" y="210" width="200" height="50" rx="6" fill="url(#greenGrad)" stroke="#4CAF50" stroke-width="1.5"/>
    <text x="440" y="240" text-anchor="middle" font-size="14" font-weight="bold" fill="#1B5E20">生成服务</text>
  </g>

  <!-- 外部大模型 -->
  <g filter="url(#shadow)">
    <rect x="370" y="310" width="140" height="50" rx="4" fill="#FFFFFF" stroke="#1E293B" stroke-width="1.5"/>
    <text x="440" y="340" text-anchor="middle" font-size="14" font-weight="bold" fill="#0F172A">外部大模型</text>
  </g>

  <!-- 执行与自愈服务 -->
  <g filter="url(#shadow)">
    <rect x="340" y="410" width="200" height="50" rx="6" fill="url(#greenGrad)" stroke="#4CAF50" stroke-width="1.5"/>
    <text x="440" y="440" text-anchor="middle" font-size="14" font-weight="bold" fill="#1B5E20">执行与自愈服务</text>
  </g>

  <!-- 被测网页 -->
  <g filter="url(#shadow)">
    <rect x="370" y="520" width="140" height="40" rx="4" fill="#FFFFFF" stroke="#1E293B" stroke-width="1.5"/>
    <text x="440" y="545" text-anchor="middle" font-size="13" font-weight="bold" fill="#0F172A">被测网页</text>
  </g>

  <!-- 数据库 1: ChromaDB -->
  <g filter="url(#shadow)">
    <path d="M 690 110 A 80 15 0 0 0 850 110 L 850 145 A 80 15 0 0 1 690 145 Z" fill="url(#orangeGrad)" stroke="#FF9800" stroke-width="1.5"/>
    <ellipse cx="770" cy="110" rx="80" ry="15" fill="url(#orangeGrad)" stroke="#FF9800" stroke-width="1.5"/>
    <text x="770" y="132" text-anchor="middle" font-size="13" font-weight="bold" fill="#E65100">ChromaDB 向量库</text>
  </g>

  <!-- 数据库 2: SQLite -->
  <g filter="url(#shadow)">
    <path d="M 690 220 A 80 15 0 0 0 850 220 L 850 255 A 80 15 0 0 1 690 255 Z" fill="url(#orangeGrad)" stroke="#FF9800" stroke-width="1.5"/>
    <ellipse cx="770" cy="220" rx="80" ry="15" fill="url(#orangeGrad)" stroke="#FF9800" stroke-width="1.5"/>
    <text x="770" y="242" text-anchor="middle" font-size="13" font-weight="bold" fill="#E65100">SQLite 数据库</text>
  </g>

  <!-- 数据库 3: 本地文件系统 -->
  <g filter="url(#shadow)">
    <path d="M 690 420 A 80 15 0 0 0 850 420 L 850 455 A 80 15 0 0 1 690 455 Z" fill="url(#orangeGrad)" stroke="#FF9800" stroke-width="1.5"/>
    <ellipse cx="770" cy="420" rx="80" ry="15" fill="url(#orangeGrad)" stroke="#FF9800" stroke-width="1.5"/>
    <text x="770" y="442" text-anchor="middle" font-size="13" font-weight="bold" fill="#E65100">本地文件系统</text>
  </g>

  <!-- ==================== LINES & ARROWS ==================== -->

  <!-- 前端框架 <-> 接口网关 (双向箭头) -->
  <path d="M 130 230 L 130 282" stroke="#334155" stroke-width="1.5" marker-start="url(#arrow)" marker-end="url(#arrow)"/>

  <!-- 接口网关 -> 生成服务 (折线) -->
  <path d="M 220 330 L 255 330 L 255 235 L 332 235" fill="none" stroke="#334155" stroke-width="1.5" marker-end="url(#arrow)"/>

  <!-- 接口网关 -> 执行与自愈服务 (折线) -->
  <path d="M 220 330 L 255 330 L 255 435 L 332 435" fill="none" stroke="#334155" stroke-width="1.5" marker-end="url(#arrow)"/>

  <!-- 生成服务 -> 检索服务 (直线向上) -->
  <path d="M 440 210 L 440 158" fill="none" stroke="#334155" stroke-width="1.5" marker-end="url(#arrow)"/>

  <!-- 检索服务 -> ChromaDB (直线向右) -->
  <path d="M 540 125 L 682 125" fill="none" stroke="#334155" stroke-width="1.5" marker-end="url(#arrow)"/>

  <!-- 生成服务 -> SQLite 数据库 (直线向右) -->
  <path d="M 540 235 L 682 235" fill="none" stroke="#334155" stroke-width="1.5" marker-end="url(#arrow)"/>

  <!-- 执行与自愈服务 -> 本地文件系统 (直线向右) -->
  <path d="M 540 435 L 682 435" fill="none" stroke="#334155" stroke-width="1.5" marker-end="url(#arrow)"/>

  <!-- 贯通的连接竖线 (汇合总线效果) -->
  <path d="M 590 235 L 590 435" fill="none" stroke="#334155" stroke-width="1.5"/>

  <!-- 外部大模型 -> 生成服务 (直线向上) -->
  <path d="M 440 310 L 440 268" fill="none" stroke="#334155" stroke-width="1.5" marker-end="url(#arrow)"/>
  <text x="445" y="290" font-size="11" fill="#475569">代码生成与自愈修复</text>

  <!-- 外部大模型 -> 执行与自愈服务 (直线向下) -->
  <path d="M 440 360 L 440 402" fill="none" stroke="#334155" stroke-width="1.5" marker-end="url(#arrow)"/>
  <text x="445" y="385" font-size="11" fill="#475569">代码生成与自愈修复</text>

  <!-- 执行与自愈服务 -> 被测网页 (直线向下) -->
  <path d="M 440 460 L 440 512" fill="none" stroke="#334155" stroke-width="1.5" marker-end="url(#arrow)"/>
  <text x="445" y="490" font-size="11" fill="#475569">WebDriver 驱动控制</text>
</svg>"""

def render_svg_to_png(svg_content, output_path, width=960, height=580):
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            html, body {{
                margin: 0;
                padding: 0;
                width: {width}px;
                height: {height}px;
                overflow: hidden;
                background-color: transparent;
            }}
            svg {{
                display: block;
                width: 100%;
                height: 100%;
            }}
        </style>
    </head>
    <body>
        {svg_content}
    </body>
    </html>
    """
    
    temp_html_path = os.path.abspath("temp_diagram.html")
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    driver = None
    try:
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument(f"--window-size={width},{height}")
        chrome_options.add_argument("--hide-scrollbars")
        driver = webdriver.Chrome(options=chrome_options)
        print("Chrome webdriver initialized successfully.")
    except Exception as e:
        print("Chrome failed, trying Edge...", e)
        try:
            edge_options = EdgeOptions()
            edge_options.add_argument("--headless")
            edge_options.add_argument("--disable-gpu")
            edge_options.add_argument(f"--window-size={width},{height}")
            edge_options.add_argument("--hide-scrollbars")
            driver = webdriver.Edge(options=edge_options)
            print("Edge webdriver initialized successfully.")
        except Exception as e2:
            print("Edge failed too:", e2)
            sys.exit(1)
            
    try:
        driver.get(f"file:///{temp_html_path}")
        time.sleep(1.5)  # Let fonts and shadows render completely
        
        body_el = driver.find_element("tag name", "body")
        body_el.screenshot(output_path)
        print(f"Successfully rendered SVG and saved as PNG to {output_path}")
    finally:
        if driver:
            driver.quit()
        if os.path.exists(temp_html_path):
            os.remove(temp_html_path)

if __name__ == "__main__":
    out_path = r"C:\Users\c5\.gemini\antigravity\brain\8bcff01c-b344-47ac-88c4-9ea920cb8254\architecture_diagram.png"
    render_svg_to_png(SVG_CODE, out_path)
