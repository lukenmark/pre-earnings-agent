from sqlalchemy.orm import Session

from models.industry import IndustryAssessment
from storage.tables import IndustryAssessmentRow


def save(db: Session, assessment: IndustryAssessment) -> IndustryAssessmentRow:
    import json
    row = IndustryAssessmentRow(
        industry_name=assessment.industry_name,
        composite_score=assessment.composite_score,
        metrics_json=json.dumps(assessment.metrics),
        status=assessment.status,
        consecutive_low_weeks=assessment.consecutive_low_weeks,
        assessed_at=assessment.assessed_at,
        notes=assessment.notes,
    )
    db.add(row)
    db.flush()
    return row


def get_active(db: Session) -> list[IndustryAssessmentRow]:
    return db.query(IndustryAssessmentRow).filter(IndustryAssessmentRow.status == "active").all()


def get_latest_by_name(db: Session, name: str) -> IndustryAssessmentRow | None:
    return (
        db.query(IndustryAssessmentRow)
        .filter(IndustryAssessmentRow.industry_name == name)
        .order_by(IndustryAssessmentRow.assessed_at.desc())
        .first()
    )


def get_history(db: Session, name: str) -> list[IndustryAssessmentRow]:
    return (
        db.query(IndustryAssessmentRow)
        .filter(IndustryAssessmentRow.industry_name == name)
        .order_by(IndustryAssessmentRow.assessed_at)
        .all()
    )
