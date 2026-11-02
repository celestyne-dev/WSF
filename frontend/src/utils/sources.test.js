// Plain-Node tests for the source form helpers' quick client-side checks
// (backend schemas/sources.py stays authoritative).
// Run with: node --test src/utils/sources.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { isPublicSourceHost, validateSources } from './sources.js'

const REJECTED = [
  'https://localhost/source',
  'http://localhost:8000/x',
  'https://foo.localhost/x',
  'https://intranet/report',
  'https://127.0.0.1/source',
  'https://192.168.1.20/report',
  'https://[::1]/source',
]
const ACCEPTED = [
  'https://example.com/report',
  'https://news.example.org/story',
  'https://www.ilo.org/report',
  'https://sub.domain.co.ke/source',
  'http://example.com:8080/x?y=1',
]

test('non-public hosts are rejected before saving', () => {
  for (const url of REJECTED) {
    assert.equal(isPublicSourceHost(url), false, url)
    assert.match(validateSources([{ title: 'T', url }]), /public domain name/, url)
  }
})

test('normal public domains are accepted', () => {
  for (const url of ACCEPTED) {
    assert.equal(isPublicSourceHost(url), true, url)
    assert.equal(validateSources([{ title: 'T', url }]), null, url)
  }
})

test('existing checks are unchanged', () => {
  assert.match(validateSources([{ title: '', url: 'https://example.com' }]), /needs a title/)
  assert.match(validateSources([{ title: 'T', url: 'javascript:alert(1)' }]), /http:\/\/ or https:\/\//)
  assert.match(validateSources([{ title: 'A', url: 'https://example.com/r' }, { title: 'B', url: ' https://example.com/r ' }]), /repeats a URL/)
})
