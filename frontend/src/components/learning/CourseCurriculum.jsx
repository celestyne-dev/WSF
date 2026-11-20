import { Link } from 'react-router-dom'
import { ArrowRight, CheckCircle2, Circle, Lock, PlayCircle } from 'lucide-react'
import { formatMinutes, moduleProgress, LESSON_TYPE_LABEL } from '../../utils/learning'

// The course outline used on the course page ("Course content") and as the
// lesson page's sidebar/drawer. Status is always text + icon, never colour
// alone: "Completed", "Current lesson", or nothing for remaining lessons.
// Lessons link to the lesson page only when the viewer can read them.
export default function CourseCurriculum({ programSlug, modules, completedIds = [], currentLessonId = null, canReadLessons, openModuleIndex = 0, onNavigate, variant = 'page' }) {
  const done = new Set(completedIds)
  const sidebar = variant === 'sidebar'
  return (
    <ol className={sidebar ? 'space-y-1' : 'space-y-3'}>
      {modules.map((module, index) => {
        const progress = moduleProgress(module, completedIds)
        const minutes = (module.lessons || []).reduce((sum, l) => sum + (l.durationMinutes || 0), 0)
        const meta = [`${progress.total} lesson${progress.total === 1 ? '' : 's'}`, formatMinutes(minutes)].filter(Boolean).join(' · ')
        return (
          <li key={module.id || index}>
            <details
              open={index === openModuleIndex || (sidebar && module.lessons?.some((l) => l.id === currentLessonId))}
              className={sidebar ? 'group' : 'group rounded-card border border-taupe-200 bg-white'}
            >
              <summary className={`flex cursor-pointer list-none items-start justify-between gap-3 [&::-webkit-details-marker]:hidden ${sidebar ? 'py-2' : 'px-5 py-4'}`}>
                <span className="min-w-0">
                  <span className="block text-[11px] font-semibold uppercase tracking-[0.14em] text-charcoal-600">
                    Module {index + 1}
                    {progress.complete && (
                      <span className="ml-2 inline-flex items-center gap-1 text-emerald-700">
                        <CheckCircle2 size={12} aria-hidden="true" /> Complete
                      </span>
                    )}
                  </span>
                  <span className={`mt-0.5 block font-serif font-semibold text-charcoal ${sidebar ? 'text-[15px] leading-snug' : 'text-lg'}`}>{module.title}</span>
                  {meta && <span className="mt-0.5 block text-xs text-charcoal-600">{meta}{completedIds.length > 0 && progress.total > 0 ? ` · ${progress.completed}/${progress.total} done` : ''}</span>}
                </span>
                <span aria-hidden="true" className="mt-1 text-charcoal-600 transition-transform group-open:rotate-90">›</span>
              </summary>
              {!sidebar && module.description && <p className="px-5 pb-2 text-sm text-charcoal-600">{module.description}</p>}
              <ol className={sidebar ? 'mb-2 border-l border-taupe-200 pl-3' : 'border-t border-taupe-100 px-2 py-2 sm:px-3'}>
                {(module.lessons || []).map((lesson, lessonIndex) => {
                  const complete = done.has(lesson.id)
                  const current = lesson.id === currentLessonId
                  const video = lesson.lessonType === 'video' || lesson.lessonType === 'recording'
                  const Icon = complete ? CheckCircle2 : current ? ArrowRight : video ? PlayCircle : Circle
                  const label = (
                    <>
                      <Icon size={16} aria-hidden="true" className={`mt-0.5 shrink-0 ${complete ? 'text-emerald-700' : current ? 'text-burgundy-600' : 'text-charcoal-600/50'}`} />
                      <span className="min-w-0 flex-1">
                        <span className={`block leading-snug ${current ? 'font-semibold text-charcoal' : 'text-charcoal'}`}>
                          <span className="sr-only">Lesson {lessonIndex + 1}: </span>
                          {lesson.title}
                        </span>
                        <span className="block text-xs text-charcoal-600">
                          {[LESSON_TYPE_LABEL[lesson.lessonType], formatMinutes(lesson.durationMinutes)].filter(Boolean).join(' · ')}
                          {complete && <span className="ml-1 font-medium text-emerald-700">· Completed</span>}
                          {current && <span className="ml-1 font-medium text-burgundy-600">· Current lesson</span>}
                        </span>
                      </span>
                    </>
                  )
                  const rowClass = `flex items-start gap-2.5 rounded-control px-2 py-2 text-[15px] ${current ? 'bg-blush-50' : ''}`
                  return (
                    <li key={lesson.id}>
                      {canReadLessons ? (
                        <Link
                          to={`/learning/${programSlug}/lessons/${lesson.id}`}
                          onClick={onNavigate}
                          aria-current={current ? 'page' : undefined}
                          className={`${rowClass} hover:bg-cream`}
                        >
                          {label}
                        </Link>
                      ) : (
                        <div className={rowClass}>
                          {label}
                          <Lock size={14} aria-label="Available after you enroll" className="mt-1 shrink-0 text-charcoal-600/50" />
                        </div>
                      )}
                    </li>
                  )
                })}
                {!module.lessons?.length && <li className="px-2 py-2 text-sm text-charcoal-600">Lessons coming soon.</li>}
              </ol>
            </details>
          </li>
        )
      })}
    </ol>
  )
}
