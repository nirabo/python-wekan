"""Filesystem models for WeKan entities."""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

import yaml

from wekan.board import Board
from wekan.card import WekanCard
from wekan.filesystem.utils import (
    ensure_directory,
    host_from_url,
    read_json_file,
    read_markdown_file,
    sanitize_filename,
    write_json_file,
    write_markdown_file,
)
from wekan.wekan_client import WekanClient
from wekan.wekan_list import WekanList


class WekanHost:
    """Represents a WeKan host in the filesystem."""

    def __init__(self, base_path: Path, base_url: str, client: Optional[WekanClient] = None):
        self.base_path = Path(base_path)
        self.base_url = base_url
        self.client = client
        self.host_name = host_from_url(base_url)
        self.host_path = self.base_path / self.host_name
        self.metadata_path = self.host_path / ".wekan-host"

    def ensure_structure(self) -> None:
        """Create the host directory structure."""
        ensure_directory(self.host_path)
        ensure_directory(self.metadata_path)

    def save_config(self) -> None:
        """Save host configuration."""
        self.ensure_structure()

        config_content = f"""# WeKan Host Configuration

**Base URL:** {self.base_url}
**Last Sync:** {datetime.utcnow().isoformat()}Z
**Default User:** {self.client.username if self.client else 'unknown'}

## Connection Settings
- API Version: v7.42
- Timeout: 30s
- SSL Verify: true

## Statistics
- Total Boards: TBD
- Active Users: TBD
- Last Health Check: {datetime.utcnow().isoformat()}Z ✓
"""

        config_path = self.metadata_path / "config.md"
        write_markdown_file(config_path, config_content)

        # Also save users cache
        if self.client:
            try:
                users = self.client.get_users()
                users_data = []
                for user in users:
                    users_data.append(
                        {
                            "id": user.id,
                            "username": user.username,
                            "emails": user.emails,
                            "profile": user.profile,
                            "is_admin": user.is_admin,
                        }
                    )
                write_json_file(self.metadata_path / "users.json", users_data)
            except Exception:  # nosec B110
                pass  # Skip if we don't have permissions

    def list_boards(self) -> list["WekanBoardFS"]:
        """List all board directories in this host."""
        boards = []
        if not self.host_path.exists():
            return boards

        for item in self.host_path.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                board = WekanBoardFS(self, item.name)
                boards.append(board)

        return boards


class WekanBoardFS:
    """Represents a WeKan board in the filesystem."""

    def __init__(
        self, host: WekanHost, board_name_or_path: Union[str, Path], board: Optional[Board] = None
    ):
        self.host = host
        self.board = board

        if isinstance(board_name_or_path, Path):
            self.board_path = board_name_or_path
            self.board_name = board_name_or_path.name
        else:
            self.board_name = sanitize_filename(board_name_or_path)
            self.board_path = host.host_path / self.board_name

        self.metadata_path = self.board_path / ".wekan-board"

    def ensure_structure(self) -> None:
        """Create the board directory structure."""
        ensure_directory(self.board_path)
        ensure_directory(self.metadata_path)

    def save_metadata(self) -> None:
        """Save board metadata."""
        if not self.board:
            return

        self.ensure_structure()

        # Save main board config
        config_content = f"""# {self.board.title}

**ID:** `{self.board.id}`
**Slug:** {self.board.slug}
**Color:** {self.board.color}
**Permission:** {self.board.permission}
**Created:** {self.board.created_at.isoformat()}Z
**Modified:** {self.board.modified_at.isoformat()}Z

## Settings
- Subtasks Enabled: {self.board.allow_subtasks}
- Comments Enabled: {self.board.allows_comments}
- Attachments Enabled: {self.board.allows_attachments}
- Card Numbers Enabled: {self.board.allows_card_number}

## Swimlanes
"""

        # Add swimlanes info
        try:
            swimlanes = self.board.list_swimlanes()
            for swimlane in swimlanes:
                config_content += f"- {swimlane.title}: `{swimlane.id}`\n"
        except Exception:
            config_content += "- Default: TBD\n"

        write_markdown_file(self.metadata_path / "config.md", config_content)

        # Save labels
        try:
            labels = self.board.get_labels()
            labels_data = []
            for label in labels:
                labels_data.append({"id": label.id, "name": label.name, "color": label.color})
            write_json_file(self.metadata_path / "labels.json", labels_data)
        except Exception:
            write_json_file(self.metadata_path / "labels.json", [])

        # Save custom fields
        try:
            fields = self.board.list_custom_fields()
            fields_data = []
            for field in fields:
                fields_data.append(
                    {
                        "id": field.id,
                        "name": field.name,
                        "type": field.type,
                        "settings": field.settings,
                        "show_on_card": field.show_on_card,
                    }
                )
            write_json_file(self.metadata_path / "custom-fields.json", fields_data)
        except Exception:
            write_json_file(self.metadata_path / "custom-fields.json", [])

        # Save integrations
        try:
            integrations = self.board.list_integrations()
            integrations_data = []
            for integration in integrations:
                integrations_data.append(
                    {
                        "id": integration.id,
                        "title": integration.title,
                        "url": integration.url,
                        "enabled": integration.enabled,
                    }
                )
            write_json_file(self.metadata_path / "integrations.json", integrations_data)
        except Exception:
            write_json_file(self.metadata_path / "integrations.json", [])

        # Save members
        try:
            members = self.board.get_members()
            write_json_file(self.metadata_path / "members.json", members)
        except Exception:
            write_json_file(self.metadata_path / "members.json", [])

    def list_lists(self) -> list["WekanListFS"]:
        """List all list directories in this board."""
        lists = []
        if not self.board_path.exists():
            return lists

        for item in self.board_path.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                list_fs = WekanListFS(self, item.name)
                lists.append(list_fs)

        return lists


class WekanListFS:
    """Represents a WeKan list in the filesystem."""

    def __init__(
        self,
        board_fs: WekanBoardFS,
        list_name_or_path: Union[str, Path],
        wekan_list: Optional[WekanList] = None,
    ):
        self.board_fs = board_fs
        self.wekan_list = wekan_list

        if isinstance(list_name_or_path, Path):
            self.list_path = list_name_or_path
            self.list_name = list_name_or_path.name
        else:
            self.list_name = sanitize_filename(list_name_or_path)
            self.list_path = board_fs.board_path / self.list_name

        self.metadata_path = self.list_path / ".wekan-list"

    def ensure_structure(self) -> None:
        """Create the list directory structure."""
        ensure_directory(self.list_path)
        ensure_directory(self.metadata_path)

    def save_metadata(self) -> None:
        """Save list metadata."""
        if not self.wekan_list:
            return

        self.ensure_structure()

        config_content = f"""# {self.wekan_list.title}

**ID:** `{self.wekan_list.id}`
**Sort Order:** {getattr(self.wekan_list, 'sort', 'N/A')}
**Color:** {self.wekan_list.color}
**WIP Limit:** {self.wekan_list.wip_limit}
**Swimlane:** `{self.wekan_list.swimlane_id}` (Default)

**Created:** {self.wekan_list.created_at.isoformat()}Z
**Updated:** {self.wekan_list.updated_at.isoformat()}Z
"""

        write_markdown_file(self.metadata_path / "config.md", config_content)

    def list_cards(self) -> list["WekanCardFS"]:
        """List all card files in this list."""
        cards = []
        if not self.list_path.exists():
            return cards

        for item in self.list_path.iterdir():
            if item.is_file() and item.suffix == ".md" and not item.name.startswith("."):
                card = WekanCardFS(self, item)
                cards.append(card)

        return cards


class WekanCardFS:
    """Represents a WeKan card as a markdown file."""

    def __init__(
        self,
        list_fs: WekanListFS,
        card_path_or_name: Union[Path, str],
        card: Optional[WekanCard] = None,
    ):
        self.list_fs = list_fs
        self.card = card

        if isinstance(card_path_or_name, Path):
            self.card_path = card_path_or_name
            self.card_name = card_path_or_name.stem
        else:
            self.card_name = sanitize_filename(card_path_or_name)
            self.card_path = list_fs.list_path / f"{self.card_name}.md"

    def save_content(self) -> None:
        """Save card content as markdown with YAML frontmatter."""
        if not self.card:
            return

        # Prepare frontmatter
        frontmatter = {
            "id": self.card.id,
            "title": self.card.title,
            "card_number": self.card.card_number,
            "swimlane_id": self.card.swimlane_id,
            "sort": self.card.sort,
            "archived": self.card.archived,
            "created_at": self.card.created_at.isoformat() + "Z",
            "modified_at": self.card.modified_at.isoformat() + "Z",
        }

        # Add optional fields
        if self.card.due_at:
            frontmatter["due_at"] = self.card.due_at.isoformat() + "Z"

        if self.card.label_ids:
            # Convert label IDs to names using board metadata
            labels_data = read_json_file(self.list_fs.board_fs.metadata_path / "labels.json")
            if labels_data:
                label_names = []
                for label_id in self.card.label_ids:
                    for label in labels_data:
                        if label["id"] == label_id:
                            label_names.append(label["name"])
                            break
                if label_names:
                    frontmatter["labels"] = label_names

        if self.card.members:
            # Convert member IDs to usernames using host metadata
            users_data = read_json_file(self.list_fs.board_fs.host.metadata_path / "users.json")
            if users_data:
                member_names = []
                for member_id in self.card.members:
                    for user in users_data:
                        if user["id"] == member_id:
                            member_names.append(user["username"])
                            break
                if member_names:
                    frontmatter["members"] = member_names

        if self.card.assignees:
            # Convert assignee IDs to usernames
            users_data = read_json_file(self.list_fs.board_fs.host.metadata_path / "users.json")
            if users_data:
                assignee_names = []
                for assignee_id in self.card.assignees:
                    for user in users_data:
                        if user["id"] == assignee_id:
                            assignee_names.append(user["username"])
                            break
                if assignee_names:
                    frontmatter["assignees"] = assignee_names

        if self.card.custom_fields:
            frontmatter["custom_fields"] = self.card.custom_fields

        # Build content
        content_parts = []

        # Add YAML frontmatter
        content_parts.append("---")
        content_parts.append(yaml.dump(frontmatter, default_flow_style=False).strip())
        content_parts.append("---")
        content_parts.append("")

        # Add title
        content_parts.append(f"# {self.card.title}")
        content_parts.append("")

        # Add description
        if self.card.description:
            content_parts.append("## Description")
            content_parts.append(self.card.description)
            content_parts.append("")

        # Add checklists
        try:
            checklists = self.card.get_checklists()
            if checklists:
                content_parts.append("## Checklists")
                content_parts.append("")

                for checklist in checklists:
                    content_parts.append(f"### {checklist.title}")
                    checklist_items = checklist.list_checklists()
                    for item in checklist_items:
                        status = "x" if item.is_finished else " "
                        content_parts.append(f"- [{status}] {item.title}")
                    content_parts.append("")
        except Exception:  # nosec B110
            pass  # Skip if checklists are not accessible

        # Add comments
        try:
            comments = self.card.get_comments()
            if comments:
                content_parts.append("## Comments")
                content_parts.append("")

                users_data = read_json_file(self.list_fs.board_fs.host.metadata_path / "users.json")

                for comment in comments:
                    # Find username
                    author = "Unknown"
                    if users_data:
                        for user in users_data:
                            if user["id"] == comment.get("userId"):
                                author = user["username"]
                                break

                    timestamp = comment.get("createdAt", "")
                    if timestamp:
                        timestamp = f" - {timestamp}"

                    content_parts.append(f"### {author}{timestamp}")
                    content_parts.append(comment.get("text", ""))
                    content_parts.append("")
        except Exception:  # nosec B110
            pass  # Skip if comments are not accessible

        # Write the file
        final_content = "\n".join(content_parts)
        write_markdown_file(self.card_path, final_content)

    def load_content(self) -> Optional[dict[str, Any]]:
        """Load card content and parse frontmatter."""
        content = read_markdown_file(self.card_path)
        if not content:
            return None

        # Parse frontmatter
        if content.startswith("---\n"):
            try:
                parts = content.split("---\n", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1])
                    body = parts[2].strip()
                    return {"frontmatter": frontmatter, "body": body}
            except yaml.YAMLError:
                pass

        return {"frontmatter": {}, "body": content}
