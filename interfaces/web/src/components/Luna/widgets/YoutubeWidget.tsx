import { P } from '../palette'

const DW_SRC = 'https://www.youtube.com/embed/live_stream?channel=UCknLrEdhRCp1aegoMqRaCZg&autoplay=1&rel=0&modestbranding=1'

// muted=true → grid widget thumbnail (no sound), muted=false → expanded full audio
export function YoutubeIframe({ muted }: { muted: boolean }) {
  if (muted) {
    // When expanded overlay is open, show a placeholder so only one iframe plays
    return (
      <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#000', gap: 6 }}>
        <div style={{ width: 6, height: 6, borderRadius: '50%', background: P.accent, opacity: 0.7 }} />
        <span style={{ fontFamily: 'monospace', fontSize: 9, color: P.textDim, letterSpacing: '0.18em' }}>EXPANDED</span>
      </div>
    )
  }
  return (
    <iframe
      src={DW_SRC}
      loading="lazy"
      style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
      allow="autoplay; encrypted-media; picture-in-picture"
      allowFullScreen
    />
  )
}
