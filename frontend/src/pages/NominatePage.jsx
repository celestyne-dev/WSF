import { useState } from 'react'
import { toast } from 'react-toastify'
import { submitNomination } from '../api/site'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'

const CATEGORIES = ['Women to Watch', 'Women Doing Incredible Things', 'Founder Stories', 'Leadership Features', 'WSF Awards']

const initialForm = {
  nomineeName: '',
  country: '',
  profession: '',
  organization: '',
  achievements: '',
  urls: '',
  nominatorName: '',
  nominatorEmail: '',
  relationship: '',
  category: CATEGORIES[0],
  consent: false,
}

export default function NominatePage() {
  const [form, setForm] = useState(initialForm)
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  useSeo({
    title: 'Nominate a Woman | Women Shaping Futures',
    description: 'Nominate a woman for our Women to Watch, Women Doing Incredible Things, or Founder Stories features.',
    canonical: 'https://womenshapingfutures.org/nominate',
  })

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.consent) {
      toast.error('Please confirm you have permission to nominate this person.')
      return
    }
    setSubmitting(true)
    const result = await submitNomination(form)
    setSubmitting(false)
    if (result.success) {
      setSubmitted(true)
      toast.success(result.message)
    }
  }

  if (submitted) {
    return (
      <div className="container-editorial flex min-h-[50vh] flex-col items-center justify-center py-16 text-center">
        <p className="eyebrow">Nomination received</p>
        <h1 className="mt-2 font-serif text-3xl font-semibold text-charcoal">Thank you for the nomination</h1>
        <p className="mt-3 max-w-md text-charcoal-600">Our editorial team reviews every nomination for upcoming features.</p>
      </div>
    )
  }

  return (
    <div>
      <PageHeader eyebrow="Nominate" title="Nominate a Woman" description="Know a woman doing exceptional work? Nominate her for a feature, a series, or a future WSF Award." />
      <form onSubmit={handleSubmit} className="container-editorial max-w-2xl space-y-5 py-14">
        <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none">
          {CATEGORIES.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <h2 className="pt-2 font-serif text-lg font-semibold text-charcoal">About the nominee</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <input required placeholder="Nominee name" value={form.nomineeName} onChange={(e) => setForm({ ...form, nomineeName: e.target.value })} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          <input required placeholder="Country" value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          <input placeholder="Profession" value={form.profession} onChange={(e) => setForm({ ...form, profession: e.target.value })} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          <input placeholder="Organization" value={form.organization} onChange={(e) => setForm({ ...form, organization: e.target.value })} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
        </div>
        <textarea required placeholder="What has she achieved? Why should we feature her?" rows={5} value={form.achievements} onChange={(e) => setForm({ ...form, achievements: e.target.value })} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
        <input placeholder="Relevant links or social profiles" value={form.urls} onChange={(e) => setForm({ ...form, urls: e.target.value })} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />

        <h2 className="pt-2 font-serif text-lg font-semibold text-charcoal">About you</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <input required placeholder="Your name" value={form.nominatorName} onChange={(e) => setForm({ ...form, nominatorName: e.target.value })} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          <input required type="email" placeholder="Your email" value={form.nominatorEmail} onChange={(e) => setForm({ ...form, nominatorEmail: e.target.value })} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
        </div>
        <input placeholder="Your relationship to the nominee" value={form.relationship} onChange={(e) => setForm({ ...form, relationship: e.target.value })} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />

        <label className="flex items-start gap-2 text-sm text-charcoal-600">
          <input type="checkbox" checked={form.consent} onChange={(e) => setForm({ ...form, consent: e.target.checked })} className="mt-1" />
          I confirm the information provided is accurate to the best of my knowledge.
        </label>
        <button type="submit" disabled={submitting} className="btn-primary disabled:opacity-60">
          {submitting ? 'Submitting…' : 'Submit nomination'}
        </button>
      </form>
    </div>
  )
}
