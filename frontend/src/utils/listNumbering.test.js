// Run with: node --test src/utils/listNumbering.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolveListStarts } from './listNumbering.js'

// Same cases the Python prerender rule is tested against.
const { cases } = JSON.parse(readFileSync(new URL('../../../backend/tests/fixtures/list_numbering_cases.json', import.meta.url), 'utf8'))

for (const c of cases) {
  test(c.name, () => {
    assert.deepEqual(resolveListStarts(c.blocks), c.expected)
  })
}

const num = (items, extra = {}) => ({ type: 'list', style: 'number', items, ...extra })

test('lengthening an earlier list renumbers a later Continue list', () => {
  const blocks = [num(['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']), { type: 'paragraph', text: 'p' }, num(['a'], { numberingMode: 'continue' })]
  assert.equal(resolveListStarts(blocks)[2], 11)
  blocks[0] = num([...blocks[0].items, '11', '12'])
  assert.equal(resolveListStarts(blocks)[2], 13)
})

test('moving blocks recalculates', () => {
  const a = num(['a', 'b', 'c'])
  const b = num(['d', 'e'], { numberingMode: 'continue' })
  const c = num(['f'], { numberingMode: 'continue' })
  assert.deepEqual(resolveListStarts([a, b, c]), [1, 4, 6])
  assert.deepEqual(resolveListStarts([b, a, c]), [1, 1, 4])
  assert.deepEqual(resolveListStarts([a, c, b]), [1, 4, 5])
})

test('tolerates missing input', () => {
  assert.deepEqual(resolveListStarts(null), [])
  assert.deepEqual(resolveListStarts([null, { type: 'list', style: 'number' }]), [null, null])
})
