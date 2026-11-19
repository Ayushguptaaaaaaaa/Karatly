from enum import StrEnum


class Role(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"


class Metal(StrEnum):
    GOLD = "GOLD"
    SILVER = "SILVER"
    PLATINUM = "PLATINUM"
    OTHER = "OTHER"


class MovementType(StrEnum):
    OPENING = "OPENING"
    PURCHASE = "PURCHASE"
    CUSTOMER_RETURN = "CUSTOMER_RETURN"
    ADJUSTMENT_IN = "ADJUSTMENT_IN"
    SALE = "SALE"
    SUPPLIER_RETURN = "SUPPLIER_RETURN"
    ADJUSTMENT_OUT = "ADJUSTMENT_OUT"


IN_TYPES = {MovementType.OPENING, MovementType.PURCHASE, MovementType.CUSTOMER_RETURN, MovementType.ADJUSTMENT_IN}
OUT_TYPES = {MovementType.SALE, MovementType.SUPPLIER_RETURN, MovementType.ADJUSTMENT_OUT}


def direction(t: MovementType | str) -> int:
    return 1 if MovementType(t) in IN_TYPES else -1


class MovementSource(StrEnum):
    MANUAL = "MANUAL"
    OPENING = "OPENING"
    PURCHASE_PLAN = "PURCHASE_PLAN"
    IMPORT = "IMPORT"
    DEMO = "DEMO"


class StockStatus(StrEnum):
    IN = "IN"
    LOW = "LOW"
    OUT = "OUT"
    DEAD = "DEAD"


class Demand(StrEnum):
    HIGH = "HIGH"
    STEADY = "STEADY"
    LOW = "LOW"
    DEAD = "DEAD"
    NEW = "NEW"


class PlanStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    DECIDED = "DECIDED"
    RECEIVED = "RECEIVED"


class PlanSource(StrEnum):
    AI = "AI"
    MANUAL = "MANUAL"


class Priority(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Decision(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class JobType(StrEnum):
    INSIGHTS_RUN = "INSIGHTS_RUN"
    CHAT_ANSWER = "CHAT_ANSWER"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class RunStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ChatRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class MessageStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


CATEGORY_ICONS = [
    "necklace", "earring", "ring", "bangle", "bracelet", "anklet",
    "chain", "pendant", "nosepin", "set", "coin", "other",
]
