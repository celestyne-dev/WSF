import { useEffect, useState } from 'react'
import { toast } from 'react-toastify'
import { fetchAdminSettings, saveAdminSettings } from '../api/admin'

// Loads one Studio settings section (GET /admin/settings) and saves it back
// (PUT /admin/settings with only that key).
export default function useSettingsSection(key) {
  const [value, setValue] = useState(null)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  useEffect(() => {
    let active = true
    fetchAdminSettings()
      .then((data) => active && setValue(data[key] || {}))
      .catch(() => active && setError('Could not load these settings. Please try again.'))
    return () => {
      active = false
    }
  }, [key])
  async function save(next) {
    setSaving(true)
    try {
      const data = await saveAdminSettings({ [key]: next })
      setValue(data?.[key] || next)
      toast.success('Saved. Public pages use it from their next load.')
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || err?.apiError?.message || 'Could not save. Please check the values.')
    } finally {
      setSaving(false)
    }
  }
  return { value, setValue, error, saving, save }
}
