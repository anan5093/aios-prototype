#!/usr/bin/env python3
"""
upload_benchmark.py — Programmatic script to push and run your task on Kaggle Benchmarks.
"""

from kaggle.api.kaggle_api_extended import KaggleApi


def upload_and_run_benchmark():
    # 1. Initialize and authenticate the Kaggle API
    print("Initializing and authenticating Kaggle API...")
    api = KaggleApi()
    api.authenticate()

    # Define task names and filenames
    # (Note: task name must match the name defined in the @task decorator in the file)
    task_slug = "what-is-kaggle"
    task_file = "example_task.py"  # Replace with your target benchmark task file

    # 2. Push the task to Kaggle Benchmarks (uploads the source code)
    print(f"Uploading '{task_file}' as task '{task_slug}'...")
    api.benchmarks_tasks_push_cli(
        task=task_slug,
        file=task_file,
        wait=True,
    )

    # 3. Trigger the remote execution against the models
    print(f"Triggering execution of '{task_slug}' on Kaggle Benchmarks...")
    api.benchmarks_tasks_run_cli(
        task=task_slug,
        wait=True,
    )
    print(
        "\n✅ Success! The benchmark run has completed. Results are uploaded and recorded on your Kaggle Benchmarks web page."
    )


if __name__ == "__main__":
    upload_and_run_benchmark()
