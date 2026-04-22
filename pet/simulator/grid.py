from enum import Enum
from pydantic import BaseModel


class Direction(str, Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class GridConfig(BaseModel):
    width: int = 20
    height: int = 15


class PetState(BaseModel):
    x: int
    y: int
    facing: Direction = Direction.RIGHT
    mood: str = "neutral"


class GridState(BaseModel):
    config: GridConfig
    pet: PetState
    tick: int = 0


class Grid:
    def __init__(self, config: GridConfig = GridConfig()):
        self.config = config
        self.state = GridState(
            config=config,
            pet=PetState(x=config.width // 2, y=config.height // 2),
        )

    def move(self, direction: Direction) -> GridState:
        pet = self.state.pet
        x, y = pet.x, pet.y
        moved = True

        if direction == Direction.UP:
            if y > 0:
                y -= 1
            else:
                moved = False
        elif direction == Direction.DOWN:
            if y < self.config.height - 1:
                y += 1
            else:
                moved = False
        elif direction == Direction.LEFT:
            if x > 0:
                x -= 1
            else:
                moved = False
        elif direction == Direction.RIGHT:
            if x < self.config.width - 1:
                x += 1
            else:
                moved = False

        self.state.pet = PetState(x=x, y=y, facing=direction, mood=pet.mood)
        if moved:
            self.state.tick += 1
        return self.state

    def set_mood(self, mood: str) -> GridState:
        self.state.pet = self.state.pet.model_copy(update={"mood": mood})
        return self.state
