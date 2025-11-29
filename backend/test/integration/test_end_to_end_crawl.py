import pytest
import time
import sys
import os
from flask import Flask

# Ensure backend directory is in sys.path so we can import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src import create_app
from src.crawl.view.crawler_view import _service

@pytest.fixture
def app():
    """Create Flask application for testing"""
    app = create_app()
    app.config.update({
        "TESTING": True,
    })
    yield app

@pytest.fixture
def client(app):
    """Create Flask test client"""
    return app.test_client()

@pytest.fixture(autouse=True)
def cleanup_service_state():
    """Clean up the singleton service state before and after each test"""
    # Clear internal state of the singleton service
    _service._tasks.clear()
    _service._paused_tasks.clear()
    _service._stopped_tasks.clear()
    _service._queue.clear()
    yield
    # Cleanup after test
    _service._tasks.clear()
    _service._paused_tasks.clear()
    _service._stopped_tasks.clear()
    _service._queue.clear()

from unittest.mock import patch

def test_end_to_end_crawl_success(client, requests_mock):
    """
    End-to-End Test: Complete Crawl Flow
    
    Scenario:
    1. User starts a crawl task via API for a mock website.
    2. The crawler visits Page 1, finds a link to Page 2.
    3. The crawler visits Page 2, finds no more links.
    4. The task completes.
    5. User verifies the status and results via API.
    """
    
    # Patch RobotFileParser to avoid urllib network calls
    with patch("src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser") as MockRobotParser:
        mock_parser_instance = MockRobotParser.return_value
        mock_parser_instance.can_fetch.return_value = True
        mock_parser_instance.read.return_value = None # Simulate successful read (or no-op)
    
        # 1. Setup Mock Website
        base_url = "http://mock-site.com"
        
        # Mock robots.txt (requests_mock handles requests, but we patched the parser anyway)
        # keeping this for consistency if we switch implementation later
        requests_mock.get(f"{base_url}/robots.txt", text="User-agent: *\nDisallow:")
        
        # Mock Page 1 (Start URL) - Links to Page 2
        page1_html = """
        <html>
            <head><title>Page 1 Title</title></head>
            <body>
                <h1>Welcome to Page 1</h1>
                <a href="/page2">Go to Page 2</a>
            </body>
        </html>
        """
        requests_mock.get(f"{base_url}/page1", text=page1_html, headers={'Content-Type': 'text/html'})
        
        # Mock Page 2 - No links
        page2_html = """
        <html>
            <head><title>Page 2 Title</title></head>
            <body>
                <h1>Content of Page 2</h1>
                <p>This is the end.</p>
            </body>
        </html>
        """
        requests_mock.get(f"{base_url}/page2", text=page2_html, headers={'Content-Type': 'text/html'})

        # 2. Start Crawl Task
        payload = {
            "start_url": f"{base_url}/page1",
            "strategy": "BFS",
            "max_depth": 2,
            "max_pages": 10,
            "interval": 0.01,  # Very fast interval for testing
            "allow_domains": ["mock-site.com"]
        }
        
        response = client.post("/api/crawl/start", json=payload)
        
        assert response.status_code == 201
        data = response.get_json()
        assert "task_id" in data
        task_id = data["task_id"]
        
        # 3. Poll Status until Completed
        # Since the crawler runs in a separate thread, we need to wait
        max_retries = 50  # 5 seconds max
        final_status = None
        
        for _ in range(max_retries):
            status_response = client.get(f"/api/crawl/status/{task_id}")
            assert status_response.status_code == 200
            status_data = status_response.get_json()
            
            status = status_data["status"]
            if status in ["COMPLETED", "FAILED", "STOPPED"]:
                final_status = status
                break
            
            time.sleep(0.1)
        
        # 4. Verify Completion
        if final_status != "COMPLETED":
            pytest.fail(f"Crawl task failed or timed out. Final status: {final_status}. Data: {status_data}")
        
        # 5. Verify Results
        # Check counts from API
        assert status_data["visited_count"] == 2
        assert status_data["result_count"] == 2
        assert status_data["queue_size"] == 0
        
        # 6. Verify Data Integrity (White-box check via singleton service)
        # Since API doesn't expose full results content, we verify internal state
        task = _service._tasks[task_id]
        results = task.results
        
        # Verify Page 1
        page1_result = next((r for r in results if r.url == f"{base_url}/page1"), None)
        assert page1_result is not None
        assert page1_result.title == "Page 1 Title"
        
        # Verify Page 2
        page2_result = next((r for r in results if r.url == f"{base_url}/page2"), None)
        assert page2_result is not None
        assert page2_result.title == "Page 2 Title"

def test_stop_crawl_task(client, requests_mock):
    """
    End-to-End Test: Stop Crawl Flow
    
    Scenario:
    1. Start a long-running task (infinite loop of pages or slow pages).
    2. Call Stop API.
    3. Verify status becomes STOPPED.
    """
    base_url = "http://mock-site.com"
    requests_mock.get(f"{base_url}/robots.txt", text="User-agent: *\nDisallow:")
    
    # Infinite chain of pages: page1 -> page1 (loop) or just slow response
    # Using a loop to ensure it keeps running until stopped
    page1_html = '<html><body><a href="/page1">Loop</a></body></html>'
    requests_mock.get(f"{base_url}/page1", text=page1_html, headers={'Content-Type': 'text/html'})
    
    # Start Task
    payload = {
        "start_url": f"{base_url}/page1",
        "interval": 0.1
    }
    response = client.post("/api/crawl/start", json=payload)
    task_id = response.get_json()["task_id"]
    
    # Let it run for a split second
    time.sleep(0.2)
    
    # Stop Task
    stop_response = client.post(f"/api/crawl/stop/{task_id}")
    assert stop_response.status_code == 200
    
    # Poll for STOPPED status
    max_retries = 20
    for _ in range(max_retries):
        status_response = client.get(f"/api/crawl/status/{task_id}")
        status = status_response.get_json()["status"]
        if status == "STOPPED":
            break
        time.sleep(0.1)
    else:
        pytest.fail(f"Task did not stop in time. Current status: {status}")
    
    # Verify it actually stopped
    final_status = client.get(f"/api/crawl/status/{task_id}").get_json()["status"]
    assert final_status == "STOPPED"
