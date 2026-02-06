import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'

interface User {
    username: string
    role: string
}

interface AuthContextType {
    user: User | null
    isAuthenticated: boolean
    isLoading: boolean
    login: (username: string, password: string) => Promise<{ success: boolean; error?: string }>
    logout: () => Promise<void>
    checkAuth: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null)
    const [isLoading, setIsLoading] = useState(true)

    const checkAuth = useCallback(async () => {
        try {
            const response = await fetch('/auth/status')
            const data = await response.json()

            if (data.authenticated && data.user) {
                setUser(data.user)
            } else {
                setUser(null)
            }
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

            const response = await fetch('/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: formData,
            })

            const data = await response.json()

            if (response.ok && data.success) {
                setUser({ username: data.user, role: data.role })
                return { success: true }
            } else {
                return { success: false, error: data.detail || 'Login failed' }
            }
        } catch (error) {
            console.error('Login error:', error)
            return { success: false, error: 'Network error' }
        }
    }, [])

    const logout = useCallback(async () => {
        try {
            await fetch('/auth/logout', { method: 'POST' })
        } catch (error) {
            console.error('Logout error:', error)
        } finally {
            setUser(null)
        }
    }, [])

    const value: AuthContextType = {
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        checkAuth,
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
