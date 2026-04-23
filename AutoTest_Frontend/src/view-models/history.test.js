import test from 'node:test'
import assert from 'node:assert/strict'

import { buildHistoryOutput, classifyOutcome } from './history.js'

const t = (key) => key

test('history helper classifies outcome and formats output', () => {
  assert.equal(classifyOutcome('healed_completed', t), 'history.outcomeRepairSuccess')
  const output = buildHistoryOutput({ logs: 'done', error: '' }, t)
  assert.match(output, /\[STDOUT\]/)
  assert.match(output, /done/)
})
