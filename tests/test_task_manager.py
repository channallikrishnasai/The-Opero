from core.task_manager import TaskJournal, TaskState


def test_task_journal_tracks_terminal_lifecycle():
    journal = TaskJournal(max_records=10)
    task = journal.create("Research current jobs", metadata={"action": "web_search"})
    assert journal.start(task.task_id, "Searching") is not None
    finished = journal.succeed(task.task_id, "Found 3 matches")
    assert finished is not None
    assert finished.state is TaskState.SUCCEEDED
    assert journal.cancel(task.task_id) is None
    assert journal.recent()[0]["result"] == "Found 3 matches"


def test_task_journal_records_failure():
    journal = TaskJournal()
    task = journal.create("Build website")
    journal.start(task.task_id)
    failed = journal.fail(task.task_id, "Build command failed")
    assert failed is not None
    assert failed.state is TaskState.FAILED
    assert failed.error == "Build command failed"
