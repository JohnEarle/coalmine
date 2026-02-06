import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Key, Plus, Trash2, Cloud, Shield } from 'lucide-react'

interface Credential {
    id: string
    name: string
    provider: string
    auth_type: string
    status: string
    account_count: number
    created_at: string
}

function useCredentials() {
    return useQuery({
        queryKey: ['credentials'],
        queryFn: async (): Promise<Credential[]> => {
            const response = await fetch('/api/v1/credentials/')
            if (!response.ok) throw new Error('Failed to fetch credentials')
            const data = await response.json()
            return data.credentials
        },
    })
}

function useDeleteCredential() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (id: string) => {
            const response = await fetch(`/api/v1/credentials/${id}`, { method: 'DELETE' })
            if (!response.ok) {
                const error = await response.json()
                throw new Error(error.detail || 'Failed to delete')
            }
            return response.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['credentials'] })
        },
    })
}

export default function CredentialsPage() {
    const { data: credentials, isLoading, error } = useCredentials()
    const deleteMutation = useDeleteCredential()
    const [showCreate, setShowCreate] = useState(false)

    if (isLoading) return <div className="loading">Loading credentials...</div>
    if (error) return <div className="error-message">Error loading credentials</div>

    const handleDelete = async (id: string, name: string) => {
        if (confirm(`Delete credential "${name}"? This will also delete all linked accounts.`)) {
            try {
                await deleteMutation.mutateAsync(id)
            } catch (err: unknown) {
                alert(err instanceof Error ? err.message : 'Failed to delete')
            }
        }
    }

    return (
        <div className="page">
            <div className="page-header">
                <h1><Key size={24} /> Credentials</h1>
                <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}>
                    <Plus size={16} /> Add Credential
                </button>
            </div>


            <p className="page-description">
                Credentials are reusable authentication sources that can access one or more cloud accounts.
            </p>

            {showCreate && <CreateCredentialForm onClose={() => setShowCreate(false)} />}

            <table className="data-table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Provider</th>
                        <th>Auth Type</th>
                        <th>Accounts</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {credentials?.map((cred) => (
                        <tr key={cred.id}>
                            <td>
                                <div className="name-cell">
                                    <Shield size={16} />
                                    <strong>{cred.name}</strong>
                                </div>
                            </td>
                            <td>
                                <span className={`badge badge-${cred.provider.toLowerCase()}`}>
                                    <Cloud size={12} /> {cred.provider}
                                </span>
                            </td>
                            <td>{cred.auth_type}</td>
                            <td>
                                <span className="badge badge-info">{cred.account_count}</span>
                            </td>
                            <td>
                                <span className={`badge badge-${cred.status.toLowerCase()}`}>
                                    {cred.status}
                                </span>
                            </td>
                            <td className="actions-cell">
                                <button
                                    className="btn btn-danger btn-sm"
                                    onClick={() => handleDelete(cred.id, cred.name)}
                                    disabled={deleteMutation.isPending || cred.account_count > 0}
                                    title={cred.account_count > 0 ? 'Delete accounts first' : 'Delete credential'}
                                >
                                    <Trash2 size={14} />
                                </button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>

            {credentials?.length === 0 && (
                <div className="empty-state">
                    <Key size={48} />
                    <h3>No credentials configured</h3>
                    <p>Add a credential to start deploying canaries to cloud accounts.</p>
                </div>
            )}
        </div>
    )
}

function CreateCredentialForm({ onClose }: { onClose: () => void }) {
    const queryClient = useQueryClient()
    const [formData, setFormData] = useState({
        name: '',
        provider: 'AWS',
        auth_type: 'STATIC',
        access_key_id: '',
        secret_access_key: '',
        region: 'us-east-1',
        service_account_json: '',
    })
    const [error, setError] = useState('')
    const [isSubmitting, setIsSubmitting] = useState(false)

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setIsSubmitting(true)
        setError('')

        const secrets = formData.provider === 'AWS'
            ? {
                access_key_id: formData.access_key_id,
                secret_access_key: formData.secret_access_key,
                region: formData.region,
            }
            : {
                service_account_json: formData.service_account_json,
            }

        try {
            const response = await fetch('/api/v1/credentials/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: formData.name,
                    provider: formData.provider,
                    auth_type: formData.auth_type,
                    secrets,
                }),
            })

            if (!response.ok) {
                const data = await response.json()
                throw new Error(data.detail || 'Failed to create credential')
            }

            queryClient.invalidateQueries({ queryKey: ['credentials'] })
            onClose()
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'An error occurred')
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <div className="card form-card">
            <h3>Add Credential</h3>
            {error && <div className="error-message">{error}</div>}
            <form onSubmit={handleSubmit}>
                <div className="form-row">
                    <div className="form-group">
                        <label htmlFor="cred-name">Name</label>
                        <input
                            id="cred-name"
                            type="text"
                            value={formData.name}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            placeholder="aws-prod-creds"
                            required
                        />
                    </div>
                    <div className="form-group">
                        <label htmlFor="cred-provider">Provider</label>
                        <select
                            id="cred-provider"
                            value={formData.provider}
                            onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
                        >
                            <option value="AWS">AWS</option>
                            <option value="GCP">GCP</option>
                        </select>
                    </div>
                </div>

                <div className="form-row">
                    <div className="form-group">
                        <label htmlFor="cred-auth-type">Auth Type</label>
                        <select
                            id="cred-auth-type"
                            value={formData.auth_type}
                            onChange={(e) => setFormData({ ...formData, auth_type: e.target.value })}
                        >
                            <option value="STATIC">Static Credentials</option>
                            <option value="ASSUME_ROLE">Assume Role (AWS)</option>
                            <option value="IMPERSONATE">Impersonate (GCP)</option>
                        </select>
                    </div>
                </div>

                {formData.provider === 'AWS' && (
                    <>
                        <div className="form-group">
                            <label htmlFor="aws-key">Access Key ID</label>
                            <input
                                id="aws-key"
                                type="text"
                                value={formData.access_key_id}
                                onChange={(e) => setFormData({ ...formData, access_key_id: e.target.value })}
                                placeholder="AKIAIOSFODNN7EXAMPLE"
                            />
                        </div>
                        <div className="form-group">
                            <label htmlFor="aws-secret">Secret Access Key</label>
                            <input
                                id="aws-secret"
                                type="password"
                                value={formData.secret_access_key}
                                onChange={(e) => setFormData({ ...formData, secret_access_key: e.target.value })}
                                placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
                            />
                        </div>
                        <div className="form-group">
                            <label htmlFor="aws-region">Region</label>
                            <input
                                id="aws-region"
                                type="text"
                                value={formData.region}
                                onChange={(e) => setFormData({ ...formData, region: e.target.value })}
                                placeholder="us-east-1"
                            />
                        </div>
                    </>
                )}

                {formData.provider === 'GCP' && (
                    <div className="form-group">
                        <label htmlFor="gcp-sa">Service Account JSON</label>
                        <textarea
                            id="gcp-sa"
                            value={formData.service_account_json}
                            onChange={(e) => setFormData({ ...formData, service_account_json: e.target.value })}
                            placeholder='{"type": "service_account", ...}'
                            rows={6}
                        />
                    </div>
                )}

                <div className="form-actions">
                    <button type="button" className="btn btn-secondary" onClick={onClose}>
                        Cancel
                    </button>
                    <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                        {isSubmitting ? 'Creating...' : 'Create Credential'}
                    </button>
                </div>
            </form>
        </div>
    )
}
