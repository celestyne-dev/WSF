import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  REPORT_REASONS, canEditNow, closedMessage, commentCountLabel, editMinutesLeft, postResultMessage, replyTargetId,
  restrictionMessage, HISTORY_LABELS, MODERATION_QUEUES,
} from './comments.js'

test('reply always targets the top-level comment (one reply level)', () => {
  assert.equal(replyTargetId({ id: 5, parentId: null }), 5)
  assert.equal(replyTargetId({ id: 9, parentId: 5 }), 5)
})

test('edit window follows the server-provided editableUntil', () => {
  const now = Date.parse('2026-11-24T12:00:00Z')
  assert.equal(canEditNow({ editableUntil: '2026-11-24T12:10:00Z' }, now), true)
  assert.equal(editMinutesLeft({ editableUntil: '2026-11-24T12:10:00Z' }, now), 10)
  assert.equal(canEditNow({ editableUntil: '2026-11-24T11:59:00Z' }, now), false)
  assert.equal(canEditNow({ editableUntil: null }, now), false)
  assert.equal(editMinutesLeft({ editableUntil: null }, now), 0)
})

test('closed / off / disabled messages', () => {
  assert.match(closedMessage('off'), /turned off/)
  assert.match(closedMessage('closed'), /closed/)
  assert.match(closedMessage('disabled'), /unavailable/)
  assert.equal(closedMessage('open'), null)
})

test('suspension and ban messages are text, not colour', () => {
  assert.equal(restrictionMessage(null), null)
  assert.match(restrictionMessage({ kind: 'ban' }), /can no longer take part/)
  assert.match(restrictionMessage({ kind: 'suspension', endsAt: '2026-12-01T10:00:00Z' }), /suspended until 1 December 2026/)
})

test('pending vs published feedback', () => {
  assert.match(postResultMessage('pending'), /once a moderator approves it/)
  assert.match(postResultMessage('published'), /published/)
})

test('report reasons are exactly the four required', () => {
  assert.deepEqual(REPORT_REASONS.map((r) => r.value), ['spam', 'harassment', 'misinformation', 'other'])
})

test('counts, queues and history labels', () => {
  assert.equal(commentCountLabel(0), 'Comments')
  assert.equal(commentCountLabel(1), '1 comment')
  assert.equal(commentCountLabel(4), '4 comments')
  assert.deepEqual(MODERATION_QUEUES.map((q) => q.value).slice(0, 3), ['pending', 'reported', 'hidden'])
  for (const action of ['created', 'edited', 'deleted_by_author', 'reported', 'approved', 'hidden', 'auto_hidden',
    'removed', 'restored', 'user_suspended', 'user_banned', 'user_restriction_lifted']) {
    assert.ok(HISTORY_LABELS[action], action)
  }
})
