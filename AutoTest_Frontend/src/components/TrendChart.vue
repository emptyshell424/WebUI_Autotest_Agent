<template>
  <div class="trend-chart" v-if="rows.length">
    <svg :viewBox="`0 0 ${width} ${height}`" :width="width" :height="height" class="trend-svg">
      <!-- grid lines -->
      <line
        v-for="i in 4"
        :key="'grid-' + i"
        :x1="padding"
        :y1="chartTop + (chartHeight / 4) * i"
        :x2="width - padding"
        :y2="chartTop + (chartHeight / 4) * i"
        stroke="var(--el-border-color-lighter, #ebeef5)"
        stroke-dasharray="4 3"
      />

      <!-- stacked bars -->
      <g v-for="(row, idx) in rows" :key="row.bucket">
        <title>{{ row.bucket }}: {{ row.execution_count }} executions</title>
        <!-- completed -->
        <rect
          :x="barX(idx)"
          :y="barY(row.completed_count, maxCount)"
          :width="barWidth"
          :height="barHeight(row.completed_count, maxCount)"
          fill="var(--el-color-success, #67c23a)"
          rx="2"
        />
        <!-- healed -->
        <rect
          :x="barX(idx)"
          :y="barY(row.completed_count + row.healed_completed_count, maxCount)"
          :width="barWidth"
          :height="barHeight(row.healed_completed_count, maxCount)"
          fill="var(--el-color-warning, #e6a23c)"
          rx="2"
        />
        <!-- failed -->
        <rect
          :x="barX(idx)"
          :y="barY(row.completed_count + row.healed_completed_count + row.failed_count, maxCount)"
          :width="barWidth"
          :height="barHeight(row.failed_count, maxCount)"
          fill="var(--el-color-danger, #f56c6c)"
          rx="2"
        />
        <!-- blocked -->
        <rect
          :x="barX(idx)"
          :y="barY(row.completed_count + row.healed_completed_count + row.failed_count + row.blocked_count, maxCount)"
          :width="barWidth"
          :height="barHeight(row.blocked_count, maxCount)"
          fill="var(--el-color-info, #909399)"
          rx="2"
        />
        <!-- bucket label -->
        <text
          :x="barX(idx) + barWidth / 2"
          :y="height - 4"
          text-anchor="middle"
          class="bucket-label"
        >{{ shortLabel(row.bucket) }}</text>
      </g>

      <!-- success rate line -->
      <polyline
        v-if="rows.length > 1"
        :points="ratePoints"
        fill="none"
        stroke="var(--el-color-primary, #409eff)"
        stroke-width="2"
        stroke-linejoin="round"
      />
      <circle
        v-for="(row, idx) in rows"
        :key="'dot-' + idx"
        :cx="barX(idx) + barWidth / 2"
        :cy="rateY(row.final_success_rate)"
        r="3"
        fill="var(--el-color-primary, #409eff)"
      />
    </svg>

    <div class="trend-legend">
      <span class="legend-item"><span class="dot" style="background: var(--el-color-success, #67c23a)"></span>{{ labels.firstPass }}</span>
      <span class="legend-item"><span class="dot" style="background: var(--el-color-warning, #e6a23c)"></span>{{ labels.healed }}</span>
      <span class="legend-item"><span class="dot" style="background: var(--el-color-danger, #f56c6c)"></span>{{ labels.failed }}</span>
      <span class="legend-item"><span class="dot" style="background: var(--el-color-info, #909399)"></span>{{ labels.blocked }}</span>
      <span class="legend-item"><span class="dot" style="background: var(--el-color-primary, #409eff)"></span>{{ labels.successRate }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  labels: { type: Object, default: () => ({ firstPass: 'First pass', healed: 'Healed', failed: 'Failed', blocked: 'Blocked', successRate: 'Success rate' }) },
})

const width = 600
const height = 200
const padding = 32
const chartTop = 12
const chartHeight = height - chartTop - 28

const maxCount = computed(() => {
  const max = Math.max(...props.rows.map(r => r.execution_count || 0), 1)
  return Math.ceil(max * 1.15)
})

const barWidth = computed(() => {
  const n = props.rows.length || 1
  const available = width - padding * 2
  return Math.max(Math.min(Math.floor(available / n) - 4, 40), 2)
})

const barX = (idx) => {
  const n = props.rows.length || 1
  const available = width - padding * 2
  const step = available / n
  return padding + step * idx + (step - barWidth.value) / 2
}

const barY = (cumulative, max) => {
  return chartTop + chartHeight - (cumulative / max) * chartHeight
}

const barHeight = (count, max) => {
  return Math.max((count / max) * chartHeight, 0)
}

const rateY = (rate) => {
  return chartTop + chartHeight - rate * chartHeight
}

const ratePoints = computed(() => {
  return props.rows.map((row, idx) => {
    const x = barX(idx) + barWidth.value / 2
    const y = rateY(row.final_success_rate)
    return `${x},${y}`
  }).join(' ')
})

const shortLabel = (bucket) => {
  if (!bucket) return ''
  return bucket.length > 10 ? bucket.slice(5) : bucket
}
</script>

<style scoped>
.trend-chart {
  width: 100%;
  overflow-x: auto;
}
.trend-svg {
  display: block;
  max-width: 100%;
  height: auto;
}
.bucket-label {
  font-size: 10px;
  fill: var(--el-text-color-secondary, #909399);
}
.trend-legend {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
}
</style>
