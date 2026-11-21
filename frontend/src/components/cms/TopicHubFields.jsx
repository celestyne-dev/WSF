import { useEffect, useState } from 'react'
import { toast } from 'react-toastify'
import EntitySelect from './EntitySelect'
import { fetchArticles } from '../../api/articles'
import { fetchAdminTopicHub, fetchTopics, saveAdminTopicHub } from '../../api/taxonomies'

async function searchArticles(query) {
  const res = await fetchArticles({ query, pageSize: 8 })
  return res.items.map((a) => ({ value: a.slug, label: a.title }))
}

// Studio: a Topic hub's curation (backend services/topic_hub.py). Related
// topics are only ever the ones an editor adds here (never inferred). Start
// here / Editor's picks never repeat a story: the public page skips any
// Article already placed earlier on it. Saved on its own.
export default function TopicHubFields({ topicId, topicSlug }) {
  const [hub, setHub] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    fetchAdminTopicHub(topicId)
      .then((data) => active && setHub(data))
      .catch(() => active && setHub({ startHereSlugs: [], editorsPicksSlugs: [], relatedTopicSlugs: [] }))
    return () => {
      active = false
    }
  }, [topicId])

  async function searchTopics(query) {
    const all = await fetchTopics()
    const q = (query || '').toLowerCase()
    return all
      .filter((t) => t.slug !== topicSlug && (!q || t.name.toLowerCase().includes(q)))
      .slice(0, 12)
      .map((t) => ({ value: t.slug, label: t.name }))
  }

  async function save() {
    setSaving(true)
    try {
      setHub(await saveAdminTopicHub(topicId, hub))
      toast.success('Topic hub saved.')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Could not save the topic hub.')
    } finally {
      setSaving(false)
    }
  }

  if (!hub) return <p className="text-sm text-charcoal-600">Loading…</p>
  const label = 'text-xs font-semibold uppercase tracking-wide text-charcoal-600'
  return (
    <div className="space-y-5">
      <div>
        <p className={label}>Browse related topics</p>
        <div className="mt-1.5">
          <EntitySelect multiple value={hub.relatedTopicSlugs} onChange={(v) => setHub({ ...hub, relatedTopicSlugs: v })} loadOptions={searchTopics} placeholder="Add a related topic…" />
        </div>
      </div>
      <div>
        <p className={label}>More “Start here” stories (after the cornerstone above, up to 6)</p>
        <div className="mt-1.5">
          <EntitySelect multiple value={hub.startHereSlugs} onChange={(v) => setHub({ ...hub, startHereSlugs: v })} loadOptions={searchArticles} placeholder="Add an article…" />
        </div>
      </div>
      <div>
        <p className={label}>Editor’s picks / most useful (up to 8)</p>
        <div className="mt-1.5">
          <EntitySelect multiple value={hub.editorsPicksSlugs} onChange={(v) => setHub({ ...hub, editorsPicksSlugs: v })} loadOptions={searchArticles} placeholder="Add an article…" />
        </div>
      </div>
      <button type="button" onClick={save} disabled={saving} className="btn-primary disabled:opacity-60">
        {saving ? 'Saving…' : 'Save topic hub'}
      </button>
    </div>
  )
}
