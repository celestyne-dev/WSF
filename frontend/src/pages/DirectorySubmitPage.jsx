import { useEffect, useRef, useState } from 'react'
import { toast } from 'react-toastify'
import { submitDirectoryListing, fetchDirectoryCategories } from '../api/directory'
import {
  DIRECTORY_LISTING_TYPES,
  DIRECTORY_LISTING_TYPE_LABELS,
  DIRECTORY_OWNERSHIP_CLASSIFICATIONS,
  DIRECTORY_OWNERSHIP_LABELS,
  DIRECTORY_SERVICE_MODES,
  DIRECTORY_SERVICE_MODE_LABELS,
} from '../constants/directory'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import CountrySelect from '../components/ui/CountrySelect'

function blankForm() {
  return {
    businessName: '',
    website: '',
    listingType: 'business',
    ownershipClassification: 'unspecified',
    countryCode: '',
    location: '',
    description: '',
    keyServices: [''],
    serviceModes: [],
    categoryIds: [],
    publicContactEmail: '',
    publicContactPhone: '',
    submitterName: '',
    submitterEmail: '',
    submitterRole: '',
    hpWebsite: '',
  }
}

export default function DirectorySubmitPage() {
  const [form, setForm] = useState(blankForm())
  const [categories, setCategories] = useState([])
  const [status, setStatus] = useState('idle') // idle | submitting | success | error
  const [result, setResult] = useState(null)
  const startedAtRef = useRef(null)

  useSeo({
    title: 'Submit Your Business | Business & Professional Directory | Women Shaping Futures',
    description: 'Submit your women-owned, women-led, or women-founded business or professional organization to the WSF Business & Professional Directory.',
    canonical: 'https://womenshapingfutures.org/directory/submit',
  })

  useEffect(() => {
    startedAtRef.current = Date.now()
    fetchDirectoryCategories().then(setCategories).catch(() => {})
  }, [])

  function setField(key, value) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (status === 'submitting') return
    setStatus('submitting')
    const res = await submitDirectoryListing(
      { ...form, keyServices: form.keyServices.map((s) => s.trim()).filter(Boolean) },
      startedAtRef.current,
    )
    if (res.success) {
      setStatus('success')
      setResult(res)
      setForm(blankForm())
    } else {
      setStatus('error')
      toast.error(res.message)
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Directory"
        title="Submit Your Business"
        description="Tell us about your women-owned, women-led, or women-founded business or professional organization. Every submission is reviewed by WSF staff before anything is published — nothing goes live automatically."
      />
      <div className="container-editorial max-w-reading py-14">
        {status === 'success' && result ? (
          <div role="status" className="border border-emerald-200 bg-emerald-50 p-6">
            <p className="font-serif text-lg font-semibold text-charcoal">Submission received</p>
            <p className="mt-2 text-sm text-charcoal-600">{result.message}</p>
            <button type="button" onClick={() => setStatus('idle')} className="mt-4 text-sm font-semibold text-burgundy-600 hover:underline">
              Submit another business
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} noValidate className="space-y-8" aria-busy={status === 'submitting'}>
            {/* Honeypot — hidden from sighted users and screen readers. */}
            <div aria-hidden="true" className="absolute -left-[9999px] top-auto h-0 w-0 overflow-hidden">
              <label htmlFor="ds-hp">Leave this field empty</label>
              <input id="ds-hp" type="text" tabIndex={-1} autoComplete="off" value={form.hpWebsite} onChange={(e) => setField('hpWebsite', e.target.value)} />
            </div>

            <section className="space-y-4">
              <h2 className="font-serif text-xl font-semibold text-charcoal">About the business</h2>
              <div>
                <label htmlFor="ds-name" className="sr-only">Business name</label>
                <input id="ds-name" required placeholder="Business name" value={form.businessName} onChange={(e) => setField('businessName', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              </div>
              <div>
                <label htmlFor="ds-website" className="sr-only">Website</label>
                <input id="ds-website" type="url" placeholder="Website (optional)" value={form.website} onChange={(e) => setField('website', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="ds-type" className="sr-only">Listing type</label>
                  <select id="ds-type" value={form.listingType} onChange={(e) => setField('listingType', e.target.value)} className="w-full border border-taupe-300 bg-white px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none">
                    {DIRECTORY_LISTING_TYPES.map((t) => (
                      <option key={t} value={t}>{DIRECTORY_LISTING_TYPE_LABELS[t]}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="ds-classification" className="sr-only">Ownership classification</label>
                  <select id="ds-classification" value={form.ownershipClassification} onChange={(e) => setField('ownershipClassification', e.target.value)} className="w-full border border-taupe-300 bg-white px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none">
                    {DIRECTORY_OWNERSHIP_CLASSIFICATIONS.map((c) => (
                      <option key={c} value={c}>{DIRECTORY_OWNERSHIP_LABELS[c]}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <CountrySelect value={form.countryCode} onChange={(v) => setField('countryCode', v)} placeholder="Country (optional)" />
                <input placeholder="City / location (optional)" value={form.location} onChange={(e) => setField('location', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              </div>
              <div>
                <label htmlFor="ds-description" className="sr-only">Short description</label>
                <textarea id="ds-description" rows={4} maxLength={2000} placeholder="Briefly describe what the business does" value={form.description} onChange={(e) => setField('description', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              </div>
            </section>

            <section className="space-y-4">
              <h2 className="font-serif text-xl font-semibold text-charcoal">Services</h2>
              <div className="space-y-2">
                {form.keyServices.map((service, i) => (
                  <div key={i} className="flex gap-2">
                    <input
                      value={service}
                      maxLength={140}
                      placeholder={`Key service ${i + 1}`}
                      onChange={(e) => {
                        const next = [...form.keyServices]
                        next[i] = e.target.value
                        setField('keyServices', next)
                      }}
                      className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
                    />
                    {form.keyServices.length > 1 && (
                      <button type="button" onClick={() => setField('keyServices', form.keyServices.filter((_, idx) => idx !== i))} className="text-xs text-charcoal-600 hover:text-rose-600">
                        Remove
                      </button>
                    )}
                  </div>
                ))}
                {form.keyServices.length < 10 && (
                  <button type="button" onClick={() => setField('keyServices', [...form.keyServices, ''])} className="text-xs font-semibold text-burgundy-600 hover:underline">
                    + Add another service
                  </button>
                )}
              </div>

              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-charcoal-600">How do you serve customers?</p>
                <div className="flex flex-wrap gap-3">
                  {DIRECTORY_SERVICE_MODES.map((mode) => (
                    <label key={mode} className="flex items-center gap-1.5 text-sm text-charcoal-600">
                      <input
                        type="checkbox"
                        checked={form.serviceModes.includes(mode)}
                        onChange={(e) => {
                          const next = e.target.checked ? [...form.serviceModes, mode] : form.serviceModes.filter((m) => m !== mode)
                          setField('serviceModes', next)
                        }}
                      />
                      {DIRECTORY_SERVICE_MODE_LABELS[mode]}
                    </label>
                  ))}
                </div>
              </div>

              {categories.length > 0 && (
                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Categories</p>
                  <div className="flex flex-wrap gap-3">
                    {categories.map((cat) => (
                      <label key={cat.id} className="flex items-center gap-1.5 text-sm text-charcoal-600">
                        <input
                          type="checkbox"
                          checked={form.categoryIds.includes(cat.id)}
                          onChange={(e) => {
                            const next = e.target.checked ? [...form.categoryIds, cat.id] : form.categoryIds.filter((id) => id !== cat.id)
                            setField('categoryIds', next)
                          }}
                        />
                        {cat.name}
                      </label>
                    ))}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <input type="email" placeholder="Public contact email (optional — shown publicly)" value={form.publicContactEmail} onChange={(e) => setField('publicContactEmail', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
                <input placeholder="Public contact phone (optional — shown publicly)" value={form.publicContactPhone} onChange={(e) => setField('publicContactPhone', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              </div>
            </section>

            <section className="space-y-4">
              <h2 className="font-serif text-xl font-semibold text-charcoal">Your contact information</h2>
              <p className="text-xs text-charcoal-600/70">Kept private — used only so our team can follow up about this submission. Never published.</p>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <input required placeholder="Your name" value={form.submitterName} onChange={(e) => setField('submitterName', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
                <input required type="email" placeholder="Your email" value={form.submitterEmail} onChange={(e) => setField('submitterEmail', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              </div>
              <input placeholder="Your role at this business (optional)" value={form.submitterRole} onChange={(e) => setField('submitterRole', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            </section>

            <button type="submit" disabled={status === 'submitting'} className="btn-primary w-full disabled:opacity-60">
              {status === 'submitting' ? 'Submitting…' : 'Submit for review'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
