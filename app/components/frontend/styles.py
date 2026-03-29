"""
Core styling system for Aegis Stack dashboard.

Centralized design system inspired by modern dev tools (ee-toolset, Supabase, Vercel).
Based on dataclass architecture for type-safe, maintainable styling.
"""

from dataclasses import asdict, dataclass

import flet as ft


@dataclass(frozen=True)
class ColorPalette:
    """
    Dark mode color palette for modern, sleek UI.

    Pure black base with vibrant accents for professional appearance.
    """

    BG_PRIMARY: str = "#000000"  # Pure black base
    BG_SECONDARY: str = "#1A1A1A"  # Slightly elevated surfaces
    BG_SELECTED: str = "#2E2E2E"  # Selected/active states
    BG_HOVER: str = "#2A2A2A"  # Hover states
    TEXT_PRIMARY_DEFAULT: str = "#E5E5E5"  # Main content text
    TEXT_SECONDARY_DEFAULT: str = "#B0B0B0"  # Supporting text
    ACCENT: str = "#1A73E8"  # Primary action color (blue)
    ACCENT_SUCCESS: str = "#52D869"  # Success states (green)
    ACCENT_STOP: str = "#E94E77"  # Destructive actions (red)
    ERROR: str = "#FF6B6B"  # Error states
    BORDER_PRIMARY: str = "#444444"  # Default borders
    DISABLED_COLOR: str = "#7F7F7F"  # Disabled states
    FOCUS_COLOR: str = "#FF6347"  # Focus indicators


@dataclass(frozen=True)
class ButtonColors:
    """Button color constants for different action types."""

    ADD_DEFAULT: str = "#1A73E8"
    ADD_BORDER_HOVERED: str = "#1558C0"
    DELETE_DEFAULT: str = "#E94E77"
    DELETE_BORDER_HOVERED: str = "#FF5A85"
    CANCEL_DEFAULT: str = "#282828"
    CANCEL_BORDER_HOVERED: str = "#444444"
    UPDATE_DEFAULT: str = ADD_DEFAULT
    UPDATE_BORDER_HOVERED: str = ADD_BORDER_HOVERED
    REFRESH_DEFAULT: str = "#1E8E3E"
    REFRESH_BORDER_HOVERED: str = "#137333"


@dataclass(frozen=True)
class FontConfig:
    """Typography configuration for consistent text styling."""

    FAMILY_PRIMARY: str = "Roboto"
    SIZE_PRIMARY: int = 16
    SIZE_SECONDARY: int = 14
    SIZE_TERTIARY: int = 12
    HEADER_SIZE: int = 24
    HEADING_SIZE: int = 18


@dataclass(frozen=True)
class ButtonTextStyle:
    """Text styling for buttons."""

    weight: str = ft.FontWeight.W_400  # type: ignore[assignment]
    size: int = 16
    font_family: str = FontConfig.FAMILY_PRIMARY


# Create instances for each button type
AddButtonTextStyle = ButtonTextStyle()
UpdateButtonTextStyle = ButtonTextStyle()
DeleteButtonTextStyle = ButtonTextStyle()
CancelButtonTextStyle = ButtonTextStyle()
RefreshButtonTextStyle = ButtonTextStyle()


@dataclass(frozen=True)
class Style:
    """Base style class with dict conversion support."""

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


@dataclass(frozen=True)
class TextStyle(Style):
    """Base text style with common properties."""

    color: str
    font_family: str
    size: int
    weight: str


@dataclass(frozen=True)
class PrimaryTextStyle(TextStyle):
    """Primary text style for main content."""

    color: str = ColorPalette.TEXT_PRIMARY_DEFAULT
    font_family: str = FontConfig.FAMILY_PRIMARY
    size: int = FontConfig.SIZE_PRIMARY
    weight: str = ft.FontWeight.W_400  # type: ignore[assignment]


@dataclass(frozen=True)
class SecondaryTextStyle(TextStyle):
    """Secondary text style for supporting content."""

    color: str = ColorPalette.TEXT_SECONDARY_DEFAULT
    font_family: str = FontConfig.FAMILY_PRIMARY
    size: int = FontConfig.SIZE_SECONDARY
    weight: str = ft.FontWeight.W_400  # type: ignore[assignment]


@dataclass(frozen=True)
class ConfirmationTextStyle(TextStyle):
    """Text style for confirmation/warning messages."""

    color: str = ColorPalette.ERROR
    font_family: str = FontConfig.FAMILY_PRIMARY
    size: int = FontConfig.SIZE_SECONDARY
    weight: str = ft.FontWeight.W_400  # type: ignore[assignment]


@dataclass(frozen=True)
class TitleTextStyle(TextStyle):
    """Text style for titles and headers."""

    color: str = ColorPalette.TEXT_PRIMARY_DEFAULT
    font_family: str = FontConfig.FAMILY_PRIMARY
    size: int = FontConfig.HEADER_SIZE
    weight: str = ft.FontWeight.W_700  # type: ignore[assignment]


@dataclass(frozen=True)
class ModalTitle(PrimaryTextStyle):
    """Text style for modal titles."""

    weight: str = ft.FontWeight.W_700  # type: ignore[assignment]


@dataclass(frozen=True)
class ModalSubtitle(SecondaryTextStyle):
    """Text style for modal subtitles."""

    weight: str = ft.FontWeight.W_400  # type: ignore[assignment]


@dataclass(frozen=True)
class TertiaryLabel(PrimaryTextStyle):
    """Small label text style."""

    weight: str = ft.FontWeight.W_600  # type: ignore[assignment]
    size: int = FontConfig.SIZE_TERTIARY


@dataclass(frozen=True)
class SidebarLabelHeadingStyle(PrimaryTextStyle):
    """Text style for sidebar headings."""

    weight: str = ft.FontWeight.W_700  # type: ignore[assignment]


@dataclass(frozen=True)
class SidebarLabelStyle(SecondaryTextStyle):
    """Text style for sidebar labels."""

    weight: str = ft.FontWeight.W_400  # type: ignore[assignment]


@dataclass(frozen=True)
class SliderLabelStyle(SecondaryTextStyle):
    """Text style for slider labels."""

    weight: str = ft.FontWeight.W_700  # type: ignore[assignment]


@dataclass(frozen=True)
class SliderValueStyle(SecondaryTextStyle):
    """Text style for slider values."""

    pass


def create_button_style(
    text_color: str,
    default_bgcolor: str,
    hover_bgcolor: str,
    focus_bgcolor: str,
    active_bgcolor: str,
    disabled_bgcolor: str = "#3A3A3A",  # Gray for disabled state
) -> ft.ButtonStyle:
    """
    Create a ButtonStyle with consistent hover, focus, and pressed states.

    Features:
    - Dramatic elevation changes on hover (4→8)
    - Fast animations (100ms) for responsive feel
    - Subtle shadows for depth
    - Theme-aware disabled states
    """
    return ft.ButtonStyle(
        color={
            ft.ControlState.DEFAULT: text_color,
            ft.ControlState.HOVERED: text_color,
            ft.ControlState.FOCUSED: text_color,
            ft.ControlState.PRESSED: text_color,
            ft.ControlState.DISABLED: "#7F7F7F",  # Gray disabled text
        },
        bgcolor={
            ft.ControlState.DEFAULT: default_bgcolor,
            ft.ControlState.HOVERED: hover_bgcolor,
            ft.ControlState.FOCUSED: focus_bgcolor,
            ft.ControlState.PRESSED: active_bgcolor,
            ft.ControlState.DISABLED: disabled_bgcolor,
        },
        shape=ft.RoundedRectangleBorder(radius=10),
        overlay_color={
            ft.ControlState.DEFAULT: ft.Colors.TRANSPARENT,
            ft.ControlState.HOVERED: ft.Colors.TRANSPARENT,
            ft.ControlState.FOCUSED: ft.Colors.TRANSPARENT,
            ft.ControlState.PRESSED: ft.Colors.with_opacity(0.1, ft.Colors.WHITE),
            ft.ControlState.DISABLED: ft.Colors.TRANSPARENT,
        },
        shadow_color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK),
        elevation={
            ft.ControlState.DEFAULT: 4,
            ft.ControlState.HOVERED: 8,  # Dramatic hover effect
            ft.ControlState.FOCUSED: 6,
            ft.ControlState.PRESSED: 2,
            ft.ControlState.DISABLED: 0,
        },
        animation_duration=100,  # Fast animation for responsive feel
    )


# Button style presets
ELEVATED_BUTTON_ADD_STYLE = create_button_style(
    text_color=ft.Colors.WHITE,
    default_bgcolor=ButtonColors.ADD_DEFAULT,
    hover_bgcolor=ButtonColors.ADD_BORDER_HOVERED,
    focus_bgcolor=ButtonColors.ADD_DEFAULT,
    active_bgcolor=ft.Colors.with_opacity(0.8, ButtonColors.ADD_DEFAULT),
)

ELEVATED_BUTTON_UPDATE_STYLE = create_button_style(
    text_color=ft.Colors.WHITE,
    default_bgcolor=ButtonColors.UPDATE_DEFAULT,
    hover_bgcolor=ButtonColors.UPDATE_BORDER_HOVERED,
    focus_bgcolor=ButtonColors.UPDATE_DEFAULT,
    active_bgcolor=ft.Colors.with_opacity(0.8, ButtonColors.UPDATE_DEFAULT),
)

ELEVATED_BUTTON_DELETE_STYLE = create_button_style(
    text_color=ft.Colors.WHITE,
    default_bgcolor=ButtonColors.DELETE_DEFAULT,
    hover_bgcolor=ButtonColors.DELETE_BORDER_HOVERED,
    focus_bgcolor=ButtonColors.DELETE_DEFAULT,
    active_bgcolor=ft.Colors.with_opacity(0.8, ButtonColors.DELETE_DEFAULT),
)

ELEVATED_BUTTON_CANCEL_STYLE = create_button_style(
    text_color=ColorPalette.TEXT_PRIMARY_DEFAULT,
    default_bgcolor=ButtonColors.CANCEL_DEFAULT,
    hover_bgcolor=ButtonColors.CANCEL_BORDER_HOVERED,
    focus_bgcolor=ButtonColors.CANCEL_DEFAULT,
    active_bgcolor=ft.Colors.with_opacity(0.8, ButtonColors.CANCEL_DEFAULT),
)

ELEVATED_BUTTON_REFRESH_STYLE = create_button_style(
    text_color=ft.Colors.WHITE,
    default_bgcolor=ButtonColors.REFRESH_DEFAULT,
    hover_bgcolor=ButtonColors.REFRESH_BORDER_HOVERED,
    focus_bgcolor=ButtonColors.REFRESH_DEFAULT,
    active_bgcolor=ft.Colors.with_opacity(0.8, ButtonColors.REFRESH_DEFAULT),
)

ELEVATED_BUTTON_LOGOUT_STYLE = create_button_style(
    text_color=ft.Colors.WHITE,
    default_bgcolor=ButtonColors.DELETE_DEFAULT,
    hover_bgcolor=ButtonColors.DELETE_BORDER_HOVERED,
    focus_bgcolor=ButtonColors.DELETE_DEFAULT,
    active_bgcolor=ft.Colors.with_opacity(0.8, ButtonColors.DELETE_DEFAULT),
)
