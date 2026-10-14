<template>
  <q-page class="app-page">
    <PageHeader icon="home" :title="authStore.username ? t('home.helloName', { name: authStore.username }) : t('home.hello')" :subtitle="todayLabel">
      <template #actions>
        <q-btn flat round dense icon="refresh" color="grey-7" :loading="loading" @click="load">
          <q-tooltip>{{ t('home.refresh') }}</q-tooltip>
        </q-btn>
      </template>
    </PageHeader>

    <div v-if="loading && !overview" class="flex flex-center q-pa-xl">
      <q-spinner color="primary" size="3em" />
    </div>

    <template v-else-if="overview">
      <!-- Compteurs -->
      <div class="row q-col-gutter-md q-mb-lg">
        <div v-for="stat in stats" :key="stat.label" class="col-6 col-sm-4 col-md">
          <q-card flat bordered class="full-height">
            <!-- Téléphone : icône plus petite, libellé sur deux lignes plutôt que coupé (« Contrôle… ») -->
            <q-card-section class="row items-center no-wrap" :class="$q.screen.lt.sm ? 'q-gutter-x-sm q-px-sm' : 'q-gutter-x-md'">
              <q-avatar :color="stat.bg" :text-color="stat.color" :icon="stat.icon" :size="$q.screen.lt.sm ? '36px' : '44px'" />
              <div class="col" style="min-width: 0">
                <div class="text-h5 text-weight-bold" :class="stat.valueClass">{{ stat.value }}</div>
                <div class="text-caption text-grey-7 stat-label">{{ stat.label }}</div>
              </div>
            </q-card-section>
            <q-tooltip v-if="stat.tooltip">{{ stat.tooltip }}</q-tooltip>
          </q-card>
        </div>
      </div>

      <div class="row q-col-gutter-lg">
        <!-- Aquariums -->
        <div class="col-12 col-lg-8">
          <div class="text-subtitle1 text-weight-bold q-mb-sm">{{ t('home.myAquariums') }}</div>

          <EmptyState
            v-if="overview.aquariums.length === 0"
            icon="water"
            :title="t('home.emptyTitle')"
            :message="t('home.emptyMessage')"
          >
            <q-btn unelevated color="primary" icon="add" :label="t('home.createAquarium')" to="/myaquariums" />
          </EmptyState>

          <div class="row q-col-gutter-md">
            <div v-for="aqua in overview.aquariums" :key="aqua.id" class="col-12 col-sm-6">
              <q-card flat bordered class="hover-card full-height cursor-pointer overflow-hidden" @click="goTo(aqua.id)">
                <q-img :src="mainPhotoUrl(PhotoEntityType.aquariums, aqua.id, photoStamp)" :ratio="16 / 7">
                  <div class="absolute-bottom row items-end justify-between no-wrap">
                    <div>
                      <div class="text-subtitle1 text-weight-bold">{{ aqua.name }}</div>
                      <div class="text-caption">{{ waterTypeLabel(aqua.water_type) }} · {{ aqua.volume }} L</div>
                    </div>
                    <q-badge
                      :color="aquaHealth(aqua).color"
                      :label="aquaHealth(aqua).label"
                      class="text-weight-bold q-pa-xs"
                    />
                  </div>
                </q-img>

                <q-card-section class="q-pb-sm">
                  <div class="row items-center justify-between no-wrap">
                    <div v-if="aqua.temperature" class="row items-baseline no-wrap">
                      <q-icon name="thermostat" color="red-7" size="sm" class="self-center q-mr-xs" />
                      <span class="text-h5 text-weight-bold">{{ formatTemp(liveTemp(aqua)) }}</span>
                      <span class="text-grey-7 q-ml-xs">°C</span>
                      <q-chip v-if="isTempLive(aqua)" dense size="sm" color="red-1" text-color="red-8" class="q-ml-sm">
                        <span class="live-dot q-mr-xs" />{{ t('home.live') }}
                      </q-chip>
                    </div>
                    <div v-else class="text-caption text-grey-6">{{ t('home.noTempProbe') }}</div>
                    <div class="text-caption text-grey-7 text-right">
                      <q-icon name="pets" size="xs" /> {{ t('home.livestock', aqua.livestock) }}
                    </div>
                  </div>
                </q-card-section>

                <q-card-section class="q-pt-none">
                  <div class="row q-gutter-xs">
                    <q-chip
                      v-if="aqua.open_alerts > 0"
                      clickable
                      dense
                      color="red-1"
                      text-color="negative"
                      icon="notifications_active"
                      @click.stop="goTo(aqua.id, 'alerts')"
                    >
                      {{ t('home.alerts', aqua.open_alerts) }}
                    </q-chip>
                    <q-chip
                      v-if="aqua.out_of_target_parameters.length > 0"
                      clickable
                      dense
                      color="orange-1"
                      text-color="orange-9"
                      icon="science"
                      @click.stop="goTo(aqua.id, 'parametres', { filtre: 'hors-cible' })"
                    >
                      {{ t('home.outOfTarget', { n: aqua.out_of_target_parameters.length }) }}
                      <q-tooltip max-width="260px">{{ aqua.out_of_target_parameters.join(', ') }}</q-tooltip>
                    </q-chip>
                    <q-chip
                      v-if="aqua.overdue_tasks > 0"
                      clickable
                      dense
                      color="deep-orange-1"
                      text-color="deep-orange-9"
                      icon="event_busy"
                      @click.stop="goTo(aqua.id, 'tasks')"
                    >
                      {{ t('home.overdueTasks', aqua.overdue_tasks) }}
                    </q-chip>
                    <q-chip
                      v-if="aqua.low_stock_items > 0"
                      clickable
                      dense
                      color="amber-1"
                      text-color="amber-10"
                      icon="inventory_2"
                      @click.stop="goTo(aqua.id, 'stock', { filtre: 'stock-bas' })"
                    >
                      {{ t('home.lowStock', aqua.low_stock_items) }}
                    </q-chip>
                    <q-chip v-if="aquaHealth(aqua).ok" dense color="green-1" text-color="positive" icon="check_circle">
                      {{ t('home.allGood') }}
                    </q-chip>
                  </div>
                  <div class="text-caption text-grey-6 q-mt-sm">
                    {{ t('home.lastReading', { date: aqua.last_reading_at ? formatDate(aqua.last_reading_at) : t('home.noReading') }) }}
                  </div>
                </q-card-section>
              </q-card>
            </div>
          </div>
        </div>

        <!-- À faire -->
        <div class="col-12 col-lg-4">
          <div class="text-subtitle1 text-weight-bold q-mb-sm">{{ t('home.todo') }}</div>
          <div class="column gap-md">
          <!-- Alertes ouvertes : mesures hors cible, capteurs muets, défauts d'équipement -->
          <q-card flat bordered class="todo-card" :class="{ 'todo-card--alert': alertCount > 0 }">
            <div class="todo-card__head row items-center no-wrap">
              <q-icon name="notifications_active" :color="alertCount ? 'negative' : 'grey-6'" size="20px" class="q-mr-sm" />
              <div class="text-subtitle2 text-weight-bold col">{{ t('home.openAlerts') }}</div>
              <q-badge v-if="alertCount" color="negative" rounded :label="alertCount" />
            </div>
            <q-list separator>
              <q-item v-if="!alertCount">
                <q-item-section avatar><q-icon name="check_circle" color="positive" /></q-item-section>
                <q-item-section class="text-grey-7">{{ t('home.noAlerts') }}</q-item-section>
              </q-item>
              <q-item
                v-for="alert in overview.todo.alerts ?? []"
                :key="`${alert.kind}${alert.id}`"
                :clickable="alert.aquarium_id != null"
                @click="alert.aquarium_id != null && goTo(alert.aquarium_id, 'alerts')"
              >
                <q-item-section avatar>
                  <q-icon :name="alert.kind === 'metric' ? METRIC_ALERT_ICONS[alert.source] : 'report_problem'" color="negative" />
                </q-item-section>
                <q-item-section>
                  <q-item-label>{{ alert.kind === 'metric' ? alert.label : alertFaultTitle(alert) }}</q-item-label>
                  <q-item-label caption>
                    {{ alert.kind === 'metric' ? metricAlertMessage(alert) : alert.message }}<template v-if="alert.aquarium_name"> · {{ alert.aquarium_name }}</template>
                  </q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-item-label caption>{{ sinceLabel(alert.created_at) }}</q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </q-card>

          <!-- Tâches à venir -->
          <q-card flat bordered class="todo-card">
            <div class="todo-card__head row items-center no-wrap">
              <q-icon name="event" color="primary" size="20px" class="q-mr-sm" />
              <div class="text-subtitle2 text-weight-bold col">{{ t('home.upcomingTasks', { n: DUE_SOON_DAYS }) }}</div>
              <q-badge v-if="overview.todo.tasks.length" :color="overdueCount ? 'negative' : 'primary'" rounded :label="overview.todo.tasks.length" />
            </div>
            <q-list separator>
              <q-item v-if="overview.todo.tasks.length === 0">
                <q-item-section class="text-grey-6">{{ t('home.noTasks') }}</q-item-section>
              </q-item>
              <q-item
                v-for="task in overview.todo.tasks"
                :key="`t${task.id}`"
                clickable
                @click="goTo(task.aquarium_id, 'tasks')"
              >
                <q-item-section avatar>
                  <q-icon :name="task.overdue ? 'event_busy' : 'event'" :color="task.overdue ? 'negative' : 'primary'" />
                </q-item-section>
                <q-item-section>
                  <q-item-label>{{ task.title }}</q-item-label>
                  <q-item-label caption><q-icon v-if="task.shared" name="join_inner" size="14px" class="q-mr-xs" />{{ task.aquarium_name }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-item-label caption :class="task.overdue ? 'text-negative text-weight-bold' : ''">
                    {{ dueLabel(task.next_due_at) }}
                  </q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </q-card>

          <!-- Stock à racheter -->
          <q-card flat bordered class="todo-card">
            <div class="todo-card__head row items-center no-wrap">
              <q-icon name="inventory_2" color="amber-9" size="20px" class="q-mr-sm" />
              <div class="text-subtitle2 text-weight-bold col">{{ t('home.restock') }}</div>
              <q-badge v-if="overview.todo.low_stock.length" color="amber-9" rounded :label="overview.todo.low_stock.length" />
            </div>
            <q-list separator>
              <q-item v-if="overview.todo.low_stock.length === 0">
                <q-item-section class="text-grey-6">{{ t('home.stockOk') }}</q-item-section>
              </q-item>
              <q-item
                v-for="item in overview.todo.low_stock"
                :key="`s${item.id}`"
                clickable
                @click="goTo(item.aquarium_id, 'stock', { filtre: 'stock-bas' })"
              >
                <q-item-section avatar>
                  <q-icon name="inventory_2" color="amber-9" />
                </q-item-section>
                <q-item-section>
                  <q-item-label>{{ item.name }}</q-item-label>
                  <q-item-label caption><q-icon v-if="item.shared" name="join_inner" size="14px" class="q-mr-xs" />{{ item.aquarium_name }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-item-label caption class="text-amber-10 text-weight-bold">
                    {{ formatNumber(item.quantity) }} {{ item.unit }}
                  </q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </q-card>
          </div>
        </div>
      </div>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import { intlLocale } from 'src/i18n/instance';
import { formatDate, formatNumber } from 'src/utils/format';
import { useAuthStore } from 'src/stores/authStore';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import { useWebSocketStore } from 'src/stores/websocket';
import { mainPhotoUrl } from 'src/stores/photoStore';
import { PhotoEntityType } from 'src/types/photo';
import type { Overview, OverviewAlert, OverviewAquarium, OverviewController } from 'src/types/overview';
import { METRIC_ALERT_ICONS, metricAlertMessage } from 'src/types/metricAlert';
import { faultTitle } from 'src/stores/faultStore';

const DUE_SOON_DAYS = 7;
const REFRESH_MS = 60_000;

const { t } = useI18n();
const router = useRouter();
const $q = useQuasar();
const authStore = useAuthStore();
const wsStore = useWebSocketStore();

const overview = ref<Overview | null>(null);
const loading = ref(false);
const photoStamp = Date.now();
let refreshTimer: ReturnType<typeof setInterval> | undefined;

const todayLabel = computed(() => {
  const raw = new Date().toLocaleDateString(intlLocale(), { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  return raw.charAt(0).toUpperCase() + raw.slice(1);
});

async function load() {
  loading.value = true;
  try {
    const { data } = await axios.get<Overview>('/overview/');
    overview.value = data;
  } catch {
    $q.notify({ type: 'negative', message: t('home.loadFailed') });
  } finally {
    loading.value = false;
  }
}

function controllerStatus(c: OverviewController): string {
  return wsStore.controllersState[`controller_${c.id}`] ?? wsStore.controllersState[c.technical_name] ?? c.status;
}

const stats = computed(() => {
  if (!overview.value) return [];
  const { counts, controllers } = overview.value;
  const online = controllers.filter((c) => controllerStatus(c) === 'ONLINE').length;
  const livestock = counts.fishes + counts.corals + counts.plants + counts.invertebrates;
  const livestockDetail = [
    counts.fishes && t('home.stats.fishes', counts.fishes),
    counts.corals && t('home.stats.corals', counts.corals),
    counts.plants && t('home.stats.plants', counts.plants),
    counts.invertebrates && t('home.stats.invertebrates', counts.invertebrates),
  ].filter(Boolean);

  return [
    { label: t('home.stats.aquariums'), value: counts.aquariums, icon: 'water', color: 'primary', bg: 'blue-1' },
    {
      label: t('home.stats.controllersOnline'),
      value: `${online}/${controllers.length}`,
      icon: 'memory',
      color: online === controllers.length ? 'positive' : 'negative',
      bg: online === controllers.length ? 'green-1' : 'red-1',
      tooltip: controllers
        .map((c) => `${c.name} : ${controllerStatus(c) === 'ONLINE' ? t('home.stats.online') : t('home.stats.offline')}`)
        .join(' · '),
    },
    { label: t('home.stats.equipments'), value: counts.equipments, icon: 'settings_input_component', color: 'teal', bg: 'teal-1' },
    {
      label: t('home.stats.livestock'),
      value: livestock,
      icon: 'set_meal',
      color: 'purple',
      bg: 'purple-1',
      tooltip: livestockDetail.join(' · ') || undefined,
    },
    {
      label: t('home.stats.openAlerts'),
      value: counts.open_alerts,
      icon: 'notifications_active',
      color: counts.open_alerts > 0 ? 'negative' : 'grey-6',
      bg: counts.open_alerts > 0 ? 'red-1' : 'grey-2',
      valueClass: counts.open_alerts > 0 ? 'text-negative' : '',
    },
  ];
});

function aquaHealth(aqua: OverviewAquarium) {
  if (aqua.open_alerts > 0) return { label: t('home.health.alert'), color: 'negative', ok: false };
  if (aqua.out_of_target_parameters.length > 0 || aqua.overdue_tasks > 0 || aqua.low_stock_items > 0) {
    return { label: t('home.health.watch'), color: 'orange-8', ok: false };
  }
  return { label: t('home.health.ok'), color: 'positive', ok: true };
}

function liveTemp(aqua: OverviewAquarium): number | null {
  if (!aqua.temperature) return null;
  const live = wsStore.sensorsState[aqua.temperature.sensor_id];
  // null : la sonde ne répond plus, pas d'ancienne valeur affichée
  return live !== undefined ? live : aqua.temperature.value;
}

function isTempLive(aqua: OverviewAquarium): boolean {
  return !!aqua.temperature && wsStore.sensorsState[aqua.temperature.sensor_id] !== undefined;
}

function formatTemp(value: number | null): string {
  return value == null ? '--' : Number(value).toFixed(1);
}

function waterTypeLabel(type: string): string {
  return type === 'sea' ? t('aquariumInfo.sea') : type === 'pure' ? t('aquariumInfo.fresh') : type;
}

function dueLabel(dateStr: string): string {
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((startOfDay(new Date(dateStr)) - startOfDay(new Date())) / 86_400_000);
  if (days < -1) return t('time.overdueDays', { n: -days });
  if (days === -1) return t('time.yesterday');
  if (days === 0) return t('time.today');
  if (days === 1) return t('time.tomorrow');
  return t('time.inDays', { n: days });
}

// Défaut d'équipement : type de défaut, et l'équipement concerné
const alertCount = computed(() => overview.value?.todo.alerts?.length ?? 0);
const overdueCount = computed(() => overview.value?.todo.tasks.filter((task) => task.overdue).length ?? 0);

function alertFaultTitle(alert: Extract<OverviewAlert, { kind: 'fault' }>): string {
  const title = faultTitle({ ...alert, controller_id: 0, equipment_id: null, latched: false, resolved_at: null });
  return alert.equipment_name ? `${title} · ${alert.equipment_name}` : title;
}

// Depuis quand : heure si aujourd'hui, sinon date
function sinceLabel(value: string): string {
  const at = new Date(value);
  return at.toDateString() === new Date().toDateString()
    ? at.toLocaleTimeString(intlLocale(), { hour: '2-digit', minute: '2-digit' })
    : formatDate(value);
}

function goTo(aquariumId: number, tab?: string, extraQuery: Record<string, string> = {}) {
  void router.push({ path: `/aquariums/${aquariumId}`, query: { ...(tab ? { tab } : {}), ...extraQuery } });
}

onMounted(() => {
  void load();
  refreshTimer = setInterval(() => void load(), REFRESH_MS);
});

onUnmounted(() => clearInterval(refreshTimer));
</script>

<style scoped>
.todo-card__head {
  padding: 12px 16px 8px;
}

/* Alertes en cours : bordure et en-tête rouges pour les repérer d'un coup d'œil */
.todo-card--alert {
  border-color: var(--q-negative);
}

.todo-card--alert .todo-card__head {
  background: color-mix(in srgb, var(--q-negative) 8%, transparent);
}

.live-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  animation: live-pulse 1.5s ease-in-out infinite;
}

@keyframes live-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}

.stat-label {
  line-height: 1.2;
  overflow-wrap: anywhere;
}
</style>
