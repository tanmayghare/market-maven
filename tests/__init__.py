"""
Test suite for the AI Stock Market Agent.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Test configuration
TEST_ENVIRONMENT = "test"
os.environ["ENVIRONMENT"] = TEST_ENVIRONMENT
os.environ["ENABLE_DRY_RUN"] = "true"
os.environ["LOG_LEVEL"] = "DEBUG"

# Mock API keys for testing
os.environ["ALPHA_VANTAGE_API_KEY"] = "test_alpha_vantage_key"
os.environ["GOOGLE_API_KEY"] = "test_google_key" 