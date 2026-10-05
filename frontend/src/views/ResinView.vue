<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api'
import { fmtResin } from '../utils/format'

const lofts = ref([])
const rolls = ref([])
const groups = ref([])
const error = ref('')
const loading = ref(false)
const loftId = ref('')
const rollId = ref('')

const rollOptions = computed(() => {
  if (loftId.value === '') return rolls.value
  return rolls.value.filter((r) => r.loftId === Number(loftId.value))
})

const grandTotal = computed(() =>
  groups.value.reduce((acc, g) => acc + Number(g.total || 0), 0)
)

const entryCount = computed(() =>
  groups.value.reduce((acc, g) => acc + g.entries.length, 0)
)

async function loadFilters() {
  const [l, r] = await Promise.all([api.get('/lofts/'), api.get('/rolls/')])
  lofts.value = l.data.results || l.data
  rolls.value = r.data.results || r.data
}

async function load() {
  error.value = ''
  loading.value = true
  try {
    const params = {}
    if (loftId.value !== '') params.loftId = loftId.value
    if (rollId.value !== '') params.rollId = rollId.value
    const { data } = await api.get('/resin/', { params })
    groups.value = data.results || data
  } catch {
    error.value = '树脂累计加载失败'
  } finally {
    loading.value = false
  }
}

function onLoftChange() {
  // 换帆布间后卷选项跟着收敛，避免选了别间的卷
  if (
    rollId.value !== '' &&
    !rollOptions.value.some((r) => r.id === Number(rollId.value))
  ) {
    rollId.value = ''
  }
  load()
}

onMounted(async () => {
  try {
    await loadFilters()
  } catch {
    error.value = '筛选项加载失败'
  }
  await load()
})
</script>

<template>
  <div class="resin-page">
    <header class="rack-head">
      <div>
        <h1>树脂累计</h1>
        <p class="sub">
          每卷历史浸渍的树脂百分比与算术合计；合计与晾晒架挂签角标同口径（库内各次相加）。
        </p>
      </div>
      <button class="btn secondary" type="button" @click="load">刷新合计</button>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="panel row resin-filters">
      <label>帆布间
        <select v-model="loftId" @change="onLoftChange">
          <option value="">全部帆布间</option>
          <option v-for="l in lofts" :key="l.id" :value="l.id">{{ l.name }}</option>
        </select>
      </label>
      <label>布卷
        <select v-model="rollId" @change="load">
          <option value="">全部布卷</option>
          <option v-for="r in rollOptions" :key="r.id" :value="r.id">
            {{ r.rollCode }} · {{ r.loftName }}
          </option>
        </select>
      </label>
      <p class="hint resin-summary">
        共 {{ groups.length }} 卷 · {{ entryCount }} 笔浸渍 · 总累计
        <strong>{{ fmtResin(grandTotal) }}%</strong>
      </p>
    </div>

    <p v-if="loading" class="hint">合计计算中…</p>

    <section v-for="g in groups" :key="g.rollId" class="panel resin-card">
      <header class="resin-head">
        <div class="resin-title">
          <strong class="resin-roll">{{ g.rollCode }}</strong>
          <span class="feed-loft">{{ g.loftName }}</span>
        </div>
        <span class="resin-total">累计 {{ fmtResin(g.total) }}%</span>
      </header>

      <template v-if="g.entries.length">
        <table class="resin-table">
          <thead>
            <tr>
              <th>开始时间</th>
              <th>树脂 %</th>
              <th>固化时长 h</th>
              <th>备注</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="e in g.entries" :key="e.id">
              <td>{{ new Date(e.startedAt).toLocaleString() }}</td>
              <td>{{ fmtResin(e.resinPct) }}</td>
              <td>{{ e.cureHours ?? '—' }}</td>
              <td>{{ e.notes }}</td>
            </tr>
          </tbody>
        </table>
        <p class="resin-sumline">
          算术合计：{{ g.entries.map((e) => fmtResin(e.resinPct)).join(' + ') }}
          = <strong>{{ fmtResin(g.total) }}%</strong>
        </p>
      </template>
      <p v-else class="hint" style="margin:0">本卷尚无浸渍记录，累计 0%。</p>
    </section>

    <p v-if="!loading && !groups.length && !error" class="hint">
      当前筛选下没有布卷
    </p>
  </div>
</template>
