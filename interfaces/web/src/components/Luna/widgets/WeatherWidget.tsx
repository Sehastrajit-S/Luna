import { useEffect, useState } from 'react'
import { Wind, Droplets } from 'lucide-react'
import { P } from '../palette'
import { fetchLunaCached } from '../lunaDashboardApi'

interface Weather { temp_f: number; feels_f: number; humidity: number; wind_mph: number; condition: string; city: string }

export function WeatherWidget() {
  const [wx, setWx] = useState<Weather | null>(null)
  const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading')

  useEffect(() => {
    const load = async () => {
      try {
        const d = await fetchLunaCached<Weather | null>('/api/luna/weather', 10 * 60_000)
        if (d?.temp_f !== undefined) { setWx(d); setStatus('ok') }
        else setStatus('error')
      } catch (e) {
        console.warn('[luna] weather unavailable', e); setStatus('error')
      }
    }
    load()
    const t = setInterval(load, 10 * 60_000)
    return () => clearInterval(t)
  }, [])

  if (status !== 'ok' || !wx) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: P.textDim, fontFamily: 'monospace', fontSize: 10, letterSpacing: '0.1em' }}>
      {status === 'loading' ? 'FETCHING...' : 'UNAVAILABLE'}
    </div>
  )

  return (
    <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 5, height: '100%', justifyContent: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontFamily: 'monospace', fontSize: 34, color: P.text, fontWeight: 200, letterSpacing: '-0.02em' }}>{wx.temp_f}°</span>
        <span style={{ fontFamily: 'monospace', fontSize: 10, color: P.textDim }}>F</span>
        <span style={{ fontFamily: 'monospace', fontSize: 10, color: P.textDim, marginLeft: 4 }}>{wx.city}</span>
      </div>
      <div style={{ fontFamily: 'monospace', fontSize: 11, color: 'rgba(255,255,255,0.65)' }}>{wx.condition}</div>
      <div style={{ display: 'flex', gap: 14, marginTop: 2 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontFamily: 'monospace', fontSize: 9, color: P.textDim }}><Droplets size={9} />{wx.humidity}%</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontFamily: 'monospace', fontSize: 9, color: P.textDim }}><Wind size={9} />{wx.wind_mph} mph</div>
        <div style={{ fontFamily: 'monospace', fontSize: 9, color: P.textDim }}>feels {wx.feels_f}°</div>
      </div>
    </div>
  )
}
