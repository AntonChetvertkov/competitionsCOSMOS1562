"""questionnaire builder: contest status/settings, new question kinds, multi-choice answers, team codes

Written by hand: Alembic does not detect CHECK constraint changes, and the
question-kind list changed. The three question tables are rebuilt from
scratch; that is only safe while they are empty, so the upgrade refuses to
run if they hold data.

Revision ID: a7c41f2b9e10
Revises: d30dd6994d85
Create Date: 2026-11-26
"""
from alembic import op
import sqlalchemy as sa

revision = "a7c41f2b9e10"
down_revision = "d30dd6994d85"
branch_labels = None
depends_on = None

FIELD_KINDS = "('short_text', 'long_text', 'number', 'date', 'single', 'dropdown', 'multiple')"


def _create_question_tables():
    op.create_table(
        "application_fields",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contest_id", sa.Integer(), sa.ForeignKey("contests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("help_text", sa.String(), nullable=False, server_default=""),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("allows_other", sa.Boolean(), nullable=False, server_default="0"),
        sa.UniqueConstraint("contest_id", "position", name="uq_field_position"),
        sa.CheckConstraint(f"kind IN {FIELD_KINDS}", name="ck_field_kind"),
        sa.CheckConstraint("allows_other = 0 OR kind IN ('single', 'dropdown', 'multiple')",
                           name="ck_field_other_only_for_choice"),
    )
    op.create_table(
        "field_options",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("field_id", sa.Integer(), sa.ForeignKey("application_fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.UniqueConstraint("field_id", "position", name="uq_option_position"),
    )
    op.create_table(
        "application_answers",
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("entries.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("field_id", sa.Integer(), sa.ForeignKey("application_fields.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("value_text", sa.String(), nullable=True),
        sa.Column("option_id", sa.Integer(), sa.ForeignKey("field_options.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_table(
        "answer_choices",
        sa.Column("entry_id", sa.Integer(), primary_key=True),
        sa.Column("field_id", sa.Integer(), primary_key=True),
        sa.Column("option_id", sa.Integer(), sa.ForeignKey("field_options.id", ondelete="CASCADE"), primary_key=True),
        sa.ForeignKeyConstraint(["entry_id", "field_id"],
                                ["application_answers.entry_id", "application_answers.field_id"],
                                ondelete="CASCADE", name="fk_choice_answer"),
    )


def upgrade():
    conn = op.get_bind()
    for table in ("application_answers", "field_options", "application_fields"):
        if conn.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar():
            raise RuntimeError(f"{table} has data; this migration rebuilds it and would lose it.")

    op.drop_table("application_answers")
    op.drop_table("field_options")
    op.drop_table("application_fields")
    _create_question_tables()

    with op.batch_alter_table("contests", schema=None) as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(), nullable=False, server_default="draft"))
        batch_op.add_column(sa.Column("cover_path", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("thank_you_text", sa.String(), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("max_entries", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("manual_approval", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.alter_column("consent_confirmed_at", existing_type=sa.DateTime(), nullable=True)
        batch_op.create_check_constraint("ck_contest_status", "status IN ('draft', 'published', 'closed')")
        batch_op.create_check_constraint("ck_contest_max_entries", "max_entries IS NULL OR max_entries > 0")
        batch_op.create_check_constraint("ck_contest_team_max", "team_max IS NULL OR team_max >= 1")
        # SQLite batch mode drops the old unnamed CHECKs when it rebuilds the
        # table, so they are re-added here, named this time.
        batch_op.create_check_constraint("ck_contest_join_mode", "join_mode IN ('open', 'application', 'link')")
        batch_op.create_check_constraint("ck_contest_entry_kind", "entry_kind IN ('individual', 'team')")
        batch_op.create_check_constraint("ck_contest_scoring",
                                         "scoring_scheme IN ('activity_and_jury', 'points', 'certificate')")
        batch_op.create_check_constraint("ck_contest_jury_weight", "jury_weight BETWEEN 0 AND 100")

    with op.batch_alter_table("entries", schema=None) as batch_op:
        batch_op.add_column(sa.Column("join_code", sa.String(), nullable=True))
        batch_op.create_unique_constraint("uq_entry_join_code", ["join_code"])
        batch_op.create_check_constraint("ck_entry_status",
                                         "status IN ('pending', 'approved', 'rejected', 'withdrawn')")


def downgrade():
    with op.batch_alter_table("entries", schema=None) as batch_op:
        batch_op.drop_constraint("ck_entry_status", type_="check")
        batch_op.drop_constraint("uq_entry_join_code", type_="unique")
        batch_op.drop_column("join_code")

    with op.batch_alter_table("contests", schema=None) as batch_op:
        for name in ("ck_contest_jury_weight", "ck_contest_scoring", "ck_contest_entry_kind",
                     "ck_contest_join_mode", "ck_contest_team_max"):
            batch_op.drop_constraint(name, type_="check")
        batch_op.drop_constraint("ck_contest_max_entries", type_="check")
        batch_op.drop_constraint("ck_contest_status", type_="check")
        batch_op.alter_column("consent_confirmed_at", existing_type=sa.DateTime(), nullable=False)
        batch_op.drop_column("manual_approval")
        batch_op.drop_column("max_entries")
        batch_op.drop_column("thank_you_text")
        batch_op.drop_column("cover_path")
        batch_op.drop_column("status")

    op.drop_table("answer_choices")
    op.drop_table("application_answers")
    op.drop_table("field_options")
    op.drop_table("application_fields")
    # Recreate the pre-builder shape (kinds: short_text, long_text, number, choice, checkbox).
    op.create_table(
        "application_fields",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contest_id", sa.Integer(), sa.ForeignKey("contests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("contest_id", "position"),
        sa.CheckConstraint("kind IN ('short_text', 'long_text', 'number', 'choice', 'checkbox')"),
    )
    op.create_table(
        "field_options",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("field_id", sa.Integer(), sa.ForeignKey("application_fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.UniqueConstraint("field_id", "position"),
    )
    op.create_table(
        "application_answers",
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("entries.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("field_id", sa.Integer(), sa.ForeignKey("application_fields.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("value_text", sa.String(), nullable=True),
        sa.Column("option_id", sa.Integer(), sa.ForeignKey("field_options.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint("value_text IS NOT NULL OR option_id IS NOT NULL"),
    )
