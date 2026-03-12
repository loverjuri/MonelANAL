"""WSGI entry for PythonAnywhere."""
import sys
from pathlib import Path

# Add project directory to path
project_dir = Path(__file__).resolve().parent
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

from app import application
