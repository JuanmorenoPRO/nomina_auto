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
  const [filtroUnidadId, setFiltroUnidadId] = useState("");
  const [historial, setHistorial] = useState<Liquidacion[]>([]);
  const [detalle, setDetalle] = useState<Liquidacion | null>(null);
  const [error, setError] = useState("");
  const [liquidando, setLiquidando] = useState(false);
  const [marcando, setMarcando] = useState(false);

  const periodo = periodos.find((p) => p.id === periodoId);

  const recargarHistorial = useCallback(async () => {
    if (!periodoId) return setHistorial([]);
    setHistorial(await api.liquidaciones.listar(periodoId));
  }, [periodoId]);

  useEffect(() => {
    recargarHistorial().catch((e) => setError(e.message));
    setDetalle(null);
  }, [recargarHistorial]);

  async function liquidar() {
    const yaExiste = historial.some((liq) => liq.unidad.id === unidadId);
    if (
      yaExiste &&
      !window.confirm(
        "Ya existe una liquidación para esta unidad en esta quincena. Al continuar se " +
          "eliminará y se reemplazará por la nueva. ¿Continuar?",
      )
    ) {
      return;
    }
    setError("");
    setLiquidando(true);
    try {
      const resultado = await api.periodos.liquidar(periodoId, unidadId);
      setDetalle(resultado);
      await recargarHistorial();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLiquidando(false);
    }
  }

  async function eliminarLiquidacion(liq: Liquidacion) {
    if (
      !window.confirm(
        `¿Eliminar la liquidación de ${liq.unidad.nombre}? Esta acción no se puede deshacer.`,
      )
    ) {
      return;
    }
    setError("");
    try {
      await api.liquidaciones.eliminar(liq.id);
      if (detalle?.id === liq.id) setDetalle(null);
      await recargarHistorial();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function marcarPeriodoLiquidado() {
    setError("");
    setMarcando(true);
    try {
      await api.periodos.marcarLiquidado(periodoId);
      await alCambiar(); // el periodo pasó a «liquidado»
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setMarcando(false);
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
        Liquidar una unidad no cierra la quincena: puede liquidar varias unidades del
        mismo periodo sin reabrirlo. Reliquidar reemplaza la liquidación anterior de esa
        unidad; solo se conserva la última.
      </p>

      {error && <div className="error">{error}</div>}

      {historial.length > 0 && (
        <div className="tarjeta">
          <h3>Liquidaciones del periodo</h3>
          <label className="campo">
            Filtrar por unidad
            <select
              value={filtroUnidadId}
              onChange={(e) => setFiltroUnidadId(e.target.value)}
            >
              <option value="">Todas las unidades</option>
              {unidades.map((u) => (
                <option key={u.id} value={u.id}>{u.nombre}</option>
              ))}
            </select>
          </label>
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
              {historial
                .filter((liq) => !filtroUnidadId || liq.unidad.id === filtroUnidadId)
                .map((liq) => (
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
                    </a>{" "}
                    <button className="peligro" onClick={() => eliminarLiquidacion(liq)}>
                      Borrar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {detalle && <DetalleLiquidacion liquidacion={detalle} />}

      {periodo && periodo.estado === "abierto" && historial.length > 0 && (
        <div className="tarjeta">
          <p className="pista">
            ¿Ya liquidó todas las unidades de esta quincena? Marque el periodo completo como
            liquidado. (Podrá reabrirlo si necesita corregir algo.)
          </p>
          <button
            className="principal"
            disabled={marcando}
            onClick={marcarPeriodoLiquidado}
          >
            {marcando ? "Marcando…" : "Marcar todo el periodo como liquidado"}
          </button>
        </div>
      )}
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
          {Number(emp.horas_sin_hora_base) > 0 && (
            <div className="error">
              <b>{emp.horas_sin_hora_base} horas trabajadas sin hora base.</b> El tiempo
              ordinario se paga como presupuesto fijo de la quincena, así que estas horas
              cobran su recargo pero no la hora base — y si son ordinarias diurnas, no
              cobran nada. Revise el criterio de horas extra de la unidad o los turnos
              registrados.
            </div>
          )}
          {Number(emp.horas_dia_31_bloqueadas) > 0 && (
            <div className="aviso-advertencia">
              <b>{emp.horas_dia_31_bloqueadas} h del día 31 quedaron como extras</b> y no
              aparecen en el concepto DIA 31. El flag &ldquo;Sin extras&rdquo; usa el
              presupuesto quincenal (105 h); si ese tope se agotó antes del 31, las horas
              de ese día son extras (ya incluyen la hora base en su factor). Para ver el
              concepto DIA 31, desactiva &ldquo;Sin extras&rdquo; en la tarjeta del
              empleado.
            </div>
          )}
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
                <td className="numero"><b>$ {pesos.format(emp.total_devengado)}</b></td>
              </tr>
              {emp.deducciones.length > 0 && (
                <>
                  <tr>
                    <td colSpan={4} className="subtitulo"><b>DEDUCCIONES</b></td>
                  </tr>
                  {emp.deducciones.map((d, i) => (
                    <tr key={`d${i}`}>
                      <td>{d.nombre}</td>
                      <td className="numero"></td>
                      <td className="numero">{d.factor ?? ""}</td>
                      <td className="numero">− $ {pesos.format(d.valor)}</td>
                    </tr>
                  ))}
                  <tr>
                    <td colSpan={3}><b>TOTAL DEDUCCIONES</b></td>
                    <td className="numero"><b>− $ {pesos.format(emp.total_deducciones)}</b></td>
                  </tr>
                </>
              )}
              <tr>
                <td colSpan={3}><b>VALOR A PAGAR</b></td>
                <td className="numero"><b>$ {pesos.format(emp.neto_a_pagar)}</b></td>
              </tr>
            </tbody>
          </table>
        </div>
      ))}
      <h3>Total devengado unidad: $ {pesos.format(liquidacion.total)}</h3>
    </div>
  );
}
