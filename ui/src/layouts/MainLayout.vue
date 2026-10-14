<template>
  <q-layout view="lHh Lpr lFf">
    <q-header class="app-header">
      <q-toolbar>
        <!-- Mobile : retour sur les pages de détail, menu dans la barre du bas -->
        <q-btn v-if="isMobile && backLink" flat dense round icon="arrow_back" :aria-label="t('layout.back')" @click="goBack" />
        <q-btn v-else-if="!isMobile" flat dense round icon="menu" :aria-label="t('layout.menu')" @click="toggleLeftDrawer" />

        <q-toolbar-title class="row items-center no-wrap">
          <img v-if="!(isMobile && backLink)" :src="logoUrl" alt="" width="30" height="30" class="q-mr-sm" />
          <span class="text-weight-bold ellipsis">{{ isMobile ? mobileTitle : 'AquasManager' }}</span>
          <q-badge v-if="envLabel" :color="envColor" class="q-ml-sm" align="middle">
            {{ envLabel }}
          </q-badge>
        </q-toolbar-title>

        <!-- Hors connexion : état du réseau et écritures en attente d'envoi -->
        <q-btn
          v-if="!offline.online || offline.ops.length"
          flat
          round
          dense
          class="q-mr-xs"
          :icon="!offline.online ? 'cloud_off' : offline.syncing ? 'sync' : offline.failed.length ? 'sync_problem' : 'cloud_upload'"
          :aria-label="t('layout.sync')"
        >
          <q-badge v-if="offline.pending.length" color="orange-8" floating rounded>{{ offline.pending.length }}</q-badge>
          <q-menu anchor="bottom right" self="top right">
            <q-list style="min-width: 280px; max-width: 360px">
              <q-item>
                <q-item-section avatar>
                  <q-icon :name="offline.online ? 'cloud_done' : 'cloud_off'" :color="offline.online ? 'positive' : 'orange-8'" />
                </q-item-section>
                <q-item-section>
                  <q-item-label class="text-weight-bold">{{ offline.online ? t('layout.online') : t('layout.offline') }}</q-item-label>
                  <q-item-label caption>
                    {{ offline.pending.length ? t('layout.pending', offline.pending.length) : t('layout.nothingPending') }}
                  </q-item-label>
                </q-item-section>
              </q-item>
              <q-separator />
              <q-item v-for="op in offline.pending" :key="op.id" dense>
                <q-item-section avatar><q-icon name="schedule" size="xs" color="orange-8" /></q-item-section>
                <q-item-section>
                  <q-item-label>{{ op.label }}</q-item-label>
                  <q-item-label caption>{{ formatDateTime(op.created_at) }}</q-item-label>
                </q-item-section>
              </q-item>
              <q-item v-for="op in offline.failed" :key="op.id" dense>
                <q-item-section avatar><q-icon name="error" size="xs" color="negative" /></q-item-section>
                <q-item-section>
                  <q-item-label>{{ op.label }}</q-item-label>
                  <q-item-label caption class="text-negative">{{ op.error }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-btn flat round dense size="sm" icon="close" @click="offline.remove(op.id)"><q-tooltip>{{ t('layout.ignore') }}</q-tooltip></q-btn>
                </q-item-section>
              </q-item>
              <q-item v-if="offline.pending.length" v-close-popup clickable :disable="!offline.online || offline.syncing" @click="offline.flush()">
                <q-item-section avatar><q-icon name="sync" color="primary" /></q-item-section>
                <q-item-section class="text-primary">{{ t('layout.sendNow') }}</q-item-section>
              </q-item>
            </q-list>
          </q-menu>
        </q-btn>
        <q-btn v-if="isMobile && assistant.status.enabled" flat round dense icon="chat" :aria-label="t('layout.assistant')" class="q-mr-xs" @click="toggleChat" />
        <q-btn flat round dense>
          <q-avatar size="32px" color="primary" text-color="white" class="text-weight-bold">{{ initials }}</q-avatar>
          <q-menu anchor="bottom right" self="top right">
            <q-list style="min-width: 220px">
              <q-item>
                <q-item-section avatar>
                  <q-avatar size="36px" color="blue-1" text-color="primary">{{ initials }}</q-avatar>
                </q-item-section>
                <q-item-section>
                  <q-item-label class="text-weight-bold">{{ authStore.username }}</q-item-label>
                  <q-item-label caption>{{ roleLabel }}</q-item-label>
                </q-item-section>
              </q-item>

              <q-separator />

              <q-item>
                <q-item-section avatar><q-icon name="contrast" /></q-item-section>
                <q-item-section>
                  <q-btn-toggle
                    :model-value="themePreference"
                    dense
                    unelevated
                    spread
                    toggle-color="primary"
                    color="grey-2"
                    text-color="grey-8"
                    :options="[
                      { value: 'auto', icon: 'brightness_auto', slot: 'auto' },
                      { value: 'light', icon: 'light_mode', slot: 'light' },
                      { value: 'dark', icon: 'dark_mode', slot: 'dark' },
                    ]"
                    @update:model-value="setThemePreference"
                  >
                    <template #auto><q-tooltip>{{ t('layout.themeAuto') }}</q-tooltip></template>
                    <template #light><q-tooltip>{{ t('layout.themeLight') }}</q-tooltip></template>
                    <template #dark><q-tooltip>{{ t('layout.themeDark') }}</q-tooltip></template>
                  </q-btn-toggle>
                </q-item-section>
              </q-item>
              <q-item>
                <q-item-section avatar><q-icon name="translate" /></q-item-section>
                <q-item-section>
                  <LanguageSelect />
                </q-item-section>
              </q-item>
              <!-- Notifications push sur cet appareil -->
              <q-item v-if="pushAvailable" tag="label">
                <q-item-section avatar><q-icon name="notifications_active" /></q-item-section>
                <q-item-section>
                  <q-item-label>{{ t('layout.pushTitle') }}</q-item-label>
                  <q-item-label v-if="pushNeedsInstall" caption>{{ t('layout.pushNeedsInstall') }}</q-item-label>
                  <q-item-label v-else-if="push.blocked.value" caption>{{ t('layout.pushBlocked') }}</q-item-label>
                  <q-item-label v-else-if="push.subscribed.value" caption>
                    <a href="#" class="text-primary" @click.prevent="testPush">{{ t('layout.pushTest') }}</a>
                  </q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-toggle
                    :model-value="push.subscribed.value"
                    :disable="push.busy.value || pushNeedsInstall"
                    color="positive"
                    @update:model-value="togglePush"
                  />
                </q-item-section>
              </q-item>
              <q-item v-if="canInstall" v-close-popup clickable @click="install">
                <q-item-section avatar><q-icon name="install_mobile" /></q-item-section>
                <q-item-section>{{ t('layout.install') }}</q-item-section>
              </q-item>
              <q-item v-if="hub?.features" v-close-popup clickable @click="featureOpen = true">
                <q-item-section avatar><q-icon name="lightbulb" /></q-item-section>
                <q-item-section>{{ t('feature.action') }}</q-item-section>
              </q-item>
              <q-item v-close-popup clickable to="/change-password">
                <q-item-section avatar><q-icon name="password" /></q-item-section>
                <q-item-section>{{ t('layout.changePassword') }}</q-item-section>
              </q-item>
              <q-item v-close-popup clickable @click="authStore.logout">
                <q-item-section avatar><q-icon name="logout" /></q-item-section>
                <q-item-section>{{ t('layout.logout') }}</q-item-section>
              </q-item>
              <q-separator />
              <!-- Version en cours : permet de vérifier que l'appli est à jour -->
              <q-item v-close-popup clickable @click="checkForUpdate">
                <q-item-section avatar><q-icon :name="appUpdate.updateAvailable.value ? 'system_update' : 'verified'" :color="appUpdate.updateAvailable.value ? 'warning' : 'positive'" /></q-item-section>
                <q-item-section>
                  <q-item-label>{{ t('layout.version', { version: appUpdate.version }) }}</q-item-label>
                  <q-item-label caption>
                    {{ appUpdate.updateAvailable.value ? t('layout.updateAvailable') : t('layout.checkUpdates') }}
                  </q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </q-menu>
        </q-btn>
      </q-toolbar>
    </q-header>

    <q-drawer v-model="leftDrawerOpen" show-if-above bordered class="app-drawer">
      <q-list padding class="column full-height">
        <template v-for="item in menuItems" :key="item.title">
          <q-expansion-item
            v-if="item.children"
            :icon="item.icon"
            :label="item.title"
            default-opened
            expand-separator
          >
            <q-item
              v-for="child in item.children"
              :key="child.title"
              v-ripple
              clickable
              :to="child.link"
              active-class="app-drawer__active"
              class="q-pl-lg"
            >
              <q-item-section avatar>
                <q-icon :name="child.icon" />
              </q-item-section>
              <q-item-section>{{ child.title }}</q-item-section>
            </q-item>
          </q-expansion-item>
          <q-item v-else v-ripple clickable :to="item.link" active-class="app-drawer__active">
            <q-item-section avatar>
              <q-icon :name="item.icon" />
            </q-item-section>
            <q-item-section>{{ item.title }}</q-item-section>
          </q-item>
        </template>

        <q-space />

        <q-separator class="q-my-sm" />
        <q-item v-ripple clickable to="/licences">
          <q-item-section avatar>
            <q-icon name="gavel" />
          </q-item-section>
          <q-item-section>{{ t('nav.licences') }}</q-item-section>
        </q-item>
        <q-item v-ripple clickable :href="apiDocsUrl" target="_blank" rel="noopener">
          <q-item-section avatar>
            <q-icon name="school" />
          </q-item-section>
          <q-item-section>{{ t('nav.apiDocs') }}</q-item-section>
          <q-item-section side>
            <q-icon name="open_in_new" size="xs" />
          </q-item-section>
        </q-item>
      </q-list>
    </q-drawer>

    <!-- Mobile : navigation principale en bas, comme une appli -->
    <q-footer v-if="isMobile && !typing" bordered class="app-bottom-nav">
      <q-tabs
        :model-value="activeNav"
        no-caps
        dense
        class="text-grey-7"
        active-color="primary"
        indicator-color="transparent"
        align="justify"
      >
        <q-tab
          v-for="item in bottomNav"
          :key="item.name"
          :name="item.name"
          :icon="item.icon"
          :label="item.label"
          class="app-bottom-nav__tab"
          @click="item.link ? router.push(item.link) : (leftDrawerOpen = true)"
        >
          <q-badge v-if="item.badge" color="negative" floating rounded>{{ item.badge }}</q-badge>
        </q-tab>
      </q-tabs>
    </q-footer>

    <q-page-container>
      <div v-if="isDemo" class="demo-bar row items-center no-wrap q-px-md q-py-xs text-caption">
        <q-icon name="science" class="q-mr-sm" />
        <div class="col">{{ t('layout.demoBar') }}</div>
        <q-btn flat dense no-caps size="sm" :label="t('layout.demoInstall')" icon-right="open_in_new" href="https://aquasmanager.fr/docs/demarrer/installation/" target="_blank" />
      </div>
      <div v-if="appUpdate.updateAvailable.value" class="update-bar row items-center no-wrap q-px-md q-py-xs text-caption">
        <q-icon name="system_update" class="q-mr-sm" />
        <div class="col">{{ t('layout.updateBar') }}</div>
        <q-btn flat dense no-caps size="sm" :label="t('layout.update')" icon="refresh" @click="appUpdate.applyUpdate" />
      </div>
      <div v-if="!offline.online" class="offline-bar row items-center no-wrap q-px-md q-py-xs text-caption">
        <q-icon name="cloud_off" class="q-mr-sm" />
        {{ t('layout.offlineBar') }}
      </div>
      <q-pull-to-refresh :disable="!isMobile" color="primary" @refresh="refreshPage">
      <!-- Compte « bourse » : pas de bandeaux techniques devant le public -->
      <div v-if="openFaults.length > 0 && !can.seller" class="app-banners">
        <q-banner
          v-for="fault in openFaults"
          :key="fault.id"
          class="app-banner bg-red-1 text-red-10 q-mb-sm"
          rounded
        >
          <template v-slot:avatar>
            <q-icon name="report_problem" color="red-10" size="28px" />
          </template>
          <div class="text-weight-bold">{{ faultTitle(fault) }}</div>
          <div>{{ fault.message }}</div>

          <template v-slot:action>
            <q-btn
              v-if="can.edit && fault.latched && fault.equipment_id"
              unelevated
              color="red-10"
              text-color="white"
              :label="t('layout.faultReset')"
              icon="restart_alt"
              @click="clearFault(fault)"
            />
            <q-btn v-else-if="can.edit" flat color="red-10" :label="t('layout.faultDismiss')" icon="done" @click="acknowledgeFault(fault)" />
          </template>
        </q-banner>
      </div>

      <div v-if="bannerControllers.length > 0 && !can.seller && !can.caretaker" class="app-banners">
        <q-banner class="app-banner bg-amber-1 text-amber-10" rounded>
          <template #avatar>
            <q-icon :name="flashStore.active.length ? 'system_update' : 'warning'" color="amber-9" size="28px" />
          </template>
          <div class="text-weight-bold">
            {{ flashStore.active.length ? t('layout.flashInProgress') : t('layout.flashRequired') }}
          </div>
          <div v-if="dirtyControllers.length">{{ t('layout.flashConfigChanged') }}</div>

          <div class="column gap-xs q-mt-sm">
            <div v-for="ctrl in visibleBannerControllers" :key="ctrl.id" class="row items-center no-wrap gap-sm banner-row">
              <q-icon name="memory" size="18px" />
              <span class="text-weight-bold ellipsis" style="min-width: 110px">{{ ctrl.name }}</span>
              <template v-if="flashStore.isFlashing(ctrl.id)">
                <q-linear-progress
                  :value="(flashStore.progress[ctrl.id]?.percent ?? 0) / 100"
                  :indeterminate="flashStore.progress[ctrl.id]?.status === 'queued'"
                  rounded
                  size="8px"
                  color="amber-9"
                  track-color="amber-2"
                  class="col"
                />
                <span class="text-caption text-no-wrap">
                  {{ flashStore.progress[ctrl.id]?.phase }}
                  <template v-if="flashStore.progress[ctrl.id]?.status === 'running'">· {{ flashStore.progress[ctrl.id]?.percent }} %</template>
                </span>
              </template>
              <template v-else>
                <q-space />
                <q-btn
                  v-if="can.manage"
                  flat
                  dense
                  color="amber-10"
                  icon="system_update"
                  :label="t('layout.flash')"
                  :disable="!isOnline(ctrl)"
                  @click="flashController(ctrl)"
                >
                  <q-tooltip v-if="!isOnline(ctrl)">{{ t('layout.controllerOffline') }}</q-tooltip>
                </q-btn>
              </template>
            </div>
            <div v-if="hiddenBannerCount > 0" class="text-caption">
              {{ t('layout.otherControllers', hiddenBannerCount) }}
            </div>
          </div>

          <template #action>
            <q-btn
              v-if="can.manage && flashableDirty.length > 1"
              unelevated
              color="amber-9"
              text-color="white"
              icon="system_update"
              :label="t('layout.flashAll')"
              @click="flashAll"
            />
            <q-btn flat color="amber-10" :label="t('layout.seeControllers')" icon="memory" @click="openControllerPage" />
          </template>
        </q-banner>
      </div>

      <router-view :key="refreshCount" />
      </q-pull-to-refresh>
    </q-page-container>

    <!-- Mobile : l'assistant est dans l'en-tête (le bouton flottant masquerait les listes) -->
    <q-page-sticky v-if="!isMobile && assistant.status.enabled" position="bottom-right" :offset="[18, 18]">
      <q-btn fab icon="chat" color="primary" @click="toggleChat">
        <q-tooltip anchor="center left" self="center right">{{ t('layout.assistant') }}</q-tooltip>
      </q-btn>
    </q-page-sticky>

    <q-dialog
      v-model="isChatOpen"
      :position="isMobile ? 'standard' : 'right'"
      :seamless="!isMobile"
      :maximized="isMobile"
      :transition-show="isMobile ? 'slide-up' : undefined"
      :transition-hide="isMobile ? 'slide-down' : undefined"
    >
      <q-card :style="isMobile ? undefined : 'width: 360px; height: 600px; max-height: 85vh'" class="column app-chat">
        <q-card-section class="row items-center q-pb-none">
          <div class="text-h6 text-weight-bold">{{ t('layout.chatTitle') }}</div>
          <q-space />
          <q-btn icon="close" flat round dense v-close-popup :aria-label="t('common.close')" />
        </q-card-section>

        <q-card-section class="col q-pt-none scroll" id="chat-container">
          <div v-for="msg in messages" :key="msg.id">
            <q-chat-message
              :name="msg.author"
              :text="[msg.text]"
              :sent="msg.author === 'Me'"
              :stamp="formatDate(msg.stamp)"
              :bg-color="msg.author === 'Me' ? 'blue-7' : 'grey-3'"
              :text-color="msg.author === 'Me' ? 'white' : 'black'"
            />
          </div>
          <q-chat-message v-if="isLoading" name="Assistant" bg-color="grey-3">
            <q-spinner-dots size="2rem" />
          </q-chat-message>
        </q-card-section>

        <q-separator />

        <q-card-actions class="q-pa-md">
          <q-input
            rounded
            dense
            outlined
            v-model="userInput"
            :label="t('layout.chatPlaceholder')"
            class="full-width"
            @keyup.enter="handleSend"
            :disable="isLoading"
          >
            <template v-slot:after>
              <q-btn
                round
                flat
                icon="send"
                color="primary"
                @click="handleSend"
                :disable="!userInput.trim() || isLoading"
              />
            </template>
          </q-input>
        </q-card-actions>
      </q-card>
    </q-dialog>
    <!-- Visionneuse de PDF et d'images (certificats, documents d'achat…) -->
    <FileViewerDialog />
    <ProposeFeatureDialog v-model="featureOpen" />
  </q-layout>
</template>

<script setup lang="ts">
import logoUrl from 'src/assets/logo.png';
import { ref, computed, onBeforeUnmount, onMounted, watch } from 'vue';
import { useDynamicTitle } from 'src/composables/usePageTitle';
import { useOfflineStore } from 'src/stores/offlineStore';
import { needsInstallForPush, pushSupported, usePushNotifications } from 'src/composables/usePushNotifications';
import { formatDateTime } from 'src/utils/format';
import { useAuthStore } from 'src/stores/authStore';
import { useChatStore } from 'src/stores/chat';
import { useAssistantStore } from 'src/stores/assistantStore';
import { useAppUpdate } from 'src/composables/useAppUpdate';
import { useControllerStore } from 'src/stores/controllerStore';
import { useFaultStore, faultTitle, type EquipmentFault } from 'src/stores/faultStore';
import { useFlashStore } from 'src/stores/flashStore';
import { useWebSocketStore } from 'src/stores/websocket';
import { usePermissions } from 'src/composables/usePermissions';
import { useLicenseStore } from 'src/stores/licenseStore';
import { useTheme } from 'src/composables/useTheme';
import { useInstallPrompt } from 'src/composables/useInstallPrompt';
import type { Controller } from 'src/types/controller';
import { API_URL, APP_ENV } from 'src/utils/runtimeConfig';
import { useRoute, useRouter } from 'vue-router';
import { date, Notify, useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import LanguageSelect from 'src/components/LanguageSelect.vue';
import FileViewerDialog from 'src/components/FileViewerDialog.vue';
import ProposeFeatureDialog from 'src/components/ProposeFeatureDialog.vue';
import { useHubStatus } from 'src/utils/hub';
import { IS_DEMO as isDemo } from 'src/composables/useDemo';

const { t } = useI18n();
const authStore = useAuthStore();
// Idées de fonctionnalités : entrée du menu affichée si le hub de l'éditeur les accepte
const hub = useHubStatus();
const featureOpen = ref(false);
const chatStore = useChatStore();
// Nouvelle version publiée : bandeau « Mettre à jour » et version dans le menu
const appUpdate = useAppUpdate();

async function checkForUpdate() {
  if (appUpdate.updateAvailable.value) return appUpdate.applyUpdate();
  await appUpdate.check();
  $q.notify({
    type: appUpdate.updateAvailable.value ? 'warning' : 'positive',
    message: appUpdate.updateAvailable.value
      ? t('layout.notifyUpdateAvailable')
      : t('layout.notifyUpToDate', { version: appUpdate.version }),
  });
}
// Bouton de l'assistant seulement s'il est activé (Configuration › Assistant IA)
const assistant = useAssistantStore();
void assistant.fetchStatus();
const controllerStore = useControllerStore();
const faultStore = useFaultStore();
const flashStore = useFlashStore();
const wsStore = useWebSocketStore();
const can = usePermissions();
// Licence : fonctionnalités ouvertes (menus), relue à chaque ouverture de l'appli
const license = useLicenseStore();
onMounted(() => void license.refresh().catch(() => undefined));
const { preference: themePreference, setPreference: setThemePreference } = useTheme();
const { canInstall, install } = useInstallPrompt();
const router = useRouter();
const route = useRoute();
const $q = useQuasar();
const offline = useOfflineStore();

// --- Notifications push ---
const push = usePushNotifications();
const pushAvailable = pushSupported();
const pushNeedsInstall = pushAvailable && needsInstallForPush();

async function togglePush(enable: boolean) {
  try {
    if (enable) await push.enable();
    else await push.disable();
  } catch (err) {
    const denied = err instanceof Error && (err.name === 'NotAllowedError' || /denied|refus/i.test(err.message));
    $q.notify({
      type: 'negative',
      message: denied ? t('layout.pushDenied') : t('layout.pushUnavailable'),
    });
  }
}

async function testPush() {
  try {
    const devices = await push.test();
    $q.notify({ type: 'positive', message: t('layout.pushTestSent', devices) });
  } catch {
    $q.notify({ type: 'negative', message: t('layout.pushTestFailed') });
  }
}

onMounted(() => void push.refresh().catch(() => undefined));

// --- Mode mobile (téléphone, petite tablette) ---
const isMobile = computed(() => $q.screen.lt.md);
const dynamicTitle = useDynamicTitle();
// meta.title : clé de traduction (voir router/routes.ts)
const mobileTitle = computed(() => {
  const key = route.meta.title as string | undefined;
  return dynamicTitle.value ?? (key ? t(key) : 'AquasManager');
});
const backLink = computed(() => route.meta.back as string | undefined);

function goBack() {
  // Retour dans l'historique si on vient de l'appli, sinon page parente
  if (window.history.state?.back) router.back();
  else void router.push(backLink.value ?? '/home');
}

const activeNav = computed(() => {
  const path = route.path;
  if (path.startsWith('/home')) return 'home';
  if (path.startsWith('/myaquariums') || path.startsWith('/aquariums')) return 'aquariums';
  if (path.startsWith('/calendar')) return 'calendar';
  if (path.startsWith('/controllers')) return 'controllers';
  if (path.startsWith('/frags')) return 'frags';
  if (path.startsWith('/transfers')) return 'transfers';
  return 'more';
});

const bottomNav = computed(() => can.caretaker ? [
  { name: 'home', label: t('nav.home'), icon: 'home', link: '/home', badge: faultStore.openFaults.length || null },
  { name: 'aquariums', label: t('nav.aquariums'), icon: 'water', link: '/myaquariums', badge: null },
  { name: 'calendar', label: t('nav.calendar'), icon: 'event', link: '/calendar', badge: null },
  { name: 'more', label: t('nav.menu'), icon: 'menu', link: null, badge: null },
] : can.seller ? [
  { name: 'frags', label: t('nav.frags'), icon: 'content_cut', link: '/frags', badge: null },
  ...(can.bourse ? [{ name: 'transfers', label: t('nav.transfers'), icon: 'description', link: '/transfers', badge: null }] : []),
  { name: 'aquariums', label: t('nav.aquariums'), icon: 'water', link: '/myaquariums', badge: null },
  { name: 'more', label: t('nav.menu'), icon: 'menu', link: null, badge: null },
] : [
  { name: 'home', label: t('nav.home'), icon: 'home', link: '/home', badge: faultStore.openFaults.length || null },
  { name: 'aquariums', label: t('nav.aquariums'), icon: 'water', link: '/myaquariums', badge: null },
  { name: 'calendar', label: t('nav.calendar'), icon: 'event', link: '/calendar', badge: null },
  { name: 'controllers', label: t('nav.controllers'), icon: 'memory', link: '/controllers', badge: dirtyControllers.value.length || null },
  { name: 'more', label: t('nav.menu'), icon: 'menu', link: null, badge: null },
]);

// Saisie en cours (clavier ouvert) : la barre du bas est masquée, sinon
// certains téléphones la font remonter au-dessus du clavier
const typing = ref(false);
function isTextField(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el?.tagName) return false;
  if (el.tagName === 'TEXTAREA' || el.isContentEditable) return true;
  return el.tagName === 'INPUT' && !['checkbox', 'radio', 'button', 'submit', 'range', 'file'].includes((el as HTMLInputElement).type);
}
function onFocusIn(event: FocusEvent) {
  if (isTextField(event.target)) typing.value = true;
}
function onFocusOut() {
  // Laisser le focus passer d'un champ à l'autre sans faire clignoter la barre
  setTimeout(() => (typing.value = isTextField(document.activeElement)), 150);
}
onMounted(() => {
  document.addEventListener('focusin', onFocusIn);
  document.addEventListener('focusout', onFocusOut);
});
onBeforeUnmount(() => {
  document.removeEventListener('focusin', onFocusIn);
  document.removeEventListener('focusout', onFocusOut);
});

// Tirer vers le bas : recharge la page courante (ses données au montage)
const refreshCount = ref(0);
function refreshPage(done: () => void) {
  refreshCount.value++;
  void faultStore.fetchOpen();
  void controllerStore.fetch();
  setTimeout(done, 500);
}

// Notifications en haut sur mobile (la barre du bas masquerait le bas de l'écran)
watch(isMobile, (mobile) => Notify.setDefaults({ position: mobile ? 'top' : 'bottom-right', timeout: 3500 }), {
  immediate: true,
});
const isChatOpen = ref<boolean>(false);
const userInput = ref<string>('');

// Badge d'environnement affiché à côté du numéro de version, pour ne
// jamais confondre prod/recette/dev en un coup d'œil (important : cette
// app pilote de vrais équipements).
const ENV_META: Record<string, { label: string; color: string }> = {
  dev: { label: 'DEV', color: 'grey-7' },
  recette: { label: 'RECETTE', color: 'orange-8' },
  prod: { label: 'PROD', color: 'positive' },
  demo: { label: 'DEMO', color: 'purple-7' },
};
const appEnv = APP_ENV;
const envLabel = computed(() => ENV_META[appEnv]?.label ?? (appEnv || null));
const envColor = computed(() => ENV_META[appEnv]?.color ?? 'grey-7');

const roleLabel = computed(() => (authStore.role ? t(`roles.${authStore.role}`) : ''));
const apiDocsUrl = `${API_URL}/docs`;

interface MenuItem {
  title: string;
  icon: string;
  link?: string;
  children?: MenuItem[];
}

// Boutures pour tous ; Cessions (vente) seulement si la licence ouvre la bourse
const bourseMenu = (): MenuItem[] => [
  { title: t('nav.frags'), icon: 'content_cut', link: '/frags' },
  ...(can.bourse ? [{ title: t('nav.transfers'), icon: 'description', link: '/transfers' }] : []),
];

// Compte « bourse » : boutures, cessions et consultation des bacs (photos)
const sellerMenu = (): MenuItem[] => [
  ...bourseMenu(),
  { title: t('nav.documents'), icon: 'folder_shared', link: '/documents' },
  { title: t('nav.myAquariums'), icon: 'water', link: '/myaquariums' },
  { title: t('nav.species'), icon: 'menu_book', link: '/species' },
];

// Compte « gardiennage » : suivi du quotidien (tâches du jour, relevés)
const caretakerMenu = (): MenuItem[] => [
  { title: t('nav.home'), icon: 'home', link: '/home' },
  { title: t('nav.myAquariums'), icon: 'water', link: '/myaquariums' },
  { title: t('nav.calendar'), icon: 'event', link: '/calendar' },
];

const menuItems = computed<MenuItem[]>(() => can.seller ? sellerMenu() : can.caretaker ? caretakerMenu() : [
  { title: t('nav.home'), icon: 'home', link: '/home' },
  { title: t('nav.myAquariums'), icon: 'water', link: '/myaquariums' },
  { title: t('nav.calendar'), icon: 'event', link: '/calendar' },
  ...bourseMenu(),
  { title: t('nav.documents'), icon: 'folder_shared', link: '/documents' },
  { title: t('nav.groupOrders'), icon: 'local_shipping', link: '/commandes-groupees' },
  {
    title: t('nav.settings'),
    icon: 'settings',
    children: [
      { title: t('nav.controllers'), icon: 'memory', link: '/controllers' },
      { title: t('nav.species'), icon: 'menu_book', link: '/species' },
      ...(authStore.isAdmin
        ? [
            { title: t('nav.users'), icon: 'people', link: '/users' },
            { title: t('nav.notifications'), icon: 'notifications_active', link: '/notifications' },
            ...(can.assistant ? [{ title: t('nav.assistant'), icon: 'smart_toy', link: '/assistant-settings' }] : []),
            { title: t('nav.backup'), icon: 'backup', link: '/backup' },
            { title: t('nav.audit'), icon: 'manage_search', link: '/audit' },
            { title: t('nav.license'), icon: 'verified', link: '/license' },
          ]
        : []),
    ],
  },
]);

// Contrôleurs à reflasher, plus ceux en cours de flash (progression en direct)
const dirtyControllers = computed(() => controllerStore.controllers.filter((ctrl) => ctrl.is_dirty === true));
const bannerControllers = computed(() =>
  controllerStore.controllers.filter((ctrl) => ctrl.is_dirty === true || flashStore.isFlashing(ctrl.id)),
);

// Liste limitée (les flashs en cours d'abord) : le détail est sur la page Contrôleurs
const visibleBannerControllers = computed(() =>
  [...bannerControllers.value]
    .sort((a, b) => Number(flashStore.isFlashing(b.id)) - Number(flashStore.isFlashing(a.id)))
    .slice(0, isMobile.value ? 2 : 4),
);
const hiddenBannerCount = computed(() => bannerControllers.value.length - visibleBannerControllers.value.length);

function isOnline(ctrl: Controller): boolean {
  const status = wsStore.controllersState[ctrl.technical_name] ?? ctrl.status;
  return status !== 'OFFLINE';
}

const flashableDirty = computed(() =>
  dirtyControllers.value.filter((ctrl) => isOnline(ctrl) && !flashStore.isFlashing(ctrl.id)),
);

function flashController(ctrl: Controller) {
  flashStore.flash(ctrl.id, ctrl.ip).catch(() => undefined);
}

function flashAll() {
  // Les flashs s'enchaînent côté API (un à la fois)
  flashableDirty.value.forEach(flashController);
}

function openControllerPage() {
  void router.push('/controllers');
}

const openFaults = computed(() => faultStore.openFaults);

async function acknowledgeFault(fault: EquipmentFault) {
  try {
    await faultStore.acknowledge(fault.id);
  } catch {
    $q.notify({ type: 'negative', message: t('layout.faultAckFailed') });
  }
}

async function clearFault(fault: EquipmentFault) {
  if (!fault.equipment_id) return;
  try {
    await faultStore.clearEquipmentFault(fault.equipment_id);
    $q.notify({ type: 'positive', message: t('layout.faultResetSent') });
  } catch {
    $q.notify({ type: 'negative', message: t('layout.faultResetFailed') });
  }
}

onMounted(() => {
  void flashStore.fetchStatus().catch(() => undefined);
});

const leftDrawerOpen = ref(false);

// Mobile : le menu se referme après avoir choisi une page
watch(
  () => route.path,
  () => {
    if (isMobile.value) leftDrawerOpen.value = false;
  },
);

function toggleLeftDrawer() {
  leftDrawerOpen.value = !leftDrawerOpen.value;
}

const initials = computed(() => {
  if (!authStore.username) return '?';
  return authStore.username
    .split(/[\s._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0])
    .join('')
    .toUpperCase();
});

const toggleChat = () => {
  isChatOpen.value = !isChatOpen.value;
};
const messages = computed(() => chatStore.messages);
const isLoading = computed(() => chatStore.isLoading);
const handleSend = async (): Promise<void> => {
  if (!userInput.value.trim()) return;

  const text = userInput.value;
  userInput.value = '';
  await chatStore.sendMessage(text);
};

const formatDate = (val: Date) => {
  return date.formatDate(val, 'HH:mm');
};
</script>

<style scoped>
.app-banners {
  max-width: 1440px;
  margin: 0 auto;
  padding: 16px 16px 0;
}

.app-banner {
  border: 1px solid currentColor;
}

.banner-row {
  max-width: 720px;
}

.demo-bar {
  background: color-mix(in srgb, #7e57c2 16%, transparent);
  color: var(--app-ink);
}

.update-bar {
  background: color-mix(in srgb, var(--app-accent) 14%, transparent);
  color: var(--app-ink);
}

.offline-bar {
  background: #fff3e0;
  color: #8a4b00;
}

.body--dark .offline-bar {
  background: rgba(255, 152, 0, 0.16);
  color: #ffcc80;
}

.app-bottom-nav {
  background: #fff;
  padding-bottom: env(safe-area-inset-bottom);
}

.body--dark .app-bottom-nav {
  background: #1d2127;
}

.app-bottom-nav__tab {
  min-height: 56px;
  padding: 0 4px;
}

.app-bottom-nav :deep(.q-tab__label) {
  font-size: 11px;
}

.app-bottom-nav :deep(.q-tab__icon) {
  font-size: 24px;
}

.app-header {
  padding-top: env(safe-area-inset-top);
}

.app-drawer__active {
  color: var(--q-primary);
  background: rgba(25, 118, 210, 0.08);
  font-weight: 600;
}
</style>
