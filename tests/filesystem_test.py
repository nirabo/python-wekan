"""Tests for filesystem functionality."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wekan.filesystem.cloner import WekanCloner
from wekan.filesystem.models import WekanBoardFS, WekanCardFS, WekanHost, WekanListFS
from wekan.filesystem.utils import host_from_url, read_json_file, sanitize_filename, write_json_file


class TestUtils:
    """Test filesystem utility functions."""

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        assert sanitize_filename("Project: Alpha/Beta") == "Project_Alpha_Beta"
        assert (
            sanitize_filename("Test<>File") == "Test_File"
        )  # Multiple invalid chars become single _
        assert sanitize_filename("   Multiple   Spaces   ") == "Multiple_Spaces"
        assert sanitize_filename("") == "untitled"
        assert sanitize_filename("a" * 250) == "a" * 200

    def test_host_from_url(self):
        """Test host directory naming from URLs."""
        assert host_from_url("https://wekan.example.com") == "wekan.example.com"
        assert host_from_url("http://localhost:8080") == "localhost_8080"  # : becomes _ in filename
        assert (
            host_from_url("https://wekan.example.com:3000") == "wekan.example.com_3000"
        )  # : becomes _ in filename

    def test_json_file_operations(self):
        """Test JSON file read/write operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            file_path = temp_path / "test.json"

            test_data = {"key": "value", "number": 42}

            # Test write
            write_json_file(file_path, test_data)
            assert file_path.exists()

            # Test read
            loaded_data = read_json_file(file_path)
            assert loaded_data == test_data

            # Test read non-existent file
            assert read_json_file(temp_path / "nonexistent.json") is None


class TestWekanHost:
    """Test WekanHost filesystem representation."""

    def test_host_initialization(self):
        """Test host initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            host = WekanHost(base_path=temp_dir, base_url="https://wekan.example.com:8080")

            assert host.host_name == "wekan.example.com_8080"  # : becomes _ in filename
            assert str(host.host_path).endswith("wekan.example.com_8080")

    def test_host_structure_creation(self):
        """Test host directory structure creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            host = WekanHost(base_path=temp_dir, base_url="https://wekan.example.com")

            host.ensure_structure()

            assert host.host_path.exists()
            assert host.metadata_path.exists()
            assert (host.metadata_path / ".").exists()  # Verify it's a directory


class TestWekanBoardFS:
    """Test WekanBoardFS filesystem representation."""

    def test_board_initialization(self):
        """Test board initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            host = WekanHost(temp_dir, "https://wekan.example.com")
            board_fs = WekanBoardFS(host, "Test Board")

            assert board_fs.board_name == "Test_Board"
            assert str(board_fs.board_path).endswith("Test_Board")

    def test_board_structure_creation(self):
        """Test board directory structure creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            host = WekanHost(temp_dir, "https://wekan.example.com")
            board_fs = WekanBoardFS(host, "Test Board")

            board_fs.ensure_structure()

            assert board_fs.board_path.exists()
            assert board_fs.metadata_path.exists()


class TestWekanCardFS:
    """Test WekanCardFS filesystem representation."""

    def test_card_filename_generation(self):
        """Test card filename generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            host = WekanHost(temp_dir, "https://wekan.example.com")
            board_fs = WekanBoardFS(host, "Test Board")
            list_fs = WekanListFS(board_fs, "Test List")

            # Test with card number
            card_fs = WekanCardFS(list_fs, "Test Card")
            assert card_fs.card_name == "Test_Card"
            assert card_fs.card_path.name == "Test_Card.md"


class TestWekanCloner:
    """Test WekanCloner functionality."""

    @patch("wekan.filesystem.cloner.WekanClient")
    def test_cloner_initialization(self, mock_client_class):
        """Test cloner initialization."""
        cloner = WekanCloner()
        assert cloner.console is not None

    @patch("wekan.filesystem.cloner.WekanClient")
    def test_board_filtering(self, mock_client_class):
        """Test board filtering functionality."""
        # Create mock client and boards
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Create mock boards
        mock_board1 = MagicMock()
        mock_board1.id = "board1"
        mock_board1.title = "Project Alpha"

        mock_board2 = MagicMock()
        mock_board2.id = "board2"
        mock_board2.title = "Project Beta"

        mock_client.list_boards.return_value = [mock_board1, mock_board2]

        cloner = WekanCloner()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Test filtering by name pattern
            host = cloner.clone_host(
                base_url="https://test.com",
                username="test",
                password="test",  # pragma: allowlist secret
                output_dir=temp_dir,
                board_filter="Alpha",
            )

            assert host.host_path.exists()


class TestConfiguredCloning:
    """Test configuration-based cloning functionality."""

    @patch("wekan.filesystem.cloner.WekanClient")
    @patch("wekan.cli.commands.clone.load_config")
    def test_configured_clone_success(self, mock_load_config, mock_client_class):
        """Test successful configured cloning."""
        from wekan.cli.commands.clone import clone_configured

        # Mock configuration
        mock_config = MagicMock()
        mock_config.base_url = "https://test.com"
        mock_config.username = "test_user"
        mock_config.password = "test_pass"  # pragma: allowlist secret
        mock_load_config.return_value = mock_config

        # Mock client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_boards.return_value = []

        with tempfile.TemporaryDirectory() as temp_dir:
            # This would normally be called via CLI, but we test the logic
            # Test the function directly by calling it with mocked typer context
            with patch("wekan.cli.commands.clone.typer.Exit"):
                clone_configured(output_dir=temp_dir, board=None)
                # Should not raise, configuration should be processed

            # Verify configuration was loaded
            mock_load_config.assert_called_once()

    @patch("wekan.cli.commands.clone.typer.Exit", side_effect=SystemExit)
    @patch("wekan.cli.commands.clone.load_config")
    def test_configured_clone_missing_config(self, mock_load_config, mock_exit):
        """Test configured cloning with missing configuration."""
        from wekan.cli.commands.clone import clone_configured

        # Mock incomplete configuration
        mock_config = MagicMock()
        mock_config.base_url = None
        mock_config.username = None
        mock_config.password = None
        mock_load_config.return_value = mock_config

        with tempfile.TemporaryDirectory() as temp_dir:
            # Should raise SystemExit due to missing config
            with pytest.raises(SystemExit):
                clone_configured(output_dir=temp_dir, board=None)

            mock_load_config.assert_called_once()
            mock_exit.assert_called_once_with(1)  # Should exit with error code 1


if __name__ == "__main__":
    pytest.main([__file__])
