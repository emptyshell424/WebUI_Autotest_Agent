# app/services/rag_service.py
import chromadb
import os

class RAGService:
    def __init__(self):
        # 1. 初始化数据库客户端
        # 解释：PersistentClient 表示数据会保存到硬盘的 './data/rag' 目录下。
        # 如果你不写 path，默认是内存模式，一重启程序数据就丢了。我们做毕设要持久化。
        self.client = chromadb.PersistentClient(path="./data/rag")
        
        # 2. 创建或获取集合 (Collection)
        # 解释：Collection 就像 MySQL 里的“表”。我们把所有 Selenium 知识都放在这个表里。
        # Chroma 会自动帮我们下载一个轻量级模型（all-MiniLM-L6-v2）来做文本向量化，不用你操心。
        self.collection = self.client.get_or_create_collection(name="selenium_knowledge")

    def add_knowledge(self, text: str, source: str):
        """
        功能：把文本切片并存入数据库
        """
        # 解释：为什么不直接存一大段？因为 AI 的上下文有限，我们把知识按行切开，
        # 这样检索时能精准找到某一条规则，而不是把整本书都扔给 AI。
        documents = [line for line in text.split('\n') if line.strip()]
        
        # 给每条知识起个唯一 ID，防止重复
        ids = [f"{source}_{i}" for i in range(len(documents))]
        
        if not documents:
            return

        print(f"📚 [RAG] 正在存入 {len(documents)} 条知识...")
        
        # 核心动作：存！
        # Chroma 会自动把 documents 里的文字转换成 [0.1, 0.5, ...] 这样的向量存起来。
        self.collection.add(
            documents=documents,
            ids=ids,
            metadatas=[{"source": source}] * len(documents)
        )

    def search(self, query: str, n_results: int = 2) -> str:
        """
        功能：根据问题检索最相关的知识
        参数：n_results=2 表示只找最匹配的 2 条（贪多嚼不烂，给 AI 最准的就行）
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        # 解释：results['documents'] 返回的是列表的列表（因为可以一次查多个问题），
        # 所以我们取 [0] 拿到当前问题的结果，然后用换行符拼接成一段话。
        knowledge_text = "\n".join(results['documents'][0])
        return knowledge_text

# 实例化服务
rag = RAGService()

# --- 初始化逻辑 ---
# 解释：为了方便，每次启动服务时，我们都重新把 txt 里的内容刷一遍进数据库。
# 在生产环境不能这么做（会重复），但毕设为了调试方便，这样能保证你改了 txt 后重启立马生效。
kb_path = "app/knowledge_base/selenium_tips.txt"
if os.path.exists(kb_path):
    with open(kb_path, "r", encoding="utf-8") as f:
        # source="selenium_tips" 是为了标记这些知识的来源
        rag.add_knowledge(f.read(), "selenium_tips")