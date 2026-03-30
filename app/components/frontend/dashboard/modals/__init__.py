"""
Dashboard Modal Components

Reusable modal dialogs for displaying detailed component information.
Each modal inherits from ft.AlertDialog and uses component composition.
"""
from .backend_modal import BackendDetailDialog
from .database_modal import DatabaseDetailDialog
from .frontend_modal import FrontendDetailDialog
from .ingress_modal import IngressDetailDialog
from .observability_modal import ObservabilityDetailDialog
from .ollama_modal import OllamaDetailDialog
from .redis_modal import RedisDetailDialog
from .worker_modal import WorkerDetailDialog

__all__ = [
    "BackendDetailDialog",
    "DatabaseDetailDialog",
    "FrontendDetailDialog",
    "IngressDetailDialog",
    "ObservabilityDetailDialog",
    "OllamaDetailDialog",
    "RedisDetailDialog",
    "WorkerDetailDialog",
]
