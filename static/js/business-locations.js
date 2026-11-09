document.addEventListener("DOMContentLoaded", () => {
  const mapElement = document.querySelector("#business-sites-map");
  if (!mapElement) return;

  if (!window.L) {
    mapElement.textContent = "The map could not load. You can still enter coordinates below.";
    return;
  }

  const latitudeInput = document.querySelector("#id_latitude");
  const longitudeInput = document.querySelector("#id_longitude");
  const editable = Boolean(latitudeInput && longitudeInput);
  const siteMarkers = [...document.querySelectorAll("[data-site-marker]")];
  const savedPoints = siteMarkers
    .map(site => [Number(site.dataset.latitude), Number(site.dataset.longitude)])
    .filter(([latitude, longitude]) =>
      Number.isFinite(latitude) && Number.isFinite(longitude)
    );
  const map = L.map(mapElement).setView([-1.286389, 36.817223], 6);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  const savedMarkers = new Map();
  for (const site of siteMarkers) {
    const latitude = Number(site.dataset.latitude);
    const longitude = Number(site.dataset.longitude);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) continue;

    const popup = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = site.dataset.name || "Business site";
    const area = document.createElement("div");
    area.textContent = site.dataset.area || "";
    popup.append(name, area);
    const marker = L.marker([latitude, longitude]).addTo(map).bindPopup(popup);
    savedMarkers.set(site.dataset.siteId, marker);
  }

  if (savedPoints.length === 1) {
    map.setView(savedPoints[0], 12);
  } else if (savedPoints.length > 1) {
    map.fitBounds(L.latLngBounds(savedPoints), { padding: [28, 28], maxZoom: 12 });
  }
  for (const button of document.querySelectorAll("[data-location-focus]")) {
    button.addEventListener("click", () => {
      const marker = savedMarkers.get(button.dataset.locationFocus);
      if (!marker) return;
      map.setView(marker.getLatLng(), 14);
      marker.openPopup();
    });
  }
  document.querySelector("[data-map-fit-sites]")?.addEventListener("click", () => {
    if (savedPoints.length === 1) map.setView(savedPoints[0], 12);
    if (savedPoints.length > 1) {
      map.fitBounds(L.latLngBounds(savedPoints), { padding: [28, 28], maxZoom: 12 });
    }
  });
  document.querySelector("[data-map-focus-kenya]")?.addEventListener("click", () => {
    map.setView([-1.286389, 36.817223], 6);
  });

  if (!editable) return;

  let selectedMarker = null;
  const updateCoordinateInputs = coordinates => {
    latitudeInput.value = coordinates.lat.toFixed(6);
    longitudeInput.value = coordinates.lng.toFixed(6);
  };
  const setSelectedPoint = (latitude, longitude, pan = false) => {
    const point = [latitude, longitude];
    if (!selectedMarker) {
      selectedMarker = L.marker(point, { draggable: true }).addTo(map);
      selectedMarker.on("dragend", event => {
        const coordinates = event.target.getLatLng();
        updateCoordinateInputs(coordinates);
      });
    } else {
      selectedMarker.setLatLng(point);
    }
    updateCoordinateInputs({ lat: latitude, lng: longitude });
    if (pan) map.panTo(point);
  };

  map.on("click", event => setSelectedPoint(event.latlng.lat, event.latlng.lng));

  const initialLatitude = Number(latitudeInput.value);
  const initialLongitude = Number(longitudeInput.value);
  if (
    latitudeInput.value
    && longitudeInput.value
    && Number.isFinite(initialLatitude)
    && Number.isFinite(initialLongitude)
  ) {
    setSelectedPoint(initialLatitude, initialLongitude, true);
    map.setZoom(13);
  }

  const updateFromInputs = () => {
    if (!latitudeInput.value || !longitudeInput.value) return;
    const latitude = Number(latitudeInput.value);
    const longitude = Number(longitudeInput.value);
    if (
      Number.isFinite(latitude)
      && Number.isFinite(longitude)
      && Math.abs(latitude) <= 90
      && Math.abs(longitude) <= 180
    ) {
      setSelectedPoint(latitude, longitude);
    }
  };
  latitudeInput.addEventListener("change", updateFromInputs);
  longitudeInput.addEventListener("change", updateFromInputs);
  window.setTimeout(() => map.invalidateSize(), 0);
});
