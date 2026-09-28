import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout, RequireRole } from './components/Layout'
import { Spinner } from './components/ui'
import { AuthProvider, GENERATORS, REVIEWERS, STAFF, useAuth } from './lib/auth'
import { AIPage } from './pages/AIPage'
import { AuditPage } from './pages/AuditPage'
import { ConfigPage } from './pages/ConfigPage'
import { DashboardsPage } from './pages/DashboardsPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { LoginPage } from './pages/LoginPage'
import { MatrixPage } from './pages/MatrixPage'
import { MyOnboardingPage } from './pages/MyOnboardingPage'
import { OrganizationPage } from './pages/OrganizationPage'
import { OverviewPage } from './pages/OverviewPage'
import { PlanDetailPage } from './pages/PlanDetailPage'
import { PlansPage } from './pages/PlansPage'
import { PolicyUpdatesPage } from './pages/PolicyUpdatesPage'
import { ProgressPage } from './pages/ProgressPage'
import { ReportsPage } from './pages/ReportsPage'
import { ReviewPage } from './pages/ReviewPage'
import { SearchPage } from './pages/SearchPage'
import { ValidationPage } from './pages/ValidationPage'

function Home() {
  const { can } = useAuth()
  return can('EMPLOYEE') ? <Navigate to="/me" replace /> : <OverviewPage />
}

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="full-center"><Spinner label="Loading…" /></div>
  return user ? children : <Navigate to="/login" replace />
}

function LoginRoute() {
  const { user, loading } = useAuth()
  if (loading) return null
  return user ? <Navigate to="/" replace /> : <LoginPage />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginRoute />} />
          <Route element={<Protected><Layout /></Protected>}>
            <Route index element={<Home />} />
            <Route path="me" element={<RequireRole roles={['EMPLOYEE']}><MyOnboardingPage /></RequireRole>} />
            <Route path="plans" element={<RequireRole roles={STAFF}><PlansPage /></RequireRole>} />
            <Route path="plans/:id" element={<RequireRole roles={STAFF}><PlanDetailPage /></RequireRole>} />
            <Route path="review" element={<RequireRole roles={REVIEWERS}><ReviewPage /></RequireRole>} />
            <Route path="progress" element={<RequireRole roles={STAFF}><ProgressPage /></RequireRole>} />
            <Route path="documents" element={<RequireRole roles={STAFF}><DocumentsPage /></RequireRole>} />
            <Route path="search" element={<SearchPage />} />
            <Route path="matrix" element={<RequireRole roles={STAFF}><MatrixPage /></RequireRole>} />
            <Route path="policy-updates" element={<RequireRole roles={GENERATORS}><PolicyUpdatesPage /></RequireRole>} />
            <Route path="validation" element={<RequireRole roles={STAFF}><ValidationPage /></RequireRole>} />
            <Route path="dashboards" element={<RequireRole roles={STAFF}><DashboardsPage /></RequireRole>} />
            <Route path="reports" element={<RequireRole roles={STAFF}><ReportsPage /></RequireRole>} />
            <Route path="organization" element={<RequireRole roles={STAFF}><OrganizationPage /></RequireRole>} />
            <Route path="ai" element={<RequireRole roles={STAFF}><AIPage /></RequireRole>} />
            <Route path="config" element={<RequireRole roles={STAFF}><ConfigPage /></RequireRole>} />
            <Route path="audit" element={<RequireRole roles={STAFF}><AuditPage /></RequireRole>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
