import pytest
from src.team_config import TeamManager
from src.learning_paths import LearningPathManager, TEMPLATES
import tempfile
import shutil


@pytest.fixture
def team_manager():
    tmpdir = tempfile.mkdtemp()
    mgr = TeamManager(data_dir=tmpdir)
    yield mgr
    shutil.rmtree(tmpdir)


@pytest.fixture
def path_manager():
    tmpdir = tempfile.mkdtemp()
    mgr = LearningPathManager(data_dir=tmpdir)
    yield mgr
    shutil.rmtree(tmpdir)


# ── Team Config Tests ──


def test_create_team(team_manager: TeamManager):
    team = team_manager.create_team("team-1", "Alpha Team", "First team")
    assert team.team_id == "team-1"
    assert team.name == "Alpha Team"
    assert team.is_active is True


def test_create_duplicate_team(team_manager: TeamManager):
    team_manager.create_team("team-1", "Alpha")
    with pytest.raises(ValueError, match="already exists"):
        team_manager.create_team("team-1", "Duplicate")


def test_get_team(team_manager: TeamManager):
    team_manager.create_team("team-1", "Alpha")
    team = team_manager.get_team("team-1")
    assert team is not None
    assert team.name == "Alpha"


def test_get_nonexistent_team(team_manager: TeamManager):
    assert team_manager.get_team("nope") is None


def test_list_teams(team_manager: TeamManager):
    team_manager.create_team("t1", "Team 1")
    team_manager.create_team("t2", "Team 2")
    teams = team_manager.list_teams()
    assert len(teams) == 2


def test_add_remove_member(team_manager: TeamManager):
    team_manager.create_team("t1", "Team 1")
    team = team_manager.add_member("t1", "alice")
    assert "alice" in team.members

    team = team_manager.add_member("t1", "bob")
    assert len(team.members) == 2

    team = team_manager.remove_member("t1", "alice")
    assert "alice" not in team.members
    assert "bob" in team.members


def test_add_member_nonexistent(team_manager: TeamManager):
    with pytest.raises(ValueError):
        team_manager.add_member("nope", "alice")


def test_update_settings(team_manager: TeamManager):
    team_manager.create_team("t1", "Team 1")
    team = team_manager.update_settings("t1", {"theme": "dark", "lang": "zh"})
    assert team.settings["theme"] == "dark"
    assert team.settings["lang"] == "zh"


def test_delete_team(team_manager: TeamManager):
    team_manager.create_team("t1", "Team 1")
    assert team_manager.delete_team("t1") is True
    team = team_manager.get_team("t1")
    assert team.is_active is False

    # Deleted teams don't appear in list_teams
    teams = team_manager.list_teams()
    assert len(teams) == 0


def test_persistence(team_manager: TeamManager):
    team_manager.create_team("t1", "Persistent Team")
    team_manager.add_member("t1", "charlie")

    # Create new manager with same dir
    mgr2 = TeamManager(data_dir=str(team_manager.data_dir))
    team = mgr2.get_team("t1")
    assert team is not None
    assert "charlie" in team.members


# ── Learning Path Tests ──


def test_list_all_templates(path_manager: LearningPathManager):
    templates = path_manager.list_templates()
    assert len(templates) >= 3


def test_list_templates_by_role(path_manager: LearningPathManager):
    backend = path_manager.list_templates(role="backend")
    for t in backend:
        assert t.role == "backend" or t.role == "any"


def test_get_template(path_manager: LearningPathManager):
    t = path_manager.get_template("ai-beginner")
    assert t is not None
    assert t.name == "AI 时代入门路径"
    assert len(t.steps) > 0


def test_get_nonexistent_template(path_manager: LearningPathManager):
    assert path_manager.get_template("nope") is None


def test_recommend_path(path_manager: LearningPathManager):
    recommended = path_manager.recommend_path("L0", "L2")
    assert len(recommended) >= 1


def test_create_custom_path(path_manager: LearningPathManager):
    steps = [
        {
            "step_id": "s1",
            "title": "Custom Step",
            "doc_path": "test.md",
            "estimated_hours": 2.0,
        },
    ]
    path = path_manager.create_custom_path(
        "custom-1", "Custom Path", "A custom path", steps
    )
    assert path.path_id == "custom-1"
    assert path.total_estimated_hours == 2.0


def test_template_calculate_hours():
    t = TEMPLATES["ai-beginner"]
    total = t.calculate_hours()
    assert total > 0
    assert t.total_estimated_hours == total
