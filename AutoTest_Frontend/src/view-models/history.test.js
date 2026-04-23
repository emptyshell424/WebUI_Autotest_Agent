import { describe, it, expect } from 'vitest'
import { buildHistoryOutput, classifyOutcome } from './history.js'

const t = (key) => key

describe('history helpers', () => {
  it('classifies outcome and formats output', () => {
    expect(classifyOutcome('healed_completed', t)).toBe('history.outcomeRepairSuccess')
    const output = buildHistoryOutput({ logs: 'done', error: '' }, t)
    expect(output).toMatch(/\[STDOUT\]/)
    expect(output).toMatch(/done/)
  })
})
