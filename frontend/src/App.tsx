import Dashboard from '@/pages/Dashboard'
import ProjectWorkspace from '@/pages/ProjectWorkspace'
import ProviderSettings from '@/pages/ProviderSettings'
import { useHashRoute } from '@/lib/useHashRoute'

export default function App() {
  const { route, navigate } = useHashRoute()
  const home = () => navigate('/')

  return (
    <div className="min-h-screen bg-muted/40">
      {route.page === 'project' && <ProjectWorkspace key={route.projectId} projectId={route.projectId} onBack={home} />}
      {route.page === 'settings' && <ProviderSettings onBack={home} />}
      {route.page === 'dashboard' && (
        <Dashboard onOpenProject={(id) => navigate(`/projects/${id}`)} onOpenSettings={() => navigate('/settings')} />
      )}
    </div>
  )
}
