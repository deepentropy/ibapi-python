#!/usr/bin/env python3
"""
Complete automation script for downloading, extracting, and committing IB API
"""
import os
import re
import sys
import zipfile
import shutil
import requests
import subprocess
import tempfile
from pathlib import Path


def extract_version_from_filename(filename):
    """Extract version number from filename like twsapi_macunix.1040.01.zip"""
    match = re.search(r'\.(\d+\.\d+)\.zip$', filename)
    if match:
        return match.group(1)

    # Try alternative patterns
    match = re.search(r'twsapi.*?(\d+\.\d+)', filename)
    if match:
        return match.group(1)

    raise ValueError(f"Could not extract version from filename: {filename}")


def download_file(url, dest_path):
    """Download a file from URL to destination path"""
    print(f"Downloading {url}...")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    response = requests.get(url, headers=headers, stream=True, verify=False, timeout=30)
    response.raise_for_status()

    total_size = int(response.headers.get('content-length', 0))
    if total_size > 0:
        print(f"File size: {total_size / 1024 / 1024:.2f} MB")

    with open(dest_path, 'wb') as f:
        downloaded = 0
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"\rProgress: {percent:.1f}%", end='', flush=True)

    print(f"\nDownloaded to {dest_path}")
    return dest_path


def extract_pythonclient(zip_path, extract_to=None):
    """Extract the pythonclient directory from the zip file"""
    if extract_to is None:
        extract_to = tempfile.gettempdir()

    print(f"\nExtracting {zip_path}...")

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # List all files to find the pythonclient directory
        all_files = zip_ref.namelist()
        print(f"Total files in zip: {len(all_files)}")

        # Find files in pythonclient path (case insensitive)
        pythonclient_files = [f for f in all_files if 'pythonclient' in f.lower()]

        if not pythonclient_files:
            print("\nSearching for alternative patterns...")
            # Show directory structure
            dirs = set()
            for f in all_files:
                parts = f.split('/')
                if len(parts) > 1:
                    dirs.add('/'.join(parts[:-1]))

            print("Available directories:")
            for d in sorted(dirs)[:20]:
                print(f"  {d}")

            raise ValueError("Could not find pythonclient directory in zip file")

        # Find the base path for pythonclient
        # Look for pattern like IBJts/source/pythonclient
        base_path = None
        for file in pythonclient_files:
            if 'pythonclient' in file.lower():
                # Extract the path up to and including pythonclient
                parts = file.split('/')
                try:
                    pythonclient_idx = next(i for i, p in enumerate(parts) if 'pythonclient' in p.lower())
                    base_path = '/'.join(parts[:pythonclient_idx+1])
                    break
                except StopIteration:
                    continue

        if not base_path:
            raise ValueError("Could not determine pythonclient base path")

        print(f"Found pythonclient at: {base_path}")

        # Extract only pythonclient files
        extracted_files = []
        for file in all_files:
            if file.startswith(base_path) and not file.endswith('/'):
                zip_ref.extract(file, extract_to)
                extracted_files.append(file)

        print(f"Extracted {len(extracted_files)} files")

        return os.path.join(extract_to, base_path)


def run_git_command(cmd, check=True):
    """Run a git command and return the output"""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if result.returncode != 0:
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        if check:
            raise RuntimeError(f"Git command failed: {' '.join(cmd)}")

    return result.stdout.strip()


def commit_and_tag(pythonclient_path, version, repo_path=None):
    """Commit the extracted pythonclient to git and tag it"""
    if repo_path is None:
        repo_path = os.getcwd()

    print(f"\nCommitting to git repository at {repo_path}...")

    # Change to repo directory
    os.chdir(repo_path)

    # Remove existing ibapi directory if it exists
    ibapi_dest = os.path.join(repo_path, 'ibapi')
    if os.path.exists(ibapi_dest):
        print(f"Removing existing {ibapi_dest}...")
        shutil.rmtree(ibapi_dest)

    # Copy pythonclient contents to ibapi directory
    print(f"Copying {pythonclient_path} to {ibapi_dest}...")
    shutil.copytree(pythonclient_path, ibapi_dest)

    # Git operations
    print("\nGit operations:")

    # Check current branch
    current_branch = run_git_command(['git', 'branch', '--show-current'])
    print(f"Current branch: {current_branch}")

    # Add all files
    run_git_command(['git', 'add', '.'])

    # Check if there are changes to commit
    status = run_git_command(['git', 'status', '--short'])
    if not status:
        print("No changes to commit")
        return False

    # Commit
    commit_message = f"Update IB API to version {version}"
    run_git_command(['git', 'commit', '-m', commit_message])

    # Create tag
    tag_name = f"v{version}"
    print(f"\nCreating tag: {tag_name}")

    # Check if tag exists
    existing_tags = run_git_command(['git', 'tag', '-l', tag_name], check=False)
    if existing_tags:
        print(f"Tag {tag_name} already exists, deleting it...")
        run_git_command(['git', 'tag', '-d', tag_name])

    # Create new tag
    run_git_command(['git', 'tag', '-a', tag_name, '-m', f'Version {version}'])

    print(f"\nCommit and tag created successfully!")
    print(f"  Commit: {commit_message}")
    print(f"  Tag: {tag_name}")

    return True


def main():
    """Main function to orchestrate the entire process"""
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    print("="*60)
    print("IB API Updater")
    print("="*60)

    # Check if URL was provided as argument
    if len(sys.argv) < 2:
        print("\nError: Download URL required")
        print("\nUsage: python update_ibapi.py <download_url>")
        print("\nExample:")
        print("  python update_ibapi.py https://interactivebrokers.github.io/downloads/twsapi_macunix.1040.01.zip")
        print("\nYou can find the latest version at: https://interactivebrokers.github.io/")
        sys.exit(1)

    download_url = sys.argv[1]
    filename = os.path.basename(download_url)

    try:
        # Extract version from filename
        version = extract_version_from_filename(filename)
        print(f"\nDetected version: {version}")

        # Create temporary directory for download
        temp_dir = tempfile.gettempdir()
        zip_path = os.path.join(temp_dir, filename)
        print(f"Using temporary directory: {temp_dir}")

        # Download the zip file
        download_file(download_url, zip_path)

        # Extract pythonclient
        pythonclient_path = extract_pythonclient(zip_path, extract_to=temp_dir)
        print(f"Extracted to: {pythonclient_path}")

        # Commit and tag
        success = commit_and_tag(pythonclient_path, version)

        # Clean up
        print(f"\nCleaning up temporary files...")
        if os.path.exists(zip_path):
            os.remove(zip_path)
            print(f"Removed: {zip_path}")

        # Clean up extracted directory
        base_dir = pythonclient_path
        while base_dir and base_dir != temp_dir and os.path.exists(base_dir):
            parent = os.path.dirname(base_dir)
            if parent == temp_dir or not parent:
                if os.path.exists(base_dir):
                    shutil.rmtree(base_dir)
                    print(f"Removed: {base_dir}")
                break
            base_dir = parent

        print("\n" + "="*60)
        if success:
            print("SUCCESS!")
            print(f"IB API version {version} has been updated and tagged")
        else:
            print("No changes were made (version might already be committed)")
        print("="*60)

    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
