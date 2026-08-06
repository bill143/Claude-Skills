"""audit_events immutability trigger (PostgreSQL)

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-06

Defense in depth for the audit ledger: the application layer already refuses
ORM updates/deletes on AuditEvent and the hash chain makes tampering
detectable, but this trigger stops raw-SQL mutation at the database itself.
SQLite (dev/tests) has no equivalent guard — detection there relies on the
hash chain, which the test suite covers.
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_events_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only: % blocked', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_events_immutable
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_immutable ON audit_events;")
    op.execute("DROP FUNCTION IF EXISTS audit_events_immutable();")
