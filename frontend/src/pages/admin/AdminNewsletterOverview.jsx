import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Users, UserPlus, UserMinus, FileEdit, CalendarClock, Send } from 'lucide-react'
import { fetchNewsletterOverview, fetchNewsletterSender } from '../../api/newsletter'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatCard from '../../components/cms/StatCard'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

export default function AdminNewsletterOverview() {
  const [overview, setOverview] = useState(undefined)
  const [sender, setSender] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    Promise.all([fetchNewsletterOverview(), fetchNewsletterSender()])
      .then(([overviewData, senderData]) => {
        if (!active) return
        setOverview(overviewData)
        setSender(senderData)
      })
      .catch(() => active && setError('Something went wrong loading the newsletter overview. Please try again.'))
    return () => {
      active = false
    }
  }, [])

  if (error) return <EmptyState title="Couldn't load the newsletter overview" description={error} />
  if (overview === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title="Newsletter"
        description="WSF Weekly subscribers and campaign activity."
        actions={
          <Link to="/admin/newsletter/issues/new" className="btn-primary !px-4 !py-2 text-xs">
            New issue
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard label="Active subscribers" value={new Intl.NumberFormat('en-US').format(overview.activeSubscribers)} icon={Users} />
        <StatCard label="New in last 30 days" value={new Intl.NumberFormat('en-US').format(overview.newSubscribers30d)} icon={UserPlus} />
        <StatCard label="Unsubscribed" value={new Intl.NumberFormat('en-US').format(overview.unsubscribedCount)} icon={UserMinus} />
        <StatCard label="Draft issues" value={overview.draftIssues} icon={FileEdit} />
        <StatCard label="Scheduled issues" value={overview.scheduledIssues} icon={CalendarClock} />
        <StatCard label="Sent issues" value={overview.sentIssues} icon={Send} />
      </div>

      <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Link to="/admin/newsletter/subscribers" className="block border border-taupe-200 bg-white p-5 hover:border-burgundy-500">
          <p className="font-serif text-lg font-semibold text-charcoal">Subscribers</p>
          <p className="mt-1 text-sm text-charcoal-600">Search, filter, and manage the subscriber list.</p>
        </Link>
        <Link to="/admin/newsletter/issues" className="block border border-taupe-200 bg-white p-5 hover:border-burgundy-500">
          <p className="font-serif text-lg font-semibold text-charcoal">Issues / Campaigns</p>
          <p className="mt-1 text-sm text-charcoal-600">Draft, schedule, and archive newsletter editions.</p>
        </Link>
      </div>

      <div className="mt-8 border border-dashed border-taupe-300 bg-taupe-50 p-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Sending address</p>
        {sender?.configured ? (
          <p className="mt-1 text-sm text-charcoal-600">
            {sender.name} &lt;{sender.email}&gt;
          </p>
        ) : (
          <p className="mt-1 text-sm text-charcoal-600">
            No sender address configured yet. Marking an issue "sent" is a manual editorial record — this CMS
            doesn't deliver email itself until a provider is connected.
          </p>
        )}
      </div>
    </div>
  )
}
