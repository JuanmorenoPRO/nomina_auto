"""Novedad de un día sin turno en el cuadro de turnos.

Un día sin turno es, por defecto, un **descanso** (remunerado: cuenta para el
auxilio de transporte). Se puede marcar como:

- `INCAPACIDAD`: el empleado estuvo incapacitado ese día.
- `NO_LABORO`: el empleado no laboró ni estaba vinculado ese día (ingreso o
  retiro a mitad de quincena, ausencia).

Ambas le quitan ese día al auxilio de transporte (`mensual / 30` por día).
No cambian el tiempo ordinario ni el IBC.
"""

INCAPACIDAD = "incapacidad"
NO_LABORO = "no_laboro"

TIPOS_NOVEDAD_DIA = frozenset({INCAPACIDAD, NO_LABORO})
