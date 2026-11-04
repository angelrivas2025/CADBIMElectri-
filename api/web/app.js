"use strict";

const SVG_NS = "http://www.w3.org/2000/svg";
const $ = (id) => document.getElementById(id);

const COLORES_AMBIENTE = {
  sala: "#e8f0fb",
  dormitorio: "#eaf5ec",
  cocina: "#fdf0e3",
  bano: "#e8f6f7",
  servicio: "#f3eefc",
  garaje: "#eef0f3",
  externo: "#f8f4e8",
  otro: "#f0f2f5",
};

const ALTURAS = { luminaria: 2.6, interruptor: 1.1, tug: 1.1, tue: 1.1 };

const ETIQUETAS_ARCHIVO = {
  svg: "Unifilar SVG",
  pdf: "Informe PDF",
  csv: "Cuadro CSV",
  materiales: "Materiales CSV",
  ifc: "Modelo IFC",
};

const estado = {
  proyecto: null,
  validacion: null,
  puedeDeshacer: false,
  nivel: null,
  vista: null,
  preview: null,
  ocupado: false,
  temporizador: null,
};

function crear(etiqueta, atributos = {}) {
  const elemento = document.createElementNS(SVG_NS, etiqueta);
  for (const [clave, valor] of Object.entries(atributos)) {
    elemento.setAttribute(clave, String(valor));
  }
  return elemento;
}

function numero(valor, decimales = 2) {
  if (valor === null || valor === undefined || Number.isNaN(Number(valor))) {
    return "—";
  }
  return Number(valor).toLocaleString("es-ES", {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimales,
  });
}

function redondear(valor) {
  return Math.round(valor * 100) / 100;
}

function mostrarEstado(mensaje, esError = false) {
  const linea = $("estado-linea");
  linea.textContent = mensaje;
  linea.classList.toggle("error", esError);
  linea.classList.add("visible");
  clearTimeout(estado.temporizador);
  estado.temporizador = setTimeout(() => linea.classList.remove("visible"), 4200);
}

async function pedir(url, opciones = {}) {
  const inicio = { method: opciones.method || "GET", headers: {} };
  if (opciones.body) {
    inicio.headers["Content-Type"] = "application/json";
    inicio.body = opciones.body;
  }
  const respuesta = await fetch(url, inicio);
  let datos = null;
  try {
    datos = await respuesta.json();
  } catch {
    datos = null;
  }
  if (!respuesta.ok) {
    let detalle = datos && datos.detail ? datos.detail : `Error HTTP ${respuesta.status}`;
    if (typeof detalle !== "string") {
      detalle = JSON.stringify(detalle);
    }
    throw new Error(detalle);
  }
  return datos;
}

function aplicarEstado(datos) {
  if (datos.proyecto) {
    estado.proyecto = datos.proyecto;
  }
  if (datos.validacion) {
    estado.validacion = datos.validacion;
  }
  if (typeof datos.puede_deshacer === "boolean") {
    estado.puedeDeshacer = datos.puede_deshacer;
  }
  if (estado.preview && estado.proyecto) {
    const existe = estado.proyecto.rooms.some(
      (ambiente) => ambiente.id === estado.preview.room
    );
    if (!existe) {
      estado.preview = null;
    }
  }
  renderTodo();
}

function renderTodo() {
  renderCabecera();
  renderNiveles();
  renderAmbientes();
  renderPlano();
  renderValidacion();
  $("btn-deshacer").disabled = !estado.puedeDeshacer;
}

function renderCabecera() {
  const proyecto = estado.proyecto;
  if (!proyecto) {
    return;
  }
  const datos = proyecto.project;
  $("proyecto-nombre").textContent = `${datos.name} · ${datos.norm} · ${numero(
    datos.voltage,
    0
  )} V · ${datos.system}`;
}

function renderNiveles() {
  const select = $("nivel-planta");
  const niveles = (estado.proyecto && estado.proyecto.levels) || [];
  if (!niveles.some((nivel) => nivel.id === estado.nivel)) {
    estado.nivel = niveles.length ? niveles[0].id : null;
  }
  select.replaceChildren();
  for (const nivel of niveles) {
    const opcion = document.createElement("option");
    opcion.value = nivel.id;
    opcion.textContent = nivel.name;
    select.append(opcion);
  }
  select.disabled = niveles.length === 0;
  if (estado.nivel) {
    select.value = estado.nivel;
  }
}

function ambientesVisibles() {
  const proyecto = estado.proyecto;
  if (!proyecto) {
    return [];
  }
  return proyecto.rooms.filter(
    (ambiente) => !estado.nivel || ambiente.level === estado.nivel
  );
}

function puntosVisibles() {
  const ids = new Set(ambientesVisibles().map((ambiente) => ambiente.id));
  return ((estado.proyecto && estado.proyecto.points) || []).filter((punto) =>
    ids.has(punto.room)
  );
}

function renderAmbientes() {
  const select = $("punto-ambiente");
  const anterior = select.value;
  select.replaceChildren();
  const ambientes = ambientesVisibles();
  if (ambientes.length === 0) {
    const opcion = document.createElement("option");
    opcion.value = "";
    opcion.textContent = "Sin ambientes";
    select.append(opcion);
    select.disabled = true;
    $("punto-potencia").disabled = true;
    $("punto-tipo").disabled = true;
    return;
  }
  select.disabled = false;
  $("punto-potencia").disabled = false;
  $("punto-tipo").disabled = false;
  for (const ambiente of ambientes) {
    const opcion = document.createElement("option");
    opcion.value = ambiente.id;
    opcion.textContent = `${ambiente.name} (${ambiente.id})`;
    select.append(opcion);
  }
  if (ambientes.some((ambiente) => ambiente.id === anterior)) {
    select.value = anterior;
  }
}

function limites() {
  const xs = [];
  const ys = [];
  for (const ambiente of ambientesVisibles()) {
    for (const [x, y] of ambiente.polygon) {
      xs.push(x);
      ys.push(y);
    }
  }
  for (const punto of puntosVisibles()) {
    xs.push(punto.position[0]);
    ys.push(punto.position[1]);
  }
  if (xs.length === 0) {
    return { minX: 0, minY: 0, maxX: 1, maxY: 1 };
  }
  return {
    minX: Math.min(...xs),
    minY: Math.min(...ys),
    maxX: Math.max(...xs),
    maxY: Math.max(...ys),
  };
}

function areaPoligono(poligono) {
  let suma = 0;
  for (let i = 0, j = poligono.length - 1; i < poligono.length; j = i++) {
    suma += poligono[j][0] * poligono[i][1] - poligono[i][0] * poligono[j][1];
  }
  return Math.abs(suma) / 2;
}

function centroide(poligono) {
  let x = 0;
  let y = 0;
  for (const [px, py] of poligono) {
    x += px;
    y += py;
  }
  return [x / poligono.length, y / poligono.length];
}

function renderPlano() {
  const svg = $("plano");
  svg.replaceChildren();
  const proyecto = estado.proyecto;
  if (!proyecto) {
    return;
  }

  const { minX, minY, maxX, maxY } = limites();
  const ancho = Math.max(maxX - minX, 0.5);
  const alto = Math.max(maxY - minY, 0.5);
  const margen = Math.min(1.2, Math.max(0.35, Math.max(ancho, alto) * 0.06));
  const anchoVista = ancho + margen * 2;
  const altoVista = alto + margen * 2;

  svg.setAttribute("viewBox", `0 0 ${anchoVista} ${altoVista}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  estado.vista = { minX, maxY, margen };

  const px = (x) => x - minX + margen;
  const py = (y) => maxY - y + margen;

  const paso = ancho + alto > 45 ? 5 : ancho + alto > 22 ? 2 : 1;
  const rejilla = crear("g", { "aria-hidden": "true" });
  const inicioX = Math.ceil(minX / paso) * paso;
  for (let x = inicioX; x <= maxX; x += paso) {
    rejilla.append(
      crear("line", {
        x1: px(x),
        y1: py(minY),
        x2: px(x),
        y2: py(maxY),
        stroke: "#e5ebf1",
        "stroke-width": 0.012,
      })
    );
  }
  const inicioY = Math.ceil(minY / paso) * paso;
  for (let y = inicioY; y <= maxY; y += paso) {
    rejilla.append(
      crear("line", {
        x1: px(minX),
        y1: py(y),
        x2: px(maxX),
        y2: py(y),
        stroke: "#e5ebf1",
        "stroke-width": 0.012,
      })
    );
  }
  svg.append(rejilla);

  const seleccionado = $("punto-ambiente").value;
  const tamanoTexto = Math.min(0.3, Math.max(0.14, Math.min(ancho, alto) * 0.022));
  for (const ambiente of ambientesVisibles()) {
    const puntos = ambiente.polygon
      .map(([x, y]) => `${px(x).toFixed(3)},${py(y).toFixed(3)}`)
      .join(" ");
    const poligono = crear("polygon", {
      points: puntos,
      class:
        "ambiente" + (ambiente.id === seleccionado ? " seleccionado" : ""),
      fill: COLORES_AMBIENTE[ambiente.type] || COLORES_AMBIENTE.otro,
    });
    const titulo = crear("title");
    titulo.textContent = `${ambiente.name} (${ambiente.id})`;
    poligono.append(titulo);
    svg.append(poligono);

    const [cx, cy] = centroide(ambiente.polygon);
    const etiqueta = crear("text", {
      x: px(cx),
      y: py(cy) - tamanoTexto * 0.15,
      class: "nombre-ambiente",
      "font-size": tamanoTexto,
    });
    etiqueta.textContent = ambiente.name;
    svg.append(etiqueta);

    const detalle = crear("text", {
      x: px(cx),
      y: py(cy) + tamanoTexto * 0.95,
      class: "nombre-ambiente",
      "font-size": tamanoTexto * 0.72,
      fill: "#71818f",
    });
    detalle.textContent = `${numero(areaPoligono(ambiente.polygon), 1)} m²`;
    svg.append(detalle);
  }

  const radio = Math.min(0.13, Math.max(0.07, Math.min(ancho, alto) * 0.012));
  for (const punto of puntosVisibles()) {
    const [x, y] = punto.position;
    let figura;
    if (punto.type === "luminaria") {
      figura = crear("circle", {
        cx: px(x),
        cy: py(y),
        r: radio,
      });
    } else if (punto.type === "tablero") {
      figura = crear("rect", {
        x: px(x) - radio * 1.2,
        y: py(y) - radio * 0.8,
        width: radio * 2.4,
        height: radio * 1.6,
        rx: radio * 0.15,
      });
    } else {
      figura = crear("rect", {
        x: px(x) - radio * 0.9,
        y: py(y) - radio * 0.9,
        width: radio * 1.8,
        height: radio * 1.8,
        rx: radio * 0.2,
      });
    }
    figura.setAttribute("class", `punto ${punto.type}`);
    const titulo = crear("title");
    const circuito = punto.circuit ? ` · circuito ${punto.circuit}` : " · sin circuito";
    titulo.textContent = `${punto.id} · ${punto.type} · ${numero(
      punto.power,
      0
    )} VA${circuito}`;
    figura.append(titulo);
    svg.append(figura);
  }

  if (estado.preview) {
    const marca = crear("circle", {
      cx: px(estado.preview.x),
      cy: py(estado.preview.y),
      r: radio * 1.9,
      class: "punto seleccion-preview",
    });
    svg.append(marca);
  }
}

function renderValidacion() {
  const validacion = estado.validacion;
  const veredicto = $("veredicto");
  const listaErrores = $("lista-errores");
  const listaAvisos = $("lista-avisos");
  listaErrores.replaceChildren();
  listaAvisos.replaceChildren();
  $("tabla-circuitos").replaceChildren();
  $("alimentador").textContent = "";

  if (!validacion) {
    veredicto.textContent = "Sin datos";
    veredicto.className = "veredicto";
    return;
  }

  veredicto.textContent = validacion.conforme
    ? "Conforme a los controles del motor"
    : "No conforme: revise los errores";
  veredicto.className = "veredicto " + (validacion.conforme ? "ok" : "error");

  const llenar = (lista, textos, vacio) => {
    if (!textos || textos.length === 0) {
      const item = document.createElement("li");
      item.textContent = vacio;
      item.className = "vacio";
      lista.append(item);
      return;
    }
    for (const texto of textos) {
      const item = document.createElement("li");
      item.textContent = texto;
      lista.append(item);
    }
  };
  llenar(listaErrores, validacion.errores, "Sin errores.");
  llenar(listaAvisos, validacion.avisos, "Sin avisos.");

  const cuerpo = $("tabla-circuitos");
  for (const circuito of validacion.circuitos || []) {
    const fila = document.createElement("tr");
    const celdas = [
      circuito.id,
      numero(circuito.breaker_a, 0),
      numero(circuito.section_mm2, 1),
      numero(circuito.current_a, 2),
      numero(circuito.voltage_drop_pct, 2),
    ];
    celdas.forEach((valor, indice) => {
      const celda = document.createElement("td");
      if (indice > 0) {
        celda.className = "num";
      }
      celda.textContent = valor;
      fila.append(celda);
    });
    cuerpo.append(fila);
  }

  const alimentador = validacion.alimentador;
  if (alimentador) {
    const partes = [];
    if (alimentador.section_mm2 !== undefined) {
      partes.push(`${numero(alimentador.section_mm2, 1)} mm²`);
    }
    if (alimentador.breaker_a !== undefined) {
      partes.push(`disyuntor ${numero(alimentador.breaker_a, 0)} A`);
    }
    if (alimentador.current_a !== undefined) {
      partes.push(`${numero(alimentador.current_a, 2)} A`);
    }
    if (alimentador.voltage_drop_pct !== undefined) {
      partes.push(`caída ${numero(alimentador.voltage_drop_pct, 2)} %`);
    }
    $("alimentador").textContent = partes.length
      ? `Alimentador: ${partes.join(" · ")}`
      : "";
  }
}

function siguienteId(prefijo, existentes) {
  const patron = new RegExp(`^${prefijo}(\\d+)$`);
  let mayor = 0;
  for (const item of existentes) {
    const coincidencia = patron.exec(item.id);
    if (coincidencia) {
      mayor = Math.max(mayor, Number(coincidencia[1]));
    }
  }
  return `${prefijo}${mayor + 1}`;
}

function aModelo(evento) {
  const svg = $("plano");
  if (!estado.vista || !svg.getScreenCTM) {
    return null;
  }
  const punto = svg.createSVGPoint();
  punto.x = evento.clientX;
  punto.y = evento.clientY;
  const transformado = punto.matrixTransform(svg.getScreenCTM().inverse());
  const { minX, maxY, margen } = estado.vista;
  return {
    x: transformado.x + minX - margen,
    y: maxY - transformado.y + margen,
  };
}

function dentroDePoligono(punto, poligono) {
  let dentro = false;
  for (let i = 0, j = poligono.length - 1; i < poligono.length; j = i++) {
    const [xi, yi] = poligono[i];
    const [xj, yj] = poligono[j];
    const cruza =
      yi > punto.y !== yj > punto.y &&
      punto.x < ((xj - xi) * (punto.y - yi)) / (yj - yi) + xi;
    if (cruza) {
      dentro = !dentro;
    }
  }
  return dentro;
}

async function enviarHerramienta(tool, argumentos, mensajeExito) {
  if (estado.ocupado) {
    return false;
  }
  estado.ocupado = true;
  try {
    const datos = await pedir("/api/herramienta", {
      method: "POST",
      body: JSON.stringify({ tool, arguments: argumentos }),
    });
    aplicarEstado(datos);
    mostrarEstado(mensajeExito || "Cambio aplicado.");
    return true;
  } catch (error) {
    mostrarEstado(error.message, true);
    return false;
  } finally {
    estado.ocupado = false;
  }
}

function conectarPlano() {
  $("plano").addEventListener("click", (evento) => {
    if (!estado.proyecto) {
      return;
    }
    const ambienteId = $("punto-ambiente").value;
    const ambiente = estado.proyecto.rooms.find((r) => r.id === ambienteId);
    if (!ambiente) {
      mostrarEstado("Primero elija un ambiente.", true);
      return;
    }
    const punto = aModelo(evento);
    if (!punto) {
      return;
    }
    if (!dentroDePoligono(punto, ambiente.polygon)) {
      mostrarEstado(`El clic quedó fuera de ${ambiente.name}.`, true);
      return;
    }
    estado.preview = { x: punto.x, y: punto.y, room: ambiente.id };
    $("btn-punto").disabled = false;
    $("pista-punto").textContent = `Punto en (${numero(punto.x)}, ${numero(
      punto.y
    )}) m dentro de ${ambiente.name}.`;
    renderPlano();
  });

  $("punto-ambiente").addEventListener("change", () => {
    estado.preview = null;
    $("btn-punto").disabled = true;
    $("pista-punto").textContent =
      "Haga clic dentro del ambiente elegido para ubicar el punto.";
    renderPlano();
  });

  $("nivel-planta").addEventListener("change", () => {
    estado.nivel = $("nivel-planta").value;
    estado.preview = null;
    $("btn-punto").disabled = true;
    $("pista-punto").textContent =
      "Haga clic dentro de un ambiente para ubicar el punto. El motor valida cada cambio.";
    renderTodo();
  });
}

function conectarFormularioPunto() {
  $("form-punto").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    if (!estado.preview) {
      mostrarEstado("Haga clic en el plano para ubicar el punto.", true);
      return;
    }
    const tipo = $("punto-tipo").value;
    const potencia = Number($("punto-potencia").value);
    if (!Number.isFinite(potencia) || potencia < 0) {
      mostrarEstado("La potencia debe ser un número mayor o igual a cero.", true);
      return;
    }
    const id = siguienteId("P", estado.proyecto.points || []);
    const argumentos = {
      id,
      type: tipo,
      room: estado.preview.room,
      position: [redondear(estado.preview.x), redondear(estado.preview.y)],
      power: potencia,
      height: ALTURAS[tipo] ?? 1.1,
    };
    const exito = await enviarHerramienta(
      "place_point",
      argumentos,
      `Punto ${id} agregado.`
    );
    if (exito) {
      estado.preview = null;
      $("btn-punto").disabled = true;
      $("pista-punto").textContent =
        "Haga clic dentro de un ambiente para ubicar el punto. El motor valida cada cambio.";
    }
  });
}

function conectarAcciones() {
  $("btn-abrir").addEventListener("click", () => $("archivo-proyecto").click());

  $("archivo-proyecto").addEventListener("change", async (evento) => {
    const archivo = evento.target.files && evento.target.files[0];
    if (!archivo) {
      return;
    }
    try {
      const proyecto = JSON.parse(await archivo.text());
      const datos = await pedir("/api/proyecto", {
        method: "POST",
        body: JSON.stringify({ proyecto }),
      });
      estado.preview = null;
      aplicarEstado(datos);
      mostrarEstado(`Proyecto ${archivo.name} cargado.`);
    } catch (error) {
      mostrarEstado(`No se pudo abrir: ${error.message}`, true);
    } finally {
      evento.target.value = "";
    }
  });

  $("btn-validar").addEventListener("click", async () => {
    try {
      const validacion = await pedir("/api/validar", { method: "POST" });
      aplicarEstado({ validacion });
      mostrarEstado("Validación actualizada.");
    } catch (error) {
      mostrarEstado(error.message, true);
    }
  });

  $("btn-deshacer").addEventListener("click", async () => {
    if (estado.ocupado) {
      return;
    }
    estado.ocupado = true;
    try {
      const datos = await pedir("/api/deshacer", {
        method: "POST",
        body: JSON.stringify({ n: 1 }),
      });
      estado.preview = null;
      $("btn-punto").disabled = true;
      aplicarEstado(datos);
      mostrarEstado("Último cambio deshecho.");
    } catch (error) {
      mostrarEstado(error.message, true);
    } finally {
      estado.ocupado = false;
    }
  });

  $("btn-exportar").addEventListener("click", async () => {
    const boton = $("btn-exportar");
    if (estado.ocupado) {
      return;
    }
    estado.ocupado = true;
    boton.disabled = true;
    try {
      const datos = await pedir("/api/exportar", { method: "POST" });
      contenedorArchivos(datos.archivos);
      if (datos.archivos && datos.archivos.svg) {
        const vista = $("unifilar");
        vista.src = `${datos.archivos.svg}?t=${Date.now()}`;
        vista.hidden = false;
        $("unifilar-vacio").hidden = true;
      }
      if ((datos.errores || []).length > 0) {
        mostrarEstado(
          `Exportado con ${datos.errores.length} error(es) de cumplimiento.`,
          true
        );
      } else {
        mostrarEstado("Archivos exportados.");
      }
    } catch (error) {
      mostrarEstado(error.message, true);
    } finally {
      estado.ocupado = false;
      boton.disabled = false;
    }
  });
}

function contenedorArchivos(archivos) {
  const contenedor = $("archivos");
  contenedor.replaceChildren();
  for (const [clave, url] of Object.entries(archivos || {})) {
    const enlace = document.createElement("a");
    enlace.href = url;
    enlace.target = "_blank";
    enlace.rel = "noopener";
    enlace.className = "boton";
    enlace.textContent = ETIQUETAS_ARCHIVO[clave] || clave;
    contenedor.append(enlace);
  }
}

function agregarMensaje(texto, clase) {
  const mensaje = document.createElement("div");
  mensaje.className = `mensaje ${clase}`;
  mensaje.textContent = texto;
  $("mensajes").append(mensaje);
  $("mensajes").scrollTop = $("mensajes").scrollHeight;
  return mensaje;
}

function quitarPendiente() {
  const pendiente = $("mensajes").querySelector("[data-pendiente]");
  if (pendiente) {
    pendiente.remove();
  }
}

function conectarChat() {
  $("form-chat").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const campo = $("chat-texto");
    const texto = campo.value.trim();
    if (!texto || estado.ocupado) {
      return;
    }
    agregarMensaje(texto, "usuario");
    campo.value = "";
    estado.ocupado = true;
    $("btn-enviar").disabled = true;
    const pendiente = agregarMensaje("El asistente está trabajando…", "estado");
    pendiente.dataset.pendiente = "1";
    try {
      const datos = await pedir("/api/chat", {
        method: "POST",
        body: JSON.stringify({ mensaje: texto }),
      });
      quitarPendiente();
      agregarMensaje(datos.respuesta || "(sin respuesta)", "asistente");
      aplicarEstado(datos);
      $("chat-aviso").textContent = "";
    } catch (error) {
      quitarPendiente();
      agregarMensaje(`No se pudo completar: ${error.message}`, "estado");
      if (error.message.includes("CADBIM_LLM_KEY")) {
        $("chat-aviso").textContent =
          "El chat necesita CADBIM_LLM_KEY en el entorno del servidor; el editor y la validación funcionan sin clave.";
      }
    } finally {
      estado.ocupado = false;
      $("btn-enviar").disabled = false;
    }
  });
}

async function iniciar() {
  conectarPlano();
  conectarFormularioPunto();
  conectarAcciones();
  conectarChat();
  try {
    const datos = await pedir("/api/estado");
    aplicarEstado(datos);
  } catch (error) {
    mostrarEstado(`No se pudo cargar el proyecto: ${error.message}`, true);
  }
}

iniciar();
