"""SQLAlchemy models. Importing this package registers every table on ``Base.metadata``."""
from app.models.curriculum import (  # noqa: F401
    LearningPlanItem,
    PrescribedText,
    Student,
    Subject,
    SyllabusOutcome,
    SyllabusTopic,
    SyllabusVersion,
)
from app.models.questions import (  # noqa: F401
    MarkingGuideline,
    Question,
    QuestionMapping,
    QuestionPart,
    Source,
    SourceDocument,
    Stimulus,
)
from app.models.study import (  # noqa: F401
    Attempt,
    AttemptFeedback,
    DailySession,
    ErrorJournal,
    Mastery,
    QuestionExposure,
    RevisionQueue,
    SessionQuestion,
    TutorComment,
)
from app.models.legal import LegalEvidence, LegalEvidenceTopic  # noqa: F401
from app.models.settings import Setting  # noqa: F401
from app.models.ingestion import QuestionOutcome, QuestionPlanItem, QuestionStimulus, ReviewDecision  # noqa: F401  # v2-ingestion
