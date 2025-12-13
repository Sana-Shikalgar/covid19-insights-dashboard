"""
Logging configuration module for the application.
Provides centralized logging setup and activity logging functionality.
"""

import logging
import os
import functools
from datetime import datetime
from pathlib import Path
from typing import Callable, Any


def setup_logging(log_level: str = "INFO", log_file: str = None) -> logging.Logger:
    """
    Set up logging configuration with file and console handlers.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional custom log file name
    
    Returns:
        Configured logger instance
    """
    # Create log directory if it doesn't exist
    log_dir = Path("log")
    log_dir.mkdir(exist_ok=True)
    
    # Generate log filename with timestamp if not provided
    if log_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"app_{timestamp}.log"
    
    log_path = log_dir / log_file
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s  [%(levelname)s]  %(name)s  (%(filename)s:%(lineno)d) - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler()  # Also log to console
        ],
        force=True  # Override any existing configuration
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_path}")
    
    return logger


def log_activity(message: str = None, log_level: str = "INFO"):
    """
    Decorator to log function execution activity.
    
    Args:
        message: Custom log message. If None, uses function name
        log_level: Log level for the activity
    
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = logging.getLogger(__name__)
            
            # Generate log message
            if message is None:
                log_msg = f"Executing function: {func.__name__}"
            else:
                log_msg = message
            
            # # Add function arguments to log if they exist
            # if args or kwargs:
            #     arg_info = []
            #     if args:
            #         arg_info.append(f"args={args}")
            #     if kwargs:
            #         arg_info.append(f"kwargs={kwargs}")
            #     log_msg += f"({', '.join(arg_info)})"
            
            # Log function start
            getattr(logger, log_level.lower())(f"START: {log_msg}")
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Log successful completion
                getattr(logger, log_level.lower())(f"SUCCESS: {func.__name__} completed successfully")
                
                return result
                
            except Exception as e:
                # Log error
                logger.error(f"ERROR: {func.__name__} failed with exception: {str(e)}")
                raise
                
        return wrapper
    return decorator


def log_user_action(action: str, details: dict = None) -> None:
    """
    Log user actions with structured format.
    
    Args:
        action: Description of the user action
        details: Optional dictionary of additional details
    """
    logger = logging.getLogger(__name__)
    
    log_message = f"USER_ACTION: {action}"
    
    if details:
        detail_str = ", ".join([f"{k}={v}" for k, v in details.items()])
        log_message += f" | Details: {detail_str}"
    
    logger.info(log_message)


def log_summary_generation(summary_type: str, input_file: str, output_file: str = None) -> None:
    """
    Specifically log summary generation activities.
    
    Args:
        summary_type: Type of summary being generated
        input_file: Input file path
        output_file: Output file path (if applicable)
    """
    details = {
        "summary_type": summary_type,
        "input_file": input_file
    }
    
    if output_file:
        details["output_file"] = output_file
    
    log_user_action("Summary Generation", details)


# Initialize default logger
logger = setup_logging()


# Example integration with existing functions
@log_activity("Processing data file", "INFO")
def process_data_file(file_path: str) -> dict:
    """Example function showing logging integration."""
    log_user_action("File Processing", {"file_path": file_path})
    
    # Simulate processing
    result = {"status": "processed", "file": file_path}
    
    return result


@log_activity("Generating summary report")
def generate_summary(data: dict, summary_type: str = "basic") -> str:
    """Example summary function with logging."""
    log_summary_generation(
        summary_type=summary_type,
        input_file=data.get("file", "unknown"),
        output_file=f"summary_{summary_type}.txt"
    )

    # Simulate summary generation
    summary = f"Summary of type {summary_type} generated"
    
    return summary