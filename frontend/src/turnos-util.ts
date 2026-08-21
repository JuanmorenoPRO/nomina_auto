// Helpers de fecha/hora/duración compartidos por la grilla de turnos y la
// tarjeta de previsualización por empleado.
import type { Periodo, Turno } from "./tipos";

export const DIAS_SEMANA = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];

export function fechaLocal(iso: string): Date {
  const [a, m, d] = iso.split("-").map(Number);
  return new Date(a, m - 1, d);
}

export function diasDelPeriodo(periodo: Periodo): string[] {
  const dias: string[] = [];
  const fin = fechaLocal(periodo.fecha_fin);
  for (let f = fechaLocal(periodo.fecha_inicio); f <= fin; f.setDate(f.getDate() + 1)) {
    const mes = String(f.getMonth() + 1).padStart(2, "0");
    const dia = String(f.getDate()).padStart(2, "0");
    dias.push(`${f.getFullYear()}-${mes}-${dia}`);
  }
  return dias;
}

/** Acepta "18", "18:30", "6", "06:00:00" y devuelve "HH:MM"; null si no es una hora.
 *  Los segundos (si vienen, p. ej. del backend como "HH:MM:SS") se ignoran. */
export function normalizarHora(texto: string): string | null {
  const limpio = texto.trim();
  const m = /^(\d{1,2})(?::(\d{2}))?(?::\d{2})?$/.exec(limpio);
  if (!m) return null;
  const horas = Number(m[1]);
  const minutos = Number(m[2] ?? "0");
  if (horas > 23 || minutos > 59) return null;
  return `${String(horas).padStart(2, "0")}:${String(minutos).padStart(2, "0")}`;
}

/** Duración en minutos; si fin <= inicio el turno cruza medianoche (+24h). */
export function minutosDeTurno(t: Pick<Turno, "hora_inicio" | "hora_fin">): number {
  const [hi, mi] = t.hora_inicio.split(":").map(Number);
  const [hf, mf] = t.hora_fin.split(":").map(Number);
  const inicio = hi * 60 + mi;
  const fin = hf * 60 + mf;
  return fin <= inicio ? fin + 24 * 60 - inicio : fin - inicio;
}

/** Horas sugeridas al marcar «jornada ordinaria»: es solo el valor inicial del
 *  campo — el umbral real se guarda en cada turno. */
export const HORAS_JORNADA_ORDINARIA_SUGERIDA = 7;

/** "7", "7,5" o "7.5" → minutos enteros; null si no es un número positivo. */
export function horasAMinutos(texto: string): number | null {
  const horas = Number(texto.trim().replace(",", "."));
  if (!Number.isFinite(horas) || horas <= 0 || horas > 24) return null;
  return Math.round(horas * 60);
}

/** Minutos → horas para mostrar en el campo ("420" → "7", "450" → "7.5"). */
export function minutosAHoras(minutos: number): string {
  return String(Number((minutos / 60).toFixed(2)));
}

/** Hora de inicio convencional de un turno de relleno. Se elige las 06:00 porque
 *  los turnos nocturnos terminan a esa hora: así nunca solapa con el del día
 *  anterior (la validación rechaza `inicio < fin_anterior`, no `inicio == fin`). */
export const HORA_INICIO_JORNADA_ORDINARIA = "06:00";

/** Horario de un turno de relleno de `minutos`: 06:00 y la hora de salida que le
 *  corresponde. */
export function ventanaJornadaOrdinaria(minutos: number): { inicio: string; fin: string } {
  const [h, m] = HORA_INICIO_JORNADA_ORDINARIA.split(":").map(Number);
  const fin = (h * 60 + m + minutos) % (24 * 60);
  const hh = String(Math.floor(fin / 60)).padStart(2, "0");
  const mm = String(fin % 60).padStart(2, "0");
  return { inicio: HORA_INICIO_JORNADA_ORDINARIA, fin: `${hh}:${mm}` };
}

/** ¿El turno es «de relleno», es decir, se registró solo para cuadrar las horas
 *  de la quincena? Se reconoce por su forma, sin guardar ninguna bandera: empieza
 *  a la hora convencional y TODO él es jornada ordinaria. Cambiarle el umbral lo
 *  redimensiona; un turno real como 06:00–16:00 marcado con 7 h no lo es (7 ≠ 10),
 *  así que a ese nunca se le mueve la hora de salida. */
export function esTurnoDeRelleno(
  inicio: string,
  fin: string,
  minutosJornada: number | null,
): boolean {
  if (minutosJornada === null) return false;
  const i = normalizarHora(inicio);
  const f = normalizarHora(fin);
  if (!i || !f || i !== HORA_INICIO_JORNADA_ORDINARIA) return false;
  return minutosDeTurno({ hora_inicio: i, hora_fin: f }) === minutosJornada;
}
