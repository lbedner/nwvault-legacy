"""
Safe schema fix migration generator.

Compares SQLModel metadata against the actual database schema and generates
an Alembic migration that only adds missing columns/tables. Never drops anything.

Usage: python -m app.cli.migrate_fix
"""


import sys
from datetime import UTC, datetime
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlmodel import SQLModel

from app.core.db import engine
from app.i18n import t





def _sa_type_str(col_type: object) -> str:
    """Convert a SQLAlchemy/SQLModel column type to a sa.X() string."""
    type_name = type(col_type).__name__
    sa_mapping = {
        "AutoString": "String",
        "Boolean": "Boolean",
        "Integer": "Integer",
        "BigInteger": "BigInteger",
        "SmallInteger": "SmallInteger",
        "DateTime": "DateTime",
        "Float": "Float",
        "Text": "Text",
        "Numeric": "Numeric",
        "Date": "Date",
        "Time": "Time",
        "LargeBinary": "LargeBinary",
        "JSON": "JSON",
    }
    mapped = sa_mapping.get(type_name, type_name)
    return f"sa.{mapped}()"


def _get_additive_diffs() -> list[tuple]:
    """
    Compare models against DB and return only additive differences.

    Filters out all destructive ops (drop table, drop column, etc.)
    and ops on tables not in SQLModel metadata.
    """
    # Tables we manage (from SQLModel models)
    managed_tables = set(SQLModel.metadata.tables.keys())

    with engine.connect() as conn:
        migration_ctx = MigrationContext.configure(conn)
        diffs = compare_metadata(migration_ctx, SQLModel.metadata)

    additive_diffs = []
    for diff in diffs:
        op_type = diff[0]

        if op_type == "add_column":
            # diff = ("add_column", schema, table_name, Column object)
            table_name = diff[2]
            if table_name in managed_tables:
                additive_diffs.append(diff)

        elif op_type == "add_table":
            # Missing tables need a full migration — too complex for auto-fix
            table = diff[1]
            if table.name in managed_tables:
                print(
                    t("migrate.table_missing_warning", table=table.name)
                )

        # Skip: add_index, remove_table, remove_column, remove_index,
        # modify_type, modify_nullable, modify_default, etc.

    return additive_diffs


def _generate_fix_migration(diffs: list[tuple]) -> Path | None:
    """Generate an Alembic migration file from additive diffs."""
    alembic_cfg = Config("alembic/alembic.ini")
    script_dir = ScriptDirectory.from_config(alembic_cfg)

    # Get current head
    heads = script_dir.get_heads()
    if not heads:
        print(t("migrate.no_existing_migrations"))
        return None

    head = heads[0]
    versions_dir = Path("alembic/versions")

    # Generate revision ID
    existing = sorted(
        f.stem.split("_")[0]
        for f in versions_dir.glob("*.py")
        if f.name != "__init__.py" and f.stem.split("_")[0].isdigit()
    )
    if existing:
        next_id = f"{int(existing[-1]) + 1:03d}"
    else:
        next_id = "001"

    # Build migration content
    upgrade_lines = []
    downgrade_lines = []

    for diff in diffs:
        op_type = diff[0]

        if op_type == "add_column":
            table_name = diff[2]
            column = diff[3]
            col_str = f"sa.Column('{column.name}', {_sa_type_str(column.type)}"
            col_str += f", nullable={column.nullable}"
            if column.server_default is not None:
                col_str += f", server_default=sa.text('{column.server_default.arg}')"
            elif not column.nullable:
                # Non-nullable columns need a server_default for existing rows
                # Try to get the Python default from the model
                py_default = column.default
                if py_default is not None and hasattr(py_default, "arg"):
                    # SQLAlchemy ColumnDefault with a scalar value
                    val = py_default.arg
                    if isinstance(val, bool):
                        col_str += f", server_default=sa.text('{str(val).lower()}')"
                    elif isinstance(val, (int, float)):
                        col_str += f", server_default=sa.text('{val}')"
                    elif isinstance(val, str):
                        col_str += f", server_default=sa.text(\"'{val}'\")"
                else:
                    # Fallback based on column type
                    type_name = type(column.type).__name__
                    if type_name in ("Boolean",):
                        col_str += ", server_default=sa.text('false')"
                    elif type_name in ("String", "Text", "VARCHAR"):
                        col_str += ", server_default=sa.text(\"''\")"
                    elif type_name in ("Integer", "BigInteger", "SmallInteger"):
                        col_str += ", server_default=sa.text('0')"
            col_str += ")"
            upgrade_lines.append(
                f"    op.add_column('{table_name}', {col_str})"
            )
            downgrade_lines.append(
                f"    op.drop_column('{table_name}', '{column.name}')"
            )

    if not upgrade_lines:
        return None

    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")
    content = f'''"""Schema fix: add missing columns and tables

Revision ID: {next_id}
Revises: {head}
Create Date: {timestamp}

Auto-generated by 'make migrate-fix' to reconcile schema mismatches
after an Aegis Stack upgrade. This migration only adds — never drops.
"""

import sqlalchemy as sa

from alembic import op

revision = '{next_id}'
down_revision = '{head}'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add missing columns and tables."""
{chr(10).join(upgrade_lines)}


def downgrade() -> None:
    """Remove added columns and tables."""
{chr(10).join(reversed(downgrade_lines))}
'''

    migration_path = versions_dir / f"{next_id}_schema_fix.py"
    migration_path.write_text(content)
    return migration_path


def main() -> None:
    """Check for schema mismatches and generate fix migration."""
    print(t("migrate.checking_schema"))

    diffs = _get_additive_diffs()

    if not diffs:
        print(t("migrate.schema_up_to_date"))
        sys.exit(0)

    print(t("migrate.found_differences", count=len(diffs)))
    for diff in diffs:
        if diff[0] == "add_column":
            print(f"  + {t('migrate.add_column')} {diff[2]}.{diff[3].name}")

    migration_path = _generate_fix_migration(diffs)
    if migration_path:
        print(f"\n{t('migrate.generated_migration', name=migration_path.name)}")
    else:
        print(f"\n{t('migrate.no_fixable_differences')}")
        sys.exit(0)


if __name__ == "__main__":
    main()

