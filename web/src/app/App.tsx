import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Shell } from './Shell'

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } })

function Placeholder({ title }: { title: string }) {
  return <h1 className="page-title">{title}</h1>
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Shell>
          <Routes>
            <Route path="/" element={<Navigate to="/projects" replace />} />
            <Route path="/projects" element={<Placeholder title="Projects" />} />
            <Route path="/projects/new" element={<Placeholder title="Project baru" />} />
            <Route path="/projects/:id" element={<Placeholder title="Project" />} />
            <Route path="/templates" element={<Placeholder title="Templates" />} />
            <Route path="/system" element={<Placeholder title="System" />} />
          </Routes>
        </Shell>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
