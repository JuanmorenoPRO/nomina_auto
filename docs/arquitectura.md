# Arquitectura — Nómina de Unidades Residenciales (Colombia)

> Fase 0. Documento de diseño aprobado antes de escribir código.
> Las reglas resumidas para el día a día están en `CLAUDE.md`.

## 1. Contexto y objetivo

La liquidación quincenal de vigilantes, personal de aseo y toderos de varias unidades
residenciales se hace hoy a mano: la contadora cuenta horas sobre «cuadros de turnos» y
aplica recargos y extras manualmente. La aplicación recibe los turnos por empleado y día
(grilla quincenal), y liquida automáticamente:

1. Horas ordinarias diurnas y nocturnas.
2. Recargo nocturno.
3. Horas extra diurnas y nocturnas.
4. Recargos y extras en dominicales y festivos.
5. Resumen por empleado, quincena y unidad residencial, exportable a Excel.

Criterio de aceptación global: la contadora ingresa una quincena real, presiona
«Liquidar» y el Excel coincide con su cálculo manual. Cuando la ley cambie, crea una
nueva vigencia desde la pantalla de configuración sin tocar código y sin afectar
liquidaciones históricas.

## 2. Stack

| Área | Tecnología |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2 |
| Base de datos | PostgreSQL (producción), SQLite (desarrollo) |
| Frontend (Fase 3) | React + Vite + TypeScript, grilla editable |
| Excel | openpyxl |
| Testing | pytest, hypothesis, coverage (≥90% en dominio), import-linter |
| Dependencias | `uv` + `pyproject.toml` |

Decisiones transversales: `Decimal`/`NUMERIC` para dinero (nunca float), minutos enteros
para duraciones, zona horaria `America/Bogota` explícita, UUID como identificadores,
migraciones Alembic desde la Fase 2.

## 3. Capas (arquitectura hexagonal)

```
┌────────────────────────────────────────────────────┐
│ presentación (Fase 3): React — grilla, config,     │
│ reportes                                           │
├────────────────────────────────────────────────────┤
│ infraestructura: FastAPI (api/), SQLAlchemy        │
│ (persistencia/), openpyxl (excel/), Argon2id +     │
│ sesiones + auditoría (seguridad/)                  │
├────────────────────────────────────────────────────┤
│ aplicación: casos de uso — RegistrarTurno,         │
│ LiquidarQuincena, ActualizarParametro,             │
│ ExportarLiquidacion, CerrarQuincena                │
├────────────────────────────────────────────────────┤
│ dominio (PURO, solo stdlib): entidades, valores,   │
│ servicios (segmentador, clasificador, calculadora, │
│ calendario de festivos), puertos                   │
└────────────────────────────────────────────────────┘
```

Reglas de dependencia (verificadas por `import-linter`):

- `dominio` no importa nada de las otras capas ni de frameworks. No hace I/O: recibe
  parámetros vigentes y festivos **como datos** ya resueltos.
- `aplicacion` solo importa `dominio`. Orquesta: carga datos por los puertos, invoca el
  motor, persiste resultados.
- `infraestructura` implementa los puertos (`Protocol`s definidos en `dominio/puertos/`).

### Estructura de carpetas

```
nomina_auto/
├── CLAUDE.md
├── docs/arquitectura.md
├── backend/
│   ├── pyproject.toml
│   ├── alembic/                  # Fase 2
│   ├── src/nomina/
│   │   ├── dominio/
│   │   │   ├── entidades/        # Empleado, UnidadResidencial, Turno,
│   │   │   │                     # PeriodoLiquidacion, ParametroLegal, ConceptoLiquidado
│   │   │   ├── valores/          # Dinero, DuracionMinutos, RangoHorario, Tramo,
│   │   │   │                     # Vigencia, FactorRecargo
│   │   │   ├── servicios/        # segmentador, clasificador_extras,
│   │   │   │                     # calculadora_conceptos, calendario_festivos
│   │   │   └── puertos/          # Protocols: repositorios, proveedor de parámetros
│   │   ├── aplicacion/casos_uso/
│   │   ├── infraestructura/{persistencia,api,excel,seguridad}/
│   │   └── cli.py                # Fase 1: probar cálculos manualmente
│   └── tests/
│       ├── dominio/golden/       # 7 casos de aceptación calculados a mano
│       └── dominio/propiedades/  # property-based (hypothesis)
└── frontend/                     # Fase 3
```

## 4. Modelo de datos

PK = UUID en todas las tablas. Timestamps técnicos en UTC; fechas/horas de negocio en
hora local Bogotá (Colombia no tiene DST, pero la TZ queda explícita).

### Tablas

**`unidad_residencial`** — id, nombre, nit, activa.

**`empleado`** — id, unidad_id FK, nombre, tipo_documento, documento (único), cargo,
salario_base `NUMERIC`, activo. Dato sensible (Ley 1581/2012): acceso restringido por rol.

**`periodo_liquidacion`** — id, fecha_inicio, fecha_fin, estado
(`abierto` → `liquidado` → `cerrado`). Las quincenas típicas son 1–15 y 16–fin de mes,
pero el periodo se define por fechas, no por regla fija.

**`turno`** — id, empleado_id FK, fecha (día en que **inicia**), hora_inicio, hora_fin.
Si `hora_fin ≤ hora_inicio`, el turno cruza medianoche y termina el día siguiente.
Turno partido = varios registros el mismo día. Descanso = ausencia de turno.
Validaciones: duración ≤ 24 h, sin solapamiento entre turnos del mismo empleado.

**`parametro_legal`** — id, codigo, valor `NUMERIC` (o texto para parámetros no
numéricos), vigente_desde `DATE`, vigente_hasta `DATE NULL` (NULL = vigente
indefinidamente), norma_referencia. **Restricción: las vigencias de un mismo código no se
solapan** (constraint de exclusión en PostgreSQL; validación en aplicación para SQLite).

**`festivo`** — id, fecha (única), nombre, origen (`calculado` | `manual`), anio.
`manual` tiene precedencia sobre `calculado` (permite corregir si la ley cambia).

**`liquidacion`** — id, periodo_id FK, unidad_id FK, version `INT`, estado, snapshot
JSON de los parámetros usados (reproducibilidad histórica), creada_por FK, creada_en.
**Nunca se actualiza:** una corrección genera `version + 1`.

**`concepto_liquidado`** — id, liquidacion_id FK, empleado_id FK, codigo_concepto,
minutos `INT`, tarifa_hora `NUMERIC`, factor `NUMERIC`, valor `NUMERIC`.

**`usuario`** — id, email, hash_password (Argon2id), rol
(`admin` | `contadora` | `operador`), activo.

**`auditoria`** — id, usuario_id, accion, entidad, entidad_id, antes JSON, despues JSON,
timestamp UTC. **Append-only**: sin UPDATE/DELETE (trigger/permisos de BD en Fase 4).
Siempre se auditan: cambios de parámetros legales y ediciones de turnos ya liquidados.

### Parámetros iniciales (semilla)

⚠️ Valores de referencia — **verificar contra fuente oficial antes de producción.**

| Código | Valor | Vigencia | Norma |
|---|---|---|---|
| `jornada_nocturna_inicio` | 19:00 | desde 25-dic-2025 | Ley 2466/2025 |
| `jornada_nocturna_fin` | 06:00 | desde 25-dic-2025 | Ley 2466/2025 |
| `recargo_nocturno` | 0.35 | vigente | CST art. 168 |
| `extra_diurna` | 0.25 | vigente | CST art. 168 |
| `extra_nocturna` | 0.75 | vigente | CST art. 168 |
| `recargo_dominical_festivo` | 0.80 | 1-jul-2025 → 30-jun-2026 | Ley 2466/2025 |
| `recargo_dominical_festivo` | 0.90 | 1-jul-2026 → 30-jun-2027 | Ley 2466/2025 |
| `recargo_dominical_festivo` | 1.00 | desde 1-jul-2027 | Ley 2466/2025 |
| `jornada_maxima_semanal` | 44 | 15-jul-2025 → 14-jul-2026 | Ley 2101/2021 |
| `jornada_maxima_semanal` | 42 | desde 15-jul-2026 | Ley 2101/2021 |
| `horas_quincena` | 110 | vigente | práctica actual |
| `divisor_hora_ordinaria` | 220 | vigente | confirmado en planilla contadora |
| `tope_horas_extra_dia` | 2 | vigente | CST art. 22 / Ley 6ª/1981 |
| `auxilio_transporte_mensual` | 200.000 / 249.095 | 2025 / desde 2026 | decreto anual (verificar) |
| `estrategia_clasificacion_extras` | `presupuesto_quincenal` | vigente | decisión de negocio |

La semilla completa (incluidas vigencias históricas: jornada nocturna 21:00 antes del
25-dic-2025, dominical 75% antes del 1-jul-2025) está en `backend/src/nomina/semilla.py`.

Para el periodo anterior al 25-dic-2025 se siembra también la jornada nocturna previa
(21:00–06:00) si se necesitan liquidaciones históricas.

## 5. Motor de cálculo (dominio)

### 5.1 Segmentación de turnos

Entrada: `Turno` + parámetros vigentes por fecha + calendario de festivos (ambos como
datos). Salida: `list[Tramo]`.

Cortes sucesivos — cada corte es genérico y la regla de la contadora («el sábado que
amanece festivo cambia a festivo a las 12 de la noche») **emerge** del corte por
medianoche, no es un caso especial:

1. Materializar el intervalo `[inicio, fin)` en datetimes locales Bogotá. Si
   `hora_fin ≤ hora_inicio`, `fin` cae al día siguiente.
2. **Corte por día calendario:** partir en cada 00:00.
3. **Corte por franja:** dentro de cada día, partir en los límites de jornada nocturna
   vigentes *ese día* (hoy 19:00 y 06:00) → franja `diurna` | `nocturna`.
4. **Tipo de día** por día calendario del tramo: `festivo` > `dominical` > `ordinario`.

`Tramo` = (intervalo, minutos, franja, tipo_día, fecha).

**Invariantes (property tests con hypothesis):**
- Σ minutos de los tramos = duración total del turno, siempre.
- Ningún tramo queda sin tarifa aplicable.
- Segmentar el resultado otra vez produce el mismo resultado (idempotencia).

### 5.2 Clasificación ordinaria vs. extra

`ClasificadorDeExtras` es una **estrategia** seleccionada por el parámetro
`estrategia_clasificacion_extras` (con vigencias, como todo):

- **`presupuesto_quincenal`** (default — método actual de la contadora): las primeras
  `horas_quincena` (110 h) del periodo, en orden cronológico, son ordinarias; el
  excedente es extra.
- **`semanal_legal`**: acumulado por semana calendario contra `jornada_maxima_semanal`
  vigente esa semana (44 h → 42 h el 15-jul-2026).

Si el umbral cae dentro de un tramo, el tramo se parte en dos. La clasificación conserva
franja y tipo de día: una extra nocturna dominical sigue siendo identificable. El golden
test 5 (quincena que cruza el 15-jul-2026) se prueba con ambas estrategias.

### 5.3 Factores componibles — modelo de pago ADICIONAL al salario

Calibrado contra la planilla real de la contadora (`NOMINA MAYO THUNAPA.xlsx`):
el salario quincenal (`horas_quincena` × tarifa = salario/2) ya paga las horas
ordinarias, caigan donde caigan. Cada tramo genera entonces un pago **adicional**
cuyo factor es la suma de componentes independientes:

- `hora_base` (1.0): la hora no está cubierta por el salario — aplica a toda hora
  **extra** y a toda hora en **dominical/festivo** (el descanso ya estaba remunerado
  en el salario; trabajarlo se paga de nuevo, más el recargo).
- `recargo_dominical_festivo`: horas en domingo o festivo.
- `recargo_nocturno`: horas nocturnas no extra.
- `extra_diurna` / `extra_nocturna`: horas extra según franja.

| Concepto (etiqueta de la contadora) | Componentes | Factor adicional hoy |
|---|---|---|
| TIEMPO ORDINARIO (base, 110 h) | salario/2 | — |
| Ordinaria diurna día ordinario | — | 0 (cubierta) |
| TIEMPO NOCTURNO (recargo) | recargo_nocturno | 0.35 |
| EXTRA DIURNA | 1 + extra_diurna | 1.25 |
| TIEMPO EXTRA NOCTURNO | 1 + extra_nocturna | 1.75 |
| TIEMPO FESTIVO (diurno) | 1 + recargo_dominical | 1.80 → 1.90 (1-jul-2026) |
| TIEMPO NOCTURNO DOMINICAL/FESTIVO | 1 + recargo_dominical + recargo_nocturno | 2.15 → 2.25 |
| TIEMPO FESTIVO EXTRA (extra diurna) | 1 + extra_diurna + recargo_dominical | 2.05 → 2.15 |
| TIEMPO EXTRA NOCTURNO DOMINICAL/FESTIVO | 1 + extra_nocturna + recargo_dominical | 2.55 → 2.65 |
| AUXILIO DE TRANSPORTE | auxilio_transporte_mensual / 2 | — |

Cada componente se resuelve contra la vigencia de la **fecha del tramo** (no la fecha del
sistema ni la de liquidación).

`valor = minutos / 60 × tarifa_hora × factor`, con
`tarifa_hora = salario_base_mensual / divisor_hora_ordinaria`.

⚠️ **Discrepancia detectada en la planilla de la contadora (mayo 2026):** usa el
festivo diurno actualizado (×1.80) pero los factores combinados viejos
(FESTIVO EXTRA ×2.00, NOCTURNO DOMINICAL ×2.10, EXTRA NOCTURNO DOMINICAL ×2.50),
que corresponden al recargo dominical del 75% anterior a la Ley 2466/2025. El
modelo aditivo con el 80% vigente da 2.05 / 2.15 / 2.55. Confirmar con ella cuál
debe prevalecer; el motor sigue los parámetros vigentes.

### 5.4 Política de redondeo

Cálculo interno en minutos enteros y `Decimal` sin redondear. Se redondea **una sola
vez, al final, por concepto liquidado**, a pesos enteros con `ROUND_HALF_UP`. Los
totales (por empleado, por unidad) suman conceptos ya redondeados, de modo que el Excel
siempre cuadra visualmente.

### 5.5 Calendario de festivos

Servicio puro: festivos fijos + móviles derivados de Pascua (algoritmo de Butcher) +
traslado a lunes de los festivos que lo exigen (Ley Emiliani 51/1983). La tabla
`festivo` materializa los calculados y admite altas/ediciones manuales con precedencia.
Tests contra los festivos oficiales de 2025, 2026 y 2027.

## 6. Seguridad (por diseño)

Datos protegidos por Ley 1581/2012 (habeas data): cédulas y salarios.

1. **Autenticación:** Argon2id, sesiones con expiración, credenciales solo por variables
   de entorno (`.env` en `.gitignore`, con `.env.example` versionado).
2. **Autorización por roles**, verificada en backend: `admin` (parámetros y usuarios),
   `contadora` (liquidar, exportar), `operador` (solo turnos).
3. **Validación de entrada:** Pydantic en todos los endpoints; rechazar turnos imposibles
   (duración > 24 h, solapamientos del mismo empleado, fin ≤ inicio sin cruce válido).
4. **Persistencia:** ORM parametrizado, UUID expuestos.
5. **Auditoría** append-only (ver tabla `auditoria`).
6. **Liquidaciones cerradas** en solo lectura; correcciones = nueva versión.
7. Cabeceras de seguridad HTTP, CORS restrictivo, rate limiting en login (Fase 4).

## 7. Testing

- **Golden tests** (valores esperados calculados a mano):
  1. Turno diurno normal entre semana — sin recargos.
  2. Turno 18:00–06:00 entre semana — recargo nocturno desde las 19:00.
  3. Sábado 18:00 → domingo 06:00 — corte en medianoche, tramo dominical.
  4. Domingo 18:00 → lunes festivo 06:00 — dominical + festivo, corte en 00:00 (el caso
     exacto de la contadora).
  5. Quincena que cruza el 15-jul-2026 — jornada 44→42 h a mitad de periodo (con ambas
     estrategias de clasificación).
  6. Turno el 1-jul-2026 vs. 30-jun-2026 — dominical 80% → 90%.
  7. Festivo trasladado a lunes por Ley Emiliani.
- **Property-based (hypothesis):** invariantes de la sección 5.1.
- **Calendario:** festivos oficiales 2025, 2026, 2027.
- **Cobertura:** ≥90% en `dominio/` (falla el build si baja).

## 8. Plan por fases

| Fase | Entregable | Estado |
|---|---|---|
| 0 | Arquitectura, modelo de datos, esqueleto, CLAUDE.md | ✅ |
| 1 | Dominio puro + motor + festivos + golden tests + CLI | pendiente |
| 2 | Persistencia, parámetros con vigencias, casos de uso, API | ✅ |
| 3 | UI: grilla quincenal, configuración, reportes, Excel | ✅ |
| 4 | Auth, roles, auditoría, cierre de quincenas, hardening | pendiente |

Una fase a la vez, con revisión del usuario al final de cada una.
