import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { BadgeCheck, XCircle } from 'lucide-react'
import { verifyCertificate } from '../api/certificates'
import { trackEvent } from '../utils/analytics'
import { formatDate } from '../utils/format'
import { joinInstructorNames, verificationHeadline } from '../utils/certificates'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'

// Public verification of a WSF Certificate of Completion. Shows only the
// snapshot facts the backend's public payload carries (no email or ids).
// noindex and never in the sitemap: shareable by link, not discoverable.
export default function CertificateVerifyPage() {
  const { publicId } = useParams()
  const [certificate, setCertificate] = useState(undefined)

  useSeo({ title: 'Verify a Certificate | Women Shaping Futures', robots: 'noindex, nofollow' })

  useEffect(() => {
    let active = true
    verifyCertificate(publicId)
      .then((c) => {
        if (!active) return
        setCertificate(c)
        trackEvent('certificate_verified', { status: c?.status })
      })
      .catch(() => active && setCertificate(null))
    return () => {
      active = false
    }
  }, [publicId])

  const revoked = certificate?.status === 'revoked'

  return (
    <div>
      <PageHeader eyebrow="WSF Learning" title="Certificate verification" />
      <div className="container-editorial max-w-xl py-14">
        {certificate === undefined && <p className="text-center text-charcoal-600">Checking this certificate…</p>}
        {certificate === null && (
          <div className="text-center">
            <XCircle size={40} className="mx-auto text-rose-500" />
            <p className="mt-4 text-lg font-semibold text-charcoal">We couldn’t find a certificate with this link.</p>
            <p className="mt-2 text-sm text-charcoal-600">Check that the full verification link was copied.</p>
          </div>
        )}
        {certificate && (
          <div className="border border-taupe-200 bg-white p-6 sm:p-8">
            <div className={`flex items-center gap-3 ${revoked ? 'text-rose-600' : 'text-emerald-700'}`}>
              {revoked ? <XCircle size={28} /> : <BadgeCheck size={28} />}
              <p className="text-lg font-semibold">{verificationHeadline(certificate)}</p>
            </div>
            <dl className="mt-6 space-y-4 text-sm">
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">Credential</dt>
                <dd className="mt-1 font-serif text-xl font-semibold text-charcoal">{certificate.certificateTitle}</dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">Awarded to</dt>
                <dd className="mt-1 text-charcoal">{certificate.recipientName}</dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">Program</dt>
                <dd className="mt-1 text-charcoal">{certificate.programTitle}</dd>
              </div>
              {certificate.instructorNames.length > 0 && (
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">Instructor</dt>
                  <dd className="mt-1 text-charcoal">{joinInstructorNames(certificate.instructorNames)}</dd>
                </div>
              )}
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">Issued by</dt>
                <dd className="mt-1 text-charcoal">{certificate.issuerName}</dd>
              </div>
              {certificate.completedAt && (
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">Completed</dt>
                  <dd className="mt-1 text-charcoal">{formatDate(certificate.completedAt)}</dd>
                </div>
              )}
              {revoked && certificate.revokedAt && (
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">Revoked</dt>
                  <dd className="mt-1 text-charcoal">{formatDate(certificate.revokedAt)}</dd>
                </div>
              )}
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">Certificate number</dt>
                <dd className="mt-1 font-mono text-charcoal">{certificate.certificateNumber}</dd>
              </div>
            </dl>
            <p className="mt-8 text-xs text-charcoal-600">
              Women Shaping Futures issues Certificates of Completion for its own learning programs.{' '}
              <Link to="/learning" className="font-semibold text-burgundy-600 hover:underline">
                Explore WSF Learning
              </Link>
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
