#!/usr/bin/env python3
"""
Main orchestrator for checking and updating IB API versions
Runs weekly to check for new releases and publish to PyPI
"""
import json
import os
import re
import subprocess
import sys

# Import from our other scripts
from get_download_url import extract_download_info, filter_mac_unix_downloads


def get_existing_tags():
    """Get all existing git tags"""
    try:
        result = subprocess.run(
            ['git', 'tag', '-l'],
            capture_output=True,
            text=True,
            check=True
        )
        tags = [tag.strip() for tag in result.stdout.strip().split('\n') if tag.strip()]
        return set(tags)
    except subprocess.CalledProcessError as e:
        print(f"Error getting git tags: {e}")
        return set()


def version_to_tag(version):
    """Convert version string to git tag format

    Version string from get_download_url.py is formatted like "10.37.02" or "10.40.01"
    We add a 'v' prefix to create tags like "v10.37.02" or "v10.40.01"
    """
    return f"v{version}"


def parse_version_number(version_str):
    """Parse version string like '10.37' into tuple (10, 37, 0)"""
    parts = version_str.split('.')
    major = int(parts[0])
    minor = int(parts[1]) if len(parts) > 1 else 0
    micro = int(parts[2]) if len(parts) > 2 else 0
    return (major, minor, micro)


def find_new_versions(downloads, existing_tags):
    """Find versions that haven't been processed yet"""
    new_versions = []

    for dl in downloads:
        version = dl['version']
        if not version:
            continue

        tag = version_to_tag(version)
        if tag not in existing_tags:
            new_versions.append(dl)
            print(f"Found new version: {version} (tag {tag} not found)")
        else:
            print(f"Version {version} already exists (tag {tag})")

    return new_versions


def sort_versions(downloads):
    """Sort downloads by version number (oldest first)"""
    def version_key(dl):
        try:
            return parse_version_number(dl['version'])
        except:
            return (0, 0, 0)

    return sorted(downloads, key=version_key)


def get_highest_version(downloads):
    """Find the highest version number (Latest)"""
    if not downloads:
        return None

    sorted_downloads = sort_versions(downloads)
    return sorted_downloads[-1]['version']  # Last one is highest


def is_latest_version(version, all_downloads):
    """Check if a version is the Latest (highest version number)"""
    highest = get_highest_version(all_downloads)
    return version == highest


def get_target_branch(version, all_downloads):
    """Determine which branch this version should be committed to"""
    if is_latest_version(version, all_downloads):
        return "main"
    else:
        return "stable"


def ensure_branch_exists(branch_name, base_ref=None):
    """Ensure a branch exists, create it if it doesn't

    Args:
        branch_name: Name of the branch to ensure exists
        base_ref: Optional git ref to create branch from (e.g., 'HEAD~1', commit hash)
    """
    try:
        # Check if branch exists locally
        result = subprocess.run(
            ['git', 'rev-parse', '--verify', branch_name],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"Branch '{branch_name}' already exists locally")
            return True
    except:
        pass

    # Check if branch exists on remote
    try:
        result = subprocess.run(
            ['git', 'ls-remote', '--heads', 'origin', branch_name],
            capture_output=True,
            text=True,
            check=True
        )
        if result.stdout.strip():
            print(f"Branch '{branch_name}' exists on remote, fetching...")
            # Fetch the remote branch
            subprocess.run(['git', 'fetch', 'origin', branch_name], check=True, capture_output=True)
            # Try to create local tracking branch from remote
            try:
                subprocess.run(['git', 'branch', '--track', branch_name, f'origin/{branch_name}'], check=True, capture_output=True)
                print(f"Created local tracking branch for '{branch_name}'")
            except subprocess.CalledProcessError:
                # Branch might already exist locally, that's ok
                print(f"Local branch '{branch_name}' already exists")
            return True
    except subprocess.CalledProcessError as e:
        print(f"Error fetching remote branch '{branch_name}': {e}")
        pass

    # Create new branch from base_ref if provided
    print(f"Creating new branch '{branch_name}'{f' from {base_ref}' if base_ref else ''}...")
    try:
        if base_ref:
            # Create branch from specific ref without checking it out yet
            subprocess.run(['git', 'branch', branch_name, base_ref], check=True, capture_output=True)
        else:
            # Create branch from current HEAD
            subprocess.run(['git', 'checkout', '-b', branch_name], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error creating branch '{branch_name}': {e}")
        return False


def clean_working_directory():
    """Clean untracked files that might interfere with branch switching"""
    import shutil

    # Remove __pycache__ directories
    for root, dirs, files in os.walk('.'):
        if '__pycache__' in dirs:
            pycache_path = os.path.join(root, '__pycache__')
            print(f"Removing {pycache_path}")
            shutil.rmtree(pycache_path)
            dirs.remove('__pycache__')  # Don't walk into removed directory

    # Remove build artifacts that cause conflicts
    for dir_name in ['dist', 'build', 'ibapi.egg-info', 'ibapi_python.egg-info']:
        if os.path.exists(dir_name):
            print(f"Removing {dir_name}/")
            shutil.rmtree(dir_name)


def switch_to_branch(branch_name):
    """Switch to the specified branch"""
    # Clean any temporary files that might interfere
    clean_working_directory()

    try:
        result = subprocess.run(['git', 'checkout', branch_name], check=True, capture_output=True, text=True)
        print(f"Switched to branch '{branch_name}'")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error switching to branch '{branch_name}': {e}")
        if e.stderr:
            print(f"Git stderr: {e.stderr}")
        if e.stdout:
            print(f"Git stdout: {e.stdout}")
        return False


def update_version(download_url):
    """Run update_ibapi.py to download, extract, and commit a version"""
    print(f"\n{'='*60}")
    print(f"Updating to version from: {download_url}")
    print(f"{'='*60}\n")

    try:
        result = subprocess.run(
            [sys.executable, 'update_ibapi.py', download_url],
            check=True,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr, file=sys.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error updating version: {e}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False


def build_package():
    """Build the package using python -m build"""
    print(f"\n{'='*60}")
    print("Building package...")
    print(f"{'='*60}\n")

    # Clean old build artifacts
    import shutil
    for dir_name in ['dist', 'build', 'ibapi.egg-info']:
        if os.path.exists(dir_name):
            print(f"Cleaning {dir_name}/")
            shutil.rmtree(dir_name)

    try:
        result = subprocess.run(
            [sys.executable, '-m', 'build'],
            check=True,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr, file=sys.stderr)

        # Verify dist files were created
        if os.path.exists('dist') and os.listdir('dist'):
            print(f"\nSuccessfully built package files:")
            for f in os.listdir('dist'):
                print(f"  - dist/{f}")
            return True
        else:
            print("ERROR: No dist files were created")
            return False

    except subprocess.CalledProcessError as e:
        print(f"Error building package: {e}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False


def publish_to_pypi():
    """Run publish_to_pypi.py to publish the package (or skip if SKIP_PYPI_UPLOAD is set)"""
    skip_upload = os.environ.get('SKIP_PYPI_UPLOAD', '').lower() in ('true', '1', 'yes')

    if skip_upload:
        print(f"\n{'='*60}")
        print("Skipping PyPI upload (SKIP_PYPI_UPLOAD is set)")
        print(f"{'='*60}\n")
        return True

    print(f"\n{'='*60}")
    print("Publishing to PyPI...")
    print(f"{'='*60}\n")

    try:
        result = subprocess.run(
            [sys.executable, 'publish_to_pypi.py'],
            check=True,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr, file=sys.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error publishing to PyPI: {e}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False


def main():
    """Main orchestration logic"""
    print("="*60)
    print("IB API Weekly Update Check")
    print("="*60)

    # Step 1: Fetch all available downloads
    print("\nStep 1: Fetching download information...")
    try:
        all_downloads = extract_download_info()
    except Exception as e:
        print(f"Error fetching downloads: {e}", file=sys.stderr)
        sys.exit(1)

    # Filter to only Mac/Unix versions (they all have the same Python source)
    downloads = filter_mac_unix_downloads(all_downloads)
    print(f"Found {len(downloads)} Mac/Unix version(s)")

    if not downloads:
        print("No downloads found. Exiting.")
        sys.exit(0)

    # Step 2: Get existing git tags
    print("\nStep 2: Checking existing versions...")
    existing_tags = get_existing_tags()
    print(f"Found {len(existing_tags)} existing tag(s)")

    # Step 3: Find new versions
    print("\nStep 3: Finding new versions...")
    new_versions = find_new_versions(downloads, existing_tags)

    if not new_versions:
        print("\nNo new versions found. Everything is up to date!")
        sys.exit(0)

    # Sort versions (oldest first, so we process Stable before Latest)
    new_versions = sort_versions(new_versions)

    # Determine highest version (Latest)
    highest_version = get_highest_version(downloads)
    print(f"\nHighest version (Latest): {highest_version}")

    print(f"\nFound {len(new_versions)} new version(s) to process:")
    for dl in new_versions:
        target_branch = get_target_branch(dl['version'], downloads)
        print(f"  - {dl['version']} ({dl['release_date']}) → branch '{target_branch}'")

    # Step 4: Process each new version
    print("\nStep 4: Processing new versions...")
    success_count = 0
    failed_versions = []
    branches_updated = set()

    # Get the current HEAD before any modifications (for creating stable branch)
    try:
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True)
        initial_head = result.stdout.strip()
    except:
        initial_head = None

    for dl in new_versions:
        version = dl['version']
        url = dl['url']
        target_branch = get_target_branch(version, downloads)

        print(f"\n{'='*60}")
        print(f"Processing version {version} → branch '{target_branch}'")
        print(f"{'='*60}")

        # Determine base ref for new branches
        # If creating stable branch and main has been updated, use initial HEAD
        base_ref = None
        if target_branch == 'stable' and 'main' in branches_updated and initial_head:
            base_ref = initial_head
            print(f"Will create stable branch from initial state: {initial_head[:8]}")

        # Ensure target branch exists
        if not ensure_branch_exists(target_branch, base_ref):
            print(f"Failed to create/access branch '{target_branch}'")
            failed_versions.append(version)
            continue

        # Switch to target branch
        if not switch_to_branch(target_branch):
            print(f"Failed to switch to branch '{target_branch}'")
            failed_versions.append(version)
            continue

        # Update and commit
        if not update_version(url):
            print(f"Failed to update version {version}")
            failed_versions.append(version)
            continue

        branches_updated.add(target_branch)

        # Build package
        if not build_package():
            print(f"Failed to build package for version {version}")
            failed_versions.append(version)
            continue

        # Publish to PyPI (or skip if SKIP_PYPI_UPLOAD is set)
        if not publish_to_pypi():
            print(f"Failed to publish version {version} to PyPI")
            failed_versions.append(version)
            continue

        success_count += 1
        print(f"\nSuccessfully processed version {version}!")

    # Step 5: Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Processed: {success_count}/{len(new_versions)} version(s)")
    print(f"Branches updated: {', '.join(sorted(branches_updated)) if branches_updated else 'none'}")

    if failed_versions:
        print(f"Failed versions: {', '.join(failed_versions)}")
        sys.exit(1)
    elif success_count > 0:
        print("All versions processed successfully!")
        print("\nNote: Changes committed to branches. Workflow will push them.")
        sys.exit(0)
    else:
        print("No versions were processed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
