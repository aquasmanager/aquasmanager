<template>
  <q-page class="app-page">
    <PageHeader icon="description" :title="t('transfers.title')" :subtitle="t('transfers.subtitle')">
      <template #actions>
        <q-btn-dropdown outline color="primary" icon="download" :label="t('transfers.exports')" no-caps>
          <q-list style="min-width: 260px">
            <q-item v-close-popup clickable @click="openReport(null)">
              <q-item-section avatar><q-icon name="insights" /></q-item-section>
              <q-item-section>
                <q-item-label>{{ t('transfers.report') }}</q-item-label>
                <q-item-label caption>{{ filterLabel }}</q-item-label>
              </q-item-section>
            </q-item>
            <q-item v-close-popup clickable @click="downloadZip(null)">
              <q-item-section avatar><q-icon name="folder_zip" /></q-item-section>
              <q-item-section>
                <q-item-label>{{ t('transfers.zip') }}</q-item-label>
                <q-item-label caption>{{ t('transfers.zipCaption', { filter: filterLabel }) }}</q-item-label>
              </q-item-section>
            </q-item>
            <q-item v-close-popup clickable @click="downloadCsv(null)">
              <q-item-section avatar><q-icon name="table_view" /></q-item-section>
              <q-item-section>
                <q-item-label>{{ t('transfers.csv') }}</q-item-label>
                <q-item-label caption>{{ filterLabel }}</q-item-label>
              </q-item-section>
            </q-item>
            <q-separator />
            <q-item v-for="year in registryYears" :key="year" v-close-popup clickable @click="downloadRegistry(year)">
              <q-item-section avatar><q-icon name="menu_book" /></q-item-section>
              <q-item-section>
                <q-item-label>{{ t('transfers.registry', { year }) }}</q-item-label>
                <q-item-label caption>{{ t('transfers.registryCaption') }}</q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
        </q-btn-dropdown>
        <q-btn outline color="primary" icon="place" :label="t('transfers.locations')" @click="openLocations" />
        <q-btn outline color="primary" icon="badge" :label="t('transfers.myInfo')" @click="profileDialog = true" />
        <q-btn unelevated color="primary" icon="content_cut" :label="t('transfers.frags')" to="/frags" />
      </template>
    </PageHeader>

    <q-banner v-if="profile && !profile.complete" rounded class="bg-amber-1 text-amber-10 q-mb-md">
      <template #avatar><q-icon name="badge" color="amber-9" /></template>
      {{ t('transfers.profileMissing') }}
      <template #action>
        <q-btn flat color="amber-10" :label="t('transfers.complete')" @click="profileDialog = true" />
      </template>
    </q-banner>

    <!-- Repère annuel : nombre de cessions signées, pour garder un œil sur le caractère occasionnel -->
    <q-card v-if="yearly.length" flat bordered class="q-mb-md">
      <q-card-section class="row items-center q-col-gutter-md">
        <div class="col-12 col-md-3">
          <div class="text-subtitle1 text-weight-bold">{{ t('transfers.thisYear', { year: thisYear.year }) }}</div>
          <div class="text-caption text-grey-7">
            {{ t('transfers.signed') }}<template v-if="lastYear">
              ·
              {{
                t('transfers.lastYear', {
                  year: lastYear.year,
                  certificates: t('transfers.certificatesCount', lastYear.certificate_count),
                  frags: t('transfers.fragsCount', lastYear.quantity),
                })
              }}</template>
          </div>
        </div>
        <div v-for="stat in yearStats" :key="stat.label" class="col-4 col-sm col-md">
          <div class="year-stat app-mono ellipsis">{{ stat.value }}</div>
          <div class="text-caption text-grey-7">{{ stat.label }}</div>
        </div>
      </q-card-section>
    </q-card>

    <!-- Ventes faites sans réseau, pas encore envoyées -->
    <q-card v-if="localSales.length" flat bordered class="q-mb-md">
      <q-card-section class="q-pb-none row items-center no-wrap">
        <q-icon name="cloud_off" color="orange-8" size="22px" class="q-mr-sm" />
        <div class="col">
          <div class="text-subtitle1 text-weight-bold">{{ t('transfers.offline.title') }}</div>
          <div class="text-caption text-grey-7">{{ t('transfers.offline.caption') }}</div>
        </div>
      </q-card-section>
      <q-list separator>
        <q-item v-for="s in localSales" :key="s.id" clickable :to="`/signature/hors-ligne/${s.id}`">
          <q-item-section avatar>
            <q-avatar :color="s.status === 'signed' ? 'green-1' : 'amber-1'" :text-color="s.status === 'signed' ? 'positive' : 'amber-9'" :icon="s.status === 'signed' ? 'schedule_send' : 'draw'" />
          </q-item-section>
          <q-item-section>
            <q-item-label class="text-weight-bold">
              {{ s.buyer ? `${s.buyer.first_name} ${s.buyer.last_name}` : t('transfers.offline.toSign') }}
            </q-item-label>
            <q-item-label caption>
              {{ formatDateTime(s.created_at) }} · {{ t('transfers.fragsCount', s.items.reduce((n, i) => n + i.quantity, 0)) }}
              <template v-if="s.location_label"> · {{ s.location_label }}</template>
            </q-item-label>
          </q-item-section>
          <q-item-section side>
            <q-chip dense :color="s.status === 'signed' ? 'positive' : 'amber-8'" text-color="white">
              {{ s.status === 'signed' ? t('transfers.offline.signedPending') : t('transfers.offline.toSignChip') }}
            </q-chip>
          </q-item-section>
        </q-item>
      </q-list>
    </q-card>

    <div v-if="loading" class="text-center q-py-xl"><q-spinner color="primary" size="3em" /></div>

    <EmptyState
      v-else-if="certificates.length === 0"
      icon="description"
      :title="t('transfers.emptyTitle')"
      :message="t('transfers.emptyMessage')"
    >
      <q-btn unelevated color="primary" icon="content_cut" :label="t('transfers.seeFrags')" to="/frags" />
    </EmptyState>

    <template v-else>
      <!-- Recherche : acheteur ou numéro de certificat -->
      <AppInput
        v-model="search"
        icon="search"
        :placeholder="t('transfers.searchPlaceholder')"
        clearable
        debounce="200"
        class="q-mb-sm"
        style="max-width: 420px"
      />
      <!-- Filtre par lieu de vente -->
      <div class="location-filter row no-wrap q-gutter-x-sm q-mb-md">
        <q-chip
          clickable
          :outline="locationFilter !== 'all'"
          color="primary"
          :text-color="locationFilter === 'all' ? 'white' : 'primary'"
          icon="apps"
          @click="locationFilter = 'all'"
        >
          {{ t('transfers.all', { n: filteredCertificates.length }) }}
        </q-chip>
        <q-chip
          v-for="group in allGroups"
          :key="group.key"
          clickable
          :outline="locationFilter !== group.key"
          color="primary"
          :text-color="locationFilter === group.key ? 'white' : 'primary'"
          :icon="group.id ? 'place' : 'help_outline'"
          @click="locationFilter = group.key"
        >
          {{ t('transfers.groupCount', { name: group.name, n: group.certificates.length }) }}
        </q-chip>
      </div>

      <EmptyState v-if="search && filteredCertificates.length === 0" icon="search_off" :title="t('transfers.noSearchResult', { search })" />

      <div v-for="group in visibleGroups" :key="group.key" class="q-mb-lg">
        <div class="row items-center no-wrap q-mb-sm">
          <q-icon :name="group.id ? 'place' : 'help_outline'" color="primary" size="22px" class="q-mr-sm" />
          <div class="col">
            <div class="text-subtitle1 text-weight-bold ellipsis">{{ group.name }}</div>
            <div class="text-caption text-grey-7">
              {{ t('transfers.certificateCount', group.certificates.length) }}
              · {{ t('transfers.fragsCount', group.quantity) }}
              <template v-if="group.total != null"> · {{ formatPrice(group.total) }}</template>
              <template v-if="group.firstDate"> · {{ periodLabel(group) }}</template>
            </div>
          </div>
          <q-btn flat dense no-caps color="primary" icon="folder_zip" class="q-mr-xs" @click="downloadZip(group)">
            <q-tooltip>{{ t('transfers.zipTooltip') }}</q-tooltip>
          </q-btn>
          <q-btn flat dense no-caps color="primary" icon="insights" :label="t('transfers.report')" @click="openReport(group)" />
        </div>
        <q-list bordered separator class="rounded-borders bg-white">
          <q-item v-for="cert in group.certificates" :key="cert.id" clickable @click="openDetail(cert)">
            <q-item-section avatar>
              <q-avatar
                :color="cert.status === 'signed' ? 'green-1' : 'amber-1'"
                :text-color="cert.status === 'signed' ? 'positive' : 'amber-9'"
                :icon="cert.status === 'signed' ? 'verified' : 'draw'"
              />
            </q-item-section>
            <q-item-section>
              <q-item-label class="text-weight-bold">
                {{ cert.number }}
                <span class="text-weight-regular text-grey-7"> · {{ cert.buyer_name ?? t('transfers.buyerMissing') }}</span>
              </q-item-label>
              <q-item-label caption>
                {{ formatDate(cert.transfer_date) }} · {{ t('transfers.fragsCount', cert.total_quantity) }}
                <template v-if="cert.total_price != null"> · {{ formatPrice(cert.total_price) }}</template>
              </q-item-label>
            </q-item-section>
            <q-item-section side>
              <div class="row items-center no-wrap gap-xs">
                <q-chip
                  dense
                  :color="cert.status === 'signed' ? 'positive' : 'amber-8'"
                  text-color="white"
                  class="gt-xs"
                >
                  {{ cert.status === 'signed' ? t('transfers.statusSigned') : t('transfers.statusPending') }}
                </q-chip>
                <q-btn v-if="cert.status === 'draft' && can.frags" flat round dense color="primary" icon="draw" @click.stop="openSign(cert.id)">
                  <q-tooltip>{{ t('transfers.askSign') }}</q-tooltip>
                </q-btn>
                <q-btn flat round dense color="grey-8" icon="picture_as_pdf" :aria-label="t('transfers.viewPdf')" @click.stop="viewPdf(cert)">
                  <q-tooltip>{{ t('transfers.viewPdf') }}</q-tooltip>
                </q-btn>
              </div>
            </q-item-section>
          </q-item>
        </q-list>
      </div>
    </template>

    <!-- Faire signer l'acquéreur -->
    <FormDialog
      v-model="signDialog"
      icon="draw"
      :title="t('transfers.sign.title')"
      :subtitle="active ? t('transfers.sign.certificate', { n: active.number }) : undefined"
      width="560px"
      :cancel-label="t('common.close')"
      hide-submit
    >
      <template v-if="active">
        <div class="text-body2">
          {{ t('transfers.sign.help') }}
        </div>
        <q-btn unelevated color="primary" icon="draw" :label="t('transfers.sign.openHere')" :to="`/signature/${active.sign_token}`" />
        <q-input :model-value="signUrl" readonly outlined dense :label="t('transfers.sign.link')">
          <template #append>
            <q-btn flat round dense icon="content_copy" @click="copyLink">
              <q-tooltip>{{ t('transfers.sign.copy') }}</q-tooltip>
            </q-btn>
            <q-btn v-if="canShare" flat round dense icon="share" @click="shareLink">
              <q-tooltip>{{ t('transfers.sign.share') }}</q-tooltip>
            </q-btn>
          </template>
        </q-input>
        <div class="row items-center text-caption text-grey-7">
          <q-icon name="schedule" size="xs" class="q-mr-xs" />
          {{ t('transfers.sign.validUntil', { date: formatDateTime(active.token_expires_at) }) }}
          <q-btn flat dense no-caps size="sm" color="primary" :label="t('transfers.sign.newLink')" class="q-ml-sm" @click="renewLink" />
        </div>
      </template>
    </FormDialog>

    <!-- Détail -->
    <FormDialog
      v-model="detailDialog"
      icon="description"
      :title="active ? t('transfers.sign.certificate', { n: active.number }) : t('transfers.detail.title')"
      :subtitle="
        active
          ? active.status === 'signed'
            ? t('transfers.detail.signedOn', { date: formatDateTime(active.signed_at) })
            : t('transfers.detail.pending')
          : undefined
      "
      width="640px"
      :cancel-label="t('common.close')"
      hide-submit
    >
      <template v-if="active">
        <div class="row q-col-gutter-md">
          <div class="col-12 col-sm-6">
            <div class="text-caption text-grey-7">{{ t('transfers.detail.seller') }}</div>
            <PersonBlock :person="active.seller" />
          </div>
          <div class="col-12 col-sm-6">
            <div class="text-caption text-grey-7">{{ t('transfers.detail.buyer') }}</div>
            <div v-if="active.anonymized_at" class="text-grey-7">
              <q-icon name="person_off" class="q-mr-xs" />{{ t('transfers.detail.anonymizedOn', { date: formatDate(active.anonymized_at) }) }}
            </div>
            <PersonBlock v-else-if="active.buyer" :person="active.buyer" />
            <div v-else class="text-grey-6">{{ t('transfers.detail.buyerToComplete') }}</div>
          </div>
        </div>
        <q-list bordered separator class="rounded-borders">
          <q-item v-for="item in active.items" :key="item.id">
            <q-item-section>
              <q-item-label class="text-weight-bold">{{ item.quantity }} × {{ item.name }}</q-item-label>
              <q-item-label caption>
                {{ item.reference }} · <i>{{ item.scientific_name }}</i> · CITES {{ item.cites || '—' }} · {{ item.mother_acquired_from || item.origin || '—' }}
              </q-item-label>
            </q-item-section>
            <q-item-section side>
              <q-item-label class="text-weight-bold">{{ formatPrice(item.price != null ? item.price * item.quantity : null) }}</q-item-label>
              <q-item-label v-if="item.price != null && item.quantity > 1" caption>{{ t('transfers.detail.perUnit', { price: formatPrice(item.price) }) }}</q-item-label>
            </q-item-section>
          </q-item>
        </q-list>
        <div v-if="active.notes" class="text-body2"><b>{{ t('transfers.detail.notes') }}</b> {{ active.notes }}</div>
        <!-- Lieu : modifiable avant signature, ou à renseigner s'il manque -->
        <div v-if="canEditLocation" class="row items-start no-wrap gap-sm">
          <LocationSelect v-model="detailLocation" class="col" />
          <q-btn
            unelevated
            color="primary"
            icon="check"
            :disable="detailLocation === (active.location_id ?? null)"
            :loading="savingLocation"
            @click="saveLocation"
          >
            <q-tooltip>{{ t('transfers.detail.saveLocation') }}</q-tooltip>
          </q-btn>
        </div>
        <div v-else class="text-body2">
          <q-icon name="place" color="primary" class="q-mr-xs" /><b>{{ t('transfers.detail.location') }}</b> {{ active.location_name ?? '—' }}
        </div>
      </template>
      <template #footer-left>
        <q-btn
          v-if="active?.status === 'draft' && can.frags"
          flat
          color="negative"
          icon="delete"
          :label="t('actions.delete')"
          @click="removeCertificate"
        />
        <q-btn v-if="active?.status === 'draft' && can.frags" flat color="primary" icon="draw" :label="t('transfers.askSign')" @click="openSign(active.id)" />
        <q-btn v-if="active" flat color="grey-8" icon="picture_as_pdf" :label="t('transfers.detail.pdf')" @click="viewPdf(active)" />
        <q-btn
          v-if="active && active.status === 'signed' && !active.anonymized_at && can.manage"
          flat
          color="grey-8"
          icon="person_off"
          :label="t('transfers.detail.anonymize')"
          @click="anonymize"
        >
          <q-tooltip>{{ t('transfers.detail.anonymizeHelp') }}</q-tooltip>
        </q-btn>
      </template>
    </FormDialog>

    <SellerProfileDialog v-model="profileDialog" @saved="(p) => (profile = p)" />

    <!-- Bilan -->
    <FormDialog
      v-model="reportDialog"
      icon="insights"
      :title="t('transfers.reportDialog.title')"
      :subtitle="reportTitle"
      width="560px"
      :cancel-label="t('common.close')"
      hide-submit
    >
      <div v-if="!report" class="text-center q-py-lg"><q-spinner color="primary" size="2em" /></div>
      <template v-else>
        <div class="row q-col-gutter-sm">
          <div v-for="stat in reportStats" :key="stat.label" class="col-6 col-sm-3">
            <q-card flat bordered class="q-pa-sm text-center">
              <div class="text-h6 text-weight-bold">{{ stat.value }}</div>
              <div class="text-caption text-grey-7">{{ stat.label }}</div>
            </q-card>
          </div>
        </div>
        <div v-if="report.pending_count" class="text-caption text-orange-9">
          {{ t('transfers.reportDialog.pending', report.pending_count) }}
        </div>
        <div v-if="report.by_species.length">
          <div class="text-subtitle2 text-weight-bold q-mb-xs">{{ t('transfers.reportDialog.bySpecies') }}</div>
          <q-list bordered separator dense class="rounded-borders">
            <q-item v-for="row in report.by_species" :key="row.scientific_name + row.name">
              <q-item-section>
                <q-item-label>{{ row.name }}</q-item-label>
                <q-item-label caption><i>{{ row.scientific_name }}</i></q-item-label>
              </q-item-section>
              <q-item-section side>
                <q-item-label class="text-weight-bold">× {{ row.quantity }}</q-item-label>
                <q-item-label v-if="row.amount" caption>{{ formatPrice(row.amount) }}</q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
        </div>
        <div class="text-caption text-grey-7">
          {{
            t('transfers.reportDialog.stockLeft', {
              frags: t('transfers.reportDialog.availableFrags', report.stock_quantity),
              lots: t('transfers.reportDialog.lots', report.stock_lots),
            })
          }}
        </div>
      </template>
      <template #footer-left>
        <q-btn v-if="report" flat color="primary" icon="table_view" :label="t('transfers.reportDialog.csv')" @click="downloadCsv(reportGroup)" />
      </template>
    </FormDialog>

    <!-- Lieux de vente -->
    <FormDialog
      v-model="locationsDialog"
      icon="place"
      :title="t('transfers.locationsDialog.title')"
      :subtitle="t('transfers.locationsDialog.subtitle')"
      width="520px"
      :cancel-label="t('common.close')"
      :submit-label="t('transfers.locationsDialog.add')"
      submit-icon="add"
      :hide-submit="!can.frags || !newLocation.trim()"
      @submit="addLocation"
    >
      <q-input v-if="can.frags" v-model="newLocation" :label="t('transfers.locationsDialog.new')" outlined dense maxlength="80">
        <template #prepend><q-icon name="add_location_alt" /></template>
      </q-input>
      <q-list v-if="locations.length" bordered separator class="rounded-borders">
        <q-item v-for="location in locations" :key="location.id">
          <q-item-section>
            <q-item-label class="text-weight-bold" :class="{ 'cursor-pointer': can.frags }">
              {{ location.name }}
              <q-popup-edit
                v-if="can.frags"
                v-slot="scope"
                :model-value="location.name"
                buttons
                :label-set="t('transfers.locationsDialog.ok')"
                :label-cancel="t('common.cancel')"
                @save="(value: string) => renameLocation(location, value)"
              >
                <q-input v-model="scope.value" dense autofocus maxlength="80" :label="t('transfers.locationsDialog.name')" @keyup.enter="scope.set" />
              </q-popup-edit>
            </q-item-label>
            <q-item-label caption>
              <template v-if="location.certificate_count">
                {{ t('transfers.certificateCount', location.certificate_count) }}
                · {{ t('transfers.fragsCount', location.total_quantity) }}
                <template v-if="location.total_price != null"> · {{ formatPrice(location.total_price) }}</template>
                <template v-if="location.last_transfer_date"> · {{ t('transfers.locationsDialog.last', { date: formatDate(location.last_transfer_date) }) }}</template>
              </template>
              <template v-else>{{ t('transfers.locationsDialog.none') }}</template>
            </q-item-label>
          </q-item-section>
          <q-item-section v-if="can.manage && !location.certificate_count" side>
            <q-btn flat round dense icon="delete" color="negative" @click="removeLocation(location)">
              <q-tooltip>{{ t('actions.delete') }}</q-tooltip>
            </q-btn>
          </q-item-section>
        </q-item>
      </q-list>
      <div v-else class="text-grey-6 text-center q-pa-md">{{ t('transfers.locationsDialog.empty') }}</div>
    </FormDialog>
  </q-page>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onBeforeUnmount, onMounted, ref, watch, type PropType } from 'vue';
import { offlineSales, type OfflineSaleRecord } from 'src/pro/offline/sales';
import { SYNCED_EVENT } from 'src/stores/offlineStore';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';
import { copyToClipboard, useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import { useFileViewerStore } from 'src/stores/fileViewerStore';
import AppInput from 'src/components/AppInput.vue';
import EmptyState from 'src/components/EmptyState.vue';
import FormDialog from 'src/components/FormDialog.vue';
import LocationSelect from 'src/components/LocationSelect.vue';
import PageHeader from 'src/components/PageHeader.vue';
import SellerProfileDialog from 'src/pro/components/SellerProfileDialog.vue';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { usePermissions } from 'src/composables/usePermissions';
import {
  locationPayload,
  type CertificateReport,
  type YearlyTransfers,
  type Certificate,
  type CertificateSummary,
  type LocationChoice,
  type Person,
  type SaleLocation,
  type SellerProfile,
} from 'src/types/frag';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatDate, formatDateTime, formatPrice } from 'src/utils/format';

// Coordonnées d'une partie (cédant / acquéreur)
const PersonBlock = defineComponent({
  props: { person: { type: Object as PropType<Person>, required: true } },
  setup(props) {
    return () => {
      const p = props.person;
      const lines = [
        h('div', { class: 'text-weight-bold' }, `${p.first_name} ${p.last_name}`),
        h('div', p.address),
        h('div', `${p.postal_code} ${p.city}`),
      ];
      const contact = [p.phone, p.email].filter(Boolean).join(' · ');
      if (contact) lines.push(h('div', { class: 'text-grey-7' }, contact));
      return h('div', { class: 'text-body2' }, lines);
    };
  },
});

const { t } = useI18n();
const fileViewer = useFileViewerStore();
const $q = useQuasar();
const route = useRoute();
const router = useRouter();
const can = usePermissions();
const { confirmRemove } = useConfirmRemove();

const certificates = ref<CertificateSummary[]>([]);
const loading = ref(true);
const profile = ref<SellerProfile | null>(null);
const profileDialog = ref(false);
const active = ref<Certificate | null>(null);
const signDialog = ref(false);
const detailDialog = ref(false);

// --- Rangement par lieu de vente ---
interface LocationGroup {
  key: string;
  id: number | null;
  name: string;
  certificates: CertificateSummary[];
  quantity: number;
  total: number | null;
  firstDate: string | null;
  lastDate: string | null;
}

const locationFilter = ref<string>('all');
const search = ref<string | null>('');
// Nouvelle recherche : tous les lieux (le lieu choisi peut ne plus avoir de résultat)
watch(search, () => (locationFilter.value = 'all'));

// Sans accents ni majuscules : « helene » trouve « Hélène »
function normalize(value: string): string {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}

const filteredCertificates = computed(() => {
  const s = normalize((search.value ?? '').trim());
  if (!s) return certificates.value;
  return certificates.value.filter((c) => normalize(`${c.buyer_name ?? ''} ${c.number}`).includes(s));
});

const allGroups = computed<LocationGroup[]>(() => {
  const groups = new Map<string, LocationGroup>();
  for (const cert of filteredCertificates.value) {
    const key = cert.location_id ? String(cert.location_id) : 'none';
    let group = groups.get(key);
    if (!group) {
      group = {
        key,
        id: cert.location_id,
        name: cert.location_name ?? t('transfers.noLocation'),
        certificates: [],
        quantity: 0,
        total: null,
        firstDate: null,
        lastDate: null,
      };
      groups.set(key, group);
    }
    group.certificates.push(cert);
    group.quantity += cert.total_quantity;
    if (cert.total_price != null) group.total = (group.total ?? 0) + cert.total_price;
    if (!group.firstDate || cert.transfer_date < group.firstDate) group.firstDate = cert.transfer_date;
    if (!group.lastDate || cert.transfer_date > group.lastDate) group.lastDate = cert.transfer_date;
  }
  // Lieux les plus récents d'abord, « Sans lieu » à la fin
  return [...groups.values()].sort((a, b) =>
    a.id === null ? 1 : b.id === null ? -1 : (b.lastDate ?? '').localeCompare(a.lastDate ?? ''),
  );
});

const visibleGroups = computed(() =>
  locationFilter.value === 'all' ? allGroups.value : allGroups.value.filter((g) => g.key === locationFilter.value),
);

function periodLabel(group: LocationGroup): string {
  if (!group.firstDate || group.firstDate === group.lastDate) return t('transfers.periodOn', { date: formatDate(group.firstDate) });
  return t('transfers.periodRange', { from: formatDate(group.firstDate), to: formatDate(group.lastDate) });
}

// --- Lieu d'un certificat ---
const detailLocation = ref<LocationChoice>(null);
const savingLocation = ref(false);
const canEditLocation = computed(
  () => can.frags && !!active.value && (active.value.status === 'draft' || active.value.location_id === null),
);

async function saveLocation() {
  if (!active.value) return;
  savingLocation.value = true;
  try {
    const payload = detailLocation.value === null ? { location_id: null } : locationPayload(detailLocation.value);
    active.value = (await axios.patch<Certificate>(`/transfer-certificates/${active.value.id}`, payload)).data;
    detailLocation.value = active.value.location_id;
    await load();
    $q.notify({ type: 'positive', message: t('transfers.notify.locationSaved') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.notify.locationFailed')) });
  } finally {
    savingLocation.value = false;
  }
}

// --- Bilans et exports ---
const reportDialog = ref(false);
const report = ref<CertificateReport | null>(null);
const reportGroup = ref<LocationGroup | null>(null);
const currentYear = new Date().getFullYear();
const yearly = ref<YearlyTransfers[]>([]);
const EMPTY_YEAR = { certificate_count: 0, quantity: 0, total: 0, location_count: 0, buyer_count: 0 };
const thisYear = computed<YearlyTransfers>(
  () => yearly.value.find((y) => y.year === currentYear) ?? { year: currentYear, ...EMPTY_YEAR },
);
const lastYear = computed(() => yearly.value.find((y) => y.year === currentYear - 1) ?? null);
const yearStats = computed(() => [
  { label: t('transfers.yearStats.transfers'), value: thisYear.value.certificate_count },
  { label: t('transfers.yearStats.frags'), value: thisYear.value.quantity },
  { label: t('transfers.yearStats.amount'), value: formatPrice(thisYear.value.total) },
  { label: t('transfers.yearStats.locations'), value: thisYear.value.location_count },
  { label: t('transfers.yearStats.buyers'), value: thisYear.value.buyer_count },
]);
const registryYears = [currentYear, currentYear - 1];

const filterLabel = computed(() => {
  if (locationFilter.value === 'all') return t('transfers.allLocations');
  return allGroups.value.find((g) => g.key === locationFilter.value)?.name ?? '';
});
const reportTitle = computed(() => (reportGroup.value ? reportGroup.value.name : filterLabel.value));

const reportStats = computed(() =>
  report.value
    ? [
        { label: t('transfers.reportDialog.signed'), value: report.value.certificate_count },
        { label: t('transfers.reportDialog.transferred'), value: report.value.quantity },
        { label: t('transfers.reportDialog.amount'), value: formatPrice(report.value.total) },
        { label: t('transfers.reportDialog.stock'), value: report.value.stock_quantity },
      ]
    : [],
);

function groupParams(group: LocationGroup | null): Record<string, number> {
  const key = group ? group.key : locationFilter.value;
  if (key === 'all') return {};
  return { location_id: key === 'none' ? 0 : Number(key) };
}

async function openReport(group: LocationGroup | null) {
  reportGroup.value = group;
  report.value = null;
  reportDialog.value = true;
  try {
    report.value = (await axios.get<CertificateReport>('/transfer-certificates/report', { params: groupParams(group) })).data;
  } catch (err) {
    reportDialog.value = false;
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.notify.reportFailed')) });
  }
}

async function download(url: string, params: Record<string, number>, filename: string) {
  try {
    const { data } = await axios.get<Blob>(url, { params, responseType: 'blob' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(data);
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 10_000);
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.notify.downloadFailed')) });
  }
}

function downloadCsv(group: LocationGroup | null = null) {
  const params = groupParams(group);
  const name = (group?.name ?? filterLabel.value).toLowerCase().replace(/[^a-z0-9]+/gi, '-');
  void download('/transfer-certificates/export.csv', params, t('transfers.files.csv', { name }));
}

function downloadZip(group: LocationGroup | null = null) {
  const name = (group?.name ?? filterLabel.value).toLowerCase().replace(/[^a-z0-9]+/gi, '-');
  void download('/transfer-certificates/export.zip', groupParams(group), t('transfers.files.zip', { name }));
}

function downloadRegistry(year: number) {
  void download('/transfer-certificates/registry.pdf', { year }, t('transfers.files.registry', { year }));
}

// --- Gestion des lieux ---
const locationsDialog = ref(false);
const locations = ref<SaleLocation[]>([]);
const newLocation = ref('');

async function fetchLocations() {
  locations.value = (await axios.get<SaleLocation[]>('/sale-locations/')).data;
}

async function openLocations() {
  newLocation.value = '';
  try {
    await fetchLocations();
    locationsDialog.value = true;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.notify.locationsFailed')) });
  }
}

async function addLocation() {
  const name = newLocation.value.trim();
  if (!name) return;
  try {
    await axios.post('/sale-locations/', { name });
    newLocation.value = '';
    await fetchLocations();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.notify.addLocationFailed')) });
  }
}

async function renameLocation(location: SaleLocation, name: string) {
  if (!name.trim() || name.trim() === location.name) return;
  try {
    await axios.patch(`/sale-locations/${location.id}`, { name: name.trim() });
    await Promise.all([fetchLocations(), load()]);
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.notify.renameFailed')) });
  }
}

function removeLocation(location: SaleLocation) {
  confirmRemove(t('transfers.locationItem', { name: location.name }), async () => {
    await axios.delete(`/sale-locations/${location.id}`);
    await fetchLocations();
  });
}

const signUrl = computed(() => (active.value ? `${window.location.origin}/signature/${active.value.sign_token}` : ''));
const canShare = typeof navigator !== 'undefined' && 'share' in navigator;

async function load() {
  try {
    const [list, seller, years] = await Promise.all([
      axios.get<CertificateSummary[]>('/transfer-certificates/'),
      axios.get<SellerProfile>('/seller-profile/'),
      axios.get<YearlyTransfers[]>('/transfer-certificates/yearly'),
    ]);
    certificates.value = list.data;
    profile.value = seller.data;
    yearly.value = years.data;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.notify.loadFailed')) });
  } finally {
    loading.value = false;
  }
}

async function fetchCertificate(id: number) {
  active.value = (await axios.get<Certificate>(`/transfer-certificates/${id}`)).data;
}

async function openDetail(cert: CertificateSummary) {
  try {
    await fetchCertificate(cert.id);
    detailLocation.value = active.value?.location_id ?? null;
    detailDialog.value = true;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.notify.notFound')) });
  }
}

async function openSign(id: number) {
  try {
    await fetchCertificate(id);
    detailDialog.value = false;
    signDialog.value = true;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.notify.notFound')) });
  }
}

async function copyLink() {
  await copyToClipboard(signUrl.value);
  $q.notify({ type: 'positive', message: t('transfers.notify.copied') });
}

function shareLink() {
  if (!active.value) return;
  navigator
    .share({
      title: t('transfers.sign.shareTitle', { n: active.value.number }),
      text: t('transfers.sign.shareText'),
      url: signUrl.value,
    })
    .catch(() => undefined);
}

async function renewLink() {
  if (!active.value) return;
  try {
    active.value = (await axios.post<Certificate>(`/transfer-certificates/${active.value.id}/renew-link`)).data;
    $q.notify({ type: 'positive', message: t('transfers.notify.linkRenewed') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.notify.renewFailed')) });
  }
}

// Certificat affiché dans la visionneuse de l'appli (téléchargement possible depuis celle-ci)
function viewPdf(cert: CertificateSummary) {
  fileViewer.show({
    title: cert.number,
    filename: t('transfers.files.certificate', { n: cert.number }),
    contentType: 'application/pdf',
    load: async () => (await axios.get<Blob>(`/transfer-certificates/${cert.id}/pdf`, { responseType: 'blob' })).data,
  });
}

// Demande d'effacement de l'acquéreur (RGPD) : définitif, les spécimens restent tracés
function anonymize() {
  const cert = active.value;
  if (!cert) return;
  $q.dialog({
    title: t('transfers.anonymizeDialog.title'),
    message: t('transfers.anonymizeDialog.message', { n: cert.number }),
    cancel: true,
    ok: { label: t('transfers.detail.anonymize'), color: 'negative', flat: true },
  }).onOk(() => {
    void (async () => {
      try {
        const { data } = await axios.post<Certificate>(`/transfer-certificates/${cert.id}/anonymize`);
        active.value = data;
        certificates.value = certificates.value.map((c) => (c.id === data.id ? { ...c, ...data } : c));
        $q.notify({ type: 'positive', message: t('transfers.notify.anonymized') });
      } catch (err) {
        $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.notify.anonymizeFailed')) });
      }
    })();
  });
}

function removeCertificate() {
  const cert = active.value;
  if (!cert) return;
  confirmRemove(
    t('transfers.certificateItem', { n: cert.number }),
    async () => {
      await axios.delete(`/transfer-certificates/${cert.id}`);
      certificates.value = certificates.value.filter((c) => c.id !== cert.id);
      detailDialog.value = false;
    },
    { message: t('transfers.deleteMessage', { n: cert.number }) },
  );
}

// --- Ventes hors connexion ---
const localSales = ref<OfflineSaleRecord[]>([]);

async function loadLocalSales() {
  localSales.value = await offlineSales.all().catch(() => []);
}

function onSynced() {
  void Promise.all([load(), loadLocalSales()]);
}

window.addEventListener(SYNCED_EVENT, onSynced);
onBeforeUnmount(() => window.removeEventListener(SYNCED_EVENT, onSynced));

onMounted(async () => {
  await Promise.all([load(), loadLocalSales()]);
  // Arrivée depuis la page Boutures après création : proposer la signature
  const signId = Number(route.query.sign);
  if (signId) {
    void router.replace({ query: {} });
    await openSign(signId);
  }
});
</script>

<style scoped>
.year-stat {
  font-size: 1.35rem;
  font-weight: 600;
  line-height: 1.2;
}

@media (max-width: 599px) {
  .year-stat {
    font-size: 1.05rem;
    letter-spacing: -0.02em;
  }
}

.location-filter {
  overflow-x: auto;
  padding-bottom: 4px;
  scrollbar-width: none;
}
</style>
