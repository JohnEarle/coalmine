import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useCreateCanary, useAccounts, useLoggingResources } from '../hooks/useApi'
import { useResourceTypes, ResourceType } from '../hooks/useMeta'

/**
 * Canary creation page with dynamic form based on resource types.
 * 
 * Form fields adjust based on the selected resource type - specifically
 * whether logging_id is required based on the type's requires_logging setting.
 */
export default function CanaryCreatePage() {
    const navigate = useNavigate()
    const { data: resourceTypes, isLoading: typesLoading } = useResourceTypes()
    const { data: accounts, isLoading: accountsLoading } = useAccounts()
    const { data: loggingResources, isLoading: loggingLoading } = useLoggingResources()
    const createCanary = useCreateCanary()

    const [formData, setFormData] = useState({
        name: '',
        resource_type: '',
        account_id: '',
        logging_id: '',
        interval: 0,
    })
    const [error, setError] = useState('')

    // Get the selected resource type config
    const selectedType: ResourceType | undefined = resourceTypes?.find(
        t => t.value === formData.resource_type
    )

    // Filter accounts by provider of selected type
    const filteredAccounts = accounts?.filter(account => {
        if (!selectedType) return true
        // Match provider: GCP_SERVICE_ACCOUNT -> GCP accounts
        return account.provider.toUpperCase().includes(selectedType.provider)
    })

    // Filter logging resources by provider
    const filteredLogging = loggingResources?.filter(log => {
        if (!selectedType) return true
        return log.provider_type.toUpperCase().includes(selectedType.provider)
    })

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault()
        setError('')

        // Validation
        if (!formData.name.trim()) {
            setError('Name is required')
            return
        }
        if (!formData.resource_type) {
            setError('Resource type is required')
            return
        }
        if (!formData.account_id) {
            setError('Account is required')
            return
        }
        if (selectedType?.requires_logging && !formData.logging_id) {
            setError('Logging resource is required for this resource type')
            return
        }

        try {
            await createCanary.mutateAsync({
                name: formData.name.trim(),
                resource_type: formData.resource_type,
                account_id: formData.account_id,
                logging_id: formData.logging_id || '',
                interval: formData.interval,
            })
            navigate('/canaries')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to create canary')
        }
    }

    const isLoading = typesLoading || accountsLoading || loggingLoading

    return (
        <div>
            <div className="page-header">
                <div className="flex items-center gap-4">
                    <button className="btn btn-ghost" onClick={() => navigate('/canaries')}>
                        <ArrowLeft size={18} />
                    </button>
                    <div>
                        <h1 className="page-title">Create Canary</h1>
                        <p className="page-description">Deploy a new canary token resource</p>
                    </div>
                </div>
            </div>

            <div className="card" style={{ maxWidth: '600px' }}>
                {error && (
                    <div className="login-error" style={{ marginBottom: '1.5rem' }}>
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit}>
                    {/* Name */}
                    <div className="form-group">
                        <label className="form-label" htmlFor="name">
                            Name *
                        </label>
                        <input
                            id="name"
                            type="text"
                            className="form-input"
                            value={formData.name}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            placeholder="my-canary"
                            required
                        />
                        <p className="form-hint">Unique identifier for this canary</p>
                    </div>

                    {/* Resource Type - dynamically populated */}
                    <div className="form-group">
                        <label className="form-label" htmlFor="resource_type">
                            Resource Type *
                        </label>
                        <select
                            id="resource_type"
                            className="form-select"
                            value={formData.resource_type}
                            onChange={(e) => setFormData({
                                ...formData,
                                resource_type: e.target.value,
                                account_id: '', // Reset when type changes
                                logging_id: '',
                            })}
                            required
                            disabled={isLoading}
                        >
                            <option value="">Select resource type...</option>
                            {resourceTypes?.map((type) => (
                                <option key={type.value} value={type.value}>
                                    {type.name} ({type.provider})
                                </option>
                            ))}
                        </select>
                        {selectedType && (
                            <p className="form-hint">{selectedType.description}</p>
                        )}
                    </div>

                    {/* Account (Deployment Target) */}
                    <div className="form-group">
                        <label className="form-label" htmlFor="account_id">
                            Account *
                        </label>
                        <select
                            id="account_id"
                            className="form-select"
                            value={formData.account_id}
                            onChange={(e) => setFormData({ ...formData, account_id: e.target.value })}
                            required
                            disabled={!formData.resource_type || isLoading}
                        >
                            <option value="">Select account...</option>
                            {filteredAccounts?.map((account) => (
                                <option key={account.id} value={account.id}>
                                    {account.name} ({account.account_id})
                                </option>
                            ))}
                        </select>
                        <p className="form-hint">Deployment target (AWS account or GCP project)</p>
                    </div>

                    {/* Logging Resource - conditionally required */}
                    {selectedType?.requires_logging && (
                        <div className="form-group">
                            <label className="form-label" htmlFor="logging_id">
                                Logging Resource *
                            </label>
                            <select
                                id="logging_id"
                                className="form-select"
                                value={formData.logging_id}
                                onChange={(e) => setFormData({ ...formData, logging_id: e.target.value })}
                                required
                                disabled={!formData.resource_type || isLoading}
                            >
                                <option value="">Select logging resource...</option>
                                {filteredLogging?.map((log) => (
                                    <option key={log.id} value={log.id}>
                                        {log.name} ({log.provider_type})
                                    </option>
                                ))}
                            </select>
                            <p className="form-hint">Required for detecting access to this canary type</p>
                        </div>
                    )}

                    {/* Interval */}
                    <div className="form-group">
                        <label className="form-label" htmlFor="interval">
                            Rotation Interval (seconds)
                        </label>
                        <input
                            id="interval"
                            type="number"
                            className="form-input"
                            value={formData.interval}
                            onChange={(e) => setFormData({ ...formData, interval: parseInt(e.target.value) || 0 })}
                            min={0}
                            placeholder="0"
                        />
                        <p className="form-hint">0 for static credentials, or rotation interval in seconds</p>
                    </div>

                    {/* Submit */}
                    <div className="flex gap-4" style={{ marginTop: '1.5rem' }}>
                        <button
                            type="submit"
                            className="btn btn-primary"
                            disabled={createCanary.isPending}
                        >
                            {createCanary.isPending ? 'Creating...' : 'Create Canary'}
                        </button>
                        <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={() => navigate('/canaries')}
                        >
                            Cancel
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}
