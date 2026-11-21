import EntitySelect from './EntitySelect'
import CareerPathwaysFields from './CareerPathwaysFields'
import ContentCollectionFields from './ContentCollectionFields'
import MediaPicker from './MediaPicker'
import { fetchArticles } from '../../api/articles'
import { fetchPeople } from '../../api/people'
import { fetchOrganizations, fetchSeries, fetchTopics } from '../../api/taxonomies'
import { fetchLearningPrograms } from '../../api/learning'
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

async function searchPrograms(query) {
  const res = await fetchLearningPrograms({ query, pageSize: 8 })
  return (res.items || []).map((p) => ({ value: p.slug, label: p.title }))
}

function SelectField({ label, value, options, onChange }) {
  return field(
    label,
    <select value={value} onChange={(e) => onChange(e.target.value)} className="w-full border border-taupe-300 bg-white px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none">
      {options.map(([v, text]) => (
        <option key={v} value={v}>{text}</option>
      ))}
    </select>,
  )
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
        <TextField label={spec.subheadingLabel || 'Subheading'} value={module.subheading} onChange={(v) => patch({ subheading: v })} placeholder="Section subheading" />
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

      {['editorial-articles', 'people-spotlight', 'learning'].includes(spec.contentSource) && (
        <>
          <SelectField label="Source" value={module.config.source || spec.sources[0][0]} options={spec.sources} onChange={(v) => patchConfig({ source: v })} />
          <TextField label="Eyebrow (optional)" value={module.config.eyebrow} onChange={(v) => patchConfig({ eyebrow: v })} placeholder="Small label above the heading" />
        </>
      )}

      {spec.contentSource === 'editorial-articles' && ['manual', 'editorial'].includes(module.config.source || spec.sources[0][0]) && (
        <div className="sm:col-span-2">
          {field(
            module.config.source === 'editorial' || spec.personalized ? 'Editor picks (shown first; the rest backfills)' : 'Selected articles',
            <EntitySelect multiple value={module.config.articleSlugs || []} onChange={(v) => patchConfig({ articleSlugs: v })} loadOptions={searchArticles} placeholder="Add an article…" />,
          )}
          <p className="mt-1 text-xs text-charcoal-600">A story already placed by an earlier homepage section is skipped here; it is never shown twice.</p>
        </div>
      )}
      {spec.contentSource === 'editorial-articles' && module.config.source === 'topic' && (
        <div className="sm:col-span-2">
          {field('Topics', <EntitySelect multiple value={module.config.topicSlugs || []} onChange={(v) => patchConfig({ topicSlugs: v })} loadOptions={searchTopics} placeholder="Add a topic…" />)}
        </div>
      )}
      {spec.contentSource === 'editorial-articles' && module.config.source === 'series' &&
        field('Series', <EntitySelect value={module.config.seriesSlug || null} onChange={(v) => patchConfig({ seriesSlug: v })} loadOptions={searchSeries} placeholder="Search series…" />)}
      {spec.personalized && (
        <TextField label="Heading for signed-in readers with Career Goals (optional)" value={module.config.personalizedHeading} onChange={(v) => patchConfig({ personalizedHeading: v })} placeholder="e.g. Picked for your goals" />
      )}

      {spec.contentSource === 'people-spotlight' && module.config.source === 'manual' && (
        <div className="sm:col-span-2">
          {field('People', <EntitySelect multiple value={module.config.personSlugs || []} onChange={(v) => patchConfig({ personSlugs: v })} loadOptions={searchPeople} placeholder="Add a person…" />)}
        </div>
      )}
      {spec.contentSource === 'learning' && module.config.source === 'manual' && (
        <div className="sm:col-span-2">
          {field('Programs', <EntitySelect multiple value={module.config.programSlugs || []} onChange={(v) => patchConfig({ programSlugs: v })} loadOptions={searchPrograms} placeholder="Add a program…" />)}
        </div>
      )}

      {spec.contentSource === 'mission' && (
        <>
          <TextField label="Eyebrow (optional)" value={module.config.eyebrow} onChange={(v) => patchConfig({ eyebrow: v })} placeholder="e.g. Our mission" />
          <div className="sm:col-span-2">
            {field(
              'Supporting copy (plain text; blank line between paragraphs)',
              <textarea rows={5} value={module.config.body || ''} onChange={(e) => patchConfig({ body: e.target.value || null })} className="w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" />,
            )}
          </div>
        </>
      )}

      {spec.sorts && <SelectField label="Show" value={module.config.sort || spec.sorts[0][0]} options={spec.sorts} onChange={(v) => patchConfig({ sort: v })} />}

      {spec.hasBenefits && (
        <div className="sm:col-span-2">
          {field(
            'What readers get (optional, one per line, up to 6)',
            <textarea
              rows={4}
              value={(module.config.benefits || []).join('\n')}
              onChange={(e) => patchConfig({ benefits: e.target.value.split('\n').slice(0, 6) })}
              className="w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
            />,
          )}
        </div>
      )}

      {spec.contentSource === 'pathways' && <CareerPathwaysFields module={module} onChange={onChange} />}

      {spec.contentSource === 'collection' && <ContentCollectionFields module={module} onChange={onChange} />}

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
          <TextField label={spec.ctaOptional ? 'Section link label (optional)' : 'CTA label'} value={module.ctaLabel} onChange={(v) => patch({ ctaLabel: v })} placeholder="e.g. Read more" />
          <TextField label={spec.ctaOptional ? 'Section link destination' : 'CTA link'} value={module.ctaUrl} onChange={(v) => patch({ ctaUrl: v })} placeholder="/jobs or https://…" />
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
