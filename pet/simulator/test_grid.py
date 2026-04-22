import pytest
from simulator.grid import Grid, Direction, GridConfig


@pytest.fixture
def grid():
    return Grid(GridConfig(width=10, height=10))


def test_pet_starts_at_center(grid):
    assert grid.state.pet.x == 5
    assert grid.state.pet.y == 5


def test_move_up_decreases_y(grid):
    grid.move(Direction.UP)
    assert grid.state.pet.y == 4


def test_move_down_increases_y(grid):
    grid.move(Direction.DOWN)
    assert grid.state.pet.y == 6


def test_move_left_decreases_x(grid):
    grid.move(Direction.LEFT)
    assert grid.state.pet.x == 4


def test_move_right_increases_x(grid):
    grid.move(Direction.RIGHT)
    assert grid.state.pet.x == 6


def test_cannot_move_past_left_boundary(grid):
    grid.state.pet.x = 0
    grid.move(Direction.LEFT)
    assert grid.state.pet.x == 0


def test_cannot_move_past_right_boundary(grid):
    grid.state.pet.x = 9
    grid.move(Direction.RIGHT)
    assert grid.state.pet.x == 9


def test_cannot_move_past_top_boundary(grid):
    grid.state.pet.y = 0
    grid.move(Direction.UP)
    assert grid.state.pet.y == 0


def test_cannot_move_past_bottom_boundary(grid):
    grid.state.pet.y = 9
    grid.move(Direction.DOWN)
    assert grid.state.pet.y == 9


def test_move_updates_facing_direction(grid):
    grid.move(Direction.LEFT)
    assert grid.state.pet.facing == Direction.LEFT


def test_tick_increments_on_move(grid):
    initial = grid.state.tick
    grid.move(Direction.UP)
    assert grid.state.tick == initial + 1


def test_tick_does_not_increment_on_blocked_move(grid):
    grid.state.pet.x = 0
    initial = grid.state.tick
    grid.move(Direction.LEFT)
    assert grid.state.tick == initial


def test_set_mood(grid):
    grid.set_mood("happy")
    assert grid.state.pet.mood == "happy"


def test_state_is_serializable(grid):
    data = grid.state.model_dump()
    assert data["pet"]["x"] == 5
    assert data["config"]["width"] == 10
    assert data["tick"] == 0
