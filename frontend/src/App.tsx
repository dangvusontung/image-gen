import Dashboard from '@/pages/Dashboard'
import ProjectWorkspace from '@/pages/ProjectWorkspace'
import { useHashRoute } from '@/lib/useHashRoute'

export default function App() {
  const { projectId, navigate } = useHashRoute()

  return (
    <div className="min-h-screen bg-muted/40">
      {projectId ? (
        <ProjectWorkspace key={projectId} projectId={projectId} onBack={() => navigate('/')} />
      ) : (
        <Dashboard onOpenProject={(id) => navigate(`/projects/${id}`)} />
      )}
    </div>
  )
}
