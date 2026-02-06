import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import { AuthProvider } from './context/AuthContext'
import { ConfirmProvider } from './components/ConfirmModal'
import Layout from './components/layout/Layout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import CanariesPage from './pages/CanariesPage'
import CanaryCreatePage from './pages/CanaryCreatePage'
import AccountsPage from './pages/AccountsPage'
import AlertsPage from './pages/AlertsPage'
import LoggingPage from './pages/LoggingPage'
import CredentialsPage from './pages/CredentialsPage'

/**
 * Protected route wrapper - redirects to login if not authenticated
 */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
    const { isAuthenticated, isLoading } = useAuth()

    if (isLoading) {
        return (
            <div className="loading-screen">
                <div className="loading-spinner" />
                <p>Loading...</p>
            </div>
        )
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />
    }

    return <>{children}</>
}

/**
 * Main App component with routing
 */
function AppRoutes() {
    return (
        <Routes>
            {/* Public routes */}
            <Route path="/login" element={<LoginPage />} />

            {/* Protected routes - wrapped in Layout */}
            <Route
                path="/"
                element={
                    <ProtectedRoute>
                        <Layout />
                    </ProtectedRoute>
                }
            >
                <Route index element={<DashboardPage />} />
                <Route path="canaries" element={<CanariesPage />} />
                <Route path="canaries/new" element={<CanaryCreatePage />} />
                <Route path="credentials" element={<CredentialsPage />} />
                <Route path="accounts" element={<AccountsPage />} />
                <Route path="logging" element={<LoggingPage />} />
                <Route path="alerts" element={<AlertsPage />} />
            </Route>

            {/* Catch-all redirect */}
            <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    )
}

export default function App() {
    return (
        <ConfirmProvider>
            <AuthProvider>
                <AppRoutes />
            </AuthProvider>
        </ConfirmProvider>
    )
}
