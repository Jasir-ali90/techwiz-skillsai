import { useState, type ReactNode } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  BarChart3, Building2, ClipboardList, Compass, Cpu, FileDown, FileText, History, Inbox, LayoutDashboard, ListChecks,
  LogOut, Menu, Monitor, Moon, RefreshCw, Search, ShieldCheck, SlidersHorizontal, Sun, TrendingUp, type LucideIcon,
} from 'lucide-react'
import { GENERATORS, REVIEWERS, STAFF, useAuth, type UserType } from '../lib/auth'
import { applyTheme, getTheme, type Theme } from '../lib/theme'
import { Logo } from './Logo'
import { Alert, Avatar, humanize } from './ui'

type NavItem = { to: string; label: string; icon: LucideIcon; roles?: UserType[] }
const NAV: { title: string; items: NavItem[] }[] = [
  {
    title: 'Onboarding',
    items: [
      { to: '/', label: 'Overview', icon: LayoutDashboard, roles: STAFF },
      { to: '/me', label: 'My onboarding', icon: Compass, roles: ['EMPLOYEE'] },
      { to: '/plans', label: 'Training plans', icon: ClipboardList, roles: STAFF },
      { to: '/review', label: 'Review queue', icon: Inbox, roles: REVIEWERS },
      { to: '/progress', label: 'Employee progress', icon: TrendingUp, roles: STAFF },
    ],
  },
  {
    title: 'Knowledge',
    items: [
      { to: '/documents', label: 'Documents', icon: FileText, roles: STAFF },
      { to: '/search', label: 'Search documents', icon: Search },
      { to: '/matrix', label: 'Requirements', icon: ListChecks, roles: STAFF },
      { to: '/policy-updates', label: 'Policy updates', icon: RefreshCw, roles: GENERATORS },
    ],
  },
  {
    title: 'Insights',
    items: [
      { to: '/validation', label: 'Quality checks', icon: ShieldCheck, roles: STAFF },
      { to: '/dashboards', label: 'Role insights', icon: BarChart3, roles: STAFF },
      { to: '/reports', label: 'Reports', icon: FileDown, roles: STAFF },
    ],
  },
  {
    title: 'Settings',
    items: [
      { to: '/organization', label: 'Organization', icon: Building2, roles: STAFF },
      { to: '/ai', label: 'AI settings', icon: Cpu, roles: STAFF },
      { to: '/config', label: 'Configuration', icon: SlidersHorizontal, roles: STAFF },
      { to: '/audit', label: 'Activity log', icon: History, roles: STAFF },
    ],
  },
]

const THEMES: { id: Theme; icon: LucideIcon; label: string }[] = [
  { id: 'light', icon: Sun, label: 'Light' },
  { id: 'dark', icon: Moon, label: 'Dark' },
  { id: 'system', icon: Monitor, label: 'Match system' },
]

function ThemeSwitch() {
  const [theme, setTheme] = useState<Theme>(getTheme)
  return (
    <div className="segmented" role="radiogroup" aria-label="Colour theme">
      {THEMES.map((t) => (
        <button
          key={t.id}
          role="radio"
          aria-checked={theme === t.id}
          title={t.label}
          aria-label={t.label}
          className={theme === t.id ? 'on' : ''}
          onClick={() => { setTheme(t.id); applyTheme(t.id) }}
        >
          <t.icon size={14} />
        </button>
      ))}
    </div>
  )
}

export function Layout() {
  const { user, logout, can } = useAuth()
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const visible = (i: NavItem) => !i.roles || can(...i.roles)

  return (
    <div className="shell">
      <div className={`scrim ${open ? 'open' : ''}`} onClick={() => setOpen(false)} />
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="brand">
          <Logo height={36} />
          <div className="brand-sub">Nexora Labs onboarding</div>
        </div>
        {NAV.map((group) => {
          const items = group.items.filter(visible)
          if (!items.length) return null
          return (
            <nav className="nav-group" key={group.title} aria-label={group.title}>
              <div className="nav-title">{group.title}</div>
              {items.map((i) => (
                <NavLink key={i.to} to={i.to} end={i.to === '/'} onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                  <i.icon size={17} aria-hidden />
                  {i.label}
                </NavLink>
              ))}
            </nav>
          )
        })}
        <div className="sidebar-foot">
          <div className="user-card">
            <Avatar name={user?.full_name} />
            <div className="user-meta">
              <div className="user-name">{user?.full_name}</div>
              <div className="user-role">{humanize(user?.user_type ?? '')}</div>
            </div>
            <button className="icon-btn" onClick={logout} title="Sign out" aria-label="Sign out">
              <LogOut size={16} />
            </button>
          </div>
          <div className="row between" style={{ padding: '6px 8px 2px' }}>
            <span className="small subtle">Theme</span>
            <ThemeSwitch />
          </div>
        </div>
      </aside>
      <div className="main">
        <div className="topbar">
          <button className="icon-btn" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu size={20} />
          </button>
          <Logo height={28} />
        </div>
        <main className="content" key={location.pathname}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export function RequireRole({ roles, children }: { roles: UserType[]; children: ReactNode }) {
  const { can } = useAuth()
  if (!can(...roles)) return <Alert kind="warn">Your account doesn't have access to this page. Ask an administrator if you need it.</Alert>
  return <>{children}</>
}
