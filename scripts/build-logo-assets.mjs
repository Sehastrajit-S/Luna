#!/usr/bin/env node
import sharp from 'sharp'
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const svg = resolve(root, 'electron/assets/logo.svg')
const outDir = resolve(root, 'electron/assets')
mkdirSync(outDir, { recursive: true })

const png256 = await sharp(svg).resize(256, 256).png().toBuffer()
const png32 = await sharp(svg).resize(32, 32).png().toBuffer()
const png16 = await sharp(svg).resize(16, 16).png().toBuffer()

writeFileSync(resolve(outDir, 'icon.png'), png256)
writeFileSync(resolve(outDir, 'tray.png'), png32)

function icoEntry(png, size, offset) {
  const b = Buffer.alloc(16)
  b.writeUInt8(size === 256 ? 0 : size, 0)
  b.writeUInt8(size === 256 ? 0 : size, 1)
  b.writeUInt8(0, 2)
  b.writeUInt8(0, 3)
  b.writeUInt16LE(1, 4)
  b.writeUInt16LE(32, 6)
  b.writeUInt32LE(png.length, 8)
  b.writeUInt32LE(offset, 12)
  return b
}

const images = [
  { size: 16, png: png16 },
  { size: 32, png: png32 },
  { size: 256, png: png256 },
]
const header = Buffer.alloc(6)
header.writeUInt16LE(0, 0)
header.writeUInt16LE(1, 2)
header.writeUInt16LE(images.length, 4)

let offset = header.length + images.length * 16
const entries = images.map(image => {
  const entry = icoEntry(image.png, image.size, offset)
  offset += image.png.length
  return entry
})

writeFileSync(resolve(outDir, 'icon.ico'), Buffer.concat([header, ...entries, ...images.map(i => i.png)]))

console.log('Built Electron logo assets from', svg)
