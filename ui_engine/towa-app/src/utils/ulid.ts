const ULID_CHARSET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'

export const ULID_RE = /^[0-9A-HJKMNP-TV-Z]{26}$/

export function createUlid(now: number = Date.now()): string {
  if (!Number.isInteger(now) || now < 0 || now > 0xffffffffffff) {
    throw new Error(`ULID timestamp must fit in 48 bits: ${now}`)
  }

  const cryptoObject = globalThis.crypto
  if (!cryptoObject?.getRandomValues) {
    throw new Error('crypto.getRandomValues is required to generate ULIDs')
  }

  const bytes = new Uint8Array(16)
  let timestamp = now
  for (let i = 5; i >= 0; i--) {
    bytes[i] = timestamp & 0xff
    timestamp = Math.floor(timestamp / 256)
  }
  cryptoObject.getRandomValues(bytes.subarray(6))

  let value = 0n
  for (const byte of bytes) {
    value = (value << 8n) | BigInt(byte)
  }

  let output = ''
  for (let i = 0; i < 26; i++) {
    const shift = BigInt(125 - (i * 5))
    const index = Number((value >> shift) & 0x1fn)
    output += ULID_CHARSET[index]
  }
  return output
}

export function isCanonicalUlid(value: string): boolean {
  return ULID_RE.test(value)
}
