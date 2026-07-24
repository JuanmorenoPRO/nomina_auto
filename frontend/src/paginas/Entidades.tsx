import { useEffect, useState } from "react";
import { api } from "../api";
import type { ConceptoFijo, ConceptoManual, Empleado, Periodo, Unidad } from "../tipos";

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
      <SeccionConceptosFijos unidades={unidades} alCambiar={alCambiar} setError={setError} />
      <SeccionEmpleados unidades={unidades} setError={setError} />
      <SeccionConceptosManuales unidades={unidades} periodos={periodos} setError={setError} />
      <SeccionPeriodos periodos={periodos} alCambiar={alCambiar} setError={setError} />
    </>
  );
}

type Props = { alCambiar: () => Promise<void>; setError: (m: string) => void };

function SeccionUnidades({ unidades, alCambiar, setError }: Props & { unidades: Unidad[] }) {
  const [form, setForm] = useState({ nombre: "", nit: "", descuenta: false });

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.unidades.crear({
        nombre: form.nombre,
        nit: form.nit,
        descuenta_seguridad_social: form.descuenta,
      });
      setForm({ nombre: "", nit: "", descuenta: false });
      await alCambiar();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function alternarDescuento(u: Unidad) {
    setError("");
    try {
      await api.unidades.actualizar(u.id, {
        descuenta_seguridad_social: !u.descuenta_seguridad_social,
      });
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
        <label className="campo casilla">
          <input
            type="checkbox"
            checked={form.descuenta}
            onChange={(e) => setForm({ ...form, descuenta: e.target.checked })}
          />
          Descontar seguridad social (salud + pensión)
        </label>
        <button className="principal" type="submit">Crear unidad</button>
      </form>
      <table className="datos">
        <thead>
          <tr><th>Nombre</th><th>NIT</th><th>Descuenta seg. social</th></tr>
        </thead>
        <tbody>
          {unidades.map((u) => (
            <tr key={u.id}>
              <td>{u.nombre}</td>
              <td>{u.nit}</td>
              <td>
                <label className="casilla">
                  <input
                    type="checkbox"
                    checked={u.descuenta_seguridad_social}
                    onChange={() => alternarDescuento(u)}
                  />
                  {u.descuenta_seguridad_social ? "Sí" : "No"}
                </label>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SeccionConceptosFijos({
  unidades,
  alCambiar,
  setError,
}: Props & { unidades: Unidad[] }) {
  const [unidadId, setUnidadId] = useState("");
  const [form, setForm] = useState({ nombre: "", valor: "", tipo: "devengado", salarial: false });
  const unidad = unidades.find((u) => u.id === unidadId);
  const fijos: ConceptoFijo[] = unidad?.config.conceptos_fijos ?? [];

  async function guardar(nuevos: ConceptoFijo[]) {
    if (!unidad) return;
    setError("");
    try {
      await api.unidades.actualizar(unidad.id, {
        config: { ...unidad.config, conceptos_fijos: nuevos },
      });
      await alCambiar();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function agregar(e: React.FormEvent) {
    e.preventDefault();
    await guardar([
      ...fijos,
      {
        nombre: form.nombre,
        valor: Number(form.valor),
        tipo: form.tipo as "devengado" | "deduccion",
        salarial: form.salarial,
      },
    ]);
    setForm({ nombre: "", valor: "", tipo: "devengado", salarial: false });
  }

  return (
    <div className="tarjeta">
      <h2>Conceptos fijos por unidad</h2>
      <p className="pista">
        Devengados o deducciones que se aplican automáticamente a TODOS los empleados de la
        unidad en cada liquidación (ej. cuota de manejo de tarjeta).
      </p>
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
      {unidad && (
        <>
          <form className="fila" onSubmit={agregar}>
            <label className="campo">
              Nombre
              <input
                required
                value={form.nombre}
                placeholder="ej. CUOTA DE MANEJO TARJETA"
                onChange={(e) => setForm({ ...form, nombre: e.target.value })}
              />
            </label>
            <label className="campo">
              Valor (quincena)
              <input
                required
                type="number"
                min={1}
                value={form.valor}
                onChange={(e) => setForm({ ...form, valor: e.target.value })}
              />
            </label>
            <label className="campo">
              Tipo
              <select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
                <option value="devengado">Devengado</option>
                <option value="deduccion">Deducción</option>
              </select>
            </label>
            <label className="campo casilla">
              <input
                type="checkbox"
                checked={form.salarial}
                onChange={(e) => setForm({ ...form, salarial: e.target.checked })}
              />
              Salarial (suma al IBC)
            </label>
            <button className="principal" type="submit">Agregar</button>
          </form>
          <table className="datos">
            <thead>
              <tr>
                <th>Concepto</th><th>Tipo</th><th className="numero">Valor</th>
                <th>Salarial</th><th></th>
              </tr>
            </thead>
            <tbody>
              {fijos.map((c, i) => (
                <tr key={i}>
                  <td>{c.nombre}</td>
                  <td>{c.tipo}</td>
                  <td className="numero">$ {pesos.format(c.valor)}</td>
                  <td>{c.salarial ? "sí" : "no"}</td>
                  <td>
                    <button
                      className="secundario"
                      onClick={() => guardar(fijos.filter((_, j) => j !== i))}
                    >
                      Quitar
                    </button>
                  </td>
                </tr>
              ))}
              {fijos.length === 0 && (
                <tr><td colSpan={5} className="pista">Sin conceptos fijos.</td></tr>
              )}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

function SeccionConceptosManuales({
  unidades,
  periodos,
  setError,
}: {
  unidades: Unidad[];
  periodos: Periodo[];
  setError: (m: string) => void;
}) {
  const [unidadId, setUnidadId] = useState("");
  const [empleadoId, setEmpleadoId] = useState("");
  const [periodoId, setPeriodoId] = useState("");
  const [empleados, setEmpleados] = useState<Empleado[]>([]);
  const [conceptos, setConceptos] = useState<ConceptoManual[]>([]);
  const [form, setForm] = useState({ nombre: "", valor: "", tipo: "deduccion", salarial: false });

  useEffect(() => {
    if (!unidadId) return setEmpleados([]);
    api.empleados.listar(unidadId).then(setEmpleados).catch((e) => setError(e.message));
  }, [unidadId, setError]);

  async function recargar() {
    if (!empleadoId || !periodoId) return setConceptos([]);
    setConceptos(await api.conceptosManuales.listar(empleadoId, periodoId));
  }

  useEffect(() => {
    recargar().catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [empleadoId, periodoId]);

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.conceptosManuales.crear({
        empleado_id: empleadoId,
        periodo_id: periodoId,
        tipo: form.tipo as "devengado" | "deduccion",
        nombre: form.nombre,
        valor: Number(form.valor),
        salarial: form.salarial,
      });
      setForm({ nombre: "", valor: "", tipo: "deduccion", salarial: false });
      await recargar();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function eliminar(id: string) {
    setError("");
    try {
      await api.conceptosManuales.eliminar(id);
      await recargar();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="tarjeta">
      <h2>Conceptos manuales (por empleado y quincena)</h2>
      <p className="pista">
        Devengados o deducciones puntuales de un empleado en una quincena (ej. préstamos,
        descuentos, bonos). Se suman a los conceptos fijos de la unidad al liquidar.
      </p>
      <div className="fila">
        <label className="campo">
          Unidad
          <select value={unidadId} onChange={(e) => { setUnidadId(e.target.value); setEmpleadoId(""); }}>
            <option value="">— seleccione —</option>
            {unidades.map((u) => (
              <option key={u.id} value={u.id}>{u.nombre}</option>
            ))}
          </select>
        </label>
        <label className="campo">
          Empleado
          <select value={empleadoId} onChange={(e) => setEmpleadoId(e.target.value)}>
            <option value="">— seleccione —</option>
            {empleados.map((emp) => (
              <option key={emp.id} value={emp.id}>{emp.nombre}</option>
            ))}
          </select>
        </label>
        <label className="campo">
          Quincena
          <select value={periodoId} onChange={(e) => setPeriodoId(e.target.value)}>
            <option value="">— seleccione —</option>
            {periodos.map((p) => (
              <option key={p.id} value={p.id}>{p.fecha_inicio} al {p.fecha_fin}</option>
            ))}
          </select>
        </label>
      </div>
      {empleadoId && periodoId && (
        <>
          <form className="fila" onSubmit={crear}>
            <label className="campo">
              Nombre
              <input
                required
                value={form.nombre}
                placeholder="ej. PRÉSTAMO"
                onChange={(e) => setForm({ ...form, nombre: e.target.value })}
              />
            </label>
            <label className="campo">
              Valor
              <input
                required
                type="number"
                min={1}
                value={form.valor}
                onChange={(e) => setForm({ ...form, valor: e.target.value })}
              />
            </label>
            <label className="campo">
              Tipo
              <select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
                <option value="deduccion">Deducción</option>
                <option value="devengado">Devengado</option>
              </select>
            </label>
            <label className="campo casilla">
              <input
                type="checkbox"
                checked={form.salarial}
                onChange={(e) => setForm({ ...form, salarial: e.target.checked })}
              />
              Salarial
            </label>
            <button className="principal" type="submit">Agregar</button>
          </form>
          <table className="datos">
            <thead>
              <tr>
                <th>Concepto</th><th>Tipo</th><th className="numero">Valor</th><th></th>
              </tr>
            </thead>
            <tbody>
              {conceptos.map((c) => (
                <tr key={c.id}>
                  <td>{c.nombre}</td>
                  <td>{c.tipo}</td>
                  <td className="numero">$ {pesos.format(c.valor)}</td>
                  <td>
                    <button className="secundario" onClick={() => eliminar(c.id)}>Quitar</button>
                  </td>
                </tr>
              ))}
              {conceptos.length === 0 && (
                <tr><td colSpan={4} className="pista">Sin conceptos manuales.</td></tr>
              )}
            </tbody>
          </table>
        </>
      )}
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
