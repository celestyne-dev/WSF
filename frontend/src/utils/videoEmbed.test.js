import { test } from 'node:test'
import assert from 'node:assert/strict'
import { isAllowedEmbedUrl, isVideoLesson, videoProviderLabel } from './videoEmbed.js'

test('only https player hosts may be embedded', () => {
  assert.equal(isAllowedEmbedUrl('https://www.youtube-nocookie.com/embed/abc'), true)
  assert.equal(isAllowedEmbedUrl('https://player.vimeo.com/video/123'), true)
  assert.equal(isAllowedEmbedUrl('https://fast.wistia.net/embed/iframe/abc'), true)
  assert.equal(isAllowedEmbedUrl('https://www.loom.com/embed/abc'), true)
  assert.equal(isAllowedEmbedUrl('http://player.vimeo.com/video/123'), false)
  assert.equal(isAllowedEmbedUrl('https://player.vimeo.com.evil.com/video/1'), false)
  assert.equal(isAllowedEmbedUrl('https://www.youtube.com/watch?v=abc'), false)
  assert.equal(isAllowedEmbedUrl('javascript:alert(1)'), false)
  assert.equal(isAllowedEmbedUrl(null), false)
})

test('video lesson helpers', () => {
  assert.equal(isVideoLesson({ lessonType: 'recording' }), true)
  assert.equal(isVideoLesson({ lessonType: 'text' }), false)
  assert.equal(videoProviderLabel('youtube'), 'YouTube')
  assert.equal(videoProviderLabel('other'), 'Other')
  assert.equal(videoProviderLabel('nope'), null)
})
