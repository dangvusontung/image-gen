import { generationProject } from '@/lib/generationPolicy'
import { useState } from 'react'
import { ArrowLeftIcon } from 'lucide-react'
import { useProject } from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'
import ProviderPicker from '@/components/ProviderPicker'
import StepSources from '@/components/StepSources'
import ReferencesStep from '@/components/ReferencesStep'
import CharacterStep from '@/components/CharacterStep'
import ConceptsStep from '@/components/ConceptsStep'
import EnhanceStep from '@/components/EnhanceStep'
import HistoryStep from '@/components/HistoryStep'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

const STEPS = [
  { value: 'references', label: '1. Ảnh tham chiếu' },
  { value: 'master', label: '2. Nhân vật gốc' },
  { value: 'turnaround', label: '3. Turnaround' },
  { value: 'concepts', label: '4. Concept' },
  { value: 'enhance', label: '5. Nâng cấp' },
  { value: 'history', label: 'Lịch sử' },
]

export default function ProjectWorkspace({ projectId, onBack }: { projectId: string; onBack: () => void }) {
  const [step, setStep] = useState('references')
  const [selectedConceptId, setSelectedConceptId] = useState<string | null>(null)
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
          <header className="mb-6 grid gap-4">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">{project.name}</h1>
              {project.description && <p className="mt-1 text-muted-foreground">{project.description}</p>}
            </div>
            <ProviderPicker project={project} />
            <div className="flex flex-wrap gap-4 text-sm">
              <a className="underline" href={`/api/projects/${projectId}/export`}>Tải toàn bộ dự án (ZIP)</a>
            </div>
          </header>

          <Tabs value={step} onValueChange={setStep}>
            <TabsList className="flex-wrap">
              {STEPS.map((s) => (
                <TabsTrigger key={s.value} value={s.value}>
                  {s.label}
                </TabsTrigger>
              ))}
            </TabsList>
            <TabsContent value="references" className="mt-4">
              <ReferencesStep project={project} />
              <Button className="mt-5" disabled={!project.rights_confirmed || !project.assets.length} onClick={() => setStep('master')}>Tiếp tục → Nhân vật gốc</Button>
            </TabsContent>
            {(['master', 'turnaround'] as const).map(step => <TabsContent key={step} value={step} className="mt-4">
              <StepSources project={project} step={step} onBack={() => setStep(step === 'master' ? 'references' : 'master')} />
              <CharacterStep onApproved={() => setStep(step === 'master' ? 'turnaround' : 'concepts')} key={`${project.workflow_mode}/${project.provider}/${project.model}`} project={generationProject(project, 'draft')} step={step} />
            </TabsContent>)}
            <TabsContent value="concepts" className="mt-4">
              <StepSources project={project} step="concepts" onBack={() => setStep('turnaround')} />
              <ConceptsStep key={`${project.workflow_mode}/${project.provider}/${project.model}`} project={generationProject(project, 'draft')} onEnhance={id => { setSelectedConceptId(id); setStep('enhance') }} />
            </TabsContent>
            <TabsContent value="enhance" className="mt-4">
              <EnhanceStep onBack={() => setStep('concepts')} key={`${project.workflow_mode}/${project.provider}/${project.model}`} project={generationProject(project, 'enhance')} selectedConceptId={selectedConceptId} onSelect={setSelectedConceptId} />
            </TabsContent>
            <TabsContent value="history" className="mt-4"><HistoryStep projectId={projectId} /></TabsContent>
          </Tabs>
        </>
      )}
    </main>
  )
}
