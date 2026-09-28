import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { mapMediaRef } from '../utils/media'

// Business & Professional Directory — public browse/submit + authorized CMS
// review/publish/feature workflow (see backend app/api/v1/directory.py).
// Deliberately narrow: no payments, no business-owner login/claim workflow,
// no reviews/ratings, no maps.

let _mockDirectory
async function loadMockDirectory() {
  if (!_mockDirectory) _mockDirectory = await import('../mock/directory')
  return _mockDirectory
}

function mapOrganizationPreview(o) {
  if (!o) return null
  return {
    id: o.id,
    slug: o.slug,
    name: o.name,
    logo: mapMediaRef(o.logo),
    industry: o.industry,
    location: o.location,
    foundedYear: o.founded_year ?? o.foundedYear,
    orgType: o.org_type ?? o.orgType,
    shortDescription: o.short_description ?? o.shortDescription,
    website: o.website,
    social: o.social || {},
    status: o.status,
    country: o.country ? { code: o.country.code, name: o.country.name, region: o.country.region } : null,
  }
}

export function mapDirectoryCategory(c) {
  if (!c) return null
  return {
    id: c.id,
    slug: c.slug,
    name: c.name,
    status: c.status || 'published',
    sortOrder: c.sort_order ?? c.sortOrder ?? 0,
  }
}

export function mapDirectoryListingPublic(l) {
  if (!l) return null
  return {
    id: l.id,
    organization: mapOrganizationPreview(l.organization),
    listingType: l.listing_type ?? l.listingType,
    ownershipClassification: l.ownership_classification ?? l.ownershipClassification,
    classificationProvenance: l.classification_provenance ?? l.classificationProvenance,
    verificationStatus: l.verification_status ?? l.verificationStatus,
    serviceSummary: l.service_summary ?? l.serviceSummary,
    keyServices: l.key_services ?? l.keyServices ?? [],
    serviceModes: l.service_modes ?? l.serviceModes ?? [],
    publicContactEmail: l.public_contact_email ?? l.publicContactEmail ?? null,
    publicContactPhone: l.public_contact_phone ?? l.publicContactPhone ?? null,
    categories: (l.categories || []).map(mapDirectoryCategory),
    isCurrentlyFeatured: l.is_currently_featured ?? l.isCurrentlyFeatured ?? false,
    publishedAt: l.published_at ?? l.publishedAt ?? null,
    seo: l.seo || null,
  }
}

function mapStaffRef(u) {
  if (!u) return null
  return { id: u.id, fullName: u.full_name, email: u.email }
}

export function mapDirectoryListingAdmin(l) {
  if (!l) return null
  return {
    ...mapDirectoryListingPublic(l),
    status: l.status,
    rejectionReason: l.rejection_reason || null,
    verificationNotes: l.verification_notes || null,
    verifiedAt: l.verified_at || null,
    verifiedBy: mapStaffRef(l.verified_by),
    reviewedBy: mapStaffRef(l.reviewed_by),
    reviewedAt: l.reviewed_at || null,
    featured: l.featured,
    featuredStartAt: l.featured_start_at || null,
    featuredEndAt: l.featured_end_at || null,
    createdAt: l.created_at,
    updatedAt: l.updated_at,
  }
}

export function mapDirectorySubmissionListItem(s) {
  if (!s) return null
  return {
    id: s.id,
    reference: s.reference || '',
    status: s.status,
    businessName: s.business_name,
    website: s.website,
    listingType: s.listing_type,
    ownershipClassification: s.ownership_classification,
    country: s.country ? { code: s.country.code, name: s.country.name, region: s.country.region } : null,
    location: s.location,
    submitterName: s.submitter_name,
    submitterEmail: s.submitter_email,
    possibleDuplicateOrganizationId: s.possible_duplicate_organization_id,
    matchedOrganizationId: s.matched_organization_id,
    resultingListingId: s.resulting_listing_id,
    createdAt: s.created_at,
  }
}

export function mapDirectorySubmission(s) {
  if (!s) return null
  return {
    ...mapDirectorySubmissionListItem(s),
    description: s.description,
    keyServices: s.key_services || [],
    serviceModes: s.service_modes || [],
    categories: (s.categories || []).map(mapDirectoryCategory),
    publicContactEmail: s.public_contact_email,
    publicContactPhone: s.public_contact_phone,
    submitterRole: s.submitter_role,
    possibleDuplicateOrganization: mapOrganizationPreview(s.possible_duplicate_organization),
    matchedOrganization: mapOrganizationPreview(s.matched_organization),
    reviewedBy: mapStaffRef(s.reviewed_by),
    reviewedAt: s.reviewed_at,
    rejectionReason: s.rejection_reason,
    notes: (s.notes || []).map((n) => ({ id: n.id, body: n.body, user: mapStaffRef(n.user), createdAt: n.created_at })),
    updatedAt: s.updated_at,
  }
}

// ---------------------------------------------------------------------------
// Public
// ---------------------------------------------------------------------------

export async function fetchDirectoryListings(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/directory', {
      params: {
        q: params.query || undefined,
        country: params.country || undefined,
        region: params.region || undefined,
        category: params.category || undefined,
        classification: params.classification || undefined,
        listingType: params.listingType || undefined,
        remote: params.remote || undefined,
        sort: params.sort || undefined,
        page: params.page,
        pageSize: params.pageSize,
      },
    })
    return { ...data, items: data.items.map(mapDirectoryListingPublic) }
  }
  const { directoryListings } = await loadMockDirectory()
  let results = directoryListings
  if (params.country) results = results.filter((l) => l.organization.country?.code === params.country)
  if (params.region) results = results.filter((l) => l.organization.country?.region === params.region)
  if (params.category) results = results.filter((l) => l.categories.some((c) => c.slug === params.category))
  if (params.classification) results = results.filter((l) => l.ownershipClassification === params.classification)
  if (params.listingType) results = results.filter((l) => l.listingType === params.listingType)
  if (params.remote) results = results.filter((l) => l.serviceModes.includes('remote'))
  if (params.query) {
    const q = params.query.toLowerCase()
    results = results.filter((l) => l.organization.name.toLowerCase().includes(q))
  }
  results = [...results].sort((a, b) => Number(b.isCurrentlyFeatured) - Number(a.isCurrentlyFeatured))
  return delay(paginate(results, params))
}

export async function fetchDirectoryListing(orgSlug) {
  if (!USE_MOCK) {
    try {
      const { data } = await apiClient.get(`/directory/${orgSlug}`)
      return mapDirectoryListingPublic(data)
    } catch (err) {
      if (err.response?.status === 404) return null
      throw err
    }
  }
  const { getDirectoryListingBySlug } = await loadMockDirectory()
  return delay(getDirectoryListingBySlug(orgSlug))
}

export async function fetchDirectoryCategories() {
  if (!USE_MOCK) return (await apiClient.get('/directory/categories')).data.map(mapDirectoryCategory)
  const { directoryCategories } = await loadMockDirectory()
  return delay(directoryCategories)
}

// POST /api/v1/directory/submit — a public visitor's claim about a
// business, held for staff triage; never auto-publishes (see
// DirectorySubmitPage's own confirmation copy).
export async function submitDirectoryListing(payload, startedAt) {
  const body = {
    businessName: payload.businessName,
    website: payload.website || undefined,
    listingType: payload.listingType || 'business',
    ownershipClassification: payload.ownershipClassification || 'unspecified',
    countryCode: payload.countryCode || undefined,
    location: payload.location || undefined,
    description: payload.description || undefined,
    keyServices: payload.keyServices || [],
    serviceModes: payload.serviceModes || [],
    categoryIds: payload.categoryIds || [],
    publicContactEmail: payload.publicContactEmail || undefined,
    publicContactPhone: payload.publicContactPhone || undefined,
    submitterName: payload.submitterName,
    submitterEmail: payload.submitterEmail,
    submitterRole: payload.submitterRole || undefined,
    hpWebsite: payload.hpWebsite || '',
    elapsedMs: startedAt ? Date.now() - startedAt : undefined,
  }
  if (!USE_MOCK) {
    try {
      const { data } = await apiClient.post('/directory/submit', body)
      return {
        success: true,
        reference: data.reference,
        message: `Thank you — we've received your submission (reference ${data.reference}). Our team reviews every submission before anything is published.`,
      }
    } catch (err) {
      return { success: false, message: err.apiError?.message || 'Something went wrong. Please try again.' }
    }
  }
  return delay(
    {
      success: true,
      reference: 'WSF-DIR-2026-000001',
      message: "Thank you — we've received your submission (reference WSF-DIR-2026-000001). Our team reviews every submission before anything is published.",
    },
    500,
  )
}

// ---------------------------------------------------------------------------
// Admin — directory.manage (listings/submissions) and taxonomy.manage
// (categories). No mock-mode fallback: the whole admin surface is
// real-data-only, same as Taxonomy/Contact admin.
// ---------------------------------------------------------------------------

export async function fetchAdminDirectoryListings(params = {}) {
  const { data } = await apiClient.get('/directory/admin/listings', {
    params: {
      status: params.status || undefined,
      verificationStatus: params.verificationStatus || undefined,
      listingType: params.listingType || undefined,
      ownershipClassification: params.ownershipClassification || undefined,
      featured: params.featured || undefined,
      country: params.country || undefined,
      region: params.region || undefined,
      q: params.query || undefined,
      page: params.page,
      pageSize: params.pageSize || 20,
    },
  })
  return { items: data.items.map(mapDirectoryListingAdmin), pagination: data.pagination }
}

export async function fetchAdminDirectoryListing(id) {
  const { data } = await apiClient.get(`/directory/admin/listings/${id}`)
  return mapDirectoryListingAdmin(data)
}

export async function createAdminDirectoryListing(payload) {
  const { data } = await apiClient.post('/directory/admin/listings', payload)
  return mapDirectoryListingAdmin(data)
}

export async function updateAdminDirectoryListing(id, payload) {
  const { data } = await apiClient.put(`/directory/admin/listings/${id}`, payload)
  return mapDirectoryListingAdmin(data)
}

export async function setAdminDirectoryListingStatus(id, status, rejectionReason) {
  const { data } = await apiClient.patch(`/directory/admin/listings/${id}/status`, { status, rejectionReason })
  return mapDirectoryListingAdmin(data)
}

export async function setAdminDirectoryListingVerification(id, verificationStatus, verificationNotes) {
  const { data } = await apiClient.patch(`/directory/admin/listings/${id}/verification`, {
    verificationStatus,
    verificationNotes,
  })
  return mapDirectoryListingAdmin(data)
}

export async function setAdminDirectoryListingFeatured(id, featured, featuredStartAt, featuredEndAt) {
  const { data } = await apiClient.patch(`/directory/admin/listings/${id}/featured`, {
    featured,
    featuredStartAt: featuredStartAt || undefined,
    featuredEndAt: featuredEndAt || undefined,
  })
  return mapDirectoryListingAdmin(data)
}

export async function deleteAdminDirectoryListing(id) {
  await apiClient.delete(`/directory/admin/listings/${id}`)
}

export async function fetchAdminDirectorySubmissions(params = {}) {
  const { data } = await apiClient.get('/directory/admin/submissions', {
    params: { status: params.status || undefined, q: params.query || undefined, page: params.page, pageSize: params.pageSize || 20 },
  })
  return { items: data.items.map(mapDirectorySubmissionListItem), pagination: data.pagination }
}

export async function fetchAdminDirectorySubmission(id) {
  const { data } = await apiClient.get(`/directory/admin/submissions/${id}`)
  return mapDirectorySubmission(data)
}

export async function setAdminDirectorySubmissionStatus(id, status, rejectionReason) {
  const { data } = await apiClient.patch(`/directory/admin/submissions/${id}/status`, { status, rejectionReason })
  return mapDirectorySubmission(data)
}

export async function convertAdminDirectorySubmission(id, organizationId) {
  const { data } = await apiClient.post(`/directory/admin/submissions/${id}/convert`, {
    organizationId: organizationId || undefined,
  })
  return { submission: mapDirectorySubmission(data.submission), listing: mapDirectoryListingAdmin(data.listing) }
}

export async function addAdminDirectorySubmissionNote(id, body) {
  const { data } = await apiClient.post(`/directory/admin/submissions/${id}/notes`, { body })
  return mapDirectorySubmission(data)
}

export async function fetchAdminDirectoryCategories(params = {}) {
  const { data } = await apiClient.get('/directory/admin/categories', { params })
  return { ...data, items: data.items.map(mapDirectoryCategory) }
}

export async function createDirectoryCategory(payload) {
  return mapDirectoryCategory((await apiClient.post('/directory/admin/categories', payload)).data)
}

export async function updateDirectoryCategory(id, payload) {
  return mapDirectoryCategory((await apiClient.put(`/directory/admin/categories/${id}`, payload)).data)
}

export async function setDirectoryCategoryStatus(id, status) {
  return mapDirectoryCategory((await apiClient.put(`/directory/admin/categories/${id}/status`, { status })).data)
}

export async function deleteDirectoryCategory(id) {
  await apiClient.delete(`/directory/admin/categories/${id}`)
}
