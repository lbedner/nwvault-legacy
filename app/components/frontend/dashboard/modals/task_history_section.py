"""
Task History Section

Displays per-task history with inspection capability.
Fetches data from the task history API and renders a scrollable,
paginated table with expandable error details for failed tasks.
Includes two independent hover-to-reveal filter icons (status + queue)
with immediate visual feedback on pill selection.
"""

import contextlib
import threading

import flet as ft
from app.components.frontend.controls import (
    BodyText,
    DataTableColumn,
    ExpandableDataTable,
    ExpandableRow,
    PrimaryText,
    SecondaryText,
)
from app.components.frontend.theme import AegisTheme as Theme
from app.core.config import settings
from app.core.log import logger

# Column widths
COL_WIDTH_STATUS_ICON = 30
COL_WIDTH_QUEUE = 90
COL_WIDTH_DURATION = 80
COL_WIDTH_ENQUEUED = 150
COL_WIDTH_STATUS = 80

# Pagination
PAGE_SIZE = 25

# Status display mapping
_STATUS_DISPLAY: dict[str, tuple[str, str]] = {
    "enqueued": ("⏳", "Enqueued"),
    "running": ("🔵", "Running"),
    "completed": ("🟢", "Done"),
    "failed": ("🔴", "Failed"),
}

# Status filter options: (label, api_value, color)
_STATUS_FILTER_OPTIONS: list[tuple[str, str, str]] = [
    ("All", "all", Theme.Colors.ACCENT),
    ("Completed", "completed", Theme.Colors.SUCCESS),
    ("Failed", "failed", Theme.Colors.ERROR),
    ("Running", "running", Theme.Colors.INFO),
]

_PILL_WIDTH = 80
_PILL_HEIGHT = 28
_PILL_SELECTED_OPACITY = 0.15


def _format_duration(duration_ms: str | None) -> str:
    """Format duration in milliseconds to a human-readable string."""
    if not duration_ms:
        return "—"
    try:
        ms = float(duration_ms)
        if ms < 1000:
            return f"{ms:.0f}ms"
        s = ms / 1000
        if s < 60:
            return f"{s:.1f}s"
        m = int(s // 60)
        s = s % 60
        return f"{m}m {s:.0f}s"
    except (ValueError, TypeError):
        return "—"


def _format_timestamp(iso_str: str | None) -> str:
    """Format ISO timestamp for display."""
    if not iso_str:
        return "—"
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%H:%M:%S")
    except (ValueError, TypeError):
        return "—"


def _build_task_row(task: dict[str, str]) -> ExpandableRow:
    """Build a table row for a single task record."""
    status = task.get("status", "unknown")
    icon, status_label = _STATUS_DISPLAY.get(status, ("⚪", status))
    has_error = status == "failed" and task.get("error")

    status_color = (
        Theme.Colors.ERROR
        if status == "failed"
        else Theme.Colors.SUCCESS
        if status == "completed"
        else Theme.Colors.INFO
        if status == "running"
        else ft.Colors.ON_SURFACE_VARIANT
    )

    cells = [
        ft.Text(icon, size=16),
        PrimaryText(
            task.get("name", "unknown"),
            size=Theme.Typography.BODY,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
        BodyText(task.get("queue", "—"), text_align=ft.TextAlign.CENTER),
        BodyText(
            _format_duration(task.get("duration_ms")),
            text_align=ft.TextAlign.CENTER,
        ),
        SecondaryText(
            _format_timestamp(task.get("enqueued_at")),
            text_align=ft.TextAlign.CENTER,
        ),
        SecondaryText(
            status_label,
            color=status_color,
            weight=Theme.Typography.WEIGHT_SEMIBOLD,
            text_align=ft.TextAlign.CENTER,
        ),
    ]

    # Expanded content — description, metadata, and error details
    expanded_items: list[ft.Control] = []

    # Task description (from function docstring)
    description = task.get("description", "")
    if description:
        expanded_items.append(
            ft.Text(
                description,
                size=Theme.Typography.BODY,
                italic=True,
                color=ft.Colors.ON_SURFACE_VARIANT,
            )
        )
        expanded_items.append(ft.Container(height=6))

    # Error details for failed tasks
    if has_error:
        error_text = task.get("error", "")
        expanded_items.append(
            ft.Text(
                "Error Details",
                size=12,
                weight=ft.FontWeight.W_600,
                color=Theme.Colors.ERROR,
            )
        )
        expanded_items.append(ft.Container(height=4))
        expanded_items.append(
            ft.Container(
                content=ft.Text(
                    error_text,
                    size=12,
                    color=ft.Colors.ON_SURFACE,
                    selectable=True,
                ),
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                border_radius=6,
                padding=ft.padding.all(10),
                border=ft.border.all(
                    1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)
                ),
            )
        )
        expanded_items.append(ft.Container(height=4))

    # Metadata row (always shown)
    expanded_items.append(
        ft.Row(
            [
                SecondaryText(f"Job ID: {task.get('job_id', '—')}", size=11),
                SecondaryText("|", size=11),
                SecondaryText(
                    f"Started: {_format_timestamp(task.get('started_at'))}",
                    size=11,
                ),
                SecondaryText("|", size=11),
                SecondaryText(
                    f"Finished: {_format_timestamp(task.get('finished_at'))}",
                    size=11,
                ),
            ],
            spacing=8,
        )
    )

    expanded = ft.Container(
        content=ft.Column(expanded_items, spacing=2),
        padding=ft.padding.all(8),
    )

    return ExpandableRow(cells=cells, expanded_content=expanded)


class TaskHistorySection(ft.Container):
    """Task history section with two independent hover-to-reveal filter icons."""

    def __init__(self, page: ft.Page) -> None:
        super().__init__()
        self.padding = Theme.Spacing.MD
        self._page = page
        self._current_queue = "all"
        self._current_status = "all"
        self._offset = 0
        self._total = 0
        self._loading = False

        # Independent collapse timers for each filter zone
        self._status_collapse_timer: threading.Timer | None = None
        self._queue_collapse_timer: threading.Timer | None = None

        _anim = ft.Animation(200, ft.AnimationCurve.EASE_OUT)

        # ── Status filter zone ───────────────────────────────────────────
        self._status_pills: list[ft.Container] = []
        for label, value, color in _STATUS_FILTER_OPTIONS:
            pill = self._build_status_pill(label, value, color)
            self._status_pills.append(pill)

        self._status_filter_wrapper = ft.Container(
            content=ft.Row(self._status_pills, spacing=Theme.Spacing.XS),
            width=0,
            opacity=0,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            animate=_anim,
            animate_opacity=_anim,
        )

        self._status_filter_dot = ft.Container(
            width=6,
            height=6,
            border_radius=3,
            bgcolor=Theme.Colors.ACCENT,
            opacity=0,
            animate_opacity=_anim,
        )

        self._status_filter_zone = ft.Container(
            content=ft.Row(
                [
                    self._status_filter_wrapper,
                    self._status_filter_dot,
                    ft.Icon(
                        ft.Icons.FILTER_LIST,
                        size=16,
                        color=Theme.Colors.TEXT_SECONDARY,
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_hover=self._handle_status_hover,
        )

        # ── Queue filter zone ────────────────────────────────────────────
        self._queue_names = ["all"]
        try:
            from app.core.config import get_available_queues

            self._queue_names.extend(get_available_queues())
        except Exception:
            pass

        self._queue_pills: list[ft.Container] = []
        for q in self._queue_names:
            pill = self._build_queue_pill(q)
            self._queue_pills.append(pill)

        self._queue_filter_wrapper = ft.Container(
            content=ft.Row(self._queue_pills, spacing=Theme.Spacing.XS),
            width=0,
            opacity=0,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            animate=_anim,
            animate_opacity=_anim,
        )

        self._queue_filter_dot = ft.Container(
            width=6,
            height=6,
            border_radius=3,
            bgcolor=Theme.Colors.INFO,
            opacity=0,
            animate_opacity=_anim,
        )

        self._queue_filter_zone = ft.Container(
            content=ft.Row(
                [
                    self._queue_filter_wrapper,
                    self._queue_filter_dot,
                    ft.Icon(
                        ft.Icons.STACKED_BAR_CHART,
                        size=16,
                        color=Theme.Colors.TEXT_SECONDARY,
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_hover=self._handle_queue_hover,
        )

        # Refresh button
        self._refresh_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            icon_size=16,
            tooltip="Refresh",
            on_click=self._on_refresh,
        )

        # Loading indicator
        self._loading_indicator = ft.ProgressRing(
            width=16,
            height=16,
            stroke_width=2,
            visible=False,
        )

        # Pagination controls
        self._page_info = SecondaryText("", size=12)
        self._prev_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT,
            icon_size=16,
            tooltip="Previous",
            on_click=self._on_prev,
            disabled=True,
        )
        self._next_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT,
            icon_size=16,
            tooltip="Next",
            on_click=self._on_next,
            disabled=True,
        )

        # ── Single toolbar row ──
        toolbar = ft.Row(
            [
                self._status_filter_zone,
                self._queue_filter_zone,
                self._refresh_btn,
                self._loading_indicator,
                ft.Container(expand=True),
                self._prev_btn,
                self._page_info,
                self._next_btn,
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Table columns
        self._columns = [
            DataTableColumn("", width=COL_WIDTH_STATUS_ICON),
            DataTableColumn("Task Name"),
            DataTableColumn("Queue", width=COL_WIDTH_QUEUE, alignment="center"),
            DataTableColumn("Duration", width=COL_WIDTH_DURATION, alignment="center"),
            DataTableColumn("Enqueued", width=COL_WIDTH_ENQUEUED, alignment="center"),
            DataTableColumn("Status", width=COL_WIDTH_STATUS, alignment="center"),
        ]

        # Initial empty table
        self._table = ExpandableDataTable(
            columns=self._columns,
            rows=[],
            row_padding=6,
            empty_message="No task history available",
        )

        self.content = ft.Column(
            [toolbar, self._table],
            spacing=Theme.Spacing.SM,
        )

    def _build_status_pill(self, label: str, value: str, color: str) -> ft.Container:
        """Build a single status filter pill."""
        is_selected = value == self._current_status
        return ft.Container(
            content=ft.Text(
                label,
                size=Theme.Typography.BODY_SMALL,
                weight=Theme.Typography.WEIGHT_SEMIBOLD,
                color=color if is_selected else Theme.Colors.TEXT_SECONDARY,
                text_align=ft.TextAlign.CENTER,
            ),
            width=_PILL_WIDTH,
            height=_PILL_HEIGHT,
            alignment=ft.alignment.center,
            border_radius=Theme.Components.BADGE_RADIUS,
            bgcolor=(
                ft.Colors.with_opacity(_PILL_SELECTED_OPACITY, color)
                if is_selected
                else ft.Colors.TRANSPARENT
            ),
            on_click=lambda e, v=value: self._on_status_change(v),
            ink=True,
        )

    def _build_queue_pill(self, queue_name: str) -> ft.Container:
        """Build a single queue filter pill."""
        display = "All" if queue_name == "all" else queue_name
        is_selected = queue_name == self._current_queue
        color = Theme.Colors.INFO
        return ft.Container(
            content=ft.Text(
                display,
                size=Theme.Typography.BODY_SMALL,
                weight=Theme.Typography.WEIGHT_SEMIBOLD,
                color=color if is_selected else Theme.Colors.TEXT_SECONDARY,
                text_align=ft.TextAlign.CENTER,
            ),
            width=_PILL_WIDTH,
            height=_PILL_HEIGHT,
            alignment=ft.alignment.center,
            border_radius=Theme.Components.BADGE_RADIUS,
            bgcolor=(
                ft.Colors.with_opacity(_PILL_SELECTED_OPACITY, color)
                if is_selected
                else ft.Colors.TRANSPARENT
            ),
            on_click=lambda e, q=queue_name: self._on_queue_pill_change(q),
            ink=True,
        )

    # ── Status filter hover/collapse ─────────────────────────────────────

    def _handle_status_hover(self, e: ft.HoverEvent) -> None:
        """Expand status pills on hover enter, schedule collapse on leave."""
        if e.data == "true":
            if self._status_collapse_timer:
                self._status_collapse_timer.cancel()
                self._status_collapse_timer = None
            self._expand_status_filters()
        else:
            self._status_collapse_timer = threading.Timer(
                0.4,
                self._delayed_status_collapse,
            )
            self._status_collapse_timer.start()

    def _expand_status_filters(self) -> None:
        """Reveal the status filter pills."""
        n_status = len(_STATUS_FILTER_OPTIONS)
        expanded_width = n_status * (_PILL_WIDTH + 4)
        self._status_filter_wrapper.width = expanded_width
        self._status_filter_wrapper.opacity = 1
        self._status_filter_dot.opacity = 0
        if self.page:
            self._status_filter_zone.update()

    def _collapse_status_filters(self) -> None:
        """Hide the status pills and show dot if filtered."""
        self._status_filter_wrapper.width = 0
        self._status_filter_wrapper.opacity = 0
        self._update_status_dot()

    def _delayed_status_collapse(self) -> None:
        """Timer callback — collapse status pills and push update."""
        self._status_collapse_timer = None
        self._collapse_status_filters()
        if self.page:
            self._status_filter_zone.update()

    def _update_status_dot(self) -> None:
        """Show/hide the status indicator dot."""
        if self._current_status != "all":
            for _, value, color in _STATUS_FILTER_OPTIONS:
                if value == self._current_status:
                    self._status_filter_dot.bgcolor = color
                    break
            self._status_filter_dot.opacity = 1
        else:
            self._status_filter_dot.opacity = 0

    # ── Queue filter hover/collapse ──────────────────────────────────────

    def _handle_queue_hover(self, e: ft.HoverEvent) -> None:
        """Expand queue pills on hover enter, schedule collapse on leave."""
        if e.data == "true":
            if self._queue_collapse_timer:
                self._queue_collapse_timer.cancel()
                self._queue_collapse_timer = None
            self._expand_queue_filters()
        else:
            self._queue_collapse_timer = threading.Timer(
                0.4,
                self._delayed_queue_collapse,
            )
            self._queue_collapse_timer.start()

    def _expand_queue_filters(self) -> None:
        """Reveal the queue filter pills."""
        n_queues = len(self._queue_names)
        expanded_width = n_queues * (_PILL_WIDTH + 4)
        self._queue_filter_wrapper.width = expanded_width
        self._queue_filter_wrapper.opacity = 1
        self._queue_filter_dot.opacity = 0
        if self.page:
            self._queue_filter_zone.update()

    def _collapse_queue_filters(self) -> None:
        """Hide the queue pills and show dot if filtered."""
        self._queue_filter_wrapper.width = 0
        self._queue_filter_wrapper.opacity = 0
        self._update_queue_dot()

    def _delayed_queue_collapse(self) -> None:
        """Timer callback — collapse queue pills and push update."""
        self._queue_collapse_timer = None
        self._collapse_queue_filters()
        if self.page:
            self._queue_filter_zone.update()

    def _update_queue_dot(self) -> None:
        """Show/hide the queue indicator dot."""
        if self._current_queue != "all":
            self._queue_filter_dot.opacity = 1
        else:
            self._queue_filter_dot.opacity = 0

    # ── Filter change handlers ───────────────────────────────────────────

    def _on_status_change(self, status: str) -> None:
        """Handle status filter pill click with immediate visual feedback."""
        if status == self._current_status:
            return
        self._current_status = status
        self._offset = 0

        # Update pill visuals immediately
        for i, (_, value, color) in enumerate(_STATUS_FILTER_OPTIONS):
            is_selected = value == self._current_status
            pill = self._status_pills[i]
            pill.bgcolor = (
                ft.Colors.with_opacity(_PILL_SELECTED_OPACITY, color)
                if is_selected
                else ft.Colors.TRANSPARENT
            )
            text = pill.content
            text.color = color if is_selected else Theme.Colors.TEXT_SECONDARY

        # Push visual update before data load
        if self.page:
            self._status_filter_zone.update()

        self._schedule_load()

    def _on_queue_pill_change(self, queue: str) -> None:
        """Handle queue filter pill click with immediate visual feedback."""
        if queue == self._current_queue:
            return
        self._current_queue = queue
        self._offset = 0

        # Update queue pill visuals immediately
        color = Theme.Colors.INFO
        for i, q in enumerate(self._queue_names):
            is_selected = q == self._current_queue
            pill = self._queue_pills[i]
            pill.bgcolor = (
                ft.Colors.with_opacity(_PILL_SELECTED_OPACITY, color)
                if is_selected
                else ft.Colors.TRANSPARENT
            )
            text = pill.content
            text.color = color if is_selected else Theme.Colors.TEXT_SECONDARY

        # Push visual update before data load
        if self.page:
            self._queue_filter_zone.update()

        self._schedule_load()

    def did_mount(self) -> None:
        """Load initial data after the control is mounted."""
        self._schedule_load()

    def _schedule_load(self) -> None:
        """Schedule an async data load on the page's event loop."""
        if self._page and hasattr(self._page, "run_task"):
            self._page.run_task(self._load_data)

    def _build_query_params(self) -> dict[str, str | int]:
        """Build query params dict for the API request."""
        params: dict[str, str | int] = {
            "offset": self._offset,
            "limit": PAGE_SIZE,
            "order": "desc",
        }
        if self._current_status != "all":
            params["status"] = self._current_status
        return params

    async def _load_data(self) -> None:
        """Fetch task history from the API."""
        if self._loading:
            return
        self._loading = True
        self._loading_indicator.visible = True
        with contextlib.suppress(Exception):
            self._loading_indicator.update()

        try:
            import httpx

            base_url = f"http://localhost:{settings.PORT}"
            queue = self._current_queue
            params = self._build_query_params()

            async with httpx.AsyncClient(timeout=10) as client:
                if queue == "all":
                    # Fetch from all queues and merge
                    all_tasks: list[dict[str, str]] = []
                    total = 0
                    try:
                        from app.core.config import get_available_queues

                        queues = get_available_queues()
                    except Exception:
                        queues = []
                    for q in queues:
                        try:
                            resp = await client.get(
                                f"{base_url}/api/v1/tasks/history/{q}",
                                params=params,
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                all_tasks.extend(data.get("tasks", []))
                                total += data.get("total", 0)
                        except Exception:
                            pass
                    # Sort merged results by enqueued_at descending
                    all_tasks.sort(key=lambda t: t.get("enqueued_at", ""), reverse=True)
                    tasks = all_tasks[:PAGE_SIZE]
                    self._total = total
                else:
                    resp = await client.get(
                        f"{base_url}/api/v1/tasks/history/{queue}",
                        params=params,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        tasks = data.get("tasks", [])
                        self._total = data.get("total", 0)
                    else:
                        tasks = []
                        self._total = 0

            # Build rows
            rows = [_build_task_row(t) for t in tasks]
            self._table._rows = rows
            self._table._expanded = [False] * len(rows)
            self._table._build()

            # Update pagination
            self._update_pagination()
            self._table.update()

        except Exception as e:
            logger.debug(f"Failed to load task history: {e}")
        finally:
            self._loading = False
            self._loading_indicator.visible = False
            with contextlib.suppress(Exception):
                self._loading_indicator.update()

    def _update_pagination(self) -> None:
        """Update pagination controls based on current state."""
        end = min(self._offset + PAGE_SIZE, self._total)
        if self._total > 0:
            self._page_info.value = f"{self._offset + 1}-{end} of {self._total}"
        else:
            self._page_info.value = "No records"

        self._prev_btn.disabled = self._offset <= 0
        self._next_btn.disabled = (self._offset + PAGE_SIZE) >= self._total

        try:
            self._page_info.update()
            self._prev_btn.update()
            self._next_btn.update()
        except Exception:
            pass

    def _on_refresh(self, e: ft.ControlEvent) -> None:
        """Handle refresh button click."""
        self._schedule_load()

    def _on_prev(self, e: ft.ControlEvent) -> None:
        """Handle previous page."""
        self._offset = max(0, self._offset - PAGE_SIZE)
        self._schedule_load()

    def _on_next(self, e: ft.ControlEvent) -> None:
        """Handle next page."""
        if self._offset + PAGE_SIZE < self._total:
            self._offset += PAGE_SIZE
            self._schedule_load()
