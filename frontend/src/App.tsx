import { useCallback, useEffect, useState } from "react";
import { api, EVENTO_NO_AUTENTICADO } from "./api";
import type { Periodo, Rol, Unidad, Usuario } from "./tipos";
import { GrillaTurnos } from "./paginas/GrillaTurnos";
import { PaginaLiquidacion } from "./paginas/Liquidacion";
import { Configuracion } from "./paginas/Configuracion";
import { Entidades } from "./paginas/Entidades";
import { Login } from "./paginas/Login";

type Pestana = "turnos" | "liquidacion" | "configuracion" | "entidades";

// La visibilidad por rol es solo comodidad de UI: el backend verifica SIEMPRE.
const PESTANAS: { id: Pestana; titulo: string; rolMinimo: Rol }[] = [
  { id: "turnos", titulo: "Cuadro de turnos", rolMinimo: "operador" },
  { id: "liquidacion", titulo: "Liquidación", rolMinimo: "contadora" },
  { id: "entidades", titulo: "Unidades y empleados", rolMinimo: "contadora" },
  { id: "configuracion", titulo: "Configuración", rolMinimo: "admin" },
];

const RANGO: Record<Rol, number> = { operador: 1, contadora: 2, admin: 3 };

export default function App() {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [verificando, setVerificando] = useState(true);
  const [pestana, setPestana] = useState<Pestana>("turnos");
  const [unidades, setUnidades] = useState<Unidad[]>([]);
  const [periodos, setPeriodos] = useState<Periodo[]>([]);

  const recargar = useCallback(async () => {
    const [u, p] = await Promise.all([api.unidades.listar(), api.periodos.listar()]);
    setUnidades(u);
    setPeriodos(p);
  }, []);

  useEffect(() => {
    api.auth
      .yo()
      .then(setUsuario)
      .catch(() => setUsuario(null))
      .finally(() => setVerificando(false));
    const alExpirar = () => setUsuario(null);
    window.addEventListener(EVENTO_NO_AUTENTICADO, alExpirar);
    return () => window.removeEventListener(EVENTO_NO_AUTENTICADO, alExpirar);
  }, []);

  useEffect(() => {
    if (usuario) recargar().catch(console.error);
  }, [usuario, recargar]);

  if (verificando) return null;
  if (!usuario) return <Login alIngresar={setUsuario} />;

  const visibles = PESTANAS.filter((p) => RANGO[usuario.rol] >= RANGO[p.rolMinimo]);
  const activa = visibles.some((p) => p.id === pestana) ? pestana : visibles[0].id;

  async function salir() {
    await api.auth.logout().catch(() => undefined);
    setUsuario(null);
  }

  return (
    <>
      <header className="barra">
        <h1>Nómina — Unidades Residenciales</h1>
        <nav className="pestanas">
          {visibles.map((p) => (
            <button
              key={p.id}
              className={activa === p.id ? "activa" : ""}
              onClick={() => setPestana(p.id)}
            >
              {p.titulo}
            </button>
          ))}
        </nav>
        <span style={{ marginLeft: "auto", fontSize: 13 }}>
          {usuario.email} ({usuario.rol}){" "}
          <button className="secundario" onClick={salir}>Salir</button>
        </span>
      </header>
      <main className="contenedor">
        {activa === "turnos" && <GrillaTurnos unidades={unidades} periodos={periodos} />}
        {activa === "liquidacion" && (
          <PaginaLiquidacion unidades={unidades} periodos={periodos} alCambiar={recargar} />
        )}
        {activa === "configuracion" && <Configuracion />}
        {activa === "entidades" && (
          <Entidades unidades={unidades} periodos={periodos} alCambiar={recargar} />
        )}
      </main>
    </>
  );
}
