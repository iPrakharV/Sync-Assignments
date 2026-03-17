from core.Google.GmailReader import GmailReader
from core.Google.GCalendarTasks import GCalendarTasks
from core.Todoist.TodoistTasks import TodoistTasks
from core.Constants import EMAIL, GCAL_SYNC, TODOIST_SYNC



if __name__ == '__main__':
    reader = GmailReader()
    reader.authenticate()

    reader.filter_messages(EMAIL)
    reader.break_down_email()

    # print("Tasks: ", reader.tasks)

    all_synced_tasks = []

    if GCAL_SYNC:
        calendar_tasks = GCalendarTasks(reader.tasks)
        calendar_tasks.authenticate()
        all_synced_tasks.extend(calendar_tasks.sync_tasks())
        print("Tasks synced to Google Calendar!")

    if TODOIST_SYNC:
        todoist_tasks = TodoistTasks(reader.tasks)
        all_synced_tasks.extend(todoist_tasks.sync_tasks())
        print("Tasks synced to Todoist!")

    if all_synced_tasks:
        print(f"SYNCED_TASKS_DATA: {', '.join(all_synced_tasks)}")
    else:
        print("SYNCED_TASKS_DATA: None")
