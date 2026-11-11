(() => {
  "use strict";
  const container = document.getElementById("venue-map");
  const latitudeInput = document.getElementById("id_latitude");
  const longitudeInput = document.getElementById("id_longitude");
  const feedback = document.getElementById("map-feedback");
  if (!container || !latitudeInput || !longitudeInput) return;

  function unavailable() {
    container.classList.add("map-unavailable");
    const message = document.createElement("p");
    message.textContent = "Map unavailable. Enter the venue address, latitude, and longitude in the form.";
    container.replaceChildren(message);
    if (feedback) feedback.textContent = "You can still save the venue using the coordinate fields. Both latitude and longitude are required.";
  }

  function coordinatesFromInputs() {
    if (!latitudeInput.value.trim() || !longitudeInput.value.trim()) return null;
    const latitude = Number(latitudeInput.value);
    const longitude = Number(longitudeInput.value);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return null;
    return [latitude, longitude];
  }

  try {
    if (typeof window.L === "undefined") {
      unavailable();
      return;
    }
    const saved = coordinatesFromInputs();
    const map = window.L.map(container, { scrollWheelZoom: false }).setView(saved || [12.8797, 121.774], saved ? 16 : 5);
    const tiles = window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    let marker = null;
    let tileFailure = false;

    function reportSelection(latitude, longitude) {
      if (!feedback) return;
      const suffix = tileFailure ? " Map tiles are unavailable; the coordinate fields still work." : " Drag the pin, click the map, or type coordinates to change it.";
      feedback.textContent = `Selected: ${latitude.toFixed(6)}, ${longitude.toFixed(6)}.${suffix} Save the form to keep this location.`;
    }

    function placeMarker(coordinates) {
      if (marker) {
        marker.setLatLng(coordinates);
      } else {
        marker = window.L.marker(coordinates, { draggable: true, autoPan: true, title: "Venue location; drag to move", alt: "Selected venue location" }).addTo(map);
        marker.on("dragend", () => updateInputs(marker.getLatLng()));
      }
    }

    function updateInputs(location) {
      latitudeInput.value = location.lat.toFixed(6);
      longitudeInput.value = location.lng.toFixed(6);
      latitudeInput.dispatchEvent(new Event("change", { bubbles: true }));
      longitudeInput.dispatchEvent(new Event("change", { bubbles: true }));
      placeMarker([location.lat, location.lng]);
      reportSelection(location.lat, location.lng);
    }

    function updateFromInputs() {
      const coordinates = coordinatesFromInputs();
      if (!coordinates) {
        if (marker) {
          map.removeLayer(marker);
          marker = null;
        }
        if (feedback) feedback.textContent = "Enter both valid coordinates, or click the map to choose a location. Latitude must be −90 to 90 and longitude −180 to 180.";
        return;
      }
      placeMarker(coordinates);
      map.panTo(coordinates);
      reportSelection(coordinates[0], coordinates[1]);
    }

    if (saved) {
      placeMarker(saved);
      reportSelection(saved[0], saved[1]);
    } else if (feedback) {
      feedback.textContent = "Click the map to choose a venue location, or enter both coordinate fields. No location has been selected yet.";
    }
    map.on("click", (event) => updateInputs(event.latlng));
    latitudeInput.addEventListener("input", updateFromInputs);
    longitudeInput.addEventListener("input", updateFromInputs);
    tiles.on("tileerror", () => {
      tileFailure = true;
      const selected = coordinatesFromInputs();
      if (selected) reportSelection(selected[0], selected[1]);
      else if (feedback) feedback.textContent = "Map tiles could not load. Enter the address, latitude, and longitude directly; the form still works.";
    });
  } catch (_error) {
    unavailable();
  }
})();
