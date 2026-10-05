<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api'
import { fmtResinTotal } from '../format'

const lofts = ref([])
const rolls = ref([])
const rows = ref([])
const loftId = ref('')
const rollId = ref('')
const error = ref('')
const loading = ref(false)

const rollOptions = computed(() => {
  if (!loftId.value) return rolls.value
  return rolls.value.filter((r) => r.loftId === Number(loftId.value))
})

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
    if (loftId.value) params.loftId = loftId.value
    if (rollId.value) params.rollId = rollId.value
    const { data } = await api.get('/resin/', { params })
    rows.value = data.results || []
  } catch {
    error.value = '树脂累计加载失败'
  } finally {
    loading.value = false
  }
}

function onLoftChange() {
  if (rollId.value && !rollOptions.value.some((r) => r.id === Number(rollId.value))) {
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
          每卷历史浸渍的树脂百分比与算术合计；合计与晾晒架挂签角标、库内该卷各次树脂相加一致。
        </p>
      </div>
      <button class="btn secondary" type="button" @click="load">刷新合计</button>
    </header>

    <div class="panel row filter-bar">
      <label>帆布间
        <select v-model="loftId" @change="onLoftChange">
          <option value="">全部帆布间</option>
          <option v-for="l in lofts" :key="l.id" :value="String(l.id)">{{ l.name }}</option>
        </select>
      </label>
      <label>布卷
        <select v-model="rollId" @change="load">
          <option value="">全部布卷</option>
          <option v-for="r in rollOptions" :key="r.id" :value="String(r.id)">
            {{ r.rollCode }} · {{ r.loftName }}
          </option>
        </select>
      </label>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <section v-for="row in rows" :key="row.rollId" class="panel resin-roll">
      <header class="resin-roll-head">
        <div>
          <p class="resin-loft">{{ row.loftName }}</p>
          <h2 class="resin-code">{{ row.rollCode }}</h2>
        </div>
        <div class="resin-total">
          <span class="resin-total-label">算术合计</span>
          <strong class="resin-total-value">{{ fmtResinTotal(row.resinTotal) }}</strong>
          <span class="hint">{{ row.dipCount }} 笔浸渍</span>
        </div>
      </header>

      <table v-if="row.dips.length" class="resin-table">
        <thead>
          <tr>
            <th>开始时间</th>
            <th>树脂 %</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in row.dips" :key="d.id">
            <td>{{ new Date(d.startedAt).toLocaleString() }}</td>
            <td>{{ d.resinPct }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td>合计</td>
            <td>{{ fmtResinTotal(row.resinTotal) }}</td>
          </tr>
        </tfoot>
      </table>
      <p v-else class="hint" style="margin:0">本卷尚无浸渍，合计 0。</p>
    </section>

    <p v-if="!rows.length && !error && !loading" class="hint">无匹配布卷</p>
  </div>
</template>
