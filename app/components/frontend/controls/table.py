"""
Table-specific text controls for consistent styling across cards.

These controls provide standardized text styling for table headers, cells, and
entity names to ensure consistency between worker, database, and other component cards.
"""

from typing import Any

import flet as ft

from ..theme import AegisTheme as Theme


class TableHeaderText(ft.Text):  # type: ignore[misc]
    """
    Table header text control with consistent styling.

    Used for column headers in component cards. Provides medium weight text
    with reduced opacity for visual hierarchy.
    """

    def __init__(self, text: str, **kwargs: Any) -> None:
        # Set defaults that can be overridden
        defaults = {
            "weight": ft.FontWeight.W_500,
            "size": Theme.Typography.BODY_SMALL,
            "color": ft.Colors.GREY_600,
        }
        defaults.update(kwargs)

        super().__init__(
            text,
            **defaults,
        )


class TableCellText(ft.Text):  # type: ignore[misc]
    """
    Table cell text control for data values.

    Used for displaying data values in table cells. Provides consistent
    sizing and coloring for tabular data.
    """

    def __init__(self, text: str, **kwargs: Any) -> None:
        # Set defaults that can be overridden
        defaults = {
            "size": Theme.Typography.BODY,
            "color": ft.Colors.ON_SURFACE,
        }
        defaults.update(kwargs)

        super().__init__(
            text,
            **defaults,
        )


class TableNameText(ft.Text):  # type: ignore[misc]
    """
    Table entity name text control.

    Used for displaying entity names (queues, tables, etc.) in table rows.
    Provides consistent styling for entity identifiers.
    """

    def __init__(self, text: str, **kwargs: Any) -> None:
        # Set defaults that can be overridden
        defaults = {
            "weight": ft.FontWeight.W_400,
            "size": Theme.Typography.BODY,
            "color": ft.Colors.ON_SURFACE,
        }
        defaults.update(kwargs)

        super().__init__(
            text,
            **defaults,
        )
