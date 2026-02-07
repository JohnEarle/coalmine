import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

/**
 * Canary resource from the API
 */
export interface Canary {
    id: string
    name: string
    resource_type: string
    status: string
    account_id: string | null
    account_name: string | null
    current_resource_id: string | null
    expires_at: string | null
    created_at: string
}

/**
 * Account from the API (deployment target)
 */
export interface Account {
    id: string
    name: string
    account_id: string  // Cloud provider account/project ID
    credential_id: string
    credential_name: string
    provider: string
    is_enabled: boolean
    status: string
}

/**
 * Logging resource from the API
 */
export interface LoggingResource {
    id: string
    name: string
    provider_type: string
    account_id: string | null
    account_name: string | null
    status: string
}

/**
 * Alert from the API
 */
export interface Alert {
    id: string
    canary_id: string
    canary_name?: string
    account_name?: string
    timestamp: string
    source_ip: string | null
    user_agent: string | null
    event_name: string | null
    status: string
}

/**
 * Hook to fetch all canaries
 */
export function useCanaries() {
    return useQuery({
        queryKey: ['canaries'],
        queryFn: async (): Promise<Canary[]> => {
            const response = await fetch('/api/v1/canaries/')
            if (!response.ok) throw new Error('Failed to fetch canaries')
            const data = await response.json()
            return data.canaries
        },
        refetchOnWindowFocus: false,
    })
}

/**
 * Hook to fetch a single canary by ID
 */
export function useCanary(canaryId: string | undefined) {
    return useQuery({
        queryKey: ['canary', canaryId],
        queryFn: async (): Promise<Canary> => {
            const response = await fetch(`/api/v1/canaries/${canaryId}`)
            if (!response.ok) throw new Error('Failed to fetch canary')
            return response.json()
        },
        enabled: !!canaryId,
        refetchOnWindowFocus: false,
    })
}

/**
 * Canary credentials from the API
 */
export interface CanaryCredentials {
    canary_id: string
    canary_name: string
    credentials: Record<string, unknown> | null
}

/**
 * Hook to fetch credentials for a canary
 */
export function useCanaryCredentials(canaryId: string | undefined) {
    return useQuery({
        queryKey: ['canary-credentials', canaryId],
        queryFn: async (): Promise<CanaryCredentials> => {
            const response = await fetch(`/api/v1/canaries/${canaryId}/credentials`)
            if (!response.ok) throw new Error('Failed to fetch credentials')
            return response.json()
        },
        enabled: !!canaryId,
        refetchOnWindowFocus: false,
    })
}

/**
 * Hook to fetch all accounts (deployment targets)
 */
export function useAccounts() {
    return useQuery({
        queryKey: ['accounts'],
        queryFn: async (): Promise<Account[]> => {
            const response = await fetch('/api/v1/accounts/')
            if (!response.ok) throw new Error('Failed to fetch accounts')
            const data = await response.json()
            return data.accounts
        },
        refetchOnWindowFocus: false,
    })
}

/**
 * Hook to fetch all logging resources
 */
export function useLoggingResources() {
    return useQuery({
        queryKey: ['logging'],
        queryFn: async (): Promise<LoggingResource[]> => {
            const response = await fetch('/api/v1/logging-resources/')
            if (!response.ok) throw new Error('Failed to fetch logging resources')
            const data = await response.json()
            return data.logging_resources
        },
        refetchOnWindowFocus: false,
    })
}

/**
 * Hook to fetch alerts
 */
export function useAlerts() {
    return useQuery({
        queryKey: ['alerts'],
        queryFn: async (): Promise<Alert[]> => {
            const response = await fetch('/api/v1/alerts/')
            if (!response.ok) throw new Error('Failed to fetch alerts')
            const data = await response.json()
            return data.alerts
        },
        refetchInterval: 30000, // Refetch every 30 seconds for real-time alerts
    })
}

/**
 * Hook to create a new canary
 */
export function useCreateCanary() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: async (data: {
            name: string
            resource_type: string
            account_id: string  // Changed from environment_id
            logging_id: string
            interval?: number
            params?: Record<string, unknown>
        }) => {
            const response = await fetch('/api/v1/canaries/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            })
            if (!response.ok) {
                const error = await response.json()
                throw new Error(error.detail || 'Failed to create canary')
            }
            return response.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['canaries'] })
        },
    })
}

/**
 * Hook to delete a canary
 */
export function useDeleteCanary() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: async (canaryId: string) => {
            const response = await fetch(`/api/v1/canaries/${canaryId}`, {
                method: 'DELETE',
            })
            if (!response.ok) {
                const error = await response.json()
                throw new Error(error.detail || 'Failed to delete canary')
            }
            return response.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['canaries'] })
        },
    })
}

/**
 * Hook to trigger a canary
 */
export function useTriggerCanary() {
    return useMutation({
        mutationFn: async (canaryId: string) => {
            const response = await fetch(`/api/v1/canaries/${canaryId}/trigger`, {
                method: 'POST',
            })
            if (!response.ok) {
                const error = await response.json()
                throw new Error(error.detail || 'Failed to trigger canary')
            }
            return response.json()
        },
    })
}

/**
 * Logging provider type from metadata API
 */
export interface LoggingType {
    value: string
    name: string
    description: string
    provider: string
}

/**
 * Hook to fetch available logging provider types
 */
export function useLoggingTypes() {
    return useQuery({
        queryKey: ['logging-types'],
        queryFn: async (): Promise<LoggingType[]> => {
            const response = await fetch('/api/v1/meta/logging-types')
            if (!response.ok) throw new Error('Failed to fetch logging types')
            const data = await response.json()
            return data.types
        },
        refetchOnWindowFocus: false,
    })
}

/**
 * Hook to create a new logging resource
 */
export function useCreateLoggingResource() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: async (data: {
            name: string
            provider_type: string
            account_id: string
            config?: Record<string, unknown>
        }) => {
            const response = await fetch('/api/v1/logging-resources/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            })
            if (!response.ok) {
                const error = await response.json()
                throw new Error(error.detail || 'Failed to create logging resource')
            }
            return response.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['logging'] })
        },
    })
}
