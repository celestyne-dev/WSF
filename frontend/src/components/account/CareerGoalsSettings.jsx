import { useEffect, useState } from 'react'
import { toast } from 'react-toastify'
import { fetchCareerHubMeta, fetchMyCareerGoals, saveMyCareerGoals } from '../../api/careerHub'
import { trackEvent } from '../../utils/analytics'
import CareerGoalsPicker from './CareerGoalsPicker'

// Account settings: edit (or clear) the private career goals that
// personalize the Career Hub's "Recommended for your goals".
export default function CareerGoalsSettings() {
  const [options, setOptions] = useState(null)
  const [selected, setSelected] = useState([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    Promise.all([fetchCareerHubMeta(), fetchMyCareerGoals()])
      .then(([meta, mine]) => {
        if (!active) return
        setOptions(meta.goals || [])
        setSelected(mine.goals.map((g) => g.key))
      })
      .catch(() => active && setError('We couldn’t load your career goals.'))
    return () => {
      active = false
    }
  }, [])

  async function save() {
    setSaving(true)
    try {
      const data = await saveMyCareerGoals(selected)
      setSelected(data.goals.map((g) => g.key))
      trackEvent('career_goals_saved', { goals: selected, source: 'account_settings' })
      toast.success('Career goals saved.')
    } catch {
      toast.error('We couldn’t save your goals. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section id="career-goals" aria-labelledby="career-goals-heading" className="mt-12 border-t border-taupe-200 pt-8">
      <h3 id="career-goals-heading" className="font-serif text-xl font-semibold text-charcoal">Career goals</h3>
      <p className="mt-1 text-sm text-charcoal-600">Choose what you want to make progress on. We’ll use this to make Career Hub more relevant. Your goals are private and never shown publicly.</p>
      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
      {!error && options === null && <div className="mt-4 h-16 animate-pulse bg-taupe-100" />}
      {options && options.length > 0 && (
        <div className="mt-4">
          <CareerGoalsPicker goals={options} value={selected} onChange={setSelected} disabled={saving} />
          <button type="button" onClick={save} disabled={saving} className="btn-primary mt-4 disabled:opacity-60">
            Save goals
          </button>
        </div>
      )}
    </section>
  )
}
