import { useMemo, useState } from "react";
import { api } from "../api";
import type { Empleado, Periodo, Turno, Unidad } from "../tipos";
import { DIAS_SEMANA, fechaLocal, minutosDeTurno, normalizarHora } from "../turnos-util";

type Par = { inicio: string; fin: string };

/** Agrupa los turnos del empleado por fecha ISO en pares editables inicio/fin.
 *  Normaliza a "HH:MM" (el backend devuelve las horas como "HH:MM:SS"). */
function paresIniciales(dias: string[], turnos: Turno[]): Record<string, Par[]> {
  const mapa: Record<string, Par[]> = {};
  for (const d of dias) mapa[d] = [];
  for (const t of turnos) {
    if (!mapa[t.fecha]) mapa[t.fecha] = [];
    mapa[t.fecha].push({
      inicio: normalizarHora(t.hora_inicio) ?? t.hora_inicio,
      fin: normalizarHora(t.hora_fin) ?? t.hora_fin,
    });
  }
  return mapa;
}

/** Clave estable de un turno para el diff al guardar. */
function clave(fecha: string, inicio: string, fin: string): string {
  return `${fecha}|${inicio}|${fin}`;
}

export function PreviaTurnosEmpleado({
  empleado,
  unidad,
  periodo,
  dias,
  festivos,
  turnos,
  soloLectura,
  alCerrar,
  alGuardado,
}: {
  empleado: Empleado;
  unidad: Unidad;
  periodo: Periodo;
  dias: string[];
  festivos: Set<string>;
  turnos: Turno[];
  soloLectura: boolean;
  alCerrar: () => void;
  alGuardado: () => void;
}) {
  const [pares, setPares] = useState<Record<string, Par[]>>(() =>
    paresIniciales(dias, turnos),
  );
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  function editar(dia: string, idx: number, campo: keyof Par, valor: string) {
    setPares((prev) => {
      const copia = prev[dia].map((p, i) => (i === idx ? { ...p, [campo]: valor } : p));
      return { ...prev, [dia]: copia };
    });
  }

  function agregarPar(dia: string) {
    setPares((prev) => ({ ...prev, [dia]: [...prev[dia], { inicio: "", fin: "" }] }));
  }

  function quitarPar(dia: string, idx: number) {
    setPares((prev) => ({ ...prev, [dia]: prev[dia].filter((_, i) => i !== idx) }));
  }

  /** Minutos de un día usando solo los pares con horas válidas. */
  function minutosDia(dia: string): number {
    return (pares[dia] ?? []).reduce((suma, p) => {
      const inicio = normalizarHora(p.inicio);
      const fin = normalizarHora(p.fin);
      if (!inicio || !fin) return suma;
      return suma + minutosDeTurno({ hora_inicio: inicio, hora_fin: fin });
    }, 0);
  }

  const totalMinutos = useMemo(
    () => dias.reduce((suma, d) => suma + minutosDia(d), 0),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [pares, dias],
  );

  async function guardar() {
    setError("");
    // Normalizar y validar todos los pares con contenido.
    const editados: { fecha: string; inicio: string; fin: string }[] = [];
    for (const d of dias) {
      for (const p of pares[d] ?? []) {
        const vacio = !p.inicio.trim() && !p.fin.trim();
        if (vacio) continue; // par en blanco = sin turno
        const inicio = normalizarHora(p.inicio);
        const fin = normalizarHora(p.fin);
        if (!inicio || !fin) {
          setError(`Horas inválidas el ${d}: revise "${p.inicio || "—"}" / "${p.fin || "—"}".`);
          return;
        }
        editados.push({ fecha: d, inicio, fin });
      }
    }

    // Normalizar también las horas de los originales ("HH:MM:SS" del backend)
    // para que el diff no borre/recree turnos que no cambiaron.
    const claveTurno = (t: Turno) =>
      clave(t.fecha, normalizarHora(t.hora_inicio) ?? t.hora_inicio, normalizarHora(t.hora_fin) ?? t.hora_fin);
    const clavesEditadas = new Set(editados.map((e) => clave(e.fecha, e.inicio, e.fin)));
    const clavesOriginales = new Set(turnos.map(claveTurno));

    const aBorrar = turnos.filter((t) => !clavesEditadas.has(claveTurno(t)));
    const aCrear = editados.filter((e) => !clavesOriginales.has(clave(e.fecha, e.inicio, e.fin)));

    setGuardando(true);
    try {
      // Borrar antes de crear evita falsos solapes con el turno que se reemplaza.
      for (const t of aBorrar) await api.turnos.eliminar(t.id);
      for (const e of aCrear) {
        await api.turnos.registrar({
          empleado_id: empleado.id,
          fecha: e.fecha,
          hora_inicio: e.inicio,
          hora_fin: e.fin,
        });
      }
      alGuardado();
      alCerrar();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.4)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
      }}
      onClick={(e) => e.target === e.currentTarget && alCerrar()}
    >
      <div className="tarjeta modal-previa">
        <div className="previa-encabezado">
          <div>
            <span className="previa-etiqueta">EDIFICIO</span> {unidad.nombre}
          </div>
          <div>
            <span className="previa-etiqueta">NOMBRE Y APELLIDO</span> {empleado.nombre}
          </div>
          <div>
            <span className="previa-etiqueta">C.C.</span> {empleado.documento}
          </div>
          <div>
            <span className="previa-etiqueta">MES</span> del {periodo.fecha_inicio} al{" "}
            {periodo.fecha_fin}
          </div>
        </div>

        {error && <div className="error">{error}</div>}
        {soloLectura && (
          <div className="pista">
            El periodo está {periodo.estado}: para corregir turnos, reábralo en «Unidades y
            empleados».
          </div>
        )}

        <div className="previa-scroll">
          <table className="tarjeta-turnos">
            <thead>
              <tr>
                <th>Día</th>
                <th>N.º</th>
                <th>Entra</th>
                <th>Sale</th>
                <th>Total h</th>
                <th>Descanso</th>
              </tr>
            </thead>
            <tbody>
              {dias.map((d) => {
                const fecha = fechaLocal(d);
                const esFestivo = festivos.has(d);
                const esDomingo = fecha.getDay() === 0;
                const filaPares = pares[d] ?? [];
                const min = minutosDia(d);
                const descanso = filaPares.every((p) => !p.inicio.trim() && !p.fin.trim());
                return (
                  <tr key={d} className={esFestivo || esDomingo ? "dia-descanso" : ""}>
                    <td>
                      {DIAS_SEMANA[fecha.getDay()]}
                      {esFestivo ? " ✦" : ""}
                    </td>
                    <td className="num-dia">{fecha.getDate()}</td>
                    <td className="celda-horas">
                      {filaPares.length === 0 && <span className="atenuado">—</span>}
                      {filaPares.map((p, i) => (
                        <div key={i} className="linea-hora">
                          {soloLectura ? (
                            <span>{p.inicio || "—"}</span>
                          ) : (
                            <input
                              value={p.inicio}
                              placeholder="hh"
                              onChange={(e) => editar(d, i, "inicio", e.target.value)}
                            />
                          )}
                        </div>
                      ))}
                    </td>
                    <td className="celda-horas">
                      {filaPares.length === 0 && <span className="atenuado">—</span>}
                      {filaPares.map((p, i) => (
                        <div key={i} className="linea-hora">
                          {soloLectura ? (
                            <span>{p.fin || "—"}</span>
                          ) : (
                            <>
                              <input
                                value={p.fin}
                                placeholder="hh"
                                onChange={(e) => editar(d, i, "fin", e.target.value)}
                              />
                              <button
                                type="button"
                                title="Quitar turno"
                                className="quitar-par"
                                onClick={() => quitarPar(d, i)}
                              >
                                ×
                              </button>
                            </>
                          )}
                        </div>
                      ))}
                    </td>
                    <td className="total">{min > 0 ? (min / 60).toFixed(1) : ""}</td>
                    <td className="celda-descanso">
                      {descanso && <span className="atenuado">Descanso</span>}
                      {!soloLectura && (
                        <button
                          type="button"
                          className="agregar-par"
                          title="Agregar turno (turno partido)"
                          onClick={() => agregarPar(d)}
                        >
                          + turno
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={4} style={{ textAlign: "right", fontWeight: 600 }}>
                  Total quincena
                </td>
                <td className="total">{(totalMinutos / 60).toFixed(1)}</td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>

        <div className="fila" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="secundario" onClick={alCerrar}>
            {soloLectura ? "Cerrar" : "Cancelar"}
          </button>
          {!soloLectura && (
            <button type="button" className="principal" disabled={guardando} onClick={guardar}>
              {guardando ? "Guardando…" : "Guardar cambios"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
