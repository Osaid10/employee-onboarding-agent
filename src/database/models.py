"""SQLAlchemy HRIS database models for the Employee Onboarding system."""

from datetime import datetime, date
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    ForeignKey,
    Enum,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ---------------------------------------------------------------------------
# Enumerations (stored as strings because SQLite has no native enum support)
# ---------------------------------------------------------------------------
EMPLOYEE_STATUS_VALUES = [
    "initialized",
    "pre_boarding",
    "documents_collection",
    "it_setup",
    "training",
    "complete",
]

TASK_CATEGORY_VALUES = ["documents", "it_setup", "training", "compliance", "hr"]

TASK_STATUS_VALUES = ["pending", "in_progress", "complete", "overdue"]

URGENCY_VALUES = ["low", "medium", "high", "critical"]

EMAIL_TYPE_VALUES = [
    "welcome",
    "reminder",
    "escalation",
    "confirmation",
    "completion",
]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class Employee(Base):
    """Represents a new hire going through the onboarding process."""

    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(10), unique=True, nullable=False)  # EMP-XXX
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    role = Column(String(150), nullable=False)
    department = Column(String(100), nullable=False)
    manager = Column(String(200), nullable=False)
    start_date = Column(Date, nullable=False)
    location = Column(String(200), nullable=False)
    status = Column(
        String(30),
        nullable=False,
        default="initialized",
    )

    # Relationships
    tasks = relationship(
        "OnboardingTask", back_populates="employee", cascade="all, delete-orphan"
    )
    escalations = relationship(
        "Escalation", back_populates="employee", cascade="all, delete-orphan"
    )
    email_logs = relationship(
        "EmailLog", back_populates="employee", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Employee {self.employee_id} — {self.first_name} {self.last_name} "
            f"({self.department})>"
        )


class OnboardingTask(Base):
    """A single onboarding task assigned to an employee."""

    __tablename__ = "onboarding_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    task_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(30), nullable=False)  # TASK_CATEGORY_VALUES
    status = Column(String(30), nullable=False, default="pending")  # TASK_STATUS_VALUES
    due_date = Column(Date, nullable=False)
    completed_date = Column(Date, nullable=True)
    reminder_count = Column(Integer, nullable=False, default=0)

    # Relationships
    employee = relationship("Employee", back_populates="tasks")
    escalations = relationship(
        "Escalation", back_populates="task", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<OnboardingTask {self.task_name} — {self.status}>"


class Escalation(Base):
    """An escalation raised when a task is critically overdue or blocked."""

    __tablename__ = "escalations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    task_id = Column(
        Integer,
        ForeignKey("onboarding_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason = Column(Text, nullable=False)
    urgency = Column(String(20), nullable=False, default="medium")  # URGENCY_VALUES
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(200), nullable=True)

    # Relationships
    employee = relationship("Employee", back_populates="escalations")
    task = relationship("OnboardingTask", back_populates="escalations")

    def __repr__(self) -> str:
        return f"<Escalation employee={self.employee_id} urgency={self.urgency}>"


class EmailLog(Base):
    """Log of every email sent during the onboarding workflow."""

    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    recipient = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    sent_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    email_type = Column(String(30), nullable=False)  # EMAIL_TYPE_VALUES

    # Relationships
    employee = relationship("Employee", back_populates="email_logs")

    def __repr__(self) -> str:
        return f"<EmailLog to={self.recipient} type={self.email_type}>"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def create_tables(engine) -> None:
    """Create all tables in the database (idempotent)."""
    Base.metadata.create_all(engine)
