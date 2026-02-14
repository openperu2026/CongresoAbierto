// script_table.js

function normalizeText(s) {
  return (s ?? "")
    .toUpperCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function unpackSeatsPayload(data) {
  if (Array.isArray(data)) return { seats: data, fecha: null };
  if (data && Array.isArray(data.resultados)) {
    return { seats: data.resultados, fecha: data.fecha ?? null };
  }
  return { seats: [], fecha: null };
}

fetch("/data/seats.json")
  .then(r => r.json())
  .then(data => {
    const { seats } = unpackSeatsPayload(data);
    const tableData = buildTableData(seats);
    renderTable(tableData);
  })
  .catch(err => console.error("Table fetch error ?", err));

function buildTableData(seats) {
  const map = new Map();

  seats.forEach(d => {
    const bancada = normalizeText(d.bancada);
    const voto = d.votacion;

    if (!map.has(bancada)) {
      map.set(bancada, { bancada, SI: 0, NO: 0, OTROS: 0, TOTAL: 0 });
    }

    const row = map.get(bancada);
    row.TOTAL += 1;

    if (voto === "SI") row.SI += 1;
    else if (voto === "NO") row.NO += 1;
    else row.OTROS += 1;
  });

  // 1) construir rows
  const rows = Array.from(map.values()).map(d => ({
    bancada: d.bancada,
    SI: d.SI,
    NO: d.NO,
    OTROS: d.OTROS,
    TOTAL: d.TOTAL,
    APROBACION: d.TOTAL > 0 ? Math.round((d.SI / d.TOTAL) * 100) : 0
  }));

  // 2) fila total general
  const totalRow = rows.reduce(
    (acc, r) => {
      acc.SI += r.SI;
      acc.NO += r.NO;
      acc.OTROS += r.OTROS;
      acc.TOTAL += r.TOTAL;
      return acc;
    },
    { bancada: "TOTAL", SI: 0, NO: 0, OTROS: 0, TOTAL: 0, APROBACION: 0 }
  );

  totalRow.APROBACION = totalRow.TOTAL > 0
    ? Math.round((totalRow.SI / totalRow.TOTAL) * 100)
    : 0;

  // 3) ordenar y agregar TOTAL al final
  rows.sort((a, b) =>
    a.bancada.localeCompare(b.bancada, "es", { sensitivity: "base" })
  );
  rows.push(totalRow);

  return rows;
}






function renderTable(rows) {
  const tbody = document.querySelector("#bancada-table tbody");
  tbody.innerHTML = "";

  rows.forEach(d => {
    const tr = document.createElement("tr");

    if (d.bancada === "TOTAL") {
      tr.classList.add("total-row");
    }

    tr.innerHTML = `
      <td>${d.bancada}</td>
      <td>${d.SI}</td>
      <td>${d.NO}</td>
      <td>${d.OTROS}</td>
      <td>${d.APROBACION}%</td>
    `;

    tbody.appendChild(tr);
  });
}
