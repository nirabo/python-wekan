"""WeKan filesystem push commands."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from wekan.cli.config import load_config
from wekan.filesystem.pusher import WekanPusher
from wekan.filesystem.utils import read_json_file
from wekan.wekan_client import WekanClient

app = typer.Typer(help="Push filesystem changes back to WeKan boards")
console = Console()


def find_board_id(board_dir: Path) -> Optional[str]:
    """Find the board ID from the cloned board directory."""
    # Look for export file first
    for export_file in board_dir.glob("export-board-*.json"):
        try:
            export_data = read_json_file(export_file)
            if export_data and "_id" in export_data:
                return export_data["_id"]
        except Exception:  # nosec B112
            continue

    # Look in board metadata
    metadata_path = board_dir / ".wekan-board" / "config.md"
    if metadata_path.exists():
        try:
            with open(metadata_path, encoding="utf-8") as f:
                content = f.read()
                # Extract ID from markdown config
                for line in content.split("\n"):
                    if line.startswith("**ID:**"):
                        # Extract ID from line like "**ID:** `c9GQbri46ub3nbivP`"
                        parts = line.split("`")
                        if len(parts) >= 2:
                            return parts[1]
        except Exception:  # nosec B110
            pass

    return None


def get_client_from_config() -> WekanClient:
    """Get authenticated WeKan client from configuration."""
    try:
        config = load_config()
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        console.print("\n[yellow]Run 'wekan config init' to set up your configuration.[/yellow]")
        raise typer.Exit(1)

    # Validate required configuration
    if not config.base_url or not config.username or not config.password:
        console.print("[red]Configuration incomplete![/red]")
        console.print("\n[yellow]Missing required configuration:[/yellow]")
        if not config.base_url:
            console.print("  • base_url")
        if not config.username:
            console.print("  • username")
        if not config.password:
            console.print("  • password")
        console.print(
            "\n[cyan]Run 'wekan config init <url> <username> <password>' to configure.[/cyan]"
        )
        raise typer.Exit(1)

    try:
        return WekanClient(
            base_url=config.base_url, username=config.username, password=config.password
        )
    except Exception as e:
        console.print(f"[red]Failed to connect to WeKan server: {e}[/red]")
        raise typer.Exit(1)


@app.command("board")
def push_board(
    board_path: str = typer.Argument(".", help="Path to cloned board directory"),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Show changes without applying them"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
    board_id: Optional[str] = typer.Option(
        None, "--board-id", help="Explicit board ID (auto-detected if not provided)"
    ),
) -> None:
    """Push filesystem changes back to WeKan board.

    Examples:
        wekan push board                                    # Push current directory
        wekan push board ./AI_Engineering                   # Push specific board
        wekan push board --dry-run                         # Preview changes only
        wekan push board --force                           # Skip confirmation
        wekan push board --board-id c9GQbri46ub3nbivP      # Explicit board ID
    """
    board_dir = Path(board_path).resolve()

    if not board_dir.exists():
        console.print(f"[red]Board directory not found: {board_dir}[/red]")
        raise typer.Exit(1)

    if not board_dir.is_dir():
        console.print(f"[red]Path is not a directory: {board_dir}[/red]")
        raise typer.Exit(1)

    # Auto-detect board ID if not provided
    if not board_id:
        board_id = find_board_id(board_dir)
        if not board_id:
            console.print(f"[red]Could not determine board ID from {board_dir}[/red]")
            console.print("\n[yellow]Try one of:[/yellow]")
            console.print("  • Use --board-id to specify explicit board ID")
            console.print("  • Ensure directory contains .wekan-board metadata")
            console.print("  • Ensure directory contains export-board-*.json file")
            raise typer.Exit(1)

    console.print(f"[blue]Board directory:[/blue] {board_dir}")
    console.print(f"[blue]Board ID:[/blue] {board_id}")

    # Get WeKan client
    client = get_client_from_config()

    # Create pusher and push
    pusher = WekanPusher(console)
    success = pusher.push_board(
        board_dir=board_dir, client=client, board_id=board_id, dry_run=dry_run, force=force
    )

    if success:
        if dry_run:
            console.print("\n[green]✓ Dry run completed successfully[/green]")
        else:
            console.print("\n[green]✓ Push completed successfully![/green]")
    else:
        console.print("\n[red]✗ Push failed[/red]")
        raise typer.Exit(1)


@app.command("status")
def push_status(
    board_path: str = typer.Argument(".", help="Path to cloned board directory"),
    board_id: Optional[str] = typer.Option(
        None, "--board-id", help="Explicit board ID (auto-detected if not provided)"
    ),
) -> None:
    """Show status of filesystem vs. WeKan server (like git status).

    Examples:
        wekan push status                                   # Show status for current directory
        wekan push status ./AI_Engineering                  # Show status for specific board
        wekan push status --board-id c9GQbri46ub3nbivP      # Explicit board ID
    """
    board_dir = Path(board_path).resolve()

    if not board_dir.exists():
        console.print(f"[red]Board directory not found: {board_dir}[/red]")
        raise typer.Exit(1)

    # Auto-detect board ID if not provided
    if not board_id:
        board_id = find_board_id(board_dir)
        if not board_id:
            console.print(f"[red]Could not determine board ID from {board_dir}[/red]")
            raise typer.Exit(1)

    console.print(f"[blue]Board directory:[/blue] {board_dir}")
    console.print(f"[blue]Board ID:[/blue] {board_id}")

    # Get WeKan client
    client = get_client_from_config()

    # Create pusher and detect changes
    pusher = WekanPusher(console)
    changes = pusher.detect_changes(board_dir, client, board_id)

    # Show changes preview
    has_changes = pusher.show_changes_preview(changes)

    if has_changes:
        console.print(
            f"\n[yellow]💡 Run 'wekan push board {board_path}' to apply these changes[/yellow]"
        )
    else:
        console.print("\n[green]✓ Board is up to date![/green]")


@app.command("diff")
def push_diff(
    board_path: str = typer.Argument(".", help="Path to cloned board directory"),
    board_id: Optional[str] = typer.Option(
        None, "--board-id", help="Explicit board ID (auto-detected if not provided)"
    ),
) -> None:
    """Show detailed differences between filesystem and WeKan server.

    Examples:
        wekan push diff                                     # Show diff for current directory
        wekan push diff ./AI_Engineering                    # Show diff for specific board
    """
    # For now, this is the same as status - we could enhance it later with detailed diffs
    push_status(board_path, board_id)


if __name__ == "__main__":
    app()
