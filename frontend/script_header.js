// script_header.js

function normalizeText(s) {
  return (s ?? "")
    .toUpperCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function extractAsuntoTitle(rawTitle) {
  const normalized = normalizeText(rawTitle);
  if (!normalized) return "";

  const start = normalized.indexOf("ASUNTO");
  if (start === -1) return normalized;

  const afterAsunto = normalized.slice(start + "ASUNTO".length).trim();
  const end = afterAsunto.indexOf("APP");
  if (end === -1) return afterAsunto.trim();

  return afterAsunto.slice(0, end).trim();
}

function unpackHeaderPayload(data) {
  if (Array.isArray(data)) return { fecha: null, titulo: null };
  return {
    fecha: data?.fecha ?? null,
    titulo: data?.titulo ?? null,
    evento: data?.evento ?? null
  };
}

window.fetchSeatsData()
  .then(data => {
    const { fecha, titulo, evento } = unpackHeaderPayload(data);
    const asuntoTitulo = extractAsuntoTitle(titulo);

    const fechaEl = document.getElementById("fecha");
    if (fechaEl) {
      fechaEl.textContent = fecha ?? "";
    }

    const tituloEl = document.getElementById("titulo");
    if (tituloEl) {
      tituloEl.textContent = asuntoTitulo ?? "";
    }

    const eventoEl = document.getElementById("evento");
    if (eventoEl) {
      eventoEl.textContent = evento ?? "";
    }
  })
  .catch(err => console.error("Header fetch error ?", err));
