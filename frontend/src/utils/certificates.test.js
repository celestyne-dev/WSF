import { test } from 'node:test'
import assert from 'node:assert/strict'
import { certificateStatusLabel, enrollmentCertificateState, joinInstructorNames, verificationHeadline } from './certificates.js'

test('verification headline is honest about revocation', () => {
  assert.equal(verificationHeadline({ status: 'active' }), 'This certificate is valid.')
  assert.equal(verificationHeadline({ status: 'revoked' }), 'This certificate has been revoked.')
  assert.equal(verificationHeadline(null), 'Certificate not found')
  assert.equal(certificateStatusLabel({ status: 'revoked' }), 'Revoked')
  assert.equal(certificateStatusLabel({ status: 'active' }), 'Valid')
})

test('certificate offered only for completed, active, certificate-enabled enrollments', () => {
  const base = { status: 'active', completedAt: '2026-11-01', certificateEnabled: true, certificate: { status: 'active' } }
  assert.equal(enrollmentCertificateState(base), 'available')
  assert.equal(enrollmentCertificateState({ ...base, completedAt: null }), null)
  assert.equal(enrollmentCertificateState({ ...base, certificateEnabled: false }), null)
  assert.equal(enrollmentCertificateState({ ...base, status: 'withdrawn' }), null)
  assert.equal(enrollmentCertificateState({ ...base, certificate: null }), null)
  assert.equal(enrollmentCertificateState({ ...base, certificate: { status: 'revoked' } }), null)
})

test('instructor names read naturally', () => {
  assert.equal(joinInstructorNames([]), '')
  assert.equal(joinInstructorNames(['A']), 'A')
  assert.equal(joinInstructorNames(['A', 'B', 'C']), 'A, B and C')
})

test('initials mirror the backend rule', async () => {
  const { initialsOf, CERTIFICATE_NAME_OPTIONS, CERTIFICATE_NAME_NOTICE } = await import('./certificates.js')
  assert.equal(initialsOf('Amara Okafor'), 'A. O.')
  assert.equal(initialsOf('Ada King-Lovelace'), 'A. K-L.')
  assert.equal(initialsOf('  zoë  '), 'Z.')
  assert.equal(initialsOf("O'Brien"), 'O.')
  assert.equal(initialsOf(''), '—')
  assert.deepEqual(CERTIFICATE_NAME_OPTIONS.map((o) => o.value), ['full', 'initials'])
  assert.match(CERTIFICATE_NAME_NOTICE, /never shows your email/)
})
