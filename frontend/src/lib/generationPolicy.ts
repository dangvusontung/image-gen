import type { ProjectDetail } from '@/api/client'

export function generationProject(project: ProjectDetail, purpose: 'draft' | 'enhance'): ProjectDetail {
  if (!project.workflow_mode || project.workflow_mode === 'manual') return project
  const bfl = purpose === 'enhance' && project.workflow_mode === 'hybrid'
  return { ...project, provider: bfl ? 'bfl' : 'gemini', model: bfl ? 'flux-2-pro' : 'gemini-nano-banana-2.1' }
}

export function defaultGenerationSize(project: ProjectDetail, modelDefault?: string | null) {
  return project.workflow_mode && project.workflow_mode !== 'manual'
    ? (project.provider === 'bfl' ? '1MP' : '1K') : modelDefault
}
