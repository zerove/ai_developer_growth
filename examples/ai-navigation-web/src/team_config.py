"""Team configuration management with isolation between teams."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class TeamConfig:
    team_id: str
    name: str
    description: str = ""
    members: list[str] = field(default_factory=list)
    learning_paths: list[str] = field(default_factory=list)
    settings: dict = field(default_factory=dict)
    created_at: str = ""
    is_active: bool = True


class TeamManager:
    """Manage team configurations with isolation."""

    def __init__(self, data_dir: str = "data/teams"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _team_file(self, team_id: str) -> Path:
        return self.data_dir / f"{team_id}.json"

    def create_team(self, team_id: str, name: str, description: str = "") -> TeamConfig:
        """Create a new team with isolation."""
        if self._team_file(team_id).exists():
            raise ValueError(f"Team {team_id} already exists")

        config = TeamConfig(
            team_id=team_id,
            name=name,
            description=description,
            created_at=datetime.now(UTC).isoformat(),
        )
        self._save(config)
        return config

    def get_team(self, team_id: str) -> TeamConfig | None:
        """Get team configuration."""
        f = self._team_file(team_id)
        if not f.exists():
            return None
        data = json.loads(f.read_text())
        return TeamConfig(**data)

    def list_teams(self) -> list[TeamConfig]:
        """List all active teams."""
        teams = []
        for f in sorted(self.data_dir.glob("*.json")):
            data = json.loads(f.read_text())
            if data.get("is_active", True):
                teams.append(TeamConfig(**data))
        return teams

    def add_member(self, team_id: str, username: str) -> TeamConfig:
        """Add a member to a team."""
        config = self.get_team(team_id)
        if not config:
            raise ValueError(f"Team {team_id} not found")
        if username not in config.members:
            config.members.append(username)
            self._save(config)
        return config

    def remove_member(self, team_id: str, username: str) -> TeamConfig:
        """Remove a member from a team."""
        config = self.get_team(team_id)
        if not config:
            raise ValueError(f"Team {team_id} not found")
        if username in config.members:
            config.members.remove(username)
            self._save(config)
        return config

    def update_settings(self, team_id: str, settings: dict) -> TeamConfig:
        """Update team settings."""
        config = self.get_team(team_id)
        if not config:
            raise ValueError(f"Team {team_id} not found")
        config.settings.update(settings)
        self._save(config)
        return config

    def delete_team(self, team_id: str) -> bool:
        """Soft delete a team."""
        config = self.get_team(team_id)
        if not config:
            return False
        config.is_active = False
        self._save(config)
        return True

    def _save(self, config: TeamConfig) -> None:
        """Save team config to file."""
        self._team_file(config.team_id).write_text(json.dumps(asdict(config), indent=2, ensure_ascii=False))
