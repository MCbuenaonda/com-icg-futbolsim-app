"""Relaciones (lógica pura): intensidad de la rivalidad entre selecciones y relaciones derivadas de rasgos para marcas, medios y cadenas.
Sin Mongo; services/relaciones_service.py arma los datos y guarda.
"""
import zlib
from typing import Dict, List, Optional, Tuple

from config import relaciones as CR


def etiqueta(intensidad: float) -> Optional[str]:
    return "Clásico" if intensidad >= CR.UMBRAL_CLASICO else ("Rivalidad" if intensidad >= CR.UMBRAL_RIVALIDAD else None)


def intensidad_seleccion(encuentros: List[dict], misma_confederacion: bool) -> Tuple[int, List[str]]:
    """encuentros = [{fase_id, dif (goles de diferencia, valor absoluto), calor (polémicas y expulsiones del partido)}] de la pareja.
    Devuelve (intensidad 0-100, motivos)."""
    P = CR.PUNTOS_SELECCION
    n = len(encuentros)
    if n == 0:
        return 0, []
    valor, motivos = 0, []
    if misma_confederacion:
        valor += P["misma_confederacion"]
        motivos.append("misma confederación")
    valor += min(P["tope_encuentros"], P["por_encuentro"] * n)
    motivos.append("se han enfrentado 1 vez" if n == 1 else f"se han enfrentado {n} veces")
    cortos = sum(1 for e in encuentros if e["dif"] <= 1)
    if cortos:
        valor += min(P["tope_margen"], P["margen_corto"] * cortos)
        motivos.append(f"{cortos} duelo{'s' if cortos != 1 else ''} muy parejo{'s' if cortos != 1 else ''}")
    if any((e.get("fase_id") or 0) >= 8 for e in encuentros):
        valor += P["eliminacion_directa"]
        motivos.append("un cruce de eliminación directa")
    calor = sum(e.get("calor", 0) for e in encuentros)
    if calor:
        valor += min(P["tope_calor"], P["por_calor"] * calor)
        motivos.append("partidos muy calientes")
    return min(100, valor), motivos


def _par(a, b) -> Tuple:
    return (a, b) if a <= b else (b, a)


def relaciones_marcas(marcas: List[dict]) -> List[dict]:
    """Rivales (mismo rubro) y aliadas (rubros distintos con dueños afines, a lo sumo ALIADOS_POR_MARCA por marca) de las marcas."""
    docs: Dict[Tuple, dict] = {}
    por_rubro: Dict[str, List[dict]] = {}
    for m in marcas:
        por_rubro.setdefault(m["rubro"], []).append(m)
    for lista in por_rubro.values():
        for i, a in enumerate(lista):
            for b in lista[i + 1:]:
                ra, rb = (a.get("dueno") or {}).get("rasgo"), (b.get("dueno") or {}).get("rasgo")
                v = CR.RIVALES_MARCA_BASE + (CR.RIVALES_MARCA_ALCANCE if a.get("alcance") == b.get("alcance") else 0)
                v += CR.RASGOS_CHOQUE.get((ra, rb), CR.RASGOS_CHOQUE.get((rb, ra), 0))
                motivos = [f"compiten en {a['rubro']}"] + ([f"dueños que chocan ({ra} y {rb})"] if CR.RASGOS_CHOQUE.get((ra, rb), CR.RASGOS_CHOQUE.get((rb, ra), 0)) else [])
                docs[("rivalidad",) + _par(a["id"], b["id"])] = {"clase": "rivalidad", "a": _par(a["id"], b["id"])[0], "b": _par(a["id"], b["id"])[1], "intensidad": min(100, v), "motivos": motivos}
    for m in marcas:
        candidatas = [o for o in marcas if o["rubro"] != m["rubro"] and o.get("alcance") == m.get("alcance")
                      and ((m.get("dueno") or {}).get("rasgo"), (o.get("dueno") or {}).get("rasgo")) in CR.RASGOS_AFINES]
        candidatas.sort(key=lambda o: zlib.crc32(f"alianza:{m['id']}:{o['id']}".encode()))
        for o in candidatas[:CR.ALIADOS_POR_MARCA]:
            a, b = _par(m["id"], o["id"])
            docs.setdefault(("alianza", a, b), {"clase": "alianza", "a": a, "b": b, "intensidad": 50 + zlib.crc32(f"i:{a}:{b}".encode()) % 31,
                                                "motivos": [f"dueños afines ({(m.get('dueno') or {}).get('rasgo')} y {(o.get('dueno') or {}).get('rasgo')})"]})
    return list(docs.values())


def relaciones_medios(medios: List[dict]) -> List[dict]:
    docs = []
    por_pais: Dict[int, List[dict]] = {}
    for m in medios:
        if m.get("pais_id") is not None:
            por_pais.setdefault(m["pais_id"], []).append(m)
    for lista in por_pais.values():
        for i, a in enumerate(lista):
            for b in lista[i + 1:]:
                x, y = _par(a["id"], b["id"])
                if frozenset((a.get("linea"), b.get("linea"))) in CR.LINEAS_OPUESTAS:
                    docs.append({"clase": "rivalidad", "a": x, "b": y, "intensidad": CR.RIVALES_MEDIO, "motivos": [f"líneas editoriales opuestas ({a['linea']} y {b['linea']})"]})
                elif a.get("linea") == b.get("linea"):
                    docs.append({"clase": "alianza", "a": x, "b": y, "intensidad": CR.ALIADOS_MEDIO, "motivos": [f"misma línea editorial ({a['linea']})"]})
    return docs


def relaciones_tv(televisoras: List[dict]) -> List[dict]:
    docs = []
    por_pais: Dict[int, List[dict]] = {}
    for t in televisoras:
        por_pais.setdefault(t["pais_id"], []).append(t)
    for lista in por_pais.values():
        for i, a in enumerate(lista):
            for b in lista[i + 1:]:
                x, y = _par(a["id"], b["id"])
                docs.append({"clase": "rivalidad", "a": x, "b": y, "intensidad": CR.RIVALES_TV, "motivos": ["compiten por los derechos de las selecciones de su país"]})
    return docs
