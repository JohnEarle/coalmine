from celery import Celery
import os

broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

celery_app = Celery('coalmine', broker=broker_url, backend=result_backend)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    imports=(
        'src.tasks.canary',
        'src.tasks.logging', 
        'src.tasks.monitoring',
        'src.tasks.validation',
        'src.tasks.notifications',
        'src.task_signals',
    ),
)

celery_app.conf.beat_schedule = {
    'check-rotations-every-minute': {
        'task': 'src.tasks.canary.check_rotations',
        'schedule': 60.0,
    },
    'monitor-every-1-minutes': {
        'task': 'src.tasks.monitoring.monitor_active_canaries',
        'schedule': 60.0,
    },
    'validate-resources-every-10-minutes': {
        'task': 'src.tasks.validation.run_health_checks',
        'schedule': 600.0,
    },
}
