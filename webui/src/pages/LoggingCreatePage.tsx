import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useCreateLoggingResource, useLoggingTypes, useAccounts } from '../hooks/useApi'

/**
 * Logging resource creation page.
 * 
 * Allows users to create new logging resources (CloudTrail, GCP Audit Sink, etc.)
 * by selecting a provider type and target account.
 */
export default function LoggingCreatePage() {
    const navigate = useNavigate()
    const { data: loggingTypes, isLoading: typesLoading } = useLoggingTypes()
    const { data: accounts, isLoading: accountsLoading } = useAccounts()
    const createLogging = useCreateLoggingResource()

    const [formData, setFormData] = useState({
        name: '',
        provider_type: '',
        account_id: '',
    })
    const [error, setError] = useState('')

    // Get selected type info for filtering accounts
    const selectedType = loggingTypes?.find(t => t.value === formData.provider_type)

    // Filter accounts by provider of selected type
    const filteredAccounts = accounts?.filter(account => {
        if (!selectedType) return true
        return account.provider.toUpperCase().includes(selectedType.provider)
    })

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault()
        setError('')

        // Validation
        if (!formData.name.trim()) {
            setError('Name is required')
            return
        }
        if (!formData.provider_type) {
            setError('Provider type is required')
            return
        }
        if (!formData.account_id) {
            setError('Account is required')
            return
        }

        try {
            await createLogging.mutateAsync({
                name: formData.name.trim(),
                provider_type: formData.provider_type,
                account_id: formData.account_id,
            })
            navigate('/logging')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to create logging resource')
        }
    }

    const isLoading = typesLoading || accountsLoading

    return (
        <div>
            <div className="page-header">
                <div className="flex items-center gap-4">
                    <button className="btn btn-ghost" onClick={() => navigate('/logging')}>
                        <ArrowLeft size={18} />
                    </button>
                    <div>
                        <h1 className="page-title">Add Logging Source</h1>
                        <p className="page-description">Configure a new log aggregation source</p>
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
                            placeholder="central-cloudtrail"
                            required
                        />
                        <p className="form-hint">Unique identifier for this logging source</p>
                    </div>

                    {/* Provider Type */}
                    <div className="form-group">
                        <label className="form-label" htmlFor="provider_type">
                            Provider Type *
                        </label>
                        <select
                            id="provider_type"
                            className="form-select"
                            value={formData.provider_type}
                            onChange={(e) => setFormData({
                                ...formData,
                                provider_type: e.target.value,
                                account_id: '', // Reset when type changes
                            })}
                            required
                            disabled={isLoading}
                        >
                            <option value="">Select provider type...</option>
                            {loggingTypes?.map((type) => (
                                <option key={type.value} value={type.value}>
                                    {type.name} ({type.provider})
                                </option>
                            ))}
                        </select>
                        {selectedType && (
                            <p className="form-hint">{selectedType.description}</p>
                        )}
                    </div>

                    {/* Account */}
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
                            disabled={!formData.provider_type || isLoading}
                        >
                            <option value="">Select account...</option>
                            {filteredAccounts?.map((account) => (
                                <option key={account.id} value={account.id}>
                                    {account.name} ({account.account_id})
                                </option>
                            ))}
                        </select>
                        <p className="form-hint">Cloud account where the logging resource will be created</p>
                    </div>

                    {/* Submit */}
                    <div className="flex gap-4" style={{ marginTop: '1.5rem' }}>
                        <button
                            type="submit"
                            className="btn btn-primary"
                            disabled={createLogging.isPending}
                        >
                            {createLogging.isPending ? 'Creating...' : 'Add Logging Source'}
                        </button>
                        <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={() => navigate('/logging')}
                        >
                            Cancel
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}
