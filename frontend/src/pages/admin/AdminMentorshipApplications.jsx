import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search } from 'lucide-react'
import { fetchApplications, fetchPrograms } from '../../api/mentorship'
import { fetchCountries } from '../../api/geography'
import { fetchTopics } from '../../api/taxonomies'
import { APPLICATION_STATUSES, CAREER_STAGES } from '../../constants/mentorship'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

const TITLES = {
  mentor: { title: 'Mentors', description: 'Mentor applications and approved mentor profiles.' },
  mentee: { title: 'Mentees', description: 'Mentee applications and approved mentee profiles.' },
  '': { title: 'Applications', description: 'All mentor and mentee applications across every program.' },
}

export default function AdminMentorshipApplications({ defaultRole = '' }) {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [programId, setProgramId] = useState('')
  const [country, setCountry] = useState('')
  const [careerStage, setCareerStage] = useState('')
  const [topic, setTopic] = useState('')
  const [unmatched, setUnmatched] = useState('')
  const [programs, setPrograms] = useState([])
  const [countries, setCountries] = useState([])
  const [topics, setTopics] = useState([])
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchPrograms({ pageSize: 100 }).then((res) => setPrograms(res.items)).catch(() => {})
    fetchCountries().then(setCountries).catch(() => {})
    fetchTopics().then(setTopics).catch(() => {})
  }, [])

  useEffect(() => {
    let active = true
    setError(null)
    fetchApplications({
      role: defaultRole || undefined, q: query, status, programId: programId || undefined,
      country, careerStage, topic, unmatched: unmatched || undefined, pageSize: 100,
    })
      .then((res) => active && setRows(res.items))
      .catch(() => active && setError('Something went wrong loading applications. Please try again.'))
    return () => {
      active = false
    }
  }, [defaultRole, query, status, programId, country, careerStage, topic, unmatched])

  const copy = TITLES[defaultRole] || TITLES['']

  return (
    <div>
      <AdminPageHeader title={copy.title} description={copy.description} />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search name, email, organization…" className="w-56 text-sm focus:outline-none" />
        </div>
        <select value={programId} onChange={(e) => setProgramId(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All programs</option>
          {programs.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {APPLICATION_STATUSES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select value={country} onChange={(e) => setCountry(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All countries</option>
          {countries.map((c) => (
            <option key={c.code} value={c.code}>{c.name}</option>
          ))}
        </select>
        <select value={careerStage} onChange={(e) => setCareerStage(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All career stages</option>
          {CAREER_STAGES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select value={topic} onChange={(e) => setTopic(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All topics</option>
          {topics.map((t) => (
            <option key={t.slug} value={t.slug}>{t.name}</option>
          ))}
        </select>
        {defaultRole === 'mentee' && (
          <select value={unmatched} onChange={(e) => setUnmatched(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
            <option value="">Matched: any</option>
            <option value="true">Unmatched only</option>
          </select>
        )}
      </div>

      {error && <EmptyState title="Couldn't load applications" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[960px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Applicant</th>
                  {!defaultRole && <th className="px-4 py-3">Role</th>}
                  <th className="px-4 py-3">Program</th>
                  <th className="px-4 py-3">Country</th>
                  <th className="px-4 py-3">Industry</th>
                  <th className="px-4 py-3">{defaultRole === 'mentor' ? 'Active mentees' : 'Career stage'}</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Submitted</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="px-4 py-3 font-medium text-charcoal">
                      <Link to={`/admin/mentorship/applications/${row.id}`} className="hover:text-burgundy-600">
                        {row.fullName}
                      </Link>
                    </td>
                    {!defaultRole && <td className="px-4 py-3 text-charcoal-600 capitalize">{row.role}</td>}
                    <td className="px-4 py-3 text-charcoal-600">{row.program?.name || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.country?.name || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.industry || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">
                      {row.role === 'mentor' ? `${row.activeMenteeCount}${row.mentorCapacity ? ` / ${row.mentorCapacity}` : ''}` : row.careerStage || '—'}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.submittedAt ? formatDate(row.submittedAt) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No applications match those filters" description="Try a different search term or clear your filters." />
        )
      )}
    </div>
  )
}
