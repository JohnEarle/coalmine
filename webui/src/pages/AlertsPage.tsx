import { AlertTriangle } from 'lucide-react'
import { useAlerts } from '../hooks/useApi'

/**
 * Alerts page showing security alerts from canary triggers
 */
export default function AlertsPage() {
    const { data: alerts, isLoading, error } = useAlerts()

    return (
        <div>
            <div className="page-header">
                <div>
                    <h1 className="page-title">Alerts</h1>
                    <p className="page-description">Security alerts from canary token access</p>
                </div>
            </div>

            <div className="card">
                {isLoading ? (
                    <p className="text-muted">Loading alerts...</p>
                ) : error ? (
                    <p className="text-muted">Error loading alerts</p>
                ) : alerts && alerts.length > 0 ? (
                    <div className="table-container">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Canary</th>
                                    <th>Event</th>
                                    <th>Source IP</th>
                                    <th>User Agent</th>
                                    <th>Time</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {alerts.map((alert) => (
                                    <tr key={alert.id}>
                                        <td className="font-mono text-sm">{alert.canary_name || alert.canary_id}</td>
                                        <td>{alert.event_name || '-'}</td>
                                        <td className="font-mono text-sm">{alert.source_ip || '-'}</td>
                                        <td className="text-sm text-muted" style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                            {alert.user_agent || '-'}
                                        </td>
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
                    <div className="empty-state">
                        <AlertTriangle className="empty-state-icon" />
                        <h3>No alerts yet</h3>
                        <p>Alerts will appear here when your canaries detect suspicious activity.</p>
                    </div>
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
