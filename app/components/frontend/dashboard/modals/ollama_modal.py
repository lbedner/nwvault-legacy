"""
Ollama Detail Modal

Displays comprehensive Ollama local LLM infrastructure information including
running models, VRAM usage, installed models, and server configuration.
"""

from __future__ import annotations

from typing import Any

import flet as ft
from app.components.frontend.controls import (
    BodyText,
    H3Text,
    SecondaryText,
    Tag,
)
from app.components.frontend.controls.data_table import DataTable, DataTableColumn
from app.components.frontend.theme import AegisTheme as Theme
from app.services.system.models import ComponentStatus

from ..cards.card_utils import get_status_detail
from .base_detail_popup import BaseDetailPopup
from .modal_sections import MetricCard

# Statistics section layout
STAT_LABEL_WIDTH = 200

# Model table column widths
COL_WIDTH_MODEL_NAME = 180
COL_WIDTH_PARAMS = 60
COL_WIDTH_QUANT = 50
COL_WIDTH_SIZE = 65
COL_WIDTH_VRAM = 65
COL_WIDTH_STATUS = 80

# Model table columns for DataTable
MODEL_COLUMNS = [
    DataTableColumn("Model", width=COL_WIDTH_MODEL_NAME, style="body"),
    DataTableColumn("Params", width=COL_WIDTH_PARAMS, style="secondary"),
    DataTableColumn("Quant", width=COL_WIDTH_QUANT, style="secondary"),
    DataTableColumn("Size", width=COL_WIDTH_SIZE, alignment="right", style="secondary"),
    DataTableColumn("VRAM", width=COL_WIDTH_VRAM, alignment="right", style="secondary"),
    DataTableColumn("Status", width=COL_WIDTH_STATUS),
]


def format_quantization(quant: str) -> str:
    """Convert quantization level to human-readable format.

    Q4_K_M → 4-bit
    Q8_0 → 8-bit
    Q5_K_S → 5-bit
    """
    if not quant or quant == "—":
        return "—"
    # Extract the bit number from formats like Q4_K_M, Q8_0, Q5_K_S
    if quant.startswith("Q") and len(quant) > 1:
        bit_num = quant[1]
        if bit_num.isdigit():
            return f"{bit_num}-bit"
    return quant


class LoadModelButton(ft.Container):
    """Load button for cold models with loading state and error handling."""

    def __init__(
        self,
        model_name: str,
        page: ft.Page,
        ollama_url: str,
        dialog: OllamaDetailDialog | None = None,
    ) -> None:
        """
        Initialize load model button.

        Args:
            model_name: Name of the model to load
            page: Flet page instance for updates
            ollama_url: Ollama server URL
            dialog: Parent dialog for refreshing data after model load
        """
        super().__init__()
        self._model_name = model_name
        self._page = page
        self._ollama_url = ollama_url
        self._dialog = dialog

        self._button = ft.TextButton(
            text="Load",
            on_click=self._on_load_click,
            style=ft.ButtonStyle(
                color=Theme.Colors.INFO,
                padding=ft.padding.symmetric(horizontal=4, vertical=2),
            ),
        )
        self.content = self._button

    async def _on_load_click(self, e: ft.ControlEvent) -> None:
        """Handle Load button click - warm up the model."""
        # Show loading spinner
        self.content = ft.Row(
            [
                ft.ProgressRing(width=16, height=16, stroke_width=2),
                SecondaryText("Loading...", color=Theme.Colors.INFO),
            ],
            spacing=4,
        )
        self._page.update()

        # Load the model asynchronously
        try:
            from app.services.ai.ollama import OllamaClient

            client = OllamaClient(base_url=self._ollama_url)
            success = await client.load_model(self._model_name)

            if success:
                # Model loaded - refresh the entire modal with fresh health data
                if self._dialog:
                    await self._dialog.refresh_data()
            else:
                # Failed to load - show error with retry button
                self.content = ft.TextButton(
                    text="Failed",
                    on_click=self._on_load_click,
                    style=ft.ButtonStyle(
                        color=Theme.Colors.ERROR,
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                    ),
                )
        except Exception:
            # Error - show with retry option
            self.content = ft.TextButton(
                text="Error",
                on_click=self._on_load_click,
                style=ft.ButtonStyle(
                    color=Theme.Colors.ERROR,
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                ),
            )

        self._page.update()


class UnloadModelButton(ft.Container):
    """Unload button for warm models with loading state and error handling."""

    def __init__(
        self,
        model_name: str,
        page: ft.Page,
        ollama_url: str,
        dialog: OllamaDetailDialog | None = None,
    ) -> None:
        """
        Initialize unload model button.

        Args:
            model_name: Name of the model to unload
            page: Flet page instance for updates
            ollama_url: Ollama server URL
            dialog: Parent dialog for refreshing data after model unload
        """
        super().__init__()
        self._model_name = model_name
        self._page = page
        self._ollama_url = ollama_url
        self._dialog = dialog

        self._button = ft.TextButton(
            text="Unload",
            on_click=self._on_unload_click,
            style=ft.ButtonStyle(
                color=Theme.Colors.WARNING,
                padding=ft.padding.symmetric(horizontal=4, vertical=2),
            ),
        )
        self.content = self._button

    async def _on_unload_click(self, e: ft.ControlEvent) -> None:
        """Handle Unload button click - remove model from VRAM."""
        # Show loading spinner
        self.content = ft.Row(
            [
                ft.ProgressRing(width=16, height=16, stroke_width=2),
                SecondaryText("...", color=Theme.Colors.WARNING),
            ],
            spacing=4,
        )
        self._page.update()

        # Unload the model asynchronously
        try:
            from app.services.ai.ollama import OllamaClient

            client = OllamaClient(base_url=self._ollama_url)
            success = await client.unload_model(self._model_name)

            if success:
                # Model unloaded - refresh the entire modal with fresh health data
                if self._dialog:
                    await self._dialog.refresh_data()
            else:
                # Failed to unload - show error with retry button
                self.content = ft.TextButton(
                    text="Failed",
                    on_click=self._on_unload_click,
                    style=ft.ButtonStyle(
                        color=Theme.Colors.ERROR,
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                    ),
                )
        except Exception:
            # Error - show with retry option
            self.content = ft.TextButton(
                text="Error",
                on_click=self._on_unload_click,
                style=ft.ButtonStyle(
                    color=Theme.Colors.ERROR,
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                ),
            )

        self._page.update()


class OverviewSection(ft.Container):
    """Overview section showing key Ollama metrics."""

    def __init__(self, ollama_component: ComponentStatus, page: ft.Page) -> None:
        """
        Initialize overview section.

        Args:
            ollama_component: Ollama ComponentStatus with metadata
            page: Flet page instance
        """
        super().__init__()
        self.padding = Theme.Spacing.MD

        metadata = ollama_component.metadata or {}

        running_models = metadata.get("running_models", [])
        running_count = metadata.get("running_models_count", 0)
        installed_count = metadata.get("installed_models_count", 0)
        total_vram_gb = metadata.get("total_vram_gb", 0.0)

        # Determine status color based on running models
        if running_count > 0:
            status_text = "Warm"
            status_color = Theme.Colors.SUCCESS
        elif installed_count > 0:
            status_text = "Cold"
            status_color = Theme.Colors.INFO
        else:
            status_text = "No models"
            status_color = Theme.Colors.WARNING

        # Metric cards row
        metrics_row = ft.Row(
            [
                MetricCard(
                    "VRAM Usage",
                    f"{total_vram_gb:.1f} GB",
                    Theme.Colors.SUCCESS if total_vram_gb > 0 else Theme.Colors.INFO,
                ),
                MetricCard(
                    "Models",
                    f"{running_count} / {installed_count}",
                    Theme.Colors.INFO,
                ),
                MetricCard(
                    "Status",
                    status_text,
                    status_color,
                ),
            ],
            spacing=Theme.Spacing.MD,
        )

        # Active models display (full width, below metrics) - show all warm models
        if running_models:
            model_tags = [
                Tag(rm.get("name", "Unknown"), color=Theme.Colors.SUCCESS)
                for rm in running_models
            ]
            active_model_row = ft.Container(
                content=ft.Row(
                    [
                        SecondaryText("Active Models:", width=110),
                        ft.Row(model_tags, spacing=Theme.Spacing.XS, wrap=True),
                    ],
                    spacing=Theme.Spacing.SM,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.only(top=Theme.Spacing.MD),
            )
        else:
            active_model_row = ft.Container(
                content=ft.Row(
                    [
                        SecondaryText("Active Models:", width=110),
                        SecondaryText("None loaded", italic=True),
                    ],
                    spacing=Theme.Spacing.SM,
                ),
                padding=ft.padding.only(top=Theme.Spacing.MD),
            )

        self.content = ft.Column(
            [metrics_row, active_model_row],
            spacing=0,
        )


class ServerInfoSection(ft.Container):
    """Server information section showing connection details."""

    def __init__(self, ollama_component: ComponentStatus, page: ft.Page) -> None:
        """
        Initialize server info section.

        Args:
            ollama_component: Ollama ComponentStatus with metadata
            page: Flet page instance
        """
        super().__init__()
        self.padding = Theme.Spacing.MD

        metadata = ollama_component.metadata or {}
        response_time = ollama_component.response_time_ms or 0

        base_url = metadata.get("base_url", "http://localhost:11434")
        version = metadata.get("version", "Unknown")
        available = metadata.get("available", False)

        def info_row(label: str, value: str) -> ft.Row:
            """Create an info row."""
            return ft.Row(
                [
                    SecondaryText(
                        f"{label}:",
                        weight=Theme.Typography.WEIGHT_SEMIBOLD,
                        width=STAT_LABEL_WIDTH,
                    ),
                    BodyText(value),
                ],
                spacing=Theme.Spacing.MD,
            )

        self.content = ft.Column(
            [
                H3Text("Server Information"),
                ft.Container(height=Theme.Spacing.SM),
                info_row("Base URL", base_url),
                info_row("Version", version if version else "Unknown"),
                info_row("Status", "Available" if available else "Unavailable"),
                info_row("Response Time", f"{response_time:.0f}ms"),
            ],
            spacing=Theme.Spacing.XS,
        )


class ModelsSection(ft.Container):
    """Models section showing all installed models with warm/cold status."""

    def __init__(
        self,
        ollama_component: ComponentStatus,
        page: ft.Page,
        dialog: OllamaDetailDialog | None = None,
    ) -> None:
        """
        Initialize models section.

        Args:
            ollama_component: Ollama ComponentStatus with installed_models
            page: Flet page instance
            dialog: Parent dialog for refreshing data after model load
        """
        super().__init__()
        self._dialog = dialog
        self.padding = Theme.Spacing.MD

        metadata = ollama_component.metadata or {}
        installed_models = metadata.get("installed_models", [])
        running_models = metadata.get("running_models", [])
        total_vram_gb = metadata.get("total_vram_gb", 0.0)
        ollama_url = metadata.get("base_url", "http://localhost:11434")

        # Build a map of running model names to their VRAM usage
        running_model_map: dict[str, float] = {}
        for rm in running_models:
            running_model_map[rm.get("name", "")] = rm.get("size_vram_gb", 0.0)

        # Build row data for DataTable (includes total VRAM row if applicable)
        rows = self._build_rows(
            installed_models, running_model_map, page, ollama_url, dialog, total_vram_gb
        )

        if rows:
            # Build table with data
            table = DataTable(
                columns=MODEL_COLUMNS,
                rows=rows,
                row_padding=6,
                show_header_border=True,
                show_row_borders=True,
                empty_message="No models installed",
            )

            self.content = ft.Column([table], spacing=0)
        else:
            # Empty state
            self.content = ft.Column(
                [
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Icon(
                                    ft.Icons.DOWNLOAD,
                                    size=48,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                                SecondaryText("No models installed"),
                                SecondaryText(
                                    "Use 'ollama pull <model>' to install a model",
                                    size=Theme.Typography.CAPTION,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=Theme.Spacing.SM,
                        ),
                        alignment=ft.alignment.center,
                        expand=True,
                        padding=Theme.Spacing.LG,
                    ),
                ],
                spacing=0,
            )

    def _build_rows(
        self,
        installed_models: list[dict[str, Any]],
        running_model_map: dict[str, float],
        page: ft.Page,
        ollama_url: str,
        dialog: OllamaDetailDialog | None,
        total_vram_gb: float = 0.0,
    ) -> list[list[Any]]:
        """Build row data for DataTable.

        Args:
            installed_models: List of installed model dicts
            running_model_map: Map of running model names to VRAM usage
            page: Flet page instance
            ollama_url: Ollama server URL
            dialog: Parent dialog for refresh
            total_vram_gb: Total VRAM usage to show in footer row

        Returns:
            List of row data lists for DataTable
        """
        rows: list[list[Any]] = []
        for model in installed_models:
            model_name = model.get("name", "")
            is_warm = model_name in running_model_map
            vram_gb = running_model_map.get(model_name)
            size_gb = model.get("size_gb", 0.0)
            details = model.get("details", {})
            parameter_size = details.get("parameter_size", "—")
            quantization = details.get("quantization_level", "—")

            # Apply opacity for cold models
            opacity = 1.0 if is_warm else 0.5

            # Build styled text controls with opacity
            name_text = BodyText(model_name, size=Theme.Typography.BODY_SMALL)
            name_text.opacity = opacity

            params_text = SecondaryText(
                parameter_size if parameter_size else "—",
                size=Theme.Typography.CAPTION,
            )
            params_text.opacity = opacity

            quant_text = SecondaryText(
                format_quantization(quantization),
                size=Theme.Typography.CAPTION,
            )
            quant_text.opacity = opacity

            size_text = SecondaryText(
                f"{size_gb:.1f}G",
                size=Theme.Typography.CAPTION,
            )
            size_text.opacity = opacity

            # VRAM: show value for warm, dash for cold
            vram_display = f"{vram_gb:.1f}G" if is_warm and vram_gb is not None else "—"
            vram_text = SecondaryText(
                vram_display,
                size=Theme.Typography.CAPTION,
            )
            vram_text.opacity = opacity

            # Status: Unload button for warm models, Load button for cold
            if is_warm:
                status_control: ft.Control = UnloadModelButton(
                    model_name=model_name,
                    page=page,
                    ollama_url=ollama_url,
                    dialog=dialog,
                )
            else:
                status_control = LoadModelButton(
                    model_name=model_name,
                    page=page,
                    ollama_url=ollama_url,
                    dialog=dialog,
                )

            rows.append(
                [
                    name_text,
                    params_text,
                    quant_text,
                    size_text,
                    vram_text,
                    status_control,
                ]
            )

        # Add total VRAM footer row if any models are loaded
        if total_vram_gb > 0:
            total_label = SecondaryText(
                "Total VRAM",
                weight=Theme.Typography.WEIGHT_BOLD,
                size=Theme.Typography.CAPTION,
            )
            total_value = SecondaryText(
                f"{total_vram_gb:.1f}G",
                weight=Theme.Typography.WEIGHT_BOLD,
                size=Theme.Typography.CAPTION,
            )
            # Empty cells for alignment (Params, Quant, Size columns)
            rows.append(
                [
                    total_label,
                    SecondaryText(""),  # Params
                    SecondaryText(""),  # Quant
                    SecondaryText(""),  # Size
                    total_value,  # VRAM
                    SecondaryText(""),  # Status
                ]
            )

        return rows


# =============================================================================
# Tab Containers
# =============================================================================


class OverviewTab(ft.Container):
    """Overview tab combining metrics and server info."""

    def __init__(self, component_data: ComponentStatus, page: ft.Page) -> None:
        super().__init__()
        self.content = ft.Column(
            [
                OverviewSection(component_data, page),
                ServerInfoSection(component_data, page),
            ],
            scroll=ft.ScrollMode.AUTO,
        )
        self.padding = ft.padding.all(Theme.Spacing.SM)
        self.expand = True


class ModelsTab(ft.Container):
    """Models tab showing all installed models with warm/cold status."""

    def __init__(
        self,
        component_data: ComponentStatus,
        page: ft.Page,
        dialog: OllamaDetailDialog | None = None,
    ) -> None:
        super().__init__()
        self.content = ft.Column(
            [ModelsSection(component_data, page, dialog=dialog)],
            scroll=ft.ScrollMode.AUTO,
        )
        self.padding = ft.padding.all(Theme.Spacing.SM)
        self.expand = True


# =============================================================================
# Main Dialog
# =============================================================================


class OllamaDetailDialog(BaseDetailPopup):
    """
    Ollama local LLM infrastructure detail popup dialog.

    Displays comprehensive Ollama information including running models,
    VRAM usage, and server configuration.
    """

    def __init__(self, component_data: ComponentStatus, page: ft.Page) -> None:
        """
        Initialize the Ollama details popup.

        Args:
            component_data: ComponentStatus containing component health and metrics
            page: Flet page instance
        """
        self._page = page
        self._component_data = component_data

        metadata = component_data.metadata or {}
        version = metadata.get("version", "")
        running_count = metadata.get("running_models_count", 0)

        # Build subtitle - show Ollama with version and model count
        subtitle = self._build_subtitle(version, running_count)

        # Build tabs - store references for refresh
        self._overview_tab = ft.Tab(
            text="Overview", content=OverviewTab(component_data, page)
        )
        self._models_tab = ft.Tab(
            text="Models", content=ModelsTab(component_data, page, dialog=self)
        )

        self._tabs = ft.Tabs(
            selected_index=0,
            animation_duration=200,
            tabs=[self._overview_tab, self._models_tab],
            expand=True,
            label_color=ft.Colors.ON_SURFACE,
            unselected_label_color=ft.Colors.ON_SURFACE_VARIANT,
            indicator_color=ft.Colors.ON_SURFACE_VARIANT,
        )

        # Initialize base popup with tabs
        super().__init__(
            page=page,
            component_data=component_data,
            title_text="Inference",
            subtitle_text=subtitle,
            sections=[self._tabs],
            scrollable=False,
            width=700,
            height=550,
            status_detail=get_status_detail(component_data),
        )

    def _build_subtitle(self, version: str, running_count: int) -> str:
        """Build subtitle text based on version and running model count."""
        subtitle = f"Ollama v{version}" if version else "Ollama"
        if running_count > 0:
            status = f"{running_count} model{'s' if running_count > 1 else ''} loaded"
            subtitle = f"{subtitle} • {status}"
        return subtitle

    async def refresh_data(self) -> None:
        """Refresh modal with fresh health data after model load."""
        from app.services.system.health import check_ollama_health

        fresh_status = await check_ollama_health()

        # Update stored component data
        self._component_data = fresh_status

        # Update subtitle with fresh counts
        metadata = fresh_status.metadata or {}
        version = metadata.get("version", "")
        running_count = metadata.get("running_models_count", 0)
        new_subtitle = self._build_subtitle(version, running_count)

        # Update subtitle in title row (second element in title column)
        if self._title_row and len(self._title_row.controls) > 0:
            title_column = self._title_row.controls[0]
            if hasattr(title_column, "controls") and len(title_column.controls) > 1:
                title_column.controls[1].value = new_subtitle

        # Update the status badge in the header
        self.update_status(fresh_status.status, get_status_detail(fresh_status))

        # Preserve current tab selection
        current_tab_index = self._tabs.selected_index

        # Rebuild tab contents with fresh data
        self._overview_tab.content = OverviewTab(fresh_status, self._page)
        self._models_tab.content = ModelsTab(fresh_status, self._page, dialog=self)

        # Restore tab selection
        self._tabs.selected_index = current_tab_index

        self._page.update()
