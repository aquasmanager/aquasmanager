<template>
  <q-page class="app-page">
    <!-- En-tête de l'aquarium -->
    <q-card v-if="aqua?.id" flat bordered class="overflow-hidden q-mb-md">
      <q-img :src="mainPhotoUrl(PhotoEntityType.aquariums, aqua.id, imageTimestamp)" :style="{ height: compactHero ? '140px' : '180px' }">
        <div class="absolute-full hero-overlay row items-end" :class="compactHero ? 'q-pa-md' : 'q-pa-lg'">
          <div class="row justify-between items-end full-width q-col-gutter-sm">
            <div class="col-12 col-sm">
              <div class="row items-center q-gutter-x-sm q-mb-xs">
                <q-badge color="teal-6" class="text-weight-bold q-px-sm q-py-xs">
                  {{ aqua.water_type === WaterType.sea ? t('aquariumInfo.sea') : t('aquariumInfo.fresh') }}
                </q-badge>
                <span class="text-white text-subtitle2">
                  <q-icon name="water_drop" size="16px" /> {{ aqua.volume }} L
                </span>
                <span v-if="aqua.biotope" class="text-white text-subtitle2">
                  <q-icon name="eco" size="16px" /> {{ aqua.biotope }}
                </span>
              </div>
              <div class="text-weight-bold text-white" :class="compactHero ? 'text-h5' : 'text-h4'">{{ aqua.name }}</div>
            </div>
            <div v-if="compactHero" class="absolute-top-right q-pa-sm row gap-sm">
              <q-btn round unelevated size="sm" color="white" text-color="primary" icon="photo_library" :aria-label="t('aquariums.page.photos')" @click="galleryOpen = true" />
              <q-btn round unelevated size="sm" color="white" text-color="primary" icon="info" :aria-label="t('aquariums.page.infos')" @click="showInfos()" />
              <q-btn round unelevated size="sm" color="white" text-color="orange-9" icon="construction" :aria-label="t('aquariums.maintenance.button')" @click="maintenanceOpen = true" />
            </div>
            <div v-else class="col-12 col-sm-auto row gap-sm">
              <q-btn unelevated color="white" text-color="primary" icon="photo_library" :label="t('aquariums.page.photos')" @click="galleryOpen = true" />
              <q-btn unelevated color="white" text-color="primary" icon="info" :label="t('aquariums.page.infos')" @click="showInfos()" />
              <q-btn unelevated color="white" text-color="orange-9" icon="construction" :label="t('aquariums.maintenance.button')" @click="maintenanceOpen = true" />
            </div>
          </div>
        </div>
      </q-img>
    </q-card>

    <!-- Mode maintenance (changement d'eau) : bandeau et fenêtre -->
    <AquariumMaintenance v-if="aqua?.id" v-model="maintenanceOpen" :aquarium-id="aqua.id" />

    <!-- Galerie de photos -->
    <PhotoGalleryDialog
      v-if="aqua?.id"
      v-model="galleryOpen"
      :entity-type="PhotoEntityType.aquariums"
      :entity-id="aqua.id"
      :entity-label="aqua.name"
      @main-changed="imageTimestamp = Date.now()"
    />

    <template v-if="aqua?.id">
      <!-- Mobile : section courante, les autres dans une feuille du bas -->
      <!-- Mobile : barre de sections toujours visible (collée sous l'en-tête),
           la grille complète dans une feuille du bas -->
      <div v-if="isMobile" ref="sectionAnchor" />
      <div v-if="isMobile" class="section-bar q-mb-md">
        <div ref="sectionBarScroll" class="section-bar__scroll">
          <button
            v-for="section in allSections"
            :key="section.name"
            v-ripple
            type="button"
            class="section-bar__item relative-position"
            :class="{ 'section-bar__item--active': section.name === tab }"
            :data-section="section.name"
            @click="selectSection(section.name)"
          >
            <q-icon :name="section.icon" size="22px" />
            <span>{{ section.label }}</span>
            <q-badge v-if="section.badge" color="negative" floating rounded>{{ section.badge }}</q-badge>
          </button>
        </div>
        <button v-ripple type="button" class="section-bar__all relative-position" :aria-label="t('aquariums.page.allSections')" @click="sectionSheet = true">
          <q-icon name="apps" size="22px" />
          <span>{{ t('aquariums.page.all') }}</span>
        </button>
      </div>

      <q-dialog v-model="sectionSheet" position="bottom">
        <q-card class="section-sheet">
          <div class="section-sheet__handle" />
          <div v-for="group in sectionGroups" :key="group.label" class="q-px-md q-pb-sm">
            <div class="text-caption text-weight-bold text-grey-7 q-mb-xs">{{ group.label }}</div>
            <div class="section-sheet__grid">
              <button
                v-for="section in group.items"
                :key="section.name"
                v-ripple
                type="button"
                class="section-sheet__item relative-position"
                :class="{ 'section-sheet__item--active': section.name === tab }"
                @click="selectSection(section.name)"
              >
                <q-icon :name="section.icon" size="26px" />
                <q-badge v-if="section.badge" color="negative" floating rounded>{{ section.badge }}</q-badge>
                <span>{{ section.label }}</span>
              </button>
            </div>
          </div>
        </q-card>
      </q-dialog>

      <!-- Navigation par onglets -->
      <q-card v-if="!isMobile" flat bordered class="q-mb-md">
        <q-tabs
          v-model="tab"
          dense
          class="text-grey-7"
          active-color="primary"
          indicator-color="primary"
          align="left"
          outside-arrows
          mobile-arrows
        >
          <q-tab name="dashboard" icon="dashboard" :label="t('aquariums.sections.dashboard')" />
          <q-tab name="parametres" icon="science" :label="t('aquariums.sections.parameters')" />
          <q-tab name="journal" icon="edit_note" :label="t('aquariums.sections.journal')" />
          <q-tab v-if="showCameras" name="cameras" icon="videocam" :label="t('aquariums.sections.cameras')" />
          <q-tab name="equipments" icon="settings_input_component" :label="t('aquariums.sections.equipments')" />
          <q-tab name="sensors" icon="sensors" :label="t('aquariums.sections.sensors')" />
          <q-tab name="lights" icon="lightbulb" :label="t('aquariums.sections.lights')" />
          <q-tab name="equipment_groups" icon="workspaces" :label="t('aquariums.sections.groups')" />
          <q-tab name="rights" icon="rule" :label="t('aquariums.sections.rules')" />
          <q-tab name="fishes" icon="set_meal" :label="t('aquariums.sections.fishes')" />
          <q-tab v-if="aqua.water_type === WaterType.sea" name="coraux" icon="grass" :label="t('aquariums.sections.corals')" />
          <q-tab v-if="aqua.water_type === WaterType.pure" name="plantes" icon="local_florist" :label="t('aquariums.sections.plants')" />
          <q-tab name="invertebrates" icon="pets" :label="t('aquariums.sections.invertebrates')" />
          <q-tab name="tasks" icon="task_alt" :label="t('aquariums.sections.tasks')" />
          <q-tab name="stock" icon="inventory_2" :label="t('aquariums.sections.stock')" />
          <q-tab name="water_changes" icon="water_drop" :label="t('aquariums.sections.waterChanges')" />
          <q-tab name="alerts">
            <div class="row items-center no-wrap">
              <q-icon name="notifications" size="24px" />
              <q-badge v-if="alertCount > 0" color="negative" floating rounded>{{ alertCount }}</q-badge>
            </div>
            <div class="q-tab__label">{{ t('aquariums.sections.alerts') }}</div>
          </q-tab>
          <q-tab name="history" icon="history" :label="t('aquariums.sections.history')" />
        </q-tabs>
      </q-card>

      <q-tab-panels v-model="tab" animated class="bg-transparent">
        <q-tab-panel name="dashboard" class="q-pa-none">
          <my-dashboard-page :aqua-id="aqua.id" :aquarium-name="aqua.name" />
        </q-tab-panel>
        <q-tab-panel name="parametres" class="q-pa-none">
          <my-water-parameters-page :aqua-id="aqua.id" />
        </q-tab-panel>
        <q-tab-panel v-if="showCameras" name="cameras" class="q-pa-none">
          <my-cameras-page :aqua-id="aqua.id" />
        </q-tab-panel>
        <q-tab-panel name="equipments" class="q-pa-none">
          <my-equipments-page :aqua-id="aqua.id" />
        </q-tab-panel>
        <q-tab-panel name="equipment_groups" class="q-pa-none">
          <my-equipment-groups-page :aqua-id="aqua.id" />
        </q-tab-panel>
        <q-tab-panel name="sensors" class="q-pa-none">
          <my-sensors-page :aqua-id="aqua.id" />
        </q-tab-panel>
        <q-tab-panel name="lights" class="q-pa-none">
          <my-lights-page :aqua-id="aqua.id" />
        </q-tab-panel>
        <q-tab-panel name="rights" class="q-pa-none">
          <my-rules-page :aqua-id="aqua.id" />
        </q-tab-panel>
        <q-tab-panel name="fishes" class="q-pa-none">
          <my-fishes-page :aqua-id="aqua.id" />
        </q-tab-panel>
        <q-tab-panel v-if="aqua.water_type === WaterType.sea" name="coraux" class="q-pa-none">
          <my-corals-page :aqua-id="aqua.id" />
        </q-tab-panel>
        <q-tab-panel v-if="aqua.water_type === WaterType.pure" name="plantes" class="q-pa-none">
          <my-plants-page :aqua-id="aqua.id" />
        </q-tab-panel>
        <q-tab-panel name="invertebrates" class="q-pa-none">
          <my-invertebrates-page :aqua-id="aqua.id" />
        </q-tab-panel>
        <q-tab-panel name="tasks" class="q-pa-none">
          <my-tasks-page :aqua-id="aqua.id" />
        </q-tab-panel>
        <q-tab-panel name="stock" class="q-pa-none">
          <my-stock-page :aqua-id="aqua.id" />
        </q-tab-panel>
        <q-tab-panel name="alerts" class="q-pa-none">
          <my-alerts-page :aqua-id="aqua.id" />
        </q-tab-panel>
        <q-tab-panel name="water_changes" class="q-pa-none">
          <AquariumWaterChanges :aqua-id="aqua.id" />
        </q-tab-panel>
        <q-tab-panel name="journal" class="q-pa-none">
          <AquariumJournal :aqua-id="aqua.id" />
        </q-tab-panel>
        <q-tab-panel name="history" class="q-pa-none">
          <my-alert-history-page :aqua-id="aqua.id" />
        </q-tab-panel>
      </q-tab-panels>
    </template>

    <div v-else-if="loading" class="flex flex-center q-pa-xl">
      <q-spinner color="primary" size="3em" />
    </div>

    <EmptyState v-else icon="search_off" :title="t('aquariums.page.notFound')" :message="t('aquariums.page.notFoundMessage')">
      <q-btn unelevated color="primary" icon="water" :label="t('aquariums.title')" to="/myaquariums" />
    </EmptyState>

    <!-- Modal d'informations -->
    <AquariumInfoDialog v-model="dialogInfos" :aquarium="aqua ?? null" />
  </q-page>
</template>

<style scoped>
.section-sheet {
  border-radius: 20px 20px 0 0 !important;
  padding-bottom: env(safe-area-inset-bottom);
  width: 100%;
  max-width: 640px;
}

.section-sheet__handle {
  width: 40px;
  height: 4px;
  border-radius: 2px;
  background: var(--app-border-color);
  margin: 10px auto 12px;
}

.section-sheet__grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
}

.section-sheet__item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 4px;
  border: 0;
  border-radius: 12px;
  background: transparent;
  color: inherit;
  font: inherit;
  font-size: 12px;
  line-height: 1.2;
  text-align: center;
  cursor: pointer;
}

.section-sheet__item--active {
  background: rgba(25, 118, 210, 0.12);
  color: var(--q-primary);
  font-weight: 600;
}

.section-bar {
  position: sticky;
  top: var(--app-sticky-top, 50px);
  z-index: 5;
  display: flex;
  align-items: stretch;
  gap: 4px;
  /* Bord à bord : annule la marge de la page sur mobile (12 px, cf. .app-page) */
  margin-left: -12px;
  margin-right: -12px;
  padding: 6px 8px;
  background: color-mix(in srgb, var(--app-page-bg, #fff) 88%, transparent);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--app-border-color);
}

.section-bar__scroll {
  display: flex;
  gap: 4px;
  flex: 1;
  overflow-x: auto;
  scrollbar-width: none;
  scroll-behavior: smooth;
}

.section-bar__scroll::-webkit-scrollbar {
  display: none;
}

.section-bar__item,
.section-bar__all {
  flex: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  min-width: 68px;
  padding: 6px 8px;
  border: 0;
  border-radius: 12px;
  background: transparent;
  color: inherit;
  font: inherit;
  font-size: 11px;
  line-height: 1.2;
  white-space: nowrap;
  cursor: pointer;
  opacity: 0.75;
}

.section-bar__item--active {
  opacity: 1;
  color: var(--app-accent, var(--q-primary));
  background: color-mix(in srgb, var(--app-accent, #0284c7) 16%, transparent);
  font-weight: 600;
}

.section-bar__all {
  min-width: 56px;
  opacity: 1;
  border-left: 1px solid var(--app-border-color);
  border-radius: 0 12px 12px 0;
}

.hero-overlay {
  background: linear-gradient(to top, rgba(0, 0, 0, 0.7) 0%, rgba(0, 0, 0, 0.2) 60%, rgba(0, 0, 0, 0) 100%);
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.6);
}
</style>

<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, computed, ref, watch } from 'vue';
import AquariumMaintenance from 'src/components/AquariumMaintenance.vue';
import AquariumJournal from 'src/components/AquariumJournal.vue';
import AquariumWaterChanges from 'src/components/AquariumWaterChanges.vue';
import { useRoute, useRouter } from 'vue-router';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import { usePageTitle } from 'src/composables/usePageTitle';
import { useAquariumStore } from '../stores/aquariumStore';
import { useEquipmentStore } from '../stores/equipmentStore';
import { useSensorStore } from '../stores/sensorStore';
import { useControllerStore } from 'src/stores/controllerStore';
import { useWebSocketStore } from 'src/stores/websocket';
import { WaterType } from 'src/types/Aquarium';
import MyDashboardPage from './MyDashboardPage.vue';
import MyWaterParametersPage from './MyWaterParametersPage.vue';
import MyTasksPage from './MyTasksPage.vue';
import MyStockPage from './MyStockPage.vue';
import MyCoralsPage from './MyCoralsPage.vue';
import MyFishesPage from './MyFishesPage.vue';
import MyEquipmentsPage from './MyEquipmentsPage.vue';
import MySensorsPage from './MySensorsPage.vue';
import MyPlantsPage from './MyPlantsPage.vue';
import MyInvertebratesPage from './MyInvertebratesPage.vue';
import MyLightsPage from './MyLightsPage.vue';
import MyRulesPage from './MyRulesPage.vue';
import MyAlertsPage from './MyAlertsPage.vue';
import MyAlertHistoryPage from './MyAlertHistoryPage.vue';
import MyEquipmentGroupsPage from './MyEquipmentGroupsPage.vue';
import MyCamerasPage from './MyCamerasPage.vue';
import { useCameraStore } from 'src/stores/cameraStore';
import { usePermissions } from 'src/composables/usePermissions';
import PhotoGalleryDialog from 'src/components/PhotoGalleryDialog.vue';
import AquariumInfoDialog from 'src/components/AquariumInfoDialog.vue';
import EmptyState from 'src/components/EmptyState.vue';
import { PhotoEntityType } from 'src/types/photo';
import { mainPhotoUrl } from 'src/stores/photoStore';

import { useRuleStore } from 'src/stores/ruleStore';
import { useEquipmentGroupStore } from 'src/stores/equipmentGroupStore';
import { useFaultStore } from 'src/stores/faultStore';
import { useMetricAlertStore } from 'src/stores/metricAlertStore';

const { t } = useI18n();
const route = useRoute();
const aquariumStore = useAquariumStore();
const equipmentStore = useEquipmentStore();
const sensorStore = useSensorStore();
const controllerStore = useControllerStore();
const equipmentGroupStore = useEquipmentGroupStore();
const ruleStore = useRuleStore();
const wsStore = useWebSocketStore();
const faultStore = useFaultStore();
const metricAlertStore = useMetricAlertStore();
const cameraStore = useCameraStore();
const can = usePermissions();
// Caméras : seulement si le service vidéo est installé, jamais pour le compte « bourse »
const showCameras = computed(() => !!cameraStore.status?.enabled && !can.seller);

const dialogInfos = ref(false);
const loading = ref(true);
const aquariumId = computed(() => Number(route.params.id));
const tab = ref(typeof route.query.tab === 'string' ? route.query.tab : 'dashboard');
const router = useRouter();
const $q = useQuasar();
const isMobile = computed(() => $q.screen.lt.md);
const compactHero = computed(() => $q.screen.lt.sm);
const sectionSheet = ref(false);

// L'onglet courant est gardé dans l'URL (retour, rechargement, tirer pour rafraîchir)
watch(tab, (value) => {
  if (route.query.tab !== value) void router.replace({ query: { ...route.query, tab: value } });
});

interface Section {
  name: string;
  label: string;
  icon: string;
  badge?: number | null;
}

const sectionGroups = computed<{ label: string; items: Section[] }[]>(() => [
  {
    label: t('aquariums.groups.monitoring'),
    items: [
      { name: 'dashboard', label: t('aquariums.sections.dashboard'), icon: 'dashboard' },
      { name: 'parametres', label: t('aquariums.sections.parameters'), icon: 'science' },
      { name: 'journal', label: t('aquariums.sections.journal'), icon: 'edit_note' },
      ...(showCameras.value ? [{ name: 'cameras', label: t('aquariums.sections.cameras'), icon: 'videocam' }] : []),
      { name: 'alerts', label: t('aquariums.sections.alerts'), icon: 'notifications', badge: alertCount.value || null },
      { name: 'history', label: t('aquariums.sections.history'), icon: 'history' },
    ],
  },
  {
    label: t('aquariums.groups.technical'),
    items: [
      { name: 'equipments', label: t('aquariums.sections.equipments'), icon: 'settings_input_component' },
      { name: 'sensors', label: t('aquariums.sections.sensors'), icon: 'sensors' },
      { name: 'lights', label: t('aquariums.sections.lights'), icon: 'lightbulb' },
      { name: 'equipment_groups', label: t('aquariums.sections.groups'), icon: 'workspaces' },
      { name: 'rights', label: t('aquariums.sections.rules'), icon: 'rule' },
    ],
  },
  {
    label: t('aquariums.groups.livestock'),
    items: [
      { name: 'fishes', label: t('aquariums.sections.fishes'), icon: 'set_meal' },
      aqua.value?.water_type === WaterType.pure
        ? { name: 'plantes', label: t('aquariums.sections.plants'), icon: 'local_florist' }
        : { name: 'coraux', label: t('aquariums.sections.corals'), icon: 'grass' },
      { name: 'invertebrates', label: t('aquariums.sections.invertebrates'), icon: 'pets' },
    ],
  },
  {
    label: t('aquariums.groups.care'),
    items: [
      { name: 'tasks', label: t('aquariums.sections.tasks'), icon: 'task_alt' },
      { name: 'stock', label: t('aquariums.sections.stock'), icon: 'inventory_2' },
      { name: 'water_changes', label: t('aquariums.sections.waterChanges'), icon: 'water_drop' },
    ],
  },
]);

const allSections = computed(() => sectionGroups.value.flatMap((g) => g.items));

// Barre de sections (mobile) : la section active est ramenée au centre
const sectionBarScroll = ref<HTMLElement | null>(null);
function centerActiveSection() {
  const bar = sectionBarScroll.value;
  const item = bar?.querySelector<HTMLElement>(`[data-section="${tab.value}"]`);
  if (!bar || !item) return;
  bar.scrollLeft = item.offsetLeft - bar.clientWidth / 2 + item.clientWidth / 2;
}
watch([tab, sectionBarScroll], () => void nextTick(centerActiveSection));

// Changement de section : la page se cale sous la barre de sections (la photo
// du bac n'est pas réaffichée) ; si on était encore en haut, rien ne bouge
const sectionAnchor = ref<HTMLElement | null>(null);
function selectSection(name: string) {
  tab.value = name;
  sectionSheet.value = false;
  const anchor = sectionAnchor.value;
  if (!anchor) return;
  const headerHeight = document.querySelector('.q-header')?.getBoundingClientRect().height ?? 50;
  const target = anchor.getBoundingClientRect().top + window.scrollY - headerHeight;
  if (window.scrollY > target) window.scrollTo({ top: target });
}

// faultStore.openFaults est déjà alimenté globalement (App.vue) via
// websocket : juste besoin de le restreindre aux équipements de cet
// aquarium. metricAlertStore.openAlerts est un état partagé (comme
// faultStore) : un acquittement depuis n'importe quelle page se répercute
// ici immédiatement, sans attendre le prochain poll.
let metricAlertRefreshInterval: number | null = null;
const alertCount = computed(() => {
  const equipmentIds = new Set(equipmentStore.getByAquariumId(aquariumId.value).map((e) => e.id));
  const faultCount = faultStore.openFaults.filter((f) => f.equipment_id != null && equipmentIds.has(f.equipment_id)).length;
  return faultCount + metricAlertStore.openAlerts.length;
});
const imageTimestamp = ref(Date.now());
const galleryOpen = ref(false);
const maintenanceOpen = ref(false);
const aqua = computed(() => aquariumStore.getById(aquariumId.value));
usePageTitle(computed(() => aqua.value?.name));


function showInfos() {
  dialogInfos.value = true;
}

onMounted(async () => {
  void cameraStore.fetchStatus().catch(() => undefined);
  try {
    // 1. Charger l'aquarium globalement
    await aquariumStore.fetch();

    // 2. Charger les contrôleurs, équipements et capteurs en parallèle (ou séquentiel)
    await Promise.all([
      controllerStore.fetch(),
      equipmentStore.fetch(),
      sensorStore.fetch(),
      equipmentGroupStore.fetch(),
      ruleStore.fetch()
    ]);

    // 3. Hydrater l'état des contrôleurs pour le WebSocket (évite le "Hors-ligne")
    controllerStore.controllers.forEach((ctrl) => {
      if (ctrl.technical_name) {
        wsStore.controllersState[ctrl.technical_name] = ctrl.status || 'OFFLINE';
      }
    });

    // 4. Hydrater l'état des capteurs pour cet aquarium
    const currentSensors = sensorStore.getByAquariumId(aquariumId.value);
    currentSensors.forEach((sensor) => {
      if (sensor.id !== undefined && sensor.last_value !== null && sensor.last_value !== undefined) {
        wsStore.sensorsState[Number(sensor.id)] = Number(sensor.last_value);
      }
    });

    // 5. Hydrater l'état des équipements pour cet aquarium
    const currentEquipments = equipmentStore.getByAquariumId(aquariumId.value);
    currentEquipments.forEach((eq) => {
      if (eq.id !== undefined && eq.status !== undefined) {
        wsStore.equipmentsState[Number(eq.id)] = eq.status;
      }
    });

    // 6. Alertes ouvertes (badge de l'onglet Alertes)
    await metricAlertStore.fetchOpen(aquariumId.value);
    await faultStore.fetchOpen();
  } catch (error) {
    console.error("❌ Erreur lors du chargement initial de la page parente :", error);
  } finally {
    loading.value = false;
  }

  // L'évaluation des alertes métriques tourne toutes les 5 min côté API :
  // sans ce polling, le badge resterait figé sur sa valeur au chargement
  // tant que la page n'est pas rechargée. Les défauts équipement, eux,
  // sont déjà mis à jour en direct via websocket (faultStore). Un
  // acquittement manuel, lui, met à jour l'état partagé immédiatement
  // (voir metricAlertStore.acknowledge) sans attendre ce polling.
  metricAlertRefreshInterval = window.setInterval(() => {
    void metricAlertStore.fetchOpen(aquariumId.value);
  }, 60_000);
});

onUnmounted(() => {
  if (metricAlertRefreshInterval !== null) window.clearInterval(metricAlertRefreshInterval);
});
</script>
