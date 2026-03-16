async function fetchSeatsData() {
  const candidates = [
    window.SEATS_DATA_URL,
    "./data/seats.json",
    "data/seats.json",
    "/data/seats.json",
  ].filter(Boolean);

  let lastError = null;

  for (const url of [...new Set(candidates)]) {
    try {
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status} for ${url}`);
      }
      return await res.json();
    } catch (err) {
      lastError = err;
      console.warn("Seats fetch failed:", url, err);
    }
  }

  throw lastError || new Error("Could not load seats data");
}

window.fetchSeatsData = fetchSeatsData;
