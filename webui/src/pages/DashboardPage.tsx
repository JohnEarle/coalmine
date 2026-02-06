import { Bird, Shield, AlertTriangle, Cloud } from 'lucide-react'
import { useCanaries, useAlerts, useAccounts } from '../hooks/useApi'
import { Link } from 'react-router-dom'

/**
 * Dashboard overview page with stats and recent activity
 */
export default function DashboardPage() {
    const { data: canaries, isLoading: canariesLoading } = useCanaries()
    const { data: alerts, isLoading: alertsLoading } = useAlerts()
    const { data: accounts, isLoading: accountsLoading } = useAccounts()

    // Calculate stats
    const totalCanaries = canaries?.length || 0
    const activeCanaries = canaries?.filter(c => c.status === 'ACTIVE').length || 0
    const newAlerts = alerts?.filter(a => a.status === 'NEW').length || 0
    const totalAccounts = accounts?.length || 0

    const isLoading = canariesLoading || alertsLoading || accountsLoading

    return (
        <div>
            <div className="page-header">
                <div>
                    <h1 className="page-title">Dashboard</h1>
                    <p className="page-description">Overview of your canary token infrastructure</p>
                </div>
            </div>

            {/* Stats Grid */}
            <div className="stats-grid">
                <div className="stat-card">
                    <div className="stat-icon accent">
                        <Bird size={24} />
                    </div>
                    <div className="stat-content">
                        <h3>{isLoading ? '...' : totalCanaries}</h3>
                        <p>Total Canaries</p>
                    </div>
                </div>

                <div className="stat-card">
                    <div className="stat-icon success">
                        <Shield size={24} />
                    </div>
                    <div className="stat-content">
                        <h3>{isLoading ? '...' : activeCanaries}</h3>
                        <p>Active Canaries</p>
                    </div>
                </div>

                <div className="stat-card">
                    <div className="stat-icon error">
                        <AlertTriangle size={24} />
                    </div>
                    <div className="stat-content">
                        <h3>{isLoading ? '...' : newAlerts}</h3>
                        <p>New Alerts</p>
                    </div>
                </div>

                <div className="stat-card">
                    <div className="stat-icon info">
                        <Cloud size={24} />
                    </div>
                    <div className="stat-content">
                        <h3>{isLoading ? '...' : totalAccounts}</h3>
                        <p>Accounts</p>
                    </div>
                </div>
            </div>

            {/* Recent Alerts */}
            <div className="card">
                <div className="card-header">
                    <h2 className="card-title">Recent Alerts</h2>
                    <Link to="/alerts" className="btn btn-ghost btn-sm">
                        View All
                    </Link>
                </div>

                {alertsLoading ? (
                    <p className="text-muted">Loading alerts...</p>
                ) : alerts && alerts.length > 0 ? (
                    <div className="table-container">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Canary</th>
                                    <th>Event</th>
                                    <th>Source IP</th>
                                    <th>Time</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {alerts.slice(0, 5).map((alert) => (
                                    <tr key={alert.id}>
                                        <td className="font-mono text-sm">{alert.canary_name || alert.canary_id}</td>
                                        <td>{alert.event_name || '-'}</td>
                                        <td className="font-mono text-sm">{alert.source_ip || '-'}</td>
                                        <td className="text-sm text-muted">
                                            {new Date(alert.timestamp).toLocaleString()}
                                        </td>
                                        <td>
                                            <span className={`badge ${getAlertStatusBadge(alert.status)}`}>
                                                {alert.status}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <p className="text-muted">No alerts yet. Your canaries are monitoring for suspicious activity.</p>
                )}
            </div>
        </div>
    )
}

function getAlertStatusBadge(status: string): string {
    switch (status) {
        case 'NEW':
            return 'badge-error'
        case 'ACKNOWLEDGED':
            return 'badge-warning'
        case 'RESOLVED':
            return 'badge-success'
        default:
            return 'badge-neutral'
    }
}
