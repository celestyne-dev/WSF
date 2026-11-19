import { apiClient } from './client'

// WSF Learning Certificates of Completion. Certificates are issued only by
// the backend completion flow (never from the browser); these calls read,
// download, verify and (staff) revoke/reissue them. Real-backend only.
export function mapCertificate(c) {
  if (!c) return null
  return {
    id: c.id ?? null,
    publicId: c.publicId,
    certificateNumber: c.certificateNumber,
    status: c.status,
    certificateTitle: c.certificateTitle,
    recipientName: c.recipientName,
    programTitle: c.programTitle,
    programSlug: c.programSlug ?? null,
    instructorNames: Array.isArray(c.instructorNames) ? c.instructorNames : [],
    issuerName: c.issuerName,
    completedAt: c.completedAt ?? null,
    issuedAt: c.issuedAt ?? null,
    revokedAt: c.revokedAt ?? null,
    verificationUrl: c.verificationUrl ?? null,
    linkedinUrl: c.linkedinUrl ?? null,
    learnerEmail: c.learnerEmail ?? null,
    learningProgramId: c.learningProgramId ?? null,
    revocationReason: c.revocationReason ?? null,
    replacesCertificateId: c.replacesCertificateId ?? null,
  }
}

export async function verifyCertificate(publicId) {
  const { data } = await apiClient.get(`/certificates/verify/${encodeURIComponent(publicId)}`)
  return mapCertificate(data)
}

export async function fetchMyCertificates() {
  const { data } = await apiClient.get('/certificates/me')
  return (Array.isArray(data) ? data : data?.items || []).map(mapCertificate)
}

// Authenticated blob download, so the bearer token is sent and the PDF
// URL is never a public, token-bearing link.
export async function downloadCertificatePdf(certificate) {
  const response = await apiClient.get(`/certificates/${encodeURIComponent(certificate.publicId)}/pdf`, { responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }))
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', `${certificate.certificateNumber || 'wsf-certificate'}.pdf`)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

// --- Admin (learning.manage) --------------------------------------------

// params: { q, status, programId, page, perPage }
export async function fetchAdminCertificates(params = {}) {
  const { data } = await apiClient.get('/certificates/admin', {
    params: { q: params.q || undefined, status: params.status || undefined, programId: params.programId || undefined, page: params.page, perPage: params.perPage },
  })
  return { items: (data.items || []).map(mapCertificate), pagination: data.pagination }
}

export async function revokeCertificate(id, reason) {
  const { data } = await apiClient.post(`/certificates/admin/${id}/revoke`, { reason })
  return mapCertificate(data)
}

export async function reissueCertificate(id, reason) {
  const { data } = await apiClient.post(`/certificates/admin/${id}/reissue`, { reason })
  return mapCertificate(data)
}
