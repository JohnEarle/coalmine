import { useQuery } from '@tanstack/react-query'

/**
 * Resource type metadata from /api/v1/meta/resource-types
 */
export interface ResourceType {
    value: string
    name: string
    description: string
    provider: 'AWS' | 'GCP'
    requires_logging: boolean
    template: string
}

/**
 * Logging type metadata from /api/v1/meta/logging-types
 */
export interface LoggingType {
    value: string
    name: string
    description: string
    provider: 'AWS' | 'GCP'
    template: string
}

/**
 * Status metadata from /api/v1/meta/statuses
 */
export interface StatusInfo {
    value: string
    name: string
    color: string
    label: string
    icon: string
}

/**
 * Hook to fetch all available resource types.
 * 
 * This enables dynamic form generation - when new canary types are added
 * to the backend, they automatically appear in the UI.
 */
export function useResourceTypes() {
    return useQuery({
        queryKey: ['meta', 'resource-types'],
        queryFn: async (): Promise<ResourceType[]> => {
            const response = await fetch('/api/v1/meta/resource-types')
            if (!response.ok) throw new Error('Failed to fetch resource types')
            const data = await response.json()
            return data.types
        },
        staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    })
}

/**
 * Hook to fetch all available logging types.
 */
export function useLoggingTypes() {
    return useQuery({
        queryKey: ['meta', 'logging-types'],
        queryFn: async (): Promise<LoggingType[]> => {
            const response = await fetch('/api/v1/meta/logging-types')
            if (!response.ok) throw new Error('Failed to fetch logging types')
            const data = await response.json()
            return data.types
        },
        staleTime: 5 * 60 * 1000,
    })
}

/**
 * Hook to fetch status metadata with colors and icons.
 */
export function useStatuses() {
    return useQuery({
        queryKey: ['meta', 'statuses'],
        queryFn: async (): Promise<StatusInfo[]> => {
            const response = await fetch('/api/v1/meta/statuses')
            if (!response.ok) throw new Error('Failed to fetch statuses')
            const data = await response.json()
            return data.statuses
        },
        staleTime: 10 * 60 * 1000, // Cache for 10 minutes
    })
}

/**
 * Hook to fetch cloud providers.
 */
export function useProviders() {
    return useQuery({
        queryKey: ['meta', 'providers'],
        queryFn: async () => {
            const response = await fetch('/api/v1/meta/providers')
            if (!response.ok) throw new Error('Failed to fetch providers')
            const data = await response.json()
            return data.providers as Array<{
                value: string
                name: string
                icon: string
                color: string
            }>
        },
        staleTime: 10 * 60 * 1000,
    })
}
