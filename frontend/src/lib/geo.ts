// src/lib/geo.ts
export type Fix = { latitude: number; longitude: number; accuracy: number };

export function getPosition(): Promise<Fix> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation)
      return reject({ code: "GPS_UNAVAILABLE", message: "This device cannot provide a location." });
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude, accuracy: p.coords.accuracy }),
      (err) =>
        reject(
          err.code === err.PERMISSION_DENIED
            ? { code: "LOCATION_REQUIRED", message: "Location access is required to mark attendance." }
            : { code: "GPS_UNAVAILABLE", message: "GPS is unavailable. Turn on Location and try again." }
        ),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 } // maximumAge 0 = no cached fix
    );
  });
}