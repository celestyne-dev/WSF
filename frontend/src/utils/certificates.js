// Display rules for WSF Certificates of Completion (pure, unit-tested).

export const CERTIFICATE_TERM = 'Certificate of Completion'

export function certificateStatusLabel(certificate) {
  if (!certificate) return null
  return certificate.status === 'revoked' ? 'Revoked' : 'Valid'
}

// The verify page's headline. A revoked certificate is shown plainly as
// revoked, never as valid, and never hidden (so a shared link stays honest).
export function verificationHeadline(certificate) {
  if (!certificate) return 'Certificate not found'
  return certificate.status === 'revoked' ? 'This certificate has been revoked.' : 'This certificate is valid.'
}

// My Learning row state: a certificate is offered only on a completed,
// active enrollment whose program issues WSF certificates.
export function enrollmentCertificateState(item) {
  if (!item || item.status !== 'active' || !item.completedAt || !item.certificateEnabled) return null
  if (item.certificate && item.certificate.status === 'active') return 'available'
  return null
}

export function joinInstructorNames(names) {
  const list = (names || []).filter(Boolean)
  if (list.length <= 1) return list[0] || ''
  return `${list.slice(0, -1).join(', ')} and ${list[list.length - 1]}`
}

// Step 20: how the learner's name appears on PUBLIC verification. The
// certificate itself (and its PDF) always keeps the full issued name.
export const CERTIFICATE_NAME_OPTIONS = [
  { value: 'full', label: 'Full name', example: (name) => name },
  { value: 'initials', label: 'Initials only', example: (name) => initialsOf(name) },
]

// Mirrors backend learning_certificates.initials_of (the server decides).
export function initialsOf(name) {
  const parts = String(name || '')
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => {
      const letters = word.split('-').filter(Boolean).map((p) => (p.match(/\p{L}/u) || [''])[0].toUpperCase()).filter(Boolean)
      return letters.length ? `${letters.join('-')}.` : ''
    })
    .filter(Boolean)
  return parts.join(' ') || '—'
}

// Shown before issuance (course page, next to Start course).
export const CERTIFICATE_NAME_NOTICE =
  'This course offers a Certificate of Completion in your account name. Anyone with its verification link sees your full name or only your initials — you choose in My Learning → My Certificates. It never shows your email.'
