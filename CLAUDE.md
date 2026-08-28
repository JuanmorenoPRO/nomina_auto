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

Dos avisos que ya costaron un error de dinero:

- **`horas_quincena` y `divisor_hora_ordinaria` se mueven SIEMPRE juntos.** El salario
  quincenal es `salario/2` y el motor lo paga como `horas_quincena × (salario / divisor)`,
  así que debe cumplirse `divisor == 2 × horas_quincena` (110/220 hasta el 14-jul-2026,
  105/210 desde el 15-jul). Cambiar uno solo descuadra el tiempo ordinario sin que nada
  falle. Lo verifica `incoherencias_horas_quincena()` y se avisa en Configuración.
- **`sembrar_parametros` es idempotente POR CÓDIGO**, así que solo agrega códigos nuevos:
  si se cambia la vigencia de un parámetro ya sembrado, las bases existentes NO se enteran.
  Ese cambio exige una **migración de datos** (plantilla:
  `c1b7e40a9f38_horas_quincena_105_desde_jul_2026.py`).

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
  permisos verificados en backend; auditoría append-only; una quincena cerrada es de
  solo lectura (no se puede reliquidar). Mientras el periodo está abierto, reliquidar una
  unidad **reemplaza** su liquidación anterior: solo se conserva la última (el cambio queda
  registrado en la auditoría append-only).

## Motor de cálculo (resumen)

1. **Segmentación:** cada turno se parte en tramos homogéneos por cortes sucesivos:
   (a) medianoche (día calendario), (b) límites de jornada nocturna vigentes ese día,
   (c) tipo de día (`festivo` > `dominical` > `ordinario`). La regla de la contadora
   («el sábado que amanece festivo cambia a festivo a las 12 de la noche») emerge del
   corte por medianoche — no es un caso especial.
2. **Invariante:** la suma de los minutos de los tramos = duración del turno, siempre.
3. **Clasificación extra/ordinaria:** estrategia parametrizable
   (`estrategia_clasificacion_extras`), cuatro opciones. **Default y criterio legal desde
   el 15-jul-2026: `semanal_legal`** (42 h por semana). El trabajo suplementario es el que
   excede la jornada ordinaria —8 h/día y 42 h/semana, CST art. 159 y 161, Ley 2101/2021—
   y no se puede promediar ni reubicar. Las otras tres: `presupuesto_quincenal` (105 h de
   la quincena; método de la contadora, **no es un criterio legal** — ver la regla de abajo),
   `diaria` (8 h por día calendario) y `jornada` (8 h por turno continuo; es la regla del
   art. 7 de la Ley 1920/2018 para vigilancia).
   `semanal_legal` mide contra un presupuesto SEMANAL, así que la semana **no** se reinicia
   en el corte de quincena: `LiquidarQuincena` carga los turnos previos de esa misma semana
   y los pasa como `tramos_contexto` (consumen presupuesto, no se liquidan).
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
- **Divisor ≠ tope de jornada:** `horas_quincena` (105) y `divisor_hora_ordinaria` (210)
  son un artificio de **mensualización** para hallar el valor de la hora ordinaria
  (210 = 42/6 × 30, Concepto MinTrabajo 16177 de 2023). No son un límite de horas: usarlos
  para decidir qué es hora extra confunde el denominador con el tope. Fue el error de fondo
  de la planilla de agosto-2026 (`docs/reconciliacion-puebla-agosto-2026.md`).
- **Horas sin hora base (alarma):** el tiempo ordinario se paga como presupuesto fijo, así
  que si la estrategia de extras deja más horas no-extra de las que ese presupuesto y el
  día 31 cubren, esas horas cobran su recargo pero no su hora base. `Liquidacion.
  minutos_sin_hora_base` lo expone y la UI lo avisa en el detalle; no cambia ningún valor.
- **Jornada ordinaria (marca por turno):** turno registrado solo para cuadrar las horas
  de la quincena, no porque se trabajara. Sus primeras N horas (`minutos_jornada_ordinaria`,
  digitado en el turno) no pagan recargo dominical/festivo ni nocturno — las cubre el
  salario — y solo el excedente sobre N se reconoce, como hora extra con su tipo de día
  real. La clasificación la hace la segmentación; el clasificador de extras no la toca.
- **Lo laborado (base compartida):** todos los minutos trabajados que **no** sean extra
  —ordinarios, festivos y nocturnos por igual—, topados al presupuesto de la quincena. Es la
  base de las dos marcas de abajo. Las horas festivas entran porque en la quincena completa
  el presupuesto también las incluye (la planilla liquida las 105 h de TIEMPO ORDINARIO con
  las festivas dentro, y encima paga TIEMPO FESTIVO ×1.90); excluirlas solo al prorratear le
  pagaría menos al empleado parcial que al completo por la misma hora. Las extras no entran:
  se pagan por encima del presupuesto y su factor ya trae la `hora_base`.
- **Quincena incompleta (marca por empleado y quincena):** el tiempo ordinario se paga sobre
  «lo laborado» en vez del presupuesto completo. No suprime nada más: dominicales, recargos
  nocturnos y extras se siguen liquidando en sus propias líneas.
- **Auxilio prorrateado (marca por empleado y quincena):** el auxilio de transporte se paga
  en proporción a lo laborado, `mensual × horas / divisor_hora_ordinaria`, en vez del
  quincenal plano. Es la cuenta de la contadora (`mensual/30 × días`, con `días = horas /
  jornada`) reducida a horas. La marca **manda** sobre `incapacitado`/`ocasional`: marcada,
  el auxilio se paga aunque esos estados lo quiten entero. Con la quincena completa da el
  mismo valor que el plano. Referencia verificada: `tests/dominio/golden/test_golden_lorena.py`.
- **Día 31 (marca por empleado y quincena):** la quincena 16–fin de mes se paga SIEMPRE
  como 15 días (`horas_quincena` = `divisor_hora_ordinaria`/30 × 15), tenga el mes 30 o 31.
  En los meses de 31, ese día es un 16.º día que el salario no cubre: marcada, sus horas
  **no-extra** se reconocen aparte a hora base (concepto `dia_31`, ×1, salarial). Los
  recargos y las extras del 31 ya se pagan en sus propias líneas — aquí solo se agrega la
  hora base que falta. Se cuenta **del 31 en adelante**, para que el turno nocturno que
  arranca ese día y cruza al 1.º del mes siguiente entre completo (se liquida en esta
  quincena y tampoco lo cubre el presupuesto). Los turnos de relleno (jornada ordinaria)
  **sí** cuentan: su marca significa «esto lo cubre el salario», y el 31 no lo cubre.
  No toca el auxilio, que sigue siendo el de 15 días.
  Referencia verificada: `tests/dominio/golden/test_golden_rio_claro_16_31.py`.
- **Liquidación:** resultado de calcular una quincena; inmutable una vez cerrada.
- **Cierre:** paso a solo lectura de una quincena aprobada; ya no se puede reliquidar.
  Mientras esté abierta, reliquidar reemplaza la liquidación previa (solo la última).
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

- [x] **Fase 5:** unidades con **descuento de seguridad social** (opción por unidad:
      salud 4% + pensión 4% sobre IBC, tasas parametrizadas), deducciones y `VALOR A PAGAR`
      en liquidación/Excel, conceptos manuales (devengados/deducciones por empleado+periodo),
      estrategia de extras `diaria` (umbral 8 h/día) y factores por unidad (`config`).
      Unidad de referencia EDIFICIO PUEBLA P.H en `nomina/puebla.py` + golden test.

**Todas las fases del plan original están completas.** Pendientes de negocio (ver
memoria/docs): confirmar con la contadora los factores combinados y su regla real de
clasificación de extras, y verificar el auxilio de transporte 2026 contra el decreto.
Los valores legales de referencia (tabla en `docs/arquitectura.md`) deben verificarse
contra fuente oficial antes de producción.
