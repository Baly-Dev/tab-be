"""Auth tables: users, roles, sessions, OAuth, password reset, passkeys.

Revision ID: 0001_auth_schema
Revises:
Create Date: 2026-11-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_auth_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

user_status = postgresql.ENUM(
    "active",
    "pending",
    "suspended",
    "deleted",
    name="user_status",
    create_type=False,
)
oauth_provider = postgresql.ENUM(
    "google",
    "linkedin",
    name="oauth_provider",
    create_type=False,
)
app_role = postgresql.ENUM(
    "super_admin",
    "admin",
    "member",
    name="app_role",
    create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    user_status.create(op.get_bind(), checkfirst=True)
    oauth_provider.create(op.get_bind(), checkfirst=True)
    app_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "auth_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("username", postgresql.CITEXT(), nullable=False),
        sa.Column("first_name", sa.Text(), nullable=False),
        sa.Column("last_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("status", user_status, nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_auth_users_email", "auth_users", ["email"], unique=True)
    op.create_index("ix_auth_users_username", "auth_users", ["username"], unique=True)

    op.create_table(
        "auth_user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", app_role, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "role", name="uq_auth_user_roles_user_role"),
    )
    op.create_index("ix_auth_user_roles_user_id", "auth_user_roles", ["user_id"])

    op.create_table(
        "auth_refresh_token",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_auth_refresh_token_user_id", "auth_refresh_token", ["user_id"])

    op.create_table(
        "auth_social_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", oauth_provider, nullable=False),
        sa.Column("provider_user_id", sa.Text(), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=True),
        sa.Column("raw_profile", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "provider",
            "provider_user_id",
            name="uq_auth_social_accounts_provider_remote",
        ),
        sa.UniqueConstraint("user_id", "provider", name="uq_auth_social_accounts_user_provider"),
    )
    op.create_index("ix_auth_social_accounts_user_id", "auth_social_accounts", ["user_id"])

    op.create_table(
        "auth_password_reset_token",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_auth_password_reset_token_user_id",
        "auth_password_reset_token",
        ["user_id"],
    )
    op.create_index(
        "ix_auth_password_reset_token_token_hash",
        "auth_password_reset_token",
        ["token_hash"],
    )

    op.create_table(
        "auth_webauthn_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credential_id", postgresql.BYTEA(), nullable=False),
        sa.Column("public_key", postgresql.BYTEA(), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transports", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("aaguid", sa.Text(), nullable=True),
        sa.Column(
            "device_name",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'Questo dispositivo'"),
        ),
        sa.Column("backed_up", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("credential_id"),
    )
    op.create_index(
        "ix_auth_webauthn_credentials_user_id",
        "auth_webauthn_credentials",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("auth_webauthn_credentials")
    op.drop_table("auth_password_reset_token")
    op.drop_table("auth_social_accounts")
    op.drop_table("auth_refresh_token")
    op.drop_table("auth_user_roles")
    op.drop_table("auth_users")
    app_role.drop(op.get_bind(), checkfirst=True)
    oauth_provider.drop(op.get_bind(), checkfirst=True)
    user_status.drop(op.get_bind(), checkfirst=True)
