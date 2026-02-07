import { useState, useCallback, useRef, ReactNode, createContext, useContext } from 'react'
import { X, AlertTriangle } from 'lucide-react'

interface ConfirmOptions {
    title?: string
    message: string
    confirmText?: string
    cancelText?: string
    dangerous?: boolean
}

interface ConfirmContextType {
    confirm: (options: ConfirmOptions) => Promise<boolean>
}

const ConfirmContext = createContext<ConfirmContextType | null>(null)

export function useConfirm() {
    const context = useContext(ConfirmContext)
    if (!context) {
        throw new Error('useConfirm must be used within ConfirmProvider')
    }
    return context.confirm
}

interface ConfirmProviderProps {
    children: ReactNode
}

export function ConfirmProvider({ children }: ConfirmProviderProps) {
    const [isOpen, setIsOpen] = useState(false)
    const [options, setOptions] = useState<ConfirmOptions | null>(null)
    // useRef instead of useState — React's setState treats functions as updaters
    // and would immediately call resolve(null), closing the modal
    const resolveRef = useRef<((value: boolean) => void) | null>(null)

    const confirm = useCallback((opts: ConfirmOptions): Promise<boolean> => {
        return new Promise((resolve) => {
            setOptions(opts)
            resolveRef.current = resolve
            setIsOpen(true)
        })
    }, [])

    const handleConfirm = () => {
        setIsOpen(false)
        resolveRef.current?.(true)
        resolveRef.current = null
    }

    const handleCancel = () => {
        setIsOpen(false)
        resolveRef.current?.(false)
        resolveRef.current = null
    }

    return (
        <ConfirmContext.Provider value={{ confirm }}>
            {children}
            {isOpen && options && (
                <div className="modal-overlay" onClick={handleCancel}>
                    <div className="modal-content" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            {options.dangerous && (
                                <AlertTriangle size={20} style={{ color: 'var(--color-error)' }} />
                            )}
                            <h3>{options.title || 'Confirm'}</h3>
                            <button className="btn btn-ghost btn-sm" onClick={handleCancel}>
                                <X size={16} />
                            </button>
                        </div>
                        <div className="modal-body">
                            <p>{options.message}</p>
                        </div>
                        <div className="modal-footer">
                            <button className="btn btn-secondary" onClick={handleCancel}>
                                {options.cancelText || 'Cancel'}
                            </button>
                            <button
                                className={`btn ${options.dangerous ? 'btn-danger' : 'btn-primary'}`}
                                onClick={handleConfirm}
                            >
                                {options.confirmText || 'Confirm'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </ConfirmContext.Provider>
    )
}
