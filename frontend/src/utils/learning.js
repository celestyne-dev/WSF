// Pure Learning helpers shared by the course page, the lesson page, the
// Learning index and Learning Paths. Everything here works from real
// program/enrollment data only — no invented percentages or durations.

export const LEVEL_LABEL = {
  beginner: 'Beginner',
  intermediate: 'Intermediate',
  advanced: 'Advanced',
  all_levels: 'All levels',
}

export const PROGRAM_TYPE_LABEL = {
  course: 'Course',
  masterclass: 'Masterclass',
  program: 'Program',
  learning_series: 'Learning Series',
  challenge: 'Challenge',
}

// "25 min", "1 hr", "2 hr 30 min"; '' for nothing known.
export function formatMinutes(minutes) {
  const total = Math.round(Number(minutes) || 0)
  if (total <= 0) return ''
  const hours = Math.floor(total / 60)
  const mins = total % 60
  if (!hours) return `${mins} min`
  return mins ? `${hours} hr ${mins} min` : `${hours} hr`
}

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

// Two short fact lines for a course header / card:
//   ["Self-paced", "Text-based", "Intermediate"]
//   ["5 modules", "18 lessons", "Approx. 2 hr 30 min"]
// Only facts the program actually has are included.
export function programMetaLines(program) {
  if (!program) return [[], []]
  const stats = program.stats || {}
  const first = [
    program.deliveryMode === 'self_paced' ? 'Self-paced' : program.deliveryMode ? program.deliveryMode.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase()) : null,
    stats.formatLabel || null,
    LEVEL_LABEL[program.difficultyLevel] || null,
  ].filter(Boolean)
  const second = []
  if (stats.moduleCount) second.push(plural(stats.moduleCount, 'module'))
  if (stats.lessonCount) second.push(plural(stats.lessonCount, 'lesson'))
  if (stats.totalMinutes) second.push(`Approx. ${formatMinutes(stats.totalMinutes)}`)
  else if (program.durationValue) second.push(`${program.durationValue} ${program.durationUnit || ''}`.trim())
  return [first, second]
}

// [{ lesson, module, moduleIndex, lessonIndex }] in curriculum order.
export function flattenLessons(modules) {
  const out = []
  ;(modules || []).forEach((module, moduleIndex) => {
    ;(module.lessons || []).forEach((lesson, lessonIndex) => out.push({ lesson, module, moduleIndex, lessonIndex }))
  })
  return out
}

// Previous / next lesson around `lessonId`, and its 1-based position.
export function lessonNeighbors(modules, lessonId) {
  const flat = flattenLessons(modules)
  const index = flat.findIndex((entry) => entry.lesson.id === Number(lessonId))
  if (index === -1) return { current: null, prev: null, next: null, position: 0, total: flat.length }
  return {
    current: flat[index],
    prev: index > 0 ? flat[index - 1] : null,
    next: index < flat.length - 1 ? flat[index + 1] : null,
    position: index + 1,
    total: flat.length,
  }
}

export function moduleProgress(module, completedIds) {
  const done = new Set(completedIds || [])
  const total = (module?.lessons || []).length
  const completed = (module?.lessons || []).filter((l) => done.has(l.id)).length
  return { completed, total, complete: total > 0 && completed === total }
}

// The first lesson not yet completed (curriculum order), or null.
export function nextIncompleteLesson(modules, completedIds) {
  const done = new Set(completedIds || [])
  return flattenLessons(modules).find((entry) => !done.has(entry.lesson.id)) || null
}

// Index of the module the learner is currently in: the module of the next
// incomplete lesson, or the last module when everything is complete.
export function currentModuleIndex(modules, completedIds) {
  const next = nextIncompleteLesson(modules, completedIds)
  if (next) return next.moduleIndex
  return Math.max(0, (modules || []).length - 1)
}

// "6 of 18 lessons complete" — only when there is real progress data.
export function progressText(enrollment) {
  if (!enrollment || !enrollment.totalLessons) return ''
  return `${enrollment.completedLessons} of ${enrollment.totalLessons} lessons complete`
}

export const LESSON_TYPE_LABEL = {
  text: 'Reading',
  activity: 'Activity',
  article: 'Article',
  resource: 'Resource',
  external_link: 'Link',
  video: 'Video',
  recording: 'Recording',
}
