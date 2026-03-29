"""
Reusable Modal Section Components

Provides commonly used section patterns across component detail modals:
- MetricCardSection: Display key metrics in card grid
- StatRowsSection: Label/value pairs for detailed information
- EmptyStatePlaceholder: Consistent "no data" messaging
- PieChartCard: Donut chart with legend
- FlowConnector: Vertical arrow between flow sections
- LifecycleInspector: Right-side inspector panel for lifecycle details
- LifecycleCard: Clickable card for lifecycle items
- FlowSection: Labeled section in a lifecycle flow diagram
"""

import contextlib
from typing import Any

import flet as ft
from app.components.frontend.controls import (
    BodyText,
    H3Text,
    LabelText,
    PrimaryText,
    SecondaryText,
    Tag,
)
from app.components.frontend.theme import AegisTheme as Theme
from app.components.frontend.theme import DarkColorPalette


class InfoCard(ft.Container):
    """Info card displaying a label and value with consistent card styling."""

    def __init__(
        self,
        label: str,
        value: str = "",
        tags: list[tuple[str, str]] | None = None,
    ) -> None:
        """
        Initialize info card.

        Args:
            label: Card label text (shown at top)
            value: Value to display (used if no tags provided)
            tags: Optional list of (text, color) tuples to show as tags
        """
        super().__init__()

        content_items: list[ft.Control] = [
            LabelText(label),
            ft.Container(height=Theme.Spacing.XS),
        ]

        if tags:
            # Show tags (e.g., provider badges)
            tag_controls = [Tag(text=t, color=c) for t, c in tags]
            content_items.append(
                ft.Row(
                    tag_controls,
                    spacing=4,
                    wrap=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                )
            )
        else:
            # Show value as body text
            content_items.append(BodyText(value))

        self.content = ft.Column(
            content_items,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
        )
        self.padding = Theme.Spacing.MD
        self.bgcolor = ft.Colors.SURFACE_CONTAINER_HIGHEST
        self.border_radius = Theme.Components.CARD_RADIUS
        self.border = ft.border.all(0.5, ft.Colors.OUTLINE)
        self.expand = True


class MetricCard(ft.Container):
    """Reusable metric display card with icon, label, and colored value."""

    def __init__(
        self,
        label: str,
        value: str,
        color: str,
        icon: str | None = None,
    ) -> None:
        """
        Initialize metric card.

        Args:
            label: Metric label text
            value: Metric value to display
            color: Color for the value text
            icon: Optional icon name (e.g., ft.Icons.TOKEN)
        """
        super().__init__()

        # Header row with icon and label
        header_items: list[ft.Control] = []
        if icon:
            header_items.append(ft.Icon(icon, size=16, color=color))
        header_items.append(SecondaryText(label))

        header_row = ft.Row(
            header_items,
            spacing=6,
        )

        # Value text — stored as instance attribute for live updates
        self.value_text = ft.Text(
            value,
            size=24,
            weight=ft.FontWeight.W_600,
        )

        self.content = ft.Column(
            [header_row, self.value_text],
            spacing=Theme.Spacing.XS,
        )
        self.padding = Theme.Spacing.MD
        self.bgcolor = ft.Colors.SURFACE_CONTAINER_HIGHEST
        self.border_radius = Theme.Components.CARD_RADIUS
        self.border = ft.border.all(0.5, ft.Colors.OUTLINE)
        self.expand = True

    def set_value(self, value: str, color: str | None = None) -> None:
        """Update the displayed value (and optionally its color) in place."""
        self.value_text.value = value
        if color is not None:
            self.value_text.color = color


class SectionHeader(ft.Row):
    """Section header with icon and title."""

    def __init__(
        self,
        title: str,
        icon: str | None = None,
        color: str | None = None,
    ) -> None:
        """
        Initialize section header.

        Args:
            title: Section title text
            icon: Optional icon name
            color: Optional icon color (defaults to secondary text color)
        """
        items: list[ft.Control] = []
        if icon:
            items.append(
                ft.Icon(icon, size=18, color=color or ft.Colors.ON_SURFACE_VARIANT)
            )
        items.append(H3Text(title))

        super().__init__(items, spacing=8)


class MetricCardSection(ft.Container):
    """
    Reusable section for displaying metric cards in a grid.

    Creates a titled section with metric cards displayed in a horizontal row.
    Each metric is rendered using the MetricCard component.
    """

    def __init__(self, title: str, metrics: list[dict[str, str]]) -> None:
        """
        Initialize metric card section.

        Args:
            title: Section title
            metrics: List of metric dicts with keys: label, value, color
                     Example: [{"label": "Total", "value": "42", "color": "#00ff00"}]
        """
        super().__init__()

        cards = []
        for metric in metrics:
            cards.append(
                MetricCard(
                    label=metric["label"],
                    value=metric["value"],
                    color=metric["color"],
                )
            )

        self.content = ft.Column(
            [
                H3Text(title),
                ft.Container(height=Theme.Spacing.SM),
                ft.Row(cards, spacing=Theme.Spacing.MD),
            ],
            spacing=0,
        )
        self.padding = Theme.Spacing.MD


class StatRowsSection(ft.Container):
    """
    Reusable section for displaying label/value pairs.

    Creates a titled section with statistics displayed as label: value rows.
    Common pattern for detailed component information.
    """

    def __init__(
        self,
        title: str,
        stats: dict[str, str],
        label_width: int = 150,
    ) -> None:
        """
        Initialize stat rows section.

        Args:
            title: Section title
            stats: Dictionary of label: value pairs
            label_width: Width for label column (default: 150px)
        """
        super().__init__()

        rows = []
        for label, value in stats.items():
            rows.append(
                ft.Row(
                    [
                        SecondaryText(
                            f"{label}:",
                            weight=Theme.Typography.WEIGHT_SEMIBOLD,
                            width=label_width,
                        ),
                        BodyText(value),
                    ],
                    spacing=Theme.Spacing.MD,
                )
            )

        self.content = ft.Column(
            [
                H3Text(title),
                ft.Container(height=Theme.Spacing.SM),
                ft.Column(rows, spacing=Theme.Spacing.SM),
            ],
            spacing=0,
        )
        self.padding = Theme.Spacing.MD


class EmptyStatePlaceholder(ft.Container):
    """
    Reusable placeholder for empty states.

    Displays a consistent message when no data is available,
    using theme colors and spacing.
    """

    def __init__(
        self,
        message: str,
    ) -> None:
        """
        Initialize empty state placeholder.

        Args:
            message: Message to display
        """
        super().__init__()

        self.content = ft.Row(
            [
                SecondaryText(
                    message,
                    size=Theme.Typography.BODY_LARGE,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=Theme.Spacing.MD,
        )
        self.padding = Theme.Spacing.XL
        self.bgcolor = (
            ft.Colors.SURFACE_CONTAINER_HIGHEST
        )  # Elevated surface for contrast
        self.border_radius = Theme.Components.CARD_RADIUS
        self.border = ft.border.all(1, ft.Colors.OUTLINE)


# Color palette for pie chart segments (distinct, visually appealing colors)
PIE_CHART_COLORS = [
    DarkColorPalette.ACCENT,  # Teal
    "#22C55E",  # Green
    "#F5A623",  # Orange/Amber
    "#A855F7",  # Purple
    "#3B82F6",  # Blue
    "#EC4899",  # Pink
    "#6366F1",  # Indigo
    "#14B8A6",  # Cyan
]


class PieChartCard(ft.Container):
    """
    Reusable pie chart card with title, donut chart, and legend.

    Provides consistent styling matching the React reference design.
    Features interactive hover effects with segment expansion and tooltips.
    """

    # Segment radius constants (must fit within chart container)
    NORMAL_RADIUS = 45
    HOVER_RADIUS = 52

    def __init__(
        self,
        title: str,
        sections: list[dict[str, Any]],
    ) -> None:
        """
        Initialize pie chart card.

        Args:
            title: Card title
            sections: List of dicts with keys: value, label (color is auto-assigned)
                      Example: [{"value": 100, "label": "Input (50%)"}]
        """
        super().__init__()

        self._section_labels: list[str] = []
        self._section_values: list[float] = []
        self._hovered_index: int | None = None

        if not sections:
            self.content = ft.Column(
                [
                    SecondaryText(title),
                    ft.Container(
                        content=SecondaryText("No data", size=13),
                        expand=True,
                        alignment=ft.alignment.center,
                    ),
                ],
                spacing=0,
                expand=True,
            )
            self._setup_card_style()
            return

        # Build pie chart sections with auto-assigned colors
        self._pie_sections: list[ft.PieChartSection] = []
        legend_items: list[ft.Row] = []

        for i, section in enumerate(sections):
            value = float(section.get("value", 0))
            # Use provided color or auto-assign from palette
            color = section.get("color") or PIE_CHART_COLORS[i % len(PIE_CHART_COLORS)]
            label = str(section.get("label", ""))

            # Store for tooltips
            self._section_labels.append(label)
            self._section_values.append(value)

            self._pie_sections.append(
                ft.PieChartSection(
                    value=value,
                    title="",
                    color=color,
                    radius=self.NORMAL_RADIUS,
                )
            )
            legend_items.append(self._legend_item(label, color))

        # Donut chart with hover interaction
        self._pie_chart = ft.PieChart(
            sections=self._pie_sections,
            sections_space=2,
            center_space_radius=28,
            on_chart_event=self._on_chart_event,
        )

        # Legend column
        legend = ft.Column(
            legend_items,
            spacing=Theme.Spacing.XS,
            alignment=ft.MainAxisAlignment.CENTER,
        )

        # Layout: chart + legend horizontal, centered
        chart_row = ft.Row(
            [
                ft.Container(
                    content=self._pie_chart,
                    width=130,
                    height=130,
                ),
                legend,
            ],
            spacing=Theme.Spacing.LG,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Column layout with chart pushed down to avoid overlap
        self.content = ft.Column(
            [
                SecondaryText(title),
                ft.Container(
                    content=chart_row,
                    expand=True,
                    alignment=ft.alignment.center,
                    margin=ft.margin.only(top=Theme.Spacing.MD),
                ),
            ],
            spacing=0,
            expand=True,
        )
        self._setup_card_style()

    def _setup_card_style(self) -> None:
        """Apply consistent card styling."""
        self.bgcolor = ft.Colors.SURFACE_CONTAINER_HIGHEST
        self.border = ft.border.all(0.5, ft.Colors.OUTLINE)
        self.border_radius = Theme.Components.CARD_RADIUS
        self.padding = ft.padding.only(
            left=Theme.Spacing.MD,
            right=Theme.Spacing.MD,
            top=Theme.Spacing.SM,
            bottom=Theme.Spacing.SM,
        )
        self.height = 210
        self.expand = True
        self.clip_behavior = ft.ClipBehavior.HARD_EDGE

    def _on_chart_event(self, e: ft.PieChartEvent) -> None:
        """Handle hover events - expand hovered segment."""
        # Reset all sections to normal radius
        for section in self._pie_sections:
            section.radius = self.NORMAL_RADIUS

        # Check if hovering over a section (section_index is -1 when not hovering)
        idx = e.section_index
        if idx is not None and idx >= 0 and idx < len(self._pie_sections):
            self._pie_sections[idx].radius = self.HOVER_RADIUS
            self._hovered_index = idx
        else:
            self._hovered_index = None

        self._pie_chart.update()

    def _legend_item(self, label: str, color: str) -> ft.Row:
        """Create a legend item with color dot and label."""
        return ft.Row(
            [
                ft.Container(width=10, height=10, bgcolor=color, border_radius=5),
                SecondaryText(label, size=Theme.Typography.BODY_SMALL),
            ],
            spacing=8,
        )


class FlowConnector(ft.Container):
    """Vertical connector with arrow between flow sections."""

    def __init__(self) -> None:
        """Initialize flow connector."""
        super().__init__()
        self.content = ft.Column(
            [
                # Vertical line (thicker)
                ft.Container(
                    width=3,
                    height=30,
                    bgcolor=Theme.Colors.BORDER_DEFAULT,
                    border_radius=2,
                ),
                # Arrow icon
                ft.Icon(
                    ft.Icons.ARROW_DROP_DOWN,
                    size=20,
                    color=Theme.Colors.BORDER_DEFAULT,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
        )
        self.padding = ft.padding.symmetric(vertical=Theme.Spacing.XS)


class LifecycleInspector(ft.Container):
    """Right-side inspector panel showing selected card details."""

    def __init__(self) -> None:
        """Initialize lifecycle inspector panel."""
        super().__init__()
        self._selected_card: LifecycleCard | None = None
        self._name_text = PrimaryText("")
        self._subtitle_text = SecondaryText("")
        self._badge_container = ft.Container(visible=False)
        self._details_column: ft.Column = ft.Column([], spacing=8)
        self._showing_empty_state = True

        # Main column that will swap between empty state and content
        self._main_column = ft.Column(
            [
                ft.Icon(
                    ft.Icons.TOUCH_APP, size=48, color=ft.Colors.ON_SURFACE_VARIANT
                ),
                SecondaryText("Select a lifecycle hook"),
                SecondaryText("to inspect configuration", size=12),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        self.content = self._main_column
        self.bgcolor = ft.Colors.SURFACE_CONTAINER_HIGHEST
        self.border_radius = Theme.Components.CARD_RADIUS
        self.border = ft.border.all(1, ft.Colors.OUTLINE)
        self.padding = ft.padding.all(Theme.Spacing.MD)
        self.width = 300

    def clear_selection(self) -> None:
        """Reset inspector to empty state (e.g., on queue switch)."""
        if self._selected_card:
            with contextlib.suppress(Exception):
                self._selected_card.set_selected(False)
            self._selected_card = None

    def select_card(self, card: "LifecycleCard") -> None:
        """Select a card and update inspector."""
        # Deselect previous (guard against unmounted cards)
        if self._selected_card:
            with contextlib.suppress(Exception):
                self._selected_card.set_selected(False)
        # Select new
        self._selected_card = card
        card.set_selected(True)
        # Show details
        self.show_details(
            card.name,
            card.subtitle,
            card._details,
            card._badge_text,
            card._badge_color,
            card.section,
        )

    def _create_code_block(self, text: str, copyable: bool = False) -> ft.Container:
        """Create styled code block for values."""
        content_items: list[ft.Control] = [
            ft.Text(
                text,
                font_family="monospace",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
                selectable=True,
                expand=True,
            ),
        ]
        if copyable:
            content_items.append(
                ft.IconButton(
                    icon=ft.Icons.COPY,
                    icon_size=14,
                    tooltip="Copy",
                    on_click=lambda e: self._copy_to_clipboard(text),
                ),
            )
        return ft.Container(
            content=ft.Row(content_items, spacing=4),
            bgcolor=ft.Colors.SURFACE,
            border_radius=6,
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
        )

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to clipboard with feedback."""
        if self.page:
            self.page.set_clipboard(text)
            self.page.open(ft.SnackBar(content=ft.Text("Copied to clipboard")))

    def show_details(
        self,
        name: str,
        subtitle: str,
        details: dict[str, object],
        badge_text: str | None = None,
        badge_color: str | None = None,
        section: str = "",
    ) -> None:
        """
        Update inspector with card data.

        Args:
            name: Card name to display
            subtitle: Card subtitle to display
            details: Dict of key-value pairs to show
            badge_text: Optional badge text (e.g., "Security")
            badge_color: Badge background color
            section: Section name for context header
        """
        self._name_text.value = name
        self._subtitle_text.value = subtitle

        # Update badge
        if badge_text:
            self._badge_container.content = LabelText(
                badge_text, color=Theme.Colors.BADGE_TEXT
            )
            self._badge_container.padding = ft.padding.symmetric(
                horizontal=6, vertical=2
            )
            self._badge_container.bgcolor = badge_color or ft.Colors.AMBER
            self._badge_container.border_radius = 4
            self._badge_container.visible = True
        else:
            self._badge_container.visible = False

        # Build details (skip Module - already shown as subtitle)
        detail_rows: list[ft.Control] = []
        for key, value in details.items():
            if key == "Module":
                continue

            detail_rows.append(SecondaryText(f"{key}:"))

            # Handle lists - join items with newlines in one block
            if isinstance(value, list):
                list_text = ",\n".join(str(item) for item in value)
                detail_rows.append(self._create_code_block(list_text))
            else:
                detail_rows.append(self._create_code_block(str(value)))

        self._details_column.controls = detail_rows

        # Build content with optional section header
        content_controls: list[ft.Control] = []

        # Section context header (e.g., "Startup Hooks")
        if section:
            content_controls.append(SecondaryText(section))

        # Card name + badge
        content_controls.append(
            ft.Row(
                [self._name_text, self._badge_container],
                spacing=Theme.Spacing.SM,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        content_controls.append(self._subtitle_text)
        content_controls.append(ft.Divider())
        content_controls.append(self._details_column)

        # Swap to content view
        self._main_column.controls = content_controls
        self._main_column.horizontal_alignment = ft.CrossAxisAlignment.START
        self._main_column.spacing = Theme.Spacing.SM
        self._showing_empty_state = False
        self.update()


class LifecycleCard(ft.Container):
    """Clickable card for lifecycle items (hooks or middleware)."""

    def __init__(
        self,
        name: str,
        subtitle: str,
        section: str = "",
        details: dict[str, object] | None = None,
        badge: str | None = None,
        badge_color: str | None = None,
        inspector: LifecycleInspector | None = None,
    ) -> None:
        """
        Initialize lifecycle card.

        Args:
            name: Function/class name (e.g., database_init, CORSMiddleware)
            subtitle: Module path for inspector
            section: Section name (e.g., "Startup Hooks") for inspector context
            details: Optional dict of key-value pairs for inspector view
            badge: Optional badge text (e.g., "Security")
            badge_color: Badge background color
            inspector: Shared inspector panel to update on click
        """
        super().__init__()
        # Auto-format: snake_case -> Title Case, preserve CamelCase
        if "_" in name:
            display_name = name.replace("_", " ").title()
        elif name.islower():
            display_name = name.capitalize()
        else:
            display_name = name  # Preserve CamelCase
        self.name = display_name
        self.subtitle = subtitle
        self.section = section
        self._raw_name = name  # Keep original for code reference
        self._details = details or {}
        self._badge_text = badge
        self._badge_color = badge_color or ft.Colors.AMBER
        self._inspector = inspector
        self._is_selected = False

        # Build card header: Title + Badge on top, code name below
        header_row_content: list[ft.Control] = [PrimaryText(display_name)]

        # Add badge if provided
        if self._badge_text:
            header_row_content.append(
                ft.Container(
                    content=LabelText(self._badge_text, color=Theme.Colors.BADGE_TEXT),
                    padding=ft.padding.symmetric(horizontal=6, vertical=2),
                    bgcolor=self._badge_color,
                    border_radius=4,
                    margin=ft.margin.only(left=Theme.Spacing.SM),
                )
            )

        self.card_header = ft.Container(
            content=ft.Row(
                header_row_content,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.all(Theme.Spacing.SM),
            on_hover=self._on_hover,
        )

        # Wrap header in gesture detector
        self.header_gesture = ft.GestureDetector(
            content=self.card_header,
            on_tap=self._handle_click,
            mouse_cursor=ft.MouseCursor.CLICK,
        )

        self.content = self.header_gesture
        self.bgcolor = ft.Colors.SURFACE_CONTAINER_HIGHEST
        self.border_radius = Theme.Components.CARD_RADIUS
        self.border = ft.border.all(1, ft.Colors.OUTLINE)

    def _on_hover(self, e: ft.ControlEvent) -> None:
        """Handle hover state change."""
        if self._is_selected:
            return  # Don't change hover state when selected
        if e.data == "true":
            self.card_header.bgcolor = ft.Colors.with_opacity(
                0.08, ft.Colors.ON_SURFACE
            )
        else:
            self.card_header.bgcolor = None
        if e.control.page:
            self.card_header.update()

    def _handle_click(self, e: ft.ControlEvent) -> None:
        """Handle card click to update inspector."""
        _ = e
        if self._inspector:
            self._inspector.select_card(self)

    def set_selected(self, selected: bool) -> None:
        """Update visual state for selection."""
        self._is_selected = selected
        if selected:
            self.border = ft.border.all(2, Theme.Colors.ACCENT)
            self.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)
        else:
            self.border = ft.border.all(1, ft.Colors.OUTLINE)
            self.bgcolor = ft.Colors.SURFACE_CONTAINER_HIGHEST
        self.update()


class FlowSection(ft.Container):
    """A section in the lifecycle flow with label and cards."""

    def __init__(
        self, title: str, cards: list[LifecycleCard], icon: str, step_number: int
    ) -> None:
        """
        Initialize flow section.

        Args:
            title: Section title
            cards: List of LifecycleCard components
            icon: Icon name for the section header
            step_number: Execution order number (1, 2, 3...)
        """
        super().__init__()
        self.title = title
        self.cards_list = cards

        # Section header with step number and icon
        section_header = ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=SecondaryText(f"{step_number:02d}", size=10),
                        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                        border_radius=4,
                        padding=ft.padding.symmetric(horizontal=6, vertical=2),
                    ),
                    ft.Icon(icon, size=18, color=Theme.Colors.TEXT_SECONDARY),
                    H3Text(title),
                    ft.Container(
                        content=SecondaryText(f"({len(cards)})"),
                        padding=ft.padding.only(left=Theme.Spacing.XS),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=Theme.Spacing.SM,
            ),
            padding=ft.padding.only(bottom=Theme.Spacing.SM),
        )

        # Cards row (wraps if many items)
        if cards:
            cards_row = ft.Row(
                cards,
                wrap=True,
                spacing=Theme.Spacing.MD,
                run_spacing=Theme.Spacing.MD,
                alignment=ft.MainAxisAlignment.CENTER,
            )
        else:
            cards_row = ft.Container(
                content=SecondaryText("None configured"),
                padding=ft.padding.all(Theme.Spacing.MD),
                alignment=ft.alignment.center,
            )

        self.content = ft.Column(
            [section_header, cards_row],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
        )
        self.padding = ft.padding.symmetric(vertical=Theme.Spacing.SM)
