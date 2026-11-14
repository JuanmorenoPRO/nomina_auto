import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { ImportarTurnos } from "./ImportarTurnos";
import type { Empleado, NovedadDia, Periodo, TipoNovedadDia, Turno, Unidad } from "../tipos";
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
    titulo:
      "Incapacitado toda la quincena: sin auxilio de transporte. Si solo fueron algunos " +
      "días, márquelos como «Incapacitado» en la columna Descanso.",
  },
  {
    campo: "ocasional",
    etiqueta: "Ocasional",
    titulo: "Ocasional: sin auxilio de transporte, salvo que se pague por días laborados.",
  },
] as const;

type CampoEstado = (typeof ESTADOS_EMPLEADO)[number]["campo"];

const TITULO_AUXILIO_POR_DIAS =
  "El auxilio de transporte se paga por días: auxilio mensual ÷ 30 × días laborados, " +
  "donde los días laborados son los 15 de la quincena menos los marcados como " +
  "«Incapacitado» o «No laboró» en la columna Descanso y los días no remunerados. " +
  "Los descansos sí cuentan. Marcado, se paga aunque el empleado esté incapacitado " +
  "u ocasional. Los días marcados descuentan el auxilio aunque esta casilla esté apagada.";

const TITULO_NOVEDAD =
  "Día sin turno: «Descanso» cuenta para el auxilio de transporte; «Incapacitado» y " +
  "«No laboró» (ingreso o retiro a mitad de quincena, ausencia) no cuentan. " +
  "No cambia el tiempo ordinario.";

const OPCIONES_NOVEDAD: { valor: TipoNovedadDia | ""; etiqueta: string }[] = [
  { valor: "", etiqueta: "Descanso" },
  { valor: "incapacidad", etiqueta: "Incapacitado" },
  { valor: "no_laboro", etiqueta: "No laboró" },
];

/** Días de la quincena que no generan auxilio, con la misma regla del backend
 *  (`_dias_marcados_por_tipo`): el 31 no cuenta, y en un mes de menos de 30 días,
 *  marcado el último día, la marca cubre hasta el 30 comercial. */
function diasMarcadosParaAuxilio(dias: string[], marcados: Set<string>): number {
  let total = 0;
  for (const d of dias) if (marcados.has(d) && !d.endsWith("-31")) total += 1;
  const ultimo = dias[dias.length - 1];
  if (ultimo && Number(ultimo.slice(8)) < 30 && Number(dias[0].slice(8)) > 15 && marcados.has(ultimo)) {
    total += 30 - Number(ultimo.slice(8));
  }
  return total;
}

const TITULO_PAGAR_DIA_31 =
  "La quincena se paga siempre como 15 días, así que en los meses de 31 ese día " +
  "queda fuera del presupuesto. Marcado, sus horas trabajadas (las que no sean " +
  "extra) se reconocen aparte a hora base, en la línea DIA 31. Los recargos y las " +
  "extras del 31 ya se pagan en sus propias líneas.";

const TITULO_NO_DEVENGAR_AUXILIO =
  "Excepción contable puntual: no se paga auxilio de transporte en esta quincena, " +
  "sin importar el estado del empleado (incapacitado/ocasional) ni si el auxilio " +
  "se prorratea por lo laborado.";

const TITULO_NO_DESCONTAR_SEGURIDAD_SOCIAL =
  "Excepción contable puntual: no se descuentan salud ni pensión en esta " +
  "quincena, aunque la unidad tenga activado el descuento de seguridad social.";

const TITULO_DIAS_NO_REMUNERADOS =
  "Permiso o licencia sin sueldo: cada día descuenta una jornada (7 h) del tiempo " +
  "ordinario y 1/30 del auxilio de transporte mensual (manda sobre el auxilio " +
  "prorrateado). Los descansos, las extras y los recargos no cambian. La quincena se paga siempre como 15 días, así que el " +
  "día 31 normalmente no se cuenta.";

const TITULO_QUINCENA_INCOMPLETA =
  "No laboró todas las horas de la quincena (incapacidad, ingreso o retiro a mitad de " +
  "periodo): el tiempo ordinario se paga sobre las horas trabajadas que no son extra " +
  "(festivas y nocturnas incluidas) en vez del presupuesto completo. Para un permiso " +
  "de pocos días use «Días no remunerados».";

const TITULO_SIN_EXTRAS =
  "No calcular horas extra por turno: solo se cobra extra si se supera el total de " +
  "horas de la quincena (el empleado concentró horas para descansar otros días). " +
  "Los recargos nocturnos y dominicales se mantienen.";

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
  novedades,
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
  /** Novedades (incapacitado / no laboró) de los días sin turno del empleado. */
  novedades: NovedadDia[];
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
  const [noDevengarAuxilio, setNoDevengarAuxilio] = useState(false);
  const [guardandoNoAuxilio, setGuardandoNoAuxilio] = useState(false);
  const [noDescontarSeguridadSocial, setNoDescontarSeguridadSocial] = useState(false);
  const [guardandoNoSeguridadSocial, setGuardandoNoSeguridadSocial] = useState(false);
  // Texto del input: se guarda al salir del campo, no en cada tecla.
  const [diasNoRemunerados, setDiasNoRemunerados] = useState("0");
  const [diasNoRemuneradosGuardados, setDiasNoRemuneradosGuardados] = useState(0);
  const [guardandoDiasNoRemunerados, setGuardandoDiasNoRemunerados] = useState(false);
  const [guardandoEstado, setGuardandoEstado] = useState<CampoEstado | null>(null);
  const [importando, setImportando] = useState(false);
  // Se guardan al cambiar el selector, como las casillas del panel.
  const [novedadPorDia, setNovedadPorDia] = useState<Record<string, TipoNovedadDia>>(() =>
    Object.fromEntries(novedades.map((n) => [n.fecha, n.tipo])),
  );
  const [guardandoNovedad, setGuardandoNovedad] = useState<string | null>(null);

  useEffect(() => {
    api.ajustesQuincena
      .obtener(empleado.id, periodo.id)
      .then((a) => {
        setQuincenaIncompleta(a.quincena_incompleta);
        setSinExtras(a.sin_extras);
        setAuxilioPorDias(a.auxilio_por_dias_laborados);
        setPagarDia31(a.pagar_dia_31);
        setNoDevengarAuxilio(a.no_devengar_auxilio);
        setNoDescontarSeguridadSocial(a.no_descontar_seguridad_social);
        setDiasNoRemunerados(String(a.dias_no_remunerados));
        setDiasNoRemuneradosGuardados(a.dias_no_remunerados);
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

  /** Descanso (null) / Incapacitado / No laboró de un día sin turno. */
  async function marcarNovedad(dia: string, tipo: TipoNovedadDia | null) {
    setError("");
    setGuardandoNovedad(dia);
    try {
      await api.novedadesDia.marcar(empleado.id, dia, tipo);
      setNovedadPorDia((prev) => {
        const copia = { ...prev };
        if (tipo === null) delete copia[dia];
        else copia[dia] = tipo;
        return copia;
      });
      alGuardado();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setGuardandoNovedad(null);
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

  async function marcarNoDevengarAuxilio(valor: boolean) {
    setError("");
    setGuardandoNoAuxilio(true);
    try {
      await api.ajustesQuincena.marcar(empleado.id, periodo.id, { no_devengar_auxilio: valor });
      setNoDevengarAuxilio(valor);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setGuardandoNoAuxilio(false);
    }
  }

  async function marcarNoDescontarSeguridadSocial(valor: boolean) {
    setError("");
    setGuardandoNoSeguridadSocial(true);
    try {
      await api.ajustesQuincena.marcar(empleado.id, periodo.id, {
        no_descontar_seguridad_social: valor,
      });
      setNoDescontarSeguridadSocial(valor);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setGuardandoNoSeguridadSocial(false);
    }
  }

  async function guardarDiasNoRemunerados() {
    const valor = Number(diasNoRemunerados);
    if (!Number.isInteger(valor) || valor < 0 || valor > 15) {
      setError("Los días no remunerados deben ser un número entero entre 0 y 15");
      setDiasNoRemunerados(String(diasNoRemuneradosGuardados));
      return;
    }
    if (valor === diasNoRemuneradosGuardados) return;
    setError("");
    setGuardandoDiasNoRemunerados(true);
    try {
      await api.ajustesQuincena.marcar(empleado.id, periodo.id, { dias_no_remunerados: valor });
      setDiasNoRemuneradosGuardados(valor);
    } catch (err) {
      setError((err as Error).message);
      setDiasNoRemunerados(String(diasNoRemuneradosGuardados));
    } finally {
      setGuardandoDiasNoRemunerados(false);
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


  /** Días que no generan auxilio: los marcados que siguen sin horas en la tarjeta. */
  const diasMarcados = useMemo(() => {
    const marcados = new Set(
      Object.keys(novedadPorDia).filter((d) =>
        (pares[d] ?? []).every((p) => !p.inicio.trim() && !p.fin.trim()),
      ),
    );
    return diasMarcadosParaAuxilio(dias, marcados);
  }, [novedadPorDia, pares, dias]);
  const diasAuxilio = Math.max(0, 15 - diasMarcados - diasNoRemuneradosGuardados);
  const sinAuxilioPorEstado = !auxilioPorDias && (empleado.incapacitado || empleado.ocasional);

  /** Tras importar, el borrador local de esta tarjeta quedó viejo: si no se
   *  vuelve a leer del servidor, «Guardar cambios» desharía la importación. */
  async function releerTrasImportar() {
    const todos = await api.periodos.turnos(periodo.id, unidad.id);
    setPares(paresIniciales(dias, todos.filter((t) => t.empleado_id === empleado.id)));
    alGuardado();
  }

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

    // Un día con turno no puede seguir marcado como incapacitado / no laboró: el
    // backend no deja registrar la marca en un día trabajado, así que se quita.
    const marcasAQuitar = [...new Set(editados.map((e) => e.fecha))].filter(
      (d) => novedadPorDia[d] !== undefined,
    );

    setGuardando(true);
    try {
      for (const d of marcasAQuitar) await api.novedadesDia.marcar(empleado.id, d, null);
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
          <div className="previa-acciones">
            <a
              className="secundario"
              href={api.turnos.urlPlantilla(periodo.id, unidad.id, empleado.id)}
              title="Descarga esta tarjeta en Excel, con los turnos que ya están registrados"
            >
              Descargar hoja
            </a>
            {!soloLectura && (
              <button type="button" className="secundario" onClick={() => setImportando(true)}>
                Importar hoja
              </button>
            )}
          </div>
        </div>

        {error && <div className="error">{error}</div>}
        {soloLectura && (
          <div className="pista">
            El periodo está {periodo.estado}: para corregir turnos, reábralo en «Unidades y
            empleados».
          </div>
        )}

        <div className="previa-cuerpo">
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
                  const novedad = descanso ? novedadPorDia[d] : undefined;
                  const claseFila = novedad
                    ? `novedad-${novedad}`
                    : esFestivo || esDomingo
                      ? "dia-descanso"
                      : "";
                  return (
                    <tr key={d} className={claseFila}>
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
                        {descanso &&
                          (soloLectura ? (
                            <span className={novedad ? "" : "atenuado"}>
                              {OPCIONES_NOVEDAD.find((o) => o.valor === (novedad ?? ""))?.etiqueta}
                            </span>
                          ) : (
                            <select
                              className="selector-novedad"
                              title={TITULO_NOVEDAD}
                              aria-label={`Novedad del ${d}`}
                              value={novedad ?? ""}
                              disabled={guardandoNovedad !== null}
                              onChange={(e) =>
                                marcarNovedad(d, (e.target.value || null) as TipoNovedadDia | null)
                              }
                            >
                              {OPCIONES_NOVEDAD.map((o) => (
                                <option key={o.valor} value={o.valor}>
                                  {o.etiqueta}
                                </option>
                              ))}
                            </select>
                          ))}
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

          <aside className="previa-ajustes" aria-label="Ajustes de la quincena">
            <fieldset className="grupo-ajustes">
              <legend>Tiempo ordinario</legend>
              <label className="casilla" title={TITULO_QUINCENA_INCOMPLETA}>
                <input
                  type="checkbox"
                  checked={quincenaIncompleta}
                  disabled={soloLectura || guardandoIncompleta}
                  onChange={(e) => marcarQuincenaIncompleta(e.target.checked)}
                />
                Quincena incompleta (pagar solo lo trabajado)
              </label>
              <label className="casilla" title={TITULO_DIAS_NO_REMUNERADOS}>
                Días no remunerados
                <input
                  type="number"
                  min={0}
                  max={15}
                  step={1}
                  style={{ width: "4em" }}
                  value={diasNoRemunerados}
                  disabled={soloLectura || guardandoDiasNoRemunerados}
                  onChange={(e) => setDiasNoRemunerados(e.target.value)}
                  onBlur={guardarDiasNoRemunerados}
                />
              </label>
              {quincenaIncompleta && diasNoRemuneradosGuardados > 0 && (
                <p className="aviso-advertencia">
                  ⚠ Están marcadas las dos: &ldquo;Quincena incompleta&rdquo; ya paga solo
                  lo trabajado. Para un permiso de pocos días basta con los días no
                  remunerados; desmarque la otra.
                </p>
              )}
            </fieldset>

            <fieldset className="grupo-ajustes">
              <legend>Horas extra</legend>
              <label className="casilla" title={TITULO_SIN_EXTRAS}>
                <input
                  type="checkbox"
                  checked={sinExtras}
                  disabled={soloLectura || guardandoSinExtras}
                  onChange={(e) => marcarSinExtras(e.target.checked)}
                />
                Sin extras (solo sobre el tope de la quincena)
              </label>
              {dia31 !== undefined && (
                <label className="casilla" title={TITULO_PAGAR_DIA_31}>
                  <input
                    type="checkbox"
                    checked={pagarDia31}
                    disabled={soloLectura || guardandoDia31}
                    onChange={(e) => marcarPagarDia31(e.target.checked)}
                  />
                  Pagar aparte el día 31 ({(minutosDia(dia31) / 60).toFixed(1)} h)
                </label>
              )}
              {sinExtras && pagarDia31 && dia31 !== undefined && (
                <p className="aviso-advertencia">
                  ⚠ &ldquo;Sin extras&rdquo; usa el presupuesto quincenal (105 h): si ese
                  tope se agota antes del 31, las horas de ese día quedan como extras y el
                  concepto DIA 31 no aparece en la liquidación. Para verlo, desactiva
                  &ldquo;Sin extras&rdquo;.
                </p>
              )}
            </fieldset>

            <fieldset className="grupo-ajustes">
              <legend>Auxilio de transporte</legend>
              <label className="casilla" title={TITULO_AUXILIO_POR_DIAS}>
                <input
                  type="checkbox"
                  checked={auxilioPorDias}
                  disabled={soloLectura || guardandoAuxilio}
                  onChange={(e) => marcarAuxilioPorDias(e.target.checked)}
                />
                Por días laborados
              </label>
              <label className="casilla" title={TITULO_NO_DEVENGAR_AUXILIO}>
                <input
                  type="checkbox"
                  checked={noDevengarAuxilio}
                  disabled={soloLectura || guardandoNoAuxilio}
                  onChange={(e) => marcarNoDevengarAuxilio(e.target.checked)}
                />
                No devengar esta quincena
              </label>
              {!noDevengarAuxilio && !sinAuxilioPorEstado && (
                <p className="dias-auxilio">
                  Días de auxilio: <b>{diasAuxilio}</b> de 15
                  {diasMarcados + diasNoRemuneradosGuardados > 0 && " (descontados incapacitados, no laborados y no remunerados)"}
                </p>
              )}
              {sinAuxilioPorEstado && !noDevengarAuxilio && (
                <p className="aviso-advertencia">
                  ⚠ El empleado está {empleado.incapacitado ? "incapacitado" : "ocasional"}:
                  no se paga auxilio. Marque &ldquo;Por días laborados&rdquo; para pagar los
                  días que sí trabajó.
                </p>
              )}
              {auxilioPorDias && noDevengarAuxilio && (
                <p className="aviso-advertencia">
                  ⚠ &ldquo;No devengar&rdquo; gana sobre el prorrateo: no se paga auxilio.
                </p>
              )}
            </fieldset>

            <fieldset className="grupo-ajustes">
              <legend>Seguridad social</legend>
              <label className="casilla" title={TITULO_NO_DESCONTAR_SEGURIDAD_SOCIAL}>
                <input
                  type="checkbox"
                  checked={noDescontarSeguridadSocial}
                  disabled={soloLectura || guardandoNoSeguridadSocial}
                  onChange={(e) => marcarNoDescontarSeguridadSocial(e.target.checked)}
                />
                No descontar salud y pensión
              </label>
            </fieldset>
            <p className="pista-ajustes">Pase el mouse sobre cada opción para ver el detalle.</p>
          </aside>
        </div>

        {importando && (
          <ImportarTurnos
            unidad={unidad}
            periodo={periodo}
            empleado={empleado}
            alCerrar={() => setImportando(false)}
            alImportado={releerTrasImportar}
          />
        )}

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
