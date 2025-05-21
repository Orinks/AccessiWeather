from enum import Enum


class IconsDualConditionSizeType0(str, Enum):
    LARGE = "large"
    MEDIUM = "medium"
    SMALL = "small"

    def __str__(self) -> str:
        return str(self.value)
