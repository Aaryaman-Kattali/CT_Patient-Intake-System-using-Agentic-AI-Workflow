"""Terms the system must never use on its own (principle P9: administrative, not clinical)."""

import re

# Words that claim or name a condition. Banned in every fixed text, including option labels.
CONDITION_CLAIMS = re.compile(
    r"\b(diagnos\w*|disorder\w*|syndrome\w*|symptom\w*|prognos\w*|patholog\w*|"
    r"has autism|is autistic|suffer\w*)\b"
    r"|\b[A-TV-Z]\d{2}\.\d{1,4}\b",  # ICD-10 style codes such as F84.0
    re.IGNORECASE,
)

# Wider list for text the system writes itself in staff outputs (SOAP-style sections).
# A user's own chosen or typed value (e.g. "An autism assessment") is quoted as theirs,
# with its source field cited, and is not checked against this list.
CLINICAL_TERMS = re.compile(
    CONDITION_CLAIMS.pattern + r"|\b(assessment|plan of care|treatment plan|impression)\b",
    re.IGNORECASE,
)
