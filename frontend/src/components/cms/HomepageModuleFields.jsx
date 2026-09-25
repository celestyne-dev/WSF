import EntitySelect from './EntitySelect'
import MediaPicker from './MediaPicker'
import { fetchArticles } from '../../api/articles'
import { fetchPeople } from '../../api/people'
import { fetchOrganizations, fetchSeries, fetchTopics } from '../../api/taxonomies'
import { HOMEPAGE_MODULE_REGISTRY, HOMEPAGE_SPONSOR_PLACEMENT_KEYS } from '../../constants/homepageModules'

async function searchArticles(query) {
  const res = await fetchArticles({ query, pageSize: 8 })
  return res.items.map((a) => ({ value: a.slug, label: a.title, sublabel: a.authorName || undefined }))
}

async function searchPeople(query) {
  const res = await fetchPeople({ query, status: 'published', pageSize: 8 })
  return res.items.map((p) => ({ value: p.slug, label: p.name, sublabel: p.title || undefined }))
}

async function searchOrganizations(query) {
  const res = await fetchOrganizations({ query, status: 'published', pageSize: 8 })
  return res.items.map((o) => ({ value: o.slug, label: o.name }))
}

// Series/Topics have no search-backed list endpoint (they're small,
// published-only lists already — see backend/app/api/v1/taxonomy.py), so
// this fetches once and filters client-side rather than adding a new
// backend query param for a handful of rows.
async function searchSeries(query) {
  const all = await fetchSeries()
  const q = (query || '').toLowerCase()
  return all
    .filter((s) => !q || s.name.toLowerCase().includes(q))
    .slice(0, 12)
    .map((s) => ({ value: s.slug, label: s.name }))
}

async function searchTopics(query) {
  const all = await fetchTopics()
  const q = (query || '').toLowerCase()
  return all
    .filter((t) => !q || t.name.toLowerCase().includes(q))
    .slice(0, 12)
    .map((t) => ({ value: t.slug, label: t.name }))
}

function field(label, input) {
  return (
    <div>
      {label && <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">{label}</label>}
      <div className="mt-1">{input}</div>
    </div>
  )
}

function TextField({ label, value, onChange, placeholder }) {
  return field(
    label,
    <input
      value={value || ''}
      onChange={(e) => onChange(e.target.value || null)}
      placeholder={placeholder}
      className="w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
    />
  )
}

function ItemCountField({ bounds, value, onChange }) {
  const [min, max] = bounds
  return field(
    `Item count (${min}–${max})`,
    <input
      type="number"
      min={min}
      max={max}
      value={value ?? ''}
      onChange={(e) => {
        const n = e.target.value === '' ? null : Number(e.target.value)
        onChange(n === null ? null : Math.min(max, Math.max(min, n)))
      }}
      className="w-28 border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
    />
  )
}

/**
 * Renders the content-source-specific fields for one homepage module,
 * driven entirely by HOMEPAGE_MODULE_REGISTRY[module.type] — no
 * `if (type === ...)` chain living in the page component itself.
 */
export default function HomepageModuleFields({ module, onChange }) {
  const spec = HOMEPAGE_MODULE_REGISTRY[module.type]
  if (!spec) return null

  function patch(fields) {
    onChange({ ...module, ...fields })
  }

  function patchConfig(fields) {
    onChange({ ...module, config: { ...module.config, ...fields } })
  }

  const showHeading = spec.contentSource !== 'sponsor'
  const showSubheading = spec.contentSource !== 'sponsor' && spec.contentSource !== 'manual-orgs'

  return (
    <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
      {showHeading && (
        <TextField label="Heading" value={module.heading} onChange={(v) => patch({ heading: v })} placeholder="Section heading" />
      )}
      {showSubheading && (
        <TextField label="Subheading" value={module.subheading} onChange={(v) => patch({ subheading: v })} placeholder="Section subheading" />
      )}

      {spec.contentSource === 'manual-hero' && (
        <>
          {field(
            'Lead article',
            <EntitySelect value={module.config.leadArticleSlug || null} onChange={(v) => patchConfig({ leadArticleSlug: v })} loadOptions={searchArticles} placeholder="Search published articles…" />
          )}
          {field(
            'Secondary articles',
            <EntitySelect multiple value={module.config.secondaryArticleSlugs || []} onChange={(v) => patchConfig({ secondaryArticleSlugs: v })} loadOptions={searchArticles} placeholder="Add a secondary article…" />
          )}
        </>
      )}

      {spec.contentSource === 'manual-articles' && (
        <div className="sm:col-span-2">
          {field(
            'Selected articles',
            <EntitySelect multiple value={module.config.articleSlugs || []} onChange={(v) => patchConfig({ articleSlugs: v })} loadOptions={searchArticles} placeholder="Add an article…" />
          )}
        </div>
      )}

      {spec.contentSource === 'manual-person' &&
        field(
          'Person',
          <EntitySelect value={module.config.personSlug || null} onChange={(v) => patchConfig({ personSlug: v })} loadOptions={searchPeople} placeholder="Search published people…" />
        )}

      {spec.contentSource === 'manual-series' &&
        field(
          'Series',
          <EntitySelect value={module.config.seriesSlug || null} onChange={(v) => patchConfig({ seriesSlug: v })} loadOptions={searchSeries} placeholder="Search series…" />
        )}

      {spec.contentSource === 'manual-topic' &&
        field(
          'Topic',
          <EntitySelect value={module.config.topicSlug || null} onChange={(v) => patchConfig({ topicSlug: v })} loadOptions={searchTopics} placeholder="Search topics…" />
        )}

      {spec.contentSource === 'manual-orgs' && (
        <div className="sm:col-span-2">
          {field(
            'Partner organizations',
            <EntitySelect multiple value={module.config.partnerSlugs || []} onChange={(v) => patchConfig({ partnerSlugs: v })} loadOptions={searchOrganizations} placeholder="Add an organization…" />
          )}
        </div>
      )}

      {spec.contentSource === 'sponsor' &&
        field(
          'Placement',
          <select
            value={module.config.placementKey || HOMEPAGE_SPONSOR_PLACEMENT_KEYS[0]}
            onChange={(e) => patchConfig({ placementKey: e.target.value })}
            className="w-full border border-taupe-300 bg-white px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
          >
            {HOMEPAGE_SPONSOR_PLACEMENT_KEYS.map((key) => (
              <option key={key} value={key}>
                {key}
              </option>
            ))}
          </select>
        )}

      {spec.hasItemCount &&
        field(
          '',
          <ItemCountField bounds={spec.itemCountBounds} value={module.config.itemCount} onChange={(v) => patchConfig({ itemCount: v })} />
        )}

      {spec.hasMedia && (
        <div className="sm:col-span-2">
          <MediaPicker
            label={spec.contentSource === 'manual-hero' ? 'Hero image (used when no lead article is selected)' : 'Image'}
            value={module.media}
            onChange={(media) => patch({ media, mediaId: media?.id ?? null })}
          />
        </div>
      )}

      {spec.hasCta && (
        <>
          <TextField label="CTA label" value={module.ctaLabel} onChange={(v) => patch({ ctaLabel: v })} placeholder="e.g. Read more" />
          <TextField label="CTA link" value={module.ctaUrl} onChange={(v) => patch({ ctaUrl: v })} placeholder="/jobs or https://…" />
        </>
      )}

      {spec.hasSecondaryCta && (
        <>
          <TextField label="Secondary CTA label" value={module.secondaryCtaLabel} onChange={(v) => patch({ secondaryCtaLabel: v })} placeholder="Optional" />
          <TextField label="Secondary CTA link" value={module.secondaryCtaUrl} onChange={(v) => patch({ secondaryCtaUrl: v })} placeholder="/community or https://…" />
        </>
      )}
    </div>
  )
}
