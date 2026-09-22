import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate, useParams } from 'react-router-dom'
import PublicLayout from '../layouts/PublicLayout'
import AdminLayout from '../layouts/AdminLayout'
import PageLoader from '../components/ui/PageLoader'

const HomePage = lazy(() => import('../pages/HomePage'))
const ArticlePage = lazy(() => import('../pages/ArticlePage'))
const TopicsIndexPage = lazy(() => import('../pages/TopicsIndexPage'))
const TopicDetailPage = lazy(() => import('../pages/TopicDetailPage'))
const PeopleDirectoryPage = lazy(() => import('../pages/PeopleDirectoryPage'))
const PersonProfilePage = lazy(() => import('../pages/PersonProfilePage'))
const AuthorsIndexPage = lazy(() => import('../pages/AuthorsIndexPage'))
const AuthorProfilePage = lazy(() => import('../pages/AuthorProfilePage'))
const SeriesIndexPage = lazy(() => import('../pages/SeriesIndexPage'))
const SeriesDetailPage = lazy(() => import('../pages/SeriesDetailPage'))
const JobsListingPage = lazy(() => import('../pages/JobsListingPage'))
const JobDetailPage = lazy(() => import('../pages/JobDetailPage'))
const OpportunitiesListingPage = lazy(() => import('../pages/OpportunitiesListingPage'))
const OpportunityDetailPage = lazy(() => import('../pages/OpportunityDetailPage'))
const EventsListingPage = lazy(() => import('../pages/EventsListingPage'))
const EventDetailPage = lazy(() => import('../pages/EventDetailPage'))
const ResourcesPage = lazy(() => import('../pages/ResourcesPage'))
const ResourceDetailPage = lazy(() => import('../pages/ResourceDetailPage'))
const OrganizationsIndexPage = lazy(() => import('../pages/OrganizationsIndexPage'))
const OrganizationDetailPage = lazy(() => import('../pages/OrganizationDetailPage'))
const NewsletterPage = lazy(() => import('../pages/NewsletterPage'))
const PartnershipsPage = lazy(() => import('../pages/PartnershipsPage'))
const AdvertisePage = lazy(() => import('../pages/AdvertisePage'))
const AboutPage = lazy(() => import('../pages/AboutPage'))
const SearchPage = lazy(() => import('../pages/SearchPage'))
const LoginPage = lazy(() => import('../pages/LoginPage'))
const SubmitStoryPage = lazy(() => import('../pages/SubmitStoryPage'))
const NominatePage = lazy(() => import('../pages/NominatePage'))
const MentorshipPage = lazy(() => import('../pages/MentorshipPage'))
const CommunityPage = lazy(() => import('../pages/CommunityPage'))
const LearningPage = lazy(() => import('../pages/LearningPage'))
const ShopPage = lazy(() => import('../pages/ShopPage'))
const ContactPage = lazy(() => import('../pages/ContactPage'))
const LegalPage = lazy(() => import('../pages/LegalPage'))
const NotFoundPage = lazy(() => import('../pages/NotFoundPage'))

const AdminDashboard = lazy(() => import('../pages/admin/AdminDashboard'))
const AdminArticles = lazy(() => import('../pages/admin/AdminArticles'))
const AdminArticleEditor = lazy(() => import('../pages/admin/AdminArticleEditor'))
const AdminPeople = lazy(() => import('../pages/admin/AdminPeople'))
const AdminPersonEditor = lazy(() => import('../pages/admin/AdminPersonEditor'))
const AdminAuthors = lazy(() => import('../pages/admin/AdminAuthors'))
const AdminAuthorEditor = lazy(() => import('../pages/admin/AdminAuthorEditor'))
const AdminOrganizations = lazy(() => import('../pages/admin/AdminOrganizations'))
const AdminOrganizationEditor = lazy(() => import('../pages/admin/AdminOrganizationEditor'))
const AdminHomepageBuilder = lazy(() => import('../pages/admin/AdminHomepageBuilder'))
const AdminGenericList = lazy(() => import('../pages/admin/AdminGenericList'))
const AdminMediaLibrary = lazy(() => import('../pages/admin/AdminMediaLibrary'))
const AdminUsers = lazy(() => import('../pages/admin/AdminUsers'))
const AdminSettings = lazy(() => import('../pages/admin/AdminSettings'))
const AdminAnalytics = lazy(() => import('../pages/admin/AdminAnalytics'))

function ArticleLegacyRedirect() {
  const { slug } = useParams()
  return <Navigate to={`/${slug}`} replace />
}

export default function AppRoutes() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route path="/" element={<HomePage />} />

          <Route path="/topics" element={<TopicsIndexPage />} />
          <Route path="/topics/:slug" element={<TopicDetailPage />} />

          <Route path="/people" element={<PeopleDirectoryPage />} />
          <Route path="/people/:slug" element={<PersonProfilePage />} />

          <Route path="/authors" element={<AuthorsIndexPage />} />
          <Route path="/authors/:slug" element={<AuthorProfilePage />} />

          <Route path="/series" element={<SeriesIndexPage />} />
          <Route path="/series/:slug" element={<SeriesDetailPage />} />

          <Route path="/jobs" element={<JobsListingPage />} />
          <Route path="/jobs/:slug" element={<JobDetailPage />} />

          <Route path="/opportunities" element={<OpportunitiesListingPage />} />
          <Route path="/opportunities/:slug" element={<OpportunityDetailPage />} />

          <Route path="/events" element={<EventsListingPage />} />
          <Route path="/events/:slug" element={<EventDetailPage />} />

          <Route path="/resources" element={<ResourcesPage />} />
          <Route path="/resources/:slug" element={<ResourceDetailPage />} />

          <Route path="/organizations" element={<OrganizationsIndexPage />} />
          <Route path="/organizations/:slug" element={<OrganizationDetailPage />} />

          <Route path="/newsletter" element={<NewsletterPage />} />
          <Route path="/partnerships" element={<PartnershipsPage />} />
          <Route path="/advertise" element={<AdvertisePage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/submit" element={<SubmitStoryPage />} />
          <Route path="/nominate" element={<NominatePage />} />
          <Route path="/mentorship" element={<MentorshipPage />} />
          <Route path="/community" element={<CommunityPage />} />
          <Route path="/learning" element={<LearningPage />} />
          <Route path="/shop" element={<ShopPage />} />

          <Route path="/privacy" element={<LegalPage docKey="privacy" />} />
          <Route path="/terms" element={<LegalPage docKey="terms" />} />
          <Route path="/cookies" element={<LegalPage docKey="cookies" />} />
          <Route path="/editorial-policy" element={<LegalPage docKey="editorial-policy" />} />

          {/* Legacy nested article URLs redirect permanently to the flat URL. */}
          <Route path="/articles/:slug" element={<ArticleLegacyRedirect />} />

          {/* Flat public article URL — ranks below every static route above. */}
          <Route path="/:slug" element={<ArticlePage />} />

          <Route path="*" element={<NotFoundPage />} />
        </Route>

        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<AdminDashboard />} />
          <Route path="articles" element={<AdminArticles />} />
          <Route path="articles/new" element={<AdminArticleEditor />} />
          <Route path="articles/:id" element={<AdminArticleEditor />} />
          <Route path="homepage" element={<AdminHomepageBuilder />} />
          <Route path="people" element={<AdminPeople />} />
          <Route path="people/new" element={<AdminPersonEditor />} />
          <Route path="people/:id" element={<AdminPersonEditor />} />
          <Route path="authors" element={<AdminAuthors />} />
          <Route path="authors/new" element={<AdminAuthorEditor />} />
          <Route path="authors/:id" element={<AdminAuthorEditor />} />
          <Route path="organizations" element={<AdminOrganizations />} />
          <Route path="organizations/new" element={<AdminOrganizationEditor />} />
          <Route path="organizations/:id" element={<AdminOrganizationEditor />} />
          <Route path="jobs" element={<AdminGenericList section="jobs" />} />
          <Route path="opportunities" element={<AdminGenericList section="opportunities" />} />
          <Route path="events" element={<AdminGenericList section="events" />} />
          <Route path="resources" element={<AdminGenericList section="resources" />} />
          <Route path="newsletter" element={<AdminGenericList section="newsletter" />} />
          <Route path="submissions" element={<AdminGenericList section="submissions" />} />
          <Route path="nominations" element={<AdminGenericList section="nominations" />} />
          <Route path="partnerships" element={<AdminGenericList section="partnerships" />} />
          <Route path="advertising" element={<AdminGenericList section="advertising" />} />
          <Route path="media" element={<AdminMediaLibrary />} />
          <Route path="seo" element={<AdminGenericList section="seo" />} />
          <Route path="analytics" element={<AdminAnalytics />} />
          <Route path="users" element={<AdminUsers />} />
          <Route path="settings" element={<AdminSettings />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
