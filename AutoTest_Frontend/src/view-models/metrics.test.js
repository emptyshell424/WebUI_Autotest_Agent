import test from 'node:test'
import assert from 'node:assert/strict'

import { buildMetricCards, formatRate } from './metrics.js'

const t = (key) => key

test('metrics helper builds cards and formats rate', () => {
  assert.equal(formatRate(0.666), '67%')
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
  assert.equal(cards.length, 6)
  assert.equal(cards[0].value, 1)
})
