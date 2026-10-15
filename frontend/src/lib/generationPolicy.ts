import type { ProjectDetail } from '@/api/client'

export function generationProject(project: ProjectDetail, purpose: 'draft' | 'master' | 'turnaround' | 'concept' | 'enhance'): ProjectDetail {
  const target = project.preset_steps?.[purpose === 'draft' ? 'master' : purpose]
  if (target) return { ...project, provider: target.provider, model: target.model, generation_size: target.size, workflow_mode: 'manual' }
  if (!project.workflow_mode || project.workflow_mode === 'manual') return project
  const bfl = purpose === 'enhance' && project.workflow_mode === 'hybrid'
  return { ...project, provider: bfl ? 'bfl' : 'gemini', model: bfl ? 'flux-2-pro' : 'gemini-nano-banana-2.1' }
}

export function defaultGenerationSize(project: ProjectDetail, modelDefault?: string | null) {
  if (project.generation_size) return project.generation_size
  return project.workflow_mode && project.workflow_mode !== 'manual'
    ? (project.provider === 'bfl' ? '1MP' : '1K') : modelDefault
}


export function generationPromptName(project: ProjectDetail, purpose: 'master' | 'turnaround' | 'concept' | 'enhance') {
  const target = generationProject(project, purpose)
  return target.provider === 'bfl' && (purpose === 'master' || purpose === 'turnaround') ? `${purpose}_flux` : purpose
}
