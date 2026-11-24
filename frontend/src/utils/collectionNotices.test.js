import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { COLLECTION_NOTICES, NEWSLETTER_CONFIRM_NOTE, collectionNotice } from './collectionNotices.js'

const read = (p) => readFileSync(new URL(p, import.meta.url), 'utf8')

test('every notice states a purpose; newsletter opt-in forms mention the confirmation email', () => {
  for (const [kind, notice] of Object.entries(COLLECTION_NOTICES)) {
    assert.ok(notice.purpose.endsWith('.'), kind)
    const { text } = collectionNotice(kind)
    assert.equal(text.includes(NEWSLETTER_CONFIRM_NOTE), Boolean(notice.newsletterNote), kind)
  }
  assert.throws(() => collectionNotice('nope'))
})

test('the notice always links the Privacy Policy, and the Terms where set', () => {
  const src = read('../components/legal/CollectionNotice.jsx')
  assert.match(src, /to="\/privacy"/)
  assert.match(src, /terms && .*to="\/terms"/s)
  assert.equal(collectionNotice('story').terms, true)
  assert.equal(collectionNotice('eventRegistration').terms, false)
})

test('the notices sit on the real forms', () => {
  const placements = {
    '../pages/SubmitStoryPage.jsx': ['story'],
    '../pages/EventDetailPage.jsx': ['eventRegistration'],
    '../pages/LearningProgramDetailPage.jsx': ['learningEnrolment'],
    '../pages/NominatePage.jsx': ['nomination'],
    '../pages/MentorshipPage.jsx': ['mentorship'],
    '../pages/CommunityPage.jsx': ['community'],
    '../pages/ResourceDetailPage.jsx': ['resourceDownload'],
    '../pages/DirectorySubmitPage.jsx': ['directory'],
    '../pages/PartnershipsPage.jsx': ['partnership'],
    '../pages/AdvertisePage.jsx': ['advertise'],
  }
  for (const [file, kinds] of Object.entries(placements)) {
    const src = read(file)
    for (const kind of kinds) assert.ok(src.includes(`<CollectionNotice kind="${kind}"`), `${file} ${kind}`)
  }
})

test('existing approved notices are preserved', () => {
  assert.match(read('../components/comments/CommentsSection.jsx'), /By commenting you agree to our/)
  const register = read('../pages/RegisterPage.jsx')
  assert.match(register, /By creating an account, you agree to our/)
  assert.match(register, /to="\/terms"/)
  assert.match(register, /to="\/privacy"/)
  assert.match(read('../pages/ContactPage.jsx'), /to="\/privacy"/)
  assert.match(read('../components/newsletter/NewsletterConsent.jsx'), /to="\/privacy"/)
})
