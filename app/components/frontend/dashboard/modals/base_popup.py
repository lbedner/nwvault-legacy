"""
Base Popup Component using Container + Stack Pattern

Provides a reusable popup/modal system with full control over borders,
overlays, and styling. Unlike AlertDialog, this Container-based approach
allows complete customization of visual properties.

Pattern inspired by ee-toolset's mobile sidebar overlay implementation.
"""

import flet as ft


class BasePopup(ft.Container):
    """
    Container-based popup with overlay and customizable styling.

    Uses ft.Stack to layer a semi-transparent backdrop over content,
    with the popup panel centered on top. Provides full control over
    borders, shadows, and dimensions.

    Features:
    - Semi-transparent backdrop overlay
    - Click-to-close on backdrop
    - Programmatic show()/hide() control
    - Customizable borders and shadows
    - Full Container property access

    Usage:
        popup = BasePopup(
            page=page,
            content=my_content,
            width=900,
            height=700,
            border=ft.border.all(2, ft.Colors.PRIMARY),
        )

        # Add to page's overlay
        page.overlay.append(popup)

        # Show/hide programmatically
        popup.show()
        popup.hide()
    """

    def __init__(
        self,
        page: ft.Page,
        content: ft.Control,
        width: int | None = None,
        height: int | None = None,
        border: ft.Border | None = None,
        border_radius: int | None = None,
        bgcolor: str | None = None,
        shadow: ft.BoxShadow | None = None,
        padding: int | ft.Padding | None = None,
    ) -> None:
        """
        Initialize the base popup.

        Args:
            content: The content to display in the popup
            width: Popup width in pixels
            height: Popup height in pixels
            border: Border configuration (e.g., ft.border.all(1, ft.Colors.PRIMARY))
            border_radius: Border radius for rounded corners
            bgcolor: Background color
            shadow: BoxShadow for elevation effect
            padding: Padding around content
        """
        super().__init__()
        self.page = page

        # Semi-transparent backdrop overlay
        self.overlay = ft.Container(
            content=None,  # Just background
            bgcolor=ft.Colors.with_opacity(0.5, ft.Colors.BLACK),
            visible=False,
            expand=True,
            on_click=self._handle_backdrop_click,
        )

        # Actual popup panel with customizable styling
        # Click handler stops propagation so clicks inside don't close popup
        self.panel = ft.Container(
            content=content,
            visible=False,
            width=width,
            height=height,
            bgcolor=bgcolor or ft.Colors.SURFACE,
            border=border,
            border_radius=border_radius,
            shadow=shadow,
            padding=padding,
            on_click=lambda e: None,  # Stop click propagation from panel content
        )

        # Stack layout for overlay + panel
        # Wrap panel in another container to enable centering
        # The wrapping container needs the click handler since it's on top
        self.content = ft.Stack(
            controls=[
                self.overlay,  # Background overlay (not needed for clicks anymore)
                ft.Container(
                    content=self.panel,
                    alignment=ft.alignment.center,  # Center the popup
                    expand=True,
                    on_click=self._handle_backdrop_click,  # Handle clicks outside panel
                ),
            ],
            expand=True,
        )

        # Initialize as invisible
        self.visible = False
        self.expand = True

    def show(self) -> None:
        """
        Show the popup with overlay.

        Note: Caller must call page.update() after this method.
        """
        self.visible = True
        self.overlay.visible = True
        self.panel.visible = True

    def hide(self) -> None:
        """
        Hide the popup and overlay.

        Note: Caller must call page.update() after this method.
        """
        self.visible = False
        self.overlay.visible = False
        self.panel.visible = False

    def _handle_backdrop_click(self, e: ft.ControlEvent) -> None:
        """Close popup when backdrop is clicked (not the panel itself)."""
        # Only close if the click was on the backdrop container, not the panel
        # The event control should be the wrapping Container, not the panel
        if e.control == self.panel:
            # Click was on the panel, don't close
            return

        self.hide()
        if e.page:
            e.page.update()
