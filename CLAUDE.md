# Nómina de Unidades Residenciales (Colombia)

Aplicación de liquidación de nómina quincenal para empleados de unidades residenciales
(vigilantes, aseo, toderos): ingreso de turnos, cálculo de recargos/extras según normativa
laboral colombiana y exportación a Excel.

El diseño completo está en `docs/arquitectura.md`. Este archivo resume las reglas que
NUNCA se rompen al escribir código en este repo.

## Regla de oro

**Ningún valor legal se escribe quemado en el código.** Porcentajes, horarios de jornada
nocturna, jornada máxima, horas de la quincena, divisores: todos viven en la tabla de
parámetros con vigencias (`vigente_desde` / `vigente_hasta`) y el motor resuelve el valor
vigente en la **fecha del tramo del turno** — nunca en la fecha actual del sistema ni en
la fecha de liquidación. Motivo: la ley colombiana cambia de forma escalonada (en julio de
2026 hay dos cambios con fechas distintas: dominical 80→90% el 1-jul y jornada 44→42 h el
15-jul).

## Arquitectura (hexagonal)

```
dominio  ←  aplicacion  ←  infraestructura
```

- `backend/src/nomina/dominio/`: **puro**. Solo stdlib. Sin I/O, sin FastAPI, sin
  SQLAlchemy, sin Pydantic. Recibe parámetros y festivos como datos, nunca los consulta.
- `backend/src/nomina/aplicacion/`: casos de uso; solo importa `dominio` y sus puertos.
- `backend/src/nomina/infraestructura/`: implementa los puertos (persistencia, API,
  Excel, seguridad).
- La regla se verifica con `import-linter` (contratos en `pyproject.toml`).

## Convenciones no negociables

- **Dinero y porcentajes:** `Decimal`. **Nunca float.** En BD, `NUMERIC`.
- **Duraciones:** minutos enteros. Nunca horas fraccionarias intermedias.
- **Redondeo:** una sola vez, al final, por concepto liquidado, a pesos enteros con
  `ROUND_HALF_UP`. Los totales suman conceptos ya redondeados.
- **Zona horaria:** `America/Bogota` (`zoneinfo`), explícita en todo datetime de negocio.
  Timestamps de auditoría en UTC.
- **Idioma:** dominio y casos de uso en español (lenguaje ubicuo del negocio);
  infraestructura técnica en inglés donde sea idiomático.
- **IDs:** UUID, nunca secuenciales expuestos.
- **Seguridad:** sin credenciales en código ni en el repo (`.env` está en `.gitignore`);
  permisos verificados en backend; auditoría append-only; liquidaciones cerradas son de
  solo lectura — las correcciones crean una nueva versión.

## Motor de cálculo (resumen)

1. **Segmentación:** cada turno se parte en tramos homogéneos por cortes sucesivos:
   (a) medianoche (día calendario), (b) límites de jornada nocturna vigentes ese día,
   (c) tipo de día (`festivo` > `dominical` > `ordinario`). La regla de la contadora
   («el sábado que amanece festivo cambia a festivo a las 12 de la noche») emerge del
   corte por medianoche — no es un caso especial.
2. **Invariante:** la suma de los minutos de los tramos = duración del turno, siempre.
3. **Clasificación extra/ordinaria:** estrategia parametrizable
   (`estrategia_clasificacion_extras`): `presupuesto_quincenal` (default, 110 h) o
   `semanal_legal` (44/42 h por semana).
4. **Modelo de pago ADICIONAL al salario** (calibrado con la planilla real de la
   contadora): el salario quincenal (110 h × tarifa = salario/2) cubre las horas
   ordinarias; cada tramo paga solo el factor adicional componible. Una nocturna
   ordinaria paga 0.35; una hora en dominical/festivo paga `1 + recargo` (la hora
   completa de nuevo, porque el descanso ya estaba remunerado); una extra nocturna
   dominical paga `1 + extra_nocturna + recargo_dominical`. Nunca una lista plana
   de porcentajes combinados a mano. Detalle en `docs/arquitectura.md` §5.3.

## Glosario del dominio

- **Quincena:** periodo de liquidación de ~15 días (1–15 y 16–fin de mes).
- **Turno:** intervalo trabajado por un empleado (puede cruzar medianoche; un día puede
  tener varios turnos = turno partido; sin turno = descanso).
- **Tramo:** fragmento de turno homogéneo (una sola tarifa aplicable) tras la segmentación.
- **Jornada nocturna:** franja horaria con recargo (hoy 19:00–06:00, Ley 2466/2025).
- **Recargo nocturno:** sobrecosto por trabajar en jornada nocturna dentro de la jornada
  ordinaria (hoy +35%).
- **Hora extra:** hora que excede la jornada máxima; diurna +25%, nocturna +75%.
- **Dominical / festivo:** trabajo en domingo o festivo; recargo hoy +80% (sube a 90% el
  1-jul-2026 y a 100% el 1-jul-2027, Ley 2466/2025).
- **Vigencia:** rango de fechas `[vigente_desde, vigente_hasta]` en que un valor de
  parámetro legal aplica. Las vigencias de un mismo parámetro no se solapan.
- **Liquidación:** resultado de calcular una quincena; inmutable una vez cerrada.
- **Cierre:** paso a solo lectura de una liquidación aprobada; corregir = nueva versión.
- **Festivo trasladado:** festivo movido a lunes por Ley Emiliani (51 de 1983).

## Comandos

```bash
cd backend
uv sync               # instalar dependencias
uv run pytest         # tests (cobertura mínima 90% en dominio)
uv run ruff check .
uv run lint-imports   # verificar regla de capas
uv run alembic upgrade head                                # migrar la BD
uv run python -m nomina.infraestructura.persistencia.sembrar   # sembrar parámetros
uv run uvicorn nomina.infraestructura.api.app:crear_app --factory --reload --port 8001  # API
# primer usuario (la contraseña se pide por consola o va en NOMINA_ADMIN_PASSWORD):
uv run python -m nomina.infraestructura.seguridad.crear_admin --email admin@ejemplo.com
```

```bash
cd frontend
npm install      # usa .npmrc del proyecto (registro público, no el corporativo)
npm run dev      # UI en http://localhost:5174 con proxy /api → backend :8001
npm run build    # verificación de tipos (tsc estricto) + build
```

Nota de esta máquina: los puertos 5173 y 8000 los ocupa otra app en Docker;
por eso el dev server usa 5174 y el backend 8001.

## Estado del plan por fases

- [x] **Fase 0:** arquitectura, modelo de datos, estructura de carpetas, este archivo.
- [x] **Fase 1:** dominio puro + segmentación + cálculo + calendario de festivos + golden
      tests + CLI mínimo (`uv run python -m nomina.cli --help`). Sin BD ni UI.
- [x] **Fase 2:** persistencia (SQLAlchemy + Alembic), parámetros con vigencias en BD,
      casos de uso (RegistrarTurno, LiquidarQuincena versionada con snapshot,
      ActualizarParametro) y API FastAPI. Sin autenticación aún (Fase 4).
- [x] **Fase 3:** UI React+Vite (grilla quincenal editable, liquidación con desglose,
      configuración de parámetros/festivos, entidades) y exportación a Excel con el
      formato de la contadora (hoja por empleado + resumen).
- [x] **Fase 4:** autenticación (Argon2id + sesiones con cookie HttpOnly, token hasheado
      en BD), roles jerárquicos operador ⊂ contadora ⊂ admin verificados en backend,
      auditoría append-only (triggers de BD bloquean UPDATE/DELETE), cierre definitivo
      de quincenas, rate limiting en login y cabeceras de seguridad.

**Todas las fases del plan original están completas.** Pendientes de negocio (ver
memoria/docs): confirmar con la contadora los factores combinados y su regla real de
clasificación de extras, y verificar el auxilio de transporte 2026 contra el decreto.
Los valores legales de referencia (tabla en `docs/arquitectura.md`) deben verificarse
contra fuente oficial antes de producción.
