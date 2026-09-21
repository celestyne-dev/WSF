import { useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import Header from '../components/layout/Header'
import Footer from '../components/layout/Footer'
import MobileNav from '../components/layout/MobileNav'
import SearchOverlay from '../components/layout/SearchOverlay'
import { loadNavigation } from '../features/site/siteSlice'
import { closeOverlays } from '../features/navigation/uiSlice'
import { captureAcquisitionContext } from '../utils/analytics'

export default function PublicLayout() {
  const dispatch = useDispatch()
  const navigationStatus = useSelector((s) => s.site.navigationStatus)
  const location = useLocation()

  useEffect(() => {
    if (navigationStatus === 'idle') dispatch(loadNavigation())
  }, [navigationStatus, dispatch])

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
