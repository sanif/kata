#!/bin/bash
# Release script for kata-workspace
# Usage: ./scripts/release.sh [major|minor|patch] or ./scripts/release.sh v1.2.3

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get current version from git tags
get_current_version() {
    git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0"
}

# Parse semver
parse_version() {
    local version="${1#v}"  # Remove 'v' prefix
    IFS='.' read -r major minor patch <<< "$version"
    echo "$major $minor $patch"
}

# Bump version
bump_version() {
    local current=$(get_current_version)
    read -r major minor patch <<< "$(parse_version "$current")"

    case "$1" in
        major)
            major=$((major + 1))
            minor=0
            patch=0
            ;;
        minor)
            minor=$((minor + 1))
            patch=0
            ;;
        patch)
            patch=$((patch + 1))
            ;;
        *)
            echo -e "${RED}Unknown bump type: $1${NC}"
            exit 1
            ;;
    esac

    echo "v${major}.${minor}.${patch}"
}

# Validate version format
validate_version() {
    if [[ ! "$1" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo -e "${RED}Invalid version format: $1${NC}"
        echo "Expected format: v1.2.3"
        exit 1
    fi
}

# Main
main() {
    if [ -z "$1" ]; then
        echo "Usage: $0 [major|minor|patch|vX.Y.Z]"
        echo ""
        echo "Current version: $(get_current_version)"
        echo ""
        echo "Examples:"
        echo "  $0 patch    # Bump patch version (0.1.0 -> 0.1.1)"
        echo "  $0 minor    # Bump minor version (0.1.0 -> 0.2.0)"
        echo "  $0 major    # Bump major version (0.1.0 -> 1.0.0)"
        echo "  $0 v1.2.3   # Set specific version"
        exit 0
    fi

    # Ensure we're on main branch
    current_branch=$(git rev-parse --abbrev-ref HEAD)
    if [ "$current_branch" != "main" ]; then
        echo -e "${YELLOW}Warning: Not on main branch (currently on: $current_branch)${NC}"
        read -p "Continue anyway? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    # Ensure working directory is clean
    if [ -n "$(git status --porcelain)" ]; then
        echo -e "${RED}Error: Working directory is not clean${NC}"
        echo "Please commit or stash your changes first."
        exit 1
    fi

    # Determine new version
    local new_version
    case "$1" in
        major|minor|patch)
            new_version=$(bump_version "$1")
            ;;
        v*)
            validate_version "$1"
            new_version="$1"
            ;;
        *)
            echo -e "${RED}Unknown argument: $1${NC}"
            exit 1
            ;;
    esac

    current_version=$(get_current_version)
    echo -e "${GREEN}Current version: $current_version${NC}"
    echo -e "${GREEN}New version:     $new_version${NC}"
    echo ""

    read -p "Create tag $new_version and push? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi

    # Create annotated tag
    git tag -a "$new_version" -m "Release $new_version"
    echo -e "${GREEN}Created tag: $new_version${NC}"

    # Push tag
    git push origin "$new_version"
    echo -e "${GREEN}Pushed tag to origin${NC}"

    echo ""
    echo -e "${GREEN}Release $new_version complete!${NC}"
    echo ""
    echo "GitHub Actions will now build and publish to PyPI."
    echo "Check status at: https://github.com/kata-workspace/kata/actions"
}

main "$@"
