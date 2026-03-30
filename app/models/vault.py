"""Vault data models for NWN1/NWN2 archive entries."""

from datetime import datetime

from sqlalchemy import JSON, Column, Index, Text
from sqlmodel import Field, Relationship, SQLModel


class VaultCategory(SQLModel, table=True):
    """A content category (e.g., modules, hakpaks, scripts)."""

    __tablename__ = "vault_categories"

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    game: str = Field(index=True)  # "nwn1" or "nwn2"
    display_name: str
    entry_count: int = Field(default=0)

    entries: list[VaultEntry] = Relationship(back_populates="category_rel")


class VaultEntry(SQLModel, table=True):
    """A single vault entry (module, hakpak, script, etc.)."""

    __tablename__ = "vault_entries"
    __table_args__ = (
        Index("ix_vault_entries_game_category", "game", "category"),
        Index("ix_vault_entries_score", "score"),
    )

    id: int | None = Field(default=None, primary_key=True)
    entry_id: int = Field(index=True)  # Original vault entry ID
    game: str = Field(index=True)  # "nwn1" or "nwn2"
    category: str = Field(index=True)  # "modules", "hakpaks", etc.
    category_id: int | None = Field(default=None, foreign_key="vault_categories.id")

    title: str = Field(index=True)
    author: str = Field(index=True)
    description: str = Field(default="", sa_column=Column(Text))
    submitted: str = Field(default="")
    updated: str = Field(default="")

    score: float = Field(default=0.0)
    votes: int = Field(default=0)
    total_comments: int = Field(default=0)

    # Category-specific fields stored as JSON
    # e.g., modules: LevelRange, NumberPlayers, DMNeeded
    # e.g., hakpaks: Expansions
    extra_fields: dict | None = Field(default=None, sa_column=Column(JSON))

    # Archive paths
    html_path: str | None = Field(default=None)  # Local path to index.html
    has_html: bool = Field(default=False)

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    category_rel: VaultCategory | None = Relationship(back_populates="entries")
    comments: list[VaultComment] = Relationship(back_populates="entry")
    files: list[VaultFile] = Relationship(back_populates="entry")
    screenshots: list[VaultScreenshot] = Relationship(back_populates="entry")
    reviews: list[VaultReview] = Relationship(back_populates="entry")


class VaultComment(SQLModel, table=True):
    """A comment on a vault entry."""

    __tablename__ = "vault_comments"

    id: int | None = Field(default=None, primary_key=True)
    entry_id: int = Field(foreign_key="vault_entries.id", index=True)
    submitter: str = Field(default="")
    date: str = Field(default="")
    content: str = Field(default="", sa_column=Column(Text))

    entry: VaultEntry | None = Relationship(back_populates="comments")


class VaultFile(SQLModel, table=True):
    """A downloadable file associated with a vault entry."""

    __tablename__ = "vault_files"

    id: int | None = Field(default=None, primary_key=True)
    entry_id: int = Field(foreign_key="vault_entries.id", index=True)
    filepath: str = Field(default="")  # Original vault filepath
    filename: str = Field(default="")
    title: str = Field(default="")
    description: str = Field(default="")
    file_type: str = Field(default="")

    entry: VaultEntry | None = Relationship(back_populates="files")


class VaultScreenshot(SQLModel, table=True):
    """A screenshot/image associated with a vault entry."""

    __tablename__ = "vault_screenshots"

    id: int | None = Field(default=None, primary_key=True)
    entry_id: int = Field(foreign_key="vault_entries.id", index=True)
    filepath: str = Field(default="")  # Original vault filepath
    filename: str = Field(default="")
    thumb_src: str = Field(default="")
    local_path: str | None = Field(default=None)  # Local path after download

    entry: VaultEntry | None = Relationship(back_populates="screenshots")


class VaultReview(SQLModel, table=True):
    """A user review/rating from the Ratings.Viewer page."""

    __tablename__ = "vault_reviews"

    id: int | None = Field(default=None, primary_key=True)
    entry_id: int = Field(foreign_key="vault_entries.id", index=True)
    username: str = Field(default="", index=True)
    user_vault_id: int | None = Field(default=None)
    score: float = Field(default=0.0)
    content: str = Field(default="", sa_column=Column(Text))
    date: str = Field(default="")

    entry: VaultEntry | None = Relationship(back_populates="reviews")
