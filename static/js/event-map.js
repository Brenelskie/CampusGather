(() => {
  "use strict";
  const container = document.getElementById("event-map");
  const dataElement = document.getElementById("event-map-data");
  const feedback = document.getElementById("map-feedback");
  if (!container || !dataElement) return;

  function unavailable() {
    container.classList.add("map-unavailable");
    const message = document.createElement("p");
    message.textContent = "Map unavailable. The venue address and coordinates are listed above.";
    container.replaceChildren(message);
    if (feedback) feedback.textContent = "The map could not load. You can still use the event information and registration links.";
  }

  try {
    if (typeof window.L === "undefined") {
      unavailable();
      return;
    }
    const data = JSON.parse(dataElement.textContent);
    const latitude = Number(data.latitude);
    const longitude = Number(data.longitude);
    if (data.latitude === null || data.longitude === null || data.latitude === "" || data.longitude === "" || !Number.isFinite(latitude) || !Number.isFinite(longitude) || latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) {
      unavailable();
      return;
    }
    const map = window.L.map(container, { scrollWheelZoom: false }).setView([latitude, longitude], 16);
    const tiles = window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    const popup = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = String(data.name || "Event venue");
    const address = document.createElement("p");
    address.textContent = String(data.address || "");
    popup.append(title, address);
    window.L.marker([latitude, longitude], { title: String(data.name || "Event venue"), alt: "Event venue location" }).addTo(map).bindPopup(popup);
    if (feedback) feedback.textContent = "The pin marks the saved venue location. Use the + and − controls to zoom, or the address and coordinates above.";
    let tileFailure = false;
    tiles.on("tileerror", () => {
      tileFailure = true;
      if (feedback) feedback.textContent = "Some map tiles could not load. The pin still marks the saved coordinates; use the venue address above if needed.";
    });
    tiles.on("load", () => {
      if (!tileFailure && feedback) feedback.textContent = "The pin marks the saved venue location. Use the + and − controls to zoom, or the address and coordinates above.";
    });
  } catch (_error) {
    unavailable();
  }
})();
