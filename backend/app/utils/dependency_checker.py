#!/usr/bin/env python3
"""
Dependency checker for PDF-OCR backend.

Verifies that all system dependencies are installed before application startup.
This prevents runtime errors from missing dependencies like Ghostscript.
"""
import sys
import subprocess
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


class DependencyError(Exception):
    """Raised when a required dependency is missing"""
    pass


def check_command_exists(command: str) -> bool:
    """Check if a command exists in PATH or common install locations"""
    # Try common installation paths first
    common_paths = [
        f"/opt/homebrew/bin/{command}",  # macOS Homebrew (Apple Silicon)
        f"/usr/local/bin/{command}",      # macOS Homebrew (Intel)
        f"/usr/bin/{command}",             # Linux
    ]
    
    for cmd_path in common_paths:
        try:
            subprocess.run(
                [cmd_path, "--version"],
                capture_output=True,
                check=True,
                timeout=5
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    # Fall back to checking PATH with which
    try:
        subprocess.run(
            ["which", command],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def check_python_package(package: str) -> bool:
    """Check if a Python package is installed"""
    try:
        __import__(package)
        return True
    except ImportError:
        return False


def get_ghostscript_install_instructions() -> str:
    """Get OS-specific Ghostscript installation instructions"""
    import platform
    os_name = platform.system()
    
    if os_name == "Darwin":  # macOS
        return """
    Install via Homebrew:
        brew install ghostscript
    """
    elif os_name == "Linux":
        return """
    Install via apt (Debian/Ubuntu):
        sudo apt-get install ghostscript
    
    Install via yum (RHEL/CentOS):
        sudo yum install ghostscript
    """
    else:
        return """
    See: https://www.ghostscript.com/download/gsdnld.html
    """


def get_poppler_install_instructions() -> str:
    """Get OS-specific Poppler installation instructions"""
    import platform
    os_name = platform.system()
    
    if os_name == "Darwin":  # macOS
        return """
    Install via Homebrew:
        brew install poppler
    """
    elif os_name == "Linux":
        return """
    Install via apt (Debian/Ubuntu):
        sudo apt-get install poppler-utils
    
    Install via yum (RHEL/CentOS):
        sudo yum install poppler-utils
    """
    else:
        return """
    See: https://poppler.freedesktop.org/
    """


def check_system_dependencies() -> List[Tuple[str, bool, str]]:
    """
    Check all required system dependencies.
    
    Returns:
        List of (dependency_name, is_installed, install_instructions) tuples
    """
    dependencies = []
    
    # Ghostscript (required by Camelot for PDF table extraction)
    gs_installed = check_command_exists("gs")
    dependencies.append((
        "Ghostscript",
        gs_installed,
        get_ghostscript_install_instructions() if not gs_installed else ""
    ))
    
    # Poppler (required by pdf2image for PDF to image conversion)
    poppler_installed = check_command_exists("pdftoppm")
    dependencies.append((
        "Poppler",
        poppler_installed,
        get_poppler_install_instructions() if not poppler_installed else ""
    ))
    
    return dependencies


def check_python_dependencies() -> List[Tuple[str, bool, str]]:
    """
    Check critical Python dependencies.
    
    Returns:
        List of (package_name, is_installed, install_instructions) tuples
    """
    dependencies = []
    
    critical_packages = [
        ("google.cloud.storage", "google-cloud-storage"),
        ("google.cloud.documentai", "google-cloud-documentai"),
        ("google.cloud.firestore", "google-cloud-firestore"),
        ("camelot", "camelot-py[cv]"),
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn[standard]"),
    ]
    
    for import_name, package_name in critical_packages:
        installed = check_python_package(import_name)
        dependencies.append((
            package_name,
            installed,
            f"pip install {package_name}" if not installed else ""
        ))
    
    return dependencies


def verify_dependencies(strict: bool = True) -> bool:
    """
    Verify all dependencies are installed.
    
    Args:
        strict: If True, raise exception on missing dependencies.
                If False, log warnings only.
    
    Returns:
        True if all dependencies are installed, False otherwise
    
    Raises:
        DependencyError: If strict=True and dependencies are missing
    """
    logger.info("Checking system dependencies...")
    
    system_deps = check_system_dependencies()
    python_deps = check_python_dependencies()
    
    missing_system = [(name, instructions) for name, installed, instructions in system_deps if not installed]
    missing_python = [(name, instructions) for name, installed, instructions in python_deps if not installed]
    
    all_installed = len(missing_system) == 0 and len(missing_python) == 0
    
    # Log results
    if all_installed:
        logger.info("✓ All dependencies are installed")
        return True
    
    # Report missing dependencies
    if missing_system:
        logger.error("✗ Missing system dependencies:")
        for name, instructions in missing_system:
            logger.error(f"  - {name}")
            if instructions:
                logger.error(f"    Installation:{instructions}")
    
    if missing_python:
        logger.error("✗ Missing Python packages:")
        for name, instructions in missing_python:
            logger.error(f"  - {name}")
            if instructions:
                logger.error(f"    Installation: {instructions}")
    
    if strict:
        raise DependencyError(
            f"Missing dependencies: {len(missing_system)} system, {len(missing_python)} Python packages. "
            "See logs above for installation instructions."
        )
    
    return False


if __name__ == "__main__":
    # Standalone check
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    
    try:
        verify_dependencies(strict=True)
        print("\n✓ All dependencies verified")
        sys.exit(0)
    except DependencyError as e:
        print(f"\n✗ Dependency check failed: {e}")
        sys.exit(1)
