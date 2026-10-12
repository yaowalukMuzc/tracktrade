/** IANA timezone of this browser, falling back to UTC. */
export function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  } catch {
    return 'UTC'
  }
}

/** `UTC+7` style offset of a zone right now. */
export function utcOffset(tz: string, at = new Date()): string {
  try {
    const part = new Intl.DateTimeFormat('en-US', { timeZone: tz, timeZoneName: 'shortOffset' })
      .formatToParts(at)
      .find((p) => p.type === 'timeZoneName')?.value
    return part === 'GMT' ? 'UTC' : (part?.replace('GMT', 'UTC') ?? 'UTC')
  } catch {
    return 'UTC'
  }
}

let cache: string[] | null = null
function allZones(): string[] {
  if (cache) return cache
  try {
    cache = Intl.supportedValuesOf('timeZone')
  } catch {
    cache = ['UTC']
  }
  if (!cache.includes('UTC')) cache = ['UTC', ...cache]
  return cache
}

/** Select options `Asia/Bangkok (UTC+7)`; `ensure` is kept even if the runtime list lacks it. */
export function timezoneOptions(ensure?: string) {
  const zones = allZones()
  const list = ensure && !zones.includes(ensure) ? [ensure, ...zones] : zones
  return list.map((tz) => ({ value: tz, label: `${tz} (${utcOffset(tz)})` }))
}
