import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Festivo, Parametro, RegistroAuditoria, Rol, Usuario } from "../tipos";

const NOMBRES_PARAMETROS: Record<string, string> = {
  jornada_nocturna_inicio: "Inicio de jornada nocturna",
  jornada_nocturna_fin: "Fin de jornada nocturna",
  recargo_nocturno: "% recargo nocturno",
  extra_diurna: "% hora extra diurna",
  extra_nocturna: "% hora extra nocturna",
  recargo_dominical_festivo: "% recargo dominical/festivo",
  jornada_maxima_semanal: "Jornada máxima semanal (horas)",
  horas_quincena: "Horas de la quincena",
  divisor_hora_ordinaria: "Divisor de hora ordinaria (horas/mes)",
  tope_horas_extra_dia: "Tope de horas extra por día",
  auxilio_transporte_mensual: "Auxilio de transporte mensual",
  estrategia_clasificacion_extras: "Estrategia de clasificación de extras",
  horas_jornada_diaria: "Jornada diaria (umbral estrategia 'diaria')",
  aporte_salud_empleado: "% aporte salud del empleado",
  aporte_pension_empleado: "% aporte pensión del empleado",
};

export function Configuracion() {
  return (
    <>
      <SeccionParametros />
      <SeccionFestivos />
      <SeccionUsuarios />
      <SeccionAuditoria />
    </>
  );
}

function SeccionUsuarios() {
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ email: "", contrasena: "", rol: "operador" as Rol });

  const recargar = useCallback(
    () => api.usuarios.listar().then(setUsuarios).catch((e) => setError(e.message)),
    [],
  );
  useEffect(() => {
    recargar();
  }, [recargar]);

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.usuarios.crear(form);
      setForm({ email: "", contrasena: "", rol: "operador" });
      await recargar();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function desactivar(id: string | null) {
    if (!id || !window.confirm("¿Desactivar este usuario? Sus sesiones se cierran.")) return;
    setError("");
    try {
      await api.usuarios.desactivar(id);
      await recargar();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <>
      <h2>Usuarios</h2>
      <p className="pista">
        Roles: <b>operador</b> solo ingresa turnos · <b>contadora</b> además liquida y
        exporta · <b>admin</b> además administra parámetros y usuarios.
      </p>
      <form className="fila tarjeta" onSubmit={crear}>
        <label className="campo">
          Correo
          <input
            required
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </label>
        <label className="campo">
          Contraseña (mínimo 10)
          <input
            required
            type="password"
            minLength={10}
            autoComplete="new-password"
            value={form.contrasena}
            onChange={(e) => setForm({ ...form, contrasena: e.target.value })}
          />
        </label>
        <label className="campo">
          Rol
          <select
            value={form.rol}
            onChange={(e) => setForm({ ...form, rol: e.target.value as Rol })}
          >
            <option value="operador">operador</option>
            <option value="contadora">contadora</option>
            <option value="admin">admin</option>
          </select>
        </label>
        <button className="principal" type="submit">Crear usuario</button>
      </form>
      {error && <div className="error">{error}</div>}
      <table className="datos">
        <thead>
          <tr><th>Correo</th><th>Rol</th><th>Estado</th><th></th></tr>
        </thead>
        <tbody>
          {usuarios.map((u) => (
            <tr key={u.email}>
              <td>{u.email}</td>
              <td>{u.rol}</td>
              <td>{u.activo ? "activo" : "inactivo"}</td>
              <td>
                {u.activo && (
                  <button className="secundario" onClick={() => desactivar(u.id)}>
                    Desactivar
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function SeccionAuditoria() {
  const [registros, setRegistros] = useState<RegistroAuditoria[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.auditoria.listar(100).then(setRegistros).catch((e) => setError(e.message));
  }, []);

  return (
    <>
      <h2>Auditoría (últimos 100 registros)</h2>
      <p className="pista">Registro inmutable: la base de datos rechaza modificaciones.</p>
      {error && <div className="error">{error}</div>}
      <table className="datos">
        <thead>
          <tr>
            <th>Fecha</th><th>Usuario</th><th>Acción</th><th>Entidad</th><th>Detalle</th>
          </tr>
        </thead>
        <tbody>
          {registros.map((r, i) => (
            <tr key={i}>
              <td>{new Date(r.timestamp).toLocaleString("es-CO")}</td>
              <td>{r.usuario_email}</td>
              <td>{r.accion}</td>
              <td>{r.entidad}</td>
              <td>
                {r.antes && <>antes: {JSON.stringify(r.antes)} </>}
                {r.despues && <>después: {JSON.stringify(r.despues)}</>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function SeccionParametros() {
  const [parametros, setParametros] = useState<Parametro[]>([]);
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [form, setForm] = useState({ codigo: "", valor: "", vigente_desde: "", norma: "" });

  const recargar = useCallback(
    () => api.parametros.listar().then(setParametros).catch((e) => setError(e.message)),
    [],
  );
  useEffect(() => {
    recargar();
  }, [recargar]);

  const porCodigo = useMemo(() => {
    const grupos = new Map<string, Parametro[]>();
    for (const p of parametros) grupos.set(p.codigo, [...(grupos.get(p.codigo) ?? []), p]);
    for (const grupo of grupos.values())
      grupo.sort((a, b) => b.vigente_desde.localeCompare(a.vigente_desde));
    return [...grupos.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [parametros]);

  async function crearVigencia(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setMensaje("");
    try {
      await api.parametros.crear(form);
      setMensaje(
        `Nueva vigencia de «${NOMBRES_PARAMETROS[form.codigo] ?? form.codigo}» desde ${form.vigente_desde}. La vigencia anterior quedó cerrada; las liquidaciones históricas no cambian.`,
      );
      setForm({ codigo: "", valor: "", vigente_desde: "", norma: "" });
      await recargar();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <>
      <h2>Parámetros legales</h2>
      <p className="pista">
        Cuando la ley cambie, cree una <b>nueva vigencia</b>: nunca se edita el valor
        histórico. El motor usa el valor vigente en la fecha de cada turno.
      </p>

      <form className="fila tarjeta" onSubmit={crearVigencia}>
        <label className="campo">
          Parámetro
          <select
            required
            value={form.codigo}
            onChange={(e) => setForm({ ...form, codigo: e.target.value })}
          >
            <option value="">— seleccione —</option>
            {Object.entries(NOMBRES_PARAMETROS).map(([codigo, nombre]) => (
              <option key={codigo} value={codigo}>{nombre}</option>
            ))}
          </select>
        </label>
        <label className="campo">
          Nuevo valor
          <input
            required
            value={form.valor}
            placeholder="ej. 0.90"
            onChange={(e) => setForm({ ...form, valor: e.target.value })}
          />
        </label>
        <label className="campo">
          Vigente desde
          <input
            required
            type="date"
            value={form.vigente_desde}
            onChange={(e) => setForm({ ...form, vigente_desde: e.target.value })}
          />
        </label>
        <label className="campo">
          Norma (opcional)
          <input
            value={form.norma}
            placeholder="ej. Ley 2466/2025"
            onChange={(e) => setForm({ ...form, norma: e.target.value })}
          />
        </label>
        <button className="principal" type="submit">Crear vigencia</button>
      </form>

      {error && <div className="error">{error}</div>}
      {mensaje && <div className="exito">{mensaje}</div>}

      <table className="datos">
        <thead>
          <tr>
            <th>Parámetro</th>
            <th>Valor</th>
            <th>Vigente desde</th>
            <th>Vigente hasta</th>
            <th>Norma</th>
          </tr>
        </thead>
        <tbody>
          {porCodigo.flatMap(([codigo, grupo]) =>
            grupo.map((p, i) => (
              <tr key={`${codigo}-${p.vigente_desde}`}>
                <td>{i === 0 ? (NOMBRES_PARAMETROS[codigo] ?? codigo) : ""}</td>
                <td>{i === 0 ? <b>{p.valor}</b> : p.valor}</td>
                <td>{p.vigente_desde}</td>
                <td>{p.vigente_hasta ?? "vigente"}</td>
                <td>{p.norma}</td>
              </tr>
            )),
          )}
        </tbody>
      </table>
    </>
  );
}

function SeccionFestivos() {
  const [anio, setAnio] = useState(new Date().getFullYear());
  const [festivos, setFestivos] = useState<Festivo[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ fecha: "", nombre: "", anular: false });

  const recargar = useCallback(
    () => api.festivos.delAnio(anio).then(setFestivos).catch((e) => setError(e.message)),
    [anio],
  );
  useEffect(() => {
    recargar();
  }, [recargar]);

  async function ajustar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.festivos.ajustar({
        fecha: form.fecha,
        nombre: form.nombre,
        es_festivo: !form.anular,
      });
      setForm({ fecha: "", nombre: "", anular: false });
      await recargar();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function quitarAjuste(fecha: string) {
    setError("");
    try {
      await api.festivos.quitarAjuste(fecha);
      await recargar();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <>
      <h2>Festivos</h2>
      <p className="pista">
        Los festivos se calculan por ley (incluye traslados a lunes y festivos de Pascua).
        Si la ley cambia, agregue un festivo manual o anule uno calculado.
      </p>
      <div className="fila">
        <label className="campo">
          Año
          <input
            type="number"
            value={anio}
            onChange={(e) => setAnio(Number(e.target.value))}
            min={2000}
            max={2100}
          />
        </label>
      </div>

      <form className="fila tarjeta" onSubmit={ajustar}>
        <label className="campo">
          Fecha
          <input
            required
            type="date"
            value={form.fecha}
            onChange={(e) => setForm({ ...form, fecha: e.target.value })}
          />
        </label>
        <label className="campo">
          Nombre
          <input
            value={form.nombre}
            placeholder="ej. día cívico"
            onChange={(e) => setForm({ ...form, nombre: e.target.value })}
          />
        </label>
        <label className="campo">
          <span>
            <input
              type="checkbox"
              checked={form.anular}
              onChange={(e) => setForm({ ...form, anular: e.target.checked })}
            />{" "}
            Anular un festivo calculado
          </span>
        </label>
        <button className="principal" type="submit">Guardar ajuste</button>
      </form>

      {error && <div className="error">{error}</div>}

      <table className="datos">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Día</th>
            <th>Origen</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {festivos.map((f) => (
            <tr key={f.fecha}>
              <td>{f.fecha}</td>
              <td>
                {new Date(`${f.fecha}T12:00:00`).toLocaleDateString("es-CO", {
                  weekday: "long",
                })}
              </td>
              <td>{f.origen === "ley" ? "por ley" : `manual ${f.nombre && `— ${f.nombre}`}`}</td>
              <td>
                {f.origen === "manual" && (
                  <button className="secundario" onClick={() => quitarAjuste(f.fecha)}>
                    Quitar ajuste
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
