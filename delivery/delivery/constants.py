from enum import IntEnum
from typing import Dict


class DeliveryTypes(IntEnum):
    WHITE_GLOVE = 1
    CURBSIDE = 2

    def __int__(self) -> int:
        return int(self.value)

    def __str__(self) -> str:
        return str(self.value)


DELIVERY_TYPE_COSTS: Dict[int, DeliveryTypes] = {
    7500: DeliveryTypes.CURBSIDE,
    12500: DeliveryTypes.WHITE_GLOVE,
}
