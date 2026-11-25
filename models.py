from datetime import datetime, timezone
from typing import Optional


from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship



class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

def utc_now():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    # Emails are stored lowercased (see auth.normalize_email), so a plain
    # UNIQUE is enough to stop look-alike accounts like Admin@x.com.
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[Optional[str]] = mapped_column(unique=True)
    first_name: Mapped[str]
    last_name: Mapped[str]
    password_hash: Mapped[Optional[str]]
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    identities: Mapped[list["OAuthIdentity"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    memberships: Mapped[list["EntryMember"]] = relationship(back_populates="user")
    organiser_requests: Mapped[list["OrganiserRequest"]] = relationship(
        back_populates="user", foreign_keys="OrganiserRequest.user_id",
        order_by="OrganiserRequest.created_at.desc()", cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_organiser(self) -> bool:
        # 3NF: no flag on the user; an approved request is the fact.
        return any(r.status == "approved" for r in self.organiser_requests)

    @property
    def latest_organiser_request(self) -> Optional["OrganiserRequest"]:
        return self.organiser_requests[0] if self.organiser_requests else None


class OAuthIdentity(db.Model):
    __tablename__ = "oauth_identities"
    __table_args__ = (
        UniqueConstraint("provider", "subject"),
        CheckConstraint("provider IN ('microsoft', 'google', 'yandex', 'vk')"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str]
    subject: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    user: Mapped["User"] = relationship(back_populates="identities")


class OrganiserRequest(db.Model):
    __tablename__ = "organiser_requests"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected')"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    organisation: Mapped[str]
    message: Mapped[str] = mapped_column(default="")
    status: Mapped[str] = mapped_column(default="pending")
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    user: Mapped["User"] = relationship(back_populates="organiser_requests", foreign_keys=[user_id])
    reviewer: Mapped[Optional["User"]] = relationship(foreign_keys=[reviewed_by])


CONTEST_STATUSES = ("draft", "published", "closed")
FIELD_KINDS = ("short_text", "long_text", "number", "date", "single", "dropdown", "multiple")
CHOICE_KINDS = ("single", "dropdown", "multiple")


class Contest(db.Model):
    __tablename__ = "contests"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published', 'closed')", name="ck_contest_status"),
        CheckConstraint("max_entries IS NULL OR max_entries > 0", name="ck_contest_max_entries"),
        CheckConstraint("team_max IS NULL OR team_max >= 1", name="ck_contest_team_max"),
        CheckConstraint("join_mode IN ('open', 'application', 'link')", name="ck_contest_join_mode"),
        CheckConstraint("entry_kind IN ('individual', 'team')", name="ck_contest_entry_kind"),
        CheckConstraint("scoring_scheme IN ('activity_and_jury', 'points', 'certificate')",
                        name="ck_contest_scoring"),
        CheckConstraint("jury_weight BETWEEN 0 AND 100", name="ck_contest_jury_weight"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    slug: Mapped[str] = mapped_column(unique=True)
    title: Mapped[str]
    description: Mapped[str] = mapped_column(default="")
    join_mode: Mapped[str] = mapped_column(default="link")
    status: Mapped[str] = mapped_column(default="draft", server_default="draft")
    cover_path: Mapped[Optional[str]]          # file name under the uploads folder
    thank_you_text: Mapped[str] = mapped_column(default="", server_default="")
    max_entries: Mapped[Optional[int]]         # counts entries (teams), not people
    manual_approval: Mapped[bool] = mapped_column(default=False, server_default="0")
    invite_token: Mapped[Optional[str]] = mapped_column(unique=True)
    entry_kind: Mapped[str] = mapped_column(default="individual")
    team_min: Mapped[Optional[int]]
    team_max: Mapped[Optional[int]]
    registration_closes_at: Mapped[Optional[datetime]]
    scoring_scheme: Mapped[str] = mapped_column(default="certificate")
    jury_weight: Mapped[int] = mapped_column(default=100)
    photo_retention_days: Mapped[int] = mapped_column(default=90)
    consent_confirmed_at: Mapped[Optional[datetime]]   # set when published
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    owner: Mapped["User"] = relationship()
    fields: Mapped[list["ApplicationField"]] = relationship(
        back_populates="contest", order_by="ApplicationField.position",
        cascade="all, delete-orphan"
    )
    entries: Mapped[list["Entry"]] = relationship(
        back_populates="contest", cascade="all, delete-orphan"
    )

    def entry_count(self) -> int:
        return db.session.scalar(
            db.select(db.func.count(Entry.id)).where(Entry.contest_id == self.id)) or 0

    def closes_passed(self) -> bool:
        if self.registration_closes_at is None:
            return False
        closes = self.registration_closes_at
        if closes.tzinfo is None:              # SQLite returns naive datetimes; stored as UTC
            closes = closes.replace(tzinfo=timezone.utc)
        return utc_now() >= closes

    def is_full(self) -> bool:
        return self.max_entries is not None and self.entry_count() >= self.max_entries

    def accepts_new_entries(self) -> bool:
        return self.status == "published" and not self.closes_passed() and not self.is_full()

    def accepts_edits(self) -> bool:
        """Existing entries can change answers / join teams while this is true."""
        return self.status == "published" and not self.closes_passed()

    def questions_locked(self) -> bool:
        """Once anyone has answered, questions can't change (answers would break)."""
        return self.entry_count() > 0


class ApplicationField(db.Model):
    __tablename__ = "application_fields"
    __table_args__ = (
        UniqueConstraint("contest_id", "position", name="uq_field_position"),
        CheckConstraint("kind IN ('short_text', 'long_text', 'number', 'date', 'single', 'dropdown', 'multiple')",
                        name="ck_field_kind"),
        CheckConstraint("allows_other = 0 OR kind IN ('single', 'dropdown', 'multiple')",
                        name="ck_field_other_only_for_choice"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("contests.id", ondelete="CASCADE"))
    position: Mapped[int]
    label: Mapped[str]
    kind: Mapped[str]
    help_text: Mapped[str] = mapped_column(default="")
    is_required: Mapped[bool] = mapped_column(default=True)
    allows_other: Mapped[bool] = mapped_column(default=False)

    contest: Mapped["Contest"] = relationship(back_populates="fields")
    options: Mapped[list["FieldOption"]] = relationship(
        back_populates="field", order_by="FieldOption.position",
        cascade="all, delete-orphan"
    )


class FieldOption(db.Model):
    __tablename__ = "field_options"
    __table_args__ = (UniqueConstraint("field_id", "position", name="uq_option_position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("application_fields.id", ondelete="CASCADE"))
    position: Mapped[int]
    label: Mapped[str]

    field: Mapped["ApplicationField"] = relationship(back_populates="options")


class Entry(db.Model):
    __tablename__ = "entries"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'withdrawn')", name="ck_entry_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("contests.id", ondelete="CASCADE"))
    team_name: Mapped[Optional[str]]
    join_code: Mapped[Optional[str]] = mapped_column(unique=True)   # team invite code
    status: Mapped[str] = mapped_column(default="pending")
    decided_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    contest: Mapped["Contest"] = relationship(back_populates="entries")
    decider: Mapped[Optional["User"]] = relationship(foreign_keys=[decided_by])
    members: Mapped[list["EntryMember"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )
    answers: Mapped[list["ApplicationAnswer"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )


class EntryMember(db.Model):
    __tablename__ = "entry_members"

    entry_id: Mapped[int] = mapped_column(
        ForeignKey("entries.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    is_captain: Mapped[bool] = mapped_column(default=False)
    joined_at: Mapped[datetime] = mapped_column(default=utc_now)

    entry: Mapped["Entry"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="memberships")


class ApplicationAnswer(db.Model):
    """One row per (entry, question).
    value_text: text / number / date answers, or the "Other" text for choice questions.
    option_id: the chosen option for single / dropdown.
    choices: the chosen options for multiple."""
    __tablename__ = "application_answers"

    entry_id: Mapped[int] = mapped_column(
        ForeignKey("entries.id", ondelete="CASCADE"), primary_key=True
    )
    field_id: Mapped[int] = mapped_column(
        ForeignKey("application_fields.id", ondelete="CASCADE"), primary_key=True
    )
    value_text: Mapped[Optional[str]]
    option_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("field_options.id", ondelete="SET NULL")
    )

    entry: Mapped["Entry"] = relationship(back_populates="answers")
    field: Mapped["ApplicationField"] = relationship()
    option: Mapped[Optional["FieldOption"]] = relationship()
    choices: Mapped[list["AnswerChoice"]] = relationship(
        back_populates="answer", cascade="all, delete-orphan"
    )

    def display(self) -> str:
        """The answer as one line of plain text (answers table, CSV).
        Choice answers show the option labels; an "Other" text is appended as-is."""
        kind = self.field.kind
        if kind == "multiple":
            labels = [c.option.label for c in sorted(self.choices, key=lambda c: c.option.position)]
            if self.value_text:
                labels.append(self.value_text)
            return "; ".join(labels)
        if kind in ("single", "dropdown"):
            return self.option.label if self.option else (self.value_text or "")
        return self.value_text or ""


class AnswerChoice(db.Model):
    """Chosen options of a 'multiple' question, one row each."""
    __tablename__ = "answer_choices"
    __table_args__ = (
        ForeignKeyConstraint(["entry_id", "field_id"],
                             ["application_answers.entry_id", "application_answers.field_id"],
                             ondelete="CASCADE", name="fk_choice_answer"),
    )

    entry_id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(primary_key=True)
    option_id: Mapped[int] = mapped_column(
        ForeignKey("field_options.id", ondelete="CASCADE"), primary_key=True
    )

    answer: Mapped["ApplicationAnswer"] = relationship(back_populates="choices")
    option: Mapped["FieldOption"] = relationship()