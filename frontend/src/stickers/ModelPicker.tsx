import { useState } from 'react'
import { LoaderCircle } from 'lucide-react'
import { request, useProviders, type ProjectDetail } from '@/api/client'
import { json } from './api'

export default function ModelPicker({ project, onChange }: { project: ProjectDetail; onChange: () => Promise<void> }) {
  const providers = useProviders()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const selected = JSON.stringify([project.provider, project.model])
  const available = providers.data?.some(provider => provider.name === project.provider && provider.models.some(model => model.id === project.model))

  async function select(value: string) {
    const [provider, model] = JSON.parse(value) as [string, string]
    setSaving(true); setError('')
    try {
      await request(`/projects/${project.id}`, json('PATCH', { provider, model }))
      await onChange()
    } catch (cause) { setError((cause as Error).message) }
    finally { setSaving(false) }
  }

  return <div className="ss-setting-section ss-model-settings">
    <h3>Generation model</h3>
    <label className="ss-field">Choose a model
      <select aria-label="Generation model" value={selected} disabled={saving || providers.isPending} onChange={event => void select(event.target.value)}>
        {!available && <option value={selected}>{project.provider} · {project.model}</option>}
        {providers.data?.filter(provider => provider.selectable).map(provider => <optgroup key={provider.name} label={`${provider.display_name}${!provider.enabled ? ' · API key required' : ''}`}>
          {provider.models.map(model => {
            const compatible = model.aspect_ratios.includes('1:1') && model.max_reference_images > 0
            return <option key={model.id} value={JSON.stringify([provider.name, model.id])} disabled={!provider.enabled || !compatible}>
              {model.display_name}{model.display_name !== model.id ? ` · ${model.id}` : ''}{!compatible ? ' · no square reference-image support' : ''}
            </option>
          })}
        </optgroup>)}
      </select>
    </label>
    <div className="ss-model-note">{saving ? <><LoaderCircle size={12} className="ss-spin" /> Saving model…</> : <><span className="ss-status-dot" /> {project.provider} / {project.model}</>}</div>
    <p className="ss-model-help">Applies to the next generation. Running jobs keep their original model.</p>
    <a className="ss-text-button" href="/#/settings" target="_blank" rel="noreferrer">Provider settings ↗</a>
    {(error || providers.error) && <p role="alert" className="ss-small-error">{error || providers.error?.message}</p>}
  </div>
}
