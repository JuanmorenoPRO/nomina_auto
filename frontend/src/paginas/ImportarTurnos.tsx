import { useState } from "react";
import { api } from "../api";
import type { Empleado, Periodo, ReporteImportacion, Unidad } from "../tipos";

const ETIQUETAS_MARCAS: Record<string, string> = {
  quincena_incompleta: "quincena incompleta",
  sin_extras: "sin extras",
  auxilio_por_dias_laborados: "auxilio prorrateado",
  pagar_dia_31: "día 31",
};

function resumenMarcas(marcas: Record<string, boolean>): string {
  const activas = Object.entries(marcas)
    .filter(([, valor]) => valor)
    .map(([clave]) => ETIQUETAS_MARCAS[clave] ?? clave);
  return activas.length ? activas.join(", ") : "—";
}

/** Importar el cuadro de turnos de una quincena desde la plantilla de Excel.
 *
 *  Son dos pasos a propósito: al elegir el archivo se valida sin escribir nada
 *  (el backend devuelve el mismo reporte) y solo se aplica al confirmar, porque
 *  la importación REEMPLAZA los turnos de la quincena de cada empleado que
 *  venga en el archivo.
 *
 *  Con `empleado` la importación es la misma (el archivo manda), pero el texto
 *  habla de una sola hoja: así se usa desde la tarjeta de turnos. */
export function ImportarTurnos({
  unidad,
  periodo,
  empleado,
  alCerrar,
  alImportado,
}: {
  unidad: Unidad;
  periodo: Periodo;
  empleado?: Empleado;
  alCerrar: () => void;
  alImportado: () => void | Promise<void>;
}) {
  const [archivo, setArchivo] = useState<File | null>(null);
  const [reporte, setReporte] = useState<ReporteImportacion | null>(null);
  const [error, setError] = useState("");
  const [trabajando, setTrabajando] = useState(false);
  const [listo, setListo] = useState(false);

  const enviar = async (candidato: File, validarSolo: boolean) => {
    setTrabajando(true);
    setError("");
    try {
      const resultado = await api.turnos.importar(periodo.id, unidad.id, candidato, validarSolo);
      setReporte(resultado);
      if (resultado.aplicado) {
        setListo(true);
        await alImportado();
      }
    } catch (e) {
      setReporte(null);
      setError((e as Error).message);
    } finally {
      setTrabajando(false);
    }
  };

  const elegir = (candidato: File | null) => {
    setArchivo(candidato);
    setReporte(null);
    setListo(false);
    setError("");
    if (candidato) void enviar(candidato, true);
  };

  const hayErrores = reporte !== null && reporte.errores.length > 0;
  const puedeImportar = archivo !== null && reporte !== null && !hayErrores && !listo;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.4)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
      }}
      onClick={(e) => e.target === e.currentTarget && alCerrar()}
    >
      <div className="tarjeta modal-importar">
        <h3 style={{ marginTop: 0 }}>
          Importar turnos {empleado ? `de ${empleado.nombre}` : "desde Excel"}
        </h3>
        <p className="pista" style={{ marginTop: 0 }}>
          {unidad.nombre} — quincena del {periodo.fecha_inicio} al {periodo.fecha_fin}.
          {" "}Los turnos de cada empleado que venga en el archivo se <b>reemplazan</b> por
          los de su hoja; los que no estén en el archivo no se tocan.
        </p>

        <div className="fila">
          <a className="secundario" href={api.turnos.urlPlantilla(periodo.id, unidad.id, empleado?.id)}>
            Descargar plantilla
          </a>
          <label className="campo">
            Archivo (.xlsx)
            <input
              type="file"
              accept=".xlsx"
              disabled={trabajando}
              onChange={(e) => elegir(e.target.files?.[0] ?? null)}
            />
          </label>
        </div>

        {error && <div className="error">{error}</div>}
        {trabajando && <p className="pista">Leyendo el archivo…</p>}

        {listo && reporte && (
          <div className="pista" style={{ background: "#ecfdf5", borderColor: "#6ee7b7" }}>
            Importado: {reporte.hojas.length} empleado(s),{" "}
            {reporte.hojas.reduce((suma, h) => suma + h.turnos_creados, 0)} turnos.
          </div>
        )}

        {hayErrores && (
          <>
            <div className="error">
              No se guardó nada: corrija el archivo y vuelva a subirlo.
            </div>
            <div className="previa-scroll">
              <table className="tarjeta-turnos">
                <thead>
                  <tr>
                    <th>Hoja</th>
                    <th>Fila</th>
                    <th>Qué corregir</th>
                  </tr>
                </thead>
                <tbody>
                  {reporte.errores.map((e, indice) => (
                    <tr key={`${e.hoja}-${e.fila}-${indice}`}>
                      <td>{e.hoja}</td>
                      <td>{e.fila ?? "—"}</td>
                      <td>{e.mensaje}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {reporte && !hayErrores && reporte.hojas.length > 0 && (
          <div className="previa-scroll">
            <table className="tarjeta-turnos">
              <thead>
                <tr>
                  <th>Empleado</th>
                  <th>C.C.</th>
                  <th>Turnos</th>
                  <th>Reemplaza</th>
                  <th>Horas</th>
                  <th>Marcas</th>
                </tr>
              </thead>
              <tbody>
                {reporte.hojas.map((h) => (
                  <tr key={h.hoja}>
                    <td>{h.empleado}</td>
                    <td>{h.documento}</td>
                    <td>{h.turnos_creados}</td>
                    <td>{h.turnos_borrados}</td>
                    <td>{h.horas}</td>
                    <td>{resumenMarcas(h.marcas)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {reporte.ignoradas.length > 0 && (
              <p className="pista">
                Hojas que no son de turnos y se ignoran: {reporte.ignoradas.join(", ")}.
              </p>
            )}
          </div>
        )}

        <div className="fila" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="secundario" onClick={alCerrar}>
            {listo ? "Cerrar" : "Cancelar"}
          </button>
          {!listo && (
            <button
              type="button"
              className="principal"
              disabled={!puedeImportar || trabajando}
              onClick={() => archivo && void enviar(archivo, false)}
            >
              {trabajando ? "Importando…" : "Importar"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
