import { test } from 'node:test'
import assert from 'node:assert/strict'
import { CTA_PRESETS } from './ctaPresets.js'
import { isInternalPath, safeLinkUrl } from '../utils/linkSafety.js'

test('every CTA preset fills only the editable CTA fields with a safe internal link', () => {
  const allowed = new Set(['eyebrow', 'title', 'text', 'buttonLabel', 'buttonUrl'])
  assert.deepEqual(CTA_PRESETS.map((p) => p.label), ['Career Hub', 'Resources', 'Learning', 'WSF Circle', 'Newsletter', 'Submit your story'])
  for (const preset of CTA_PRESETS) {
    for (const key of Object.keys(preset.fields)) assert.ok(allowed.has(key), `${preset.key}.${key}`)
    assert.equal(safeLinkUrl(preset.fields.buttonUrl), preset.fields.buttonUrl)
    assert.ok(isInternalPath(preset.fields.buttonUrl))
    assert.ok(preset.fields.title.length <= 160 && preset.fields.text.length <= 600 && preset.fields.buttonLabel.length <= 60)
  }
  assert.equal(CTA_PRESETS.find((p) => p.key === 'submit').fields.buttonUrl, '/submit')
})
