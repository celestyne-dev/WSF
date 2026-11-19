// Career goal selection rules shared by the Career Hub prompt and account
// settings (mirrors backend MAX_USER_GOALS).
export const MAX_CAREER_GOALS = 3

export function toggleGoal(selected, key) {
  const list = selected || []
  if (list.includes(key)) return list.filter((k) => k !== key)
  if (list.length >= MAX_CAREER_GOALS) return list
  return [...list, key]
}
