// Run with: node --test src/utils/bootstrap.test.js
import { test, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { consumeBootstrap, readBootstrap } from './bootstrap.js'

// Minimal stand-in for the one DOM call bootstrap.js makes.
let tags
beforeEach(() => {
  tags = {}
  globalThis.document = {
    querySelector(selector) {
      const type = /data-wsf-bootstrap="([^"]+)"/.exec(selector)?.[1]
      const text = tags[type]
      return text === undefined ? null : { textContent: text, remove: () => delete tags[type] }
    },
  }
})

test('author bootstrap is used only for the matching slug', () => {
  tags.author = JSON.stringify({ key: 'celestine', data: { author: { slug: 'celestine' } } })
  assert.equal(readBootstrap('author', 'celestine').data.author.slug, 'celestine')
  // A client-side navigation to another Author must fetch, never reuse it.
  assert.equal(readBootstrap('author', 'someone-else'), null)
  // Other route types never see it.
  assert.equal(readBootstrap('person', 'celestine'), null)
})

test('consumed or malformed bootstrap falls back to fetching', () => {
  tags.author = JSON.stringify({ key: 'celestine', data: {} })
  consumeBootstrap('author')
  assert.equal(readBootstrap('author', 'celestine'), null)
  tags.author = '{not json'
  assert.equal(readBootstrap('author', 'celestine'), null)
  consumeBootstrap('author')
  consumeBootstrap('author') // removing twice is a no-op
})
