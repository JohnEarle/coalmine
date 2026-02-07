import { useAuthContext } from '../context/AuthContext'

/**
 * Role hierarchy (mirrors config/rbac_policy.csv):
 *   superuser > admin > operator > viewer
 *
 * hasRole('admin') returns true for both admin and superuser.
 */
const ROLE_HIERARCHY: Record<string, number> = {
    viewer: 0,
    operator: 1,
    admin: 2,
    superuser: 3,
}

export function useAuth() {
    const auth = useAuthContext()

    /** Check if current user has at least the given role level. */
    const hasRole = (requiredRole: string): boolean => {
        const userLevel = ROLE_HIERARCHY[auth.user?.role ?? ''] ?? -1
        const requiredLevel = ROLE_HIERARCHY[requiredRole] ?? 999
        return userLevel >= requiredLevel
    }

    return { ...auth, hasRole }
}
