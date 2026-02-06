import { Link } from 'react-router-dom'
import { Plus, Bird, Trash2, Zap } from 'lucide-react'
import { useCanaries, useDeleteCanary, useTriggerCanary } from '../hooks/useApi'
import { useResourceTypes } from '../hooks/useMeta'
import { useConfirm } from '../components/ConfirmModal'

/**
 * Canaries list page with create, delete, and trigger actions
 */
export default function CanariesPage() {
    const { data: canaries, isLoading, error } = useCanaries()
    const { data: resourceTypes } = useResourceTypes()
    const deleteCanary = useDeleteCanary()
    const triggerCanary = useTriggerCanary()
    const confirm = useConfirm()

    const handleDelete = async (id: string, name: string) => {
        const confirmed = await confirm({
            title: 'Delete Canary',
            message: `Are you sure you want to delete canary "${name}"?`,
            confirmText: 'Delete',
            dangerous: true,
        })
        if (confirmed) {
            try {
                await deleteCanary.mutateAsync(id)
            } catch {
                // Error is handled by mutation
            }
        }
    }

    const handleTrigger = async (id: string, name: string) => {
        const confirmed = await confirm({
            title: 'Trigger Test Alert',
            message: `Trigger test alert for "${name}"? This will simulate canary access.`,
            confirmText: 'Trigger',
        })
        if (confirmed) {
            try {
                await triggerCanary.mutateAsync(id)
            } catch {
                // Error is handled by mutation
            }
        }
    }

    // Get provider from resource type
    const getProvider = (resourceType: string): string => {
        const type = resourceTypes?.find(t => t.value === resourceType)
        return type?.provider || (resourceType.startsWith('AWS') ? 'AWS' : 'GCP')
    }

    return (
        <div>
            <div className="page-header">
                <div>
                    <h1 className="page-title">Canaries</h1>
                    <p className="page-description">Manage your canary token resources</p>
                </div>
                <Link to="/canaries/new" className="btn btn-primary">
                    <Plus size={18} />
                    Create Canary
                </Link>
            </div>

            <div className="card">
                {isLoading ? (
                    <p className="text-muted">Loading canaries...</p>
                ) : error ? (
                    <p className="text-muted">Error loading canaries</p>
                ) : canaries && canaries.length > 0 ? (
                    <div className="table-container">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Type</th>
                                    <th>Provider</th>
                                    <th>Status</th>
                                    <th>Resource ID</th>
                                    <th>Created</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {canaries.map((canary) => (
                                    <tr key={canary.id}>
                                        <td>
                                            <div className="flex items-center gap-2">
                                                <Bird size={16} style={{ color: 'var(--color-accent)' }} />
                                                <span className="font-mono">{canary.name}</span>
                                            </div>
                                        </td>
                                        <td>
                                            <span className="text-sm">{canary.resource_type}</span>
                                        </td>
                                        <td>
                                            <span className={`badge badge-${getProvider(canary.resource_type).toLowerCase()}`}>
                                                {getProvider(canary.resource_type)}
                                            </span>
                                        </td>
                                        <td>
                                            <span className={`badge ${getStatusBadge(canary.status)}`}>
                                                {canary.status}
                                            </span>
                                        </td>
                                        <td className="font-mono text-sm text-muted">
                                            {canary.current_resource_id || '-'}
                                        </td>
                                        <td className="text-sm text-muted">
                                            {new Date(canary.created_at).toLocaleDateString()}
                                        </td>
                                        <td>
                                            <div className="flex gap-2">
                                                <button
                                                    className="btn btn-ghost btn-sm"
                                                    onClick={() => handleTrigger(canary.id, canary.name)}
                                                    title="Trigger test"
                                                    disabled={canary.status !== 'ACTIVE'}
                                                >
                                                    <Zap size={16} />
                                                </button>
                                                <button
                                                    className="btn btn-ghost btn-sm"
                                                    onClick={() => handleDelete(canary.id, canary.name)}
                                                    title="Delete"
                                                    style={{ color: 'var(--color-error)' }}
                                                >
                                                    <Trash2 size={16} />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="empty-state">
                        <Bird className="empty-state-icon" />
                        <h3>No canaries yet</h3>
                        <p>Create your first canary to start monitoring for unauthorized access.</p>
                        <Link to="/canaries/new" className="btn btn-primary">
                            <Plus size={18} />
                            Create Canary
                        </Link>
                    </div>
                )}
            </div>
        </div>
    )
}

function getStatusBadge(status: string): string {
    switch (status) {
        case 'ACTIVE':
            return 'badge-success'
        case 'CREATING':
            return 'badge-info'
        case 'ERROR':
            return 'badge-error'
        case 'DRIFT':
            return 'badge-purple'
        case 'DELETING':
            return 'badge-warning'
        default:
            return 'badge-neutral'
    }
}
