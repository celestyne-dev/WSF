import { test } from 'node:test'
import assert from 'node:assert/strict'
import { describeVideoLink, isAllowedEmbedUrl, isVideoLesson, videoLinkHint, videoProviderLabel } from './videoEmbed.js'

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

test('describeVideoLink previews server detection', () => {
  assert.equal(describeVideoLink('https://www.youtube.com/watch?v=abc').provider, 'youtube')
  assert.equal(describeVideoLink('https://youtu.be/abc').state, 'embed')
  assert.equal(describeVideoLink('https://acme.wistia.com/medias/x').provider, 'wistia')
  assert.equal(describeVideoLink('https://vimeo.com.evil.com/1').state, 'link')
  assert.equal(describeVideoLink('https://example.com/talk.mp4').state, 'link')
  assert.equal(describeVideoLink('<iframe src="https://player.vimeo.com/video/1"></iframe>').state, 'embed_code')
  assert.equal(describeVideoLink('javascript:alert(1)').state, 'invalid')
  assert.equal(describeVideoLink('  ').state, 'empty')
  assert.equal(videoLinkHint(''), null)
  assert.equal(videoLinkHint('https://example.com/a').tone, 'info')
  assert.equal(videoLinkHint('<iframe>').tone, 'error')
})
