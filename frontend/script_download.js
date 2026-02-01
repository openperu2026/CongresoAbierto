// script_download.js

console.log("script_download.js loaded ✅");

// ---------- helpers ----------
function objectsToCSV(rows) {
  if (!Array.isArray(rows) || rows.length === 0) return "";

  const headers = Array.from(
    rows.reduce((set, row) => {
      Object.keys(row || {}).forEach(k => set.add(k));
      return set;
    }, new Set())
  );

  const escapeCSV = (value) => {
    if (value === null || value === undefined) return "";
    const str = String(value);
    const escaped = str.replace(/"/g, '""');
    return /[",\n]/.test(escaped) ? `"${escaped}"` : escaped;
  };

  const lines = [];
  lines.push(headers.join(","));
  rows.forEach(row => {
    lines.push(headers.map(h => escapeCSV(row?.[h])).join(","));
  });

  return lines.join("\n");
}

function downloadTextFile(text, filename, mime = "text/csv;charset=utf-8") {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();

  URL.revokeObjectURL(url);
}

async function downloadSeatsAsCSV(
  jsonUrl = "/data/seats.json",
  filename = "seats.csv"
) {
  const res = await fetch(jsonUrl);
  if (!res.ok) {
    throw new Error(`Failed to fetch ${jsonUrl}`);
  }

  const data = await res.json();
  const csv = objectsToCSV(data);
  downloadTextFile(csv, filename);
}

// ---------- BUTTON BINDING ----------
document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("download-csv");

  if (!btn) {
    console.warn("Download button not found");
    return;
  }

  btn.addEventListener("click", async () => {
    try {
      await downloadSeatsAsCSV("/data/seats.json", "seats.csv");
    } catch (err) {
      console.error("CSV download failed ❌", err);
      alert("No se pudo descargar el archivo CSV");
    }
  });
});
