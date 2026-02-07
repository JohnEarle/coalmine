import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, CheckCircle, XCircle, Clock, Loader } from 'lucide-react'

/**
 * Task log entry from the API
 */
interface TaskLog {
    id: string
    celery_task_id: string
    task_name: string
    source: string
    status: string
    canary_id: string | null
    canary_name: string | null
    created_at: string | null
    started_at: string | null
    finished_at: string | null
    error: string | null
    result_data: Record<string, unknown> | null
}

function useTasks() {
    return useQuery({
        queryKey: ['tasks'],
        queryFn: async (): Promise<TaskLog[]> => {
            const response = await fetch('/api/v1/tasks/')
            if (!response.ok) throw new Error('Failed to fetch tasks')
            const data = await response.json()
            return data.tasks
        },
        refetchInterval: 5000,
    })
}

const STATUS_CONFIG: Record<string, { icon: typeof Clock; className: string; label: string }> = {
    PENDING: { icon: Clock, className: 'task-status-pending', label: 'Pending' },
    STARTED: { icon: Loader, className: 'task-status-started', label: 'Running' },
    SUCCESS: { icon: CheckCircle, className: 'task-status-success', label: 'Done' },
    FAILURE: { icon: XCircle, className: 'task-status-failure', label: 'Failed' },
}

function formatTaskName(name: string): string {
    return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function timeAgo(dateStr: string | null): string {
    if (!dateStr) return ''
    const seconds = Math.floor((Date.now() - new Date(dateStr + 'Z').getTime()) / 1000)
    if (seconds < 60) return `${seconds}s ago`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
    return `${Math.floor(seconds / 86400)}d ago`
}

/**
 * Small activity icon in the top-right corner of the layout.
 * Shows a dropdown with recent task statuses when clicked.
 */
export default function TaskActivity() {
    const { data: tasks, isLoading } = useTasks()
    const [open, setOpen] = useState(false)
    const ref = useRef<HTMLDivElement>(null)

    // Close on click outside
    useEffect(() => {
        function handleClick(e: MouseEvent) {
            if (ref.current && !ref.current.contains(e.target as Node)) {
                setOpen(false)
            }
        }
        if (open) document.addEventListener('mousedown', handleClick)
        return () => document.removeEventListener('mousedown', handleClick)
    }, [open])

    const activeCount = tasks?.filter(t => t.status === 'PENDING' || t.status === 'STARTED').length ?? 0

    return (
        <div className="task-activity" ref={ref}>
            <button
                className="task-activity-btn"
                onClick={() => setOpen(o => !o)}
                title="Task Activity"
            >
                <Activity size={18} />
                {activeCount > 0 && (
                    <span className="task-activity-badge">{activeCount}</span>
                )}
            </button>

            {open && (
                <div className="task-activity-dropdown">
                    <div className="task-activity-header">
                        <span>Recent Tasks</span>
                    </div>

                    <div className="task-activity-list">
                        {isLoading && (
                            <div className="task-activity-empty">Loading...</div>
                        )}

                        {!isLoading && (!tasks || tasks.length === 0) && (
                            <div className="task-activity-empty">No recent tasks</div>
                        )}

                        {tasks?.slice(0, 10).map(task => {
                            const cfg = STATUS_CONFIG[task.status] ?? STATUS_CONFIG.PENDING
                            const Icon = cfg.icon

                            return (
                                <div key={task.id} className="task-activity-item">
                                    <div className={`task-activity-icon ${cfg.className}`}>
                                        <Icon size={14} className={task.status === 'STARTED' ? 'spin' : ''} />
                                    </div>
                                    <div className="task-activity-info">
                                        <div className="task-activity-name">
                                            {formatTaskName(task.task_name)}
                                        </div>
                                        <div className="task-activity-meta">
                                            {task.canary_name && (
                                                <span className="task-activity-canary">{task.canary_name}</span>
                                            )}
                                            <span className={cfg.className}>{cfg.label}</span>
                                            <span className="task-activity-time">{timeAgo(task.created_at)}</span>
                                        </div>
                                        {task.error && (
                                            <div className="task-activity-error">{task.error}</div>
                                        )}
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>
            )}
        </div>
    )
}
