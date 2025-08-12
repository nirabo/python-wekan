"""
WeKan filesystem pusher - sync filesystem changes back to WeKan server.

This module implements the "git push" equivalent for WeKan boards,
allowing changes made to cloned filesystem representations to be
synchronized back to the WeKan server.
"""

from pathlib import Path
from typing import Optional

import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from wekan.filesystem.utils import sanitize_filename
from wekan.wekan_client import WekanClient


class ChangeType:
    """Types of changes that can be detected."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MOVE = "move"


class CardChange:
    """Represents a change to a card."""

    def __init__(
        self,
        change_type: str,
        card_id: Optional[str] = None,
        file_path: Optional[Path] = None,
        old_data: Optional[dict] = None,
        new_data: Optional[dict] = None,
    ):
        self.change_type = change_type
        self.card_id = card_id
        self.file_path = file_path
        self.old_data = old_data or {}
        self.new_data = new_data or {}

    def __repr__(self):
        if self.change_type == ChangeType.CREATE:
            return f"CREATE: {self.new_data.get('title', 'Unknown')}"
        elif self.change_type == ChangeType.UPDATE:
            return f"UPDATE: {self.card_id} - {self.new_data.get('title', 'Unknown')}"
        elif self.change_type == ChangeType.DELETE:
            return f"DELETE: {self.card_id}"
        elif self.change_type == ChangeType.MOVE:
            return f"MOVE: {self.card_id} to {self.new_data.get('list_name', 'Unknown')}"
        return f"UNKNOWN: {self.change_type}"


class WekanPusher:
    """Synchronizes filesystem changes back to WeKan server."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    def detect_changes(
        self, board_dir: Path, client: WekanClient, board_id: str
    ) -> list[CardChange]:
        """Detect changes between filesystem and WeKan server."""
        self.console.print("[blue]🔍 Detecting changes...[/blue]")

        changes = []

        # Load filesystem state
        fs_cards = self._load_filesystem_cards(board_dir)

        # Load server state
        server_cards = self._load_server_cards(client, board_id)

        # Detect changes
        changes.extend(self._detect_card_changes(fs_cards, server_cards, board_dir))

        return changes

    def _load_filesystem_cards(self, board_dir: Path) -> dict[str, dict]:
        """Load all cards from filesystem representation."""
        cards = {}

        for md_file in board_dir.rglob("*.md"):
            if md_file.name.startswith(".") or "export-board-" in md_file.name:
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
                            # Determine list from directory structure
                            list_name = md_file.parent.name

                            cards[card_id] = {
                                "frontmatter": frontmatter,
                                "body": body,
                                "file_path": md_file,
                                "list_name": list_name,
                                "modified_at_fs": md_file.stat().st_mtime,
                            }
            except Exception as e:
                self.console.print(f"[red]Error reading {md_file}: {e}[/red]")

        return cards

    def _load_server_cards(self, client: WekanClient, board_id: str) -> dict[str, dict]:
        """Load current cards from WeKan server."""
        cards = {}

        try:
            # Get board and its lists
            boards = client.list_boards()
            board = None
            for b in boards:
                if b.id == board_id:
                    board = b
                    break

            if not board:
                self.console.print(f"[red]Board {board_id} not found on server[/red]")
                return cards

            # Get lists
            lists = board.get_lists()
            # list_id_to_name = {l.id: l.title for l in lists}

            # Get all cards
            for list_obj in lists:
                list_cards = list_obj.get_cards()
                for card in list_cards:
                    cards[card.id] = {
                        "card": card,
                        "list_name": sanitize_filename(list_obj.title),
                        "list_id": list_obj.id,
                        "server_modified_at": card.modified_at,
                    }

        except Exception as e:
            self.console.print(f"[red]Error loading server cards: {e}[/red]")

        return cards

    def _detect_card_changes(
        self,
        fs_cards: dict[str, dict],
        server_cards: dict[str, dict],
        board_dir: Path,  # noqa: ARG002
    ) -> list[CardChange]:
        """Detect changes between filesystem and server cards."""
        changes = []

        # Check for updates and moves
        for card_id, fs_card in fs_cards.items():
            if card_id in server_cards:
                server_card = server_cards[card_id]

                # Check for actual content changes (not just timestamps)
                fs_title = fs_card["frontmatter"].get("title", "")
                fs_description = fs_card["body"].strip()
                server_title = server_card["card"].title or ""
                server_description = server_card["card"].description or ""

                # Normalize filesystem description by removing auto-generated title header
                # Our cloner adds "# Title" automatically, so we need to ignore this
                normalized_fs_desc = fs_description
                expected_header = f"# {fs_title}"
                if normalized_fs_desc.startswith(expected_header):
                    # Remove the header and any following empty lines
                    normalized_fs_desc = (
                        normalized_fs_desc[len(expected_header) :].lstrip("\n").strip()
                    )

                # Compare normalized content
                fs_description = normalized_fs_desc

                # Check if content actually changed
                title_changed = fs_title != server_title
                description_changed = fs_description != server_description

                if title_changed or description_changed:
                    # Content actually changed - this is an update
                    changes.append(
                        CardChange(
                            ChangeType.UPDATE,
                            card_id=card_id,
                            file_path=fs_card["file_path"],
                            old_data={
                                "title": server_card["card"].title,
                                "description": server_card["card"].description,
                                "list_name": server_card["list_name"],
                            },
                            new_data={
                                "title": fs_card["frontmatter"].get("title"),
                                "description": fs_card["body"],
                                "list_name": fs_card["list_name"],
                                "frontmatter": fs_card["frontmatter"],
                            },
                        )
                    )

                # Check for moves (different list)
                if fs_card["list_name"] != server_card["list_name"]:
                    changes.append(
                        CardChange(
                            ChangeType.MOVE,
                            card_id=card_id,
                            old_data={"list_name": server_card["list_name"]},
                            new_data={"list_name": fs_card["list_name"]},
                        )
                    )
            else:
                # Card exists in filesystem but not on server - this is a create
                # (or the card was deleted on server, which we'll treat as create for now)
                changes.append(
                    CardChange(
                        ChangeType.CREATE,
                        file_path=fs_card["file_path"],
                        new_data={
                            "title": fs_card["frontmatter"].get("title"),
                            "description": fs_card["body"],
                            "list_name": fs_card["list_name"],
                            "frontmatter": fs_card["frontmatter"],
                        },
                    )
                )

        # Check for deletes (cards on server but not in filesystem)
        for card_id, server_card in server_cards.items():
            if card_id not in fs_cards:
                changes.append(
                    CardChange(
                        ChangeType.DELETE,
                        card_id=card_id,
                        old_data={
                            "title": server_card["card"].title,
                            "list_name": server_card["list_name"],
                        },
                    )
                )

        return changes

    def show_changes_preview(self, changes: list[CardChange]) -> bool:
        """Show a preview of changes and ask for confirmation."""
        if not changes:
            self.console.print("[green]✓ No changes detected - board is up to date![/green]")
            return False

        self.console.print(f"\n[yellow]📋 Found {len(changes)} change(s) to sync:[/yellow]")

        # Group changes by type
        creates = [c for c in changes if c.change_type == ChangeType.CREATE]
        updates = [c for c in changes if c.change_type == ChangeType.UPDATE]
        moves = [c for c in changes if c.change_type == ChangeType.MOVE]
        deletes = [c for c in changes if c.change_type == ChangeType.DELETE]

        if creates:
            self.console.print(f"\n[green]➕ {len(creates)} card(s) to create:[/green]")
            for change in creates:
                title = change.new_data.get("title", "Untitled")
                list_name = change.new_data.get("list_name", "Unknown list")
                self.console.print(f'  • "{title}" in {list_name}')

        if updates:
            self.console.print(f"\n[blue]✏️  {len(updates)} card(s) to update:[/blue]")
            for change in updates:
                title = change.new_data.get("title", "Untitled")
                self.console.print(f'  • "{title}"')

        if moves:
            self.console.print(f"\n[magenta]↔️  {len(moves)} card(s) to move:[/magenta]")
            for change in moves:
                old_list = change.old_data.get("list_name", "Unknown")
                new_list = change.new_data.get("list_name", "Unknown")
                self.console.print(f"  • {change.card_id}: {old_list} → {new_list}")

        if deletes:
            self.console.print(f"\n[red]🗑️  {len(deletes)} card(s) to delete:[/red]")
            for change in deletes:
                title = change.old_data.get("title", "Untitled")
                self.console.print(f'  • "{title}"')

        return True

    def apply_changes(
        self,
        changes: list[CardChange],
        client: WekanClient,
        board_id: str,
        board_dir: Path,  # noqa: ARG002
        dry_run: bool = False,
    ) -> bool:
        """Apply the changes to WeKan server."""
        if not changes:
            return True

        if dry_run:
            self.console.print("\n[yellow]🔍 DRY RUN - No changes will be applied[/yellow]")
            return True

        try:
            # Get board object
            boards = client.list_boards()
            board = None
            for b in boards:
                if b.id == board_id:
                    board = b
                    break

            if not board:
                self.console.print(f"[red]Board {board_id} not found[/red]")
                return False

            # Get lists for reference
            lists = board.get_lists()
            list_name_to_obj = {sanitize_filename(lst.title): lst for lst in lists}

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
            ) as progress:
                task = progress.add_task("Applying changes...", total=len(changes))

                success_count = 0
                for change in changes:
                    try:
                        if change.change_type == ChangeType.CREATE:
                            success = self._apply_create(change, board, list_name_to_obj)
                        elif change.change_type == ChangeType.UPDATE:
                            success = self._apply_update(change, board, list_name_to_obj)
                        elif change.change_type == ChangeType.MOVE:
                            success = self._apply_move(change, board, list_name_to_obj)
                        elif change.change_type == ChangeType.DELETE:
                            success = self._apply_delete(change, board)
                        else:
                            self.console.print(
                                f"[yellow]⚠️  Unknown change type: {change.change_type}[/yellow]"
                            )
                            success = False

                        if success:
                            success_count += 1
                        progress.advance(task)

                    except Exception as e:
                        self.console.print(f"[red]Error applying {change}: {e}[/red]")
                        progress.advance(task)

            self.console.print(
                f"\n[green]✓ Successfully applied {success_count}/{len(changes)} changes[/green]"
            )
            return success_count == len(changes)

        except Exception as e:
            self.console.print(f"[red]Error applying changes: {e}[/red]")
            return False

    def _apply_create(self, change: CardChange, board, list_name_to_obj: dict) -> bool:
        """Apply a card creation."""
        try:
            list_name = change.new_data.get("list_name")
            if list_name not in list_name_to_obj:
                self.console.print(f"[red]list '{list_name}' not found[/red]")
                return False

            target_list = list_name_to_obj[list_name]

            # Get swimlanes (use default for now)
            swimlanes = board.list_swimlanes()
            default_swimlane = swimlanes[0] if swimlanes else None

            if not default_swimlane:
                self.console.print("[red]No swimlanes found[/red]")
                return False

            # Create the card
            card = target_list.add_card(
                title=change.new_data.get("title", "Untitled"),
                swimlane=default_swimlane,
                description=change.new_data.get("description", ""),
            )

            self.console.print(f"[green]✓ Created card: {card.title}[/green]")
            return True

        except Exception as e:
            self.console.print(f"[red]Failed to create card: {e}[/red]")
            return False

    def _apply_update(
        self, change: CardChange, board, list_name_to_obj: dict
    ) -> bool:  # noqa: ARG002
        """Apply a card update."""
        try:
            # Find the card
            card = self._find_card_by_id(board, change.card_id)
            if not card:
                self.console.print(f"[red]Card {change.card_id} not found[/red]")
                return False

            # Update the card
            card.edit(
                title=change.new_data.get("title"),
                description=change.new_data.get("description", ""),
            )

            self.console.print(f"[green]✓ Updated card: {card.title}[/green]")
            return True

        except Exception as e:
            self.console.print(f"[red]Failed to update card: {e}[/red]")
            return False

    def _apply_move(self, change: CardChange, board, list_name_to_obj: dict) -> bool:
        """Apply a card move."""
        try:
            # Find the card
            card = self._find_card_by_id(board, change.card_id)
            if not card:
                self.console.print(f"[red]Card {change.card_id} not found[/red]")
                return False

            # Find target list
            target_list_name = change.new_data.get("list_name")
            if target_list_name not in list_name_to_obj:
                self.console.print(f"[red]Target list '{target_list_name}' not found[/red]")
                return False

            target_list = list_name_to_obj[target_list_name]

            # Move the card
            card.edit(new_list=target_list)

            old_list = change.old_data.get("list_name", "Unknown")
            self.console.print(f"[green]✓ Moved card from {old_list} to {target_list_name}[/green]")
            return True

        except Exception as e:
            self.console.print(f"[red]Failed to move card: {e}[/red]")
            return False

    def _apply_delete(self, change: CardChange, board) -> bool:
        """Apply a card deletion."""
        try:
            # Find the card
            card = self._find_card_by_id(board, change.card_id)
            if not card:
                self.console.print(f"[yellow]Card {change.card_id} already deleted[/yellow]")
                return True

            # Archive the card (safer than delete)
            card.archive()

            title = change.old_data.get("title", "Unknown")
            self.console.print(f"[green]✓ Archived card: {title}[/green]")
            return True

        except Exception as e:
            self.console.print(f"[red]Failed to archive card: {e}[/red]")
            return False

    def _find_card_by_id(self, board, card_id: Optional[str]):
        """Find a card by ID in the board."""
        if not card_id:
            return None
        try:
            lists = board.get_lists()
            for list_obj in lists:
                cards = list_obj.get_cards()
                for card in cards:
                    if card.id == card_id:
                        return card
        except Exception:  # nosec B110
            pass
        return None

    def push_board(
        self,
        board_dir: Path,
        client: WekanClient,
        board_id: str,
        dry_run: bool = False,
        force: bool = False,
    ) -> bool:
        """Push filesystem changes to WeKan server."""
        self.console.print(f"\n[blue]🚀 Pushing changes to WeKan board {board_id}[/blue]")

        # Detect changes
        changes = self.detect_changes(board_dir, client, board_id)

        # Show preview
        has_changes = self.show_changes_preview(changes)
        if not has_changes:
            return True

        # Confirm with user (unless force)
        if not force and not dry_run:
            confirm = self.console.input("\n[yellow]Apply these changes? (y/N): [/yellow]")
            if confirm.lower() != "y":
                self.console.print("[yellow]Push cancelled[/yellow]")
                return False

        # Apply changes
        return self.apply_changes(changes, client, board_id, board_dir, dry_run)
