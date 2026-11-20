import { useCallback, useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import { fetchLearningProgramBySlug } from '../api/learning'
import {
  checkLearningEnrollment,
  enrollInProgram,
  fetchProtectedCurriculum,
  markLessonComplete,
  markLessonIncomplete,
} from '../api/learningEnrollments'

// One loader for a course and the viewer's learning state, shared by the
// course page and the lesson page so both read the same truth:
//   program            public detail (full curriculum for free; outline otherwise)
//   enrollment         the learner's own enrollment (undefined = still checking)
//   modules            the curriculum to show: protected (full) when the
//                      learner may read it, else the public payload's modules
//   canReadLessons     whether lesson bodies are available to this viewer
// Access is always decided by the backend; this only reflects its answers.
export default function useCourse(slug) {
  const accessToken = useSelector((s) => s.auth.accessToken)
  // Each async result is stored with the key it belongs to, and read back
  // only while that key is current — so a slug/enrollment change never
  // shows stale data and no effect has to reset state synchronously.
  const [loaded, setLoaded] = useState({ slug: null, program: undefined, error: null })
  const [enrollmentState, setEnrollmentState] = useState({ programId: null, value: undefined })
  const [curriculum, setCurriculum] = useState({ enrollmentId: null, modules: null, denied: false })
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    fetchLearningProgramBySlug(slug)
      .then((data) => active && setLoaded({ slug, program: data, error: null }))
      .catch(() => active && setLoaded({ slug, program: undefined, error: 'Something went wrong loading this course. Please try again.' }))
    return () => {
      active = false
    }
  }, [slug])

  const program = loaded.slug === slug ? loaded.program : undefined
  const error = loaded.slug === slug ? loaded.error : null
  const enrollable =
    !!program &&
    (program.accessType === 'free' || program.accessType === 'circle_only' || (program.accessType === 'product' && program.viewerCanAccess === true))
  const protectedAccess = !!program && program.accessType !== 'free' && enrollable
  const checkEnrollment = enrollable && !!accessToken

  useEffect(() => {
    if (!checkEnrollment) return undefined
    let active = true
    const programId = program.id
    checkLearningEnrollment(programId)
      .then((result) => active && setEnrollmentState({ programId, value: result.enrollment || null }))
      .catch(() => active && setEnrollmentState({ programId, value: null }))
    return () => {
      active = false
    }
  }, [program, checkEnrollment])

  let enrollment
  if (!program) enrollment = undefined
  else if (!checkEnrollment) enrollment = null
  else enrollment = enrollmentState.programId === program.id ? enrollmentState.value : undefined

  const enrollmentId = enrollment?.id
  const loadProtected = protectedAccess && !!accessToken && !!enrollmentId && enrollment?.status === 'active'
  useEffect(() => {
    if (!loadProtected) return undefined
    let active = true
    fetchProtectedCurriculum(enrollmentId)
      .then((modules) => active && setCurriculum({ enrollmentId, modules, denied: false }))
      .catch((err) => {
        if (active) setCurriculum({ enrollmentId, modules: null, denied: ['circle_required', 'access_denied'].includes(err?.response?.data?.error?.code) })
      })
    return () => {
      active = false
    }
  }, [loadProtected, enrollmentId])

  const current = loadProtected && curriculum.enrollmentId === enrollmentId
  const protectedModules = current ? curriculum.modules : null
  const accessDenied = current ? curriculum.denied : false

  const setEnrollment = useCallback((value) => setEnrollmentState({ programId: value?.program?.id ?? program?.id ?? null, value }), [program])

  const enroll = useCallback(async () => {
    setBusy(true)
    try {
      const result = await enrollInProgram(program.id)
      setEnrollmentState({ programId: program.id, value: result.enrollment })
      return result.enrollment
    } finally {
      setBusy(false)
    }
  }, [program])

  const setLessonComplete = useCallback(
    async (lessonId, complete) => {
      if (!enrollment) return null
      const updated = complete ? await markLessonComplete(enrollment.id, lessonId) : await markLessonIncomplete(enrollment.id, lessonId)
      setEnrollmentState({ programId: program.id, value: updated })
      return updated
    },
    [enrollment, program],
  )

  const canReadLessons = !!program && (program.accessType === 'free' || protectedModules !== null)
  const modules = protectedModules || program?.modules || []

  return {
    program,
    error,
    enrollment,
    setEnrollment,
    modules,
    canReadLessons,
    accessDenied,
    enrollable,
    busy,
    enroll,
    setLessonComplete,
    signedIn: !!accessToken,
  }
}
