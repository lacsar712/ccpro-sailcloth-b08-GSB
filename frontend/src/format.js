// 树脂累计的统一展示格式：晾晒架挂签角标与树脂累计专页必须使用同一函数，
// 保证两处合计文本完全一致。无浸渍时显示 0。
export function fmtResinTotal(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '0'
  // 入库精度为两位小数；四舍五入到分位后去掉多余的 0（54.50 -> "54.5"，0 -> "0"）
  return String(Math.round(n * 100) / 100)
}
