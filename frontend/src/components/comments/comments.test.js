import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

// Source-level guarantees for the comment UI (behaviour is covered by the
// backend tests and the Chromium flow; these catch regressions in markup).
const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const section = read('./CommentsSection.jsx')
const dialog = read('./CommentDialog.jsx')
const studio = read('../../pages/admin/AdminComments.jsx')
const article = read('../../pages/ArticlePage.jsx')

test('notice links Community Guidelines to Terms and the Privacy Policy', () => {
  assert.match(section, /By commenting you agree to our/)
  assert.match(section, /<Link to="\/terms"[^>]*>Community Guidelines<\/Link>/)
  assert.match(section, /<Link to="\/privacy"[^>]*>Privacy Policy<\/Link>/)
})

test('logged-out readers get a sign-in prompt that returns to the comments', () => {
  assert.match(section, /to="\/login" state=\{\{ from: `\$\{location.pathname\}#comments` \}\}/)
  assert.match(section, /to join the conversation/)
})

test('honeypot is hidden from assistive technology and keyboard, not only visually', () => {
  assert.match(section, /<div aria-hidden="true"[^>]*>\s*<label htmlFor=\{`\$\{id\}-website`\}/)
  assert.match(section, /name="website" type="text" tabIndex=\{-1\} autoComplete="off"/)
})

test('form fields are labelled and errors announced', () => {
  assert.match(section, /<label htmlFor=\{`\$\{id\}-body`\}/)
  assert.match(section, /role="alert"/)
  assert.match(section, /role="status" aria-live="polite"/)
})

test('pending, edited and closed states are shown as text', () => {
  assert.match(section, /Awaiting approval — only you can see this/)
  assert.match(section, / · edited/)
  assert.match(section, /closedMessage\(data\.state\)/)
  assert.match(section, /restrictionMessage\(restriction\)/)
})

test('delete and report use the modal dialog; report offers the four reasons', () => {
  assert.match(section, /title="Delete this comment\?"/)
  assert.match(section, /title="Report this comment"/)
  assert.match(section, /REPORT_REASONS\.map/)
  assert.match(dialog, /showModal\(\)/)
  assert.match(dialog, /aria-labelledby=\{titleId\}/)
  assert.match(dialog, /target\.focus\(\)/) // focus returns to the opener
})

test('reply control says whom it replies to and exposes its state', () => {
  assert.match(section, /Reply<span className="sr-only"> to \{comment\.author\?\.name\}<\/span>/)
  assert.match(section, /aria-expanded=\{replyingTo === replyTargetId\(comment\)\}/)
})

test('comments are lazy-loaded below the article (not in its first paint)', () => {
  assert.match(article, /const CommentsSection = lazy\(\(\) => import\('\.\.\/components\/comments\/CommentsSection'\)\)/)
  assert.match(article, /<Suspense fallback=\{null\}>\s*<CommentsSection slug=\{article\.slug\} \/>/)
})

test('moderation queue: tabs, actions, reasons and restrictions', () => {
  assert.match(studio, /role="group" aria-label="Queue"/)
  assert.match(studio, /aria-pressed=\{queue === q\.value\}/)
  for (const label of ['Approve', 'Restore', 'Hide', 'Remove', 'Suspend from comments', 'Ban from comments', 'Lift restriction']) {
    assert.ok(studio.includes(label), label)
  }
  assert.match(studio, /A reason is required to remove a comment\./)
  assert.match(studio, /Restrictions only affect comments\. The account itself stays active/)
})

test('no third-party comment or CAPTCHA services', () => {
  for (const src of [section, studio]) {
    assert.doesNotMatch(src, /disqus|facebook|recaptcha|hcaptcha|turnstile/i)
  }
})
