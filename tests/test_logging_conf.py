import pytest
import logging
from pathlib import Path
from src.logging_conf import setup_logging, log_activity, log_user_action, log_summary_generation, process_data_file, generate_summary

# --------------------------
# Test setup_logging
# --------------------------
def test_setup_logging_creates_logger(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    monkeypatch.chdir(tmp_path)  # Change working dir to tmp_path
    
    logger = setup_logging(log_level="DEBUG")
    
    assert isinstance(logger, logging.Logger)
    assert logger.getEffectiveLevel() == logging.DEBUG
    # The log directory should exist
    assert log_dir.exists() or (tmp_path / "logs").exists()

def test_setup_logging_custom_log_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_file_name = "custom_log.log"
    logger = setup_logging(log_file=log_file_name)
    
    log_path = Path("logs") / log_file_name
    assert log_path.parent.exists()
    # Log file path should match
    root_logger = logging.getLogger()
    file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
    
        # Fix 1: Assert using RESOLVED absolute path
    expected_path = (tmp_path / "logs" / log_file_name).resolve()
    actual_paths = [Path(h.baseFilename).resolve() for h in file_handlers]
    assert expected_path in actual_paths, f"Expected {expected_path}, got {actual_paths}"
    
    # Fix 2: Verify directory created
    assert (tmp_path / "logs").exists()

# --------------------------
# Test log_activity decorator
# --------------------------
def test_log_activity_decorator_executes_function():
    @log_activity("Test function execution", "INFO")
    def dummy(a, b):
        return a + b
    
    result = dummy(2, 3)
    assert result == 5  # Ensure the function returns correct result

def test_log_activity_decorator_handles_exception():
    @log_activity("Test exception handling", "ERROR")
    def faulty():
        raise ValueError("Test error")
    
    with pytest.raises(ValueError, match="Test error"):
        faulty()  # Should raise the exception but still log it

# --------------------------
# Test log_user_action
# --------------------------
def test_log_user_action_runs_without_error(caplog):
    caplog.set_level(logging.INFO)
    
    log_user_action("Test Action")
    assert any("USER_ACTION: Test Action" in rec.message for rec in caplog.records)

def test_log_user_action_with_details(caplog):
    caplog.set_level(logging.INFO)
    
    log_user_action("Action with details", {"key": "value"})
    assert any("USER_ACTION:" in rec.message for rec in caplog.records)

# --------------------------
# Test log_summary_generation
# --------------------------
def test_log_summary_generation_logs_info(caplog):
    caplog.set_level(logging.INFO)
    
    log_summary_generation("basic", "input.txt", "output.txt")
    assert any("USER_ACTION: Summary Generation" in rec.message for rec in caplog.records)
    assert any("summary_type=basic" in rec.message for rec in caplog.records)

# --------------------------
# Test example integration functions
# --------------------------
def test_process_data_file_returns_dict(caplog):
    caplog.set_level(logging.INFO)
    
    result = process_data_file("file.txt")
    assert result == {"status": "processed", "file": "file.txt"}
    assert any("START: Processing data file" in rec.message for rec in caplog.records)
    assert any("SUCCESS:" in rec.message for rec in caplog.records)

def test_generate_summary_returns_string(caplog):
    caplog.set_level(logging.INFO)
    
    data = {"file": "file.txt"}
    summary = generate_summary(data, summary_type="detailed")
    assert summary == "Summary of type detailed generated"
    assert any("USER_ACTION: Summary Generation" in rec.message for rec in caplog.records)
