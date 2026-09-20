import { Link } from 'react-router-dom'
import { Quote } from 'lucide-react'
import { getPersonBySlug } from '../../mock/people'
import CloudinaryImage from '../ui/CloudinaryImage'

export default function FeaturedWomanModule({ module }) {
  const person = getPersonBySlug(module.personSlug)
  if (!person) return null

  return (
    <section className="bg-plum-600 py-16 text-ivory sm:py-20">
      <div className="container-editorial grid grid-cols-1 items-center gap-10 lg:grid-cols-2">
        <CloudinaryImage
          publicId={person.photo}
          alt={person.name}
          width={900}
          height={1080}
          aspect={5 / 6}
          tone="plum"
          className="aspect-[5/6] w-full max-w-md object-cover"
        />
        <div>
          <p className="eyebrow !text-blush-200">{module.heading}</p>
          <Quote size={32} className="mt-4 text-blush-200/70" />
          <p className="mt-3 font-serif text-2xl font-medium leading-snug sm:text-3xl">{person.featuredQuote}</p>
          <div className="mt-6">
            <p className="font-serif text-xl font-semibold">{person.name}</p>
            <p className="text-sm text-ivory/75">
              {person.title}, {person.organization}
            </p>
          </div>
          <Link to={`/people/${person.slug}`} className="btn-outline-light mt-6">
            Read her story
          </Link>
        </div>
      </div>
    </section>
  )
}
