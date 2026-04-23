import { describe, it, expect } from 'vitest'
import { buildMetricCards, formatRate } from './metrics.js'

const t = (key) => key

describe('metrics helpers', () => {
  it('builds cards and formats rate', () => {
    expect(formatRate(0.666)).toBe('67%')
    const cards = buildMetricCards(
      {
        generated_count: 1,
        execution_count: 2,
        first_pass_success_rate: 0.5,
        self_heal_triggered_rate: 0.5,
        self_heal_success_rate: 1,
        final_success_rate: 1,
      },
      t
    )
    expect(cards).toHaveLength(6)
    expect(cards[0].value).toBe(1)
  })
})
