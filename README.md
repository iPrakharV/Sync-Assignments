# Sync Assignments 📚

## Thank You for Visiting! &emsp; ![Visitor Count](https://visitor-badge.laobi.icu/badge?page_id=abhisaranand.SyncAssignments)

**Sync Assignments** is a tool designed for Purdue University students to seamlessly integrate their academic assignments from Brightspace into their personal Google Calendar and Google Tasks. This automation tool scans your Gmail for emails related to course assignments, extracts key information, and ensures your calendar and tasks are up-to-date with your academic deadlines.

## 🌟 Features

- **Brightspace Integration**: Specifically tuned for Purdue University students, focusing on assignment emails from Brightspace.
- **Email Parsing**: Automatically parses assignment details from Gmail, reducing manual entry.
- **Calendar Sync**: Creates Google Calendar events for each assignment with due dates and reminders.
- **Task Sync**: Adds assignments to Google Tasks with comprehensive details.
- **Todoist Integration**: Seamlessly integrates with Todoist, allowing for efficient task management alongside Google Tasks.
- **Duplication Avoidance**: Intelligent checks to prevent duplicate calendar events and tasks.
- **Log Management**: Maintains a detailed log of synced assignments, ensuring transparency and control.
- **Automated Cleanup**: Removes past-due assignments from logs to keep your list current.

## 🔧 Languages and Tools Used

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Google API](https://img.shields.io/badge/Google%20API-4285F4?style=for-the-badge&logo=google&logoColor=white)
![JSON](https://img.shields.io/badge/JSON-000000?style=for-the-badge&logo=json&logoColor=white)
![Gmail](https://img.shields.io/badge/Gmail-D14836?style=for-the-badge&logo=gmail&logoColor=white)
![GoogleCalendar](https://img.shields.io/badge/Google%20Calendar-4285F4?style=for-the-badge&logo=google-calendar&logoColor=white%60)
![Todoist](https://img.shields.io/badge/Todoist-EF8E1F?style=for-the-badge&logo=todoist&logoColor=white%60)

## 🚀 Getting Started

### Prerequisites

- Python 3.6+
- Pip for Python package management
- Google Cloud Platform account for API access

### Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/AbhisarAnand/Sync-Assignments
    cd SyncAssignments
    ```

2. Install required Python packages:
    ```bash
    pip3 install -r requirements.txt
    ```

3. Follow [Google's guide](https://developers.google.com/workspace/guides/create-credentials) to set up `client_secret.json` for Gmail and Google Calendar API.

### Setup

1. Place your `client_secret.json` in the `Google/` folder.
2. Put your Todoist API token in `Todoist/Token.json` as `{"API_Token": "..."}`.
3. Copy `config.example.json` to `config.json` and fill it in:
   - `senders`: the address(es) your Brightspace summaries come from (e.g. your school email, if you forward them to Gmail).
   - `todoist.project` / `todoist.section`: where tasks go.
   - `todoist.course_labels`: rename course labels, e.g. `{"CS 36400": "Databases"}`. Courses not listed get labels like `CS36400`.
   - `todoist.label_colors`: optional colors for any label (Todoist color names like `blue`, `red`, `grape`).
   - `notifications`: `always`, `changes`, `errors` or `never`.

`config.json`, tokens and state files are gitignored.

### Usage

```bash
.venv/bin/python Main.py              # sync now (first run opens a browser to sign in to Google)
.venv/bin/python Main.py --dry-run    # show what would change, touch nothing
.venv/bin/python Main.py --lookback 14
```

### Run it automatically (macOS)

```bash
scripts/install_schedule.sh          # runs daily at 8:00 and 20:00
scripts/install_schedule.sh 7 13 21  # custom hours
scripts/install_schedule.sh --remove
```

If the Mac is asleep at a scheduled time, the job runs when it wakes. Scheduled runs never open a browser: if Google needs you to sign in again, you get a notification telling you to run `Main.py` by hand once. Logs are in `logs/sync.log`.

## 🛠️ How It Works

- **GmailReader**: Finds Brightspace "Activity summary" emails from the last few days and parses every item with a due date: name, course, category (Quiz, Assignment...), due time with timezone, and the Brightspace links. Grades and content updates are ignored. When an assignment appears in several emails, the newest one wins.
- **TodoistTasks**: Creates a task per assignment with a course label, a type label (`exam`, `quiz`, `assignment`), the exact due time, and a description with links back to Brightspace. Each assignment is tracked by course + name and its Todoist task ID (`Todoist/todoist_state.json`), so:
  - if a professor moves a due date, the existing task is updated instead of duplicated;
  - tasks you complete or delete are never re-created;
  - two courses can both have a "Quiz 1".
- **Summary**: After each run you get a macOS notification like "Todoist: 2 new, 1 updated · Due soon: Exam 2 (tomorrow 11:59 PM)".
- **GCalendarTasks**: Optional Google Tasks sync (`google_tasks.enabled` in config).

## 📄 License

This project is licensed under the MIT License - see the `LICENSE` file for details.

## 📧 Contact

For queries or support, please email us at [abhisar.muz@gmail.com](mailto:abhisar.muz@gmail.com).

---

*Proudly created for Purdue University students by Abhisar Anand.*
