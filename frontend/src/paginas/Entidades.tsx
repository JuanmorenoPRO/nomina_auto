import { useEffect, useState } from "react";
import { api } from "../api";
import type { Empleado, Periodo, Unidad } from "../tipos";

const pesos = new Intl.NumberFormat("es-CO");

export function Entidades({
  unidades,
  periodos,
  alCambiar,
}: {
  unidades: Unidad[];
  periodos: Periodo[];
  alCambiar: () => Promise<void>;
}) {
  const [error, setError] = useState("");
  return (
    <>
      {error && <div className="error">{error}</div>}
      <SeccionUnidades unidades={unidades} alCambiar={alCambiar} setError={setError} />
      <SeccionEmpleados unidades={unidades} setError={setError} />
      <SeccionPeriodos periodos={periodos} alCambiar={alCambiar} setError={setError} />
    </>
  );
}

type Props = { alCambiar: () => Promise<void>; setError: (m: string) => void };

function SeccionUnidades({ unidades, alCambiar, setError }: Props & { unidades: Unidad[] }) {
  const [form, setForm] = useState({ nombre: "", nit: "" });

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.unidades.crear(form);
      setForm({ nombre: "", nit: "" });
      await alCambiar();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="tarjeta">
      <h2>Unidades residenciales</h2>
      <form className="fila" onSubmit={crear}>
        <label className="campo">
          Nombre
          <input
            required
            value={form.nombre}
            placeholder="ej. Edificio Thunapa P.H."
            onChange={(e) => setForm({ ...form, nombre: e.target.value })}
          />
        </label>
        <label className="campo">
          NIT
          <input value={form.nit} onChange={(e) => setForm({ ...form, nit: e.target.value })} />
        </label>
        <button className="principal" type="submit">Crear unidad</button>
      </form>
      <table className="datos">
        <thead>
          <tr><th>Nombre</th><th>NIT</th></tr>
        </thead>
        <tbody>
          {unidades.map((u) => (
            <tr key={u.id}><td>{u.nombre}</td><td>{u.nit}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SeccionEmpleados({
  unidades,
  setError,
}: {
  unidades: Unidad[];
  setError: (m: string) => void;
}) {
  const [unidadId, setUnidadId] = useState("");
  const [empleados, setEmpleados] = useState<Empleado[]>([]);
  const [form, setForm] = useState({ nombre: "", documento: "", cargo: "", salario: "" });

  async function recargar(unidad: string) {
    if (!unidad) return setEmpleados([]);
    setEmpleados(await api.empleados.listar(unidad));
  }

  useEffect(() => {
    recargar(unidadId).catch((e) => setError(e.message));
  }, [unidadId, setError]);

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.empleados.crear({
        unidad_id: unidadId,
        nombre: form.nombre,
        documento: form.documento,
        cargo: form.cargo,
        salario_base: Number(form.salario),
      });
      setForm({ nombre: "", documento: "", cargo: "", salario: "" });
      await recargar(unidadId);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="tarjeta">
      <h2>Empleados</h2>
      <div className="fila">
        <label className="campo">
          Unidad
          <select value={unidadId} onChange={(e) => setUnidadId(e.target.value)}>
            <option value="">— seleccione —</option>
            {unidades.map((u) => (
              <option key={u.id} value={u.id}>{u.nombre}</option>
            ))}
          </select>
        </label>
      </div>
      {unidadId && (
        <>
          <form className="fila" onSubmit={crear}>
            <label className="campo">
              Nombre
              <input
                required
                value={form.nombre}
                onChange={(e) => setForm({ ...form, nombre: e.target.value })}
              />
            </label>
            <label className="campo">
              Documento (CC)
              <input
                required
                value={form.documento}
                onChange={(e) => setForm({ ...form, documento: e.target.value })}
              />
            </label>
            <label className="campo">
              Cargo
              <input
                required
                value={form.cargo}
                placeholder="vigilante / aseo / todero"
                onChange={(e) => setForm({ ...form, cargo: e.target.value })}
              />
            </label>
            <label className="campo">
              Salario básico mensual
              <input
                required
                type="number"
                min={1}
                value={form.salario}
                onChange={(e) => setForm({ ...form, salario: e.target.value })}
              />
            </label>
            <button className="principal" type="submit">Crear empleado</button>
          </form>
          <table className="datos">
            <thead>
              <tr>
                <th>Nombre</th><th>Documento</th><th>Cargo</th>
                <th className="numero">Salario</th>
              </tr>
            </thead>
            <tbody>
              {empleados.map((emp) => (
                <tr key={emp.id}>
                  <td>{emp.nombre}</td>
                  <td>{emp.documento}</td>
                  <td>{emp.cargo}</td>
                  <td className="numero">$ {pesos.format(emp.salario_base)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

function SeccionPeriodos({ periodos, alCambiar, setError }: Props & { periodos: Periodo[] }) {
  const [form, setForm] = useState({ fecha_inicio: "", fecha_fin: "" });

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.periodos.crear(form);
      setForm({ fecha_inicio: "", fecha_fin: "" });
      await alCambiar();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function reabrir(id: string) {
    setError("");
    try {
      await api.periodos.reabrir(id);
      await alCambiar();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function cerrar(id: string) {
    const seguro = window.confirm(
      "¿Cerrar definitivamente esta quincena? Quedará en SOLO LECTURA para siempre: " +
        "no podrá reabrirse, ni modificar turnos, ni reliquidar.",
    );
    if (!seguro) return;
    setError("");
    try {
      await api.periodos.cerrar(id);
      await alCambiar();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="tarjeta">
      <h2>Periodos de liquidación (quincenas)</h2>
      <form className="fila" onSubmit={crear}>
        <label className="campo">
          Desde
          <input
            required
            type="date"
            value={form.fecha_inicio}
            onChange={(e) => setForm({ ...form, fecha_inicio: e.target.value })}
          />
        </label>
        <label className="campo">
          Hasta
          <input
            required
            type="date"
            value={form.fecha_fin}
            onChange={(e) => setForm({ ...form, fecha_fin: e.target.value })}
          />
        </label>
        <button className="principal" type="submit">Crear periodo</button>
      </form>
      <table className="datos">
        <thead>
          <tr><th>Desde</th><th>Hasta</th><th>Estado</th><th></th></tr>
        </thead>
        <tbody>
          {periodos.map((p) => (
            <tr key={p.id}>
              <td>{p.fecha_inicio}</td>
              <td>{p.fecha_fin}</td>
              <td><span className={`insignia ${p.estado}`}>{p.estado}</span></td>
              <td>
                {p.estado === "liquidado" && (
                  <>
                    <button className="secundario" onClick={() => reabrir(p.id)}>
                      Reabrir para corregir
                    </button>{" "}
                    <button className="secundario" onClick={() => cerrar(p.id)}>
                      Cerrar definitivamente
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
