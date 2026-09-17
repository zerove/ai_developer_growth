#!/usr/bin/env python3
"""
Case Study Quality Analyzer

Performs deep quality analysis beyond structural validation:
- Content authenticity scoring
- Efficiency data credibility
- Insight specificity and actionability
- Cross-referencing with INDEX.md and MOC.md
- AI collaboration pattern detection
"""

from ._case_quality import CaseStudyQualityAnalyzer as CaseStudyQualityAnalyzer
from ._case_quality import QualityMetrics as QualityMetrics
from ._case_report import format_report as format_report
from ._case_report import main as main

__all__ = ["QualityMetrics", "CaseStudyQualityAnalyzer", "main", "format_report"]


if __name__ == "__main__":
    import sys

    sys.exit(main())
