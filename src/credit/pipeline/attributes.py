"""The UCI Statlog (German Credit) codebook, and which attributes the model may use.

Codes and labels follow the UCI dataset page (id 144). Protected or prohibited-basis
attributes are kept for the fairness audit but never reach the model (D-B2-4).
"""

from __future__ import annotations

from typing import Final

CATEGORY_LABELS: Final[dict[str, dict[str, str]]] = {
    "checking_status": {
        "A11": "below 0 DM",
        "A12": "0 to 200 DM",
        "A13": "200 DM or more, or salary assigned for at least 1 year",
        "A14": "no checking account",
    },
    "credit_history": {
        "A30": "no credits taken, or all credits paid back duly",
        "A31": "all credits at this bank paid back duly",
        "A32": "existing credits paid back duly so far",
        "A33": "delay in paying off in the past",
        "A34": "critical account, or other credits existing at other banks",
    },
    "purpose": {
        "A40": "new car",
        "A41": "used car",
        "A42": "furniture or equipment",
        "A43": "radio or television",
        "A44": "domestic appliances",
        "A45": "repairs",
        "A46": "education",
        "A47": "vacation",
        "A48": "retraining",
        "A49": "business",
        "A410": "other",
    },
    "savings": {
        "A61": "below 100 DM",
        "A62": "100 to 500 DM",
        "A63": "500 to 1,000 DM",
        "A64": "1,000 DM or more",
        "A65": "unknown, or no savings account",
    },
    "employment_since": {
        "A71": "unemployed",
        "A72": "less than 1 year",
        "A73": "1 to 4 years",
        "A74": "4 to 7 years",
        "A75": "7 years or more",
    },
    "personal_status_sex": {
        "A91": "male: divorced or separated",
        "A92": "female: divorced, separated or married",
        "A93": "male: single",
        "A94": "male: married or widowed",
        "A95": "female: single",
    },
    "other_debtors": {
        "A101": "none",
        "A102": "co-applicant",
        "A103": "guarantor",
    },
    "property": {
        "A121": "real estate",
        "A122": "building society savings or life insurance",
        "A123": "car or other property",
        "A124": "unknown, or no property",
    },
    "other_installment_plans": {"A141": "bank", "A142": "stores", "A143": "none"},
    "housing": {"A151": "rent", "A152": "own", "A153": "for free"},
    "job": {
        "A171": "unemployed or unskilled, non-resident",
        "A172": "unskilled, resident",
        "A173": "skilled employee or official",
        "A174": "management, self-employed, or highly qualified",
    },
    "telephone": {"A191": "none", "A192": "yes, registered in the applicant's name"},
    "foreign_worker": {"A201": "yes", "A202": "no"},
}

# Column order of german.data (attributes 1-20, then the class).
COLUMNS: Final[tuple[str, ...]] = (
    "checking_status",
    "duration_months",
    "credit_history",
    "purpose",
    "credit_amount",
    "savings",
    "employment_since",
    "installment_rate",
    "personal_status_sex",
    "other_debtors",
    "residence_since",
    "property",
    "age_years",
    "other_installment_plans",
    "housing",
    "existing_credits",
    "job",
    "dependents",
    "telephone",
    "foreign_worker",
)

NUMERIC: Final[tuple[str, ...]] = (
    "duration_months",
    "credit_amount",
    "installment_rate",
    "residence_since",
    "age_years",
    "existing_credits",
    "dependents",
)

# Never model inputs. Kept only for the audit (age, sex, foreign worker) or dropped
# outright (telephone). See docs/decisions/0004-protected-attributes.md.
EXCLUDED: Final[tuple[str, ...]] = (
    "personal_status_sex",
    "age_years",
    "foreign_worker",
    "telephone",
)

MODEL_FEATURES: Final[tuple[str, ...]] = tuple(c for c in COLUMNS if c not in EXCLUDED)
MODEL_NUMERIC: Final[tuple[str, ...]] = tuple(c for c in NUMERIC if c in MODEL_FEATURES)
MODEL_CATEGORICAL: Final[tuple[str, ...]] = tuple(c for c in MODEL_FEATURES if c not in MODEL_NUMERIC)

TARGET: Final[str] = "bad"

FIELD_NAMES: Final[dict[str, str]] = {
    "checking_status": "Checking account",
    "duration_months": "Loan term (months)",
    "credit_history": "Credit history",
    "purpose": "Purpose",
    "credit_amount": "Amount requested (DM)",
    "savings": "Savings or bonds",
    "employment_since": "Present employment since",
    "installment_rate": "Instalment rate band (1-4)",
    "personal_status_sex": "Personal status and sex",
    "other_debtors": "Other debtors or guarantors",
    "residence_since": "Present residence band (1-4)",
    "property": "Property",
    "age_years": "Age (years)",
    "other_installment_plans": "Other instalment plans",
    "housing": "Housing",
    "existing_credits": "Existing credits at this bank",
    "job": "Job",
    "dependents": "People supported",
    "telephone": "Telephone",
    "foreign_worker": "Foreign worker",
}


def label(attribute: str, code: str) -> str:
    """Readable label for a category code; raises on an unknown code."""
    return CATEGORY_LABELS[attribute][code]
