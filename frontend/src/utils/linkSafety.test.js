import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { isInternalPath, safeLinkUrl } from './linkSafety.js'

test('internal paths and http(s) URLs are allowed', () => {
  for (const url of ['/career-hub', '/topics/leadership?x=1#y', 'https://example.org/a', 'http://example.org', ' /resources ']) {
    assert.notEqual(safeLinkUrl(url), '', url)
  }
})

test('unsafe or private URLs are rejected', () => {
  for (const url of ['javascript:alert(1)', 'JAVASCRIPT:alert(1)', 'data:text/html,x', '//evil.example', '/admin', '/admin/articles', '/api/v1/x', '/a b', '/a\u0000b', 'mailto:a@b.c', '', null, 42]) {
    assert.equal(safeLinkUrl(url), '', String(url))
  }
})

test('mailto only when allowed (Simple CTA / Newsletter)', () => {
  assert.equal(safeLinkUrl('mailto:hello@example.org', { allowMailto: true }), 'mailto:hello@example.org')
})

test('isInternalPath', () => {
  assert.equal(isInternalPath('/x'), true)
  assert.equal(isInternalPath('//x'), false)
  assert.equal(isInternalPath('https://x'), false)
})

// The same cases the backend sanitizer (content_blocks.safe_link_url) is
// tested against, so React and the server prerender agree on every link.

const LINK_CASES = JSON.parse(readFileSync(new URL('../../../backend/tests/fixtures/link_url_cases.json', import.meta.url), 'utf8')).cases

test('shared link cases: Simple CTA allows safe mailto, rich CTA never does', () => {
  for (const c of LINK_CASES) {
    assert.equal(safeLinkUrl(c.url, { allowMailto: true }), c.simple, `simple ${JSON.stringify(c.url)}`)
    assert.equal(safeLinkUrl(c.url), c.rich, `rich ${JSON.stringify(c.url)}`)
  }
})
