// One function per backend operation, grouped by area. Pages call these, never fetch directly.
import { api, type Json } from './client'

export const auth = {
  login: (email: string, password: string) => api.post<{ access_token: string }>('/auth/login', { email, password }),
  me: () => api.get('/auth/me'),
}

export const org = {
  departments: () => api.get('/departments'),
  createDepartment: (b: Json) => api.post('/departments', b),
  roles: () => api.get('/roles'),
  createRole: (b: Json) => api.post('/roles', b),
  updateRole: (id: string, b: Json) => api.patch(`/roles/${id}`, b),
  stages: () => api.get('/stages'),
  createStage: (b: Json) => api.post('/stages', b),
  updateStage: (id: string, b: Json) => api.patch(`/stages/${id}`, b),
  employees: (q?: Json) => api.get('/employees', q),
  createEmployee: (b: Json) => api.post('/employees', b),
  updateEmployee: (id: string, b: Json) => api.patch(`/employees/${id}`, b),
}

export const documents = {
  list: (q?: Json) => api.get('/documents', q),
  get: (id: string) => api.get(`/documents/${id}`),
  versions: (id: string) => api.get(`/documents/${id}/versions`),
  upload: (form: FormData) => api.upload('/documents', form),
  parse: (id: string, force = false) => api.post(`/documents/${id}/parse`, undefined, { force }),
  chunks: (id: string, q?: Json) => api.get(`/documents/${id}/chunks`, q),
  suspicious: () => api.get('/documents/chunks/suspicious'),
  trace: (code: string) => api.get(`/documents/chunks/${encodeURIComponent(code)}/trace`),
}

export const search = {
  semantic: (q: Json) => api.get('/search', q),
  coverage: () => api.get('/search/coverage'),
  embedAll: (force = false) => api.post('/search/embed-all', undefined, { force }),
  embedDocument: (id: string, force = false) => api.post(`/search/embed/${id}`, undefined, { force }),
  records: (q: Json) => api.get('/search/records', q),
}

export const matrix = {
  extract: (b: Json = {}) => api.post('/matrix/extract', b),
  mapRoles: (b: Json = {}) => api.post('/matrix/map-roles', b),
  prerequisites: () => api.post('/matrix/prerequisites'),
  resolveConflicts: () => api.post('/matrix/resolve-conflicts'),
  summary: () => api.get('/matrix/summary'),
  role: (id: string) => api.get(`/matrix/role/${id}`),
  requirements: (q?: Json) => api.get('/requirements', q),
  requirement: (code: string) => api.get(`/requirements/${code}`),
  patchRequirement: (code: string, b: Json) => api.patch(`/requirements/${code}`, b),
  addRoleMapping: (code: string, b: Json) => api.post(`/requirements/${code}/roles`, b),
}

export const plans = {
  generate: (b: Json) => api.post('/plans/generate', b),
  list: (q?: Json) => api.get('/plans', q),
  get: (id: string) => api.get(`/plans/${id}`),
  generationRun: (id: string) => api.get(`/plans/${id}/generation-run`),
  outdated: (id: string) => api.get(`/plans/${id}/outdated`),
  compare: (q: Json) => api.get('/plans/compare', q),
  promptTemplates: () => api.get('/prompt-templates'),
}

export const validation = {
  run: (planId: string) => api.post(`/validation/run/${planId}`),
  result: (planId: string) => api.get(`/validation/${planId}`),
  findings: (planId: string, q?: Json) => api.get(`/validation/${planId}/findings`, q),
  rules: () => api.get('/validation/rules'),
  updateRules: (b: Json) => api.put('/validation/rules', b),
  contradictions: (includeObsolete = true) => api.get('/validation/contradictions', { include_obsolete: includeObsolete }),
}

export const review = {
  compare: (planId: string) => api.post(`/comparison/${planId}`),
  comparison: (planId: string) => api.get(`/comparison/${planId}`),
  exportComparison: (planId: string) => api.download(`/comparison/${planId}/export`, `comparison_${planId}.csv`),
  startConsistency: (planId: string, runCount: number) => api.post(`/consistency/${planId}`, { run_count: runCount }),
  consistency: (planId: string) => api.get(`/consistency/${planId}`),
  queue: (q?: Json) => api.get('/review/queue', q),
  decide: (findingId: string, b: Json) => api.post(`/review/${findingId}/decision`, b),
  audit: (type: string, id: string) => api.get(`/audit/${encodeURIComponent(type)}/${encodeURIComponent(id)}`),
}

export const progress = {
  get: (employeeId: string) => api.get(`/progress/${employeeId}`),
  setItem: (type: string, id: string, status: string) => api.post(`/progress/items/${type}/${id}`, { status }),
  attempt: (questionId: string, answer: string[]) => api.post(`/progress/quiz/${questionId}/attempt`, { answer }),
  assessment: (id: string, b: Json) => api.post(`/progress/assessments/${id}/result`, b),
  me: () => api.get('/dashboard/me'),
  employeeDashboard: (id: string) => api.get(`/dashboard/employee/${id}`),
  admin: () => api.get('/dashboard/admin'),
  roles: () => api.get('/dashboard/roles'),
  role: (id: string) => api.get(`/dashboard/role/${id}`),
}

export const impact = {
  analyse: (docId: string) => api.post(`/impact/analyse/${docId}`),
  get: (docId: string) => api.get(`/impact/${docId}`),
  affected: (docId: string) => api.get(`/impact/${docId}/affected`),
  regenerate: (docId: string, dryRun: boolean) => api.post(`/impact/${docId}/regenerate`, undefined, { dry_run: dryRun }),
}

export const reports = {
  list: () => api.get('/reports'),
  get: (name: string) => api.get(`/reports/${name}`),
  download: (name: string, format: string) => api.download(`/reports/${name}`, `${name}.${format}`, { format }),
}

export const config = {
  keys: () => api.get('/config'),
  get: (key: string) => api.get(`/config/${key}`),
  put: (key: string, value: Json) => api.put(`/config/${key}`, value),
  reset: (key: string) => api.del(`/config/${key}`),
  reapplyPrecedence: () => api.post('/config/precedence/reapply'),
  resolvePrecedence: (ids: string[]) => api.post('/config/precedence/resolve', ids),
}

export const genai = {
  status: () => api.get('/genai/status'),
  test: (provider: string) => api.post(`/genai/test/${provider}`),
}

export const health = () => api.get('/health')
