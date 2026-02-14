console.log("script.js loaded ✅");
console.log("d3 type:", typeof d3);

const BANCADA_COLORS = {
  "ACCION POPULAR": "#da2f2f",
  "ALIANZA PARA EL PROGRESO": "#1F77B4",
  "AVANZA PAIS - PARTIDO DE INTEGRACION SOCIAL": "#E377C2",
  "BANCADA SOCIALISTA": "#B2182B",
  "BLOQUE DEMOCRATICO POPULAR": "#66C2A5",
  "BLOQUE MAGISTERIAL DE CONCERTACION NACIONAL": "#E6D690",
  "FUERZA POPULAR": "#FF7F0E",
  "HONOR Y DEMOCRACIA": "#4682B4",
  "JUNTOS POR EL PERU - VOCES DEL PUEBLO": "#A6D854",
  "PERU LIBRE": "#D62728",
  "PODEMOS PERU": "#003F5C",
  "RENOVACION POPULAR": "#76B7B2",
  "SOMOS PERU": "#2C7FB8",
  "NO AGRUPADO": "#000000"
  
};

// --- helper: normalize text like your Python function, but in JS ---
function normalizeText(s) {
  return (s ?? "")
    .toUpperCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

const svg = d3.select("#chart");
const width = +svg.attr("width");
const height = +svg.attr("height");

const cx = width / 2;
const cy = height - 30;

const seatRadius = 6;
const rows = 6;
const gray = "#D0D0D0";




const tooltip = d3.select("body")
  .append("div")
  .attr("class", "tooltip");




function getField(data, name) {
  if (!data || typeof data !== "object") return null;
  if (Object.prototype.hasOwnProperty.call(data, name)) return data[name];
  const key = Object.keys(data).find(
    k => k.trim().toLowerCase() === name
  );
  return key ? data[key] : null;
}

function unpackSeatsForChart(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.resultados)) return data.resultados;
  if (Array.isArray(data?.seats)) return data.seats;
  if (Array.isArray(data?.data)) return data.data;
  if (Array.isArray(data?.resultados?.data)) return data.resultados.data;
  return [];
}


fetch("/data/seats.json")
  .then(res => {
    console.log("fetch status:", res.status);
    return res.json();
  })
  .then(data => {
    const seats = unpackSeatsForChart(data);
    console.log("seats loaded:", seats.length);
    if (!Array.isArray(seats)) {
      console.error("seats is not an array:", seats);
      return;
    }
    drawHemicycle(seats);
    console.log("circles drawn:", document.querySelectorAll("#chart circle").length);
  })
  .catch(err => console.error("fetch error ?", err));

function getSeatColor(d) {
  const baseColor = BANCADA_COLORS[d.bancada_norm] ?? "#999999";
  if (d.votacion === "SI") return baseColor;
  return d3.color(baseColor).copy({ opacity: 0.1 });
}

function drawHemicycle(seats) {
  seats.forEach(d => {
    d.bancada_norm = normalizeText(d.bancada);
  });

  seats.sort((a, b) => {
    const A = a.bancada_norm ?? "";
    const B = b.bancada_norm ?? "";
    return A.localeCompare(B, "es", { sensitivity: "base" });
  });

  const totalSeats = seats.length;
  const seatsPerCol = rows; // vertical stack
  const numCols = Math.ceil(totalSeats / seatsPerCol);
  const maxRadius = 170;

  const angleScale = d3.scaleLinear()
    .domain([0, numCols - 1])
    .range([-Math.PI, 0]);

  seats.forEach((d, i) => {
    const idx = Math.floor(i / seatsPerCol); // column -> angle
    const row = i % seatsPerCol;             // row -> radius (vertical)

    const angle = angleScale(idx);
    const r = maxRadius - row * (seatRadius * 2.25);

    d.x = cx + r * Math.cos(angle);
    d.y = cy + r * Math.sin(angle);
  });




    // ---- LEGEND ----

  // get unique bancadas in the data (already normalized)
  const bancadasUnicas = Array.from(
    new Set(seats.map(d => d.bancada_norm))
  );

  // alphabetical legend (matches your layout)
  bancadasUnicas.sort((a, b) =>
    a.localeCompare(b, "es", { sensitivity: "base" })
  );

  const legend = d3.select("#legend");
  legend.selectAll("*").remove(); // clear previous legend

  const legendItems = legend.selectAll(".legend-item")
    .data(bancadasUnicas)
    .join("div")
    .attr("class", "legend-item");

  legendItems.append("span")
    .attr("class", "legend-swatch")
    .style("background-color", d => BANCADA_COLORS[d] ?? "#999");

  legendItems.append("span")
    .text(d => d);


  svg.selectAll("circle")
  .data(seats, d => d.id)
  .join("circle")
  .attr("class", "seat")
  .attr("cx", d => d.x)
  .attr("cy", d => d.y)
  .attr("r", seatRadius)
  .attr("fill", d => getSeatColor(d))
  .on("mouseover", (event, d) => {
    tooltip
      .style("opacity", 1)
      .html(`
        <div><strong>${d.nombre_completo ?? ""}</strong></div>
        <div>Bancada: ${d.bancada ?? ""}</div>
        <div>Voto: <strong>${d.votacion ?? ""}</strong></div>
      `);
  })
  .on("mousemove", (event) => {
    tooltip
      .style("left", (event.pageX + 12) + "px")
      .style("top", (event.pageY - 12) + "px");
  })
  .on("mouseout", () => {
    tooltip.style("opacity", 0);
  });
}
