"""Convenios de presentación entre cadenas de TV y marcas (lógica pura salvo la lectura del catálogo): sin dinero ni efecto económico."""
import random
from typing import Dict, List

from config import televisoras as CT


def ids_convenio(tele_id: int, seq: int, marcas: Dict[int, dict]) -> List[int]:
    """
    Marcas con convenio de una cadena en el partido `seq` del torneo: hasta CONVENIO_MAX_MARCAS, de cualquier alcance, de rubros
    distintos. Cada una cambia cada CONVENIO_PARTIDOS partidos, desfasadas entre sí. Determinístico (misma cadena y época = mismas marcas).
    """
    candidatas = sorted(i for i, m in marcas.items() if (m.get("dueno") or {}).get("nombre"))
    elegidas: List[int] = []
    rubros = set()
    for k in range(CT.CONVENIO_MAX_MARCAS):
        epoca = (int(seq) + k * CT.CONVENIO_PARTIDOS // CT.CONVENIO_MAX_MARCAS) // CT.CONVENIO_PARTIDOS
        rng = random.Random(f"convenio:{tele_id}:{k}:{epoca}")
        pool = [i for i in candidatas if i not in elegidas and marcas[i].get("rubro") not in rubros]
        if not pool:
            break
        pick = rng.choice(pool)
        elegidas.append(pick)
        rubros.add(marcas[pick].get("rubro"))
    return elegidas
