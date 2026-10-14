import { generationProject } from '@/lib/generationPolicy'
import { useEffect, useRef, useState } from 'react'
import { ArrowLeftIcon } from 'lucide-react'
import { request, usePresets, useProject, type GenerationJob } from '@/api/client'
import { useQuery } from '@tanstack/react-query'
import { ErrorAlert } from '@/components/ErrorAlert'
import { PromptEditor } from '@/components/GenerationUI'
import StepSources from '@/components/StepSources'
import ReferencesStep from '@/components/ReferencesStep'
import CharacterStep from '@/components/CharacterStep'
import GenerationMonitor from '@/components/GenerationMonitor'
import PinnedModelSwitcher from '@/components/PinnedModelSwitcher'
import ProjectSwitcher from '@/components/ProjectSwitcher'
import ConceptsStep from '@/components/ConceptsStep'
import EnhanceStep from '@/components/EnhanceStep'
import HistoryStep from '@/components/HistoryStep'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

/** Which tab a finished or running job belongs to. */
const STEP_OF_PURPOSE: Record<string, string> = {
  master: 'master', turnaround: 'turnaround', concept: 'concepts', enhance: 'enhance',
}

const STEPS = [
  { value: 'references', label: '1. Ảnh tham chiếu' },
  { value: 'master', label: '2. Nhân vật gốc' },
  { value: 'turnaround', label: '3. Turnaround (tùy chọn)' },
  { value: 'concepts', label: '4. Concept' },
  { value: 'enhance', label: '5. Nâng cấp' },
  { value: 'history', label: 'Lịch sử' },
]

export default function ProjectWorkspace({ projectId, onBack }: { projectId: string; onBack: () => void }) {
  const [step, setStep] = useState('references')
  const [selectedConceptId, setSelectedConceptId] = useState<string | null>(null)
  const { data: savedProject, isPending, error } = useProject(projectId)

  const { data: presets } = usePresets()
  const project = savedProject ? { ...savedProject, preset_steps: presets?.find(p => p.id === savedProject.preset_id)?.steps } : undefined

  // Open where the work left off, but never yank the tab out from under the user.
  const chosen = useRef(false)
  const latest = useQuery({
    queryKey: ['latest-job', projectId],
    queryFn: () => request<GenerationJob[]>(`/projects/${projectId}/jobs?limit=1`),
  })
  useEffect(() => {
    if (chosen.current || !latest.data) return
    chosen.current = true
    const resume = STEP_OF_PURPOSE[latest.data[0]?.purpose ?? '']
    if (resume) setStep(resume)
  }, [latest.data])

  const pickStep = (value: string) => { chosen.current = true; setStep(value) }

  return (
    // Bottom padding keeps the floating switcher and job monitor clear of page content.
    <main className="mx-auto max-w-7xl px-6 pt-8 pb-28">
      <Button variant="ghost" onClick={onBack} className="mb-4">
        <ArrowLeftIcon /> Tất cả dự án
      </Button>

      {isPending && <Skeleton className="h-96 rounded-xl" />}
      {error && <ErrorAlert title="Không mở được dự án" error={error} />}

      {project && (
        <>
          <header className="mb-6 grid gap-4">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">{project.name}</h1>
              {project.description && <p className="mt-1 text-muted-foreground">{project.description}</p>}
            </div>
            <div className="flex flex-wrap gap-4 text-sm">
              <a className="underline" href={`/api/projects/${projectId}/export`}>Tải toàn bộ dự án (ZIP)</a>
            </div>
          </header>

          <Tabs value={step} onValueChange={pickStep}>
            <TabsList className="flex-wrap">
              {STEPS.map((s) => (
                <TabsTrigger key={s.value} value={s.value}>
                  {s.label}
                </TabsTrigger>
              ))}
            </TabsList>
            <TabsContent value="references" className="mt-4">
              <ReferencesStep project={project} />
              <Button className="mt-5" disabled={!project.rights_confirmed || !project.assets.length} onClick={() => pickStep('master')}>Tiếp tục → Nhân vật gốc</Button>
            </TabsContent>
            {(['master', 'turnaround'] as const).map(step => <TabsContent key={step} value={step} className="mt-4 grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
              <div className="min-w-0 space-y-5"><PromptEditor projectId={project.id} name={step} />
              <CharacterStep onSkip={step === 'turnaround' ? () => pickStep('concepts') : undefined} onApproved={() => pickStep(step === 'master' ? 'turnaround' : 'concepts')} key={`${project.preset_id}/${JSON.stringify(project.preset_steps)}/${project.workflow_mode}/${project.provider}/${project.model}`} project={generationProject(project, step === 'turnaround' ? 'turnaround' : 'master')} step={step} /></div>
              <aside className="min-w-0 xl:sticky xl:top-4"><StepSources project={project} step={step} onBack={() => pickStep(step === 'master' ? 'references' : 'master')} /></aside>
            </TabsContent>)}
            <TabsContent value="concepts" className="mt-4 grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
              <div className="min-w-0 space-y-5">
              <ConceptsStep key={`${project.preset_id}/${JSON.stringify(project.preset_steps)}/${project.workflow_mode}/${project.provider}/${project.model}`} project={generationProject(project, 'concept')} onEnhance={id => { setSelectedConceptId(id); pickStep('enhance') }} /></div>
              <aside className="min-w-0 xl:sticky xl:top-4"><StepSources project={project} step="concepts" onBack={() => pickStep('turnaround')} /></aside>
            </TabsContent>
            <TabsContent value="enhance" className="mt-4 space-y-5">
              <PromptEditor projectId={project.id} name="enhance" />
              <EnhanceStep onBack={() => pickStep('concepts')} key={`${project.preset_id}/${JSON.stringify(project.preset_steps)}/${project.workflow_mode}/${project.provider}/${project.model}`} project={generationProject(project, 'enhance')} selectedConceptId={selectedConceptId} onSelect={setSelectedConceptId} />
            </TabsContent>
            <TabsContent value="history" className="mt-4"><HistoryStep projectId={projectId} /></TabsContent>
          </Tabs>
          <GenerationMonitor projectId={projectId} projectName={project.name} />
          <PinnedModelSwitcher project={project} purpose={step === 'concepts' ? 'concept' : step === 'enhance' ? 'enhance' : step === 'turnaround' ? 'turnaround' : 'master'} />
          <ProjectSwitcher projectId={projectId} onOpen={(id) => { window.location.hash = `/projects/${id}` }} />
        </>
      )}
    </main>
  )
}
