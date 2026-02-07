import { useParams, Link, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { Bird, ArrowLeft, Copy, Download, Trash2, Zap, Key, CheckCircle, Clock, AlertCircle } from 'lucide-react'
import { useCanary, useCanaryCredentials, useDeleteCanary, useTriggerCanary } from '../hooks/useApi'
import { useResourceTypes } from '../hooks/useMeta'
import { useConfirm } from '../components/ConfirmModal'

/**
 * Canary detail page with metadata and credentials viewing
 */
export default function CanaryDetailPage() {
    const { id } = useParams<{ id: string }>()
    const navigate = useNavigate()
    const { data: canary, isLoading, error } = useCanary(id)
    const { data: credentialsData, isLoading: credsLoading } = useCanaryCredentials(id)
    const { data: resourceTypes } = useResourceTypes()
    const deleteCanary = useDeleteCanary()
    const triggerCanary = useTriggerCanary()
    const confirm = useConfirm()
    const [copied, setCopied] = useState<string | null>(null)

    const handleDelete = async () => {
        if (!canary) return
        const confirmed = await confirm({
            title: 'Delete Canary',
            message: `Are you sure you want to delete canary "${canary.name}"? This will remove the cloud resource.`,
            confirmText: 'Delete',
            dangerous: true,
        })
        if (confirmed) {
            try {
                await deleteCanary.mutateAsync(canary.id)
                navigate('/canaries')
            } catch {
                // Error handled by mutation
            }
        }
    }

    const handleTrigger = async () => {
        if (!canary) return
        const confirmed = await confirm({
            title: 'Trigger Test Alert',
            message: `Trigger test alert for "${canary.name}"? This will simulate unauthorized access.`,
            confirmText: 'Trigger',
        })
        if (confirmed) {
            try {
                await triggerCanary.mutateAsync(canary.id)
            } catch {
                // Error handled by mutation
            }
        }
    }

    const copyToClipboard = async (text: string, key: string) => {
        try {
            await navigator.clipboard.writeText(text)
            setCopied(key)
            setTimeout(() => setCopied(null), 2000)
        } catch (err) {
            console.error('Failed to copy:', err)
        }
    }

    const downloadAsFile = (content: string, filename: string) => {
        const blob = new Blob([content], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = filename
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
    }

    const getProvider = (resourceType: string): string => {
        const type = resourceTypes?.find(t => t.value === resourceType)
        return type?.provider || (resourceType.startsWith('AWS') ? 'AWS' : 'GCP')
    }

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'ACTIVE':
                return <CheckCircle size={18} style={{ color: 'var(--color-success)' }} />
            case 'CREATING':
                return <Clock size={18} style={{ color: 'var(--color-info)' }} />
            case 'ERROR':
            case 'DRIFT':
                return <AlertCircle size={18} style={{ color: 'var(--color-error)' }} />
            default:
                return null
        }
    }

    if (isLoading) {
        return <div className="loading">Loading canary...</div>
    }

    if (error || !canary) {
        return (
            <div className="error-state">
                <AlertCircle size={48} />
                <h3>Canary not found</h3>
                <Link to="/canaries" className="btn btn-primary">Back to Canaries</Link>
            </div>
        )
    }

    const credentials = credentialsData?.credentials
    const isGcp = canary.resource_type.includes('GCP')
    const isAws = canary.resource_type.includes('AWS')

    return (
        <div>
            {/* Header */}
            <div className="page-header">
                <div className="flex items-center gap-4">
                    <Link to="/canaries" className="btn btn-ghost">
                        <ArrowLeft size={18} />
                    </Link>
                    <div>
                        <h1 className="page-title flex items-center gap-2">
                            <Bird size={24} style={{ color: 'var(--color-accent)' }} />
                            {canary.name}
                        </h1>
                        <p className="page-description">Canary resource details and credentials</p>
                    </div>
                </div>
                <div className="flex gap-2">
                    <button
                        className="btn btn-secondary"
                        onClick={handleTrigger}
                        disabled={canary.status !== 'ACTIVE'}
                    >
                        <Zap size={18} />
                        Trigger Test
                    </button>
                    <button
                        className="btn btn-danger"
                        onClick={handleDelete}
                    >
                        <Trash2 size={18} />
                        Delete
                    </button>
                </div>
            </div>

            {/* Metadata Card */}
            <div className="card" style={{ marginBottom: '1.5rem' }}>
                <h2 className="card-title">Details</h2>
                <div className="detail-grid">
                    <div className="detail-item">
                        <span className="detail-label">Status</span>
                        <span className="detail-value flex items-center gap-2">
                            {getStatusIcon(canary.status)}
                            <span className={`badge ${getStatusBadge(canary.status)}`}>
                                {canary.status}
                            </span>
                        </span>
                    </div>
                    <div className="detail-item">
                        <span className="detail-label">Resource Type</span>
                        <span className="detail-value">{canary.resource_type}</span>
                    </div>
                    <div className="detail-item">
                        <span className="detail-label">Provider</span>
                        <span className="detail-value">
                            <span className={`badge badge-${getProvider(canary.resource_type).toLowerCase()}`}>
                                {getProvider(canary.resource_type)}
                            </span>
                        </span>
                    </div>
                    <div className="detail-item">
                        <span className="detail-label">Account</span>
                        <span className="detail-value">{canary.account_name || '-'}</span>
                    </div>
                    <div className="detail-item">
                        <span className="detail-label">Resource ID</span>
                        <span className="detail-value font-mono text-sm">
                            {canary.current_resource_id || '-'}
                        </span>
                    </div>
                    <div className="detail-item">
                        <span className="detail-label">Created</span>
                        <span className="detail-value">
                            {new Date(canary.created_at).toLocaleString()}
                        </span>
                    </div>
                    {canary.expires_at && (
                        <div className="detail-item">
                            <span className="detail-label">Expires</span>
                            <span className="detail-value">
                                {new Date(canary.expires_at).toLocaleString()}
                            </span>
                        </div>
                    )}
                </div>
            </div>

            {/* Credentials Card */}
            <div className="card">
                <h2 className="card-title flex items-center gap-2">
                    <Key size={20} />
                    Credentials
                </h2>

                {credsLoading ? (
                    <p className="text-muted">Loading credentials...</p>
                ) : !credentials ? (
                    <div className="empty-state-small">
                        <p className="text-muted">No credentials available. The canary may still be creating.</p>
                    </div>
                ) : (
                    <div className="credentials-section">
                        {/* AWS Credentials */}
                        {isAws && (
                            <>
                                {Boolean(credentials.access_key_id) && (
                                    <div className="credential-item">
                                        <span className="credential-label">Access Key ID</span>
                                        <div className="credential-value-row">
                                            <code className="credential-value">{String(credentials.access_key_id)}</code>
                                            <button
                                                className="btn btn-ghost btn-sm"
                                                onClick={() => copyToClipboard(credentials.access_key_id as string, 'access_key_id')}
                                                title="Copy"
                                            >
                                                {copied === 'access_key_id' ? <CheckCircle size={16} /> : <Copy size={16} />}
                                            </button>
                                        </div>
                                    </div>
                                )}
                                {Boolean(credentials.secret_access_key) && (
                                    <div className="credential-item">
                                        <span className="credential-label">Secret Access Key</span>
                                        <div className="credential-value-row">
                                            <code className="credential-value credential-secret">
                                                {String(credentials.secret_access_key).substring(0, 8)}...
                                            </code>
                                            <button
                                                className="btn btn-ghost btn-sm"
                                                onClick={() => copyToClipboard(credentials.secret_access_key as string, 'secret_access_key')}
                                                title="Copy"
                                            >
                                                {copied === 'secret_access_key' ? <CheckCircle size={16} /> : <Copy size={16} />}
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </>
                        )}

                        {/* GCP Credentials */}
                        {isGcp && Boolean(credentials.service_account_key) && (
                            <div className="credential-item">
                                <span className="credential-label">Service Account Key (JSON)</span>
                                <div className="credential-value-row">
                                    <code className="credential-value">
                                        {canary.name}.json
                                    </code>
                                    <button
                                        className="btn btn-ghost btn-sm"
                                        onClick={() => copyToClipboard(
                                            JSON.stringify(credentials.service_account_key, null, 2),
                                            'sa_key'
                                        )}
                                        title="Copy JSON"
                                    >
                                        {copied === 'sa_key' ? <CheckCircle size={16} /> : <Copy size={16} />}
                                    </button>
                                    <button
                                        className="btn btn-secondary btn-sm"
                                        onClick={() => downloadAsFile(
                                            JSON.stringify(credentials.service_account_key, null, 2),
                                            `${canary.name}.json`
                                        )}
                                    >
                                        <Download size={16} />
                                        Download
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* GCP Service Account Email */}
                        {isGcp && Boolean(credentials.service_account_email) && (
                            <div className="credential-item">
                                <span className="credential-label">Service Account Email</span>
                                <div className="credential-value-row">
                                    <code className="credential-value">{String(credentials.service_account_email)}</code>
                                    <button
                                        className="btn btn-ghost btn-sm"
                                        onClick={() => copyToClipboard(credentials.service_account_email as string, 'sa_email')}
                                        title="Copy"
                                    >
                                        {copied === 'sa_email' ? <CheckCircle size={16} /> : <Copy size={16} />}
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Bucket Name (for bucket canaries) */}
                        {Boolean(credentials.bucket_name) && (
                            <div className="credential-item">
                                <span className="credential-label">Bucket Name</span>
                                <div className="credential-value-row">
                                    <code className="credential-value">{String(credentials.bucket_name)}</code>
                                    <button
                                        className="btn btn-ghost btn-sm"
                                        onClick={() => copyToClipboard(credentials.bucket_name as string, 'bucket_name')}
                                        title="Copy"
                                    >
                                        {copied === 'bucket_name' ? <CheckCircle size={16} /> : <Copy size={16} />}
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Raw JSON fallback for other credential types */}
                        {!isAws && !isGcp && (
                            <div className="credential-item">
                                <span className="credential-label">Raw Credentials</span>
                                <pre className="credential-json">
                                    {JSON.stringify(credentials, null, 2)}
                                </pre>
                            </div>
                        )}
                    </div>
                )}
            </div>

            <style>{`
                .detail-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                    gap: 1.5rem;
                }
                .detail-item {
                    display: flex;
                    flex-direction: column;
                    gap: 0.25rem;
                }
                .detail-label {
                    font-size: 0.75rem;
                    text-transform: uppercase;
                    color: var(--text-tertiary);
                    letter-spacing: 0.05em;
                }
                .detail-value {
                    font-size: 1rem;
                    color: var(--text-primary);
                }
                .card-title {
                    font-size: 1.125rem;
                    font-weight: 600;
                    margin-bottom: 1rem;
                    color: var(--text-primary);
                }
                .credentials-section {
                    display: flex;
                    flex-direction: column;
                    gap: 1rem;
                }
                .credential-item {
                    display: flex;
                    flex-direction: column;
                    gap: 0.5rem;
                    padding: 1rem;
                    background: var(--bg-elevated);
                    border-radius: 0.5rem;
                    border: 1px solid var(--border-subtle);
                }
                .credential-label {
                    font-size: 0.875rem;
                    font-weight: 500;
                    color: var(--text-secondary);
                }
                .credential-value-row {
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                }
                .credential-value {
                    flex: 1;
                    font-family: var(--font-mono);
                    font-size: 0.875rem;
                    color: var(--text-primary);
                    word-break: break-all;
                }
                .credential-secret {
                    color: var(--text-tertiary);
                }
                .credential-json {
                    background: var(--bg-code);
                    padding: 1rem;
                    border-radius: 0.375rem;
                    font-family: var(--font-mono);
                    font-size: 0.75rem;
                    overflow-x: auto;
                    margin: 0;
                }
                .empty-state-small {
                    padding: 2rem;
                    text-align: center;
                }
                .error-state {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    gap: 1rem;
                    padding: 4rem;
                    color: var(--text-secondary);
                }
                .btn-danger {
                    background: var(--color-error);
                    color: white;
                }
                .btn-danger:hover {
                    background: color-mix(in srgb, var(--color-error) 90%, black);
                }
            `}</style>
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
