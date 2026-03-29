"""
Professional button components for Aegis Stack dashboard.

Provides reusable, theme-aware button components with consistent styling,
hover effects, and semantic variants for common actions.
"""

from collections.abc import Callable
from dataclasses import asdict

import flet as ft
from app.components.frontend import styles
from app.components.frontend.controls.text import BodyText, H3Text


class BaseElevatedButton(ft.ElevatedButton):
    """
    Base elevated button with consistent styling and hover effects.

    Features:
    - Dramatic elevation changes on hover (4→8)
    - Fast animations (100ms)
    - Consistent height and padding
    - Theme-aware colors
    """

    def __init__(
        self,
        on_click_callable: Callable,
        style: ft.ButtonStyle,
        text: str,
        text_style: styles.ButtonTextStyle,
        *args,
        **kwargs,
    ) -> None:
        super().__init__()
        self.on_click_callable = on_click_callable
        self.style = style
        self.text = text
        self.text_style = text_style
        self.args = args
        self.content = ft.Text(self.text, **asdict(self.text_style))
        self.on_click = lambda _: self.on_click_callable()
        self.on_hover = self.on_hover_event  # type: ignore[assignment]
        self.kwargs = kwargs
        self.height = 36  # Consistent button height

    def on_hover_event(self, e: ft.HoverEvent) -> None:
        """Handle hover events for visual feedback."""
        # Elevation changes handled by ButtonStyle
        if self.page:
            self.update()


class ElevatedAddButton(BaseElevatedButton):
    """Button for add/create actions."""

    def __init__(
        self, on_click_callable: Callable, text: str = "Add", **kwargs
    ) -> None:
        super().__init__(
            on_click_callable,
            style=styles.ELEVATED_BUTTON_ADD_STYLE,
            text=text,
            text_style=styles.AddButtonTextStyle,
            **kwargs,
        )


class ElevatedUpdateButton(BaseElevatedButton):
    """Button for update/edit actions."""

    def __init__(
        self, on_click_callable: Callable, text: str = "Update", **kwargs
    ) -> None:
        super().__init__(
            on_click_callable,
            style=styles.ELEVATED_BUTTON_UPDATE_STYLE,
            text=text,
            text_style=styles.UpdateButtonTextStyle,
            **kwargs,
        )


class ElevatedDeleteButton(BaseElevatedButton):
    """Button for delete/remove actions."""

    def __init__(
        self, on_click_callable: Callable, text: str = "Delete", **kwargs
    ) -> None:
        super().__init__(
            on_click_callable,
            style=styles.ELEVATED_BUTTON_DELETE_STYLE,
            text=text,
            text_style=styles.DeleteButtonTextStyle,
            **kwargs,
        )


class ElevatedCancelButton(BaseElevatedButton):
    """Button for cancel actions."""

    def __init__(
        self, on_click_callable: Callable, text: str = "Cancel", **kwargs
    ) -> None:
        super().__init__(
            on_click_callable,
            style=styles.ELEVATED_BUTTON_CANCEL_STYLE,
            text=text,
            text_style=styles.CancelButtonTextStyle,
            **kwargs,
        )


class ElevatedRefreshButton(BaseElevatedButton):
    """Button for refresh/reload actions."""

    def __init__(
        self, on_click_callable: Callable, text: str = "Refresh", **kwargs
    ) -> None:
        super().__init__(
            on_click_callable,
            style=styles.ELEVATED_BUTTON_REFRESH_STYLE,
            text=text,
            text_style=styles.RefreshButtonTextStyle,
            **kwargs,
        )


class BaseIconButton(ft.IconButton):
    """
    Base icon button with theme-aware colors and disabled states.

    Features:
    - Theme-aware icon colors
    - Proper disabled state handling
    - Tooltip support
    - Optional parameter passing to click handler
    """

    def __init__(
        self,
        on_click_callable: Callable,
        icon: str,
        icon_color: str | None = None,
        get_param_callable: Callable | None = None,
        tooltip: str | None = None,
        disabled: bool = False,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.on_click_callable = on_click_callable
        self.get_param_callable = get_param_callable
        self.icon = icon
        self.disabled_color = ft.Colors.OUTLINE  # Theme-aware disabled color

        # Use theme-aware color if none provided
        if icon_color is None:
            icon_color = ft.Colors.ON_SURFACE_VARIANT

        self.enabled_color = icon_color
        self.icon_color = self.enabled_color if not disabled else self.disabled_color
        self.default_tooltip = tooltip
        self.tooltip = tooltip if not disabled else None
        self.on_click = lambda e: self.on_click_event(e)
        self.disabled = disabled

    def on_click_event(self, e: ft.ControlEvent) -> None:
        """Handle click events with optional parameter passing."""
        if not self.disabled:
            param = self.get_param_callable() if self.get_param_callable else None
            if param:
                self.on_click_callable(param)
            else:
                self.on_click_callable()

    def update_state(self, disabled: bool) -> None:
        """Update button disabled state and visual appearance."""
        self.disabled = disabled
        self.tooltip = self.default_tooltip if not self.disabled else None
        self.icon_color = (
            self.enabled_color if not self.disabled else self.disabled_color
        )
        if self.page:
            self.update()


class IconAddButton(BaseIconButton):
    """Icon button for add actions."""

    def __init__(
        self, on_click_callable: Callable, disabled: bool = False, **kwargs
    ) -> None:
        super().__init__(
            on_click_callable,
            icon=ft.Icons.ADD_OUTLINED,
            tooltip="Add",
            disabled=disabled,
            **kwargs,
        )


class IconRefreshButton(BaseIconButton):
    """Icon button for refresh actions."""

    def __init__(
        self,
        on_click_callable: Callable,
        get_param_callable: Callable | None = None,
        disabled: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(
            on_click_callable,
            icon=ft.Icons.REFRESH_SHARP,
            get_param_callable=get_param_callable,
            tooltip="Refresh",
            disabled=disabled,
            **kwargs,
        )


class IconDeleteButton(BaseIconButton):
    """Icon button for delete actions."""

    def __init__(
        self,
        on_click_callable: Callable,
        get_param_callable: Callable | None = None,
        disabled: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(
            on_click_callable,
            icon=ft.Icons.DELETE_OUTLINED,
            get_param_callable=get_param_callable,
            tooltip="Delete",
            disabled=disabled,
            **kwargs,
        )


class ConfirmDialog(ft.AlertDialog):
    """
    Reusable confirmation dialog with consistent styling.

    Features:
    - Theme-aware styling
    - Cancel and Confirm buttons
    - Optional destructive mode (red confirm button)
    - Async callback support
    """

    def __init__(
        self,
        page: ft.Page,
        title: str,
        message: str,
        confirm_text: str = "Confirm",
        cancel_text: str = "Cancel",
        on_confirm: Callable | None = None,
        destructive: bool = False,
    ) -> None:
        """
        Initialize confirmation dialog.

        Args:
            page: Flet page instance
            title: Dialog title
            message: Dialog message/content
            confirm_text: Text for confirm button
            cancel_text: Text for cancel button
            on_confirm: Callback when confirmed (can be sync or async)
            destructive: If True, confirm button is styled as destructive (red)
        """
        self._page = page
        self._on_confirm = on_confirm

        # Confirm button style
        confirm_style = None
        if destructive:
            confirm_style = ft.ButtonStyle(
                bgcolor=ft.Colors.ERROR,
                color=ft.Colors.ON_ERROR,
            )

        super().__init__(
            modal=True,
            title=H3Text(title),
            content=BodyText(message),
            actions=[
                ft.TextButton(cancel_text, on_click=self._close),
                ft.FilledButton(
                    confirm_text,
                    on_click=self._confirm,
                    style=confirm_style,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        )

    def _close(self, e: ft.ControlEvent) -> None:
        """Close the dialog."""
        self.open = False
        self._page.update()

    def _confirm(self, e: ft.ControlEvent) -> None:
        """Handle confirm action."""
        self.open = False
        self._page.update()
        if self._on_confirm:
            import asyncio
            import inspect

            if inspect.iscoroutinefunction(self._on_confirm):
                self._page.run_task(self._on_confirm)
            else:
                result = self._on_confirm()
                if asyncio.iscoroutine(result):
                    self._page.run_task(lambda: result)

    def show(self) -> None:
        """Show the dialog."""
        self._page.open(self)
