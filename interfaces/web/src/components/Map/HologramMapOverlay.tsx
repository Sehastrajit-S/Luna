import { useEffect, useRef, useState, useCallback } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { LocateFixed, MapPin, X, Search, Navigation, Clock, Route, Pencil, Check } from 'lucide-react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useStore } from '../../store'

type GeoState =
  | { status: 'loading' }
  | { status: 'ready'; lat: number; lon: number; accuracy: number | null }
  | { status: 'blocked'; message: string }

interface PlaceResult {
  place_id: number
  display_name: string
  lat: string
  lon: string
  type: string
  category: string
}

interface RouteInfo {
  distance: number   // metres
  duration: number   // seconds
  geometry: GeoJSON.LineString
}

function formatCoord(value: number, axis: 'lat' | 'lon') {
  const dir = axis === 'lat' ? (value >= 0 ? 'N' : 'S') : (value >= 0 ? 'E' : 'W')
  return `${Math.abs(value).toFixed(4)} ${dir}`
}

function formatDistance(m: number) {
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`
}

function formatDuration(s: number) {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m} min`
}

const PULSE_CSS = `
  @keyframes lunaMarkerPulse {
    0%   { transform: translate(-50%,-50%) scale(0.5); opacity: 0.9; }
    100% { transform: translate(-50%,-50%) scale(2.8); opacity: 0; }
  }
  .luna-marker-ring {
    position: absolute; top: 50%; left: 50%;
    width: 36px; height: 36px;
    border-radius: 50%;
    border: 2px solid rgba(34,211,238,0.75);
    animation: lunaMarkerPulse 2.2s ease-out infinite;
  }
  .luna-marker-dot {
    position: absolute; top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    width: 14px; height: 14px;
    border-radius: 50%;
    background: rgba(34,211,238,1);
    border: 2.5px solid #fff;
    box-shadow: 0 0 18px rgba(34,211,238,0.95), 0 0 44px rgba(34,211,238,0.4);
    z-index: 2;
  }
  .luna-dest-dot {
    position: absolute; top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    width: 14px; height: 14px;
    border-radius: 50%;
    background: rgba(251,146,60,1);
    border: 2.5px solid #fff;
    box-shadow: 0 0 18px rgba(251,146,60,0.95), 0 0 44px rgba(251,146,60,0.4);
    z-index: 2;
  }
  @keyframes lunaDropIn {
    0%   { transform: translateY(-32px) scaleY(0.6); opacity: 0; }
    70%  { transform: translateY(4px)   scaleY(1.1); opacity: 1; }
    100% { transform: translateY(0)     scaleY(1);   opacity: 1; }
  }
  .luna-result-wrap {
    animation: lunaDropIn 0.38s cubic-bezier(0.34,1.56,0.64,1) both;
  }
  .luna-result-pin {
    position: absolute;
    left: 50%;
    top: 0;
    transform: translateX(-50%) rotate(-45deg);
    transform-origin: center center;
    width: 18px; height: 18px;
    border-radius: 50% 50% 50% 0;
    background: rgba(250,204,21,1);
    border: 2.5px solid #fff;
    box-shadow: 0 0 14px rgba(250,204,21,0.9), 0 0 30px rgba(250,204,21,0.4);
    z-index: 2;
    transition: transform 0.15s;
  }
  .luna-result-wrap:hover .luna-result-pin {
    transform: translateX(-50%) rotate(-45deg) scale(1.2);
  }
  .luna-result-label {
    position: absolute;
    top: calc(100% + 4px);
    left: 50%;
    transform: translateX(-50%);
    white-space: nowrap;
    background: rgba(0,0,0,0.78);
    color: rgba(254,240,138,0.95);
    font-size: 10px;
    padding: 2px 7px;
    border-radius: 4px;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.15s;
    border: 1px solid rgba(250,204,21,0.3);
  }
  .luna-result-wrap:hover .luna-result-label { opacity: 1; }
  .maplibregl-ctrl-attrib,
  .maplibregl-ctrl-logo { display: none !important; }
`

const ROUTE_SOURCE = 'luna-route'
const ROUTE_LAYER  = 'luna-route-line'

export function HologramMapOverlay() {
  const { mapOverlayOpen, closeMapOverlay, mapPendingSearch, mapPendingRoute, setMapPendingSearch, setMapPendingRoute } = useStore()
  const [geo, setGeo]                     = useState<GeoState>({ status: 'loading' })
  const [query, setQuery]                 = useState('')
  const [results, setResults]             = useState<PlaceResult[]>([])
  const [searching, setSearching]         = useState(false)
  const [destination, setDestination]     = useState<{ lat: number; lon: number; name: string } | null>(null)
  const [route, setRoute]                 = useState<RouteInfo | null>(null)
  const [routeLoading, setRouteLoading]   = useState(false)

  const [locEditing, setLocEditing] = useState(false)
  const [locInput, setLocInput]     = useState('')
  const [locLoading, setLocLoading] = useState(false)

  const mapContainerRef      = useRef<HTMLDivElement>(null)
  const mapRef               = useRef<maplibregl.Map | null>(null)
  const destMarkerRef        = useRef<maplibregl.Marker | null>(null)
  const resultMarkersRef     = useRef<maplibregl.Marker[]>([])
  const searchTimerRef       = useRef<ReturnType<typeof setTimeout> | null>(null)
  const locInputRef          = useRef<HTMLInputElement>(null)
  const selectPlaceRef       = useRef<(place: PlaceResult) => void>(() => {})

  // â”€â”€ keyboard close â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  useEffect(() => {
    if (!mapOverlayOpen) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') closeMapOverlay() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [mapOverlayOpen, closeMapOverlay])

  // â”€â”€ reset on open â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  useEffect(() => {
    if (!mapOverlayOpen) {
      setQuery(''); setResults([]); setDestination(null); setRoute(null)
      setLocEditing(false); setLocInput('')
      clearResultMarkers()
      return
    }
    setGeo({ status: 'loading' })

    // Pinned location takes priority over auto-detect
    try {
      const saved = localStorage.getItem('luna_map_location')
      if (saved) {
        const { lat, lon } = JSON.parse(saved)
        if (typeof lat === 'number' && typeof lon === 'number') {
          setGeo({ status: 'ready', lat, lon, accuracy: null })
          return
        }
      }
    } catch {}

    const applyPos = (lat: number, lon: number, accuracy: number | null) =>
      setGeo({ status: 'ready', lat, lon, accuracy })

    const api = (window as any).electronAPI

    // Electron cannot use browser geolocation reliably, so it asks the shell for
    // approximate IP-based location and lets users pin a more accurate location.
    if (api?.getLocation) {
      api.getLocation()
        .then((r: { lat: number | null; lon: number | null; accuracy: number | null }) => {
          if (typeof r.lat === 'number' && typeof r.lon === 'number') {
            applyPos(r.lat, r.lon, r.accuracy)
          } else {
            setGeo({ status: 'blocked', message: 'location unavailable' })
          }
        })
        .catch(() => setGeo({ status: 'blocked', message: 'location unavailable' }))
      return
    }

    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        pos => applyPos(pos.coords.latitude, pos.coords.longitude,
          Number.isFinite(pos.coords.accuracy) ? pos.coords.accuracy : null),
        () => setGeo({ status: 'blocked', message: 'location unavailable' }),
        { enableHighAccuracy: true, timeout: 8000, maximumAge: 30000 },
      )
    } else {
      setGeo({ status: 'blocked', message: 'location unavailable' })
    }
  }, [mapOverlayOpen])

  // â”€â”€ init map â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  useEffect(() => {
    if (!mapOverlayOpen || !mapContainerRef.current) return

    const styleEl = document.createElement('style')
    styleEl.textContent = PULSE_CSS
    document.head.appendChild(styleEl)

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: 'Â© OpenStreetMap contributors',
          },
        },
        layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
      },
      center: [-98.5795, 39.8283],
      zoom: 3,
    })

    map.on('load', () => {
      map.addSource(ROUTE_SOURCE, { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [] }, properties: {} } })
      map.addLayer({
        id: ROUTE_LAYER,
        type: 'line',
        source: ROUTE_SOURCE,
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': 'rgba(251,146,60,0.9)', 'line-width': 4, 'line-blur': 1 },
      })
    })

    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
      document.head.removeChild(styleEl)
    }
  }, [mapOverlayOpen])

  // â”€â”€ fly to user location + user marker â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  useEffect(() => {
    if (geo.status !== 'ready' || !mapRef.current) return
    const map = mapRef.current

    const el = document.createElement('div')
    el.style.cssText = 'position:relative;width:36px;height:36px;'
    el.innerHTML = `<div class="luna-marker-ring"></div><div class="luna-marker-dot"></div>`

    const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
      .setLngLat([geo.lon, geo.lat])
      .addTo(map)

    const doFly = () =>
      map.flyTo({ center: [geo.lon, geo.lat], zoom: 13.5, duration: 2000, essential: true })

    if (map.loaded()) doFly()
    else map.once('load', doFly)

    return () => { marker.remove() }
  }, [geo])

  // â”€â”€ place destination marker + draw route â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  useEffect(() => {
    if (!mapRef.current) return
    const map = mapRef.current

    // Remove old dest marker
    if (destMarkerRef.current) { destMarkerRef.current.remove(); destMarkerRef.current = null }

    if (!destination) {
      // Clear route
      if (map.getSource(ROUTE_SOURCE)) {
        (map.getSource(ROUTE_SOURCE) as maplibregl.GeoJSONSource).setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: [] }, properties: {} })
      }
      return
    }

    const el = document.createElement('div')
    el.style.cssText = 'position:relative;width:36px;height:36px;'
    el.innerHTML = `<div class="luna-dest-dot"></div>`
    destMarkerRef.current = new maplibregl.Marker({ element: el, anchor: 'center' })
      .setLngLat([destination.lon, destination.lat])
      .addTo(map)

    map.flyTo({ center: [destination.lon, destination.lat], zoom: 13, duration: 1800, essential: true })
  }, [destination])

  // â”€â”€ draw route geometry on map â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  useEffect(() => {
    if (!mapRef.current || !route) return
    const map = mapRef.current
    const setData = () => {
      if (map.getSource(ROUTE_SOURCE)) {
        (map.getSource(ROUTE_SOURCE) as maplibregl.GeoJSONSource).setData({
          type: 'Feature', geometry: route.geometry, properties: {},
        })
        // Fit bounds to route
        const coords = route.geometry.coordinates as [number, number][]
        if (coords.length > 1) {
          const bounds = coords.reduce(
            (b, c) => b.extend(c as maplibregl.LngLatLike),
            new maplibregl.LngLatBounds(coords[0], coords[0]),
          )
          map.fitBounds(bounds, { padding: 80, duration: 1800 })
        }
      }
    }
    if (map.loaded()) setData()
    else map.once('load', setData)
  }, [route])

  // â”€â”€ OSM tag map for category POI searches â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const OSM_CATEGORY: Record<string, [string, string][]> = {
    'coffee':          [['amenity','cafe']],
    'coffee shop':     [['amenity','cafe']],
    'coffee shops':    [['amenity','cafe']],
    'cafe':            [['amenity','cafe']],
    'cafes':           [['amenity','cafe']],
    'restaurant':      [['amenity','restaurant']],
    'restaurants':     [['amenity','restaurant']],
    'food':            [['amenity','restaurant'],['amenity','fast_food']],
    'fast food':       [['amenity','fast_food']],
    'pizza':           [['amenity','restaurant']],
    'burger':          [['amenity','fast_food']],
    'sushi':           [['amenity','restaurant']],
    'bar':             [['amenity','bar']],
    'bars':            [['amenity','bar']],
    'pub':             [['amenity','pub']],
    'gas station':     [['amenity','fuel']],
    'gas stations':    [['amenity','fuel']],
    'gas':             [['amenity','fuel']],
    'fuel':            [['amenity','fuel']],
    'pharmacy':        [['amenity','pharmacy']],
    'pharmacies':      [['amenity','pharmacy']],
    'drugstore':       [['amenity','pharmacy']],
    'hospital':        [['amenity','hospital']],
    'hospitals':       [['amenity','hospital']],
    'clinic':          [['amenity','clinic']],
    'doctor':          [['amenity','doctors']],
    'gym':             [['leisure','fitness_centre']],
    'gyms':            [['leisure','fitness_centre']],
    'fitness':         [['leisure','fitness_centre']],
    'grocery':         [['shop','supermarket'],['shop','grocery']],
    'grocery store':   [['shop','supermarket'],['shop','grocery']],
    'grocery stores':  [['shop','supermarket'],['shop','grocery']],
    'supermarket':     [['shop','supermarket']],
    'convenience':     [['shop','convenience']],
    'convenience store':[['shop','convenience']],
    'bank':            [['amenity','bank']],
    'banks':           [['amenity','bank']],
    'atm':             [['amenity','atm']],
    'post office':     [['amenity','post_office']],
    'library':         [['amenity','library']],
    'park':            [['leisure','park']],
    'parks':           [['leisure','park']],
    'parking':         [['amenity','parking']],
    'hotel':           [['tourism','hotel']],
    'hotels':          [['tourism','hotel']],
    'motel':           [['tourism','motel']],
    'mall':            [['shop','mall']],
    'shopping':        [['shop','mall'],['shop','department_store']],
    'school':          [['amenity','school']],
    'university':      [['amenity','university']],
    'airport':         [['aeroway','aerodrome']],
    'police':          [['amenity','police']],
    'fire station':    [['amenity','fire_station']],
    'laundry':         [['shop','laundry'],['shop','dry_cleaning']],
    'barbershop':      [['shop','hairdresser']],
    'salon':           [['shop','hairdresser'],['shop','beauty']],
    'dentist':         [['amenity','dentist']],
    'dentists':        [['amenity','dentist']],
  }

  // â”€â”€ Search: Overpass for categories, Nominatim for named places â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const searchPlaces = useCallback(async (q: string) => {
    if (!q.trim()) { setResults([]); return }
    setSearching(true)
    try {
      const NEARBY_RE = /\s+(?:near(?:by|\s+me|\s+here)?|close\s+by|around\s+here|in\s+my\s+area)$/i
      const cleanQ = q.replace(NEARBY_RE, '').trim().toLowerCase()

      const tags = OSM_CATEGORY[cleanQ]
      if (tags && geo.status === 'ready') {
        // Overpass: find POIs by type within 3 km
        const tagFilters = tags.map(([k, v]) =>
          `node["${k}"="${v}"](around:3000,${geo.lat},${geo.lon});way["${k}"="${v}"](around:3000,${geo.lat},${geo.lon});`
        ).join('')
        const overpassQ = `[out:json][timeout:12];(${tagFilters});out center 12;`
        const res = await fetch('https://overpass-api.de/api/interpreter', {
          method: 'POST',
          body: overpassQ,
        })
        const data = await res.json()
        const places: PlaceResult[] = (data.elements ?? [])
          .filter((el: any) => el.tags?.name && (el.lat ?? el.center?.lat))
          .map((el: any) => ({
            place_id: el.id,
            display_name: [
              el.tags.name,
              el.tags['addr:street'] ? `${el.tags['addr:housenumber'] ?? ''} ${el.tags['addr:street']}`.trim() : '',
              el.tags['addr:city'] ?? '',
            ].filter(Boolean).join(', '),
            lat: String(el.lat ?? el.center.lat),
            lon: String(el.lon ?? el.center.lon),
            type: tags[0][1],
            category: tags[0][0],
          }))
          .slice(0, 8)
        setResults(places)
        return
      }

      // Nominatim fallback for specific named places / addresses
      const bias = geo.status === 'ready'
        ? `&viewbox=${geo.lon - 0.5},${geo.lat + 0.35},${geo.lon + 0.5},${geo.lat - 0.35}&bounded=0`
        : ''
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(cleanQ)}&format=json&limit=6&addressdetails=1${bias}`,
        { headers: { 'Accept-Language': 'en' } },
      )
      const data: PlaceResult[] = await res.json()
      setResults(data)
    } catch {
      setResults([])
    } finally {
      setSearching(false)
    }
  }, [geo])

  const onQueryChange = (v: string) => {
    setQuery(v)
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    searchTimerRef.current = setTimeout(() => searchPlaces(v), 400)
  }

  const clearResultMarkers = useCallback(() => {
    resultMarkersRef.current.forEach(m => m.remove())
    resultMarkersRef.current = []
  }, [])

  // â”€â”€ OSRM routing â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const fetchRoute = useCallback(async (dest: { lat: number; lon: number }) => {
    if (geo.status !== 'ready') return
    setRouteLoading(true)
    try {
      const url = `https://router.project-osrm.org/route/v1/driving/${geo.lon},${geo.lat};${dest.lon},${dest.lat}?overview=full&geometries=geojson`
      const res  = await fetch(url)
      const data = await res.json()
      const leg  = data.routes?.[0]
      if (leg) {
        setRoute({ distance: leg.distance, duration: leg.duration, geometry: leg.geometry })
      }
    } catch {
      setRoute(null)
    } finally {
      setRouteLoading(false)
    }
  }, [geo])

  const selectPlace = useCallback((place: PlaceResult) => {
    const dest = { lat: parseFloat(place.lat), lon: parseFloat(place.lon), name: place.display_name.split(',')[0] }
    setDestination(dest)
    setQuery(dest.name)
    setResults([])
    fetchRoute(dest)
  }, [fetchRoute])

  // Keep ref in sync so marker click handlers always call the latest version
  useEffect(() => { selectPlaceRef.current = selectPlace }, [selectPlace])

  // â”€â”€ Pin all search results on the map â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  useEffect(() => {
    clearResultMarkers()
    if (!mapRef.current || results.length === 0) return
    const map = mapRef.current

    const placeMarkers = () => {
      clearResultMarkers()
      results.forEach((p, i) => {
        const lat = parseFloat(p.lat)
        const lon = parseFloat(p.lon)
        if (!isFinite(lat) || !isFinite(lon)) return
        const wrap = document.createElement('div')
        wrap.style.cssText = `position:relative;width:24px;height:32px;cursor:pointer;`
        wrap.innerHTML = `
          <div style="position:absolute;left:50%;top:0;transform:translateX(-50%) rotate(-45deg);width:18px;height:18px;border-radius:50% 50% 50% 0;background:#facc15;border:2.5px solid #fff;box-shadow:0 0 14px rgba(250,204,21,0.9),0 0 30px rgba(250,204,21,0.4);z-index:9999;"></div>
          <div style="position:absolute;top:calc(100% + 4px);left:50%;transform:translateX(-50%);white-space:nowrap;background:rgba(0,0,0,0.78);color:rgba(254,240,138,0.95);font-size:10px;padding:2px 7px;border-radius:4px;pointer-events:none;opacity:0;transition:opacity 0.15s;border:1px solid rgba(250,204,21,0.3);">${p.display_name.split(',')[0]}</div>
        `
        wrap.addEventListener('mouseenter', () => { const lbl = wrap.querySelector('div:last-child') as HTMLElement; if (lbl) lbl.style.opacity = '1' })
        wrap.addEventListener('mouseleave', () => { const lbl = wrap.querySelector('div:last-child') as HTMLElement; if (lbl) lbl.style.opacity = '0' })
        wrap.addEventListener('click', () => selectPlaceRef.current(p))
        const marker = new maplibregl.Marker({ element: wrap, anchor: 'bottom' })
          .setLngLat([lon, lat])
          .addTo(map)
        resultMarkersRef.current.push(marker)
      })

      const lnglats = results
        .map(p => [parseFloat(p.lon), parseFloat(p.lat)] as [number, number])
        .filter(([lon, lat]) => isFinite(lon) && isFinite(lat))
      if (lnglats.length === 0) return
      if (lnglats.length === 1) {
        map.flyTo({ center: lnglats[0], zoom: 15, duration: 1400 })
      } else {
        const bounds = lnglats.reduce(
          (b, c) => b.extend(c),
          new maplibregl.LngLatBounds(lnglats[0], lnglats[0]),
        )
        map.fitBounds(bounds, { padding: 80, maxZoom: 15, duration: 1600 })
      }
    }

    placeMarkers()
  }, [results, clearResultMarkers])

  // â”€â”€ voice-triggered search â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  useEffect(() => {
    if (!mapPendingSearch || !mapOverlayOpen) return
    setQuery(mapPendingSearch)
    searchPlaces(mapPendingSearch)
    setMapPendingSearch(null)
  }, [mapPendingSearch, mapOverlayOpen, searchPlaces, setMapPendingSearch])

  // â”€â”€ voice-triggered route â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  useEffect(() => {
    if (!mapPendingRoute || !mapOverlayOpen) return
    const NEARBY_RE = /\s+(?:near(?:by|\s+me|\s+here)?|close\s+by|around\s+here|in\s+my\s+area)$/i
    const rawQ  = mapPendingRoute
    const isNearby = NEARBY_RE.test(rawQ)
    const q     = rawQ.replace(NEARBY_RE, '').trim() || rawQ
    setMapPendingRoute(null)
    setQuery(q)
    setSearching(true)
    const bias = geo.status === 'ready'
      ? isNearby
        ? `&viewbox=${geo.lon - 0.08},${geo.lat + 0.06},${geo.lon + 0.08},${geo.lat - 0.06}&bounded=1`
        : `&viewbox=${geo.lon - 0.5},${geo.lat + 0.3},${geo.lon + 0.5},${geo.lat - 0.3}&bounded=0`
      : ''
    fetch(
      `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(q)}&format=json&limit=1&addressdetails=1${bias}`,
      { headers: { 'Accept-Language': 'en' } },
    )
      .then(r => r.json())
      .then((data: PlaceResult[]) => {
        if (data[0]) selectPlace(data[0])
      })
      .catch(() => {})
      .finally(() => setSearching(false))
  }, [mapPendingRoute, mapOverlayOpen, geo, selectPlace, setMapPendingRoute])

  const commitLocation = async () => {
    if (!locInput.trim()) { setLocEditing(false); return }
    setLocLoading(true)
    try {
      const res  = await fetch(
        `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(locInput.trim())}&format=json&limit=1`,
        { headers: { 'Accept-Language': 'en' } },
      )
      const data = await res.json()
      if (data[0]) {
        const lat = parseFloat(data[0].lat)
        const lon = parseFloat(data[0].lon)
        localStorage.setItem('luna_map_location', JSON.stringify({ lat, lon }))
        setGeo({ status: 'ready', lat, lon, accuracy: null })
        mapRef.current?.flyTo({ center: [lon, lat], zoom: 13.5, duration: 1800 })
      }
    } catch {}
    setLocLoading(false)
    setLocEditing(false)
    setLocInput('')
  }

  const clearDestination = () => {
    setDestination(null)
    setRoute(null)
    setQuery('')
    setResults([])
    clearResultMarkers()
    if (geo.status === 'ready' && mapRef.current) {
      mapRef.current.flyTo({ center: [geo.lon, geo.lat], zoom: 13.5, duration: 1800 })
    }
  }

  return (
    <AnimatePresence>
      {mapOverlayOpen && (
        <motion.div
          className="fixed inset-0 z-[60]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.28 }}
          style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
        >
          <div ref={mapContainerRef} className="absolute inset-0" />

          {/* vignette */}
          <div className="pointer-events-none absolute inset-0 z-[1]" style={{ background: 'radial-gradient(ellipse at center, transparent 38%, rgba(0,0,0,0.78) 100%)' }} />

          {/* scanlines */}
          <div className="pointer-events-none absolute inset-0 z-[1]" style={{ backgroundImage: 'repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.055) 2px,rgba(0,0,0,0.055) 3px)' }} />

          {/* header â€” location info */}
          <div className="absolute left-5 top-5 z-10 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full border shrink-0" style={{ borderColor: 'rgba(34,211,238,0.45)', background: 'rgba(0,0,0,0.6)', boxShadow: '0 0 24px rgba(34,211,238,0.2)', backdropFilter: 'blur(8px)' }}>
              <LocateFixed size={18} color="rgba(165,243,252,0.95)" />
            </div>
            <div style={{ background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(8px)', padding: '5px 12px', borderRadius: 8, border: '1px solid rgba(34,211,238,0.22)', minWidth: 160 }}>
              <div className="text-[11px] uppercase text-cyan-300" style={{ letterSpacing: '0.18em' }}>location</div>
              {locEditing ? (
                <div className="flex items-center gap-1.5 mt-0.5">
                  <input
                    ref={locInputRef}
                    value={locInput}
                    onChange={e => setLocInput(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') commitLocation(); if (e.key === 'Escape') { setLocEditing(false); setLocInput('') } }}
                    placeholder="City or address..."
                    autoFocus
                    className="bg-transparent text-xs text-cyan-100 placeholder-cyan-100/30 outline-none w-36"
                  />
                  <button onClick={commitLocation} disabled={locLoading} className="text-cyan-400 hover:text-cyan-200 transition-colors shrink-0">
                    {locLoading ? <span className="text-[10px] text-cyan-400/60">...</span> : <Check size={13} />}
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => { setLocEditing(true); setLocInput('') }}
                  className="flex items-center gap-1.5 group"
                  title="Fix location"
                >
                  <span className="text-xs text-cyan-100/70">
                    {geo.status === 'ready' ? `${formatCoord(geo.lat, 'lat')} / ${formatCoord(geo.lon, 'lon')}` : geo.status === 'loading' ? 'locating...' : geo.message}
                  </span>
                  <Pencil size={10} className="text-cyan-400/40 group-hover:text-cyan-400 transition-colors" />
                </button>
              )}
            </div>
          </div>

          {/* search bar */}
          <div className="absolute left-1/2 top-5 z-10 -translate-x-1/2" style={{ width: 340 }}>
            <div className="relative flex items-center" style={{ background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(12px)', borderRadius: 12, border: '1px solid rgba(34,211,238,0.28)', boxShadow: '0 0 20px rgba(34,211,238,0.08)' }}>
              <Search size={15} className="absolute left-3 text-cyan-400/70 pointer-events-none" />
              <input
                value={query}
                onChange={e => onQueryChange(e.target.value)}
                placeholder="Search places, shops, addresses..."
                className="w-full bg-transparent py-2.5 pl-9 pr-9 text-sm text-cyan-100 placeholder-cyan-100/30 outline-none"
              />
              {query && (
                <button onClick={clearDestination} className="absolute right-3 text-cyan-400/60 hover:text-cyan-300">
                  <X size={14} />
                </button>
              )}
              {searching && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 border-2 border-cyan-400/40 border-t-cyan-400 rounded-full animate-spin pointer-events-none" />
              )}
            </div>
          </div>

          {/* close */}
          <button onClick={closeMapOverlay} className="absolute right-5 top-5 z-10 flex h-10 w-10 items-center justify-center rounded-full border transition-colors hover:bg-cyan-900/30" style={{ borderColor: 'rgba(34,211,238,0.35)', color: 'rgba(207,250,254,0.9)', background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(8px)' }} title="Close map">
            <X size={18} />
          </button>

          {/* route info panel */}
          <AnimatePresence>
            {(route || routeLoading || destination) && (
              <motion.div
                initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 24 }}
                transition={{ duration: 0.22 }}
                className="absolute bottom-6 left-1/2 z-10 -translate-x-1/2"
              >
                <div className="flex items-center gap-3" style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(12px)', padding: '10px 18px', borderRadius: 16, border: '1px solid rgba(251,146,60,0.35)', boxShadow: '0 0 24px rgba(251,146,60,0.12)' }}>
                  {routeLoading ? (
                    <div className="flex items-center gap-2 text-orange-300/80">
                      <Route size={14} className="animate-pulse" />
                      <span className="text-xs">Calculating route...</span>
                    </div>
                  ) : route ? (
                    <>
                      <Navigation size={14} className="text-orange-400" />
                      <div className="flex items-center gap-3 text-xs text-orange-100">
                        <span className="flex items-center gap-1">
                          <Route size={12} className="text-orange-400/70" />
                          {formatDistance(route.distance)}
                        </span>
                        <span className="text-orange-100/40">Â·</span>
                        <span className="flex items-center gap-1">
                          <Clock size={12} className="text-orange-400/70" />
                          {formatDuration(route.duration)}
                        </span>
                        {destination && <span className="text-orange-100/50 max-w-[160px] truncate">â†’ {destination.name}</span>}
                      </div>
                      <button onClick={clearDestination} className="ml-1 text-orange-400/50 hover:text-orange-300 transition-colors">
                        <X size={13} />
                      </button>
                    </>
                  ) : destination ? (
                    <div className="flex items-center gap-2 text-orange-300/80">
                      <MapPin size={14} />
                      <span className="text-xs max-w-[220px] truncate">{destination.name}</span>
                    </div>
                  ) : null}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* footer â€” coordinates (hidden when route panel showing) */}
          {!destination && (
            <div className="absolute bottom-6 left-1/2 z-10 -translate-x-1/2 text-center">
              <div className="flex items-center gap-2 text-cyan-100" style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(8px)', padding: '5px 14px', borderRadius: 20, border: '1px solid rgba(34,211,238,0.2)' }}>
                <MapPin size={14} />
                <span className="text-xs uppercase" style={{ letterSpacing: '0.16em' }}>
                  {geo.status === 'ready' ? 'location locked' : 'waiting for location'}
                </span>
              </div>
              {geo.status === 'ready' && geo.accuracy !== null && (
                <div className="mt-1 text-[11px] text-cyan-100/50">accuracy Â±{Math.round(geo.accuracy)} m</div>
              )}
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  )
}
