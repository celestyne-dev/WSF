// Run with: node --test src/utils/firstPaintSnapshot.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { captureFirstPaintSnapshot, firstPaintSnapshotFor, releaseFirstPaintSnapshot } from './firstPaintSnapshot.js'

function fakeDocument(main, url = { pathname: '/jobs/role', search: '' }) {
  return { defaultView: { location: url }, querySelector: (sel) => (sel === '#root > [data-wsf-prerender]' ? main : null) }
}
const main = { innerHTML: '<h1>Role</h1>', getAttribute: (n) => ({ 'data-wsf-prerender': 'job', class: 'container-editorial' })[n] }

test('captures the server prerender for the hard-loaded URL only', () => {
  captureFirstPaintSnapshot(fakeDocument(main))
  assert.deepEqual(firstPaintSnapshotFor('/jobs/role'), { url: '/jobs/role', kind: 'job', className: 'container-editorial', html: '<h1>Role</h1>' })
  assert.equal(firstPaintSnapshotFor('/jobs/role?page=2'), null)
  assert.equal(firstPaintSnapshotFor('/jobs'), null)
})

test('released after the first navigation; nothing captured without a prerender', () => {
  captureFirstPaintSnapshot(fakeDocument(main))
  releaseFirstPaintSnapshot()
  assert.equal(firstPaintSnapshotFor('/jobs/role'), null)
  assert.equal(captureFirstPaintSnapshot(fakeDocument(null)), null)
})
