import { useAuthContext } from '../context/AuthContext'

/**
 * Hook to access authentication state and methods.
 * 
 * Must be used within an AuthProvider.
 */
export function useAuth() {
    return useAuthContext()
}
