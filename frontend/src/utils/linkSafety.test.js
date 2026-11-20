import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { isInternalPath, normalizeEditorLink, safeLinkUrl } from './linkSafety.js'

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



test('editor link entry: normalizes friendly input, refuses unsafe links with a reason', () => {
  assert.deepEqual(normalizeEditorLink(' /resources/salary-guide '), { url: '/resources/salary-guide' })
  assert.deepEqual(normalizeEditorLink('https://example.org/report'), { url: 'https://example.org/report' })
  assert.deepEqual(normalizeEditorLink('www.example.org/x'), { url: 'https://www.example.org/x' })
  assert.deepEqual(normalizeEditorLink('example.org'), { url: 'https://example.org' })
  assert.deepEqual(normalizeEditorLink('hello@example.org'), { url: 'mailto:hello@example.org' })
  for (const bad of ['javascript:alert(1)', 'data:text/html,x', '//evil.example', '/admin', '', 'not a link']) {
    assert.ok(normalizeEditorLink(bad).error, bad)
  }
})
