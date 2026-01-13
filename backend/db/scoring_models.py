"""
Scoring Models for JarlPM
RICE and MoSCoW scoring frameworks
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class MoSCoWScore(str, Enum):
    """MoSCoW prioritization categories"""
    MUST_HAVE = "must_have"
    SHOULD_HAVE = "should_have"
    COULD_HAVE = "could_have"
    WONT_HAVE = "wont_have"


class RICEScore(BaseModel):
    """
    RICE Score components
    Total = (Reach * Impact * Confidence) / Effort
    """
    reach: int = Field(ge=1, le=10, description="Users affected per time period (1-10 scale)")
    impact: float = Field(description="Impact per user: 0.25 (minimal), 0.5 (low), 1 (medium), 2 (high), 3 (massive)")
    confidence: float = Field(description="Confidence in estimates: 0.5 (low), 0.8 (medium), 1.0 (high)")
    effort: float = Field(ge=0.5, le=10, description="Person-months of effort (0.5-10)")
    
    @property
    def total(self) -> float:
        """Calculate RICE score"""
        if self.effort <= 0:
            return 0
        return round((self.reach * self.impact * self.confidence) / self.effort, 2)
    
    def to_dict(self) -> dict:
        return {
            "reach": self.reach,
            "impact": self.impact,
            "confidence": self.confidence,
            "effort": self.effort,
            "total": self.total
        }


# Valid values for RICE components
IMPACT_VALUES = [0.25, 0.5, 1.0, 2.0, 3.0]
CONFIDENCE_VALUES = [0.5, 0.8, 1.0]

IMPACT_LABELS = {
    0.25: "Minimal",
    0.5: "Low",
    1.0: "Medium",
    2.0: "High",
    3.0: "Massive"
}

CONFIDENCE_LABELS = {
    0.5: "Low",
    0.8: "Medium",
    1.0: "High"
}

MOSCOW_LABELS = {
    MoSCoWScore.MUST_HAVE: "Must Have",
    MoSCoWScore.SHOULD_HAVE: "Should Have",
    MoSCoWScore.COULD_HAVE: "Could Have",
    MoSCoWScore.WONT_HAVE: "Won't Have"
}
