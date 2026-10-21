from __future__ import annotations

import re
import datetime
from dataclasses import dataclass
from typing import Optional

EXAM_PATTERN = re.compile(r'\b(exam|test|midterm|final)\b', re.IGNORECASE)


@dataclass
class Assignment:
    name: str                       # "Exam 2- Requires Respondus LockDown Browser"
    course_code: str                # "ECON 20101"
    course_title: str               # "Intro To Microeconomics"
    category: str                   # Brightspace section heading: "Quiz", "Assignment", ...
    due: datetime.datetime          # timezone-aware
    due_text: str                   # due date exactly as written in the email
    url: Optional[str] = None       # direct link to the item
    list_url: Optional[str] = None  # "Go to Quiz >>" link
    email_date: Optional[datetime.date] = None

    @property
    def key(self):
        return f"{self.course_code}|{self.name}"

    @property
    def kind(self):
        if EXAM_PATTERN.search(self.name):
            return 'exam'
        return self.category.lower()

    def description(self):
        lines = [f"**{self.course_code} — {self.course_title}** · {self.category}",
                 f"Due: {self.due_text}"]
        if self.url:
            lines.append(f"[Open in Brightspace]({self.url})")
        if self.list_url:
            lines.append(f"[All {self.category.lower()} items]({self.list_url})")
        if self.email_date:
            lines.append(f"_From the Brightspace activity summary of {self.email_date:%b %d, %Y}_")
        return '\n'.join(lines)
