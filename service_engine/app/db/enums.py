from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class UsageOperationKind(StrEnum):
    MASK = "mask"
    TRANSLATE = "translate"
    INPAINT = "inpaint"


class UsageJobStatus(StrEnum):
    AUTHORIZED = "authorized"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CreditHoldStatus(StrEnum):
    HELD = "held"
    CAPTURED = "captured"
    RELEASED = "released"


class CreditLedgerEntryType(StrEnum):
    USAGE = "usage"
    ADJUSTMENT = "adjustment"

