import { test } from 'node:test'
import assert from 'node:assert/strict'
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
