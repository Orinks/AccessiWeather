from enum import Enum


class QuantitativeValueQualityControl(str, Enum):
    B = "B"
    C = "C"
    G = "G"
    Q = "Q"
    S = "S"
    T = "T"
    V = "V"
    X = "X"
    Z = "Z"

    def __str__(self) -> str:
        return str(self.value)
