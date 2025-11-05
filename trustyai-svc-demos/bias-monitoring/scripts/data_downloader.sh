#!/bin/bash

# Title: GitHub Directory Downloader (No SVN)
# Description: Downloads a single subdirectory from a GitHub repository using 'curl' and 'unzip'.
# It downloads the entire repository as a ZIP archive and extracts only the specified path.
# Usage: ./github_dir_downloader.sh <repository_url> <directory_path> [branch_name]
# Example: ./github_dir_downloader.sh https://github.com/twbs/bootstrap 'site/docs/5.3/assets' main

REPO_URL_TEST="https://github.com/trustyai-explainability/odh-trustyai-demos"
DIR_PATH_TEST="2-BiasMonitoring/kserve-demo/data"
BRANCH_TEST="main"

REPO_URL="${1:-$REPO_URL_TEST}"
DIR_PATH="${2:-$DIR_PATH_TEST}"
BRANCH="${3:-$BRANCH_TEST}"

# --- 1. Input Validation ---
if [ -z "$REPO_URL" ] || [ -z "$DIR_PATH" ]; then
    echo "Usage: $0 <repository_url> <directory_path> [branch_name]"
    echo "Example: $0 https://github.com/octocat/Spoon-Knife 'lib/test' main"
    echo ""
    echo "Note: The repository URL should be the base URL (e.g., https://github.com/user/repo)."
    echo "The directory path is relative to the repository root."
    exit 1
fi

# --- 2. Tool Check ---
if ! command -v curl &> /dev/null || ! command -v unzip &> /dev/null; then
    echo "Error: 'curl' and 'unzip' are required for this script."
    echo "Please ensure both are installed."
    exit 1
fi

# --- 3. Prepare Variables ---
# Extract the 'repo' part from the URL (e.g., "user/repo")
REPO_NAME_WITH_USER=$(basename "$REPO_URL")
TEMP_ZIP_FILE="${REPO_NAME_WITH_USER}-${BRANCH}.zip"

# GitHub ZIP URL format: https://github.com/user/repo/archive/refs/heads/branch.zip
ZIP_URL="${REPO_URL}/archive/refs/heads/${BRANCH}.zip"

# The name of the root directory created by unzip (e.g., 'repo-main')
UNZIP_ROOT_DIR="${REPO_NAME_WITH_USER}-${BRANCH}"

# The full path to the directory * inside * the extracted structure (e.g., repo-main/path/to/dir)
FULL_PATH_IN_ZIP="${UNZIP_ROOT_DIR}/${DIR_PATH}"

# The final destination folder (the last component of the DIR_PATH)
DEST_FOLDER=$(basename "${DIR_PATH}")

echo "=================================================="
echo "GitHub Directory Downloader (No SVN)"
echo "=================================================="
echo "Repository: ${REPO_URL}"
echo "Directory:  ${DIR_PATH}"
echo "Branch:     ${BRANCH}"
echo "Destination: ./${DEST_FOLDER}"
echo "--------------------------------------------------"

# --- 4. Download the Repository ZIP ---
echo "1. Downloading repository archive..."
# -f: Fail silently on HTTP errors, -s: Silent, -S: Show error if silent fails, -L: Follow redirects, -o: Output file
if ! curl -fsSL -o "${TEMP_ZIP_FILE}" "${ZIP_URL}"; then
    echo "Error: Failed to download archive. Check if the URL and branch name ('${BRANCH}') are correct."
    rm -f "${TEMP_ZIP_FILE}" # Clean up failed download attempt
    exit 1
fi

# --- 5. Extract the Specific Directory ---
echo "2. Extracting directory '${DIR_PATH}'..."

# Create a temporary directory for extraction to avoid cluttering the current directory
TEMP_EXTRACT_DIR="__temp_gh_extract_$$" # Unique temp dir name
mkdir -p "${TEMP_EXTRACT_DIR}"

# Unzip only the files matching the desired path structure into the temp dir.
# The pattern must include the root directory created by the zip file.
if ! unzip -q "${TEMP_ZIP_FILE}" "${UNZIP_ROOT_DIR}/${DIR_PATH}/*" -d "${TEMP_EXTRACT_DIR}"; then
    # This might happen if the directory is empty or the path is slightly off.
    echo "Warning: Initial extraction failed. Checking for files at the root of the path."
fi

# --- 6. Final Move and Cleanup ---
if [ -d "${TEMP_EXTRACT_DIR}/${FULL_PATH_IN_ZIP}" ]; then
    echo "3. Moving contents to ./${DEST_FOLDER} and cleaning up..."
    
    # Move the contents of the target directory to the final destination
    mkdir -p "${DEST_FOLDER}"
    mv "${TEMP_EXTRACT_DIR}/${FULL_PATH_IN_ZIP}"/* "${DEST_FOLDER}/"

    # Cleanup temporary files and directories
    rm -rf "${TEMP_EXTRACT_DIR}"
    rm -f "${TEMP_ZIP_FILE}"
    
    echo "--------------------------------------------------"
    echo "SUCCESS! Directory '${DIR_PATH}' downloaded to './${DEST_FOLDER}'"
else
    # Failed to find the extracted path
    echo "--------------------------------------------------"
    echo "ERROR: Directory '${DIR_PATH}' could not be extracted or located inside the ZIP archive (looking for ${FULL_PATH_IN_ZIP})."
    echo "Double-check the branch name ('${BRANCH}') and directory path."
    
    # Cleanup temporary files and directories
    rm -rf "${TEMP_EXTRACT_DIR}"
    rm -f "${TEMP_ZIP_FILE}"
    exit 1
fi
echo "=================================================="
