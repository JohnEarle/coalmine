import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import TaskActivity from '../TaskActivity'
import {
    LayoutDashboard,
    Bird,
    FileText,
    AlertTriangle,
    LogOut,
    User,
    Users,
    Key,
    KeyRound,
    Building2,
} from 'lucide-react'

/**
 * Main application layout with sidebar navigation
 */
export default function Layout() {
    const { user, logout } = useAuth()
    const navigate = useNavigate()

    const handleLogout = async () => {
        await logout()
        navigate('/login')
    }

    return (
        <div className="app-layout">
            {/* Sidebar */}
            <aside className="sidebar">
                <div className="sidebar-header">
                    <Bird className="sidebar-logo" />
                    <span className="sidebar-title">Coalmine</span>
                </div>

                <nav className="sidebar-nav">
                    <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                        <LayoutDashboard />
                        <span>Dashboard</span>
                    </NavLink>

                    <NavLink to="/canaries" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                        <Bird />
                        <span>Canaries</span>
                    </NavLink>

                    <div className="nav-section">Cloud</div>

                    <NavLink to="/credentials" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                        <Key />
                        <span>Credentials</span>
                    </NavLink>

                    <NavLink to="/accounts" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                        <Building2 />
                        <span>Accounts</span>
                    </NavLink>

                    <NavLink to="/logging" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                        <FileText />
                        <span>Logging</span>
                    </NavLink>

                    <div className="nav-section">Security</div>

                    <NavLink to="/alerts" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                        <AlertTriangle />
                        <span>Alerts</span>
                    </NavLink>

                    <NavLink to="/users" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                        <Users />
                        <span>Users</span>
                    </NavLink>

                    <NavLink to="/api-keys" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                        <KeyRound />
                        <span>API Keys</span>
                    </NavLink>
                </nav>

                <div className="sidebar-footer">
                    <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                            <User size={18} />
                            <span className="text-sm">{user?.username}</span>
                        </div>
                        <button className="btn btn-ghost btn-sm" onClick={handleLogout} title="Logout">
                            <LogOut size={18} />
                        </button>
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="main-content">
                <TaskActivity />
                <div className="page-content">
                    <Outlet />
                </div>
            </main>
        </div>
    )
}
