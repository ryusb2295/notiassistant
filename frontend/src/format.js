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

// 서버 UTC 시각을 "10분 전"처럼 보여준다.
export function ago(value) {
  if (!value) return '기록 없음'
  const minutes = Math.floor((Date.now() - new Date(`${value.replace(' ', 'T')}Z`).getTime()) / 60000)
  if (minutes < 1) return '방금'
  if (minutes < 60) return `${minutes}분 전`
  if (minutes < 60 * 24) return `${Math.floor(minutes / 60)}시간 전`
  return `${Math.floor(minutes / 60 / 24)}일 전`
}

export function dDayLabel(days) {
  if (days < 0) return '마감'
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
