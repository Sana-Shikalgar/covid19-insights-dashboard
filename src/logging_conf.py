"""
Logging configuration module for the application.
Provides centralized logging setup and activity logging decorators.
"""

import logging
import functools
from datetime import datetime
from pathlib import Path
from typing import Callable, Any, Optional


# ==================== LOGGING SETUP ====================

def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """
    Set up application-wide logging configuration.
    
    Creates log directory and configures both file and console handlers.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Custom log filename (default: app_TIMESTAMP.log)
    
    Returns:
        Configured logger instance
    """
    # Create log directory
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
            # logging.StreamHandler()  # Console output
        ],
        force=True  # Override existing configuration
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized: {log_path}")
    
    return logger


# ==================== ACTIVITY LOGGING DECORATOR ====================

def log_activity(message: Optional[str] = None, log_level: str = "INFO"):
    """
    Decorator to log function execution lifecycle.
    
    Logs:
    - Function start
    - Successful completion
    - Errors with exception details
    
    Args:
        message: Custom log message (default: function name)
        log_level: Log level for the activity
    
    Returns:
        Decorated function
    
    Example:
        @log_activity("Processing data")
        def process_data(df):
            return df.clean()
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = logging.getLogger(__name__)
            
            # Generate log message
            log_msg = message if message else f"Executing {func.__name__}"
            
            # Log function start
            getattr(logger, log_level.lower())(f"START: {log_msg}")
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Log successful completion
                getattr(logger, log_level.lower())(f"SUCCESS: {func.__name__} completed")
                
                return result
            
            except Exception as e:
                # Log error with exception details
                logger.error(f"ERROR: {func.__name__} failed - {str(e)}")
                raise
        
        return wrapper
    return decorator


# ==================== USER ACTION LOGGING ====================

def log_user_action(action: str, details: Optional[dict] = None) -> None:
    """
    Log user actions with structured format.
    
    Use this for tracking user interactions in the GUI.
    
    Args:
        action: Description of user action
        details: Optional dictionary of additional context
    
    Example:
        log_user_action("File uploaded", {"filename": "data.csv", "size": 1024})
    """
    logger = logging.getLogger(__name__)
    
    log_message = f"USER_ACTION: {action}"
    
    if details:
        detail_str = ", ".join([f"{k}={v}" for k, v in details.items()])
        log_message += f" | {detail_str}"
    
    logger.info(log_message)


# ==================== SPECIALIZED LOGGING ====================

def log_summary_generation(
    summary_type: str,
    input_file: str,
    output_file: Optional[str] = None
) -> None:
    """
    Log summary/report generation activities.
    
    NOTE: This function may be redundant with log_user_action().
    Consider using log_user_action() directly instead.
    
    Args:
        summary_type: Type of summary generated
        input_file: Input file path
        output_file: Output file path (optional)
    """
    details = {
        "summary_type": summary_type,
        "input_file": input_file
    }
    
    if output_file:
        details["output_file"] = output_file
    
    log_user_action("Summary Generation", details)


# ==================== INITIALIZE DEFAULT LOGGER ====================

# Create default logger on module import
logger = setup_logging()


# ==================== EXAMPLE FUNCTIONS ====================
# NOTE: These example functions are not used in the application.
# Consider removing if not needed for documentation purposes.

@log_activity("Processing data file", "INFO")
def process_data_file(file_path: str) -> dict:
    """
    Example function demonstrating logging integration.
    
    NOTE: This is an example/documentation function.
    Not used in actual application code.
    """
    log_user_action("File Processing", {"file_path": file_path})
    result = {"status": "processed", "file": file_path}
    return result


@log_activity("Generating summary report")
def generate_summary(data: dict, summary_type: str = "basic") -> str:
    """
    Example summary function with logging.
    
    NOTE: This is an example/documentation function.
    Not used in actual application code.
    """
    log_summary_generation(
        summary_type=summary_type,
        input_file=data.get("file", "unknown"),
        output_file=f"summary_{summary_type}.txt"
    )
    summary = f"Summary of type {summary_type} generated"
    return summary