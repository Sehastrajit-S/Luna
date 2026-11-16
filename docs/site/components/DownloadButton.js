import { useEffect, useState } from 'react';
import Link from 'next/link';
import PlatformIcon from './PlatformIcon';

const LATEST = 'https://github.com/Sehastrajit-S/Luna/releases/latest/download';

// Fixed-name release files: these always point at the newest version.
export const DOWNLOADS = {
  windows: { icon: 'windows', label: 'Download for Windows', href: `${LATEST}/Luna-Setup.exe`, note: 'Windows 10 and 11 · 64-bit' },
  mac: {
    icon: 'apple',
    label: 'Download for Mac',
    href: `${LATEST}/Luna-macos-arm64.dmg`,
    note: 'Apple silicon',
    alt: { label: 'Intel Mac', href: `${LATEST}/Luna-macos-x64.dmg` },
  },
  linux: {
    icon: 'linux',
    label: 'Download for Linux',
    href: `${LATEST}/Luna-linux-x86_64.AppImage`,
    note: 'AppImage · x86_64',
    alt: { label: 'arm64', href: `${LATEST}/Luna-linux-arm64.AppImage` },
  },
  android: { icon: 'android', label: 'Download for Android', href: `${LATEST}/Luna-android.apk`, note: 'APK' },
  ios: { icon: 'apple', label: 'Use Luna on iPhone', href: '/setup#remote', note: 'In Safari: Add to Home Screen', internal: true },
};

export const INSTALL_COMMANDS = {
  unix: 'curl -fsSL https://www.luna-ai-engine.com/install.sh | sh',
  windows: 'irm https://www.luna-ai-engine.com/install.ps1 | iex',
};

export function detectPlatform() {
  if (typeof navigator === 'undefined') return null;
  const ua = navigator.userAgent || '';
  const platform = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || '';
  if (/android/i.test(ua)) return 'android';
  if (/iphone|ipad|ipod/i.test(ua) || (/Mac/i.test(platform) && navigator.maxTouchPoints > 1)) return 'ios';
  if (/win/i.test(platform) || /windows/i.test(ua)) return 'windows';
  if (/mac/i.test(platform) || /mac os x/i.test(ua)) return 'mac';
  if (/linux|x11/i.test(platform) || /linux/i.test(ua)) return 'linux';
  return null;
}

/**
 * One big button for the visitor's OS. Before hydration (and for unknown systems)
 * it links to the full download list, so it never points at the wrong file.
 */
export default function DownloadButton({ className = 'lp-btn lp-btn-primary', fallbackHref = '#download', showNote = true }) {
  const [os, setOs] = useState(null);
  useEffect(() => setOs(detectPlatform()), []);

  const target = os ? DOWNLOADS[os] : null;
  if (!target) {
    return (
      <Link href={fallbackHref} className={className}>Download Luna free</Link>
    );
  }

  const button = target.internal
    ? <Link href={target.href} className={className}><PlatformIcon name={target.icon} size={18} className="btn-platform-icon" />{target.label}</Link>
    : <a href={target.href} className={className}><PlatformIcon name={target.icon} size={18} className="btn-platform-icon" />{target.label}</a>;

  return (
    <span className="lp-download-cta">
      {button}
      {showNote && (
        <span className="lp-download-cta-note">
          {target.note}
          {target.alt && <> · <a href={target.alt.href}>{target.alt.label}</a></>}
          {' · '}<Link href={fallbackHref}>Other platforms</Link>
        </span>
      )}
    </span>
  );
}
