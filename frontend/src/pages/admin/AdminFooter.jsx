import { useEffect, useState } from 'react'
import { toast } from 'react-toastify'
import { Plus, Save, ExternalLink, ChevronUp, ChevronDown, Trash2 } from 'lucide-react'
import { fetchAdminFooter, saveAdminFooter } from '../../api/footer'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import FooterLinkRow from '../../components/cms/FooterLinkRow'
import FooterSocialLinkRow from '../../components/cms/FooterSocialLinkRow'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { FOOTER_MAX_GROUPS, newFooterGroup, newFooterLink, newSocialLink } from '../../constants/footerItems'

function Section({ title, description, children }) {
  return (
    <section className="mb-8 border border-taupe-200 bg-white p-5">
      <h2 className="font-serif text-lg font-semibold text-charcoal">{title}</h2>
      {description && <p className="mt-1 text-sm text-charcoal-600">{description}</p>}
      <div className="mt-4">{children}</div>
    </section>
  )
}

function labeledInput(label, value, onChange, { textarea = false, maxLength, placeholder } = {}) {
  const Tag = textarea ? 'textarea' : 'input'
  return (
    <div>
      <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">{label}</label>
      <Tag
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        maxLength={maxLength}
        placeholder={placeholder}
        rows={textarea ? 3 : undefined}
        className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none"
      />
    </div>
  )
}

export default function AdminFooter() {
  const [footer, setFooter] = useState(undefined)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchAdminFooter()
      .then(setFooter)
      .catch(() => setError('Something went wrong loading the footer. Please try again.'))
  }, [])

  if (error) return <EmptyState title="Couldn't load the footer" description={error} />
  if (footer === undefined) return <PageLoader />

  const { groups, socialLinks, settings } = footer

  function updateSettings(patch) {
    setFooter((prev) => ({ ...prev, settings: { ...prev.settings, ...patch } }))
  }

  function updateGroups(nextGroups) {
    setFooter((prev) => ({ ...prev, groups: nextGroups }))
  }

  function updateGroup(index, patch) {
    const next = [...groups]
    next[index] = { ...next[index], ...patch }
    updateGroups(next)
  }

  function moveGroup(index, direction) {
    const target = index + direction
    if (target < 0 || target >= groups.length) return
    const next = [...groups]
    ;[next[index], next[target]] = [next[target], next[index]]
    updateGroups(next)
  }

  function addGroup() {
    if (groups.length >= FOOTER_MAX_GROUPS) {
      toast.error(`Footer supports at most ${FOOTER_MAX_GROUPS} groups.`)
      return
    }
    updateGroups([...groups, newFooterGroup()])
  }

  function removeGroup(index) {
    const group = groups[index]
    if (!window.confirm(`Remove the "${group.heading || 'Untitled'}" group and all its links? This never deletes the Pages/Topics/Series those links point to.`)) return
    updateGroups(groups.filter((_, i) => i !== index))
  }

  function updateLink(groupIndex, linkIndex, nextItem) {
    const items = [...groups[groupIndex].items]
    items[linkIndex] = nextItem
    updateGroup(groupIndex, { items })
  }

  function removeLink(groupIndex, linkIndex) {
    const items = groups[groupIndex].items.filter((_, i) => i !== linkIndex)
    updateGroup(groupIndex, { items })
  }

  function moveLink(groupIndex, linkIndex, direction) {
    const items = [...groups[groupIndex].items]
    const target = linkIndex + direction
    if (target < 0 || target >= items.length) return
    ;[items[linkIndex], items[target]] = [items[target], items[linkIndex]]
    updateGroup(groupIndex, { items })
  }

  function addLink(groupIndex) {
    updateGroup(groupIndex, { items: [...groups[groupIndex].items, newFooterLink('route')] })
  }

  function updateSocialLinks(next) {
    setFooter((prev) => ({ ...prev, socialLinks: next }))
  }

  function updateSocialLink(index, next) {
    const links = [...socialLinks]
    links[index] = next
    updateSocialLinks(links)
  }

  function moveSocialLink(index, direction) {
    const target = index + direction
    if (target < 0 || target >= socialLinks.length) return
    const next = [...socialLinks]
    ;[next[index], next[target]] = [next[target], next[index]]
    updateSocialLinks(next)
  }

  async function handleSave() {
    setSaving(true)
    try {
      const saved = await saveAdminFooter(footer)
      setFooter(saved)
      toast.success('Footer published.')
    } catch (err) {
      const message = err?.response?.data?.error?.message
      toast.error(message || 'Something went wrong saving the footer. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <AdminPageHeader
        title="Footer"
        description="Manage the site-wide footer — branding, link groups, social links, the newsletter CTA, contact info, and copyright."
        actions={
          <>
            <a href="/" target="_blank" rel="noreferrer" className="btn-secondary !px-4 !py-2 text-xs">
              <ExternalLink size={14} /> View live
            </a>
            <button type="button" onClick={handleSave} disabled={saving} className="btn-primary !px-4 !py-2 text-xs disabled:opacity-60">
              <Save size={14} /> {saving ? 'Publishing…' : 'Save & publish'}
            </button>
          </>
        }
      />

      <Section title="Branding" description="A short description shown near the logo in the footer.">
        {labeledInput('Brand description', settings.brandDescription, (v) => updateSettings({ brandDescription: v }), {
          textarea: true,
          maxLength: 280,
          placeholder: 'A short line about Women Shaping Futures…',
        })}
      </Section>

      <Section title="Newsletter CTA" description="Presentation only — subscribing still uses the existing Newsletter signup form and consent handling.">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {labeledInput('Heading', settings.newsletterHeading, (v) => updateSettings({ newsletterHeading: v }), { maxLength: 150 })}
          {labeledInput('Description', settings.newsletterDescription, (v) => updateSettings({ newsletterDescription: v }), { maxLength: 300 })}
        </div>
        <label className="mt-3 flex items-center gap-2 text-sm text-charcoal">
          <input type="checkbox" checked={settings.newsletterVisible} onChange={(e) => updateSettings({ newsletterVisible: e.target.checked })} />
          Show the newsletter CTA in the footer
        </label>
      </Section>

      <Section title="Link groups" description="Group → Links, no deeper nesting. Reorder groups and links, show/hide either without deleting them.">
        <div className="space-y-4">
          {groups.map((group, gi) => (
            <div key={group.key || `new-${gi}`} className="border border-taupe-300 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex flex-col">
                  <button type="button" disabled={gi === 0} onClick={() => moveGroup(gi, -1)} className="text-charcoal-600 hover:text-burgundy-600 disabled:opacity-30">
                    <ChevronUp size={14} />
                  </button>
                  <button type="button" disabled={gi === groups.length - 1} onClick={() => moveGroup(gi, 1)} className="text-charcoal-600 hover:text-burgundy-600 disabled:opacity-30">
                    <ChevronDown size={14} />
                  </button>
                </div>
                <input
                  value={group.heading}
                  onChange={(e) => updateGroup(gi, { heading: e.target.value })}
                  maxLength={40}
                  placeholder="Group heading"
                  className="flex-1 border border-taupe-300 px-3 py-2 text-sm font-semibold focus:border-burgundy-500 focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => updateGroup(gi, { visible: !group.visible })}
                  className={`px-3 py-1.5 text-xs font-semibold uppercase tracking-wide ${group.visible ? 'text-charcoal-600' : 'bg-taupe-200 text-charcoal-600'}`}
                >
                  {group.visible ? 'Visible' : 'Hidden'}
                </button>
                <button type="button" onClick={() => removeGroup(gi)} className="text-charcoal-600 hover:text-burgundy-600" aria-label="Remove group">
                  <Trash2 size={16} />
                </button>
              </div>

              <div className="mt-3 space-y-2 pl-4">
                {group.items.length === 0 && <p className="text-xs text-charcoal-600">No links yet.</p>}
                {group.items.map((item, li) => (
                  <FooterLinkRow
                    key={item.id}
                    item={item}
                    index={li}
                    siblingCount={group.items.length}
                    onChange={(next) => updateLink(gi, li, next)}
                    onRemove={() => removeLink(gi, li)}
                    onMove={(dir) => moveLink(gi, li, dir)}
                  />
                ))}
                <button type="button" onClick={() => addLink(gi)} className="btn-secondary !px-3 !py-1.5 text-xs">
                  <Plus size={13} /> Add link
                </button>
              </div>
            </div>
          ))}
        </div>

        {groups.length === 0 && <EmptyState title="No groups yet" description="Add the first footer group." />}

        <button type="button" onClick={addGroup} className="btn-secondary mt-4 !px-4 !py-2 text-xs">
          <Plus size={14} /> Add group
        </button>
      </Section>

      <Section title="Social links" description="Controlled platforms only, with a real accessible name — never an icon alone.">
        <div className="space-y-2">
          {socialLinks.map((link, i) => (
            <FooterSocialLinkRow
              key={link.id}
              item={link}
              index={i}
              siblingCount={socialLinks.length}
              onChange={(next) => updateSocialLink(i, next)}
              onRemove={() => updateSocialLinks(socialLinks.filter((_, idx) => idx !== i))}
              onMove={(dir) => moveSocialLink(i, dir)}
            />
          ))}
        </div>
        {socialLinks.length === 0 && <EmptyState title="No social links yet" description="Add the first social link." />}
        <button type="button" onClick={() => updateSocialLinks([...socialLinks, newSocialLink()])} className="btn-secondary mt-3 !px-4 !py-2 text-xs">
          <Plus size={14} /> Add social link
        </button>
      </Section>

      <Section title="Contact / public info" description="Only intentionally public information — never internal staff emails or phone numbers.">
        {labeledInput('Public contact email', settings.contactEmail, (v) => updateSettings({ contactEmail: v }), { placeholder: 'hello@womenshapingfutures.org' })}
      </Section>

      <Section title="Copyright" description="The year is always computed automatically — never edited here.">
        {labeledInput('Copyright text', settings.copyrightText, (v) => updateSettings({ copyrightText: v }), { maxLength: 200 })}
        <p className="mt-2 text-xs text-charcoal-600">Preview: © {new Date().getFullYear()} {settings.copyrightText}</p>
      </Section>
    </div>
  )
}
