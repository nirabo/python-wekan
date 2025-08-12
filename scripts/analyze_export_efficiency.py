#!/usr/bin/env python3
"""
Analyze export efficiency and content coverage.

Compare WeKan board export with filesystem representation to demonstrate
the efficiency and completeness of our cloning approach.
"""

import json
import sys
from pathlib import Path
from typing import Any


def get_file_sizes(export_path: Path, board_dir: Path) -> dict[str, int]:
    """Get file sizes for comparison."""
    sizes = {}

    # JSON export size
    sizes["json_export"] = export_path.stat().st_size

    # Filesystem representation size
    fs_size = 0
    for file in board_dir.rglob("*"):
        if file.is_file():
            fs_size += file.stat().st_size
    sizes["filesystem"] = fs_size

    return sizes


def analyze_content_structure(json_data: dict, board_dir: Path) -> dict[str, Any]:
    """Analyze content structure and coverage."""
    analysis = {"json_structure": {}, "filesystem_structure": {}, "content_coverage": {}}

    # Analyze JSON structure
    analysis["json_structure"] = {
        "total_cards": len(json_data.get("cards", [])),
        "active_cards": len(
            [c for c in json_data.get("cards", []) if not c.get("archived", False)]
        ),
        "archived_cards": len([c for c in json_data.get("cards", []) if c.get("archived", False)]),
        "lists": len(json_data.get("lists", [])),
        "swimlanes": len(json_data.get("swimlanes", [])),
        "labels": len(json_data.get("labels", [])),
        "members": len(json_data.get("members", [])),
        "activities": len(json_data.get("activities", [])),
        "checklists": len(json_data.get("checklists", [])),
        "comments": len(json_data.get("comments", [])),
    }

    # Analyze filesystem structure
    card_files = list(board_dir.rglob("*.md"))
    actual_cards = [f for f in card_files if not f.parts[-2].startswith(".wekan-")]
    metadata_files = [f for f in card_files if f.parts[-2].startswith(".wekan-")]

    list_dirs = [d for d in board_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]

    analysis["filesystem_structure"] = {
        "total_files": len(card_files),
        "card_files": len(actual_cards),
        "metadata_files": len(metadata_files),
        "list_directories": len(list_dirs),
        "metadata_directories": len(list(board_dir.rglob(".wekan-*"))),
    }

    # Content coverage analysis
    json_cards_with_description = len(
        [c for c in json_data.get("cards", []) if c.get("description", "").strip()]
    )
    json_cards_with_labels = len([c for c in json_data.get("cards", []) if c.get("labelIds")])

    analysis["content_coverage"] = {
        "cards_with_content": json_cards_with_description,
        "cards_with_labels": json_cards_with_labels,
        "content_rich_ratio": json_cards_with_description / max(len(json_data.get("cards", [])), 1),
        "label_usage_ratio": json_cards_with_labels / max(len(json_data.get("cards", [])), 1),
    }

    return analysis


def print_efficiency_report(sizes: dict[str, int], analysis: dict[str, Any], board_title: str):
    """Print comprehensive efficiency report."""
    print(f"\n📊 Export Efficiency Analysis: {board_title}")
    print("=" * 60)

    # Size comparison
    print("\n💾 Storage Efficiency:")
    print(
        f"  • JSON Export:      {sizes['json_export']:,} bytes ({sizes['json_export']/1024:.1f} KB)"
    )
    print(
        f"  • Filesystem Rep:   {sizes['filesystem']:,} bytes ({sizes['filesystem']/1024:.1f} KB)"
    )

    if sizes["json_export"] > 0:
        ratio = sizes["filesystem"] / sizes["json_export"]
        print(f"  • Size Ratio:       {ratio:.2f}x")
        if ratio < 1:
            print(f"    → Filesystem is {(1-ratio)*100:.1f}% smaller (more efficient)")
        else:
            print(f"    → Filesystem is {(ratio-1)*100:.1f}% larger (includes metadata)")

    # Structure comparison
    print("\n🏗️  Structure Analysis:")
    json_struct = analysis["json_structure"]
    fs_struct = analysis["filesystem_structure"]

    print(
        f"  • Cards:            JSON={json_struct['total_cards']:2d} | "
        f"FS={fs_struct['card_files']:2d} | "
        f"Active={json_struct['active_cards']:2d}"
    )
    print(
        f"  • Lists:            JSON={json_struct['lists']:2d} | "
        f"FS={fs_struct['list_directories']:2d}"
    )
    print(f"  • Archived Cards:   {json_struct['archived_cards']} (not cloned - expected)")
    print(f"  • Labels:           {json_struct['labels']} available")
    print(f"  • Members:          {json_struct['members']} members")

    # Content richness
    print("\n📝 Content Analysis:")
    content = analysis["content_coverage"]
    print(
        f"  • Cards with descriptions: "
        f"{content['cards_with_content']}/{json_struct['total_cards']} "
        f"({content['content_rich_ratio']:.1%})"
    )
    print(
        f"  • Cards with labels:       "
        f"{content['cards_with_labels']}/{json_struct['total_cards']} "
        f"({content['label_usage_ratio']:.1%})"
    )

    # Efficiency insights
    print("\n✨ Efficiency Insights:")

    active_card_efficiency = fs_struct["card_files"] / max(json_struct["active_cards"], 1)
    print(f"  • Active card coverage:    {active_card_efficiency:.1%}")

    if json_struct["archived_cards"] > 0:
        print(
            f"  • Space saved by filtering archived: "
            f"{json_struct['archived_cards']} cards not stored"
        )

    # Check for rich content
    if content["content_rich_ratio"] > 0.3:
        print(
            f"  • High content richness:   "
            f"{content['content_rich_ratio']:.1%} of cards have descriptions"
        )

    if content["label_usage_ratio"] > 0.2:
        print(
            f"  • Good label organization: "
            f"{content['label_usage_ratio']:.1%} of cards are labeled"
        )

    # JSON vs Filesystem advantages
    print("\n⚖️  Comparison Summary:")
    print("  📦 JSON Export Advantages:")
    print("     • Complete historical data (activities, comments)")
    print("     • Single file for easy backup/transfer")
    print("     • Includes archived cards and system metadata")

    print("  📁 Filesystem Representation Advantages:")
    print("     • Human-readable markdown files")
    print("     • Git-friendly version control")
    print("     • Individual file editing capability")
    print("     • Hierarchical directory structure")
    print("     • Filtered to active content only")


def main():
    """Main analysis function."""
    if len(sys.argv) != 3:
        print("Usage: python analyze_export_efficiency.py <export.json> <board_dir>")
        sys.exit(1)

    export_path = Path(sys.argv[1])
    board_dir = Path(sys.argv[2])

    if not export_path.exists():
        print(f"Export file not found: {export_path}")
        sys.exit(1)

    if not board_dir.exists():
        print(f"Board directory not found: {board_dir}")
        sys.exit(1)

    # Load and analyze
    print("Loading data...")
    with open(export_path, encoding="utf-8") as f:
        json_data = json.load(f)

    sizes = get_file_sizes(export_path, board_dir)
    analysis = analyze_content_structure(json_data, board_dir)

    # Generate report
    print_efficiency_report(sizes, analysis, json_data.get("title", "Unknown Board"))


if __name__ == "__main__":
    main()
