#!/bin/bash

set -e

# Default bump type
bump_type="patch"

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --minor) bump_type="minor"; shift ;;
        --major) bump_type="major"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
done

# Function to bump version
bump_version() {
    local version=$1
    local bump_type=$2

    IFS='.' read -r -a parts <<< "$version"

    case $bump_type in
        patch)
            parts[2]=$((parts[2] + 1))
            ;;
        minor)
            parts[1]=$((parts[1] + 1))
            parts[2]=0
            ;;
        major)
            parts[0]=$((parts[0] + 1))
            parts[1]=0
            parts[2]=0
            ;;
    esac

    echo "${parts[0]}.${parts[1]}.${parts[2]}"
}

# Read current version from pyproject.toml
current_version=$(grep -oE '^version = "[^"]+"' pyproject.toml | awk -F'"' '{print $2}')

# Bump the version
new_version=$(bump_version "$current_version" "$bump_type")

echo "Bumping version from $current_version to $new_version"

# Update the version in pyproject.toml
sed -i '' "s/version = \"$current_version\"/version = \"$new_version\"/" pyproject.toml

echo "Version bumped from $current_version to $new_version"

# Run uv lock
uv --version
uv lock
uv sync
sync
# Create a new branch
branch_name="release-${new_version}"
if git show-ref --verify --quiet refs/heads/"$branch_name"; then
    git checkout "$branch_name"
else
    git checkout -b "$branch_name"
fi

# Add changes and commit
git add pyproject.toml
git add uv.lock


# Read the version from pyproject.toml
VERSION=$(grep -oE '^version = "[^"]+' pyproject.toml | sed 's/version = "//')

# Split the version by the dot and write it to version.py
IFS='.' read -r MAJOR MINOR PATCH <<< "$VERSION"

# Update version.py with the new version
cat <<EOF > src/mutenix/version.py
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>

MAJOR = $MAJOR
MINOR = $MINOR
PATCH = $PATCH
EOF

git add src/mutenix/version.py

git commit -m "chore: Bump version to $new_version"

echo "Branch $branch_name created and changes committed"

# Check if the tag exists, if not, create it
if ! git rev-parse "v$VERSION" >/dev/null 2>&1; then
    git tag "v$VERSION"
    echo "Tag v$VERSION created."
else
    echo "Tag v$VERSION already exists."
    read -p "Tag v$VERSION already exists. Do you want to force the release? (y/n): " FORCE_RELEASE
    if [[ "$FORCE_RELEASE" == "y" ]]; then
        git tag -d "v$VERSION"
        git tag "v$VERSION"
        echo "Tag v$VERSION has been forced."
    else
        echo "Release aborted."
        exit 1
    fi
fi

git push origin "$branch_name"
gh pr create --fill
gh pr merge --auto -r

for i in {1..12}; do
    pr_status=$(gh pr view --json merged --jq '.merged')
    if [[ "$pr_status" == "true" ]]; then
        break
    fi
    echo "Waiting for PR to be merged..."
    sleep 5
done

# Check if the PR has been merged
pr_status=$(gh pr view --json merged --jq '.merged')

if [[ "$pr_status" == "true" ]]; then
    echo "PR has been merged. Pushing the tag."
    git push origin "v$VERSION"
else
    echo "PR has not been merged yet. Please check the status manually."
fi
