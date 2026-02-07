import { FileText, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useLoggingResources } from '../hooks/useApi'

/**
 * Logging resources list page
 */
export default function LoggingPage() {
    const { data: loggingResources, isLoading, error } = useLoggingResources()

    return (
        <div>
            <div className="page-header">
                <div>
                    <h1 className="page-title">Logging Resources</h1>
                    <p className="page-description">Log aggregation sources for canary detection</p>
                </div>
                <Link to="/logging/new" className="btn btn-primary">
                    <Plus size={18} />
                    Add Source
                </Link>
            </div>

            <div className="card">
                {isLoading ? (
                    <p className="text-muted">Loading logging resources...</p>
                ) : error ? (
                    <p className="text-muted">Error loading logging resources</p>
                ) : loggingResources && loggingResources.length > 0 ? (
                    <div className="table-container">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Provider Type</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {loggingResources.map((log) => (
                                    <tr key={log.id}>
                                        <td>
                                            <div className="flex items-center gap-2">
                                                <FileText size={16} style={{ color: 'var(--color-accent)' }} />
                                                <span>{log.name}</span>
                                            </div>
                                        </td>
                                        <td>
                                            <span className={`badge badge-${getProviderBadge(log.provider_type)}`}>
                                                {log.provider_type}
                                            </span>
                                        </td>
                                        <td>
                                            <span className={`badge ${getStatusBadge(log.status)}`}>
                                                {log.status}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="empty-state">
                        <FileText className="empty-state-icon" />
                        <h3>No logging resources configured</h3>
                        <p>Add a logging source to start detecting canary access.</p>
                        <Link to="/logging/new" className="btn btn-primary" style={{ marginTop: '1rem' }}>
                            <Plus size={18} />
                            Add Logging Source
                        </Link>
                    </div>
                )}
            </div>
        </div>
    )
}

function getProviderBadge(provider: string): string {
    if (provider.includes('AWS') || provider.includes('CLOUDTRAIL')) return 'aws'
    if (provider.includes('GCP') || provider.includes('AUDIT')) return 'gcp'
    return 'neutral'
}

function getStatusBadge(status: string): string {
    switch (status) {
        case 'ACTIVE':
            return 'badge-success'
        case 'ERROR':
            return 'badge-error'
        default:
            return 'badge-neutral'
    }
}
