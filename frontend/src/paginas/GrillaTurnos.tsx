import { memo, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Empleado, Festivo, Periodo, Turno, Unidad } from "../tipos";
import {
  DIAS_SEMANA,
  HORAS_JORNADA_ORDINARIA_SUGERIDA,
  diasDelPeriodo,
  esTurnoDeRelleno,
  fechaLocal,
  horasAMinutos,
  minutosAHoras,
  minutosDeTurno,
  normalizarHora,
  ventanaJornadaOrdinaria,
} from "../turnos-util";
import { PreviaTurnosEmpleado } from "./PreviaTurnosEmpleado";

/** Referencia estable para celdas sin turnos: evita romper la memoización. */
const SIN_TURNOS: Turno[] = [];

/** Celda con foco/clic: identifica fila (empleado) y columna (día) activas. */
type CeldaActiva = { fila: number; col: number } | null;

export function GrillaTurnos({ unidades, periodos }: { unidades: Unidad[]; periodos: Periodo[] }) {
  const [unidadId, setUnidadId] = useState("");
  const [periodoId, setPeriodoId] = useState("");
  const [empleados, setEmpleados] = useState<Empleado[]>([]);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [festivos, setFestivos] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");
  const [activa, setActiva] = useState<CeldaActiva>(null);
  const [empleadoPrevia, setEmpleadoPrevia] = useState<Empleado | null>(null);

  // Callback estable: solo cambia el estado si la celda activa es distinta,
  // para no re-renderizar celdas ya resaltadas.
  const activar = useCallback((fila: number, col: number) => {
    setActiva((prev) => (prev?.fila === fila && prev?.col === col ? prev : { fila, col }));
  }, []);

  const periodo = periodos.find((p) => p.id === periodoId);
  const dias = useMemo(() => (periodo ? diasDelPeriodo(periodo) : []), [periodo]);
  const soloLectura = periodo !== undefined && periodo.estado !== "abierto";

  const recargarTurnos = useCallback(async () => {
    if (!periodoId || !unidadId) return;
    setTurnos(await api.periodos.turnos(periodoId, unidadId));
  }, [periodoId, unidadId]);

  useEffect(() => {
    if (unidadId) api.empleados.listar(unidadId).then(setEmpleados).catch((e) => setError(e.message));
  }, [unidadId]);

  /** Reemplaza un empleado ya cargado tras editarlo desde la tarjeta. Hay que tocar
   *  las dos piezas de estado: la lista alimenta la grilla y `empleadoPrevia` la
   *  tarjeta abierta, y son objetos distintos. */
  const actualizarEmpleado = useCallback((emp: Empleado) => {
    setEmpleados((prev) => prev.map((e) => (e.id === emp.id ? emp : e)));
    setEmpleadoPrevia((prev) => (prev && prev.id === emp.id ? emp : prev));
  }, []);

  useEffect(() => {
    recargarTurnos().catch((e) => setError(e.message));
  }, [recargarTurnos]);

  useEffect(() => {
    if (!periodo) return;
    const anios = [...new Set(dias.map((d) => Number(d.slice(0, 4))))];
    Promise.all(anios.map((a) => api.festivos.delAnio(a)))
      .then((listas) =>
        setFestivos(new Set(listas.flat().map((f: Festivo) => f.fecha))),
      )
      .catch((e) => setError(e.message));
  }, [periodo, dias]);

  const porEmpleadoYDia = useMemo(() => {
    const mapa = new Map<string, Turno[]>();
    for (const t of turnos) {
      const clave = `${t.empleado_id}|${t.fecha}`;
      mapa.set(clave, [...(mapa.get(clave) ?? []), t]);
    }
    return mapa;
  }, [turnos]);

  const agregarTurno = useCallback(
    async (empleadoId: string, fecha: string, texto: string) => {
      const partes = texto.split("-");
      if (partes.length !== 2) {
        setError(`Turno inválido "${texto}": use el formato inicio-fin, ej. 18:00-06:00`);
        return;
      }
      const inicio = normalizarHora(partes[0]);
      const fin = normalizarHora(partes[1]);
      if (!inicio || !fin) {
        setError(`Horas inválidas en "${texto}"`);
        return;
      }
      setError("");
      try {
        await api.turnos.registrar({
          empleado_id: empleadoId,
          fecha,
          hora_inicio: inicio,
          hora_fin: fin,
        });
        await recargarTurnos();
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [recargarTurnos],
  );

  const marcarJornadaOrdinaria = useCallback(
    async (id: string, minutos: number | null) => {
      try {
        await api.turnos.jornadaOrdinaria(id, minutos);
        await recargarTurnos();
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [recargarTurnos],
  );

  /** Crea un turno de relleno en un día sin turnos: la casilla es lo único que
   *  hay que marcar, el horario lo pone `ventanaJornadaOrdinaria`. */
  const crearTurnoDeRelleno = useCallback(
    async (empleadoId: string, fecha: string, minutos: number) => {
      setError("");
      const { inicio, fin } = ventanaJornadaOrdinaria(minutos);
      try {
        await api.turnos.registrar({
          empleado_id: empleadoId,
          fecha,
          hora_inicio: inicio,
          hora_fin: fin,
          minutos_jornada_ordinaria: minutos,
        });
        await recargarTurnos();
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [recargarTurnos],
  );

  /** En un turno de relleno el horario lo dicta el umbral, así que cambiarlo
   *  obliga a reemplazar el turno (no basta el PATCH de la marca). Se borra antes
   *  de crear para no chocar con la validación de solapamientos. */
  const redimensionarRelleno = useCallback(
    async (turno: Turno, minutos: number) => {
      setError("");
      const { inicio, fin } = ventanaJornadaOrdinaria(minutos);
      try {
        await api.turnos.eliminar(turno.id);
        await api.turnos.registrar({
          empleado_id: turno.empleado_id,
          fecha: turno.fecha,
          hora_inicio: inicio,
          hora_fin: fin,
          minutos_jornada_ordinaria: minutos,
        });
        await recargarTurnos();
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [recargarTurnos],
  );

  const eliminarTurno = useCallback(
    async (id: string) => {
      try {
        await api.turnos.eliminar(id);
        await recargarTurnos();
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [recargarTurnos],
  );

  return (
    <>
      <h2>Cuadro de turnos</h2>
      <div className="fila">
        <label className="campo">
          Unidad residencial
          <select value={unidadId} onChange={(e) => setUnidadId(e.target.value)}>
            <option value="">— seleccione —</option>
            {unidades.map((u) => (
              <option key={u.id} value={u.id}>{u.nombre}</option>
            ))}
          </select>
        </label>
        <label className="campo">
          Quincena
          <select value={periodoId} onChange={(e) => setPeriodoId(e.target.value)}>
            <option value="">— seleccione —</option>
            {periodos.map((p) => (
              <option key={p.id} value={p.id}>
                {p.fecha_inicio} al {p.fecha_fin} ({p.estado})
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && <div className="error">{error}</div>}
      {soloLectura && (
        <div className="pista">
          El periodo está {periodo?.estado}: para corregir turnos, reábralo en «Unidades y
          empleados».
        </div>
      )}

      {unidadId && periodo && (
        <>
          <p className="pista">
            Escriba el turno en la celda y presione Enter, ej. <b>06:00-18:00</b> o{" "}
            <b>18-6</b> (cruza medianoche). Celda vacía = descanso. Puede agregar más de un
            turno por día (turno partido).
          </p>
          <div className="grilla-envoltura">
            <table className="grilla">
              <thead>
                <tr>
                  <th className="esquina">Empleado</th>
                  {dias.map((d, col) => {
                    const fecha = fechaLocal(d);
                    const especial = festivos.has(d) || fecha.getDay() === 0;
                    const clases = [
                      especial ? "dia-descanso" : "",
                      activa?.col === col ? "col-activa" : "",
                    ].filter(Boolean).join(" ");
                    return (
                      <th key={d} className={clases}>
                        {fecha.getDate()}
                        <br />
                        <small>{DIAS_SEMANA[fecha.getDay()]}{festivos.has(d) ? " ✦" : ""}</small>
                      </th>
                    );
                  })}
                  <th>Total h</th>
                </tr>
              </thead>
              <tbody>
                {empleados.map((emp, fila) => {
                  const minutos = turnos
                    .filter((t) => t.empleado_id === emp.id)
                    .reduce((suma, t) => suma + minutosDeTurno(t), 0);
                  const filaActiva = activa?.fila === fila;
                  return (
                    <tr key={emp.id}>
                      <td
                        className={`nombre-empleado${filaActiva ? " fila-activa" : ""}`}
                        title={emp.cargo}
                      >
                        <span className="nombre-empleado-contenido">
                          <button
                            type="button"
                            className="boton-previa"
                            title="Previsualizar turnos (formato tarjeta)"
                            onClick={() => setEmpleadoPrevia(emp)}
                          >
                            🗂
                          </button>
                          {emp.nombre}
                          {emp.incapacitado && (
                            <span className="marca-incapacitado" title="Incapacitado">
                              ✚
                            </span>
                          )}
                        </span>
                      </td>
                      {dias.map((d, col) => (
                        <CeldaTurno
                          key={d}
                          empleadoId={emp.id}
                          fecha={d}
                          fila={fila}
                          col={col}
                          esActiva={filaActiva && activa?.col === col}
                          esFila={filaActiva}
                          esColumna={activa?.col === col}
                          turnos={porEmpleadoYDia.get(`${emp.id}|${d}`) ?? SIN_TURNOS}
                          soloLectura={soloLectura}
                          alActivar={activar}
                          alAgregar={agregarTurno}
                          alEliminar={eliminarTurno}
                          alMarcarJornada={marcarJornadaOrdinaria}
                          alCrearRelleno={crearTurnoDeRelleno}
                          alRedimensionarRelleno={redimensionarRelleno}
                        />
                      ))}
                      <td className={`total${filaActiva ? " fila-activa" : ""}`}>
                        {(minutos / 60).toFixed(1)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {empleados.length === 0 && (
            <p className="pista">La unidad no tiene empleados: créelos en «Unidades y empleados».</p>
          )}
          {empleadoPrevia && (
            <PreviaTurnosEmpleado
              empleado={empleadoPrevia}
              unidad={unidades.find((u) => u.id === unidadId)!}
              periodo={periodo}
              dias={dias}
              festivos={festivos}
              turnos={turnos.filter((t) => t.empleado_id === empleadoPrevia.id)}
              soloLectura={soloLectura}
              alCerrar={() => setEmpleadoPrevia(null)}
              alGuardado={recargarTurnos}
              alActualizarEmpleado={actualizarEmpleado}
            />
          )}
        </>
      )}
    </>
  );
}

type CeldaTurnoProps = {
  empleadoId: string;
  fecha: string;
  fila: number;
  col: number;
  esActiva: boolean;
  esFila: boolean;
  esColumna: boolean;
  turnos: Turno[];
  soloLectura: boolean;
  alActivar: (fila: number, col: number) => void;
  alAgregar: (empleadoId: string, fecha: string, texto: string) => void;
  alEliminar: (id: string) => void;
  alMarcarJornada: (id: string, minutos: number | null) => void;
  alCrearRelleno: (empleadoId: string, fecha: string, minutos: number) => void;
  alRedimensionarRelleno: (turno: Turno, minutos: number) => void;
};

// `memo`: con props estables (callbacks + primitivos), al cambiar la celda
// activa solo se re-renderizan las celdas cuyo resaltado cambió.
const CeldaTurno = memo(function CeldaTurno({
  empleadoId,
  fecha,
  fila,
  col,
  esActiva,
  esFila,
  esColumna,
  turnos,
  soloLectura,
  alActivar,
  alAgregar,
  alEliminar,
  alMarcarJornada,
  alCrearRelleno,
  alRedimensionarRelleno,
}: CeldaTurnoProps) {
  const [texto, setTexto] = useState("");
  const clases = [
    "celda-turno",
    esActiva ? "activa" : "",
    esFila ? "fila-activa" : "",
    esColumna ? "col-activa" : "",
  ].filter(Boolean).join(" ");
  return (
    <td
      className={clases}
      onFocus={() => alActivar(fila, col)}
      onClick={() => alActivar(fila, col)}
    >
      {turnos.map((t) => (
        <span
          key={t.id}
          className={`chip${t.cruza_medianoche ? " nocturno" : ""}${
            t.minutos_jornada_ordinaria !== null ? " jornada-ordinaria" : ""
          }`}
        >
          <span className="chip-horas">
            {normalizarHora(t.hora_inicio) ?? t.hora_inicio}–
            {normalizarHora(t.hora_fin) ?? t.hora_fin}
            {!soloLectura && (
              <button title="Eliminar turno" onClick={() => alEliminar(t.id)}>×</button>
            )}
          </span>
          {!soloLectura && (
            <MarcaJornadaOrdinaria
              turno={t}
              alMarcar={alMarcarJornada}
              alEliminar={alEliminar}
              alRedimensionar={alRedimensionarRelleno}
            />
          )}
        </span>
      ))}
      {!soloLectura && (
        <input
          value={texto}
          placeholder="hh-hh"
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && texto.trim()) {
              alAgregar(empleadoId, fecha, texto);
              setTexto("");
            }
          }}
        />
      )}
      {/* Día de descanso: la casilla crea por sí sola el turno de relleno. */}
      {!soloLectura && turnos.length === 0 && (
        <label className="marca-jornada" title={TITULO_JORNADA_ORDINARIA}>
          <input
            type="checkbox"
            checked={false}
            onChange={() =>
              alCrearRelleno(empleadoId, fecha, HORAS_JORNADA_ORDINARIA_SUGERIDA * 60)
            }
          />
          ord.
        </label>
      )}
    </td>
  );
});


const TITULO_JORNADA_ORDINARIA =
  "Jornada ordinaria: el turno se registró para cuadrar las horas de la quincena, " +
  "no porque se trabajara. Las primeras horas indicadas no pagan recargo festivo " +
  "ni nocturno; solo el excedente se reconoce, como hora extra.";

/** Casilla «jornada ordinaria» de un turno, con el umbral en horas. */
function MarcaJornadaOrdinaria({
  turno,
  alMarcar,
  alEliminar,
  alRedimensionar,
}: {
  turno: Turno;
  alMarcar: (id: string, minutos: number | null) => void;
  alEliminar: (id: string) => void;
  alRedimensionar: (turno: Turno, minutos: number) => void;
}) {
  const marcado = turno.minutos_jornada_ordinaria !== null;
  const guardadas =
    turno.minutos_jornada_ordinaria === null ? "" : minutosAHoras(turno.minutos_jornada_ordinaria);
  const [horas, setHoras] = useState(guardadas);
  // Turno que existe solo por la marca: la casilla lo creó y la casilla lo quita.
  const esRelleno = esTurnoDeRelleno(
    turno.hora_inicio,
    turno.hora_fin,
    turno.minutos_jornada_ordinaria,
  );

  // El valor lo manda el servidor: al recargar los turnos se resincroniza.
  useEffect(() => setHoras(guardadas), [guardadas]);

  function confirmar() {
    const minutos = horasAMinutos(horas);
    if (minutos === null) {
      setHoras(guardadas); // entrada inválida: se descarta
      return;
    }
    if (minutos === turno.minutos_jornada_ordinaria) return;
    // En un relleno el horario lo dicta el umbral: hay que reemplazar el turno.
    if (esRelleno) alRedimensionar(turno, minutos);
    else alMarcar(turno.id, minutos);
  }

  function alternar(marcar: boolean) {
    if (marcar) {
      alMarcar(turno.id, HORAS_JORNADA_ORDINARIA_SUGERIDA * 60);
      return;
    }
    if (esRelleno) alEliminar(turno.id); // desmarcar un relleno = quitar el turno
    else alMarcar(turno.id, null);
  }

  return (
    <span className="marca-jornada" title={TITULO_JORNADA_ORDINARIA}>
      <label>
        <input
          type="checkbox"
          checked={marcado}
          onChange={(e) => alternar(e.target.checked)}
        />
        ord.
      </label>
      {marcado && (
        <input
          className="horas-jornada"
          value={horas}
          inputMode="decimal"
          aria-label="Horas de jornada ordinaria"
          onChange={(e) => setHoras(e.target.value)}
          onBlur={confirmar}
          onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
        />
      )}
    </span>
  );
}
