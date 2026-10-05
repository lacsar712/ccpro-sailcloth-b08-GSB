// 树脂累计的统一展示格式：挂签角标与树脂累计专页共用，保证两处文案一致。
// 0 显示为 "0"（不是写死的占位，是合计算出来的 0）；去掉多余的尾零。
export function fmtResin(value) {
  const n = Number(value ?? 0)
  if (!Number.isFinite(n)) return '0'
  return (Math.round(n * 100) / 100).toString()
}
