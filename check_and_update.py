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
    """Convert version string to git tag format"""
    # Version like "10.37" becomes "v10.37.02" if full version is 1037.02
    # For now, just use v prefix
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


def publish_to_pypi():
    """Run publish_to_pypi.py to build and publish the package"""
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

    print(f"\nFound {len(new_versions)} new version(s) to process:")
    for dl in new_versions:
        print(f"  - {dl['version']} ({dl['release_date']})")

    # Step 4: Process each new version
    print("\nStep 4: Processing new versions...")
    success_count = 0
    failed_versions = []

    for dl in new_versions:
        version = dl['version']
        url = dl['url']

        print(f"\n{'='*60}")
        print(f"Processing version {version}")
        print(f"{'='*60}")

        # Update and commit
        if not update_version(url):
            print(f"Failed to update version {version}")
            failed_versions.append(version)
            continue

        # Publish to PyPI
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

    if failed_versions:
        print(f"Failed versions: {', '.join(failed_versions)}")
        sys.exit(1)
    elif success_count > 0:
        print("All versions processed successfully!")
        sys.exit(0)
    else:
        print("No versions were processed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
