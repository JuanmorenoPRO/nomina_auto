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
