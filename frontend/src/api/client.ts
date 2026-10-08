import { QueryClient, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

const API_BASE = '/api'

export type AssetKind = 'reference' | 'side_profile'

export interface Asset {
  id: string
  kind: AssetKind
  filename: string
  size: number
  content_type: string
  width: number | null
  height: number | null
  position: number
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
}

export interface ProjectDetail {
  id: string
  name: string
  description: string | null
  rights_confirmed: boolean
  provider: string
  model: string
  created_at: string
  updated_at: string
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
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

export const api = {
  listProjects: () => request<ProjectSummary[]>('/projects'),
  getProject: (id: string) => request<ProjectDetail>(`/projects/${id}`),
  createProject: (data: { name: string; description?: string }) =>
    request<ProjectDetail>('/projects', json('POST', data)),
  updateProject: (
    id: string,
    data: Partial<Pick<ProjectDetail, 'name' | 'description' | 'rights_confirmed' | 'provider' | 'model'>>,
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
  updateAsset: (assetId: string, kind: AssetKind) => request<Asset>(`/assets/${assetId}`, json('PATCH', { kind })),
  deleteAsset: (assetId: string) => request<void>(`/assets/${assetId}`, { method: 'DELETE' }),
  listProviders: () => request<ProviderInfo[]>('/providers'),
  testProvider: (name: string) => request<ConnectionTestResult>(`/providers/${name}/test`, { method: 'POST' }),
  getSpend: () => request<SpendInfo>('/spend'),
}

export const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})

const keys = {
  projects: ['projects'] as const,
  project: (id: string) => ['projects', id] as const,
}

export const useProjects = () => useQuery({ queryKey: keys.projects, queryFn: api.listProjects })

export const useProject = (id: string) => useQuery({ queryKey: keys.project(id), queryFn: () => api.getProject(id) })

export const useProviders = () =>
  useQuery({ queryKey: ['providers'], queryFn: api.listProviders, staleTime: 5 * 60_000 })

export const useSpend = () => useQuery({ queryKey: ['spend'], queryFn: api.getSpend })

export const useTestProvider = () => useMutation({ mutationFn: api.testProvider })

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
    api.updateAsset(assetId, kind),
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
