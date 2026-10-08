import { useQuery } from '@tanstack/react-query'
import { request, type GenerationJob } from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'
import { DownloadLinks, ImagePreview, JobDetails } from '@/components/GenerationUI'

export default function HistoryStep({ projectId }: { projectId: string }) {
  const jobs = useQuery({ queryKey: ['jobs', projectId], queryFn: () => request<GenerationJob[]>(`/projects/${projectId}/jobs?limit=500`), refetchInterval: 1500 })
  const workflow = useQuery({ queryKey: ['workflow', projectId], queryFn: () => request<{ approvals: { target_type: string; target_id: string; created_at: string }[] }>(`/projects/${projectId}/workflow`), refetchInterval: 1500 })
  const purpose: Record<string, string> = { master: 'Nhân vật gốc', turnaround: 'Turnaround', concept: 'Concept', enhance: 'Nâng cấp' }
  return <section className="space-y-5">
    <h2 className="text-xl font-semibold">Lịch sử tạo ảnh và phê duyệt</h2>
    {jobs.error && <ErrorAlert error={jobs.error} title="Không tải được lịch sử job" />}
    {workflow.error && <ErrorAlert error={workflow.error} title="Không tải được phê duyệt" />}
    <details className="rounded-lg border p-4"><summary>Phê duyệt ({workflow.data?.approvals.length ?? 0})</summary>
      {workflow.data?.approvals.map((e, i) => <p className="mt-2 text-sm" key={i}>{new Date(e.created_at).toLocaleString('vi-VN')} · {purpose[e.target_type]} · {e.target_id}</p>)}
    </details>
    {jobs.isPending && <p>Đang tải lịch sử…</p>}
    {jobs.data?.length === 0 && <p>Chưa có lần tạo ảnh nào.</p>}
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">{jobs.data?.map(job => <article key={job.id} className="space-y-3 rounded-xl border p-4">
      <h3 className="font-medium">{purpose[job.purpose] ?? job.purpose} · {new Date(job.created_at).toLocaleString('vi-VN')}</h3>
      {job.output_asset_ids.map(id => <div key={id} className="space-y-2"><ImagePreview assetId={id} title={purpose[job.purpose] ?? 'Ảnh kết quả'} /><DownloadLinks assetId={id} /></div>)}
      <JobDetails job={job} projectId={projectId} />
    </article>)}</div>
    {(jobs.data?.length ?? 0) >= 500 && <p className="text-sm">Hiển thị 500 job gần nhất. Tải ZIP để lấy đầy đủ ảnh và lịch sử.</p>}
  </section>
}
