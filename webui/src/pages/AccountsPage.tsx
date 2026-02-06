import { useState, useEffect } from 'react'
import { useQueryClient, useMutation } from '@tanstack/react-query'
import { Building2, Plus, Trash2, Search, Check, Edit3 } from 'lucide-react'
import { useAccounts } from '../hooks/useApi'
import { useConfirm } from '../components/ConfirmModal'

interface Credential {
    id: string
    name: string
    provider: string
}

interface DiscoverableAccount {
    account_id: string
    name: string
    metadata: Record<string, unknown>
    already_exists: boolean
}

function useDeleteAccount() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (id: string) => {
            const response = await fetch(`/api/v1/accounts/${id}`, { method: 'DELETE' })
            if (!response.ok) {
                const error = await response.json()
                throw new Error(error.detail || 'Failed to delete')
            }
            return response.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['accounts'] })
        },
    })
}

export default function AccountsPage() {
    const { data: accounts, isLoading, error, refetch } = useAccounts()
    const deleteMutation = useDeleteAccount()
    const [showCreate, setShowCreate] = useState(false)
    const confirm = useConfirm()

    const handleDelete = async (id: string, name: string) => {
        const confirmed = await confirm({
            title: 'Delete Account',
            message: `Delete account "${name}"? This cannot be undone.`,
            confirmText: 'Delete',
            dangerous: true,
        })
        if (confirmed) {
            try {
                await deleteMutation.mutateAsync(id)
            } catch {
                // Error handled by mutation
            }
        }
    }

    return (
        <div className="page">
            <div className="page-header">
                <h1><Building2 size={24} /> Accounts</h1>
                <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}>
                    <Plus size={16} /> Add Account
                </button>
            </div>

            <p className="page-description">
                Deployment targets for canary resources (AWS accounts, GCP projects).
            </p>

            {showCreate && (
                <AddAccountPanel
                    onClose={() => setShowCreate(false)}
                    onSuccess={() => { setShowCreate(false); refetch(); }}
                />
            )}

            <table className="data-table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Account/Project ID</th>
                        <th>Provider</th>
                        <th>Credential</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {isLoading ? (
                        <tr><td colSpan={6} className="text-muted">Loading accounts...</td></tr>
                    ) : error ? (
                        <tr><td colSpan={6} className="text-muted">Error loading accounts</td></tr>
                    ) : accounts && accounts.length > 0 ? (
                        accounts.map((account) => (
                            <tr key={account.id}>
                                <td>
                                    <div className="name-cell">
                                        <Building2 size={16} />
                                        <strong>{account.name}</strong>
                                    </div>
                                </td>
                                <td className="font-mono">{account.account_id}</td>
                                <td>
                                    <span className={`badge badge-${account.provider.toLowerCase()}`}>
                                        {account.provider}
                                    </span>
                                </td>
                                <td>{account.credential_name || '-'}</td>
                                <td>
                                    <span className={`badge badge-${account.status.toLowerCase()}`}>
                                        {account.status}
                                    </span>
                                </td>
                                <td className="actions-cell">
                                    <button
                                        className="btn btn-danger btn-sm"
                                        onClick={() => handleDelete(account.id, account.name)}
                                        disabled={deleteMutation.isPending}
                                        title="Delete account"
                                    >
                                        <Trash2 size={14} />
                                    </button>
                                </td>
                            </tr>
                        ))
                    ) : (
                        <tr>
                            <td colSpan={6} className="empty-state">
                                <Building2 size={32} />
                                <p>No accounts configured. Click "Add Account" to create one.</p>
                            </td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    )
}

interface AddAccountPanelProps {
    onClose: () => void
    onSuccess: () => void
}

function AddAccountPanel({ onClose, onSuccess }: AddAccountPanelProps) {
    const [credentials, setCredentials] = useState<Credential[]>([])
    const [selectedCredId, setSelectedCredId] = useState('')
    const [isLoadingCreds, setIsLoadingCreds] = useState(true)
    const [mode, setMode] = useState<'discover' | 'manual'>('discover')

    const selectedCred = credentials.find(c => c.id === selectedCredId)

    useEffect(() => {
        fetch('/api/v1/credentials/')
            .then(r => r.json())
            .then(data => {
                setCredentials(data.credentials || [])
                setIsLoadingCreds(false)
            })
            .catch(() => setIsLoadingCreds(false))
    }, [])

    return (
        <div className="card form-card">
            <h3>Add Account</h3>

            <div className="form-group">
                <label htmlFor="add-cred">Credential</label>
                <select
                    id="add-cred"
                    value={selectedCredId}
                    onChange={(e) => setSelectedCredId(e.target.value)}
                    disabled={isLoadingCreds}
                >
                    <option value="">Select credential...</option>
                    {credentials.map((cred) => (
                        <option key={cred.id} value={cred.id}>
                            {cred.name} ({cred.provider})
                        </option>
                    ))}
                </select>
            </div>

            {selectedCredId && (
                <>
                    <div className="form-tabs">
                        <button
                            className={`tab ${mode === 'discover' ? 'active' : ''}`}
                            onClick={() => setMode('discover')}
                            type="button"
                        >
                            <Search size={14} /> Discover
                        </button>
                        <button
                            className={`tab ${mode === 'manual' ? 'active' : ''}`}
                            onClick={() => setMode('manual')}
                            type="button"
                        >
                            <Edit3 size={14} /> Manual
                        </button>
                    </div>

                    {mode === 'discover' ? (
                        <DiscoverTab
                            credentialId={selectedCredId}
                            credential={selectedCred}
                            onSuccess={onSuccess}
                        />
                    ) : (
                        <ManualTab
                            credentialId={selectedCredId}
                            credential={selectedCred}
                            onSuccess={onSuccess}
                        />
                    )}
                </>
            )}

            <div className="form-actions">
                <button type="button" className="btn btn-secondary" onClick={onClose}>
                    Close
                </button>
            </div>
        </div>
    )
}

interface TabProps {
    credentialId: string
    credential?: Credential
    onSuccess: () => void
}

function DiscoverTab({ credentialId, credential, onSuccess }: TabProps) {
    const queryClient = useQueryClient()
    const [discoverable, setDiscoverable] = useState<DiscoverableAccount[]>([])
    const [selected, setSelected] = useState<Set<string>>(new Set())
    const [isDiscovering, setIsDiscovering] = useState(false)
    const [isImporting, setIsImporting] = useState(false)
    const [error, setError] = useState('')
    const [hasRun, setHasRun] = useState(false)

    useEffect(() => {
        if (!hasRun && credentialId) {
            runDiscovery()
        }
    }, [credentialId])

    const runDiscovery = async () => {
        setIsDiscovering(true)
        setError('')
        setHasRun(true)

        try {
            const response = await fetch(`/api/v1/credentials/${credentialId}/discoverable`)
            const data = await response.json()

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to discover')
            }

            setDiscoverable(data.accounts || [])

            const newAccounts = (data.accounts || [])
                .filter((a: DiscoverableAccount) => !a.already_exists)
                .map((a: DiscoverableAccount) => a.account_id)
            setSelected(new Set(newAccounts))
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Discovery failed')
        } finally {
            setIsDiscovering(false)
        }
    }

    const handleImport = async () => {
        if (selected.size === 0) return
        setIsImporting(true)
        setError('')

        try {
            const selectedAccounts = discoverable.filter(a => selected.has(a.account_id))

            for (const account of selectedAccounts) {
                await fetch('/api/v1/accounts/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: account.name || `${credential?.name}-${account.account_id.slice(0, 8)}`,
                        credential_id: credentialId,
                        account_id: account.account_id,
                        source: 'DISCOVERED',
                        account_metadata: account.metadata,
                    }),
                })
            }

            queryClient.invalidateQueries({ queryKey: ['accounts'] })
            onSuccess()
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Import failed')
        } finally {
            setIsImporting(false)
        }
    }

    const toggleSelect = (accountId: string) => {
        const newSelected = new Set(selected)
        if (newSelected.has(accountId)) {
            newSelected.delete(accountId)
        } else {
            newSelected.add(accountId)
        }
        setSelected(newSelected)
    }

    if (isDiscovering) {
        return <p className="text-muted">Discovering {credential?.provider} accounts...</p>
    }

    if (error) {
        return <div className="error-message">{error}</div>
    }

    if (discoverable.length === 0) {
        return <p className="text-muted">No accounts found. Try the Manual tab.</p>
    }

    const selectableCount = discoverable.filter(a => !a.already_exists).length

    return (
        <div>
            <table className="data-table">
                <thead>
                    <tr>
                        <th style={{ width: '32px' }}>
                            <input
                                type="checkbox"
                                checked={selected.size === selectableCount && selectableCount > 0}
                                onChange={() => {
                                    if (selected.size === selectableCount) {
                                        setSelected(new Set())
                                    } else {
                                        setSelected(new Set(
                                            discoverable.filter(a => !a.already_exists).map(a => a.account_id)
                                        ))
                                    }
                                }}
                            />
                        </th>
                        <th>Name</th>
                        <th>{credential?.provider === 'GCP' ? 'Project ID' : 'Account ID'}</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {discoverable.map((account) => (
                        <tr key={account.account_id} style={{ opacity: account.already_exists ? 0.5 : 1 }}>
                            <td>
                                <input
                                    type="checkbox"
                                    checked={selected.has(account.account_id)}
                                    onChange={() => toggleSelect(account.account_id)}
                                    disabled={account.already_exists}
                                />
                            </td>
                            <td>{account.name}</td>
                            <td className="font-mono">{account.account_id}</td>
                            <td>
                                {account.already_exists ? (
                                    <span className="badge badge-neutral"><Check size={12} /> Imported</span>
                                ) : (
                                    <span className="badge badge-success">Available</span>
                                )}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>

            {selected.size > 0 && (
                <button
                    className="btn btn-primary"
                    onClick={handleImport}
                    disabled={isImporting}
                    style={{ marginTop: '1rem' }}
                >
                    {isImporting ? 'Importing...' : `Import ${selected.size} Account${selected.size !== 1 ? 's' : ''}`}
                </button>
            )}
        </div>
    )
}

function ManualTab({ credentialId, credential, onSuccess }: TabProps) {
    const queryClient = useQueryClient()
    const [name, setName] = useState('')
    const [accountId, setAccountId] = useState('')
    const [error, setError] = useState('')
    const [isSubmitting, setIsSubmitting] = useState(false)

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!name || !accountId) return

        setIsSubmitting(true)
        setError('')

        try {
            const response = await fetch('/api/v1/accounts/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name,
                    credential_id: credentialId,
                    account_id: accountId,
                    source: 'MANUAL',
                }),
            })

            if (!response.ok) {
                const data = await response.json()
                throw new Error(data.detail || 'Failed to create')
            }

            queryClient.invalidateQueries({ queryKey: ['accounts'] })
            onSuccess()
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to add account')
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <form onSubmit={handleSubmit}>
            {error && <div className="error-message">{error}</div>}

            <div className="form-row">
                <div className="form-group">
                    <label htmlFor="manual-name">Name</label>
                    <input
                        id="manual-name"
                        type="text"
                        placeholder="prod-east"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        required
                    />
                </div>
                <div className="form-group">
                    <label htmlFor="manual-id">
                        {credential?.provider === 'GCP' ? 'Project ID' : 'Account ID'}
                    </label>
                    <input
                        id="manual-id"
                        type="text"
                        placeholder={credential?.provider === 'GCP' ? 'my-project-id' : '123456789012'}
                        value={accountId}
                        onChange={(e) => setAccountId(e.target.value)}
                        required
                    />
                </div>
            </div>

            <button type="submit" className="btn btn-primary" disabled={isSubmitting || !name || !accountId}>
                {isSubmitting ? 'Adding...' : 'Add Account'}
            </button>
        </form>
    )
}
