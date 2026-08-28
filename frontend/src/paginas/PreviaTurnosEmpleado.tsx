import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Empleado, Periodo, Turno, Unidad } from "../tipos";
import {
  DIAS_SEMANA,
  HORAS_JORNADA_ORDINARIA_SUGERIDA,
  esTurnoDeRelleno,
  fechaLocal,
  horasAMinutos,
  minutosAHoras,
  minutosDeTurno,
  normalizarHora,
  ventanaJornadaOrdinaria,
} from "../turnos-util";

/** `jornadaOrdinaria` es el texto de las horas (null = sin marcar): se guarda como
 *  texto igual que `inicio`/`fin` para poder escribir "7,5" sin reformatear en cada
 *  tecla; se valida al confirmar. `relleno` marca las filas cuyo horario lo dicta el
 *  umbral (ver `esTurnoDeRelleno`): cambiarlo las redimensiona. */
type Par = { inicio: string; fin: string; jornadaOrdinaria: string | null; relleno: boolean };

const PAR_VACIO: Par = { inicio: "", fin: "", jornadaOrdinaria: null, relleno: false };

/** Agrupa los turnos del empleado por fecha ISO en pares editables inicio/fin.
 *  Normaliza a "HH:MM" (el backend devuelve las horas como "HH:MM:SS"). */
function paresIniciales(dias: string[], turnos: Turno[]): Record<string, Par[]> {
  const mapa: Record<string, Par[]> = {};
  for (const d of dias) mapa[d] = [];
  for (const t of turnos) {
    if (!mapa[t.fecha]) mapa[t.fecha] = [];
    const inicio = normalizarHora(t.hora_inicio) ?? t.hora_inicio;
    const fin = normalizarHora(t.hora_fin) ?? t.hora_fin;
    mapa[t.fecha].push({
      inicio,
      fin,
      jornadaOrdinaria:
        t.minutos_jornada_ordinaria === null
          ? null
          : minutosAHoras(t.minutos_jornada_ordinaria),
      // Se deriva del dato guardado, así que sobrevive a recargar la página.
      relleno: esTurnoDeRelleno(inicio, fin, t.minutos_jornada_ordinaria),
    });
  }
  // Cada día arranca con al menos una fila editable (como la celda de la grilla):
  // se escribe la hora directamente y, si se deja vacía, es un día de descanso.
  for (const d of dias) if (mapa[d].length === 0) mapa[d].push(PAR_VACIO);
  return mapa;
}

/** Estados del empleado editables desde la tarjeta: los mismos de «Unidades y
 *  empleados», aquí para no tener que cambiar de pestaña a mitad de la digitación.
 *  Cada uno se guarda solo, con un PATCH que lleva únicamente su clave. */
const ESTADOS_EMPLEADO = [
  { campo: "activo", etiqueta: "Activo", titulo: "Un empleado inactivo no entra en la liquidación." },
  {
    campo: "incapacitado",
    etiqueta: "Incapacitado",
    titulo: "Incapacitado: sin auxilio de transporte, salvo que se prorratee por lo laborado.",
  },
  {
    campo: "ocasional",
    etiqueta: "Ocasional",
    titulo: "Ocasional: sin auxilio de transporte, salvo que se prorratee por lo laborado.",
  },
] as const;

type CampoEstado = (typeof ESTADOS_EMPLEADO)[number]["campo"];

const TITULO_AUXILIO_POR_DIAS =
  "El auxilio de transporte se paga en proporción a las horas laboradas de la quincena " +
  "(auxilio mensual × horas ÷ horas del mes), en vez del auxilio quincenal completo. " +
  "Marcado, se paga aunque el empleado esté incapacitado u ocasional.";

const TITULO_PAGAR_DIA_31 =
  "La quincena se paga siempre como 15 días, así que en los meses de 31 ese día " +
  "queda fuera del presupuesto. Marcado, sus horas trabajadas (las que no sean " +
  "extra) se reconocen aparte a hora base, en la línea DIA 31. Los recargos y las " +
  "extras del 31 ya se pagan en sus propias líneas.";

const TITULO_JORNADA_ORDINARIA =
  "Jornada ordinaria: el turno se registró para cuadrar las horas de la quincena, " +
  "no porque se trabajara. Las primeras horas indicadas no pagan recargo festivo " +
  "ni nocturno; solo el excedente se reconoce, como hora extra.";

/** Clave estable de un turno para el diff al guardar. */
function clave(fecha: string, inicio: string, fin: string): string {
  return `${fecha}|${inicio}|${fin}`;
}

/** Clave de un turno del servidor, con las horas normalizadas a "HH:MM". */
function claveTurno(t: Turno): string {
  return clave(
    t.fecha,
    normalizarHora(t.hora_inicio) ?? t.hora_inicio,
    normalizarHora(t.hora_fin) ?? t.hora_fin,
  );
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
  alActualizarEmpleado,
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
  /** Devuelve al padre el empleado ya actualizado tras cambiar uno de sus estados,
   *  para que la grilla y esta tarjeta no queden mostrando datos distintos. */
  alActualizarEmpleado: (empleado: Empleado) => void;
}) {
  const [pares, setPares] = useState<Record<string, Par[]>>(() =>
    paresIniciales(dias, turnos),
  );
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [quincenaIncompleta, setQuincenaIncompleta] = useState(false);
  const [guardandoIncompleta, setGuardandoIncompleta] = useState(false);
  const [sinExtras, setSinExtras] = useState(false);
  const [guardandoSinExtras, setGuardandoSinExtras] = useState(false);
  const [auxilioPorDias, setAuxilioPorDias] = useState(false);
  const [guardandoAuxilio, setGuardandoAuxilio] = useState(false);
  const [pagarDia31, setPagarDia31] = useState(false);
  const [guardandoDia31, setGuardandoDia31] = useState(false);
  const [guardandoEstado, setGuardandoEstado] = useState<CampoEstado | null>(null);

  useEffect(() => {
    api.ajustesQuincena
      .obtener(empleado.id, periodo.id)
      .then((a) => {
        setQuincenaIncompleta(a.quincena_incompleta);
        setSinExtras(a.sin_extras);
        setAuxilioPorDias(a.auxilio_por_dias_laborados);
        setPagarDia31(a.pagar_dia_31);
      })
      .catch((e) => setError(e.message));
  }, [empleado.id, periodo.id]);

  /** Cambia uno de los estados del empleado (activo/incapacitado/ocasional). El
   *  PATCH lleva solo esa clave y el empleado actualizado sube al padre. */
  async function marcarEstado(campo: CampoEstado, valor: boolean) {
    setError("");
    setGuardandoEstado(campo);
    try {
      alActualizarEmpleado(await api.empleados.actualizar(empleado.id, { [campo]: valor }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setGuardandoEstado(null);
    }
  }

  async function marcarQuincenaIncompleta(valor: boolean) {
    setError("");
    setGuardandoIncompleta(true);
    try {
      await api.ajustesQuincena.marcar(empleado.id, periodo.id, { quincena_incompleta: valor });
      setQuincenaIncompleta(valor);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setGuardandoIncompleta(false);
    }
  }

  async function marcarSinExtras(valor: boolean) {
    setError("");
    setGuardandoSinExtras(true);
    try {
      await api.ajustesQuincena.marcar(empleado.id, periodo.id, { sin_extras: valor });
      setSinExtras(valor);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setGuardandoSinExtras(false);
    }
  }

  async function marcarAuxilioPorDias(valor: boolean) {
    setError("");
    setGuardandoAuxilio(true);
    try {
      await api.ajustesQuincena.marcar(empleado.id, periodo.id, {
        auxilio_por_dias_laborados: valor,
      });
      setAuxilioPorDias(valor);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setGuardandoAuxilio(false);
    }
  }

  async function marcarPagarDia31(valor: boolean) {
    setError("");
    setGuardandoDia31(true);
    try {
      await api.ajustesQuincena.marcar(empleado.id, periodo.id, { pagar_dia_31: valor });
      setPagarDia31(valor);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setGuardandoDia31(false);
    }
  }

  function editar(dia: string, idx: number, campo: "inicio" | "fin", valor: string) {
    setPares((prev) => {
      const copia = prev[dia].map((p, i) =>
        // Editar las horas a mano rompe el vínculo con el umbral.
        i === idx ? { ...p, [campo]: valor, relleno: false } : p,
      );
      return { ...prev, [dia]: copia };
    });
  }

  function agregarPar(dia: string) {
    setPares((prev) => ({ ...prev, [dia]: [...prev[dia], PAR_VACIO] }));
  }

  function quitarPar(dia: string, idx: number) {
    setPares((prev) => {
      const restantes = prev[dia].filter((_, i) => i !== idx);
      // Siempre queda al menos una fila editable (vacía = descanso).
      return { ...prev, [dia]: restantes.length ? restantes : [PAR_VACIO] };
    });
  }

  /** Turnos ya guardados, por clave `fecha|inicio|fin`: dice si una fila de la
   *  tarjeta corresponde a un turno que existe en el servidor. */
  const turnoPorClave = useMemo(() => {
    const mapa = new Map<string, Turno>();
    for (const t of turnos) mapa.set(claveTurno(t), t);
    return mapa;
  }, [turnos]);

  /** El turno guardado que corresponde a una fila, o undefined si es una fila
   *  nueva (o con las horas ya editadas): entonces la marca viaja en el POST. */
  function turnoDeLaFila(dia: string, par: Par): Turno | undefined {
    const inicio = normalizarHora(par.inicio);
    const fin = normalizarHora(par.fin);
    if (!inicio || !fin) return undefined;
    return turnoPorClave.get(clave(dia, inicio, fin));
  }

  function actualizarPar(dia: string, idx: number, cambios: Partial<Par>) {
    setPares((prev) => {
      const copia = prev[dia].map((p, i) => (i === idx ? { ...p, ...cambios } : p));
      return { ...prev, [dia]: copia };
    });
  }

  /** Marca o desmarca la jornada ordinaria de una fila.
   *
   *  En un día sin horas, marcar CREA el turno de relleno (06:00 + el umbral) y
   *  desmarcarlo lo quita: el día vuelve a «Descanso» y el diff de `guardar()`
   *  borra el turno si ya estaba en el servidor. */
  function alternarJornada(dia: string, idx: number, par: Par, marcado: boolean) {
    const horas = String(HORAS_JORNADA_ORDINARIA_SUGERIDA);
    if (!marcado) {
      if (par.relleno) {
        actualizarPar(dia, idx, PAR_VACIO);
        return;
      }
      actualizarPar(dia, idx, { jornadaOrdinaria: null });
      aplicarJornada(dia, idx, par, null);
      return;
    }
    if (normalizarHora(par.inicio) && normalizarHora(par.fin)) {
      actualizarPar(dia, idx, { jornadaOrdinaria: horas });
      aplicarJornada(dia, idx, par, horas);
      return;
    }
    actualizarPar(dia, idx, {
      ...ventanaJornadaOrdinaria(HORAS_JORNADA_ORDINARIA_SUGERIDA * 60),
      jornadaOrdinaria: horas,
      relleno: true,
    });
  }

  /** Confirma el umbral escrito. En un turno de relleno el horario lo dicta el
   *  umbral, así que el turno se redimensiona; en uno normal solo cambia la marca. */
  function confirmarJornada(dia: string, idx: number, par: Par) {
    if (!par.relleno) {
      aplicarJornada(dia, idx, par, par.jornadaOrdinaria);
      return;
    }
    const minutos = par.jornadaOrdinaria === null ? null : horasAMinutos(par.jornadaOrdinaria);
    if (minutos === null) {
      // Entrada inválida: vuelve el largo que el turno tiene ahora.
      const actual = minutosDeTurno({ hora_inicio: par.inicio, hora_fin: par.fin });
      actualizarPar(dia, idx, { jornadaOrdinaria: minutosAHoras(actual) });
      return;
    }
    actualizarPar(dia, idx, ventanaJornadaOrdinaria(minutos));
  }

  /** Aplica la marca al instante (como en la grilla) si la fila ya es un turno
   *  guardado. Si no lo es, se queda en el estado local y se envía al guardar. */
  async function aplicarJornada(dia: string, idx: number, par: Par, valor: string | null) {
    const turno = turnoDeLaFila(dia, par);
    if (!turno) return;
    const minutos = valor === null ? null : horasAMinutos(valor);
    if (valor !== null && minutos === null) {
      // Entrada inválida: se descarta y vuelve el valor guardado, como en la grilla.
      actualizarPar(dia, idx, {
        jornadaOrdinaria:
          turno.minutos_jornada_ordinaria === null
            ? null
            : minutosAHoras(turno.minutos_jornada_ordinaria),
      });
      return;
    }
    if (minutos === turno.minutos_jornada_ordinaria) return;
    setError("");
    try {
      await api.turnos.jornadaOrdinaria(turno.id, minutos);
      alGuardado();
    } catch (err) {
      setError((err as Error).message);
    }
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

  /** El 31 del periodo, si el mes lo tiene: la quincena se paga como 15 días. */
  const dia31 = useMemo(() => dias.find((d) => d.endsWith("-31")), [dias]);

  const totalMinutos = useMemo(
    () => dias.reduce((suma, d) => suma + minutosDia(d), 0),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [pares, dias],
  );


  async function guardar() {
    setError("");
    // Normalizar y validar todos los pares con contenido.
    const editados: {
      fecha: string;
      inicio: string;
      fin: string;
      minutosJornadaOrdinaria: number | null;
    }[] = [];
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
        const minutos = p.jornadaOrdinaria === null ? null : horasAMinutos(p.jornadaOrdinaria);
        if (p.jornadaOrdinaria !== null && minutos === null) {
          setError(`Jornada ordinaria inválida el ${d}: revise "${p.jornadaOrdinaria}".`);
          return;
        }
        editados.push({ fecha: d, inicio, fin, minutosJornadaOrdinaria: minutos });
      }
    }

    // El diff compara por `fecha|inicio|fin` con las horas de los originales ya
    // normalizadas, para no borrar/recrear turnos que no cambiaron.
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
          // La marca sobrevive a un cambio de horas: el turno se recrea con ella.
          minutos_jornada_ordinaria: e.minutosJornadaOrdinaria,
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
            {empleado.incapacitado && (
              <span className="marca-incapacitado" title="Incapacitado">
                {" "}
                ✚
              </span>
            )}
          </div>
          <div>
            <span className="previa-etiqueta">C.C.</span> {empleado.documento}
          </div>
          <div>
            <span className="previa-etiqueta">MES</span> del {periodo.fecha_inicio} al{" "}
            {periodo.fecha_fin}
          </div>
        </div>

        <div className="previa-estados">
          <span className="previa-etiqueta">ESTADO DEL EMPLEADO</span>
          {ESTADOS_EMPLEADO.map(({ campo, etiqueta, titulo }) => (
            <label key={campo} className="casilla" title={titulo}>
              <input
                type="checkbox"
                checked={empleado[campo]}
                disabled={guardandoEstado !== null}
                onChange={(e) => marcarEstado(campo, e.target.checked)}
              />
              {etiqueta}
            </label>
          ))}
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
                <th title={TITULO_JORNADA_ORDINARIA}>Jornada ord.</th>
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
                              {filaPares.length > 1 && (
                                <button
                                  type="button"
                                  title="Quitar turno"
                                  className="quitar-par"
                                  onClick={() => quitarPar(d, i)}
                                >
                                  ×
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      ))}
                    </td>
                    <td className="celda-jornada" title={TITULO_JORNADA_ORDINARIA}>
                      {filaPares.map((p, i) => {
                        const marcado = p.jornadaOrdinaria !== null;
                        if (soloLectura) {
                          return (
                            <div key={i} className="linea-hora">
                              {marcado ? (
                                <span>{p.jornadaOrdinaria} h</span>
                              ) : (
                                <span className="atenuado">—</span>
                              )}
                            </div>
                          );
                        }
                        // La casilla se dibuja siempre: en un día sin horas,
                        // marcarla crea el turno de relleno con su horario.
                        return (
                          <div key={i} className="linea-hora">
                            <input
                              type="checkbox"
                              checked={marcado}
                              aria-label="Jornada ordinaria"
                              onChange={(e) => alternarJornada(d, i, p, e.target.checked)}
                            />
                            {marcado && (
                              <input
                                className="horas-jornada"
                                value={p.jornadaOrdinaria ?? ""}
                                inputMode="decimal"
                                aria-label="Horas de jornada ordinaria"
                                onChange={(e) =>
                                  actualizarPar(d, i, { jornadaOrdinaria: e.target.value })
                                }
                                onBlur={() => confirmarJornada(d, i, p)}
                                onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
                              />
                            )}
                          </div>
                        );
                      })}
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
                <td colSpan={5} style={{ textAlign: "right", fontWeight: 600 }}>
                  Total quincena
                </td>
                <td className="total">{(totalMinutos / 60).toFixed(1)}</td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>

        <div className="fila" style={{ flexDirection: "column", alignItems: "flex-start", gap: 6 }}>
          <label className="casilla">
            <input
              type="checkbox"
              checked={quincenaIncompleta}
              disabled={soloLectura || guardandoIncompleta}
              onChange={(e) => marcarQuincenaIncompleta(e.target.checked)}
            />
            No laboró todas las horas de la quincena: pagar el tiempo ordinario sobre las horas trabajadas (festivas y nocturnas incluidas) en vez del presupuesto completo
          </label>
          <label className="casilla">
            <input
              type="checkbox"
              checked={sinExtras}
              disabled={soloLectura || guardandoSinExtras}
              onChange={(e) => marcarSinExtras(e.target.checked)}
            />
            No calcular horas extra: solo cobrar extra si supera las horas de la quincena
            (concentró horas para descansar otros días)
          </label>
          <label className="casilla" title={TITULO_AUXILIO_POR_DIAS}>
            <input
              type="checkbox"
              checked={auxilioPorDias}
              disabled={soloLectura || guardandoAuxilio}
              onChange={(e) => marcarAuxilioPorDias(e.target.checked)}
            />
            Calcular el auxilio de transporte con lo laborado (
            {(totalMinutos / 60).toFixed(1)} h)
          </label>
          {dia31 !== undefined && (
            <label className="casilla" title={TITULO_PAGAR_DIA_31}>
              <input
                type="checkbox"
                checked={pagarDia31}
                disabled={soloLectura || guardandoDia31}
                onChange={(e) => marcarPagarDia31(e.target.checked)}
              />
              Pagar aparte el día 31 ({(minutosDia(dia31) / 60).toFixed(1)} h registradas):
              la quincena se liquida como 15 días, así que ese día queda fuera del
              presupuesto y sus horas se reconocen a hora base
            </label>
          )}
          {sinExtras && pagarDia31 && dia31 !== undefined && (
            <p className="aviso-advertencia" style={{ margin: 0 }}>
              ⚠ &ldquo;Sin extras&rdquo; usa el presupuesto quincenal (105 h): si ese tope
              se agota antes del 31, las horas de ese día quedan como extras y el concepto
              DIA 31 no aparece en la liquidación. Para verlo, desactiva &ldquo;Sin
              extras&rdquo;.
            </p>
          )}
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
