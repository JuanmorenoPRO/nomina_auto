# Arquitectura — Nómina de Unidades Residenciales (Colombia)

> Nació como el documento de diseño de la Fase 0, aprobado antes de escribir código, y se
> mantiene al día con lo que se construyó. Las reglas resumidas para el día a día y el
> estado del proyecto están en `CLAUDE.md`; la referencia de componentes, en `README.md`.

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

**`unidad_residencial`** — id, nombre, nit, activa, descuenta_seguridad_social,
config `JSON`. `config` guarda lo que la unidad hace distinto: `estrategia_extras`
(sobreescribe la global), `factores_override` (factor fijo por concepto, para unidades
cuya planilla usa la tabla de factores legada) y `conceptos_fijos` (devengados o
deducciones que se aplican a todos sus empleados en cada liquidación).

**`empleado`** — id, unidad_id FK, nombre, tipo_documento, documento (único), cargo,
salario_base `NUMERIC`, activo, incapacitado, ocasional. Dato sensible (Ley 1581/2012):
acceso restringido por rol. `incapacitado` y `ocasional` quitan el auxilio de transporte,
salvo que se prorratee (ver `ajuste_quincena`).

**`periodo_liquidacion`** — id, fecha_inicio, fecha_fin (únicos como par), estado
(`abierto` → `liquidado` → `cerrado`). Las quincenas típicas son 1–15 y 16–fin de mes,
pero el periodo se define por fechas, no por regla fija.

**`turno`** — id, empleado_id FK, fecha (día en que **inicia**), hora_inicio, hora_fin,
minutos_jornada_ordinaria `INT NULL`. Si `hora_fin ≤ hora_inicio`, el turno cruza
medianoche y termina el día siguiente. Turno partido = varios registros el mismo día.
Descanso = ausencia de turno. Validaciones: duración ≤ 24 h, sin solapamiento entre turnos
del mismo empleado. `minutos_jornada_ordinaria` (`NULL` = turno normal) marca el turno como
**jornada ordinaria**: se registró para cuadrar las horas de la quincena, no porque se
trabajara, así que sus primeros N minutos no pagan recargo y solo el excedente se reconoce
como extra.

**`ajuste_quincena`** — id, empleado_id FK, periodo_id FK (únicos como par),
quincena_incompleta, sin_extras, auxilio_por_dias_laborados, pagar_dia_31. Las marcas que cambian
cómo se liquida ese empleado en esa quincena: pagar el tiempo ordinario sobre lo laborado,
no cobrar extras por turno, y prorratear el auxilio de transporte. La tercera **manda**
sobre `incapacitado` / `ocasional`.

**`parametro_legal`** — id, codigo, valor `NUMERIC` (o texto para parámetros no
numéricos), vigente_desde `DATE`, vigente_hasta `DATE NULL` (NULL = vigente
indefinidamente), norma. **Restricción: las vigencias de un mismo código no se
solapan** (constraint de exclusión en PostgreSQL; validación en aplicación para SQLite).

**`festivo`** — id, fecha (única), nombre, es_festivo. Guarda **solo los ajustes manuales**
al calendario: `es_festivo = true` agrega un festivo que la ley no contempla,
`false` anula uno calculado. Los festivos de ley **no se persisten**: se calculan
(ver §5.5).

**`liquidacion`** — id, periodo_id FK, unidad_id FK, version `INT` (únicos como trío),
parametros_snapshot `JSON` (todos los parámetros usados, para reproducibilidad histórica),
creada_en. **Nunca se actualiza:** una corrección genera una versión nueva.

**`liquidacion_empleado`** — id, liquidacion_id FK, empleado_id FK, nombre_empleado,
salario_mensual `NUMERIC`, tarifa_hora `NUMERIC`. Nivel intermedio entre la liquidación y
sus conceptos: congela el nombre y el salario que tenía el empleado al liquidar, para que
una liquidación vieja no cambie si después se le corrige el salario.

**`concepto_liquidado`** — id, liquidacion_empleado_id FK, orden, tipo
(`devengado` | `deduccion`), codigo, nombre, minutos `INT`, tarifa_hora `NUMERIC`,
factor `NUMERIC`, componentes `JSON`, valor `NUMERIC`. `componentes` desglosa de qué se
compone el factor (ej. `{"hora_base": 1, "recargo_dominical_festivo": 0.90}`): es lo que
hace auditable cada peso.

**`concepto_manual`** — id, empleado_id FK, periodo_id FK, tipo
(`devengado` | `deduccion`), nombre, valor `NUMERIC`, salarial. Devengados y deducciones
puntuales de un empleado en una quincena (préstamos, bonos, descuentos). `salarial` solo
aplica a los devengados: indica si suma al IBC.

**`usuario`** — id, email, hash_password (Argon2id), rol
(`admin` | `contadora` | `operador`), activo.

**`sesion`** — id, token_hash, usuario_id FK, expira_en, creada_en. **En la base solo se
guarda el SHA-256 del token**, nunca el token: el valor real vive únicamente en la cookie
`HttpOnly` del navegador.

**`auditoria`** — id, usuario_email, accion, entidad, entidad_id, antes `JSON`,
despues `JSON`, timestamp UTC. **Append-only**: triggers de BD rechazan `UPDATE` y
`DELETE`. Se guarda el correo, no el id, para que el rastro sobreviva a la desactivación
del usuario. Siempre se auditan: cambios de parámetros legales y ediciones de turnos ya
liquidados.

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

⚠️ `horas_quincena` y `divisor_hora_ordinaria` son un **par acoplado**: debe cumplirse
`divisor == 2 × horas_quincena` (110/220 hasta el 14-jul-2026; 105/210 desde el 15-jul),
porque el salario quincenal es `salario/2 = horas_quincena × (salario / divisor)`.
Cambiar uno sin el otro descuadra el tiempo ordinario sin que el motor falle; lo
reporta `incoherencias_horas_quincena()` y se ve en Configuración.

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

- **`semanal_legal`** (default desde el 15-jul-2026): acumulado por semana calendario
  contra `jornada_maxima_semanal` vigente esa semana (44 h → 42 h el 15-jul-2026). Es el
  criterio de la ley: trabajo suplementario es el que excede la jornada ordinaria —8 h/día
  y 42 h/semana— y no se puede promediar ni reubicar (CST art. 159 y 161, Ley 2101/2021).
- **`presupuesto_quincenal`** (default hasta el 14-jul-2026 — método de la contadora): las
  primeras `horas_quincena` del periodo, en orden cronológico, son ordinarias; el excedente
  es extra. **No es un criterio legal**: `horas_quincena` y `divisor_hora_ordinaria` son un
  artificio de mensualización para hallar el valor de la hora (210 h = 42/6 × 30, Concepto
  MinTrabajo 16177 de 2023), no un tope de jornada. Se conserva para reproducir planillas
  históricas y para la marca `sin_extras`.
- **`diaria`**: umbral por día calendario (`horas_jornada_diaria`, 8 h). La cola de un turno
  que cruzó medianoche cuenta en el día siguiente.
- **`jornada`**: umbral por TURNO o jornada continua — los tramos contiguos, aunque crucen
  medianoche, son una sola jornada; un descanso abre otra. Es la regla del art. 7 de la Ley
  1920/2018 para el sector de vigilancia (turnos de hasta 12 h con la jornada ordinaria en
  8 h). Legal, pero más estrecha que el tope semanal.

Si el umbral cae dentro de un tramo, el tramo se parte en dos. La clasificación conserva
franja y tipo de día: una extra nocturna dominical sigue siendo identificable. El golden
test 5 (quincena que cruza el 15-jul-2026) se prueba con dos estrategias.

**La semana no se parte donde se parte la quincena.** `semanal_legal` mide contra un
presupuesto SEMANAL, así que una semana partida por el corte de quincena recibiría 42 h
dos veces. `LiquidarQuincena` carga los turnos de esa semana anteriores al periodo y los
pasa como `tramos_contexto`: consumen presupuesto y no se liquidan (ya se pagaron en su
quincena). Las otras tres estrategias los ignoran.

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
| AUXILIO DE TRANSPORTE (prorrateado) | auxilio_transporte_mensual × horas laboradas / divisor_hora_ordinaria | — |
| DIA 31 | hora_base | 1.00 |

El auxilio se paga quincenal plano por defecto. La marca por empleado y quincena
`auxilio_por_dias_laborados` lo prorratea sobre **lo laborado** (los minutos no-extra,
topados al presupuesto): pesos del mes × horas / horas del mes. Marcada, se paga aunque el
empleado esté `incapacitado` u `ocasional`, que normalmente lo quitan entero. Con la
quincena completa el prorrateo da el mismo valor que el plano.

La marca `pagar_dia_31` cubre el desfase entre el presupuesto y el calendario: la quincena
16–fin de mes se paga siempre como 15 días (`horas_quincena` = divisor/30 × 15), así que en
los meses de 31 ese día queda fuera. Marcada, sus horas no-extra se pagan a `hora_base` ×1 en
la línea `dia_31` (salarial, entra al IBC) y se descuentan de la base del tiempo ordinario
para no pagarlas dos veces; el auxilio no cambia. El corte es «del 31 en adelante», no «el
día 31», para que el turno nocturno que arranca ese día y cruza al mes siguiente entre
completo. Los turnos de relleno (jornada ordinaria) cuentan como cualquier otro: su marca
solo dice que el salario cubre esas horas, y el 31 no las cubre. Verificada contra
`JULIO RIO CLARO 2026.xlsx`.

La misma base alimenta la marca `quincena_incompleta`, que paga el TIEMPO ORDINARIO sobre lo
laborado en vez del presupuesto completo. Las horas festivas y nocturnas **sí** cuentan en
esa base (así lo liquida la contadora y así es coherente con la quincena completa, cuyo
presupuesto también las incluye); las extras no, porque su factor ya trae la `hora_base`.

Cada componente se resuelve contra la vigencia de la **fecha del tramo** (no la fecha del
sistema ni la de liquidación).

`valor = minutos / 60 × tarifa_hora × factor`, con
`tarifa_hora = salario_base_mensual / divisor_hora_ordinaria`.

⚠️ **Factores combinados legados — resuelto el 27-ago-2026.** La planilla de la contadora
usa el festivo diurno actualizado pero los combinados viejos (FESTIVO EXTRA ×2.00,
NOCTURNO DOMINICAL ×2.10, EXTRA NOCTURNO DOMINICAL ×2.50), armados con el recargo
dominical del 75 % anterior a la Ley 2466/2025. Con el 90 % vigente desde el 1-jul-2026
el modelo aditivo da **2.15 / 2.25 / 2.65**, y son los correctos: el override pagaba de
menos. Las unidades se sembraban con esa tabla en `config.factores_override`; la migración
`f2a7c91d40e8` la quita y el motor vuelve a calcularlos de forma aditiva. Los módulos de
referencia (`puebla.py`, `julio_1_15.py`, `thunapa.py`, `rio_claro_16_31.py`) conservan
`FACTORES_OVERRIDE` porque sus golden tests reproducen la planilla histórica al peso.
Ver `docs/reconciliacion-puebla-agosto-2026.md`.

### 5.4 Política de redondeo

Cálculo interno en minutos enteros y `Decimal` sin redondear. Se redondea **una sola
vez, al final, por concepto liquidado**, a pesos enteros con `ROUND_HALF_UP`. Los
totales (por empleado, por unidad) suman conceptos ya redondeados, de modo que el Excel
siempre cuadra visualmente.

### 5.5 Calendario de festivos

Servicio puro: festivos fijos + móviles derivados de Pascua (algoritmo de Butcher) +
traslado a lunes de los festivos que lo exigen (Ley Emiliani 51/1983). Los festivos de ley
**se calculan, no se guardan**; la tabla `festivo` almacena solo los **ajustes manuales**
—altas y anulaciones— que se aplican encima del calendario calculado.
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
| 1 | Dominio puro + motor + festivos + golden tests + CLI | ✅ |
| 2 | Persistencia, parámetros con vigencias, casos de uso, API | ✅ |
| 3 | UI: grilla quincenal, configuración, reportes, Excel | ✅ |
| 4 | Auth, roles, auditoría, cierre de quincenas, hardening | ✅ |
| 5 | Descuento de seguridad social por unidad, conceptos manuales y fijos, estrategia de extras `diaria`, factores por unidad | ✅ |

Una fase a la vez, con revisión del usuario al final de cada una.

> **Las cinco fases del plan original están completas.** Esta tabla queda como registro de
> ese plan. El estado vigente del proyecto y las funciones que se añadieron después
> (jornada ordinaria por turno, quincena incompleta, auxilio prorrateado) se llevan en
> `CLAUDE.md`, que es la fuente única: no dupliquen aquí el estado o volverán a
> desincronizarse.
