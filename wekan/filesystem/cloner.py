"""WeKan cloning functionality for filesystem representation."""

import re
from pathlib import Path
from typing import Optional, Union

from rich.console import Console
from rich.progress import Progress, TaskID

from wekan.board import Board
from wekan.filesystem.models import WekanBoardFS, WekanCardFS, WekanHost, WekanListFS
from wekan.filesystem.utils import sanitize_filename
from wekan.wekan_client import WekanClient


class WekanCloner:
    """Handles cloning WeKan instances to filesystem representation."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    def clone_host(
        self,
        base_url: str,
        username: str,
        password: str,
        output_dir: Union[str, Path] = "wekan-repos",
        board_filter: Optional[str] = None,
    ) -> WekanHost:
        """Clone an entire WeKan host or specific boards."""
        self.console.print(f"[bold blue]Cloning WeKan host: {base_url}[/bold blue]")

        # Connect to WeKan
        client = WekanClient(base_url, username, password)

        # Create host representation
        host = WekanHost(Path(output_dir), base_url, client)
        host.save_config()

        self.console.print(f"[green]✓[/green] Connected to {base_url}")

        # Get boards
        try:
            all_boards = client.list_boards()

            # Apply filter if provided
            if board_filter:
                # Support board ID, index, or name matching
                filtered_boards = []

                # Try as index first
                try:
                    index = int(board_filter)
                    if 0 <= index < len(all_boards):
                        filtered_boards = [all_boards[index]]
                except ValueError:
                    # Try as ID or name pattern
                    for board in all_boards:
                        if board.id == board_filter or re.search(
                            board_filter, board.title, re.IGNORECASE
                        ):
                            filtered_boards.append(board)

                if not filtered_boards:
                    self.console.print(
                        f"[red]✗[/red] No boards found matching filter: {board_filter}"
                    )
                    return host

                boards = filtered_boards
                self.console.print(f"[yellow]Filtered to {len(boards)} board(s)[/yellow]")
            else:
                boards = all_boards

            self.console.print(f"[green]✓[/green] Found {len(boards)} board(s) to clone")

            # Clone each board
            with Progress() as progress:
                main_task = progress.add_task("[cyan]Cloning boards...", total=len(boards))

                for board in boards:
                    self._clone_board(host, board, progress, main_task)
                    progress.advance(main_task)

            self.console.print(
                f"[bold green]✓ Successfully cloned {len(boards)} board(s) "
                f"to {host.host_path}[/bold green]"
            )

        except Exception as e:
            self.console.print(f"[red]✗ Error cloning host: {e}[/red]")
            raise

        return host

    def _clone_board(
        self, host: WekanHost, board: Board, progress: Progress, main_task: TaskID
    ) -> WekanBoardFS:
        """Clone a single board."""
        board_name = sanitize_filename(board.title)
        progress.print(f"[blue]Cloning board: {board.title}[/blue]")

        # Create board filesystem representation
        board_fs = WekanBoardFS(host, board_name, board)
        board_fs.save_metadata()

        # Get lists
        try:
            lists = board.get_lists()

            if not lists:
                progress.print(f"[yellow]  No lists found in board: {board.title}[/yellow]")
                return board_fs

            # Clone each list
            list_task = progress.add_task(f"[green]  Lists in {board.title}...", total=len(lists))

            for wekan_list in lists:
                self._clone_list(board_fs, wekan_list, progress, list_task)
                progress.advance(list_task)

            progress.remove_task(list_task)
            progress.print(f"[green]✓ Cloned {len(lists)} list(s) from {board.title}[/green]")

        except Exception as e:
            progress.print(f"[red]✗ Error cloning lists from {board.title}: {e}[/red]")

        return board_fs

    def _clone_list(
        self, board_fs: WekanBoardFS, wekan_list, progress: Progress, list_task: TaskID
    ) -> WekanListFS:
        """Clone a single list."""
        list_name = sanitize_filename(wekan_list.title)

        # Create list filesystem representation
        list_fs = WekanListFS(board_fs, list_name, wekan_list)
        list_fs.save_metadata()

        # Get cards
        try:
            cards = wekan_list.get_cards()

            if not cards:
                return list_fs

            progress.print(f"[dim]    Cloning {len(cards)} card(s) from {wekan_list.title}[/dim]")

            # Clone each card
            for card in cards:
                self._clone_card(list_fs, card)

        except Exception as e:
            progress.print(f"[red]    ✗ Error cloning cards from {wekan_list.title}: {e}[/red]")

        return list_fs

    def _clone_card(self, list_fs: WekanListFS, card) -> WekanCardFS:
        """Clone a single card."""
        # Generate safe filename from card title and number
        if hasattr(card, "card_number") and card.card_number:
            card_name = f"{card.card_number:03d}-{sanitize_filename(card.title)}"
        else:
            card_name = sanitize_filename(card.title)

        # Create card filesystem representation
        card_fs = WekanCardFS(list_fs, card_name, card)
        card_fs.save_content()

        return card_fs

    def sync_board(self, host: WekanHost, board_identifier: str, direction: str = "pull") -> None:
        """Sync a specific board (future implementation)."""
        # TODO: Implement bidirectional sync
        # For now, this is a placeholder for future push/pull functionality
        self.console.print("[yellow]Sync functionality not yet implemented[/yellow]")
        self.console.print(
            f"[dim]Would sync board {board_identifier} in {direction} direction[/dim]"
        )
