import { useState, useEffect } from 'react'
import { Users, Trash2, Plus, Mail } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { useConfirm } from '../components/ConfirmModal'

interface User {
    id: string
    email: string
    role: string
    is_active: boolean
    is_verified: boolean
    display_name: string | null
}

interface RoleOption {
    value: string
    name: string
}

/**
 * Users management page (admin only)
 */
export default function UsersPage() {
    const [users, setUsers] = useState<User[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [showCreateModal, setShowCreateModal] = useState(false)
    const { hasRole } = useAuth()
    const confirm = useConfirm()

    // Form state for new user
    const [newEmail, setNewEmail] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [newRole, setNewRole] = useState('viewer')
    const [creating, setCreating] = useState(false)
    const [roles, setRoles] = useState<RoleOption[]>([])

    const fetchRoles = async () => {
        try {
            const response = await fetch('/api/v1/meta/roles', { credentials: 'include' })
            if (response.ok) {
                const data = await response.json()
                setRoles(data.roles)
            }
        } catch (err) {
            console.error('Failed to fetch roles:', err)
        }
    }

    const fetchUsers = async () => {
        try {
            const response = await fetch('/api/v1/users', {
                credentials: 'include'
            })
            if (response.ok) {
                const data = await response.json()
                setUsers(data)
            } else if (response.status === 403) {
                setError('Admin access required to view users')
            } else {
                setError('Failed to load users')
            }
        } catch (err) {
            setError('Network error')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchRoles()
        fetchUsers()
    }, [])

    const handleCreateUser = async (e: React.FormEvent) => {
        e.preventDefault()
        setCreating(true)
        setError('')

        try {
            const response = await fetch('/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    email: newEmail,
                    password: newPassword,
                    role: newRole,
                    is_active: true,
                    is_verified: true
                })
            })

            if (response.ok) {
                setShowCreateModal(false)
                setNewEmail('')
                setNewPassword('')
                setNewRole('viewer')
                fetchUsers()
            } else {
                const data = await response.json()
                setError(data.detail || 'Failed to create user')
            }
        } catch (err) {
            setError('Network error')
        } finally {
            setCreating(false)
        }
    }

    const handleDeleteUser = async (userId: string, email: string) => {
        const confirmed = await confirm({
            title: 'Delete User',
            message: `Are you sure you want to delete user "${email}"?`,
            confirmText: 'Delete',
            dangerous: true,
        })
        if (!confirmed) return

        try {
            const response = await fetch(`/api/v1/users/${userId}`, {
                method: 'DELETE',
                credentials: 'include'
            })
            if (response.ok) {
                fetchUsers()
            } else {
                const data = await response.json()
                setError(data.detail || 'Failed to delete user')
            }
        } catch (err) {
            setError('Network error')
        }
    }

    const handleRoleChange = async (userId: string, newRole: string) => {
        try {
            const response = await fetch(`/api/v1/users/${userId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ role: newRole })
            })
            if (response.ok) {
                fetchUsers()
            } else {
                setError('Failed to update role')
            }
        } catch (err) {
            setError('Network error')
        }
    }

    if (loading) {
        return (
            <div className="loading-screen">
                <div className="loading-spinner" />
                <p>Loading users...</p>
            </div>
        )
    }

    return (
        <div className="page-container">
            <div className="page-header">
                <div>
                    <h1 className="page-title">
                        <Users size={24} style={{ marginRight: '0.5rem' }} />
                        Users
                    </h1>
                    <p className="page-description">Manage user accounts and roles</p>
                </div>
                {hasRole('admin') && (
                    <button
                        className="btn btn-primary"
                        onClick={() => setShowCreateModal(true)}
                    >
                        <Plus size={18} /> Add User
                    </button>
                )}
            </div>

            {error && <div className="alert alert-error">{error}</div>}

            <div className="card">
                <table className="table">
                    <thead>
                        <tr>
                            <th>Email</th>
                            <th>Display Name</th>
                            <th>Role</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {users.map(user => (
                            <tr key={user.id}>
                                <td>
                                    <Mail size={14} style={{ marginRight: '0.5rem', opacity: 0.5 }} />
                                    {user.email}
                                </td>
                                <td>{user.display_name || '-'}</td>
                                <td>
                                    <select
                                        value={user.role}
                                        onChange={(e) => handleRoleChange(user.id, e.target.value)}
                                        className="form-input"
                                        style={{ width: 'auto', padding: '0.25rem 0.5rem' }}
                                    >
                                        {roles.map(r => (
                                            <option key={r.value} value={r.value}>{r.name}</option>
                                        ))}
                                    </select>
                                </td>
                                <td>
                                    <span className={`badge ${user.is_active ? 'badge-success' : 'badge-error'}`}>
                                        {user.is_active ? 'Active' : 'Inactive'}
                                    </span>
                                </td>
                                <td>
                                    <button
                                        className="btn btn-danger btn-sm"
                                        onClick={() => handleDeleteUser(user.id, user.email)}
                                        title="Delete user"
                                    >
                                        <Trash2 size={14} />
                                    </button>
                                </td>
                            </tr>
                        ))}
                        {users.length === 0 && (
                            <tr>
                                <td colSpan={5} style={{ textAlign: 'center', opacity: 0.5 }}>
                                    No users found
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            {/* Create User Modal */}
            {showCreateModal && (
                <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
                    <div className="modal" onClick={e => e.stopPropagation()}>
                        <h2>Create New User</h2>
                        <form onSubmit={handleCreateUser}>
                            <div className="form-group">
                                <label className="form-label">Email</label>
                                <input
                                    type="email"
                                    className="form-input"
                                    value={newEmail}
                                    onChange={e => setNewEmail(e.target.value)}
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Password</label>
                                <input
                                    type="password"
                                    className="form-input"
                                    value={newPassword}
                                    onChange={e => setNewPassword(e.target.value)}
                                    required
                                    minLength={8}
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Role</label>
                                <select
                                    className="form-input"
                                    value={newRole}
                                    onChange={e => setNewRole(e.target.value)}
                                >
                                    {roles.map(r => (
                                        <option key={r.value} value={r.value}>{r.name}</option>
                                    ))}
                                </select>
                            </div>
                            <div className="modal-actions">
                                <button type="button" className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>
                                    Cancel
                                </button>
                                <button type="submit" className="btn btn-primary" disabled={creating}>
                                    {creating ? 'Creating...' : 'Create User'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    )
}
