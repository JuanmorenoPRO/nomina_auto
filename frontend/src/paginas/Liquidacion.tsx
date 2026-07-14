import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { Liquidacion, Periodo, Unidad } from "../tipos";

const pesos = new Intl.NumberFormat("es-CO");

export function PaginaLiquidacion({
  unidades,
  periodos,
  alCambiar,
}: {
  unidades: Unidad[];
  periodos: Periodo[];
  alCambiar: () => Promise<void>;
}) {
  const [unidadId, setUnidadId] = useState("");
  const [periodoId, setPeriodoId] = useState("");
  const [historial, setHistorial] = useState<Liquidacion[]>([]);
  const [detalle, setDetalle] = useState<Liquidacion | null>(null);
  const [error, setError] = useState("");
  const [liquidando, setLiquidando] = useState(false);

  const recargarHistorial = useCallback(async () => {
    if (!periodoId) return setHistorial([]);
    setHistorial(await api.liquidaciones.listar(periodoId));
  }, [periodoId]);

  useEffect(() => {
    recargarHistorial().catch((e) => setError(e.message));
    setDetalle(null);
  }, [recargarHistorial]);

  async function liquidar() {
    setError("");
    setLiquidando(true);
    try {
      const resultado = await api.periodos.liquidar(periodoId, unidadId);
      setDetalle(resultado);
      await recargarHistorial();
      await alCambiar(); // el periodo cambió a «liquidado»
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLiquidando(false);
    }
  }

  return (
    <>
      <h2>Liquidación de quincena</h2>
      <div className="fila">
        <label className="campo">
          Quincena
          <select value={periodoId} onChange={(e) => setPeriodoId(e.target.value)}>
            <option value="">— seleccione —</option>
            {periodos.map((p) => (
              <option key={p.id} value={p.id}>
                {p.fecha_inicio} al {p.fecha_fin} ({p.estado})
              </option>
            ))}
          </select>
        </label>
        <label className="campo">
          Unidad residencial
          <select value={unidadId} onChange={(e) => setUnidadId(e.target.value)}>
            <option value="">— seleccione —</option>
            {unidades.map((u) => (
              <option key={u.id} value={u.id}>{u.nombre}</option>
            ))}
          </select>
        </label>
        <button
          className="principal"
          disabled={!unidadId || !periodoId || liquidando}
          onClick={liquidar}
        >
          {liquidando ? "Liquidando…" : "Liquidar"}
        </button>
      </div>
      <p className="pista">
        Reliquidar crea una nueva versión: las versiones anteriores no se modifican.
      </p>

      {error && <div className="error">{error}</div>}

      {historial.length > 0 && (
        <div className="tarjeta">
          <h3>Liquidaciones del periodo</h3>
          <table className="datos">
            <thead>
              <tr>
                <th>Unidad</th>
                <th>Versión</th>
                <th>Fecha de creación</th>
                <th className="numero">Total devengado</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {historial.map((liq) => (
                <tr key={liq.id}>
                  <td>{liq.unidad.nombre}</td>
                  <td>v{liq.version}</td>
                  <td>{new Date(liq.creada_en).toLocaleString("es-CO")}</td>
                  <td className="numero">$ {pesos.format(liq.total)}</td>
                  <td>
                    <button className="secundario" onClick={() => setDetalle(liq)}>
                      Ver detalle
                    </button>{" "}
                    <a className="principal" href={api.liquidaciones.urlExcel(liq.id)}>
                      Excel
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {detalle && <DetalleLiquidacion liquidacion={detalle} />}
    </>
  );
}

function DetalleLiquidacion({ liquidacion }: { liquidacion: Liquidacion }) {
  return (
    <div className="tarjeta">
      <h3>
        {liquidacion.unidad.nombre} — {liquidacion.periodo.fecha_inicio} al{" "}
        {liquidacion.periodo.fecha_fin} (versión {liquidacion.version})
      </h3>
      {liquidacion.empleados.map((emp) => (
        <div key={emp.empleado_id}>
          <h3>
            {emp.nombre} — CC {emp.documento} · salario $ {pesos.format(emp.salario_mensual)}
          </h3>
          <table className="datos">
            <thead>
              <tr>
                <th>Concepto</th>
                <th className="numero">Horas</th>
                <th className="numero">Factor</th>
                <th className="numero">Valor</th>
              </tr>
            </thead>
            <tbody>
              {emp.conceptos.map((c, i) => (
                <tr key={i}>
                  <td title={Object.entries(c.componentes)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(" + ")}>
                    {c.nombre}
                  </td>
                  <td className="numero">{c.minutos ? c.horas : ""}</td>
                  <td className="numero">{c.factor ?? ""}</td>
                  <td className="numero">$ {pesos.format(c.valor)}</td>
                </tr>
              ))}
              <tr>
                <td colSpan={3}><b>TOTAL DEVENGADO</b></td>
                <td className="numero"><b>$ {pesos.format(emp.total)}</b></td>
              </tr>
            </tbody>
          </table>
        </div>
      ))}
      <h3>Total unidad: $ {pesos.format(liquidacion.total)}</h3>
    </div>
  );
}
