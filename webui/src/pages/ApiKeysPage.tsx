import { useState, useEffect } from 'react'
import { Key, Plus, Trash2, Copy, Check, Clock } from 'lucide-react'

interface ApiKey {
    name: string
    description: string
    permissions: string[]
    created_at: string | null
    expires_at: string | null
}

/**
 * API Keys management page (self-service)
 */
export default function ApiKeysPage() {
    const [keys, setKeys] = useState<ApiKey[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [showCreateModal, setShowCreateModal] = useState(false)
    const [newKeyValue, setNewKeyValue] = useState<string | null>(null)
    const [copied, setCopied] = useState(false)

    // Form state for new key
    const [newName, setNewName] = useState('')
    const [newDescription, setNewDescription] = useState('')
    const [newPermissions, setNewPermissions] = useState(['read'])
    const [creating, setCreating] = useState(false)

    const fetchKeys = async () => {
        try {
            const response = await fetch('/api/v1/api-keys/me', {
                credentials: 'include'
            })
            if (response.ok) {
                const data = await response.json()
                setKeys(data.keys || [])
            } else {
                setError('Failed to load API keys')
            }
        } catch (err) {
            setError('Network error')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchKeys()
    }, [])

    const handleCreateKey = async (e: React.FormEvent) => {
        e.preventDefault()
        setCreating(true)
        setError('')

        try {
            const response = await fetch('/api/v1/api-keys/me', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    name: newName,
                    description: newDescription,
                    permissions: newPermissions,
                    scopes: ['*']
                })
            })

            if (response.ok) {
                const data = await response.json()
                setNewKeyValue(data.key) // Show key once
                setNewName('')
                setNewDescription('')
                setNewPermissions(['read'])
                fetchKeys()
            } else {
                const data = await response.json()
                setError(data.detail || 'Failed to create API key')
            }
        } catch (err) {
            setError('Network error')
        } finally {
            setCreating(false)
        }
    }

    const handleDeleteKey = async (keyName: string) => {
        if (!confirm(`Are you sure you want to revoke API key "${keyName}"?`)) return

        try {
            const response = await fetch(`/api/v1/api-keys/me/${keyName}`, {
                method: 'DELETE',
                credentials: 'include'
            })
            if (response.ok) {
                fetchKeys()
            } else {
                setError('Failed to revoke API key')
            }
        } catch (err) {
            setError('Network error')
        }
    }

    const copyToClipboard = () => {
        if (newKeyValue) {
            navigator.clipboard.writeText(newKeyValue)
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
        }
    }

    if (loading) {
        return (
            <div className="loading-screen">
                <div className="loading-spinner" />
                <p>Loading API keys...</p>
            </div>
        )
    }

    return (
        <div className="page-container">
            <div className="page-header">
                <div>
                    <h1 className="page-title">
                        <Key size={24} style={{ marginRight: '0.5rem' }} />
                        API Keys
                    </h1>
                    <p className="page-description">Manage your personal API keys for programmatic access</p>
                </div>
                <button
                    className="btn btn-primary"
                    onClick={() => setShowCreateModal(true)}
                >
                    <Plus size={18} /> Create Key
                </button>
            </div>

            {error && <div className="alert alert-error">{error}</div>}

            {/* New Key Display */}
            {newKeyValue && (
                <div className="alert alert-success" style={{ marginBottom: '1rem' }}>
                    <strong>New API Key Created!</strong>
                    <p style={{ fontSize: '0.85rem', opacity: 0.9, marginTop: '0.5rem' }}>
                        Copy this key now. You won't be able to see it again.
                    </p>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem' }}>
                        <code style={{
                            flex: 1,
                            padding: '0.5rem',
                            background: 'rgba(0,0,0,0.1)',
                            borderRadius: '4px',
                            fontSize: '0.9rem'
                        }}>
                            {newKeyValue}
                        </code>
                        <button className="btn btn-secondary btn-sm" onClick={copyToClipboard}>
                            {copied ? <Check size={14} /> : <Copy size={14} />}
                        </button>
                    </div>
                    <button
                        className="btn btn-secondary btn-sm"
                        style={{ marginTop: '0.5rem' }}
                        onClick={() => setNewKeyValue(null)}
                    >
                        Dismiss
                    </button>
                </div>
            )}

            <div className="card">
                <table className="table">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Description</th>
                            <th>Permissions</th>
                            <th>Expires</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {keys.map(key => (
                            <tr key={key.name}>
                                <td>
                                    <Key size={14} style={{ marginRight: '0.5rem', opacity: 0.5 }} />
                                    {key.name}
                                </td>
                                <td>{key.description || '-'}</td>
                                <td>
                                    {key.permissions.map(p => (
                                        <span key={p} className="badge badge-info" style={{ marginRight: '0.25rem' }}>
                                            {p}
                                        </span>
                                    ))}
                                </td>
                                <td>
                                    {key.expires_at ? (
                                        <span>
                                            <Clock size={14} style={{ marginRight: '0.25rem' }} />
                                            {new Date(key.expires_at).toLocaleDateString()}
                                        </span>
                                    ) : (
                                        <span style={{ opacity: 0.5 }}>Never</span>
                                    )}
                                </td>
                                <td>
                                    <button
                                        className="btn btn-danger btn-sm"
                                        onClick={() => handleDeleteKey(key.name)}
                                        title="Revoke key"
                                    >
                                        <Trash2 size={14} />
                                    </button>
                                </td>
                            </tr>
                        ))}
                        {keys.length === 0 && (
                            <tr>
                                <td colSpan={5} style={{ textAlign: 'center', opacity: 0.5 }}>
                                    No API keys yet. Create one to get started.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            {/* Create Key Modal */}
            {showCreateModal && (
                <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
                    <div className="modal" onClick={e => e.stopPropagation()}>
                        <h2>Create API Key</h2>
                        <form onSubmit={handleCreateKey}>
                            <div className="form-group">
                                <label className="form-label">Name</label>
                                <input
                                    type="text"
                                    className="form-input"
                                    value={newName}
                                    onChange={e => setNewName(e.target.value)}
                                    placeholder="my-automation-key"
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Description</label>
                                <input
                                    type="text"
                                    className="form-input"
                                    value={newDescription}
                                    onChange={e => setNewDescription(e.target.value)}
                                    placeholder="Key for CI/CD pipeline"
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Permissions</label>
                                <div style={{ display: 'flex', gap: '1rem' }}>
                                    <label>
                                        <input
                                            type="checkbox"
                                            checked={newPermissions.includes('read')}
                                            onChange={e => {
                                                if (e.target.checked) {
                                                    setNewPermissions([...newPermissions, 'read'])
                                                } else {
                                                    setNewPermissions(newPermissions.filter(p => p !== 'read'))
                                                }
                                            }}
                                        /> Read
                                    </label>
                                    <label>
                                        <input
                                            type="checkbox"
                                            checked={newPermissions.includes('write')}
                                            onChange={e => {
                                                if (e.target.checked) {
                                                    setNewPermissions([...newPermissions, 'write'])
                                                } else {
                                                    setNewPermissions(newPermissions.filter(p => p !== 'write'))
                                                }
                                            }}
                                        /> Write
                                    </label>
                                    <label>
                                        <input
                                            type="checkbox"
                                            checked={newPermissions.includes('admin')}
                                            onChange={e => {
                                                if (e.target.checked) {
                                                    setNewPermissions([...newPermissions, 'admin'])
                                                } else {
                                                    setNewPermissions(newPermissions.filter(p => p !== 'admin'))
                                                }
                                            }}
                                        /> Admin
                                    </label>
                                </div>
                            </div>
                            <div className="modal-actions">
                                <button type="button" className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>
                                    Cancel
                                </button>
                                <button type="submit" className="btn btn-primary" disabled={creating}>
                                    {creating ? 'Creating...' : 'Create Key'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    )
}
