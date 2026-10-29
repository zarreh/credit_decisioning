"""The champion model: L2 logistic regression with cross-fitted sigmoid calibration.

``ensemble=False`` keeps one logistic model fitted on all training rows, so reasons
come from exactly the coefficients that score the applicant (D-B2-6, C7). Sigmoid
calibration is a monotone map of the logit, so ranking reasons in logit space is
faithful to the calibrated probability as long as the slope keeps its sign; this is
checked at fit time.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from credit.pipeline.attributes import MODEL_CATEGORICAL, MODEL_FEATURES, MODEL_NUMERIC
from credit.pipeline.policy import THRESHOLD

SEED = 20261029
MIN_REFERENCE_ROWS = 50


class ModelValidationError(RuntimeError):
    """A fitted model violates an assumption the reasons depend on."""


def preprocess() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), list(MODEL_CATEGORICAL)),
            ("num", StandardScaler(), list(MODEL_NUMERIC)),
        ],
        verbose_feature_names_out=False,
    )


def champion() -> CalibratedClassifierCV:
    base = Pipeline([("prep", preprocess()), ("lr", LogisticRegression(C=1.0, max_iter=2000))])
    return CalibratedClassifierCV(base, method="sigmoid", cv=5, ensemble=False)


def challenger() -> CalibratedClassifierCV:
    base = Pipeline(
        [
            ("prep", preprocess()),
            ("hgb", HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, random_state=SEED)),
        ]
    )
    return CalibratedClassifierCV(base, method="sigmoid", cv=5, ensemble=False)


@dataclass
class CreditModel:
    """A fitted champion plus the frozen attribution reference."""

    calibrated: CalibratedClassifierCV
    version: str
    reference: np.ndarray = field(repr=False)
    reference_kind: str
    reference_n: int

    @property
    def pipeline(self) -> Pipeline:
        return self.calibrated.calibrated_classifiers_[0].estimator

    def p_bad(self, frame: pd.DataFrame) -> np.ndarray:
        return self.calibrated.predict_proba(frame[list(MODEL_FEATURES)])[:, 1]  # type: ignore[no-any-return]

    def transformed(self, frame: pd.DataFrame) -> np.ndarray:
        return self.pipeline.named_steps["prep"].transform(frame[list(MODEL_FEATURES)])  # type: ignore[no-any-return]

    def logit(self, frame: pd.DataFrame) -> np.ndarray:
        return self.pipeline.decision_function(frame[list(MODEL_FEATURES)])  # type: ignore[no-any-return]

    def coefficients(self) -> np.ndarray:
        return self.pipeline.named_steps["lr"].coef_[0]  # type: ignore[no-any-return]

    def feature_names(self) -> list[str]:
        return list(self.pipeline.named_steps["prep"].get_feature_names_out())


def _assert_monotone(calibrated: CalibratedClassifierCV) -> None:
    # sklearn's sigmoid is 1 / (1 + exp(a * f + b)); increasing in f requires a < 0.
    slope = calibrated.calibrated_classifiers_[0].calibrators[0].a_
    if not slope < 0:
        raise ModelValidationError(f"calibration slope {slope} is not monotone increasing")


def fit_champion(train: pd.DataFrame, version: str) -> CreditModel:
    """Fit on ``train`` only and freeze the attribution reference from ``train`` only.

    Reference: mean transformed features of training applicants the model would
    approve. If fewer than ``MIN_REFERENCE_ROWS`` qualify, fall back to training
    applicants with a good outcome (ADR 0010).
    """
    calibrated = champion().fit(train[list(MODEL_FEATURES)], train["bad"])
    _assert_monotone(calibrated)
    model = CreditModel(calibrated, version, np.empty(0), "", 0)
    approved = model.p_bad(train) < THRESHOLD
    if approved.sum() >= MIN_REFERENCE_ROWS:
        rows, kind = train[approved], "approve_band_training_mean"
    else:
        rows, kind = train[train["bad"] == 0], "good_outcome_training_mean"
    model.reference = model.transformed(rows).mean(axis=0)
    model.reference_kind, model.reference_n = kind, int(len(rows))
    return model
