<!--
  Vitrine : réservations reçues, liens de partage (une bourse, une personne :
  adresse privée, dates, révocable) et réglages (lien permanent, textes, prix).
-->
<template>
  <FormDialog
    :model-value="modelValue"
    icon="storefront"
    :title="t('transfers.showcase.title')"
    :subtitle="t('transfers.showcase.subtitle')"
    width="640px"
    :submit-label="tab === 'settings' ? t('common.save') : t('common.close')"
    :hide-submit="tab !== 'settings' || !can.frags"
    :cancel-label="t('common.close')"
    :loading="saving"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    @show="load"
    @submit="saveSettings"
  >
    <q-tabs v-model="tab" dense align="left" active-color="primary" indicator-color="primary" class="text-grey-7" outside-arrows mobile-arrows>
      <q-tab name="reservations" icon="shopping_cart" :label="newCount ? t('transfers.showcase.reservationsCount', { n: newCount }) : t('transfers.showcase.reservations')" />
      <q-tab name="links" icon="link" :label="activeCount ? t('transfers.showcase.linksCount', { n: activeCount }) : t('transfers.showcase.links')" />
      <q-tab name="settings" icon="tune" :label="t('transfers.showcase.settings')" />
    </q-tabs>

    <!-- Réservations -->
    <template v-if="tab === 'reservations'">
      <q-list v-if="reservations.length" bordered separator class="rounded-borders">
        <q-item v-for="r in reservations" :key="r.id" class="column items-stretch">
          <div class="row items-center no-wrap">
            <div class="col">
              <div class="text-weight-bold">{{ r.name }} <span class="text-weight-regular text-grey-7">· {{ r.contact }}</span></div>
              <div class="text-caption text-grey-7">
                {{ formatDateTime(r.created_at) }}
                <template v-if="r.link_label"> · {{ t('transfers.showcase.via', { label: r.link_label }) }}</template>
              </div>
            </div>
            <q-chip dense :color="STATUS[r.status].color" text-color="white">{{ t(`transfers.showcase.status.${r.status}`) }}</q-chip>
          </div>
          <div class="text-body2 q-mt-xs">{{ r.items.map((i) => `${i.quantity} × ${i.name}`).join(', ') }}</div>
          <div v-if="r.message" class="text-body2 text-grey-8 q-mt-xs">« {{ r.message }} »</div>
          <div v-if="r.status === 'new' && can.frags" class="column gap-sm q-mt-sm">
            <LocationSelect
              :model-value="locations[r.id] !== undefined ? locations[r.id]! : r.link_location_id"
              @update:model-value="(v: LocationChoice) => (locations[r.id] = v)"
            />
            <div class="row justify-end gap-sm">
              <q-btn flat color="negative" icon="close" :label="t('transfers.showcase.decline')" @click="decline(r)" />
              <q-btn unelevated color="primary" icon="description" :label="t('transfers.showcase.setAside')" @click="confirm(r)" />
            </div>
          </div>
          <div v-else-if="r.status === 'confirmed'" class="row justify-end q-mt-xs">
            <q-btn flat dense no-caps color="primary" icon="description" :label="t('transfers.showcase.seeTransfers')" to="/transfers" />
          </div>
        </q-item>
      </q-list>
      <div v-else class="text-center text-grey-6 q-pa-md">{{ t('transfers.showcase.noReservation') }}</div>
    </template>

    <!-- Liens de partage -->
    <template v-else-if="tab === 'links'">
      <div class="text-caption text-grey-7">{{ t('transfers.showcase.linksHelp') }}</div>

      <q-card v-if="draft" flat bordered class="q-pa-md column gap-sm">
        <div class="row gap-sm">
          <q-btn outline dense no-caps color="primary" icon="groups" :label="t('transfers.showcase.forSwap')" @click="preset('bourse')" />
          <q-btn outline dense no-caps color="primary" icon="person" :label="t('transfers.showcase.forPerson')" @click="preset('personne')" />
        </div>
        <q-input v-model="draft.label" :label="t('transfers.showcase.linkName')" outlined dense maxlength="80" :hint="t('transfers.showcase.linkNameHint')" />
        <LocationSelect v-model="draft.location" />
        <div class="row q-col-gutter-sm">
          <div class="col-6">
            <q-input v-model="draft.starts_on" type="date" :label="t('transfers.showcase.startsOn')" stack-label outlined dense clearable />
          </div>
          <div class="col-6">
            <q-input v-model="draft.ends_on" type="date" :label="t('transfers.showcase.endsOn')" stack-label outlined dense clearable />
          </div>
        </div>
        <q-toggle v-model="draft.qr_labels" :label="t('transfers.showcase.qrLabels')" />
        <div class="row justify-end gap-sm">
          <q-btn flat :label="t('common.cancel')" @click="draft = null" />
          <q-btn unelevated color="primary" icon="add_link" :label="t('transfers.showcase.createLink')" :loading="creating" @click="createLink" />
        </div>
      </q-card>
      <q-btn v-else-if="can.frags" unelevated color="primary" icon="add_link" :label="t('transfers.showcase.newLink')" class="self-start" @click="startDraft" />

      <q-list v-if="links.length" bordered separator class="rounded-borders">
        <q-item v-for="link in links" :key="link.id" class="column items-stretch" :class="{ 'link--inactive': link.state !== 'active' }">
          <div class="row items-center no-wrap gap-sm">
            <div class="col">
              <div class="text-weight-bold ellipsis">{{ link.label }}</div>
              <div class="text-caption text-grey-7">
                {{ periodLabel(link) }}
                <template v-if="link.location_name"> · <q-icon name="place" size="12px" /> {{ link.location_name }}</template>
              </div>
              <div class="text-caption text-grey-7">
                {{ t('transfers.showcase.visits', link.view_count) }}
                <template v-if="link.last_viewed_at"> · {{ t('transfers.showcase.lastVisit', { date: formatDateTime(link.last_viewed_at) }) }}</template>
                <template v-if="link.qr_labels"> · <q-icon name="qr_code_2" size="12px" /> {{ t('transfers.showcase.qrShort') }}</template>
              </div>
            </div>
            <span class="app-tag" :class="LINK_STATE[link.state].tag">{{ t(`transfers.showcase.linkState.${link.state}`) }}</span>
          </div>
          <div class="row justify-end q-mt-xs">
            <q-btn flat round dense icon="content_copy" :disable="link.state === 'revoked'" @click="copy(showcaseLinkUrl(link.token))"><q-tooltip>{{ t('transfers.showcase.copyLink') }}</q-tooltip></q-btn>
            <q-btn v-if="canShare" flat round dense icon="share" :disable="link.state === 'revoked'" @click="share(link)"><q-tooltip>{{ t('transfers.showcase.share') }}</q-tooltip></q-btn>
            <q-btn flat round dense icon="open_in_new" :href="showcaseLinkUrl(link.token)" target="_blank" :disable="link.state !== 'active'"><q-tooltip>{{ t('transfers.showcase.open') }}</q-tooltip></q-btn>
            <template v-if="can.frags">
              <q-btn v-if="link.state !== 'revoked'" flat round dense color="negative" icon="link_off" @click="setRevoked(link, true)"><q-tooltip>{{ t('transfers.showcase.revoke') }}</q-tooltip></q-btn>
              <q-btn v-else flat round dense icon="restore" @click="setRevoked(link, false)"><q-tooltip>{{ t('transfers.showcase.reactivate') }}</q-tooltip></q-btn>
              <q-btn flat round dense icon="delete" @click="removeLink(link)"><q-tooltip>{{ t('actions.delete') }}</q-tooltip></q-btn>
            </template>
          </div>
        </q-item>
      </q-list>
      <div v-else-if="!draft" class="text-center text-grey-6 q-pa-md">{{ t('transfers.showcase.noLink') }}</div>
    </template>

    <!-- Réglages -->
    <template v-else>
      <q-input v-model="settings.title" :label="t('transfers.showcase.fieldTitle')" outlined dense maxlength="80" :readonly="!can.frags" />
      <q-input v-model="settings.intro" :label="t('transfers.showcase.intro')" type="textarea" outlined dense autogrow :readonly="!can.frags" />
      <q-input
        v-model="settings.contact"
        :label="t('transfers.showcase.contact')"
        outlined
        dense
        maxlength="200"
        :hint="t('transfers.showcase.contactHint')"
        :readonly="!can.frags"
      />
      <q-toggle v-model="settings.show_prices" :disable="!can.frags" :label="t('transfers.showcase.showPrices')" />
      <q-input
        v-if="settings.show_prices"
        v-model="settings.price_label"
        :label="t('transfers.showcase.priceLabel')"
        outlined
        dense
        maxlength="30"
        :hint="t('transfers.showcase.priceLabelHint')"
        :readonly="!can.frags"
      />
      <q-toggle v-model="settings.allow_reservations" :disable="!can.frags" :label="t('transfers.showcase.allowReservations')" />

      <q-separator />
      <q-toggle v-model="settings.enabled" :disable="!can.frags" :label="t('transfers.showcase.permanent')" color="warning" />
      <div class="text-caption text-grey-7">{{ t('transfers.showcase.permanentHelp') }}</div>
      <q-input v-if="settings.enabled" :model-value="permanentUrl" readonly outlined dense :label="t('transfers.showcase.permanentLink')">
        <template #append>
          <q-btn flat round dense icon="content_copy" @click="copy(permanentUrl)"><q-tooltip>{{ t('transfers.showcase.copy') }}</q-tooltip></q-btn>
        </template>
      </q-input>
      <div class="text-caption text-grey-7">{{ t('transfers.showcase.privacyHelp') }}</div>
    </template>
  </FormDialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import axios from 'axios';
import { copyToClipboard, date as qdate, useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import FormDialog from 'src/components/FormDialog.vue';
import LocationSelect from 'src/components/LocationSelect.vue';
import { usePermissions } from 'src/composables/usePermissions';
import { locationPayload, type LocationChoice } from 'src/types/frag';
import {
  showcaseLinkUrl,
  type Reservation,
  type ShowcaseLink,
  type ShowcaseLinkState,
  type ShowcaseSettings,
} from 'src/pro/types/showcase';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatDate, formatDateTime } from 'src/utils/format';

defineProps<{ modelValue: boolean }>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; changed: [] }>();

// Libellés : transfers.showcase.status.* et transfers.showcase.linkState.*
const STATUS = {
  new: { color: 'orange-8' },
  confirmed: { color: 'positive' },
  declined: { color: 'grey-6' },
} as const;

const LINK_STATE: Record<ShowcaseLinkState, { tag: string }> = {
  active: { tag: 'app-tag--ok' },
  upcoming: { tag: 'app-tag--teal' },
  expired: { tag: 'app-tag--warn' },
  revoked: { tag: 'app-tag--danger' },
};

interface LinkDraft {
  label: string;
  location: LocationChoice;
  starts_on: string | null;
  ends_on: string | null;
  qr_labels: boolean;
}

const { t } = useI18n();
const $q = useQuasar();
const can = usePermissions();
const tab = ref<'reservations' | 'links' | 'settings'>('reservations');
const saving = ref(false);
const creating = ref(false);
const reservations = ref<Reservation[]>([]);
const links = ref<ShowcaseLink[]>([]);
const draft = ref<LinkDraft | null>(null);
const locations = ref<Record<number, LocationChoice>>({});
const settings = ref<ShowcaseSettings>({
  enabled: false,
  title: '',
  intro: '',
  contact: '',
  show_prices: false,
  price_label: t('transfers.showcase.defaultPriceLabel'),
  allow_reservations: true,
});
const permanentUrl = `${window.location.origin}/vitrine`;
const canShare = typeof navigator !== 'undefined' && 'share' in navigator;
const newCount = computed(() => reservations.value.filter((r) => r.status === 'new').length);
const activeCount = computed(() => links.value.filter((l) => l.state === 'active').length);

function isoDay(offset = 0): string {
  return qdate.formatDate(qdate.addToDate(new Date(), { days: offset }), 'YYYY-MM-DD');
}

function periodLabel(link: ShowcaseLink): string {
  if (link.starts_on && link.ends_on) {
    return link.starts_on === link.ends_on
      ? t('transfers.showcase.period.on', { date: formatDate(link.starts_on) })
      : t('transfers.showcase.period.range', { from: formatDate(link.starts_on), to: formatDate(link.ends_on) });
  }
  if (link.ends_on) return t('transfers.showcase.period.until', { date: formatDate(link.ends_on) });
  if (link.starts_on) return t('transfers.showcase.period.from', { date: formatDate(link.starts_on) });
  return t('transfers.showcase.period.none');
}

async function load() {
  draft.value = null;
  locations.value = {};
  try {
    const [s, r, l] = await Promise.all([
      axios.get<ShowcaseSettings>('/showcase/settings'),
      axios.get<Reservation[]>('/showcase/reservations'),
      axios.get<ShowcaseLink[]>('/showcase/links'),
    ]);
    settings.value = s.data;
    reservations.value = r.data;
    links.value = l.data;
    tab.value = newCount.value ? 'reservations' : 'links';
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.showcase.notify.loadFailed')) });
  }
}

function startDraft() {
  // Une semaine par défaut : un lien sans fin reste ouvert indéfiniment
  draft.value = { label: '', location: null, starts_on: isoDay(), ends_on: isoDay(7), qr_labels: false };
}

function preset(kind: 'bourse' | 'personne') {
  if (!draft.value) return;
  if (kind === 'bourse') {
    Object.assign(draft.value, { starts_on: isoDay(), ends_on: isoDay(1), qr_labels: true });
    if (!draft.value.label) draft.value.label = t('transfers.showcase.swapDefault');
  } else {
    Object.assign(draft.value, { starts_on: isoDay(), ends_on: isoDay(7), qr_labels: false });
    if (!draft.value.label) draft.value.label = t('transfers.showcase.personDefault');
  }
}

async function createLink() {
  const d = draft.value;
  if (!d || !d.label.trim()) {
    $q.notify({ type: 'warning', message: t('transfers.showcase.notify.nameRequired') });
    return;
  }
  creating.value = true;
  try {
    const { data } = await axios.post<ShowcaseLink>('/showcase/links', {
      label: d.label.trim(),
      starts_on: d.starts_on || null,
      ends_on: d.ends_on || null,
      qr_labels: d.qr_labels,
      ...locationPayload(d.location),
    });
    links.value = [data, ...links.value];
    draft.value = null;
    await copy(showcaseLinkUrl(data.token), t('transfers.showcase.notify.created'));
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.showcase.notify.createFailed')) });
  } finally {
    creating.value = false;
  }
}

async function setRevoked(link: ShowcaseLink, revoked: boolean) {
  try {
    const { data } = await axios.patch<ShowcaseLink>(`/showcase/links/${link.id}`, { revoked });
    links.value = links.value.map((l) => (l.id === data.id ? data : l));
    $q.notify({
      type: 'positive',
      message: revoked ? t('transfers.showcase.notify.revoked') : t('transfers.showcase.notify.reactivated'),
    });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.showcase.notify.failed')) });
  }
}

function removeLink(link: ShowcaseLink) {
  $q.dialog({
    title: t('transfers.showcase.deleteTitle'),
    message: t('transfers.showcase.deleteMessage', { label: link.label }),
    cancel: true,
    ok: { label: t('actions.delete'), color: 'negative', flat: true },
  }).onOk(() => {
    void (async () => {
      try {
        await axios.delete(`/showcase/links/${link.id}`);
        links.value = links.value.filter((l) => l.id !== link.id);
      } catch (err) {
        $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.showcase.notify.deleteFailed')) });
      }
    })();
  });
}

async function share(link: ShowcaseLink) {
  try {
    await navigator.share({ title: settings.value.title || t('transfers.showcase.defaultTitle'), url: showcaseLinkUrl(link.token) });
  } catch {
    // partage annulé
  }
}

async function saveSettings() {
  saving.value = true;
  try {
    settings.value = (await axios.put<ShowcaseSettings>('/showcase/settings', settings.value)).data;
    $q.notify({ type: 'positive', message: t('transfers.showcase.notify.saved') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.showcase.notify.saveFailed')) });
  } finally {
    saving.value = false;
  }
}

async function confirm(r: Reservation) {
  const choice = locations.value[r.id] !== undefined ? locations.value[r.id]! : r.link_location_id;
  try {
    await axios.post(`/showcase/reservations/${r.id}/confirm`, locationPayload(choice));
    reservations.value = (await axios.get<Reservation[]>('/showcase/reservations')).data;
    emit('changed');
    $q.notify({ type: 'positive', message: t('transfers.showcase.notify.setAside') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.showcase.notify.setAsideFailed')) });
  }
}

async function decline(r: Reservation) {
  try {
    const { data } = await axios.post<Reservation>(`/showcase/reservations/${r.id}/decline`);
    reservations.value = reservations.value.map((x) => (x.id === data.id ? data : x));
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.showcase.notify.failed')) });
  }
}

async function copy(url: string, message = t('transfers.showcase.notify.copied')) {
  try {
    await copyToClipboard(url);
    $q.notify({ type: 'positive', message });
  } catch {
    $q.notify({ type: 'info', message: url, timeout: 8000 });
  }
}
</script>

<style scoped>
.link--inactive {
  opacity: 0.65;
}
</style>
