# Copyright (c) Opendatalab. All rights reserved.
import unittest
from types import SimpleNamespace

from mineru.cli.api_client import SubmitResponse, TaskStatusSnapshot
from mineru.cli.fast_api import AsyncParseTask, AsyncTaskManager, TASK_PENDING
from mineru.cli.router import RouterTaskRegistry, parse_submit_response


def _build_request_with_routes() -> SimpleNamespace:
    return SimpleNamespace(
        url_for=lambda name, task_id: f"http://testserver/{name}/{task_id}"
    )


def _build_async_task() -> AsyncParseTask:
    return AsyncParseTask(
        task_id="task-1",
        status=TASK_PENDING,
        backend="pipeline",
        file_names=["sample"],
        created_at="2026-06-08T00:00:00+00:00",
        output_dir="/tmp/output",
        parse_method="auto",
        lang_list=["en"],
        formula_enable=True,
        table_enable=True,
        image_analysis=True,
        server_url=None,
        return_md=True,
        return_middle_json=True,
        return_model_output=True,
        return_content_list=True,
        return_images=True,
        response_format_zip=False,
        return_original_file=False,
        client_side_output_generation=False,
        start_page_id=0,
        end_page_id=1,
        upload_names=["sample.pdf"],
        uploads=["/tmp/sample.pdf"],
    )


def test_async_task_status_payload_includes_progress_fields():
    task = _build_async_task()
    AsyncTaskManager.update_task_progress(
        task,
        progress_percent=42,
        progress_stage="analyzing",
        progress_message="Analyzing pipeline pages",
        progress_detail={"processed_pages": 21, "total_pages": 50},
    )

    payload = task.to_status_payload(_build_request_with_routes(), queued_ahead=2)

    assert payload["progress_percent"] == 42
    assert payload["progress_stage"] == "analyzing"
    assert payload["progress_message"] == "Analyzing pipeline pages"
    assert payload["progress_detail"] == {"processed_pages": 21, "total_pages": 50}
    assert payload["queued_ahead"] == 2


def test_parse_submit_response_preserves_optional_progress_fields():
    payload = parse_submit_response(
        {
            "task_id": "upstream-task",
            "status": "processing",
            "backend": "pipeline",
            "file_names": ["sample"],
            "created_at": "2026-06-08T00:00:00+00:00",
            "started_at": "2026-06-08T00:00:05+00:00",
            "completed_at": None,
            "error": None,
            "queued_ahead": 0,
            "progress_percent": 67,
            "progress_stage": "analyzing",
            "progress_message": "Analyzing pipeline pages",
            "progress_detail": {"processed_pages": 40, "total_pages": 60},
        }
    )

    assert payload["progress_percent"] == 67
    assert payload["progress_stage"] == "analyzing"
    assert payload["progress_message"] == "Analyzing pipeline pages"
    assert payload["progress_detail"] == {"processed_pages": 40, "total_pages": 60}


def test_client_dataclasses_accept_progress_fields():
    submit_response = SubmitResponse(
        task_id="task-1",
        status_url="http://test/status",
        result_url="http://test/result",
        progress_percent=5,
        progress_stage="preparing",
        progress_message="Preparing pipeline task",
        progress_detail={"processed_pages": 0, "total_pages": 10},
    )
    snapshot = TaskStatusSnapshot(
        status="processing",
        queued_ahead=0,
        progress_percent=45,
        progress_stage="analyzing",
        progress_message="Analyzing pipeline pages",
        progress_detail={"processed_pages": 9, "total_pages": 20},
    )

    assert submit_response.progress_stage == "preparing"
    assert snapshot.progress_percent == 45


class RouterTaskRegistryProgressTests(unittest.IsolatedAsyncioTestCase):
    async def test_router_registry_updates_progress_from_upstream_payload(self):
        registry = RouterTaskRegistry()
        task = await registry.register(
            upstream_server_id="server-1",
            upstream_base_url="http://upstream",
            upstream_task_id="upstream-task",
            backend="pipeline",
            file_names=["sample"],
            created_at="2026-06-08T00:00:00+00:00",
            status="pending",
            started_at=None,
            completed_at=None,
            error=None,
            queued_ahead=1,
            progress_percent=0,
            progress_stage="pending",
            progress_message="Task is pending",
            progress_detail=None,
        )

        updated = await registry.update_from_upstream_payload(
            task.task_id,
            {
                "status": "processing",
                "backend": "pipeline",
                "file_names": ["sample"],
                "created_at": "2026-06-08T00:00:00+00:00",
                "started_at": "2026-06-08T00:00:05+00:00",
                "completed_at": None,
                "error": None,
                "queued_ahead": 0,
                "progress_percent": 55,
                "progress_stage": "analyzing",
                "progress_message": "Analyzing pipeline pages",
                "progress_detail": {"processed_pages": 11, "total_pages": 20},
            },
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.progress_percent, 55)
        self.assertEqual(updated.progress_stage, "analyzing")
        self.assertEqual(updated.progress_message, "Analyzing pipeline pages")
        self.assertEqual(
            updated.progress_detail,
            {"processed_pages": 11, "total_pages": 20},
        )
