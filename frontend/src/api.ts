import type {
  Empleado,
  Festivo,
  Liquidacion,
  Parametro,
  Periodo,
  Turno,
  Unidad,
} from "./tipos";

const BASE = "/api";

async function pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
  const respuesta = await fetch(BASE + ruta, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => ({ detail: respuesta.statusText }));
    const detalle =
      typeof cuerpo.detail === "string" ? cuerpo.detail : JSON.stringify(cuerpo.detail);
    throw new Error(detalle);
  }
  if (respuesta.status === 204) return undefined as T;
  return respuesta.json();
}

const json = (datos: unknown) => JSON.stringify(datos);

export const api = {
  unidades: {
    listar: () => pedir<Unidad[]>("/unidades"),
    crear: (datos: { nombre: string; nit: string }) =>
      pedir<Unidad>("/unidades", { method: "POST", body: json(datos) }),
  },
  empleados: {
    listar: (unidadId?: string) =>
      pedir<Empleado[]>(`/empleados${unidadId ? `?unidad_id=${unidadId}` : ""}`),
    crear: (datos: {
      unidad_id: string;
      nombre: string;
      documento: string;
      cargo: string;
      salario_base: number;
    }) => pedir<Empleado>("/empleados", { method: "POST", body: json(datos) }),
  },
  periodos: {
    listar: () => pedir<Periodo[]>("/periodos"),
    crear: (datos: { fecha_inicio: string; fecha_fin: string }) =>
      pedir<Periodo>("/periodos", { method: "POST", body: json(datos) }),
    reabrir: (id: string) => pedir<Periodo>(`/periodos/${id}/reabrir`, { method: "POST" }),
    turnos: (id: string, unidadId?: string) =>
      pedir<Turno[]>(`/periodos/${id}/turnos${unidadId ? `?unidad_id=${unidadId}` : ""}`),
    liquidar: (id: string, unidadId: string) =>
      pedir<Liquidacion>(`/periodos/${id}/liquidar`, {
        method: "POST",
        body: json({ unidad_id: unidadId }),
      }),
  },
  turnos: {
    registrar: (datos: {
      empleado_id: string;
      fecha: string;
      hora_inicio: string;
      hora_fin: string;
    }) => pedir<Turno>("/turnos", { method: "POST", body: json(datos) }),
    eliminar: (id: string) => pedir<void>(`/turnos/${id}`, { method: "DELETE" }),
  },
  parametros: {
    listar: (fecha?: string) =>
      pedir<Parametro[]>(`/parametros${fecha ? `?fecha=${fecha}` : ""}`),
    crear: (datos: { codigo: string; valor: string; vigente_desde: string; norma: string }) =>
      pedir<Parametro>("/parametros", { method: "POST", body: json(datos) }),
  },
  festivos: {
    delAnio: (anio: number) => pedir<Festivo[]>(`/festivos/${anio}`),
    ajustar: (datos: { fecha: string; nombre: string; es_festivo: boolean }) =>
      pedir<Festivo>("/festivos", { method: "PUT", body: json(datos) }),
    quitarAjuste: (fecha: string) => pedir<void>(`/festivos/${fecha}`, { method: "DELETE" }),
  },
  liquidaciones: {
    listar: (periodoId?: string) =>
      pedir<Liquidacion[]>(`/liquidaciones${periodoId ? `?periodo_id=${periodoId}` : ""}`),
    urlExcel: (id: string) => `${BASE}/liquidaciones/${id}/excel`,
  },
};
