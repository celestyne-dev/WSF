import EntitySelect from './EntitySelect'
import { searchCollectionEntity, searchSeriesSlugs, searchTopicSlugs } from '../../api/destinationSearch'
import {
  COLLECTION_ENTITIES,
  COLLECTION_ENTITY_TYPES,
  COLLECTION_LAYOUTS,
  COLLECTION_MAX_ITEMS,
  COLLECTION_MIN_ITEMS,
  changeCollectionEntity,
  changeCollectionMode,
} from '../../utils/homepageCollections'

const inputClass = 'w-full border border-taupe-300 bg-white px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none'

function Field({ label, children, wide }) {
  return (
    <div className={wide ? 'sm:col-span-2' : undefined}>
      <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">{label}</label>
      <div className="mt-1">{children}</div>
    </div>
  )
}

function Select({ value, onChange, options, emptyLabel }) {
  return (
    <select value={value || ''} onChange={(e) => onChange(e.target.value || null)} className={inputClass}>
      {emptyLabel && <option value="">{emptyLabel}</option>}
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}

const TERM_LOADERS = { topic: searchTopicSlugs, series: searchSeriesSlugs }

/**
 * Content Collection — entity type + manual (ordered picks) or automatic
 * (entity-aware sort/filters). Only the fields relevant to the current
 * entity and mode are shown; switching either clears the stale ones
 * (utils/homepageCollections.js).
 */
export default function ContentCollectionFields({ module, onChange }) {
  const config = module.config || {}
  const entityType = COLLECTION_ENTITIES[config.entityType] ? config.entityType : null
  const spec = entityType ? COLLECTION_ENTITIES[entityType] : null
  const mode = module.selectionMode === 'manual' ? 'manual' : 'automatic'
  const patchConfig = (fields) => onChange({ ...module, config: { ...config, ...fields } })
  const patchFilter = (key, value) => patchConfig({ filters: { ...(config.filters || {}), [key]: value || undefined } })

  return (
    <>
      <Field label="Eyebrow (optional)">
        <input value={config.eyebrow || ''} maxLength={60} onChange={(e) => patchConfig({ eyebrow: e.target.value || null })} placeholder="e.g. From the community" className={inputClass} />
      </Field>
      <Field label="Shows">
        <Select
          value={entityType}
          onChange={(v) => v && onChange(changeCollectionEntity(module, v))}
          options={COLLECTION_ENTITY_TYPES.map((t) => ({ value: t, label: COLLECTION_ENTITIES[t].label }))}
        />
      </Field>
      <Field label="Selection">
        <div className="flex gap-4 pt-2 text-sm text-charcoal">
          {['automatic', 'manual'].map((m) => (
            <label key={m} className="flex items-center gap-2">
              <input type="radio" name={`mode-${module.id}`} checked={mode === m} onChange={() => onChange(changeCollectionMode(module, m))} />
              {m === 'automatic' ? 'Automatic' : 'Hand-picked'}
            </label>
          ))}
        </div>
      </Field>
      <Field label="Layout">
        <Select value={config.layout || 'grid'} onChange={(v) => patchConfig({ layout: v || 'grid' })} options={COLLECTION_LAYOUTS} />
      </Field>

      {spec && mode === 'manual' && (
        <Field label={`Selected ${spec.label.toLowerCase()} (up to ${COLLECTION_MAX_ITEMS}, shown in this order)`} wide>
          <EntitySelect
            key={entityType}
            multiple
            value={config.slugs || []}
            onChange={(v) => patchConfig({ slugs: (v || []).slice(0, COLLECTION_MAX_ITEMS) })}
            loadOptions={(q) => searchCollectionEntity(entityType, q)}
            placeholder={`Search published ${spec.label.toLowerCase()}…`}
          />
        </Field>
      )}

      {spec && mode === 'automatic' && (
        <>
          <Field label={`Item count (${COLLECTION_MIN_ITEMS}–${COLLECTION_MAX_ITEMS})`}>
            <input
              type="number"
              min={COLLECTION_MIN_ITEMS}
              max={COLLECTION_MAX_ITEMS}
              value={config.itemCount ?? ''}
              onChange={(e) => {
                const n = e.target.value === '' ? null : Number(e.target.value)
                patchConfig({ itemCount: n === null ? null : Math.min(COLLECTION_MAX_ITEMS, Math.max(COLLECTION_MIN_ITEMS, n)) })
              }}
              className="w-28 border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
            />
          </Field>
          <Field label="Order">
            <Select value={config.sort || spec.sorts[0].value} onChange={(v) => patchConfig({ sort: v })} options={spec.sorts} />
          </Field>
          {Object.entries(spec.filters).map(([key, filter]) => (
            <Field key={`${entityType}-${key}`} label={`${filter.label} (optional)`}>
              {filter.kind === 'choice' ? (
                <Select value={config.filters?.[key]} onChange={(v) => patchFilter(key, v)} options={filter.options} emptyLabel="Any" />
              ) : (
                <EntitySelect value={config.filters?.[key] || null} onChange={(v) => patchFilter(key, v)} loadOptions={TERM_LOADERS[filter.kind]} placeholder={`Any ${filter.label.toLowerCase()}`} />
              )}
            </Field>
          ))}
          {(entityType === 'jobs' || entityType === 'opportunities') && (
            <p className="self-end text-xs text-charcoal-600 sm:col-span-2">
              Expired listings never show. “Closing soon” only includes listings with a future deadline.
            </p>
          )}
        </>
      )}
      <p className="text-xs text-charcoal-600 sm:col-span-2">Only published, publicly visible items appear. The section hides itself when nothing matches.</p>
    </>
  )
}
