import type {
  ConceptoManual,
  ConfigUnidad,
  Empleado,
  Festivo,
  Liquidacion,
  Parametro,
  Periodo,
  RegistroAuditoria,
  Rol,
  Turno,
  Unidad,
  Usuario,
} from "./tipos";

const BASE = "/api";

/** Se dispara cuando el backend responde 401 (sesión vencida o inexistente). */
export const EVENTO_NO_AUTENTICADO = "nomina:no-autenticado";

async function pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
  const respuesta = await fetch(BASE + ruta, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (respuesta.status === 401 && !ruta.startsWith("/auth/")) {
    window.dispatchEvent(new Event(EVENTO_NO_AUTENTICADO));
  }
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
  auth: {
    login: (email: string, contrasena: string) =>
      pedir<Usuario>("/auth/login", { method: "POST", body: json({ email, contrasena }) }),
    logout: () => pedir<void>("/auth/logout", { method: "POST" }),
    yo: () => pedir<Usuario>("/auth/yo"),
  },
  usuarios: {
    listar: () => pedir<Usuario[]>("/usuarios"),
    crear: (datos: { email: string; contrasena: string; rol: Rol }) =>
      pedir<Usuario>("/usuarios", { method: "POST", body: json(datos) }),
    desactivar: (id: string) =>
      pedir<Usuario>(`/usuarios/${id}/desactivar`, { method: "POST" }),
  },
  auditoria: {
    listar: (limite = 100) => pedir<RegistroAuditoria[]>(`/auditoria?limite=${limite}`),
  },
  unidades: {
    listar: () => pedir<Unidad[]>("/unidades"),
    crear: (datos: {
      nombre: string;
      nit: string;
      descuenta_seguridad_social?: boolean;
      config?: ConfigUnidad;
    }) => pedir<Unidad>("/unidades", { method: "POST", body: json(datos) }),
    actualizar: (
      id: string,
      datos: Partial<{
        nombre: string;
        nit: string;
        activa: boolean;
        descuenta_seguridad_social: boolean;
        config: ConfigUnidad;
      }>,
    ) => pedir<Unidad>(`/unidades/${id}`, { method: "PATCH", body: json(datos) }),
  },
  conceptosManuales: {
    listar: (empleadoId?: string, periodoId?: string) => {
      const q = new URLSearchParams();
      if (empleadoId) q.set("empleado_id", empleadoId);
      if (periodoId) q.set("periodo_id", periodoId);
      const qs = q.toString();
      return pedir<ConceptoManual[]>(`/conceptos-manuales${qs ? `?${qs}` : ""}`);
    },
    crear: (datos: {
      empleado_id: string;
      periodo_id: string;
      tipo: "devengado" | "deduccion";
      nombre: string;
      valor: number;
      salarial: boolean;
    }) => pedir<ConceptoManual>("/conceptos-manuales", { method: "POST", body: json(datos) }),
    eliminar: (id: string) =>
      pedir<void>(`/conceptos-manuales/${id}`, { method: "DELETE" }),
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
    cerrar: (id: string) => pedir<Periodo>(`/periodos/${id}/cerrar`, { method: "POST" }),
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
