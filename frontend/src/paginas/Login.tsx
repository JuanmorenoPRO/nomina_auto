import { useState } from "react";
import { api } from "../api";
import type { Usuario } from "../tipos";

export function Login({ alIngresar }: { alIngresar: (usuario: Usuario) => void }) {
  const [email, setEmail] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  async function ingresar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setCargando(true);
    try {
      alIngresar(await api.auth.login(email, contrasena));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setCargando(false);
    }
  }

  return (
    <main className="contenedor" style={{ maxWidth: 420, marginTop: 80 }}>
      <div className="tarjeta">
        <h2>Nómina — Unidades Residenciales</h2>
        <form onSubmit={ingresar}>
          <div className="fila">
            <label className="campo" style={{ flex: 1 }}>
              Correo
              <input
                required
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
          </div>
          <div className="fila">
            <label className="campo" style={{ flex: 1 }}>
              Contraseña
              <input
                required
                type="password"
                autoComplete="current-password"
                value={contrasena}
                onChange={(e) => setContrasena(e.target.value)}
              />
            </label>
          </div>
          {error && <div className="error">{error}</div>}
          <button className="principal" type="submit" disabled={cargando}>
            {cargando ? "Ingresando…" : "Ingresar"}
          </button>
        </form>
      </div>
    </main>
  );
}
