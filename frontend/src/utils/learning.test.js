import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  currentModuleIndex,
  formatMinutes,
  lessonNeighbors,
  moduleProgress,
  nextIncompleteLesson,
  programMetaLines,
  progressText,
} from './learning.js'

const modules = [
  { id: 1, title: 'M1', lessons: [{ id: 11 }, { id: 12 }] },
  { id: 2, title: 'M2', lessons: [{ id: 21 }] },
  { id: 3, title: 'Empty', lessons: [] },
]

test('formatMinutes', () => {
  assert.equal(formatMinutes(0), '')
  assert.equal(formatMinutes(null), '')
  assert.equal(formatMinutes(25), '25 min')
  assert.equal(formatMinutes(60), '1 hr')
  assert.equal(formatMinutes(150), '2 hr 30 min')
})

test('meta lines use only real facts (text-only course, no video wording)', () => {
  const program = { deliveryMode: 'self_paced', difficultyLevel: 'intermediate', stats: { moduleCount: 5, lessonCount: 18, totalMinutes: 150, formatLabel: 'Text-based' } }
  assert.deepEqual(programMetaLines(program), [['Self-paced', 'Text-based', 'Intermediate'], ['5 modules', '18 lessons', 'Approx. 2 hr 30 min']])
  const bare = { deliveryMode: 'self_paced', stats: { moduleCount: 1, lessonCount: 1 } }
  assert.deepEqual(programMetaLines(bare), [['Self-paced'], ['1 module', '1 lesson']])
  const legacy = { deliveryMode: 'live_online', durationValue: 6, durationUnit: 'weeks', stats: {} }
  assert.deepEqual(programMetaLines(legacy), [['Live online'], ['6 weeks']])
})

test('neighbors cross module boundaries; unknown lesson is safe', () => {
  const n = lessonNeighbors(modules, 12)
  assert.equal(n.prev.lesson.id, 11)
  assert.equal(n.next.lesson.id, 21)
  assert.equal(n.position, 2)
  assert.equal(n.total, 3)
  assert.equal(lessonNeighbors(modules, '11').prev, null)
  assert.equal(lessonNeighbors(modules, 21).next, null)
  assert.equal(lessonNeighbors(modules, 999).current, null)
})

test('progress helpers derive from completed ids only', () => {
  assert.deepEqual(moduleProgress(modules[0], [11]), { completed: 1, total: 2, complete: false })
  assert.deepEqual(moduleProgress(modules[2], []), { completed: 0, total: 0, complete: false })
  assert.equal(nextIncompleteLesson(modules, [11]).lesson.id, 12)
  assert.equal(nextIncompleteLesson(modules, [11, 12, 21]), null)
  assert.equal(currentModuleIndex(modules, [11, 12]), 1)
  assert.equal(currentModuleIndex(modules, [11, 12, 21]), 2)
  assert.equal(progressText({ completedLessons: 6, totalLessons: 18 }), '6 of 18 lessons complete')
  assert.equal(progressText({ completedLessons: 0, totalLessons: 0 }), '')
  assert.equal(progressText(null), '')
})
