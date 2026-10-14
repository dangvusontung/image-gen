import { describe, expect, it } from 'vitest'
import type { ProjectDetail } from '@/api/client'
import { defaultGenerationSize, generationProject } from './generationPolicy'

const project = { provider: 'mock', model: 'mock-v1', workflow_mode: 'hybrid', preset_steps: {
  master: { provider: 'openai', model: 'image-model', size: 'low' },
  concept: { provider: 'modelark', model: 'seedream', size: '2K' },
} } as ProjectDetail

describe('per-step generation settings', () => {
  it('loads a different preset model and size for each configured step over hybrid settings', () => {
    const master = generationProject(project, 'master')
    const concept = generationProject(project, 'concept')
    expect([master.provider, master.model, defaultGenerationSize(master, 'high')]).toEqual(['openai', 'image-model', 'low'])
    expect([concept.provider, concept.model, defaultGenerationSize(concept, '4K')]).toEqual(['modelark', 'seedream', '2K'])
  })
  it('keeps the workflow fallback for unconfigured steps and manual settings when removed', () => {
    expect(generationProject(project, 'turnaround').provider).toBe('gemini')
    expect(generationProject({ ...project, preset_steps: undefined, workflow_mode: 'manual' }, 'concept').model).toBe('mock-v1')
  })
})
