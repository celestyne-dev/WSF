import { series } from '../mock/series'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import SeriesCard from '../components/cards/SeriesCard'

export default function SeriesIndexPage() {
  useSeo({
    title: 'Editorial Series | Women Shaping Futures',
    description: 'Explore our ongoing editorial series, from Women Doing Incredible Things to Founder Stories.',
    canonical: 'https://womenshapingfutures.org/series',
  })

  return (
    <div>
      <PageHeader eyebrow="Series" title="Editorial Series" description="Ongoing collections of stories built around a single theme, question, or kind of woman we can't stop covering." />
      <div className="container-editorial py-14">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {series.map((item) => (
            <SeriesCard key={item.id} item={item} />
          ))}
        </div>
      </div>
    </div>
  )
}
