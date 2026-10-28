"""
Motor de ilustraciones de estadios (SVG, dibujo de líneas en vista 3/4) para las ciudades sede.
  base.py      proyección, superficies paramétricas, gradas, cancha y encuadre (clase Estadio)
  piezas.py    fachadas, cubiertas y extras reutilizables (mixin de Estadio)
  catalogo.py  los 50 conceptos (cada uno con su función de dibujo, grupo y regiones preferidas)
  color.py     paleta del país en 3 roles (principal, secundario, detalle) legible sobre el tema oscuro
Lo usa generar_estadios.py. Lógica pura, sin dependencias.
"""
