import { QueryClient, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

const API_BASE = '/api'


export type AssetKind = 'reference' | 'side_profile' | 'template'

export interface Asset {
  id: string
  kind: AssetKind
  filename: string
  size: number
  content_type: string
  width: number | null
  height: number | null
  position: number
  /** Deselected photos stay in the project but are never sent to a provider. */
  selected: boolean
  created_at: string
}

export interface ProjectSummary {
  id: string
  name: string
  description: string | null
  rights_confirmed: boolean
  provider: string
  model: string
  created_at: string
  updated_at: string
  asset_count: number
  thumbnail_asset_id: string | null
  completed_jobs: number
  active_jobs: number
  failed_jobs: number
  recent_activity: string | null
}

export type WorkflowStep = 'master' | 'turnaround' | 'concept' | 'enhance'

export interface PresetStep { provider: string; model: string; size: string | null }

export interface Preset {
  id: string; name: string
  steps: Partial<Record<WorkflowStep, PresetStep>>
  created_at: string; updated_at: string
}

export interface ProjectDetail {
  workflow_mode?: "manual" | "hybrid" | "hybrid_gemini"
  id: string
  name: string
  description: string | null
  rights_confirmed: boolean
  provider: string
  model: string
  created_at: string
  updated_at: string
  /** Which reference leads each step; missing keys mean the automatic choice. */
  step_leads: Partial<Record<WorkflowStep, string>>
  /** Template image steering each step's art direction. */
  step_templates: Partial<Record<WorkflowStep, string>>
  /** When set, this preset decides provider/model/size per step. */
  preset_id: string | null
  assets: Asset[]
}

export interface ModelInfo {
  id: string
  display_name: string
  max_reference_images: number
  aspect_ratios: string[]
  default_aspect_ratio: string
  price_per_image_usd: number | null
  price_note: string | null
  status: string
  notes: string | null
  default: boolean
  sizes?: string[]
  default_size?: string | null
  price_table?: Record<string, number>
}

export interface ProviderInfo {
  name: string
  display_name: string
  selectable: boolean
  key_configured: boolean
  enabled: boolean
  info_url: string | null
  data_notice: string | null
  models: ModelInfo[]
  /** Set when the provider can list the account's own models. */
  catalogue_source: string | null
  catalogue_fetched_at: string | null
  /** True when the provider can answer with text, not only images. */
  supports_text: boolean
}

export interface CatalogueResult {
  provider: string
  source: string | null
  fetched_at: string | null
  models: ModelInfo[]
}

export interface ConnectionTestResult {
  ok: boolean
  message: string
  code: string | null
}

export interface SpendInfo {
  spent_24h_usd: number
  limit_usd: number
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message)
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response
  try {
    resp = await fetch(`${API_BASE}${path}`, init)
  } catch {
    throw new ApiError(0, 'network_error', 'Không kết nối được tới server. Kiểm tra backend đang chạy.')
  }
  if (resp.status === 204) return undefined as T
  const body = await resp.json().catch(() => null)
  if (!resp.ok) {
    const detail = body?.detail
    if (detail && typeof detail === 'object' && 'message' in detail) {
      throw new ApiError(resp.status, detail.code, detail.message)
    }
    if (Array.isArray(detail)) {
      throw new ApiError(resp.status, 'validation_error', 'Dữ liệu không hợp lệ')
    }
    throw new ApiError(resp.status, 'http_error', `Lỗi máy chủ (${resp.status})`)
  }
  return body as T
}

const json = (method: string, data: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data),
})

export const assetUrl = (assetId: string) => `${API_BASE}/assets/${assetId}/content`
export const downloadUrl = (assetId: string, format = 'original') => `${API_BASE}/assets/${assetId}/download?format=${format}`

export interface GenerationJob {
  id: string; project_id: string; purpose: string; provider: string; model: string; status: string
  output_asset_ids: string[]; reference_asset_ids: string[]
  error_message: string | null; error_code: string | null
  prompt: string; meta: Record<string, unknown>; settings: Record<string, unknown>
  estimated_cost_usd: number | null; actual_cost_usd: number | null
  attempts: number; max_attempts: number; cancel_requested: boolean
  created_at: string; updated_at: string
}

export interface ConceptProposal {
  id: string; run: number; slot: number; title: string
  brief: Record<string, string>; master_version_id: string; created_at: string
}

export interface Concept {
  id: string; run: number; slot: number; revision: number
  mood: string; camera: string; brief: Record<string, string>; stale: boolean
  master_version_id: string; turnaround_version_id: string | null; job: GenerationJob
}

export interface Enhancement {
  id: string; concept_id: string; number: number; stale: boolean; job: GenerationJob
}

export interface ReferencePlan {
  provider: string; model: string; size: string | null
  reference_asset_ids: string[]; reference_labels: string[]; omitted_asset_ids: string[]
  warning: string | null; estimated_cost_usd: number | null; master_version_id: string
}

export const api = {
  listProjects: () => request<ProjectSummary[]>('/projects'),
  getProject: (id: string) => request<ProjectDetail>(`/projects/${id}`),
  createProject: (data: { name: string; description?: string }) =>
    request<ProjectDetail>('/projects', json('POST', data)),
  updateProject: (
    id: string,
    data: Partial<Pick<ProjectDetail, 'name' | 'description' | 'rights_confirmed' | 'provider' | 'model' | 'workflow_mode' | 'preset_id'>>,
  ) =>
    request<ProjectDetail>(`/projects/${id}`, json('PATCH', data)),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: 'DELETE' }),
  uploadAssets: (projectId: string, files: File[], kind: AssetKind) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    form.append('kind', kind)
    return request<Asset[]>(`/projects/${projectId}/assets`, { method: 'POST', body: form })
  },
  reorderAssets: (projectId: string, assetIds: string[]) =>
    request<Asset[]>(`/projects/${projectId}/assets/order`, json('PUT', { asset_ids: assetIds })),
  setStepLead: (projectId: string, step: WorkflowStep, lead: string | null) =>
    request<ProjectDetail>(`/projects/${projectId}/step-lead`, json('PUT', { step, lead })),
  copyPrompts: (projectId: string, sourceProjectId: string) =>
    request<unknown>(`/projects/${projectId}/prompts/copy`, json('POST', { source_project_id: sourceProjectId })),
  setStepTemplate: (projectId: string, step: WorkflowStep, assetId: string | null) =>
    request<ProjectDetail>(`/projects/${projectId}/step-template`, json('PUT', { step, asset_id: assetId })),
  updateAsset: (assetId: string, patch: { kind?: AssetKind; selected?: boolean }) =>
    request<Asset>(`/assets/${assetId}`, json('PATCH', patch)),
  deleteAsset: (assetId: string) => request<void>(`/assets/${assetId}`, { method: 'DELETE' }),
  listPresets: () => request<Preset[]>('/presets'),
  savePreset: (preset: { id?: string; name: string; steps: Partial<Record<WorkflowStep, PresetStep>> }) =>
    request<Preset>(preset.id ? `/presets/${preset.id}` : '/presets',
      json(preset.id ? 'PUT' : 'POST', { name: preset.name, steps: preset.steps })),
  deletePreset: (id: string) => request<void>(`/presets/${id}`, { method: 'DELETE' }),
  listProviders: () => request<ProviderInfo[]>('/providers'),
  testProvider: (name: string) => request<ConnectionTestResult>(`/providers/${name}/test`, { method: 'POST' }),
  fetchProviderModels: (name: string) => request<CatalogueResult>(`/providers/${name}/models/fetch`, { method: 'POST' }),
  resetProviderModels: (name: string) => request<CatalogueResult>(`/providers/${name}/models/fetch`, { method: 'DELETE' }),
  getSpend: () => request<SpendInfo>('/spend'),
}

export const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})

const keys = {
  projects: ['projects'] as const,
  project: (id: string) => ['projects', id] as const,
}

export const useProjects = () => useQuery({ queryKey: keys.projects, queryFn: api.listProjects, refetchInterval: 5000 })

export const useProject = (id: string) => useQuery({ queryKey: keys.project(id), queryFn: () => api.getProject(id) })

export const usePresets = () => useQuery({ queryKey: ['presets'], queryFn: api.listPresets })

function usePresetMutation<T>(fn: (input: T) => Promise<unknown>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['presets'] })
      qc.invalidateQueries({ queryKey: keys.projects })
    },
  })
}

export const useSavePreset = () => usePresetMutation(api.savePreset)
export const useDeletePreset = () => usePresetMutation(api.deletePreset)

export const useProviders = () =>
  useQuery({ queryKey: ['providers'], queryFn: api.listProviders, staleTime: 5 * 60_000 })

export const useSpend = () => useQuery({ queryKey: ['spend'], queryFn: api.getSpend })

export const useTestProvider = () => useMutation({ mutationFn: api.testProvider })

function useCatalogueMutation(fn: (name: string) => Promise<CatalogueResult>) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: ['providers'] }) })
}

export const useFetchProviderModels = () => useCatalogueMutation(api.fetchProviderModels)
export const useResetProviderModels = () => useCatalogueMutation(api.resetProviderModels)

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.createProject,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.projects }),
  })
}

export function useDeleteProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.deleteProject,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.projects }),
  })
}

// Invalidates both the dashboard list and every project detail (prefix match).
function useInvalidatingMutation<TVars, TResult>(fn: (vars: TVars) => Promise<TResult>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSettled: () => qc.invalidateQueries({ queryKey: keys.projects }),
  })
}

export function useUpdateProject(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Parameters<typeof api.updateProject>[1]) => api.updateProject(projectId, data),
    onSuccess: (project) => {
      qc.setQueryData(keys.project(projectId), project)
      qc.invalidateQueries({ queryKey: ['estimate', projectId] })
      qc.invalidateQueries({ queryKey: ['enhance-plan', projectId] })
      qc.invalidateQueries({ queryKey: keys.projects, exact: true })
    },
  })
}

export const useUploadAssets = (projectId: string) =>
  useInvalidatingMutation(({ files, kind }: { files: File[]; kind: AssetKind }) =>
    api.uploadAssets(projectId, files, kind),
  )

export const useDeleteAsset = () => useInvalidatingMutation(api.deleteAsset)

export const useUpdateAssetKind = () =>
  useInvalidatingMutation(({ assetId, kind }: { assetId: string; kind: AssetKind }) =>
    api.updateAsset(assetId, { kind }),
  )

export function useSetStepLead(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ step, lead }: { step: WorkflowStep; lead: string | null }) => api.setStepLead(projectId, step, lead),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.project(projectId) }),
  })
}

export function useCopyPrompts(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (sourceProjectId: string) => api.copyPrompts(projectId, sourceProjectId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['prompt', projectId] }),
  })
}

export function useSetStepTemplate(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ step, assetId }: { step: WorkflowStep; assetId: string | null }) =>
      api.setStepTemplate(projectId, step, assetId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.project(projectId) }),
  })
}

export const useSelectAsset = () =>
  useInvalidatingMutation(({ assetId, selected }: { assetId: string; selected: boolean }) =>
    api.updateAsset(assetId, { selected }),
  )

export function useReorderAssets(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (assetIds: string[]) => api.reorderAssets(projectId, assetIds),
    onMutate: async (assetIds) => {
      await qc.cancelQueries({ queryKey: keys.project(projectId) })
      const previous = qc.getQueryData<ProjectDetail>(keys.project(projectId))
      if (previous) {
        const byId = new Map(previous.assets.map((a) => [a.id, a]))
        qc.setQueryData(keys.project(projectId), {
          ...previous,
          assets: assetIds.map((id, position) => ({ ...byId.get(id)!, position })),
        })
      }
      return { previous }
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previous) qc.setQueryData(keys.project(projectId), ctx.previous)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: keys.projects }),
  })
}
