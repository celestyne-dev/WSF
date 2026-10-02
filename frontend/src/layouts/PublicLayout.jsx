import { useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import Header from '../components/layout/Header'
import Footer from '../components/layout/Footer'
import MobileNav from '../components/layout/MobileNav'
import SearchOverlay from '../components/layout/SearchOverlay'
import { loadNavigation, loadCountries, loadSiteSettings, loadFooter } from '../features/site/siteSlice'
import { closeOverlays } from '../features/navigation/uiSlice'
import { restoreSession } from '../features/auth/authSlice'
import { captureAcquisitionContext } from '../utils/analytics'
import useSiteStructuredData from '../hooks/useSiteStructuredData'

export default function PublicLayout() {
  const dispatch = useDispatch()
  const navigationStatus = useSelector((s) => s.site.navigationStatus)
  const countriesStatus = useSelector((s) => s.site.countriesStatus)
  const settingsStatus = useSelector((s) => s.site.settingsStatus)
  const footerStatus = useSelector((s) => s.site.footerStatus)
  const accessToken = useSelector((s) => s.auth.accessToken)
  const user = useSelector((s) => s.auth.user)
  const location = useLocation()

  useSiteStructuredData()

  useEffect(() => {
    if (navigationStatus === 'idle') dispatch(loadNavigation())
    if (countriesStatus === 'idle') dispatch(loadCountries())
    if (settingsStatus === 'idle') dispatch(loadSiteSettings())
    if (footerStatus === 'idle') dispatch(loadFooter())
  }, [navigationStatus, countriesStatus, settingsStatus, footerStatus, dispatch])

  // Every public route shares this layout, so restoring the session here —
  // rather than only on /account — means Header/MobileNav reflect a real
  // logged-in session after a refresh on "/", "/community", "/about",
  // anywhere. Guarded on `!user` (not a request-status flag): once
  // restoreSession resolves (either way), `user` is either populated or
  // the token's been cleared (see authSlice.js), so this effect can't
  // re-fire and loop — it only runs again if accessToken itself changes.
  useEffect(() => {
    if (accessToken && !user) dispatch(restoreSession())
  }, [accessToken, user, dispatch])

  useEffect(() => {
    dispatch(closeOverlays())
    window.scrollTo(0, 0)
    captureAcquisitionContext()
  }, [location.pathname, location.search, dispatch])

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <MobileNav />
      <SearchOverlay />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
