import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'

interface User {
    username: string
    role: string
}

interface AuthContextType {
    user: User | null
    isAuthenticated: boolean
    isLoading: boolean
    oidcEnabled: boolean
    oidcProviderName: string | null
    login: (username: string, password: string) => Promise<{ success: boolean; error?: string }>
    logout: () => Promise<void>
    checkAuth: () => Promise<void>
    loginWithOidc: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [oidcEnabled, setOidcEnabled] = useState(false)
    const [oidcProviderName, setOidcProviderName] = useState<string | null>(null)

    const checkAuth = useCallback(async () => {
        try {
            const response = await fetch('/auth/status')
            const data = await response.json()

            if (data.authenticated && data.user) {
                setUser(data.user)
            } else {
                setUser(null)
            }

            // Update OIDC status
            setOidcEnabled(data.oidc_enabled || false)
            setOidcProviderName(data.oidc_provider_name || null)
        } catch (error) {
            console.error('Auth check failed:', error)
            setUser(null)
        } finally {
            setIsLoading(false)
        }
    }, [])

    useEffect(() => {
        checkAuth()
    }, [checkAuth])

    const login = useCallback(async (username: string, password: string) => {
        try {
            const formData = new URLSearchParams()
            formData.append('username', username)
            formData.append('password', password)

            // Use fastapi-users cookie login
            const response = await fetch('/auth/cookie/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: formData,
            })

            if (response.ok || response.status === 204) {
                // Login succeeded - fetch user info
                await checkAuth()
                return { success: true }
            }

            // Login failed
            const errorData = await response.json().catch(() => ({}))
            return { success: false, error: errorData.detail || 'Invalid credentials' }
        } catch (error) {
            console.error('Login error:', error)
            return { success: false, error: 'Network error' }
        }
    }, [checkAuth])

    const logout = useCallback(async () => {
        try {
            // Use fastapi-users cookie logout
            await fetch('/auth/cookie/logout', { method: 'POST' })
        } catch (error) {
            console.error('Logout error:', error)
        } finally {
            setUser(null)
        }
    }, [])

    const loginWithOidc = useCallback(() => {
        // Redirect to OIDC login endpoint - browser will be redirected to IdP
        window.location.href = '/auth/oidc/login'
    }, [])

    const value: AuthContextType = {
        user,
        isAuthenticated: !!user,
        isLoading,
        oidcEnabled,
        oidcProviderName,
        login,
        logout,
        checkAuth,
        loginWithOidc,
    }

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuthContext(): AuthContextType {
    const context = useContext(AuthContext)
    if (!context) {
        throw new Error('useAuthContext must be used within an AuthProvider')
    }
    return context
}
