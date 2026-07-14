import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Empleado, Festivo, Periodo, Turno, Unidad } from "../tipos";

const DIAS_SEMANA = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];

function fechaLocal(iso: string): Date {
  const [a, m, d] = iso.split("-").map(Number);
  return new Date(a, m - 1, d);
}

function diasDelPeriodo(periodo: Periodo): string[] {
  const dias: string[] = [];
  const fin = fechaLocal(periodo.fecha_fin);
  for (let f = fechaLocal(periodo.fecha_inicio); f <= fin; f.setDate(f.getDate() + 1)) {
    const mes = String(f.getMonth() + 1).padStart(2, "0");
    const dia = String(f.getDate()).padStart(2, "0");
    dias.push(`${f.getFullYear()}-${mes}-${dia}`);
  }
  return dias;
}

/** Acepta "18", "18:30", "6" y devuelve "HH:MM"; null si no es una hora. */
function normalizarHora(texto: string): string | null {
  const limpio = texto.trim();
  const m = /^(\d{1,2})(?::(\d{2}))?$/.exec(limpio);
  if (!m) return null;
  const horas = Number(m[1]);
  const minutos = Number(m[2] ?? "0");
  if (horas > 23 || minutos > 59) return null;
  return `${String(horas).padStart(2, "0")}:${String(minutos).padStart(2, "0")}`;
}

function minutosDeTurno(t: Turno): number {
  const [hi, mi] = t.hora_inicio.split(":").map(Number);
  const [hf, mf] = t.hora_fin.split(":").map(Number);
  const inicio = hi * 60 + mi;
  const fin = hf * 60 + mf;
  return fin <= inicio ? fin + 24 * 60 - inicio : fin - inicio;
}

export function GrillaTurnos({ unidades, periodos }: { unidades: Unidad[]; periodos: Periodo[] }) {
  const [unidadId, setUnidadId] = useState("");
  const [periodoId, setPeriodoId] = useState("");
  const [empleados, setEmpleados] = useState<Empleado[]>([]);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [festivos, setFestivos] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");

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

  async function agregarTurno(empleadoId: string, fecha: string, texto: string) {
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
  }

  async function eliminarTurno(id: string) {
    try {
      await api.turnos.eliminar(id);
      await recargarTurnos();
    } catch (e) {
      setError((e as Error).message);
    }
  }

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
                  <th>Empleado</th>
                  {dias.map((d) => {
                    const fecha = fechaLocal(d);
                    const especial = festivos.has(d) || fecha.getDay() === 0;
                    return (
                      <th key={d} className={especial ? "dia-descanso" : ""}>
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
                {empleados.map((emp) => {
                  const minutos = turnos
                    .filter((t) => t.empleado_id === emp.id)
                    .reduce((suma, t) => suma + minutosDeTurno(t), 0);
                  return (
                    <tr key={emp.id}>
                      <td className="nombre-empleado" title={emp.cargo}>{emp.nombre}</td>
                      {dias.map((d) => (
                        <CeldaTurno
                          key={d}
                          turnos={porEmpleadoYDia.get(`${emp.id}|${d}`) ?? []}
                          soloLectura={soloLectura}
                          alAgregar={(texto) => agregarTurno(emp.id, d, texto)}
                          alEliminar={eliminarTurno}
                        />
                      ))}
                      <td className="total">{(minutos / 60).toFixed(1)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {empleados.length === 0 && (
            <p className="pista">La unidad no tiene empleados: créelos en «Unidades y empleados».</p>
          )}
        </>
      )}
    </>
  );
}

function CeldaTurno({
  turnos,
  soloLectura,
  alAgregar,
  alEliminar,
}: {
  turnos: Turno[];
  soloLectura: boolean;
  alAgregar: (texto: string) => void;
  alEliminar: (id: string) => void;
}) {
  const [texto, setTexto] = useState("");
  return (
    <td className="celda-turno">
      {turnos.map((t) => (
        <span key={t.id} className={`chip${t.cruza_medianoche ? " nocturno" : ""}`}>
          {t.hora_inicio}–{t.hora_fin}
          {!soloLectura && (
            <button title="Eliminar turno" onClick={() => alEliminar(t.id)}>×</button>
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
              alAgregar(texto);
              setTexto("");
            }
          }}
        />
      )}
    </td>
  );
}
