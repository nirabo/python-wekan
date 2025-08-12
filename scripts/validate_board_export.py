#!/usr/bin/env python3
"""
Validate that exported board JSON matches filesystem representation.

This script compares WeKan board export JSON with our cloned filesystem
representation to ensure content agreement and verify export efficiency.
"""

import json
import sys
from pathlib import Path
from typing import Any

import yaml


def load_json_export(export_path: Path) -> dict[str, Any]:
    """Load board export JSON."""
    with open(export_path, encoding="utf-8") as f:
        return json.load(f)


def load_filesystem_cards(board_dir: Path) -> dict[str, dict[str, Any]]:
    """Load all cards from filesystem representation."""
    cards = {}

    # Find all markdown files
    for md_file in board_dir.glob("**/*.md"):
        if md_file.name.startswith("."):
            continue

        try:
            with open(md_file, encoding="utf-8") as f:
                content = f.read()

            # Parse YAML frontmatter
            if content.startswith("---\n"):
                parts = content.split("---\n", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1])
                    body = parts[2].strip()

                    card_id = frontmatter.get("id")
                    if card_id:
                        cards[card_id] = {
                            "frontmatter": frontmatter,
                            "body": body,
                            "file_path": md_file,
                        }
        except Exception as e:
            print(f"Error reading {md_file}: {e}")

    return cards


def compare_cards(json_cards: list[dict], fs_cards: dict[str, dict]) -> dict[str, list]:
    """Compare JSON cards with filesystem cards."""
    results = {
        "matches": [],
        "missing_in_fs": [],
        "missing_in_json": [],
        "metadata_mismatches": [],
        "content_differences": [],
    }

    # Check JSON cards against filesystem
    for json_card in json_cards:
        card_id = json_card.get("_id")
        if not card_id:
            continue

        if card_id in fs_cards:
            fs_card = fs_cards[card_id]
            frontmatter = fs_card["frontmatter"]

            # Compare key metadata fields
            mismatches = []

            if json_card.get("title") != frontmatter.get("title"):
                mismatches.append(
                    f"title: JSON='{json_card.get('title')}' " f"vs FS='{frontmatter.get('title')}'"
                )

            if json_card.get("cardNumber") != frontmatter.get("card_number"):
                mismatches.append(
                    f"card_number: JSON={json_card.get('cardNumber')} "
                    f"vs FS={frontmatter.get('card_number')}"
                )

            if json_card.get("archived", False) != frontmatter.get("archived", False):
                mismatches.append(
                    f"archived: JSON={json_card.get('archived')} "
                    f"vs FS={frontmatter.get('archived')}"
                )

            if json_card.get("sort") != frontmatter.get("sort"):
                mismatches.append(
                    f"sort: JSON={json_card.get('sort')} " f"vs FS={frontmatter.get('sort')}"
                )

            if mismatches:
                results["metadata_mismatches"].append(
                    {"card_id": card_id, "title": json_card.get("title"), "mismatches": mismatches}
                )
            else:
                results["matches"].append({"card_id": card_id, "title": json_card.get("title")})

        else:
            results["missing_in_fs"].append(
                {
                    "card_id": card_id,
                    "title": json_card.get("title"),
                    "archived": json_card.get("archived", False),
                }
            )

    # Check for cards in filesystem but not in JSON
    json_card_ids = {card.get("_id") for card in json_cards if card.get("_id")}
    for fs_card_id in fs_cards:
        if fs_card_id not in json_card_ids:
            fs_card = fs_cards[fs_card_id]
            results["missing_in_json"].append(
                {
                    "card_id": fs_card_id,
                    "title": fs_card["frontmatter"].get("title"),
                    "file_path": str(fs_card["file_path"]),
                }
            )

    return results


def print_results(results: dict[str, list], board_title: str):
    """Print comparison results."""
    print(f"\n🔍 Board Export Validation: {board_title}")
    print("=" * 50)

    print(f"\n✅ Matching cards: {len(results['matches'])}")
    for match in results["matches"][:5]:  # Show first 5
        print(f"  • {match['card_id']}: {match['title']}")
    if len(results["matches"]) > 5:
        print(f"  • ... and {len(results['matches']) - 5} more")

    if results["metadata_mismatches"]:
        print(f"\n⚠️  Metadata mismatches: {len(results['metadata_mismatches'])}")
        for mismatch in results["metadata_mismatches"]:
            print(f"  • {mismatch['card_id']}: {mismatch['title']}")
            for diff in mismatch["mismatches"]:
                print(f"    - {diff}")

    if results["missing_in_fs"]:
        print(f"\n❌ Missing in filesystem: {len(results['missing_in_fs'])}")
        for missing in results["missing_in_fs"]:
            archived_note = " (archived)" if missing["archived"] else ""
            print(f"  • {missing['card_id']}: {missing['title']}{archived_note}")

    if results["missing_in_json"]:
        print(f"\n❓ In filesystem but not JSON: {len(results['missing_in_json'])}")
        for missing in results["missing_in_json"]:
            print(f"  • {missing['card_id']}: {missing['title']}")
            print(f"    File: {missing['file_path']}")

    # Summary
    total_json_cards = (
        len(results["matches"])
        + len(results["metadata_mismatches"])
        + len(results["missing_in_fs"])
    )
    total_fs_cards = (
        len(results["matches"])
        + len(results["metadata_mismatches"])
        + len(results["missing_in_json"])
    )

    print("\n📊 Summary:")
    print(f"  • JSON cards: {total_json_cards}")
    print(f"  • Filesystem cards: {total_fs_cards}")
    print(f"  • Perfect matches: {len(results['matches'])}")
    issues_found = (
        len(results["metadata_mismatches"])
        + len(results["missing_in_fs"])
        + len(results["missing_in_json"])
    )
    print(f"  • Issues found: {issues_found} ")


def main():
    """Main validation function."""
    if len(sys.argv) != 3:
        print("Usage: python validate_board_export.py <export.json> <board_dir>")
        sys.exit(1)

    export_path = Path(sys.argv[1])
    board_dir = Path(sys.argv[2])

    if not export_path.exists():
        print(f"Export file not found: {export_path}")
        sys.exit(1)

    if not board_dir.exists():
        print(f"Board directory not found: {board_dir}")
        sys.exit(1)

    # Load data
    print("Loading export JSON...")
    json_data = load_json_export(export_path)

    print("Loading filesystem cards...")
    fs_cards = load_filesystem_cards(board_dir)

    # Compare
    print("Comparing content...")
    results = compare_cards(json_data.get("cards", []), fs_cards)

    # Print results
    print_results(results, json_data.get("title", "Unknown Board"))


if __name__ == "__main__":
    main()
