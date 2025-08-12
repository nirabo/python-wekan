"""WeKan filesystem clone commands."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from wekan.filesystem.cloner import WekanCloner

app = typer.Typer(help="Clone WeKan boards to filesystem representation")
console = Console()


@app.command("host")
def clone_host(
    base_url: str = typer.Argument(help="WeKan server URL"),
    username: str = typer.Argument(help="Username for authentication"),
    password: str = typer.Argument(help="Password for authentication"),
    output_dir: str = typer.Option(
        "wekan-repos", "--output", "-o", help="Output directory for cloned data"
    ),
    board: Optional[str] = typer.Option(
        None, "--board", "-b", help="Specific board ID, index, or name pattern to clone"
    ),
) -> None:
    """Clone a WeKan host with all boards (or specific board) to filesystem.

    Examples:
        wekan clone host https://wekan.example.com admin password
        wekan clone host https://wekan.example.com admin password --board "Project Alpha"
        wekan clone host https://wekan.example.com admin password --board 0  # First board
        wekan clone host https://wekan.example.com admin password --board 64a1b2c3d4e5f6789012345
    """
    try:
        cloner = WekanCloner(console)
        host = cloner.clone_host(
            base_url=base_url,
            username=username,
            password=password,
            output_dir=output_dir,
            board_filter=board,
        )

        console.print("\n[bold green]Clone completed successfully![/bold green]")
        console.print(f"[dim]Data saved to: {host.host_path}[/dim]")

        # Show next steps
        console.print("\n[bold cyan]Next steps:[/bold cyan]")
        console.print(f"• cd {host.host_path}")
        console.print("• ls -la  # Explore the cloned structure")
        console.print("• Find cards: find . -name '*.md' -not -path '*/.*'")
        console.print("• Edit cards with your favorite editor")

    except Exception as e:
        console.print(f"[red]Error during clone: {e}[/red]")
        raise typer.Exit(1)


@app.command("board")
def clone_board(
    base_url: str = typer.Argument(help="WeKan server URL"),
    username: str = typer.Argument(help="Username for authentication"),
    password: str = typer.Argument(help="Password for authentication"),
    board_identifier: str = typer.Argument(help="Board ID, index, or name pattern"),
    output_dir: str = typer.Option(
        "wekan-repos", "--output", "-o", help="Output directory for cloned data"
    ),
) -> None:
    """Clone a specific WeKan board to filesystem.

    Examples:
        wekan clone board https://wekan.example.com admin password "Project Alpha"
        wekan clone board https://wekan.example.com admin password 0  # First board
        wekan clone board https://wekan.example.com admin password 64a1b2c3d4e5f6789012345  # By ID
    """
    try:
        cloner = WekanCloner(console)
        host = cloner.clone_host(
            base_url=base_url,
            username=username,
            password=password,
            output_dir=output_dir,
            board_filter=board_identifier,
        )

        console.print("\n[bold green]Board clone completed successfully![/bold green]")
        console.print(f"[dim]Data saved to: {host.host_path}[/dim]")

    except Exception as e:
        console.print(f"[red]Error during board clone: {e}[/red]")
        raise typer.Exit(1)


@app.command("list")
def list_cloned(
    directory: str = typer.Argument("wekan-repos", help="Directory containing cloned WeKan data")
) -> None:
    """List cloned WeKan hosts and boards.

    Examples:
        wekan clone list
        wekan clone list /path/to/wekan-repos
    """
    base_path = Path(directory)

    if not base_path.exists():
        console.print(f"[red]Directory does not exist: {base_path}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold blue]WeKan repositories in {base_path}:[/bold blue]\n")

    found_any = False
    for host_dir in base_path.iterdir():
        if host_dir.is_dir() and not host_dir.name.startswith("."):
            found_any = True
            console.print(f"[cyan]📡 Host: {host_dir.name}[/cyan]")

            # Look for boards
            board_count = 0
            for board_dir in host_dir.iterdir():
                if board_dir.is_dir() and not board_dir.name.startswith("."):
                    board_count += 1
                    console.print(f"  [green]📋 {board_dir.name}[/green]")

                    # Count lists
                    list_count = 0
                    card_count = 0
                    for list_dir in board_dir.iterdir():
                        if list_dir.is_dir() and not list_dir.name.startswith("."):
                            list_count += 1
                            # Count cards in this list
                            for item in list_dir.iterdir():
                                if item.is_file() and item.suffix == ".md":
                                    card_count += 1

                    if list_count > 0:
                        console.print(f"    [dim]{list_count} list(s), {card_count} card(s)[/dim]")

            if board_count == 0:
                console.print("  [dim](no boards)[/dim]")
            console.print()

    if not found_any:
        console.print("[dim]No WeKan repositories found.[/dim]")
        console.print("\n[yellow]Try running:[/yellow]")
        console.print("  wekan clone host <url> <username> <password>")


if __name__ == "__main__":
    app()
