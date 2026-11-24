import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

// Step 14: every newsletter signup form carries the same unticked consent
// checkbox, sends consent: true only when ticked, and promises confirmation.
const read = (p) => readFileSync(new URL(p, import.meta.url), 'utf8')
const consent = read('./NewsletterConsent.jsx')

test('consent checkbox: wording, Privacy link, unticked by default (controlled from false)', () => {
  assert.match(consent, /Yes, send me the WSF Weekly newsletter by email\. I can unsubscribe at any time\./)
  assert.match(consent, /<Link to="\/privacy"/)
  assert.match(consent, /type="checkbox" checked=\{checked\}/)
  assert.match(consent, /<label htmlFor=\{id\}>/)
})

for (const [file, path] of [
  ['NewsletterForm', '../ui/NewsletterForm.jsx'],
  ['NewsletterPopup', './NewsletterPopup.jsx'],
  ['NewsletterPage', '../../pages/NewsletterPage.jsx'],
]) {
  test(`${file}: unticked by default, blocks submit without it, sends consent: true`, () => {
    const src = read(path)
    assert.match(src, /const \[consent, setConsent\] = useState\(false\)/)
    assert.match(src, /if \(!consent\)/)
    assert.match(src, /consent: true/)
    assert.match(src, /<NewsletterConsent /)
    assert.doesNotMatch(src, /By subscribing, you agree to receive/)
  })
}

test('confirmation page posts the token and handles expired links', () => {
  const page = read('../../pages/NewsletterConfirmPage.jsx')
  assert.match(page, /confirmNewsletterSubscription\(token\)/)
  assert.match(page, /confirmation_expired/)
  assert.match(page, /robots: 'noindex, nofollow'/)
})

test('Studio never offers Reactivate or "Mark as sent"', () => {
  const detail = read('../../pages/admin/AdminSubscriberDetail.jsx')
  const editor = read('../../pages/admin/AdminNewsletterEditor.jsx')
  assert.doesNotMatch(detail, /Reactivate/)
  assert.match(detail, /Ask to confirm by email/)
  assert.doesNotMatch(editor, /Mark as sent/)
  assert.match(editor, /Record external send/)
  assert.match(editor, /WSF does not transmit newsletters itself/)
})
