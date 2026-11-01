const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']

function parse(iso) {
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year, month - 1, day)
}

// 서버 시각은 UTC로 저장된다.
export function dateTime(value) {
  const date = new Date(`${value.replace(' ', 'T')}Z`)
  const pad = (number) => String(number).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function dDayLabel(days) {
  return days === 0 ? 'D-Day' : `D-${days}`
}

export function shortDate(iso) {
  const date = parse(iso)
  return `${date.getMonth() + 1}.${date.getDate()}`
}

export function longDate(iso) {
  const date = parse(iso)
  return `${date.getMonth() + 1}.${date.getDate()} (${WEEKDAYS[date.getDay()]})`
}

export function weekday(iso) {
  return WEEKDAYS[parse(iso).getDay()]
}

export function dayOfMonth(iso) {
  return parse(iso).getDate()
}
