import logging
import sys

# Configure structured logging
def setup_logger():
    logger = logging.getLogger("SnapInsure")
    logger.setLevel(logging.INFO)

    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    
    # File handler for debugging
    file_handler = logging.FileHandler("backend_debug.log")
    file_handler.setLevel(logging.INFO)
    
    # Professional startup-grade format
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s',
        datefmt='%H:%M:%S'
    )
    handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    if not logger.handlers:
        logger.addHandler(handler)
        logger.addHandler(file_handler)
        
    return logger

logger = setup_logger()
