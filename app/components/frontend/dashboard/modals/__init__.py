"""
Dashboard Modal Components

Reusable modal dialogs for displaying detailed component information.
Each modal inherits from ft.AlertDialog and uses component composition.
"""
from .backend_modal import BackendDetailDialog
from .database_modal import DatabaseDetailDialog
from .frontend_modal import FrontendDetailDialog
from .redis_modal import RedisDetailDialog
from .worker_modal import WorkerDetailDialog

__all__ = [
    "BackendDetailDialog",
    "DatabaseDetailDialog",
    "FrontendDetailDialog",
    "RedisDetailDialog",
    "WorkerDetailDialog",
]
