from contextlib import contextmanager

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn


@contextmanager
def progress_steps(label: str, total_steps: int):
    """Simple stage-based progress with clear step labels."""
    columns = [SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), TimeElapsedColumn()]
    with Progress(*columns, transient=False) as progress:
        task_id = progress.add_task(label, total=total_steps)
        yield progress, task_id
        progress.update(task_id, completed=progress.tasks[task_id].total)
