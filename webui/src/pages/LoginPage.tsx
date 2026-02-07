import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { Bird, Lock, User, LogIn } from 'lucide-react'

/**
 * Login page with session-based authentication and optional SSO
 */
export default function LoginPage() {
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState('')
    const [isSubmitting, setIsSubmitting] = useState(false)

    const { login, oidcEnabled, oidcProviderName, loginWithOidc } = useAuth()
    const navigate = useNavigate()

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault()
        setError('')
        setIsSubmitting(true)

        try {
            const result = await login(username, password)

            if (result.success) {
                navigate('/')
            } else {
                setError(result.error || 'Login failed')
            }
        } catch (err) {
            setError('An unexpected error occurred')
        } finally {
            setIsSubmitting(false)
        }
    }

    const handleSsoLogin = () => {
        loginWithOidc()
    }

    return (
        <div className="login-page">
            <div className="login-container">
                <div className="login-card">
                    <div className="login-header">
                        <Bird className="login-logo" style={{ color: 'var(--color-accent)' }} />
                        <h1 className="login-title">Coalmine</h1>
                        <p className="login-subtitle">Canary Token Management</p>
                    </div>

                    {error && (
                        <div className="login-error">
                            {error}
                        </div>
                    )}

                    {/* SSO Button - only shown if OIDC is enabled */}
                    {oidcEnabled && (
                        <>
                            <button
                                type="button"
                                className="btn btn-secondary"
                                style={{
                                    width: '100%',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    gap: '0.5rem',
                                    marginBottom: '1.5rem'
                                }}
                                onClick={handleSsoLogin}
                            >
                                <LogIn size={18} />
                                Sign in with {oidcProviderName || 'SSO'}
                            </button>

                            <div style={{
                                display: 'flex',
                                alignItems: 'center',
                                marginBottom: '1.5rem',
                                gap: '1rem'
                            }}>
                                <hr style={{ flex: 1, border: 'none', borderTop: '1px solid var(--color-border)' }} />
                                <span style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>or</span>
                                <hr style={{ flex: 1, border: 'none', borderTop: '1px solid var(--color-border)' }} />
                            </div>
                        </>
                    )}

                    <form onSubmit={handleSubmit}>
                        <div className="form-group">
                            <label className="form-label" htmlFor="username">
                                <User size={16} style={{ display: 'inline', marginRight: '0.5rem' }} />
                                Username
                            </label>
                            <input
                                id="username"
                                type="text"
                                className="form-input"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                placeholder="admin"
                                required
                                autoFocus={!oidcEnabled}
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label" htmlFor="password">
                                <Lock size={16} style={{ display: 'inline', marginRight: '0.5rem' }} />
                                Password
                            </label>
                            <input
                                id="password"
                                type="password"
                                className="form-input"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="••••••••"
                                required
                            />
                        </div>

                        <button
                            type="submit"
                            className="btn btn-primary"
                            style={{ width: '100%', marginTop: '0.5rem' }}
                            disabled={isSubmitting}
                        >
                            {isSubmitting ? 'Signing in...' : 'Sign In'}
                        </button>
                    </form>
                </div>
            </div>
        </div>
    )
}
