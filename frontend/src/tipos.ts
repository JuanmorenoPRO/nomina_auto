// Tipos espejo de los schemas del backend.

export type Rol = "operador" | "contadora" | "admin";

export interface Usuario {
  id: string | null;
  email: string;
  rol: Rol;
  activo: boolean;
}

export interface RegistroAuditoria {
  usuario_email: string;
  accion: string;
  entidad: string;
  entidad_id: string;
  antes: Record<string, unknown> | null;
  despues: Record<string, unknown> | null;
  timestamp: string;
}

export interface ConceptoFijo {
  nombre: string;
  valor: number;
  tipo: "devengado" | "deduccion";
  salarial: boolean;
}

export interface ConfigUnidad {
  estrategia_extras: string | null;
  factores_override: Record<string, string>;
  conceptos_fijos: ConceptoFijo[];
}

export interface Unidad {
  id: string;
  nombre: string;
  nit: string;
  activa: boolean;
  descuenta_seguridad_social: boolean;
  config: ConfigUnidad;
}

export interface ConceptoManual {
  id: string;
  empleado_id: string;
  periodo_id: string;
  tipo: "devengado" | "deduccion";
  nombre: string;
  valor: number;
  salarial: boolean;
}

export interface Empleado {
  id: string;
  unidad_id: string;
  nombre: string;
  tipo_documento: string;
  documento: string;
  cargo: string;
  salario_base: number;
  activo: boolean;
}

export interface Periodo {
  id: string;
  fecha_inicio: string;
  fecha_fin: string;
  estado: "abierto" | "liquidado" | "cerrado";
}

export interface Turno {
  id: string;
  empleado_id: string;
  fecha: string;
  hora_inicio: string;
  hora_fin: string;
  cruza_medianoche: boolean;
}

export interface Parametro {
  codigo: string;
  valor: string;
  vigente_desde: string;
  vigente_hasta: string | null;
  norma: string;
}

export interface Festivo {
  fecha: string;
  nombre: string;
  origen: "ley" | "manual";
}

export interface Concepto {
  codigo: string;
  nombre: string;
  minutos: number;
  horas: string;
  factor: string | null;
  componentes: Record<string, string>;
  valor: number;
}

export interface LiquidacionEmpleado {
  empleado_id: string;
  nombre: string;
  documento: string;
  salario_mensual: number;
  tarifa_hora: string;
  conceptos: Concepto[];
  deducciones: Concepto[];
  total_devengado: number;
  total_deducciones: number;
  neto_a_pagar: number;
  total: number;
}

export interface Liquidacion {
  id: string;
  periodo: Periodo;
  unidad: Unidad;
  version: number;
  creada_en: string;
  empleados: LiquidacionEmpleado[];
  total: number;
}
