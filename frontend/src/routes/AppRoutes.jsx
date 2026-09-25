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
const NewsletterIssuePage = lazy(() => import('../pages/NewsletterIssuePage'))
const NewsletterUnsubscribePage = lazy(() => import('../pages/NewsletterUnsubscribePage'))
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
const ProductDetailPage = lazy(() => import('../pages/ProductDetailPage'))
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
const AdminJobs = lazy(() => import('../pages/admin/AdminJobs'))
const AdminJobEditor = lazy(() => import('../pages/admin/AdminJobEditor'))
const AdminOpportunities = lazy(() => import('../pages/admin/AdminOpportunities'))
const AdminOpportunityEditor = lazy(() => import('../pages/admin/AdminOpportunityEditor'))
const AdminEvents = lazy(() => import('../pages/admin/AdminEvents'))
const AdminEventEditor = lazy(() => import('../pages/admin/AdminEventEditor'))
const AdminProducts = lazy(() => import('../pages/admin/AdminProducts'))
const AdminProductEditor = lazy(() => import('../pages/admin/AdminProductEditor'))
const AdminResources = lazy(() => import('../pages/admin/AdminResources'))
const AdminResourceEditor = lazy(() => import('../pages/admin/AdminResourceEditor'))
const AdminTopics = lazy(() => import('../pages/admin/AdminTopics'))
const AdminTopicEditor = lazy(() => import('../pages/admin/AdminTopicEditor'))
const AdminCategories = lazy(() => import('../pages/admin/AdminCategories'))
const AdminSeries = lazy(() => import('../pages/admin/AdminSeries'))
const AdminSeriesEditor = lazy(() => import('../pages/admin/AdminSeriesEditor'))
const AdminTags = lazy(() => import('../pages/admin/AdminTags'))
const AdminNewsletterOverview = lazy(() => import('../pages/admin/AdminNewsletterOverview'))
const AdminNewsletterIssues = lazy(() => import('../pages/admin/AdminNewsletterIssues'))
const AdminNewsletterEditor = lazy(() => import('../pages/admin/AdminNewsletterEditor'))
const AdminSubscribers = lazy(() => import('../pages/admin/AdminSubscribers'))
const AdminSubscriberDetail = lazy(() => import('../pages/admin/AdminSubscriberDetail'))
const AdminPartnerships = lazy(() => import('../pages/admin/AdminPartnerships'))
const AdminPartnershipDetail = lazy(() => import('../pages/admin/AdminPartnershipDetail'))
const AdminSponsors = lazy(() => import('../pages/admin/AdminSponsors'))
const AdminSponsorEditor = lazy(() => import('../pages/admin/AdminSponsorEditor'))
const AdminAdvertise = lazy(() => import('../pages/admin/AdminAdvertise'))
const AdminMembers = lazy(() => import('../pages/admin/AdminMembers'))
const AdminMemberDetail = lazy(() => import('../pages/admin/AdminMemberDetail'))
const AdminCommunityPage = lazy(() => import('../pages/admin/AdminCommunityPage'))
const AdminMentorshipOverview = lazy(() => import('../pages/admin/AdminMentorshipOverview'))
const AdminMentorshipPrograms = lazy(() => import('../pages/admin/AdminMentorshipPrograms'))
const AdminMentorshipProgramEditor = lazy(() => import('../pages/admin/AdminMentorshipProgramEditor'))
const AdminMentorshipApplications = lazy(() => import('../pages/admin/AdminMentorshipApplications'))
const AdminMentorshipApplicationDetail = lazy(() => import('../pages/admin/AdminMentorshipApplicationDetail'))
const AdminMentorshipMatches = lazy(() => import('../pages/admin/AdminMentorshipMatches'))
const AdminMentorshipMatchDetail = lazy(() => import('../pages/admin/AdminMentorshipMatchDetail'))
const AdminStorySubmissions = lazy(() => import('../pages/admin/AdminStorySubmissions'))
const AdminStorySubmissionDetail = lazy(() => import('../pages/admin/AdminStorySubmissionDetail'))
const AdminNominations = lazy(() => import('../pages/admin/AdminNominations'))
const AdminNominationDetail = lazy(() => import('../pages/admin/AdminNominationDetail'))
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
          <Route path="/newsletter/unsubscribe/:token" element={<NewsletterUnsubscribePage />} />
          <Route path="/newsletter/:slug" element={<NewsletterIssuePage />} />
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
          <Route path="/shop/:slug" element={<ProductDetailPage />} />

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
          <Route path="jobs" element={<AdminJobs />} />
          <Route path="jobs/new" element={<AdminJobEditor />} />
          <Route path="jobs/:id" element={<AdminJobEditor />} />
          <Route path="opportunities" element={<AdminOpportunities />} />
          <Route path="opportunities/new" element={<AdminOpportunityEditor />} />
          <Route path="opportunities/:id" element={<AdminOpportunityEditor />} />
          <Route path="events" element={<AdminEvents />} />
          <Route path="events/new" element={<AdminEventEditor />} />
          <Route path="events/:id" element={<AdminEventEditor />} />
          <Route path="products" element={<AdminProducts />} />
          <Route path="products/new" element={<AdminProductEditor />} />
          <Route path="products/:id" element={<AdminProductEditor />} />
          <Route path="resources" element={<AdminResources />} />
          <Route path="resources/new" element={<AdminResourceEditor />} />
          <Route path="resources/:id" element={<AdminResourceEditor />} />
          <Route path="taxonomy/topics" element={<AdminTopics />} />
          <Route path="taxonomy/topics/new" element={<AdminTopicEditor />} />
          <Route path="taxonomy/topics/:id" element={<AdminTopicEditor />} />
          <Route path="taxonomy/categories" element={<AdminCategories />} />
          <Route path="taxonomy/series" element={<AdminSeries />} />
          <Route path="taxonomy/series/new" element={<AdminSeriesEditor />} />
          <Route path="taxonomy/series/:id" element={<AdminSeriesEditor />} />
          <Route path="taxonomy/tags" element={<AdminTags />} />
          <Route path="newsletter" element={<AdminNewsletterOverview />} />
          <Route path="newsletter/issues" element={<AdminNewsletterIssues />} />
          <Route path="newsletter/issues/new" element={<AdminNewsletterEditor />} />
          <Route path="newsletter/issues/:slug" element={<AdminNewsletterEditor />} />
          <Route path="newsletter/subscribers" element={<AdminSubscribers />} />
          <Route path="newsletter/subscribers/:id" element={<AdminSubscriberDetail />} />
          <Route path="members" element={<AdminMembers />} />
          <Route path="members/:id" element={<AdminMemberDetail />} />
          <Route path="community-page" element={<AdminCommunityPage />} />
          <Route path="mentorship" element={<AdminMentorshipOverview />} />
          <Route path="mentorship/programs" element={<AdminMentorshipPrograms />} />
          <Route path="mentorship/programs/new" element={<AdminMentorshipProgramEditor />} />
          <Route path="mentorship/programs/:id" element={<AdminMentorshipProgramEditor />} />
          <Route path="mentorship/applications" element={<AdminMentorshipApplications />} />
          <Route path="mentorship/applications/:id" element={<AdminMentorshipApplicationDetail />} />
          <Route path="mentorship/mentors" element={<AdminMentorshipApplications defaultRole="mentor" />} />
          <Route path="mentorship/mentees" element={<AdminMentorshipApplications defaultRole="mentee" />} />
          <Route path="mentorship/matches" element={<AdminMentorshipMatches />} />
          <Route path="mentorship/matches/:id" element={<AdminMentorshipMatchDetail />} />
          <Route path="submissions" element={<AdminStorySubmissions />} />
          <Route path="submissions/:id" element={<AdminStorySubmissionDetail />} />
          <Route path="nominations" element={<AdminNominations />} />
          <Route path="nominations/:id" element={<AdminNominationDetail />} />
          <Route path="partnerships" element={<AdminPartnerships />} />
          <Route path="partnerships/:id" element={<AdminPartnershipDetail />} />
          <Route path="sponsors" element={<AdminSponsors />} />
          <Route path="sponsors/new" element={<AdminSponsorEditor />} />
          <Route path="sponsors/:id" element={<AdminSponsorEditor />} />
          <Route path="advertising" element={<AdminAdvertise />} />
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
