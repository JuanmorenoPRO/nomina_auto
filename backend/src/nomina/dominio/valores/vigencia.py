from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Vigencia:
    """Rango de fechas [desde, hasta] en que aplica un valor legal.

    `hasta = None` significa vigente indefinidamente.
    """

    desde: date
    hasta: date | None = None

    def __post_init__(self) -> None:
        if self.hasta is not None and self.hasta < self.desde:
            raise ValueError(f"Vigencia inválida: hasta {self.hasta} < desde {self.desde}")

    def contiene(self, fecha: date) -> bool:
        if fecha < self.desde:
            return False
        return self.hasta is None or fecha <= self.hasta

    def se_solapa_con(self, otra: Vigencia) -> bool:
        fin_propia = self.hasta or date.max
        fin_otra = otra.hasta or date.max
        return self.desde <= fin_otra and otra.desde <= fin_propia
