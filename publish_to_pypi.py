#!/usr/bin/env python3
"""
Script to build and publish the IB API package to PyPI
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path


def clean_build_artifacts():
    """Remove old build artifacts"""
    print("Cleaning old build artifacts...")

    dirs_to_remove = ['build', 'dist', 'ibapi.egg-info', 'ibapi/ibapi.egg-info']
    for dir_name in dirs_to_remove:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"  Removing {dir_path}")
            shutil.rmtree(dir_path)


def build_package():
    """Build the package using setup.py"""
    print("\nBuilding package...")

    # Change to ibapi directory where setup.py is located
    os.chdir('ibapi')

    try:
        # Build source distribution and wheel
        subprocess.run(
            [sys.executable, 'setup.py', 'sdist', 'bdist_wheel'],
            check=True
        )
        print("Package built successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error building package: {e}")
        return False
    finally:
        # Change back to root
        os.chdir('..')


def check_pypi_credentials():
    """Check if PyPI credentials are available"""
    # Check for token in environment variable
    token = os.environ.get('PYPI_TOKEN') or os.environ.get('PYPI_API_TOKEN')

    if token:
        print("Found PyPI token in environment")
        return True

    # Check for .pypirc file
    pypirc = Path.home() / '.pypirc'
    if pypirc.exists():
        print(f"Found PyPI config at {pypirc}")
        return True

    print("WARNING: No PyPI credentials found!")
    print("Set PYPI_TOKEN environment variable or create ~/.pypirc")
    return False


def upload_to_pypi(test=False):
    """Upload the package to PyPI using twine"""
    print("\nUploading to PyPI...")

    # Check if twine is installed
    try:
        subprocess.run(
            [sys.executable, '-m', 'twine', '--version'],
            check=True,
            capture_output=True
        )
    except subprocess.CalledProcessError:
        print("Error: twine is not installed")
        print("Install it with: pip install twine")
        return False

    # Prepare upload command
    cmd = [sys.executable, '-m', 'twine', 'upload']

    if test:
        cmd.extend(['--repository', 'testpypi'])
        print("Uploading to Test PyPI...")
    else:
        print("Uploading to production PyPI...")

    # Check for token
    token = os.environ.get('PYPI_TOKEN') or os.environ.get('PYPI_API_TOKEN')
    if token:
        cmd.extend(['--username', '__token__', '--password', token])

    # Add distribution files
    cmd.append('ibapi/dist/*')

    try:
        # Use shell=True on Windows to handle wildcards
        if sys.platform == 'win32':
            # On Windows, manually expand the glob
            import glob
            dist_files = glob.glob('ibapi/dist/*')
            cmd = cmd[:-1] + dist_files

        subprocess.run(cmd, check=True)
        print("Successfully uploaded to PyPI!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error uploading to PyPI: {e}")
        return False


def get_package_version():
    """Get the current package version"""
    try:
        # Import from ibapi package
        sys.path.insert(0, 'ibapi')
        from ibapi import get_version_string
        version = get_version_string()
        sys.path.pop(0)
        return version
    except Exception as e:
        print(f"Error getting version: {e}")
        return None


def main():
    """Main function"""
    print("="*60)
    print("PyPI Publishing Script")
    print("="*60)

    # Get current version
    version = get_package_version()
    if version:
        print(f"\nCurrent version: {version}")
    else:
        print("\nWarning: Could not determine version")

    # Check if we're in the right directory
    if not Path('ibapi/setup.py').exists():
        print("Error: ibapi/setup.py not found!")
        print("Make sure you're in the project root directory")
        sys.exit(1)

    # Check for PyPI credentials
    if not check_pypi_credentials():
        print("\nContinuing without credentials (will prompt during upload)")

    # Clean old artifacts
    clean_build_artifacts()

    # Build the package
    if not build_package():
        print("\nFailed to build package")
        sys.exit(1)

    # Check if we should skip upload (for testing)
    skip_upload = os.environ.get('SKIP_PYPI_UPLOAD', '').lower() in ('1', 'true', 'yes')
    if skip_upload:
        print("\nSkipping PyPI upload (SKIP_PYPI_UPLOAD is set)")
        sys.exit(0)

    # Upload to PyPI
    test_mode = os.environ.get('PYPI_TEST', '').lower() in ('1', 'true', 'yes')
    if not upload_to_pypi(test=test_mode):
        print("\nFailed to upload to PyPI")
        sys.exit(1)

    print("\n" + "="*60)
    print("SUCCESS!")
    print(f"Version {version} published to PyPI")
    print("="*60)


if __name__ == "__main__":
    main()
