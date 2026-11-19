import openpyxl
import os
from typing import List, Dict, Optional

AREAS_PATH = os.path.join(os.path.dirname(__file__), "..", "areas", "Areas_OCDE.xlsx")
_OCDE_CACHE: Optional[List[Dict[str, str]]] = None


def get_ocde_areas() -> List[Dict[str, str]]:
    """Lee el archivo Excel de áreas OCDE y devuelve una lista de diccionarios con la jerarquía."""
    global _OCDE_CACHE
    if _OCDE_CACHE is not None:
        return _OCDE_CACHE

    wb = openpyxl.load_workbook(AREAS_PATH, data_only=True)
    sheet = wb.active
    areas = []

    for row in sheet.iter_rows(min_row=2, values_only=True):
        if row and row[0] and row[1]:
            areas.append({
                "id_area": str(row[0]).strip(),
                "nombre_area": str(row[1]).strip(),
                "id_subarea": str(row[2]).strip() if len(row) > 2 and row[2] else "",
                "nombre_subarea": str(row[3]).strip() if len(row) > 3 and row[3] else "",
                "id_disciplina": str(row[4]).strip() if len(row) > 4 and row[4] else "",
                "nombre_disciplina": str(row[5]).strip() if len(row) > 5 and row[5] else ""
            })

    _OCDE_CACHE = areas
    return _OCDE_CACHE


def get_ocde_subareas() -> List[Dict[str, str]]:
    """Devuelve la lista única de las 42 subáreas OCDE."""
    areas = get_ocde_areas()
    subareas_dict = {}
    for item in areas:
        sub_id = item["id_subarea"]
        if sub_id and sub_id not in subareas_dict:
            subareas_dict[sub_id] = {
                "id_area": item["id_area"],
                "nombre_area": item["nombre_area"],
                "id_subarea": item["id_subarea"],
                "nombre_subarea": item["nombre_subarea"]
            }
    return list(subareas_dict.values())


def get_ocde_subareas_formatted() -> str:
    """
    Construye la lista compacta de las 42 subáreas permitidas para el Paso 1 de clasificación jerárquica.
    Formato: - 1.02.00: Computer and information sciences (Área: Natural sciences)
    """
    subareas = get_ocde_subareas()
    lines = [
        f"- {s['id_subarea']}: {s['nombre_subarea']} (Área: {s['nombre_area']})"
        for s in subareas
    ]
    return "\n".join(lines)


def get_ocde_disciplines_for_subareas(codigos_subarea: List[str]) -> List[Dict[str, str]]:
    """Filtra y devuelve solo las disciplinas hijas asociadas a las subáreas seleccionadas."""
    areas = get_ocde_areas()
    if not codigos_subarea:
        return areas

    codigos_clean = {c.strip() for c in codigos_subarea if c and c.strip()}
    filtered = [a for a in areas if a["id_subarea"] in codigos_clean]
    return filtered if filtered else areas


def get_ocde_disciplines_formatted(codigos_subarea: Optional[List[str]] = None) -> str:
    """
    Construye la lista de disciplinas específicas filtradas para el Paso 2 de clasificación jerárquica.
    Formato: - 1.02.01 | Computer sciences (Subárea: Computer and information sciences)
    """
    disciplinas = get_ocde_disciplines_for_subareas(codigos_subarea or [])
    lines = []
    seen = set()
    for d in disciplinas:
        code = d["id_disciplina"]
        if code and code not in seen:
            seen.add(code)
            lines.append(f"- {code} | {d['nombre_disciplina']} (Subárea: {d['nombre_subarea']})")
    return "\n".join(lines)


def get_ocde_discipline_by_code(codigo_disciplina: str) -> Optional[Dict[str, str]]:
    """Busca determinísticamente una disciplina por su código exacto en el catálogo."""
    if not codigo_disciplina:
        return None
    code_clean = codigo_disciplina.strip()
    areas = get_ocde_areas()
    for a in areas:
        if a["id_disciplina"] == code_clean:
            return a
    return None


def get_ocde_areas_formatted() -> str:
    """Compatibilidad: Devuelve todas las áreas formateadas como texto."""
    areas = get_ocde_areas()
    lines = []
    for item in areas:
        line = f"- Área {item['id_area']} {item['nombre_area']}"
        if item['id_subarea'] and item['nombre_subarea']:
            line += f" > Subárea {item['id_subarea']} {item['nombre_subarea']}"
            if item['id_disciplina'] and item['nombre_disciplina']:
                line += f" > Disciplina {item['id_disciplina']} {item['nombre_disciplina']}"
        lines.append(line)
    return "\n".join(list(dict.fromkeys(lines)))
