import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { Periodo, Unidad } from "./tipos";
import { GrillaTurnos } from "./paginas/GrillaTurnos";
import { PaginaLiquidacion } from "./paginas/Liquidacion";
import { Configuracion } from "./paginas/Configuracion";
import { Entidades } from "./paginas/Entidades";

type Pestana = "turnos" | "liquidacion" | "configuracion" | "entidades";

const PESTANAS: { id: Pestana; titulo: string }[] = [
  { id: "turnos", titulo: "Cuadro de turnos" },
  { id: "liquidacion", titulo: "Liquidación" },
  { id: "configuracion", titulo: "Configuración" },
  { id: "entidades", titulo: "Unidades y empleados" },
];

export default function App() {
  const [pestana, setPestana] = useState<Pestana>("turnos");
  const [unidades, setUnidades] = useState<Unidad[]>([]);
  const [periodos, setPeriodos] = useState<Periodo[]>([]);

  const recargar = useCallback(async () => {
    const [u, p] = await Promise.all([api.unidades.listar(), api.periodos.listar()]);
    setUnidades(u);
    setPeriodos(p);
  }, []);

  useEffect(() => {
    recargar().catch(console.error);
  }, [recargar]);

  return (
    <>
      <header className="barra">
        <h1>Nómina — Unidades Residenciales</h1>
        <nav className="pestanas">
          {PESTANAS.map((p) => (
            <button
              key={p.id}
              className={pestana === p.id ? "activa" : ""}
              onClick={() => setPestana(p.id)}
            >
              {p.titulo}
            </button>
          ))}
        </nav>
      </header>
      <main className="contenedor">
        {pestana === "turnos" && <GrillaTurnos unidades={unidades} periodos={periodos} />}
        {pestana === "liquidacion" && (
          <PaginaLiquidacion unidades={unidades} periodos={periodos} alCambiar={recargar} />
        )}
        {pestana === "configuracion" && <Configuracion />}
        {pestana === "entidades" && (
          <Entidades unidades={unidades} periodos={periodos} alCambiar={recargar} />
        )}
      </main>
    </>
  );
}
