import test from 'node:test'
import assert from 'node:assert/strict'

import { buildExecutionOutput, resolveTagType } from './workbench.js'

const t = (key) => key

test('workbench helper resolves tag and output', () => {
  assert.equal(resolveTagType('completed'), 'success')
  assert.equal(resolveTagType('failed'), 'danger')
  const output = buildExecutionOutput({ logs: 'ok', error: 'boom' }, t)
  assert.match(output, /\[STDERR\]/)
  assert.match(output, /boom/)
})
