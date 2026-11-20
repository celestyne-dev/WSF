import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Award, CheckCircle2 } from 'lucide-react'
import { downloadCertificatePdf } from '../../api/certificates'
import { formatDate } from '../../utils/format'
import { trackEvent } from '../../utils/analytics'

// Shown once the learner's own enrollment is complete. Certificate
// actions appear only when the backend actually issued one (certificate-
// enabled, WSF-owned course, all completion rules met). The wording is
// always "Certificate of Completion" — never an accreditation claim.
export default function CourseCompletion({ program, enrollment }) {
  const [downloading, setDownloading] = useState(false)
  if (!enrollment?.completedAt) return null
  const certificate = enrollment.certificate?.status === 'active' ? enrollment.certificate : null

  async function download() {
    setDownloading(true)
    try {
      await downloadCertificatePdf(certificate)
      trackEvent('certificate_downloaded', { certificateNumber: certificate.certificateNumber })
    } catch {
      toast.error('We couldn’t download your certificate. Please try again.')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <section aria-labelledby="course-completed-title" className="rounded-card border border-emerald-600/40 bg-emerald-50 p-6 sm:p-7">
      <p id="course-completed-title" className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-emerald-800">
        <CheckCircle2 size={16} aria-hidden="true" /> Course completed
      </p>
      <p className="mt-2 font-serif text-2xl font-semibold text-charcoal">{program.title}</p>
      <p className="mt-1 text-sm text-charcoal-600">Completed {formatDate(enrollment.completedAt)}</p>
      {certificate ? (
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button type="button" onClick={download} disabled={downloading} className="btn-primary !py-2.5 disabled:opacity-60">
            <Award size={16} aria-hidden="true" /> {downloading ? 'Preparing…' : 'Download certificate'}
          </button>
          <Link to={`/certificates/verify/${certificate.publicId}`} className="btn-secondary !py-2.5">
            Verify credential
          </Link>
          {certificate.linkedinUrl && (
            <a
              href={certificate.linkedinUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackEvent('certificate_linkedin_clicked', { certificateNumber: certificate.certificateNumber })}
              className="text-sm font-semibold text-burgundy-600 hover:underline"
            >
              Add to LinkedIn
            </a>
          )}
        </div>
      ) : (
        program.certificateAvailable && (
          <p className="mt-3 text-sm text-charcoal-600">Your Certificate of Completion will appear in My Learning once it&apos;s issued.</p>
        )
      )}
    </section>
  )
}
