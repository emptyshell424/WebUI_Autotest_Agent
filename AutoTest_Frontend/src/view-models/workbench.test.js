import { describe, it, expect } from 'vitest'
import { buildExecutionOutput, resolveTagType } from './workbench.js'

const t = (key) => key

describe('workbench helpers', () => {
  it('resolves tag and output', () => {
    expect(resolveTagType('completed')).toBe('success')
    expect(resolveTagType('failed')).toBe('danger')
    const output = buildExecutionOutput({ logs: 'ok', error: 'boom' }, t)
    expect(output).toMatch(/\[STDERR\]/)
    expect(output).toMatch(/boom/)
  })
})
