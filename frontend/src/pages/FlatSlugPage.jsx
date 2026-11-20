import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import ArticlePage from './ArticlePage'
import GeneralPage from './GeneralPage'
import { mapPagePublic } from '../api/pages'
import { readBootstrap } from '../utils/bootstrap'

// The flat /<slug> namespace is shared by Articles and published general
// Pages (one owner per slug: backend app/services/flat_slugs.py). On a hard
// load of a Page the server already knows it is a Page and embeds a
// one-shot "page" bootstrap plus a visible prerender, so render the Page
// directly: no Article request, no loader, no Page refetch. Everything
// else (client navigation, Articles) goes through ArticlePage, which still
// falls back to GeneralPage when no Article owns the slug.
export default function FlatSlugPage() {
  const { slug } = useParams()
  const initialPage = useMemo(() => {
    const payload = readBootstrap('page', slug)
    const page = payload?.data ? mapPagePublic(payload.data) : null
    return page?.pageType === 'general' ? page : null
  }, [slug])
  return initialPage ? <GeneralPage slug={slug} initialPage={initialPage} /> : <ArticlePage />
}
