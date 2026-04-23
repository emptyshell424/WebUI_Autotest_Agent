<template>
  <div class="code-editor-wrap">
    <div class="line-numbers" aria-hidden="true">
      <span v-for="n in lineCount" :key="n">{{ n }}</span>
    </div>
    <textarea
      ref="textareaRef"
      class="code-textarea"
      :value="modelValue"
      :placeholder="placeholder"
      :rows="rows"
      spellcheck="false"
      @input="$emit('update:modelValue', $event.target.value)"
      @keydown="handleKeydown"
      @scroll="syncScroll"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  rows: { type: Number, default: 18 },
})

defineEmits(['update:modelValue'])

const textareaRef = ref(null)

const lineCount = computed(() => {
  const lines = (props.modelValue || '').split('\n').length
  return Math.max(lines, props.rows)
})

const handleKeydown = (event) => {
  if (event.key === 'Tab') {
    event.preventDefault()
    const textarea = event.target
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const value = textarea.value
    textarea.value = value.substring(0, start) + '    ' + value.substring(end)
    textarea.selectionStart = textarea.selectionEnd = start + 4
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
  }
}

const syncScroll = (event) => {
  const el = event.target.parentElement?.querySelector('.line-numbers')
  if (el) {
    el.scrollTop = event.target.scrollTop
  }
}
</script>

<style scoped>
.code-editor-wrap {
  display: flex;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  overflow: hidden;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  background: var(--el-bg-color, #fff);
}

.line-numbers {
  display: flex;
  flex-direction: column;
  padding: 8px 0;
  min-width: 40px;
  text-align: right;
  background: var(--el-fill-color-lighter, #f5f7fa);
  color: var(--el-text-color-placeholder, #a8abb2);
  user-select: none;
  overflow: hidden;
  border-right: 1px solid var(--el-border-color-lighter, #ebeef5);
}

.line-numbers span {
  padding: 0 8px;
  display: block;
}

.code-textarea {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  padding: 8px 12px;
  font-family: inherit;
  font-size: inherit;
  line-height: inherit;
  background: transparent;
  color: var(--el-text-color-primary, #303133);
  tab-size: 4;
  white-space: pre;
  overflow-wrap: normal;
  overflow-x: auto;
}

.code-textarea::placeholder {
  color: var(--el-text-color-placeholder, #a8abb2);
}
</style>
