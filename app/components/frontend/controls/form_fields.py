"""
Reusable form field components for Aegis Stack dashboard.

Provides theme-aware form inputs with consistent styling for labels,
text fields, secret fields (with visibility toggle), and action buttons.
"""

from collections.abc import Callable
from typing import Any

import flet as ft
from app.components.frontend.controls.buttons import (
    ElevatedCancelButton,
    ElevatedUpdateButton,
)
from app.components.frontend.controls.text import LabelText
from app.components.frontend.theme import AegisTheme as Theme


class FormTextField(ft.Container):
    """
    Reusable text input with label and error state.

    Features:
    - Theme-aware styling with consistent border radius and colors
    - Label using existing LabelText component
    - Error text display below field (red) when error provided
    - Optional hint text for placeholder guidance
    """

    def __init__(
        self,
        label: str,
        value: str = "",
        hint: str = "",
        on_change: Callable[[ft.ControlEvent], None] | None = None,
        error: str | None = None,
        disabled: bool = False,
        width: int | None = None,
    ) -> None:
        """
        Initialize form text field.

        Args:
            label: Label text displayed above the field
            value: Initial value for the field
            hint: Placeholder/hint text when field is empty
            on_change: Callback when field value changes
            error: Error message to display below field (None = no error)
            disabled: Whether the field is disabled
            width: Optional fixed width for the field
        """
        super().__init__()

        self._label = label
        self._error = error
        self._on_change = on_change

        # Create the text field
        self._text_field = ft.TextField(
            value=value,
            hint_text=hint,
            on_change=self._handle_change,
            disabled=disabled,
            border_radius=Theme.Components.INPUT_RADIUS,
            bgcolor=ft.Colors.SURFACE,
            border_color=Theme.Colors.ERROR if error else ft.Colors.OUTLINE,
            focused_border_color=Theme.Colors.PRIMARY,
            text_size=13,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            expand=width is None,
            width=width,
        )

        # Build content
        self._build_content()

    def _build_content(self) -> None:
        """Build the form field content with label and optional error."""
        children: list[ft.Control] = [
            LabelText(self._label),
            ft.Container(height=4),
            self._text_field,
        ]

        # Add error text if present
        if self._error:
            children.append(ft.Container(height=4))
            children.append(
                ft.Text(
                    self._error,
                    size=Theme.Typography.BODY_SMALL,
                    color=Theme.Colors.ERROR,
                )
            )

        self.content = ft.Column(
            children,
            spacing=0,
            tight=True,
        )

    def _handle_change(self, e: ft.ControlEvent) -> None:
        """Handle text field change events."""
        if self._on_change:
            self._on_change(e)

    @property
    def value(self) -> str:
        """Get the current field value."""
        return self._text_field.value or ""

    @value.setter
    def value(self, new_value: str) -> None:
        """Set the field value."""
        self._text_field.value = new_value
        if self.page:
            self._text_field.update()

    def set_error(self, error: str | None) -> None:
        """Set or clear the error message."""
        self._error = error
        # Update border color based on error state
        self._text_field.border_color = (
            Theme.Colors.ERROR if error else ft.Colors.OUTLINE
        )
        self._build_content()
        if self.page:
            self.update()

    def focus(self) -> None:
        """Focus the text field."""
        self._text_field.focus()


class FormSecretField(ft.Container):
    """
    Text input for secrets with show/hide toggle.

    Features:
    - Password field with visibility toggle (eye icon)
    - Theme-aware styling consistent with FormTextField
    - Never shows full value in view mode (always masked)
    - Label and error state support
    """

    def __init__(
        self,
        label: str,
        value: str = "",
        hint: str = "Enter value...",
        on_change: Callable[[ft.ControlEvent], None] | None = None,
        error: str | None = None,
        disabled: bool = False,
        width: int | None = None,
    ) -> None:
        """
        Initialize form secret field.

        Args:
            label: Label text displayed above the field
            value: Initial value for the field
            hint: Placeholder/hint text when field is empty
            on_change: Callback when field value changes
            error: Error message to display below field (None = no error)
            disabled: Whether the field is disabled
            width: Optional fixed width for the field
        """
        super().__init__()

        self._label = label
        self._error = error
        self._on_change = on_change
        self._password_visible = False

        # Create the text field
        self._text_field = ft.TextField(
            value=value,
            hint_text=hint,
            password=True,
            can_reveal_password=False,  # We use our own toggle
            on_change=self._handle_change,
            disabled=disabled,
            border_radius=Theme.Components.INPUT_RADIUS,
            bgcolor=ft.Colors.SURFACE,
            border_color=Theme.Colors.ERROR if error else ft.Colors.OUTLINE,
            focused_border_color=Theme.Colors.PRIMARY,
            text_size=13,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            expand=True,
        )

        # Create visibility toggle button
        self._toggle_button = ft.IconButton(
            icon=ft.Icons.VISIBILITY_OFF,
            icon_color=Theme.Colors.TEXT_SECONDARY,
            icon_size=18,
            tooltip="Show/hide value",
            on_click=self._toggle_visibility,
            disabled=disabled,
        )

        # Build content
        self._build_content(width)

    def _build_content(self, width: int | None = None) -> None:
        """Build the form field content with label, field, toggle, and error."""
        # Field with toggle button
        field_row = ft.Row(
            [
                self._text_field,
                self._toggle_button,
            ],
            spacing=4,
            expand=width is None,
            width=width,
        )

        children: list[ft.Control] = [
            LabelText(self._label),
            ft.Container(height=4),
            field_row,
        ]

        # Add error text if present
        if self._error:
            children.append(ft.Container(height=4))
            children.append(
                ft.Text(
                    self._error,
                    size=Theme.Typography.BODY_SMALL,
                    color=Theme.Colors.ERROR,
                )
            )

        self.content = ft.Column(
            children,
            spacing=0,
            tight=True,
        )

    def _handle_change(self, e: ft.ControlEvent) -> None:
        """Handle text field change events."""
        if self._on_change:
            self._on_change(e)

    def _toggle_visibility(self, e: ft.ControlEvent) -> None:
        """Toggle password visibility."""
        self._password_visible = not self._password_visible
        self._text_field.password = not self._password_visible
        self._toggle_button.icon = (
            ft.Icons.VISIBILITY if self._password_visible else ft.Icons.VISIBILITY_OFF
        )
        if self.page:
            self._text_field.update()
            self._toggle_button.update()

    @property
    def value(self) -> str:
        """Get the current field value."""
        return self._text_field.value or ""

    @value.setter
    def value(self, new_value: str) -> None:
        """Set the field value."""
        self._text_field.value = new_value
        if self.page:
            self._text_field.update()

    def set_error(self, error: str | None) -> None:
        """Set or clear the error message."""
        self._error = error
        # Update border color based on error state
        self._text_field.border_color = (
            Theme.Colors.ERROR if error else ft.Colors.OUTLINE
        )
        self._build_content()
        if self.page:
            self.update()

    def focus(self) -> None:
        """Focus the text field."""
        self._text_field.focus()


class FormActionButtons(ft.Row):
    """
    Save/Cancel button pair for forms.

    Features:
    - Uses existing ElevatedUpdateButton and ElevatedCancelButton
    - Shows loading state when saving=True
    - Consistent right-aligned layout
    """

    def __init__(
        self,
        on_save: Callable[[], Any],
        on_cancel: Callable[[], Any],
        save_text: str = "Save",
        cancel_text: str = "Cancel",
        saving: bool = False,
    ) -> None:
        """
        Initialize form action buttons.

        Args:
            on_save: Callback when save button is clicked
            on_cancel: Callback when cancel button is clicked
            save_text: Text for the save button
            cancel_text: Text for the cancel button
            saving: Whether save operation is in progress (shows loading)
        """
        self._on_save = on_save
        self._on_cancel = on_cancel
        self._save_text = save_text
        self._saving = saving

        # Create buttons
        self._cancel_button = ElevatedCancelButton(
            on_click_callable=on_cancel,
            text=cancel_text,
        )

        self._save_button = ElevatedUpdateButton(
            on_click_callable=self._handle_save,
            text=save_text if not saving else "Saving...",
        )
        self._save_button.disabled = saving

        super().__init__(
            controls=[
                self._cancel_button,
                self._save_button,
            ],
            spacing=Theme.Spacing.SM,
            alignment=ft.MainAxisAlignment.END,
        )

    def _handle_save(self) -> None:
        """Handle save button click."""
        self._on_save()

    def set_saving(self, saving: bool) -> None:
        """Update the saving state."""
        self._saving = saving
        self._save_button.disabled = saving
        self._save_button.text = self._save_text if not saving else "Saving..."
        if self.page:
            self._save_button.update()
