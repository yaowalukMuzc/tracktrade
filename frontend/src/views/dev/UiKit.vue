<script setup lang="ts">
// Dev-only showcase content (not shipped: /dev/ui is registered only when import.meta.env.DEV).
// Sample copy is intentionally literal; the i18n raw-text lint rule is disabled for src/views/dev.
import { ref } from 'vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtBadge from '@/components/ui/TtBadge.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtCard from '@/components/ui/TtCard.vue'
import TtCheckbox from '@/components/ui/TtCheckbox.vue'
import TtChip from '@/components/ui/TtChip.vue'
import TtField from '@/components/ui/TtField.vue'
import TtGrade from '@/components/ui/TtGrade.vue'
import TtIconButton from '@/components/ui/TtIconButton.vue'
import TtInput from '@/components/ui/TtInput.vue'
import TtModal from '@/components/ui/TtModal.vue'
import TtPnl from '@/components/ui/TtPnl.vue'
import TtSegmented from '@/components/ui/TtSegmented.vue'
import TtSelect from '@/components/ui/TtSelect.vue'
import TtSheet from '@/components/ui/TtSheet.vue'
import TtStat from '@/components/ui/TtStat.vue'
import TtTable from '@/components/ui/TtTable.vue'
import TtTabs from '@/components/ui/TtTabs.vue'
import TtTextarea from '@/components/ui/TtTextarea.vue'
import TtToggle from '@/components/ui/TtToggle.vue'
import type { BadgeVariant } from '@/components/ui/TtBadge.vue'

const period = ref<'month' | 'year' | 'all'>('month')
const unit = ref<'$' | 'R'>('$')
const tab = ref<'all' | 'review' | 'pending'>('all')
const tags = ref<Record<string, boolean>>({ calm: true, fomo: true, focused: false })
const on = ref(true)
const off = ref(false)
const remember = ref(true)
const modal = ref(false)
const sheet = ref(false)
const entry = ref('4387.52')
const sl = ref('4366')
const note = ref('')
const session = ref('london')

const badges: { v: BadgeVariant; label: string }[] = [
  { v: 'neutral', label: 'Draft' },
  { v: 'solid', label: 'Locked' },
  { v: 'brand', label: 'Triggered' },
  { v: 'outline', label: 'MT5' },
  { v: 'warning', label: 'รอรีวิว' },
  { v: 'loss', label: 'Invalidated' },
  { v: 'profit', label: 'Win' },
  { v: 'long', label: 'LONG' },
  { v: 'short', label: 'SHORT' },
  { v: 'gold', label: 'PRO' },
]
const rows = [
  { id: 1, symbol: 'XAUUSD', dir: 'LONG', pnl: 1669.98, r: 2.4, grade: 'A' as const },
  { id: 2, symbol: 'EURUSD', dir: 'SHORT', pnl: -486, r: -1, grade: 'B' as const },
  { id: 3, symbol: 'GBPJPY', dir: 'LONG', pnl: 0, r: 0, grade: 'C' as const },
]
const columns = [
  { key: 'symbol', label: 'Symbol' },
  { key: 'dir', label: 'Direction' },
  { key: 'pnl', label: 'P/L', align: 'right' as const },
  { key: 'grade', label: 'Quality', align: 'center' as const },
]
</script>

<template>
  <div class="flex flex-col gap-6">
    <TtCard title="Button">
      <div class="tt-row">
        <TtButton variant="primary" icon="planLocked">ล็อกแผน</TtButton>
        <TtButton variant="secondary" icon="add">เพิ่มเทรด</TtButton>
        <TtButton variant="ghost">ดูทั้งหมด</TtButton>
        <TtButton variant="danger" icon="delete">Revoke</TtButton>
        <TtButton variant="primary" disabled>Lock (checklist 2/3)</TtButton>
        <TtButton variant="primary" loading>กำลังบันทึก</TtButton>
      </div>
      <div class="tt-row mt-3">
        <TtButton variant="primary" size="sm">Small</TtButton>
        <TtButton variant="secondary" size="sm" icon="scan">Scan</TtButton>
        <TtButton variant="primary" size="lg">Large CTA</TtButton>
      </div>
      <div class="mt-3"><TtButton variant="primary" size="lg" block>บันทึกรีวิว (block)</TtButton></div>
    </TtCard>

    <TtCard title="IconButton">
      <div class="tt-row">
        <TtIconButton icon="alerts" label="แจ้งเตือน" dot />
        <TtIconButton icon="aiCoach" label="AI Coach" :active="true" />
        <TtIconButton icon="edit" label="แก้ไข" :active="false" />
        <TtIconButton icon="close" label="ปิด" bare />
        <TtIconButton icon="delete" label="ลบ" disabled />
      </div>
    </TtCard>

    <TtCard title="Field">
      <div class="grid gap-4 sm:grid-cols-2">
        <TtField label="อีเมล" required help="ใช้สำหรับเข้าสู่ระบบ">
          <TtInput type="email" placeholder="you@email.com" />
        </TtField>
        <TtField label="รหัสผ่าน" error="รหัสผ่านต้องยาวอย่างน้อย 8 ตัวอักษร (ตอนนี้ 6)">
          <TtInput type="password" model-value="trade1" revealable />
        </TtField>
        <TtField label="Entry">
          <TtInput v-model="entry" numeric suffix="USD" />
        </TtField>
        <TtField label="SL" low-confidence="อ่านได้ไม่ชัด (62%) — ตรวจอีกครั้ง">
          <TtInput v-model="sl" numeric suffix="USD" />
        </TtField>
        <TtField label="Session">
          <TtSelect
            v-model="session"
            :options="[
              { value: 'asia', label: 'Asia' },
              { value: 'london', label: 'London' },
              { value: 'ny', label: 'New York' },
            ]"
          />
        </TtField>
        <TtField label="Disabled">
          <TtInput model-value="FTMO 100K" disabled />
        </TtField>
        <TtField label="Narrative" class="sm:col-span-2">
          <TtTextarea v-model="note" placeholder="ราคากลับมายืนเหนือ 4,366 …" />
        </TtField>
      </div>
      <div class="tt-row mt-4">
        <TtCheckbox v-model="remember">จดจำฉันไว้</TtCheckbox>
      </div>
    </TtCard>

    <TtCard title="SegmentedControl · Tabs">
      <div class="flex flex-col gap-4">
        <div class="tt-row">
          <TtSegmented
            v-model="period"
            label="Period"
            :options="[
              { value: 'month', label: 'เดือนนี้' },
              { value: 'year', label: 'ทั้งปี' },
              { value: 'all', label: 'ทั้งหมด' },
            ]"
          />
          <TtSegmented
            v-model="unit"
            label="Unit"
            :options="[
              { value: '$', label: '$' },
              { value: 'R', label: 'R' },
            ]"
          />
        </div>
        <TtSegmented
          v-model="period"
          label="Period block"
          block
          :options="[
            { value: 'month', label: 'เดือนนี้' },
            { value: 'year', label: 'ทั้งปี' },
            { value: 'all', label: 'ทั้งหมด' },
          ]"
        />
        <TtTabs
          v-model="tab"
          label="Trades"
          :items="[
            { value: 'all', label: 'ทั้งหมด', count: 42 },
            { value: 'review', label: 'รอรีวิว', count: 3 },
            { value: 'pending', label: 'รอจับคู่', count: 2 },
          ]"
        />
      </div>
    </TtCard>

    <TtCard title="Chip">
      <div class="tt-row">
        <TtChip :selected="tags.calm" valence="pos" @click="tags.calm = !tags.calm">พักผ่อนพอ</TtChip>
        <TtChip :selected="tags.fomo" valence="neg" @click="tags.fomo = !tags.fomo">FOMO</TtChip>
        <TtChip :selected="tags.focused" @click="tags.focused = !tags.focused">มีสมาธิ</TtChip>
        <TtChip selected>London</TtChip>
        <TtChip dot>H4</TtChip>
        <TtChip size="sm">M15</TtChip>
        <TtChip add>เพิ่ม tag</TtChip>
      </div>
    </TtCard>

    <TtCard title="Badge · Grade">
      <div class="tt-row">
        <TtBadge v-for="b in badges" :key="b.v" :variant="b.v">{{ b.label }}</TtBadge>
        <TtBadge variant="solid" icon="planLocked">Locked</TtBadge>
      </div>
      <div class="tt-row mt-3">
        <TtGrade grade="A" :score="88" />
        <TtGrade grade="B" :score="74" />
        <TtGrade grade="C" :score="58" />
        <TtGrade grade="D" :score="41" />
      </div>
    </TtCard>

    <TtCard title="PnL">
      <div class="flex flex-col gap-2">
        <TtPnl :money="1669.98" :r="2.4" size="display" arrow />
        <TtPnl :money="-486" :r="-1" size="lg" arrow />
        <TtPnl :money="0" :r="0" size="md" />
        <TtPnl :money="420" size="sm" />
        <TtPnl :money="-1025.4" compact size="sm" />
        <div class="tt-row"><span class="text-caption text-ink-muted">r_only:</span><TtPnl :money="1669.98" :r="2.4" visibility="r_only" /></div>
      </div>
    </TtCard>

    <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
      <TtStat label="P/L วันนี้"><TtPnl :money="420" size="lg" /></TtStat>
      <TtStat label="เทรด" icon="trades" delta="max 5 / วัน">2 / 5</TtStat>
      <TtStat label="Avg adherence" :meter="86" delta="+4 จากสัปดาห์ก่อน">86%</TtStat>
      <TtStat label="Daily loss" :meter="0">0%</TtStat>
    </div>

    <TtCard title="Card + action">
      <template #action><TtButton variant="ghost" size="sm" icon="add">เพิ่ม</TtButton></template>
      <p class="m-0 text-body text-ink-muted">Border only, no shadow, radius 14px.</p>
    </TtCard>

    <TtCard title="Alert">
      <div class="flex flex-col gap-3">
        <TtAlert title="ข้อมูลเทรดของคุณเป็นของคุณ" body="Mentor เห็นข้อมูลได้เฉพาะเมื่อคุณเชิญ" icon="risk" />
        <TtAlert variant="warning" icon="news" title="USD CPI 19:30 · High impact" body="News blackout 19:15–19:45" />
        <TtAlert variant="loss" title="ผิดกฎ: เกิน max trades/วัน" body="FTMO 100K · 6/5 เทรด" dismissible />
        <TtAlert variant="profit" title="บันทึกรีวิวแล้ว" />
        <TtAlert variant="gold" title="Pro feature" body="AI Coach รายสัปดาห์" />
      </div>
    </TtCard>

    <TtCard title="Toggle">
      <div class="tt-row gap-4">
        <TtToggle v-model="on" label="On" />
        <TtToggle v-model="off" label="Off" />
        <TtToggle :model-value="true" label="Disabled" disabled />
      </div>
    </TtCard>

    <TtCard title="Table" flush>
      <TtTable :columns="columns" :rows="rows" row-key="id" caption="Trades" clickable>
        <template #cell-symbol="{ row }"><b>{{ row.symbol }}</b></template>
        <template #cell-dir="{ row }">
          <TtBadge :variant="row.dir === 'LONG' ? 'long' : 'short'">{{ row.dir }}</TtBadge>
        </template>
        <template #cell-pnl="{ row }"><TtPnl :money="row.pnl" :r="row.r" /></template>
        <template #cell-grade="{ row }"><TtGrade :grade="row.grade" /></template>
      </TtTable>
    </TtCard>
    <TtCard title="Table (empty)" flush>
      <TtTable :columns="columns" :rows="[]" row-key="id" empty="ยังไม่มีเทรด — เริ่มจากสร้างแผน" />
    </TtCard>

    <TtCard title="Modal · Sheet">
      <div class="tt-row">
        <TtButton variant="secondary" @click="modal = true">Open modal</TtButton>
        <TtButton variant="secondary" @click="sheet = true">Open sheet</TtButton>
      </div>
    </TtCard>

    <TtModal v-model:open="modal" title="จับคู่เทรดกับแผน" subtitle="XAUUSD LONG · 08:42">
      <p class="m-0 text-body text-ink-muted">เลือกแผนที่เทรดนี้ทำตาม หรือติดว่าไม่มีแผน</p>
      <template #footer>
        <TtButton variant="secondary" @click="modal = false">ไม่มีแผน</TtButton>
        <TtButton variant="primary" @click="modal = false">ยืนยัน</TtButton>
      </template>
    </TtModal>
    <TtSheet v-model:open="sheet" title="ขยับ SL — ทำไม?" subtitle="XAUUSD · SL 4,366.78 → 4,360.00">
      <div class="tt-row">
        <TtChip valence="neg" selected>กลัวโดน SL</TtChip>
        <TtChip>ตามแผน</TtChip>
      </div>
      <template #footer>
        <TtButton variant="primary" block @click="sheet = false">บันทึก</TtButton>
      </template>
    </TtSheet>
  </div>
</template>
