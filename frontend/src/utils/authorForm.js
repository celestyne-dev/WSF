// Pure AdminAuthorEditor form helpers (API Author -> editor form -> save
// payload), kept out of the JSX so the round trip is unit-tested by plain
// `node --test` (authorForm.test.js).
import { blankSource, sourcesToPayload } from './sources.js'

export function blankAuthorForm() {
  return {
    name: '',
    slug: '',
    role: '',
    shortBio: '',
    bio: [],
    photoMedia: null,
    location: '',
    countryCode: '',
    topicSlugs: [],
    // Legacy freeform expertise (feeds Author knowsAbout). Not edited in the
    // CMS — the Topic taxonomy is preferred — but carried through every save
    // so opening an Author (e.g. only to add sources) never erases it.
    expertise: [],
    personId: '',
    website: '',
    socialLinkedin: '',
    socialTwitter: '',
    socialInstagram: '',
    sources: [],
    status: 'draft',
    seoTitle: '',
    seoDescription: '',
    seoCanonical: '',
    seoOgMedia: null,
  }
}

export function authorToForm(author) {
  return {
    name: author.name || '',
    slug: author.slug || '',
    role: author.role || '',
    shortBio: author.shortBio || '',
    bio: author.bio || [],
    photoMedia: author.photoMediaId ? { ...author.photoMedia, id: author.photoMediaId } : null,
    location: author.location || '',
    countryCode: author.countryCode || '',
    topicSlugs: author.topicSlugs || [],
    expertise: author.expertise || [],
    personId: author.personId || '',
    website: author.website || '',
    socialLinkedin: author.social?.linkedin || '',
    socialTwitter: author.social?.twitter || '',
    socialInstagram: author.social?.instagram || '',
    sources: (author.sources || []).map((s) => ({ ...blankSource(), ...s })),
    status: author.status || 'draft',
    seoTitle: author.seo?.title || '',
    seoDescription: author.seo?.description || '',
    seoCanonical: author.seo?.canonical || '',
    seoOgMedia: author.seo?.ogImageMediaId ? { id: author.seo.ogImageMediaId } : null,
  }
}

// Editor form -> POST/PUT /api/v1/authors payload (AuthorInputSchema's
// camelCase data_keys).
export function authorFormToPayload(form, nextStatus) {
  return {
    name: form.name,
    slug: form.slug,
    role: form.role || null,
    shortBio: form.shortBio || null,
    bio: form.bio,
    photoMediaId: form.photoMedia?.id || null,
    location: form.location || null,
    countryCode: form.countryCode || null,
    topicSlugs: form.topicSlugs,
    expertise: form.expertise,
    personId: form.personId || null,
    website: form.website || null,
    social: {
      linkedin: form.socialLinkedin || null,
      twitter: form.socialTwitter || null,
      instagram: form.socialInstagram || null,
    },
    sources: sourcesToPayload(form.sources),
    status: nextStatus,
    seo: {
      title: form.seoTitle || null,
      description: form.seoDescription || null,
      canonical: form.seoCanonical || null,
      ogImageMediaId: form.seoOgMedia?.id || null,
    },
  }
}
