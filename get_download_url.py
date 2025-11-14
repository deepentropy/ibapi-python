#!/usr/bin/env python3
"""
Helper script to fetch the IB API download URLs from the website
This script should be run on a machine with unrestricted web access
"""
import json
import re
import sys

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: Required packages not installed")
    print("Please run: pip install requests beautifulsoup4")
    sys.exit(1)


def extract_download_info():
    """Extract all download links with their metadata from the IB GitHub page"""
    url = "https://interactivebrokers.github.io/"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    print(f"Fetching {url}...")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching page: {e}")
        print("\nAlternative method:")
        print("1. Open https://interactivebrokers.github.io/ in your browser")
        print("2. Find the download links in the table")
        print("3. Manually extract the information")
        sys.exit(1)

    soup = BeautifulSoup(response.content, 'html.parser')

    # Find all table rows with class 'linebottom'
    rows = soup.find_all('tr', class_='linebottom')

    downloads = []

    for row in rows:
        # Find all cells in the row
        cells = row.find_all('td')

        for cell in cells:
            # Find download link (with .zip or .msi extension)
            link = cell.find('a', href=re.compile(r'(//)?interactivebrokers\.github\.io/downloads/(tws|TWS).*\.(zip|msi)$', re.IGNORECASE))

            if link:
                download_url = link['href']

                # Make sure it's an absolute URL
                if not download_url.startswith('http'):
                    if download_url.startswith('//'):
                        download_url = 'https:' + download_url
                    else:
                        download_url = 'https://interactivebrokers.github.io' + download_url

                # Extract button text to determine platform
                button_text = link.get_text(strip=True)

                # Determine platform from button text or cell position
                platform = None
                if 'Windows' in button_text or '.msi' in download_url:
                    platform = 'Windows'
                elif 'Mac' in button_text or 'Unix' in button_text:
                    platform = 'Mac / Unix'

                # Find version and release date in the same cell
                cell_text = cell.get_text()

                version_match = re.search(r'Version:\s*(?:API\s*)?(\d+\.\d+)', cell_text)
                date_match = re.search(r'Release Date:\s*([A-Za-z]+\s+\d+\s+\d{4})', cell_text)

                version = version_match.group(1) if version_match else None
                release_date = date_match.group(1) if date_match else None

                # Find release notes link in the same cell
                release_notes_link = cell.find('a', href=re.compile(r'releasenotes'))
                release_notes_url = None
                if release_notes_link:
                    release_notes_url = release_notes_link['href']
                    if release_notes_url.startswith('//'):
                        release_notes_url = 'https:' + release_notes_url

                download_info = {
                    'url': download_url,
                    'version': version,
                    'release_date': release_date,
                    'platform': platform,
                    'release_notes': release_notes_url
                }

                downloads.append(download_info)

    if not downloads:
        print("Could not find any download links")
        sys.exit(1)

    return downloads


def display_downloads(downloads):
    """Display the download information in a readable format"""
    print(f"\nFound {len(downloads)} download(s):\n")

    for i, dl in enumerate(downloads, 1):
        print(f"{i}. Platform: {dl['platform']}")
        print(f"   Version: {dl['version']}")
        print(f"   Release Date: {dl['release_date']}")
        print(f"   Download URL: {dl['url']}")
        if dl['release_notes']:
            print(f"   Release Notes: {dl['release_notes']}")
        print()

    # Also save to JSON file
    output_file = 'download_info.json'
    with open(output_file, 'w') as f:
        json.dump(downloads, f, indent=2)
    print(f"Download information saved to {output_file}")

    # Show example usage
    if downloads:
        mac_unix_downloads = [d for d in downloads if d['platform'] == 'Mac / Unix']
        if mac_unix_downloads:
            latest = mac_unix_downloads[0]
            print(f"\nTo update to the latest Mac/Unix version, run:")
            print(f"  python update_ibapi.py {latest['url']}")


if __name__ == "__main__":
    downloads = extract_download_info()
    display_downloads(downloads)
