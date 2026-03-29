"""Stunning marketing-grade dashboard with professional component cards."""

import asyncio
from collections.abc import Awaitable, Callable
import json
import time
from typing import Any

import flet as ft
from flet import PageDisconnectedException
import httpx

from app.core.log import logger
from app.services.system.models import ComponentStatus, ComponentStatusType

from .dashboard.activity_feed import ActivityFeed
from .dashboard.cards import (




    DatabaseCard,





    RedisCard,


    ServerCard,


    WorkerCard,

)
from .dashboard.cards.card_utils import create_health_status_indicator
from .dashboard.diagram import DiagramView
from .dashboard.status_overview import StatusOverviewPanel
from .theme import AegisTheme as Theme, ThemeManager

# Constants for health system grouping
COMPONENTS_GROUP_KEY = "components"
SERVICES_GROUP_KEY = "services"
SERVICE_PREFIX = "service_"

# Use simple filenames - Flet should auto-resolve from assets_dir
DEFAULT_LOGO_PATH = "aegis-manifesto.png"
DEFAULT_DARK_LOGO_PATH = "aegis-manifesto-dark.png"


def _format_uptime(start: float) -> str:
    """Format elapsed time since start as a compact uptime string."""
    elapsed = int(time.monotonic() - start)
    minutes = elapsed // 60
    hours = minutes // 60
    days = hours // 24
    if days > 0:
        return f"Up {days}d {hours % 24}h"
    elif hours > 0:
        return f"Up {hours}h {minutes % 60}m"
    elif minutes > 0:
        return f"Up {minutes}m"
    else:
        return "Up <1m"


def _convert_component(comp_data: dict[str, Any]) -> ComponentStatus:
    """Recursively convert API component data to ComponentStatus."""
    try:
        sub_components = {}
        if "sub_components" in comp_data:
            for sub_name, sub_data in comp_data[
                "sub_components"
            ].items():
                sub_components[sub_name] = _convert_component(sub_data)

        # Parse status from API response
        status_str = comp_data.get("status", "unhealthy")
        try:
            status = ComponentStatusType(status_str)
        except ValueError:
            logger.warning(
                f"Unknown status: {status_str}, default UNHEALTHY"
            )
            status = ComponentStatusType.UNHEALTHY

        return ComponentStatus(
            name=comp_data.get("name", "Unknown"),
            status=status,
            message=comp_data.get("message", "No message"),
            response_time_ms=comp_data.get("response_time_ms"),
            metadata=comp_data.get("metadata", {}),
            sub_components=sub_components,
        )
    except Exception as e:
        logger.error(
            f"Failed to convert component data: {e}",
            exc_info=True,
            extra={
                "error_type": type(e).__name__,
                "function": "_convert_component",
                "comp_data": comp_data
            }
        )
        # Return a fallback ComponentStatus
        return ComponentStatus(
            name=comp_data.get("name", "Unknown"),
            status=ComponentStatusType.UNHEALTHY,
            message=f"Error converting component: {e}",
            response_time_ms=None,
            metadata={},
            sub_components={},
        )


class SystemDashboard:
    """
    Professional system dashboard with safe component references.

    Eliminates IndexError crashes by storing direct references to dashboard
    components instead of using brittle index-based access patterns.

    Includes robust page disconnection handling to prevent crashes when
    users navigate away from the dashboard during auto-refresh cycles.

    Note: Uses defensive programming around Flet's private APIs for
    connection checking. This may need updates with future Flet versions.
    """

    def __init__(self):
        # Direct component references - no more brittle indexing!
        self._health_indicator_container: ft.Container | None = None
        self._cards_container: ft.Container | None = None
        self._status_overview_panel: StatusOverviewPanel | None = None
        self._activity_feed: ActivityFeed | None = None
        self._diagram_view: DiagramView | None = None
        self._theme_manager: ThemeManager | None = None
        self._logo_image: ft.Image | None = None
        self._page: ft.Page | None = None

    def initialize_components(
        self,
        health_indicator_container: ft.Container,
        cards_container: ft.Container,
        status_overview_panel: StatusOverviewPanel,
        activity_feed: ActivityFeed,
        diagram_view: DiagramView,
        theme_manager: ThemeManager,
        logo_image: ft.Image,
        page: ft.Page,
    ) -> None:
        """Initialize dashboard with component references."""
        self._health_indicator_container = health_indicator_container
        self._cards_container = cards_container
        self._status_overview_panel = status_overview_panel
        self._activity_feed = activity_feed
        self._diagram_view = diagram_view
        self._theme_manager = theme_manager
        self._logo_image = logo_image
        self._page = page

        # Log Flet version for debugging connection check compatibility
        try:
            from importlib.metadata import version

            flet_version = version("flet")
            logger.debug(f"Initializing dashboard with Flet version: {flet_version}")
        except Exception:
            logger.debug("Flet version not available for compatibility logging")

    def _is_page_connected(self) -> bool:
        """
        Check if the page is still connected.

        Note: This uses Flet's private attribute access as a last resort.
        This is necessary because Flet doesn't provide a public API for
        connection status checking. While brittle, this prevents crashes
        when users navigate away from the dashboard.

        Returns False on any error to fail safely.
        """
        try:
            if self._page is None:
                return False

            # Attempt to access Flet's private connection attribute
            # This may break with future Flet versions, but will fail safely
            if not hasattr(self._page, '_Page__conn'):
                logger.debug(
                    "Flet page connection attribute not found - assuming disconnected"
                )
                return False

            return self._page._Page__conn is not None

        except (AttributeError, Exception) as e:
            # If anything goes wrong with connection checking, assume disconnected
            # This provides defensive behavior against Flet internal changes
            logger.debug(f"Page connection check failed, assuming disconnected: {e}")
            return False

    async def update_health_status(
        self,
        healthy_count: int,
        total_count: int,
        worst_status: ComponentStatusType | None = None,
    ) -> None:
        """Safely update health status indicator."""
        if not self._is_page_connected():
            logger.debug("Page disconnected, skipping health status update")
            return

        if not self._health_indicator_container:
            logger.warning("Health indicator container not initialized")
            return

        try:
            new_health_indicator = create_health_status_indicator(
                healthy_count, total_count, worst_status
            )
            self._health_indicator_container.content = new_health_indicator
            # No .update() call here - batched with
            # page.update() in refresh_dashboard
        except PageDisconnectedException:
            logger.debug("Page disconnected during health status update")
            return
        except Exception as e:
            logger.error(
                f"Failed to update health status: {e}",
                exc_info=True,
                extra={
                    "error_type": type(e).__name__,
                    "function": "update_health_status",
                    "healthy_count": healthy_count,
                    "total_count": total_count,
                }
            )

    async def update_component_cards(
        self, components: dict[str, ComponentStatus], card_creator_fn: Callable
    ) -> None:
        """Safely update component cards."""
        if not self._is_page_connected():
            logger.debug("Page disconnected, skipping component cards update")
            return

        if not self._cards_container or not self._cards_container.content:
            logger.warning("Cards container not initialized")
            return

        try:
            # Clear existing cards
            self._cards_container.content.controls.clear()

            # Create cards for all available components with responsive sizing
            for component_name, component_data in components.items():
                card = card_creator_fn(component_name, component_data)

                # Skip empty cards (e.g., frontend merged into ServerCard)
                if not card.content:
                    continue

                if (
                    isinstance(card.content, ft.Text)
                    and "Unknown component" in card.content.value
                ):
                    continue  # Skip unknown components

                # All cards use uniform 1/3 width (3-column grid)
                card.col = {"xs": 12, "sm": 6, "md": 4, "lg": 4, "xl": 4}
                self._cards_container.content.controls.append(card)

            # No .update() call here - batched with
            # page.update() in refresh_dashboard
        except PageDisconnectedException:
            logger.debug("Page disconnected during component cards update")
            return
        except Exception as e:
            logger.error(
                f"Failed to update component cards: {e}",
                exc_info=True,
                extra={
                    "error_type": type(e).__name__,
                    "function": "update_component_cards",
                    "component_count": len(components),
                }
            )

    async def update_status_overview(
        self, components: dict[str, ComponentStatus]
    ) -> None:
        """Safely update the status overview panel and activity feed."""
        if not self._is_page_connected():
            logger.debug("Page disconnected, skipping status overview update")
            return

        if not self._status_overview_panel:
            logger.debug("Status overview panel not initialized")
            return

        try:
            self._status_overview_panel.update_components(components)

            # Also refresh the activity feed
            if self._activity_feed:
                self._activity_feed.refresh()

            # No .update() calls here - batched with
            # page.update() in refresh_dashboard
        except PageDisconnectedException:
            logger.debug("Page disconnected during status overview update")
            return
        except Exception as e:
            logger.error(
                f"Failed to update status overview: {e}",
                exc_info=True,
                extra={
                    "error_type": type(e).__name__,
                    "function": "update_status_overview",
                    "component_count": len(components),
                }
            )

    async def update_diagram_view(
        self, components: dict[str, ComponentStatus]
    ) -> None:
        """Safely update the diagram view."""
        if not self._is_page_connected():
            logger.debug("Page disconnected, skipping diagram view update")
            return

        if not self._diagram_view:
            logger.debug("Diagram view not initialized")
            return

        try:
            self._diagram_view.update_components(components)
            # No .update() calls here - batched with
            # page.update() in refresh_dashboard
        except PageDisconnectedException:
            logger.debug("Page disconnected during diagram view update")
            return
        except Exception as e:
            logger.error(
                f"Failed to update diagram view: {e}",
                exc_info=True,
                extra={
                    "error_type": type(e).__name__,
                    "function": "update_diagram_view",
                    "component_count": len(components),
                }
            )

    async def show_error_status(self) -> None:
        """Safely show error status in health indicator."""
        if not self._is_page_connected():
            logger.debug("Page disconnected, skipping error status display")
            return

        if not self._health_indicator_container:
            logger.warning(
                "Health indicator container not initialized for error display"
            )
            return

        try:
            error_indicator = create_health_status_indicator(0, 1)
            self._health_indicator_container.content = error_indicator
            # Check connection again before updating container
            if self._is_page_connected():
                self._health_indicator_container.update()
        except PageDisconnectedException:
            logger.debug("Page disconnected during error status display")
            return
        except Exception as e:
            logger.error(
                f"Failed to show error status: {e}",
                exc_info=True,
                extra={
                    "error_type": type(e).__name__,
                    "function": "show_error_status",
                }
            )


# Load both light and dark logos as base64
def get_logo_base64(dark_mode: bool = False) -> str:
    """Get the Overseer logo as base64."""
    try:
        import base64
        from pathlib import Path

        # Use overseer.png for both light and dark mode
        logo_path = (
            Path(__file__).parent.parent.parent.parent / "assets" / "overseer.png"
        )
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        # Fallback to tiny red pixel if file read fails
        return (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHg"
            "gJ/PchI7wAAAABJRU5ErkJggg=="
        )


def create_frontend_app() -> Callable[[ft.Page], Awaitable[None]]:
    """Returns the Flet target function - simple system health dashboard."""

    async def flet_main(page: ft.Page) -> None:
        page.title = "Aegis Stack - System Dashboard"
        page.padding = ft.padding.only(
            left=12, right=12, top=12, bottom=12
        )  # Compact padding
        # No page scroll - content scrolls below fixed header

        # Simple theme setup
        theme_manager = ThemeManager(page)
        await theme_manager.initialize_themes()

        # Aegis Stack logo - theme-aware loading
        logo_image = ft.Image(
            src_base64=get_logo_base64(theme_manager.is_dark_mode),
            width=96,
            height=96,
            fit=ft.ImageFit.CONTAIN,
            error_content=ft.Text(
                "OVERSEER",
                size=20,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.ON_SURFACE,
            ),
        )

        # Theme toggle button
        theme_button = ft.IconButton(
            icon=ft.Icons.DARK_MODE,
            tooltip="Switch to Dark Mode",
            icon_size=24,
            icon_color=Theme.Colors.TEXT_SECONDARY,
        )

        # View toggle button - cycle between Stack, Cards, and Diagram views
        view_toggle_button = ft.IconButton(
            icon=ft.Icons.VIEW_LIST,
            tooltip="Switch to Cards View",
            icon_size=24,
            icon_color=Theme.Colors.TEXT_SECONDARY,
        )
        # View state: 0=stack, 1=cards, 2=diagram
        current_view = 0

        async def update_logo() -> None:
            """Update logo based on current theme."""
            try:
                # Update the base64 source for the current theme
                logo_image.src_base64 = get_logo_base64(theme_manager.is_dark_mode)
                logo_image.src = None  # Clear the src to use src_base64
            except Exception as e:
                logger.error(
                    f"Logo update failed: {e}",
                    exc_info=True,
                    extra={
                        "error_type": type(e).__name__,
                        "function": "update_logo",
                        "is_dark_mode": getattr(
                            theme_manager, 'is_dark_mode', 'unknown'
                        )
                    }
                )

        async def toggle_theme(_: Any) -> None:
            """Toggle theme and update button icon and logo."""
            try:
                await theme_manager.toggle_theme()
                if theme_manager.is_dark_mode:
                    theme_button.icon = ft.Icons.LIGHT_MODE
                    theme_button.tooltip = "Switch to Light Mode"
                else:
                    theme_button.icon = ft.Icons.DARK_MODE
                    theme_button.tooltip = "Switch to Dark Mode"

                # Update logo immediately after theme change
                await update_logo()
                # Safe updates - check connection first
                if dashboard._is_page_connected():
                    try:
                        logo_image.update()
                        page.update()
                    except PageDisconnectedException:
                        logger.debug("Page disconnected during theme toggle")
            except PageDisconnectedException:
                logger.debug("Page disconnected during theme toggle")
            except Exception as e:
                logger.error(
                    f"Theme toggle failed: {e}",
                    exc_info=True,
                    extra={
                        "error_type": type(e).__name__,
                        "function": "toggle_theme"
                    }
                )

        theme_button.on_click = toggle_theme

        # Set initial logo based on current theme after theme manager is ready
        await update_logo()

        # Health status indicator with circular progress - create before header
        health_status_indicator = create_health_status_indicator(
            0, 0
        )  # Start with loading state

        # Create health indicator container with direct reference
        # (no more brittle indexing)
        health_indicator_container = ft.Container(
            content=health_status_indicator,
            margin=ft.margin.only(right=20),  # Space before theme button
        )

        # Subtle uptime indicator - updated on each refresh cycle
        _session_start = time.monotonic()
        uptime_text = ft.Text(
            value=_format_uptime(_session_start),
            size=Theme.Typography.CAPTION,
            color=Theme.Colors.TEXT_SECONDARY,
            weight=ft.FontWeight.W_400,
            opacity=0.7,
        )

        # Wrap health indicator + uptime in a column
        health_with_uptime = ft.Column(
            [
                health_indicator_container,
                ft.Container(
                    content=uptime_text,
                    alignment=ft.alignment.center,
                ),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Header with modern layout: logo left, status+controls right
        header = ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=logo_image,
                        padding=ft.padding.all(10),
                    ),
                    ft.Row(
                        [
                            health_with_uptime,  # Health status + uptime
                            # View toggle
                            ft.Container(content=view_toggle_button, padding=10),
                            # Theme toggle
                            ft.Container(content=theme_button, padding=10),
                        ],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            margin=ft.margin.only(bottom=8),
            padding=ft.padding.only(left=0, right=0),  # Remove any default padding
        )
        # Status overview panel - compact view of all components
        status_overview_panel = StatusOverviewPanel()

        # Activity feed panel - expands to fill available space
        activity_feed = ActivityFeed()

        # Stack view: Status overview + Activity feed (50/50 split)
        # Activity feed expands to fill remaining vertical space
        top_row = ft.ResponsiveRow(
            controls=[
                ft.Container(
                    content=status_overview_panel,
                    col={"xs": 12, "sm": 12, "md": 6, "lg": 6, "xl": 6},
                ),
                ft.Container(
                    content=activity_feed,
                    col={"xs": 12, "sm": 12, "md": 6, "lg": 6, "xl": 6},
                    expand=True,
                ),
            ],
            spacing=20,
            run_spacing=20,
            expand=True,
        )

        # Responsive grid container for cards
        component_cards_container = ft.Container(
            content=ft.ResponsiveRow(
                controls=[],  # Will be populated with cards
                spacing=20,  # Space between cards
                run_spacing=20,  # Space between rows
            ),
            alignment=ft.alignment.center,
        )

        # Assign to the view containers (defined earlier for toggle_view access)
        # Cards view has its own scroll for when there are many cards
        cards_view_container = ft.Column(
            controls=[component_cards_container],
            scroll=ft.ScrollMode.AUTO,
            visible=False,
            expand=True,
        )

        stack_view_container = ft.Container(
            content=top_row,
            visible=True,
            expand=True,
        )

        # Diagram view for architecture visualization
        diagram_view = DiagramView()
        diagram_view_container = ft.Container(
            content=diagram_view,
            visible=False,
            expand=True,
            alignment=ft.alignment.center,
        )

        # View toggle handler (defined after containers exist)
        async def toggle_view(_: Any) -> None:
            """Cycle through Stack, Cards, and Diagram views."""
            nonlocal current_view
            try:
                # Cycle: 0 (stack) -> 1 (cards) -> 2 (diagram) -> 0 (stack)
                current_view = (current_view + 1) % 3

                # Update visibility and button state
                if current_view == 0:  # Stack view
                    view_toggle_button.icon = ft.Icons.VIEW_LIST
                    view_toggle_button.tooltip = "Switch to Cards View"
                    stack_view_container.visible = True
                    cards_view_container.visible = False
                    diagram_view_container.visible = False
                elif current_view == 1:  # Cards view
                    view_toggle_button.icon = ft.Icons.GRID_VIEW
                    view_toggle_button.tooltip = "Switch to Diagram View"
                    stack_view_container.visible = False
                    cards_view_container.visible = True
                    diagram_view_container.visible = False
                else:  # Diagram view (current_view == 2)
                    view_toggle_button.icon = ft.Icons.ACCOUNT_TREE
                    view_toggle_button.tooltip = "Switch to Stack View"
                    stack_view_container.visible = False
                    cards_view_container.visible = False
                    diagram_view_container.visible = True

                page.update()
            except PageDisconnectedException:
                logger.debug("Page disconnected during view toggle")
            except Exception as e:
                logger.error(
                    f"View toggle failed: {e}",
                    exc_info=True,
                    extra={
                        "error_type": type(e).__name__,
                        "function": "toggle_view"
                    }
                )

        view_toggle_button.on_click = toggle_view

        # Create SystemDashboard with safe component references
        dashboard = SystemDashboard()

        # Initialize dashboard with component references (using direct references)
        dashboard.initialize_components(
            health_indicator_container=health_indicator_container,
            cards_container=component_cards_container,
            status_overview_panel=status_overview_panel,
            activity_feed=activity_feed,
            diagram_view=diagram_view,
            theme_manager=theme_manager,
            logo_image=logo_image,
            page=page,
        )

        # Add everything to page with modern layout
        # Header stays fixed, content below scrolls when zoomed in
        page.add(
            header,
            ft.Container(
                content=ft.Column(
                    [
                        stack_view_container,   # Stack + Activity view (default)
                        cards_view_container,   # Cards view
                        diagram_view_container, # Diagram view
                    ],
                    spacing=20,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    scroll=ft.ScrollMode.AUTO,  # Content scrolls, header stays fixed
                ),
                alignment=ft.alignment.top_center,
                expand=True,
            ),
        )

        # Persistent HTTP client - reused across refresh cycles, closed on exit
        http_client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))

        def create_component_card(
            component_name: str, component_data: Any
        ) -> ft.Container:
            """Create stunning marketing-grade component cards."""
            try:
                if not component_data:
                    logger.warning(f"No component data provided for {component_name}")
                    return ft.Container()

                # Map component names to their stunning card classes
                if component_name == "backend":
                    return ServerCard(component_data).build()
                elif component_name == "frontend":
                    # Frontend is merged into ServerCard, return empty
                    return ft.Container()

                elif component_name == "worker":
                    return WorkerCard(component_data).build()


                elif component_name == "cache":
                    return RedisCard(component_data).build()


                elif component_name == "database":
                    return DatabaseCard(component_data).build()






                # Service cards - specific checks BEFORE generic fallback




                else:
                    # Fallback for unknown components - should not happen in practice
                    logger.warning(f"Unknown component type: {component_name}")
                    return ft.Container(
                        content=ft.Text(f"Unknown component: {component_name}"),
                        padding=20,
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        border_radius=16,
                        width=800,
                        height=240,
                    )
            except Exception as e:
                logger.error(
                    f"Failed to create component card for {component_name}: {e}",
                    exc_info=True,
                    extra={
                        "error_type": type(e).__name__,
                        "function": "create_component_card",
                        "component_name": component_name,
                        "component_data": component_data
                    }
                )
                # Return fallback card on error
                return ft.Container(
                    content=ft.Text(f"Error loading {component_name}"),
                    padding=20,
                    bgcolor=ft.Colors.ERROR_CONTAINER,
                    border=ft.border.all(1, ft.Colors.ERROR),
                    border_radius=16,
                    width=800,
                    height=240,
                )

        async def refresh_dashboard() -> None:
            """Refresh the stunning marketing-grade dashboard."""
            try:
                # Use the single /health/ endpoint for all health data
                response = await http_client.get("http://localhost:8000/health/")
                data = response.json()

                # Extract components from health API response (navigate structure)
                if "components" in data and "aegis" in data["components"]:
                    aegis_component = data["components"]["aegis"]
                    if "sub_components" in aegis_component:
                        api_components = aegis_component["sub_components"]
                    else:
                        api_components = {}
                else:
                    api_components = {}

                components = {}
                for name, comp_data in api_components.items():
                    # Special handling for "components" grouping - expand it
                    if name == COMPONENTS_GROUP_KEY and "sub_components" in comp_data:
                        # Add all individual components from the grouping
                        for sub_name, sub_data in comp_data["sub_components"].items():
                            components[sub_name] = _convert_component(sub_data)
                    # Special handling for "services" grouping - expand services
                    elif name == SERVICES_GROUP_KEY and "sub_components" in comp_data:
                        # Add all individual services from the grouping
                        for service_name, service_data in comp_data[
                            "sub_components"
                        ].items():
                            components[
                                f"{SERVICE_PREFIX}{service_name}"
                            ] = _convert_component(service_data)
                    else:
                        # For other groupings, add as-is
                        components[name] = _convert_component(comp_data)

                total_components = len(components)
                healthy_components = len([c for c in components.values() if c.healthy])

                # Determine worst status for color coding
                # Priority: UNHEALTHY > WARNING > INFO > HEALTHY
                worst_status = ComponentStatusType.HEALTHY
                for c in components.values():
                    if c.status == ComponentStatusType.UNHEALTHY:
                        worst_status = ComponentStatusType.UNHEALTHY
                        break
                    elif c.status == ComponentStatusType.WARNING:
                        worst_status = ComponentStatusType.WARNING
                    elif c.status == ComponentStatusType.INFO and worst_status not in (
                        ComponentStatusType.WARNING,
                        ComponentStatusType.UNHEALTHY,
                    ):
                        worst_status = ComponentStatusType.INFO

                # Update health status, status overview, diagram, and component cards
                await dashboard.update_health_status(
                    healthy_components, total_components, worst_status
                )
                await dashboard.update_status_overview(components)
                await dashboard.update_diagram_view(components)
                await dashboard.update_component_cards(
                    components, create_component_card
                )

                # Update uptime display
                uptime_text.value = _format_uptime(_session_start)

                # Safe page update - check connection first
                if dashboard._is_page_connected():
                    try:
                        page.update()
                    except PageDisconnectedException:
                        logger.debug("Page disconnected during page.update()")
                        raise

            except PageDisconnectedException:
                logger.debug("Page disconnected during dashboard refresh")
                # Do NOT call show_error_status here: the page is already disconnected,
                # so any attempt to update the UI (including showing an error) fails.
                # Instead, propagate this exception so the auto_refresh loop can handle
                # the disconnection gracefully and stop further updates.
                raise
            except httpx.TimeoutException:
                # Health endpoint slow (e.g. during load tests) — skip this cycle
                logger.warning("Dashboard refresh skipped: health endpoint timed out")
            except Exception as e:
                logger.error(
                    f"Dashboard refresh failed: {e}",
                    exc_info=True,
                    extra={
                        "error_type": type(e).__name__,
                        "function": "refresh_dashboard"
                    }
                )
                # Show error indicator using safe dashboard method
                await dashboard.show_error_status()

        # Register refresh function on page.data for access by any component
        if page.data is None:
            page.data = {}
        page.data["refresh_dashboard"] = refresh_dashboard

        # Consecutive disconnect checks before declaring page truly dead.
        # Flet sessions reconnect within a few seconds — this grace period
        # prevents background tasks from exiting during transient blips.
        _disconnect_grace_checks = 30  # ~30s at 1s per check
        _consecutive_disconnects = 0

        def _is_alive() -> bool:
            """Check if the page is still alive.

            Tolerates transient WebSocket disconnects (Flet session reconnects)
            by requiring multiple consecutive failures before returning False.
            """
            nonlocal _consecutive_disconnects
            if dashboard._is_page_connected():
                _consecutive_disconnects = 0
                return True
            _consecutive_disconnects += 1
            if _consecutive_disconnects >= _disconnect_grace_checks:
                logger.debug("Page permanently disconnected after grace period")
                return False
            return True  # Still within grace period

        async def auto_refresh() -> None:
            """Auto-refresh loop. Exits on page disconnect to allow clean shutdown.

            On hot-reload, uvicorn kills the process and starts fresh —
            flet_main runs again with a new http_client and new tasks.
            """
            while _is_alive():
                try:
                    await refresh_dashboard()
                    await asyncio.sleep(30)
                except PageDisconnectedException:
                    # Transient disconnect — skip this cycle, loop will retry
                    logger.debug("Page disconnected during refresh, retrying")
                    await asyncio.sleep(5)
                except Exception as e:
                    logger.error(f"Error in auto-refresh loop: {e}", exc_info=True)
                    await asyncio.sleep(30)


        # How often the frontend pushes UI updates to the browser (seconds).
        # Events are received and counted immediately; only rendering is throttled.
        _UI_FLUSH_INTERVAL = 0.1

        async def flush_worker_modal() -> None:
            """Periodically flush dirty worker modal UI updates.

            Runs independently of the SSE listener so that the final batch
            of events is always rendered — even when the stream goes quiet
            and aiter_lines() blocks waiting for the next event.
            """
            while _is_alive():
                await asyncio.sleep(_UI_FLUSH_INTERVAL)
                worker_popup = page.data.get(
                    "_modal_cache", {}
                ).get("worker")
                if worker_popup and worker_popup.visible:
                    try:
                        worker_popup.flush()
                    except PageDisconnectedException:
                        # Transient disconnect — skip this flush, loop will retry
                        pass
                    except Exception as e:
                        logger.debug(f"Worker modal flush failed: {e}")

        async def listen_for_worker_events() -> None:
            """
            Listen to SSE worker events and update the worker modal directly.

            On connect, receives a "totals" event with absolute counters
            (baseline). Then receives individual job events as deltas.
            On reconnect, a new baseline is sent automatically.

            UI updates are flushed by a separate periodic task, not inline,
            so the last batch always renders even when the stream goes quiet.

            Survives transient page disconnects (Flet session reconnects).
            Only exits when _is_alive() returns False after the grace period.
            """
            logger.info("SSE: starting worker event listener")
            while _is_alive():
                try:
                    logger.info("SSE: connecting to /events/worker/stream")
                    async with http_client.stream(
                        "GET", "http://localhost:8000/events/worker/stream",
                        timeout=httpx.Timeout(
                            connect=5.0, read=15.0, write=5.0, pool=5.0,
                        ),
                    ) as response:
                        logger.info(
                            f"SSE: connected, status={response.status_code}"
                        )
                        async for line in response.aiter_lines():
                            if not _is_alive():
                                return
                            if not line.startswith("data: "):
                                continue

                            try:
                                event = json.loads(line[6:])
                            except (json.JSONDecodeError, ValueError):
                                continue

                            event_type = event.get("type", "")
                            queue = event.get("queue", "")

                            worker_popup = page.data.get(
                                "_modal_cache", {}
                            ).get("worker")
                            if not worker_popup:
                                continue

                            try:
                                # Absolute baseline (sent once on connect)
                                if event_type == "totals":
                                    worker_popup.set_totals(
                                        event.get("queues", {})
                                    )
                                # Individual deltas
                                elif event_type == "job.enqueued" and queue:
                                    worker_popup.increment_queued(queue)
                                elif event_type == "job.started" and queue:
                                    worker_popup.increment_ongoing(queue)
                                    worker_popup.decrement_queued(queue)
                                elif event_type == "job.completed" and queue:
                                    worker_popup.increment_completed(queue)
                                elif event_type == "job.failed" and queue:
                                    worker_popup.increment_failed(queue)
                            except PageDisconnectedException:
                                # Transient disconnect — break inner loop,
                                # outer loop will reconnect after sleep
                                break
                            except Exception as e:
                                logger.debug(
                                    f"SSE modal update failed: {e}"
                                )

                except PageDisconnectedException:
                    # Transient disconnect — sleep and retry
                    logger.debug("SSE: page disconnected, retrying in 5s")
                    await asyncio.sleep(5)
                except Exception as e:
                    logger.info(f"SSE: connection error: {e}, reconnecting in 5s")
                    await asyncio.sleep(5)
            logger.info("SSE: listener exiting (page permanently disconnected)")


        # Initial load and start refresh
        await refresh_dashboard()

        asyncio.create_task(listen_for_worker_events())
        asyncio.create_task(flush_worker_modal())

        asyncio.create_task(auto_refresh())

    return flet_main
