import { ArrowLeftIcon } from 'lucide-react'
import { useProject } from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'
import ReferencesStep from '@/components/ReferencesStep'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

const STEPS = [
  { value: 'references', label: '1. Ảnh tham chiếu', ready: true },
  { value: 'master', label: '2. Nhân vật gốc', ready: false },
  { value: 'turnaround', label: '3. Turnaround', ready: false },
  { value: 'concepts', label: '4. Concept', ready: false },
  { value: 'enhance', label: '5. Nâng cấp', ready: false },
  { value: 'history', label: 'Lịch sử', ready: false },
]

export default function ProjectWorkspace({ projectId, onBack }: { projectId: string; onBack: () => void }) {
  const { data: project, isPending, error } = useProject(projectId)

  return (
    <main className="mx-auto max-w-7xl px-6 py-8">
      <Button variant="ghost" onClick={onBack} className="mb-4">
        <ArrowLeftIcon /> Tất cả dự án
      </Button>

      {isPending && <Skeleton className="h-96 rounded-xl" />}
      {error && <ErrorAlert title="Không mở được dự án" error={error} />}

      {project && (
        <>
          <header className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight">{project.name}</h1>
            {project.description && <p className="mt-1 text-muted-foreground">{project.description}</p>}
          </header>

          <Tabs defaultValue="references">
            <TabsList className="flex-wrap">
              {STEPS.map((s) => (
                <TabsTrigger key={s.value} value={s.value} disabled={!s.ready} title={s.ready ? undefined : 'Sắp có'}>
                  {s.label}
                </TabsTrigger>
              ))}
            </TabsList>
            <TabsContent value="references" className="mt-4">
              <ReferencesStep project={project} />
            </TabsContent>
          </Tabs>
        </>
      )}
    </main>
  )
}
