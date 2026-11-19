import { test } from 'node:test'
import assert from 'node:assert/strict'
import { MAX_CAREER_GOALS, toggleGoal } from './careerGoals.js'

test('toggleGoal adds, removes and caps at the maximum', () => {
  assert.deepEqual(toggleGoal([], 'earn_more'), ['earn_more'])
  assert.deepEqual(toggleGoal(['earn_more'], 'earn_more'), [])
  const full = ['a', 'b', 'c']
  assert.equal(full.length, MAX_CAREER_GOALS)
  assert.deepEqual(toggleGoal(full, 'd'), full)
  assert.deepEqual(toggleGoal(undefined, 'a'), ['a'])
})
