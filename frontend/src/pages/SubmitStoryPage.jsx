import { useState } from 'react'
import { toast } from 'react-toastify'
import { submitStory } from '../api/site'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'

const initialForm = { name: '', email: '', title: '', body: '', links: '', consent: false, terms: false }

export default function SubmitStoryPage() {
  const [form, setForm] = useState(initialForm)
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  useSeo({
    title: 'Submit a Story | Women Shaping Futures',
    description: 'Share your personal, career, or founder story with Women Shaping Futures.',
    canonical: 'https://womenshapingfutures.org/submit',
  })

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.consent || !form.terms) {
      toast.error('Please confirm consent and terms before submitting.')
      return
    }
    setSubmitting(true)
    const result = await submitStory(form)
    setSubmitting(false)
    if (result.success) {
      setSubmitted(true)
      toast.success(result.message)
    }
  }

  if (submitted) {
    return (
      <div className="container-editorial flex min-h-[50vh] flex-col items-center justify-center py-16 text-center">
        <p className="eyebrow">Thank you</p>
        <h1 className="mt-2 font-serif text-3xl font-semibold text-charcoal">Your story is in our queue</h1>
        <p className="mt-3 max-w-md text-charcoal-600">Our editorial team reviews every submission. If yours is selected, we'll reach out at the email you provided.</p>
      </div>
    )
  }

  return (
    <div>
      <PageHeader eyebrow="Submit" title="Submit Your Story" description="Personal stories, founder journeys, career pivots, essays, and opinion pieces — tell us what happened." />
      <form onSubmit={handleSubmit} className="container-editorial max-w-2xl space-y-5 py-14">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <input required placeholder="Your name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          <input required type="email" placeholder="Your email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
        </div>
        <input required placeholder="Story title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
        <textarea required placeholder="Tell your story (500-1500 words)" rows={10} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
        <input placeholder="Relevant links (LinkedIn, website, press)" value={form.links} onChange={(e) => setForm({ ...form, links: e.target.value })} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-charcoal-600">Photo (optional)</label>
          <input type="file" accept="image/*" className="mt-1.5 w-full text-sm text-charcoal-600" />
        </div>
        <label className="flex items-start gap-2 text-sm text-charcoal-600">
          <input type="checkbox" checked={form.consent} onChange={(e) => setForm({ ...form, consent: e.target.checked })} className="mt-1" />
          I consent to Women Shaping Futures editing and publishing my story if selected.
        </label>
        <label className="flex items-start gap-2 text-sm text-charcoal-600">
          <input type="checkbox" checked={form.terms} onChange={(e) => setForm({ ...form, terms: e.target.checked })} className="mt-1" />
          I confirm this story is my own and accept the submission terms.
        </label>
        <button type="submit" disabled={submitting} className="btn-primary disabled:opacity-60">
          {submitting ? 'Submitting…' : 'Submit story'}
        </button>
      </form>
    </div>
  )
}
