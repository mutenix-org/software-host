#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
# Check if the working directory is clean
if ! git diff-index --quiet HEAD --; then
    echo "Working directory is not clean. Please commit or stash your changes."
    exit 1
fi
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

# Check if the working directory is clean
if ! git diff-index --quiet HEAD --; then
    git add src/mutenix/version.py
    git commit -am "chore: Update version.py to $VERSION"
fi


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
