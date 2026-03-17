import os
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("SYNC_EMAIL", "example@example.com")

GCAL_SYNC = os.getenv("GCAL_SYNC", "False").lower() in ("true", "1", "t")
TODOIST_SYNC = os.getenv("TODOIST_SYNC", "True").lower() in ("true", "1", "t")

# TODOIST
PROJECT_NAME = os.getenv("TODOIST_PROJECT_NAME", "ToDo")
SECTION_NAME = os.getenv("TODOIST_SECTION_NAME", "General")
ASSIGNEE_ID = os.getenv("TODOIST_ASSIGNEE_ID", None)
