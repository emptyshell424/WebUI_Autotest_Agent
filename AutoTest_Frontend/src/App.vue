<template>
  <div class="main-container">
    <el-container class="layout-container">
      <el-header class="header">
        <div class="logo">🤖 AutoTest Agent <span class="version">v0.1</span></div>
        <el-tag type="success" effect="dark">后端已连接</el-tag>
      </el-header>

      <el-container>
        <el-aside width="400px" class="aside-panel">
          <el-card class="box-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <span>💬 测试指令</span>
              </div>
            </template>
            
            <el-input
              v-model="prompt"
              type="textarea"
              :rows="6"
              placeholder="例如：打开百度，搜索 'DeepSeek'，等待3秒后关闭"
              resize="none"
            />
            
            <div class="control-panel">
              <el-checkbox v-model="autoRun" label="生成后立即运行" size="large" border />
              <el-button 
                type="primary" 
                :icon="VideoPlay" 
                :loading="loading" 
                @click="sendRequest" 
                size="large"
                class="send-btn"
              >
                {{ loading ? 'AI 思考中...' : '生成并执行' }}
              </el-button>
            </div>
          </el-card>

          <el-alert
            v-if="ragContext"
            title="已检索到相关知识库"
            type="info"
            :description="ragContext.slice(0, 100) + '...'"
            show-icon
            class="mt-20"
          />
        </el-aside>

        <el-main class="main-panel">
          <el-row :gutter="20" style="height: 100%">
            <el-col :span="14" style="height: 100%">
              <el-card class="code-card" shadow="never">
                <template #header>
                  <span>📜 生成的代码 (Python Selenium)</span>
                </template>
                <el-input
                  v-model="generatedCode"
                  type="textarea"
                  class="code-editor"
                  readonly
                  placeholder="等待 AI 生成代码..."
                />
              </el-card>
            </el-col>

            <el-col :span="10" style="height: 100%">
              <el-card class="log-card" shadow="never">
                <template #header>
                  <span>🚀 执行结果</span>
                  <el-tag v-if="executionResult" :type="executionResult.success ? 'success' : 'danger'" size="small">
                    {{ executionResult.success ? 'Success' : 'Failed' }}
                  </el-tag>
                </template>
                <div class="log-content">
                  <pre v-if="executionResult">
                    【标准输出】: 
                    {{ executionResult.logs }}

                    【错误信息】: 
                    {{ executionResult.error }}
                   </pre>
                   <div v-else class="empty-log">等待执行...</div>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'
import { VideoPlay } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

// 响应式数据
const prompt = ref("打开 www.baidu.com，最大化窗口，搜索 'DeepSeek'，点击按钮，等待3秒关闭")
const autoRun = ref(true)
const loading = ref(false)
const generatedCode = ref("")
const ragContext = ref("")
const executionResult = ref(null)

// 发送请求给后端
const sendRequest = async () => {
  if (!prompt.value) return
  
  loading.value = true
  generatedCode.value = ""
  executionResult.value = null
  ragContext.value = ""

  try {
    // 调用 FastAPI 接口
    const res = await axios.post('http://127.0.0.1:8000/api/debug/chat', {
      prompt: prompt.value,
      run: autoRun.value
    })

    const data = res.data
    generatedCode.value = data.cleaned_code
    ragContext.value = data.rag_context
    executionResult.value = data.execution_result

    if (data.status === 'success') {
      ElMessage.success('任务完成！')
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('请求失败，请检查后端服务是否启动')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* 简单的样式美化 */
.main-container { height: 100vh; background: #f5f7fa; }
.layout-container { height: 100%; }
.header { 
  background: #fff; 
  border-bottom: 1px solid #dcdfe6; 
  display: flex; 
  align-items: center; 
  justify-content: space-between;
  padding: 0 40px;
}
.logo { font-size: 20px; font-weight: bold; color: #409eff; }
.aside-panel { padding: 20px; background: #fff; border-right: 1px solid #eee; }
.main-panel { padding: 20px; }
.control-panel { margin-top: 20px; display: flex; flex-direction: column; gap: 10px; }
.send-btn { width: 100%; }
.mt-20 { margin-top: 20px; }
.code-card, .log-card { height: 100%; display: flex; flex-direction: column; }
/* 让输入框充满容器高度 */
:deep(.el-textarea__inner) { height: 100% !important; font-family: 'Consolas', monospace; background-color: #fafafa; }
.log-content { 
  background: #1e1e1e; 
  color: #00ff00; 
  padding: 10px; 
  height: 400px; 
  border-radius: 4px; 
  font-family: monospace; 
  overflow-y: auto;
}
.empty-log { color: #666; text-align: center; margin-top: 50px; }
</style>