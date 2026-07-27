import { useState } from "react";
import { api } from "../api";

export function CambiarContrasena({ alCerrar }: { alCerrar: () => void }) {
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [error, setError] = useState("");
  const [exito, setExito] = useState(false);
  const [cargando, setCargando] = useState(false);

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (nueva !== confirmar) {
      setError("Las contraseñas nuevas no coinciden");
      return;
    }
    if (nueva.length < 10) {
      setError("La nueva contraseña debe tener al menos 10 caracteres");
      return;
    }
    setCargando(true);
    try {
      await api.auth.cambiarContrasena(actual, nueva);
      setExito(true);
      setTimeout(alCerrar, 1500);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setCargando(false);
    }
  }

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
      <div className="tarjeta" style={{ width: 360, margin: 0 }}>
        <h3 style={{ marginTop: 0 }}>Cambiar contraseña</h3>
        {exito ? (
          <p style={{ color: "green" }}>Contraseña actualizada correctamente.</p>
        ) : (
          <form onSubmit={guardar}>
            <div className="fila">
              <label className="campo" style={{ flex: 1 }}>
                Contraseña actual
                <input
                  required
                  type="password"
                  autoComplete="current-password"
                  value={actual}
                  onChange={(e) => setActual(e.target.value)}
                />
              </label>
            </div>
            <div className="fila">
              <label className="campo" style={{ flex: 1 }}>
                Nueva contraseña
                <input
                  required
                  type="password"
                  autoComplete="new-password"
                  value={nueva}
                  onChange={(e) => setNueva(e.target.value)}
                />
              </label>
            </div>
            <div className="fila">
              <label className="campo" style={{ flex: 1 }}>
                Confirmar nueva contraseña
                <input
                  required
                  type="password"
                  autoComplete="new-password"
                  value={confirmar}
                  onChange={(e) => setConfirmar(e.target.value)}
                />
              </label>
            </div>
            {error && <div className="error">{error}</div>}
            <div className="fila" style={{ justifyContent: "flex-end" }}>
              <button type="button" className="secundario" onClick={alCerrar}>
                Cancelar
              </button>
              <button className="principal" type="submit" disabled={cargando}>
                {cargando ? "Guardando…" : "Guardar"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
