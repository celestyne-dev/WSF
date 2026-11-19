// Run with: node --test src/utils/authorAuthority.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { authorFirstName, authorStatItems, hasItems } from './authorAuthority.js'

test('stats show only real, non-zero derived counts with correct plurals', () => {
  assert.deepEqual(authorStatItems({ articles: 24, resources: 6, courses: 3 }), [
    { value: 24, label: 'Articles' },
    { value: 6, label: 'Career Tools' },
    { value: 3, label: 'Courses' },
  ])
  assert.deepEqual(authorStatItems({ articles: 1, resources: 0, courses: 1 }), [
    { value: 1, label: 'Article' },
    { value: 1, label: 'Course' },
  ])
  assert.deepEqual(authorStatItems(null), [])
})

test('first name and empty-section guards', () => {
  assert.equal(authorFirstName('Celestine Nyamoita'), 'Celestine')
  assert.equal(authorFirstName('  '), '')
  assert.equal(hasItems([]), false)
  assert.equal(hasItems([{}]), true)
  assert.equal(hasItems(undefined), false)
})
