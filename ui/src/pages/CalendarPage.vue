<template>
  <q-page class="app-page">
    <PageHeader icon="event" :title="t('tasks.calendar')" :subtitle="t('tasks.cal.subtitle')">
      <template #actions>
        <AppSelect v-model="aquariumFilter" :options="aquariumOptions" :label="t('tasks.cal.aquarium')" style="min-width: 200px" />
        <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('tasks.cal.newTask')" @click="openCreate(todayKey)" />
      </template>
    </PageHeader>

    <!-- Navigation par mois -->
    <div class="row items-center no-wrap gap-sm q-mb-md">
      <q-btn flat round dense icon="chevron_left" :aria-label="t('tasks.cal.prevMonth')" @click="shiftMonth(-1)">
        <q-tooltip>{{ t('tasks.cal.prevMonth') }}</q-tooltip>
      </q-btn>
      <div class="text-h6 text-weight-bold month-title">{{ monthLabel }}</div>
      <q-btn flat round dense icon="chevron_right" :aria-label="t('tasks.cal.nextMonth')" @click="shiftMonth(1)">
        <q-tooltip>{{ t('tasks.cal.nextMonth') }}</q-tooltip>
      </q-btn>
      <q-btn outline dense color="primary" :label="t('tasks.cal.today')" class="q-px-sm" @click="goToday" />
      <q-spinner v-if="loading" color="primary" size="1.2em" />
    </div>

    <!-- Légende -->
    <div class="row items-center q-gutter-md q-mb-sm text-caption text-grey-8">
      <div v-for="item in legend" :key="item.label" class="row items-center no-wrap">
        <span class="legend-swatch q-mr-xs" :class="item.cls" />{{ item.label }}
      </div>
      <div v-if="!aquariumFilter && aquariumStore.aquariums.length > 1" class="row items-center q-gutter-sm">
        <span class="text-grey-6">|</span>
        <div v-for="aqua in aquariumStore.aquariums" :key="aqua.id" class="row items-center no-wrap">
          <span class="aqua-dot q-mr-xs" :style="{ background: aquariumColor(aqua.id) }" />{{ aqua.name }}
        </div>
      </div>
    </div>

    <!-- Grille mensuelle (écran large) -->
    <q-card v-if="$q.screen.gt.xs" flat bordered class="calendar-grid">
      <div v-for="d in WEEKDAYS" :key="d" class="weekday text-caption text-weight-bold text-grey-7">{{ d }}</div>
      <div
        v-for="day in gridDays"
        :key="day.key"
        class="day-cell"
        :class="{ 'other-month': !day.inMonth, today: day.key === todayKey }"
        @click="openCreate(day.key)"
      >
        <div class="row items-center justify-between">
          <span class="day-number" :class="{ 'today-number': day.key === todayKey }">{{ day.date.getDate() }}</span>
          <q-icon name="add" size="xs" class="add-hint" color="grey-5" />
        </div>
        <!-- no-wrap : sinon la colonne prend la largeur du titre le plus long et déborde sur le jour suivant -->
        <div class="column no-wrap q-gutter-y-xs q-mt-xs">
          <div
            v-for="event in (eventsByDay[day.key] ?? []).slice(0, MAX_CHIPS)"
            :key="eventKey(event)"
            class="event-chip ellipsis"
            :class="eventClass(event)"
            :style="{ borderLeftColor: event.shared ? SHARED_COLOR : aquariumColor(event.aquarium_id) }"
            @click.stop="openEvent(event)"
          >
            <q-icon :name="eventIcon(event)" size="12px" class="q-mr-xs" />{{ event.title }}<q-icon
              v-if="event.shared"
              name="join_inner"
              size="12px"
              class="q-ml-xs"
            />
            <q-tooltip>{{ eventTooltip(event) }}</q-tooltip>
          </div>
          <div
            v-if="(eventsByDay[day.key]?.length ?? 0) > MAX_CHIPS"
            class="text-caption text-primary cursor-pointer more-link"
            @click.stop="openDay(day.key)"
          >
            {{ t('tasks.cal.more', (eventsByDay[day.key]?.length ?? 0) - MAX_CHIPS) }}
          </div>
        </div>
      </div>
    </q-card>

    <!-- Agenda (mobile) -->
    <q-card v-else flat bordered>
      <q-list separator>
        <q-item v-if="agendaDays.length === 0">
          <q-item-section class="text-grey-6">{{ t('tasks.cal.noTask') }}</q-item-section>
        </q-item>
        <template v-for="dayKey in agendaDays" :key="dayKey">
          <q-item-label header class="q-py-sm" :class="{ 'text-primary text-weight-bold': dayKey === todayKey }">
            {{ formatDayLabel(dayKey) }}
          </q-item-label>
          <q-item v-for="event in eventsByDay[dayKey]" :key="eventKey(event)" clickable @click="openEvent(event)">
            <q-item-section avatar>
              <q-icon :name="eventIcon(event)" :color="eventIconColor(event)" />
            </q-item-section>
            <q-item-section>
              <q-item-label>{{ event.title }}</q-item-label>
              <q-item-label caption>{{ event.aquarium_name }} · {{ kindLabel(event) }}</q-item-label>
            </q-item-section>
          </q-item>
        </template>
      </q-list>
    </q-card>

    <!-- Détail d'un évènement -->
    <FormDialog
      v-model="eventDialog"
      :icon="activeEvent ? eventIcon(activeEvent) : 'event'"
      :title="activeEvent?.title ?? ''"
      :subtitle="activeEvent ? `${activeEvent.aquarium_name} · ${formatDayLabel(dayKeyOf(activeEvent.date))}` : undefined"
      width="440px"
      :cancel-label="activeEvent?.kind === 'due' ? t('common.cancel') : t('common.close')"
      :hide-submit="activeEvent?.kind !== 'due' || !can.care"
      :submit-label="t('tasks.markDone')"
      submit-color="positive"
      :loading="saving"
      @submit="completeEvent"
    >
      <template v-if="activeEvent">
        <div>
          <q-chip dense :color="eventIconColor(activeEvent)" text-color="white" :icon="eventIcon(activeEvent)" class="q-ml-none">
            {{ kindLabel(activeEvent) }}
          </q-chip>
        </div>
        <div v-if="activeEvent.kind === 'planned'" class="text-body2 text-grey-7">
          {{ t('tasks.cal.plannedHelp') }}
        </div>
        <div v-if="activeEvent.note" class="text-body2">{{ t('tasks.cal.note', { note: activeEvent.note }) }}</div>
        <template v-if="activeEvent.kind === 'due' && can.care">
          <DateInput v-model="completeForm.date" :label="t('tasks.doneDateLabel')" />
          <q-input v-model="completeForm.note" :label="t('tasks.note')" outlined dense />
        </template>
      </template>
      <template #footer-left>
        <q-btn v-if="activeEvent" flat color="primary" icon="open_in_new" :label="t('tasks.cal.seeAquarium')" @click="goToAquarium(activeEvent)" />
      </template>
    </FormDialog>

    <!-- Liste d'un jour chargé -->
    <FormDialog v-model="dayDialog" icon="today" :title="formatDayLabel(activeDayKey)" width="440px" :cancel-label="t('common.close')" hide-submit>
      <q-list bordered separator class="rounded-borders">
        <q-item v-for="event in eventsByDay[activeDayKey] ?? []" :key="eventKey(event)" clickable @click="openEvent(event)">
          <q-item-section avatar>
            <q-icon :name="eventIcon(event)" :color="eventIconColor(event)" />
          </q-item-section>
          <q-item-section>
            <q-item-label>{{ event.title }}</q-item-label>
            <q-item-label caption>{{ event.aquarium_name }} · {{ kindLabel(event) }}</q-item-label>
          </q-item-section>
        </q-item>
      </q-list>
    </FormDialog>

    <!-- Création -->
    <FormDialog
      v-model="createDialog"
      icon="task_alt"
      :title="t('tasks.cal.newTask')"
      :subtitle="t('tasks.cal.createSubtitle')"
      width="480px"
      :submit-label="t('actions.add')"
      :loading="saving"
      :submit-disabled="!canCreate"
      @submit="createTask"
    >
      <ScopeSelector v-model="createScope" :current-aquarium-id="createForm.aquarium_id ?? 0" :single-label="t('tasks.cal.oneAquarium')" />
      <AppSelect
        v-if="createScope.scope === 'single'"
        v-model="createForm.aquarium_id"
        :options="aquariumStore.aquariums.map((a) => ({ label: a.name, value: a.id }))"
        :label="t('tasks.cal.aquariumRequired')"
      />
      <q-input v-model="createForm.title" :label="t('tasks.titleField')" outlined dense autofocus />
      <q-input v-model="createForm.description" :label="t('tasks.description')" type="textarea" outlined dense autogrow />
      <AppSelect v-model="createForm.recurrence" :options="recurrenceOptions" :label="t('tasks.recurrence')" />
      <q-input
        v-if="createForm.recurrence === 'custom_days'"
        v-model.number="createForm.recurrence_days"
        type="number"
        min="1"
        :label="t('tasks.everyHowManyDays')"
        :suffix="t('tasks.days')"
        outlined
        dense
      />
      <DateInput v-model="createForm.date" :label="t('tasks.cal.dueRequired')" />
    </FormDialog>
  </q-page>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import { usePermissions } from 'src/composables/usePermissions';
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useQuasar } from 'quasar';
import { useAquariumStore } from 'src/stores/aquariumStore';
import { useMaintenanceTaskStore } from 'src/stores/maintenanceTaskStore';
import { parameterColor } from 'src/types/waterParameter';
import type { CalendarEvent, TaskRecurrence } from 'src/types/maintenanceTask';
import PageHeader from 'src/components/PageHeader.vue';
import FormDialog from 'src/components/FormDialog.vue';
import ScopeSelector from 'src/components/ScopeSelector.vue';
import { scopePayload, type ScopeValue } from 'src/utils/sharedScope';
import AppSelect from 'src/components/AppSelect.vue';
import DateInput from 'src/components/DateInput.vue';
import { intlLocale } from 'src/i18n/instance';

const { t } = useI18n();

const MAX_CHIPS = 3;
const RECURRENCES: TaskRecurrence[] = ['none', 'daily', 'weekly', 'monthly', 'custom_days'];
const recurrenceOptions = computed(() => RECURRENCES.map((value) => ({ label: t(`tasks.recurrenceOptions.${value}`), value })));
// Lundi → dimanche (le 1er janvier 2024 était un lundi)
const WEEKDAYS = computed(() =>
  Array.from({ length: 7 }, (_, i) => {
    // « lun. » → « Lun »
    const name = new Date(2024, 0, 1 + i).toLocaleDateString(intlLocale(), { weekday: 'short' }).replace(/\.$/, '');
    return name.charAt(0).toUpperCase() + name.slice(1);
  }),
);

const $q = useQuasar();
const can = usePermissions();
const router = useRouter();
const aquariumStore = useAquariumStore();
const taskStore = useMaintenanceTaskStore();

function toKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function dayKeyOf(iso: string): string {
  return toKey(new Date(iso));
}

const todayKey = toKey(new Date());
const currentMonth = ref(new Date(new Date().getFullYear(), new Date().getMonth(), 1));
const aquariumFilter = ref<number | null>(null);
const events = ref<CalendarEvent[]>([]);
const loading = ref(false);
const saving = ref(false);

const monthLabel = computed(() =>
  currentMonth.value.toLocaleDateString(intlLocale(), { month: 'long', year: 'numeric' }),
);

const aquariumOptions = computed(() => [
  { label: t('tasks.cal.allAquariums'), value: null },
  ...aquariumStore.aquariums.map((a) => ({ label: a.name, value: a.id })),
]);

// Semaines complètes du lundi au dimanche englobant le mois affiché.
const gridDays = computed(() => {
  const first = currentMonth.value;
  const start = new Date(first);
  start.setDate(1 - ((first.getDay() + 6) % 7));
  const last = new Date(first.getFullYear(), first.getMonth() + 1, 0);
  const end = new Date(last);
  end.setDate(last.getDate() + (6 - ((last.getDay() + 6) % 7)));

  const days = [];
  for (const d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    const date = new Date(d);
    days.push({ key: toKey(date), date, inMonth: date.getMonth() === first.getMonth() });
  }
  return days;
});

const eventsByDay = computed(() => {
  const map: Record<string, CalendarEvent[]> = {};
  for (const event of events.value) (map[dayKeyOf(event.date)] ??= []).push(event);
  return map;
});

const agendaDays = computed(() => {
  const month = currentMonth.value.getMonth();
  return Object.keys(eventsByDay.value)
    .filter((key) => new Date(`${key}T00:00:00`).getMonth() === month)
    .sort();
});

const legend = computed(() => [
  { label: t('tasks.cal.kinds.due'), cls: 'event-due' },
  { label: t('tasks.cal.kinds.overdue'), cls: 'event-overdue' },
  { label: t('tasks.cal.plannedLegend'), cls: 'event-planned' },
  { label: t('tasks.cal.kinds.done'), cls: 'event-done' },
]);

async function load() {
  const days = gridDays.value;
  if (days.length === 0) return;
  loading.value = true;
  try {
    events.value = await taskStore.fetchCalendar(days[0]!.key, days[days.length - 1]!.key, aquariumFilter.value);
  } catch {
    $q.notify({ type: 'negative', message: t('tasks.notify.calendarFailed') });
  } finally {
    loading.value = false;
  }
}

function shiftMonth(delta: number) {
  const d = currentMonth.value;
  currentMonth.value = new Date(d.getFullYear(), d.getMonth() + delta, 1);
}

function goToday() {
  currentMonth.value = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
}

// Tâches partagées : couleur neutre plutôt que celle de l'aquarium de rattachement
const SHARED_COLOR = '#5c6bc0';

function aquariumColor(aquariumId: number): string {
  return parameterColor(aquariumId, aquariumStore.aquariums);
}

function eventKey(event: CalendarEvent): string {
  return `${event.kind}-${event.task_id}-${event.date}`;
}

function eventClass(event: CalendarEvent): string {
  if (event.kind === 'done') return 'event-done';
  if (event.kind === 'planned') return 'event-planned';
  return event.overdue ? 'event-overdue' : 'event-due';
}

function eventIcon(event: CalendarEvent): string {
  if (event.kind === 'done') return 'check_circle';
  if (event.kind === 'planned') return 'autorenew';
  return event.overdue ? 'event_busy' : 'event';
}

function eventIconColor(event: CalendarEvent): string {
  if (event.kind === 'done') return 'positive';
  if (event.kind === 'planned') return 'blue-grey-5';
  return event.overdue ? 'negative' : 'primary';
}

function kindLabel(event: CalendarEvent): string {
  if (event.kind === 'done') return t('tasks.cal.kinds.done');
  if (event.kind === 'planned') return t('tasks.cal.kinds.planned');
  return event.overdue ? t('tasks.cal.kinds.overdue') : t('tasks.cal.kinds.due');
}

function eventTooltip(event: CalendarEvent): string {
  return `${event.title} — ${event.aquarium_name} (${kindLabel(event)})${event.note ? ` : ${event.note}` : ''}`;
}

function formatDayLabel(key: string): string {
  const label = new Date(`${key}T00:00:00`).toLocaleDateString(intlLocale(), {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  });
  return label.charAt(0).toUpperCase() + label.slice(1);
}

// --- Détail / réalisation ---
const eventDialog = ref(false);
const activeEvent = ref<CalendarEvent | null>(null);
const completeForm = ref({ date: todayKey, note: '' });

function openEvent(event: CalendarEvent) {
  activeEvent.value = event;
  completeForm.value = { date: todayKey, note: '' };
  dayDialog.value = false;
  eventDialog.value = true;
}

async function completeEvent() {
  if (!activeEvent.value || !completeForm.value.date) return;
  saving.value = true;
  try {
    await taskStore.complete(activeEvent.value.task_id, {
      completed_at: `${completeForm.value.date}T12:00:00`,
      note: completeForm.value.note || null,
    });
    eventDialog.value = false;
    $q.notify({ type: 'positive', message: t('tasks.notify.doneNamed', { title: activeEvent.value.title }) });
    await load();
  } catch {
    $q.notify({ type: 'negative', message: t('tasks.notify.failed') });
  } finally {
    saving.value = false;
  }
}

function goToAquarium(event: CalendarEvent) {
  void router.push({ path: `/aquariums/${event.aquarium_id}`, query: { tab: 'tasks' } });
}

// --- Jour chargé ---
const dayDialog = ref(false);
const activeDayKey = ref(todayKey);

function openDay(key: string) {
  activeDayKey.value = key;
  dayDialog.value = true;
}

// --- Création ---
const createDialog = ref(false);
const createForm = ref<{
  aquarium_id: number | null;
  title: string;
  description: string;
  recurrence: TaskRecurrence;
  recurrence_days: number | null;
  date: string;
}>({ aquarium_id: null, title: '', description: '', recurrence: 'none', recurrence_days: null, date: todayKey });
const createScope = ref<ScopeValue>({ scope: 'single', aquarium_ids: [] });

const canCreate = computed(
  () =>
    (createScope.value.scope === 'multiple' ? createScope.value.aquarium_ids.length > 0 : !!createForm.value.aquarium_id) &&
    !!createForm.value.title.trim() &&
    !!createForm.value.date &&
    (createForm.value.recurrence !== 'custom_days' || (createForm.value.recurrence_days ?? 0) > 0),
);

function openCreate(dayKey: string) {
  if (!can.edit) return;
  createForm.value = {
    aquarium_id: aquariumFilter.value ?? aquariumStore.aquariums[0]?.id ?? null,
    title: '',
    description: '',
    recurrence: 'none',
    recurrence_days: null,
    date: dayKey,
  };
  createScope.value = { scope: 'single', aquarium_ids: [] };
  createDialog.value = true;
}

async function createTask() {
  if (!canCreate.value) return;
  const scope = scopePayload(createScope.value, createForm.value.aquarium_id ?? 0);
  // Aquarium de rattachement : celui choisi, sinon le premier de la sélection
  const ownerId = createScope.value.scope === 'multiple' ? scope.aquarium_ids[0] : createForm.value.aquarium_id;
  if (!ownerId) return;
  saving.value = true;
  try {
    await taskStore.create({
      aquarium_id: ownerId,
      ...scope,
      title: createForm.value.title.trim(),
      description: createForm.value.description || null,
      recurrence: createForm.value.recurrence,
      recurrence_days: createForm.value.recurrence === 'custom_days' ? createForm.value.recurrence_days : null,
      next_due_at: `${createForm.value.date}T12:00:00`,
    });
    createDialog.value = false;
    $q.notify({ type: 'positive', message: t('tasks.notify.added') });
    await load();
  } catch {
    $q.notify({ type: 'negative', message: t('tasks.notify.createFailed') });
  } finally {
    saving.value = false;
  }
}

watch([currentMonth, aquariumFilter], () => void load());

onMounted(async () => {
  await Promise.all([aquariumStore.fetch(), load()]);
});
</script>

<style scoped>
.month-title {
  text-align: center;
  text-transform: capitalize;
}

/* Téléphone : le mois prend la place libre (une largeur fixe faisait déborder « Aujourd'hui ») */
@media (max-width: 599.98px) {
  .month-title {
    flex: 1 1 auto;
    min-width: 0;
    font-size: 1.1rem;
  }
}

@media (min-width: 600px) {
  .month-title {
    min-width: 170px;
  }
}

.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  border-radius: 12px;
  overflow: hidden;
}

.weekday {
  padding: 8px;
  text-align: center;
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
}

.day-cell {
  min-width: 0;
  overflow: hidden;
  min-height: 112px;
  padding: 6px;
  border-right: 1px solid rgba(0, 0, 0, 0.08);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  cursor: pointer;
  transition: background 0.15s ease;
}

.day-cell:nth-child(7n) {
  border-right: none;
}

.day-cell:hover {
  background: rgba(2, 123, 227, 0.04);
}

.day-cell .add-hint {
  opacity: 0;
  transition: opacity 0.15s ease;
}

.day-cell:hover .add-hint {
  opacity: 1;
}

.other-month {
  background: rgba(0, 0, 0, 0.02);
}

.other-month .day-number {
  color: #9e9e9e;
}

.day-number {
  font-weight: 600;
  font-size: 0.85rem;
  width: 24px;
  height: 24px;
  line-height: 24px;
  text-align: center;
  border-radius: 50%;
}

.today-number {
  background: var(--q-primary);
  color: white;
}

.event-chip {
  font-size: 0.75rem;
  padding: 2px 6px;
  border-radius: 4px;
  border-left: 3px solid transparent;
  cursor: pointer;
}

.event-chip:hover {
  filter: brightness(0.95);
}

.event-due {
  background: #e3f2fd;
  color: #0d47a1;
}

.event-overdue {
  background: #ffebee;
  color: #b71c1c;
  font-weight: 600;
}

.event-planned {
  background: transparent;
  color: #546e7a;
  border: 1px dashed #b0bec5;
}

.event-done {
  background: #e8f5e9;
  color: #1b5e20;
  text-decoration: line-through;
  text-decoration-color: rgba(27, 94, 32, 0.4);
}

.legend-swatch {
  display: inline-block;
  width: 14px;
  height: 10px;
  border-radius: 2px;
}

.aqua-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.more-link:hover {
  text-decoration: underline;
}
</style>
