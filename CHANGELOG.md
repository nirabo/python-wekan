# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2025-08-07

### Added
- Comprehensive API coverage for Boards, Lists, and Cards.
- `Board.update()` to modify board properties.
- `Board.archive()` and `Board.restore()` to manage board archival.
- `Board.get_members()` to retrieve board members.
- `Board.create_label()` to add labels to a board.
- `WekanList.update()` to modify list properties.
- `WekanList.archive()` and `WekanList.restore()` to manage list archival.
- `WekanCard.update()`, `WekanCard.move_to_list()`, `WekanCard.set_due_date()`, and `WekanCard.assign_member()` wrapper methods for easier card manipulation.
- `WekanClient.get_current_user()` and `WekanClient.find_user()` for easier user management.
- A custom exception hierarchy for more specific error handling (`WekanAPIError`, `WekanNotFoundError`, `WekanAuthenticationError`).
- Unit test suite (`tests/test_unit.py`) with mocking for CI validation.
- CI workflow to run unit tests on pull requests.

### Changed
- Renamed `User` class to `WekanUser`.
- Renamed `List` class to `WekanList`.
- Renamed `Card` class to `WekanCard`.
- Renamed `WekanClient.list_users()` to `get_users()`.
- Renamed `Board.add_list()` to `create_list()` and added `position` parameter.
- Renamed `Board.list_lists()` to `get_lists()`.
- Renamed `WekanList.add_card()` to `create_card()` with a simpler signature.
- Renamed `WekanList.list_cards()` to `get_cards()`.
- Renamed `WekanCard.list_comments()` to `get_comments()` and changed return type to `list[dict]`.
- Renamed `WekanCard.add_comment()` to return a `dict` instead of a `CardComment` object.
- Updated all examples in `README.md` to reflect the new API.

### Fixed
- A bug in the unit tests where a mock object was missing the `user_id` attribute.

### Removed
- The disabled E2E test steps from the CI workflow, in favor of unit tests.
