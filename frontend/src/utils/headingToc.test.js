import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildArticleToc, buildHeadingToc, slugifyHeading } from './headingToc.js'

const h = (text, level = 2) => ({ type: 'heading', level, text })

test('slugs are stable and unique', () => {
  assert.equal(slugifyHeading('What’s next? A plan!'), 'whats-next-a-plan')
  assert.equal(slugifyHeading('  '), 'section')
  assert.deepEqual(buildHeadingToc([h('Overview'), { type: 'paragraph' }, h('Overview')]).map((x) => x.id), ['overview', 'overview-2'])
})

test('article TOC appears only from three H2/H3 headings; H4 never listed', () => {
  assert.deepEqual(buildArticleToc([h('One'), h('Two')]).entries, [])
  assert.deepEqual(buildArticleToc([h('One'), h('Two'), h('Deep', 4)]).entries, [])
  const toc = buildArticleToc([h('One'), { type: 'paragraph' }, h('Two', 3), h('Deep', 4), h('Three')])
  assert.deepEqual(toc.entries.map((e) => [e.id, e.level, e.index]), [['one', 2, 0], ['two', 3, 2], ['three', 2, 4]])
  // Every heading (H4 too) keeps an anchor id.
  assert.equal(toc.idByIndex.get(3), 'deep')
})

test('blank headings are skipped and bad input is safe', () => {
  assert.deepEqual(buildHeadingToc([h(''), null]).length, 0)
  assert.deepEqual(buildArticleToc(undefined).entries, [])
})
