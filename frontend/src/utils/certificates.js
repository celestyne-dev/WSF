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
