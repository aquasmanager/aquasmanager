<!--
  Page de l'acquéreur (sans compte, lien à jeton) : il vérifie les boutures,
  remplit ses coordonnées et signe. Après signature, il télécharge le PDF.
-->
<template>
  <q-layout view="hHh lpr fFf">
    <q-header class="app-header">
      <q-toolbar>
        <img :src="logoUrl" alt="" width="30" height="30" class="q-mr-sm" />
        <q-toolbar-title class="text-weight-bold">{{ t('transfers.signPage.title') }}</q-toolbar-title>
        <LanguageSelect short class="q-mr-sm" />
        <q-btn v-if="auth.accessToken" flat round dense icon="close" :aria-label="t('common.back')" :to="backLink" />
      </q-toolbar>
    </q-header>

    <q-page-container>
      <q-page class="sign-page q-pa-md">
        <div v-if="loading" class="text-center q-py-xl"><q-spinner color="primary" size="3em" /></div>

        <EmptyState v-else-if="error" icon="link_off" :title="t('transfers.signPage.unavailable')" :message="error" />

        <template v-else-if="certificate">
          <div class="text-h6 text-weight-bold">{{ saleId ? t('transfers.signPage.offlineNumber') : t('transfers.signPage.number', { n: certificate.number }) }}</div>
          <div class="text-body2 text-grey-7 q-mb-md">
            {{ t('transfers.signPage.transferOn', { date: formatDate(certificate.transfer_date) }) }}
            <template v-if="certificate.location_name"> · {{ certificate.location_name }}</template>
          </div>

          <q-banner v-if="saleId" rounded class="q-mb-md" :class="certificate.status === 'signed' ? 'bg-green-1 text-green-9' : 'bg-orange-1 text-orange-10'">
            <template #avatar><q-icon :name="certificate.status === 'signed' ? 'verified' : 'cloud_off'" :color="certificate.status === 'signed' ? 'positive' : 'orange-8'" /></template>
            <template v-if="certificate.status === 'signed'">
              {{ t('transfers.signPage.offlineSigned', { date: formatDateTime(certificate.signed_at) }) }}
            </template>
            <template v-else>{{ t('transfers.signPage.offlineReady') }}</template>
          </q-banner>

          <q-banner v-else-if="certificate.status === 'signed'" rounded class="bg-green-1 text-green-9 q-mb-md">
            <template #avatar><q-icon name="verified" color="positive" /></template>
            {{ t('transfers.signPage.signed', { date: formatDateTime(certificate.signed_at) }) }}
            <template #action>
              <q-btn unelevated color="positive" icon="picture_as_pdf" :label="t('transfers.signPage.downloadPdf')" :href="pdfUrl" target="_blank" />
            </template>
          </q-banner>

          <q-card flat bordered class="q-mb-md">
            <q-card-section>
              <div class="text-caption text-grey-7">{{ t('transfers.signPage.seller') }}</div>
              <div class="text-weight-bold">{{ certificate.seller.first_name }} {{ certificate.seller.last_name }}</div>
              <div class="text-body2">{{ certificate.seller.address }}, {{ certificate.seller.postal_code }} {{ certificate.seller.city }}</div>
              <div v-if="sellerContact" class="text-body2 text-grey-7">{{ sellerContact }}</div>
            </q-card-section>
          </q-card>

          <div class="text-subtitle1 text-weight-bold q-mb-sm">{{ t('transfers.signPage.specimens') }}</div>
          <q-list bordered separator class="rounded-borders q-mb-sm">
            <q-item v-for="item in certificate.items" :key="item.id">
              <q-item-section>
                <q-item-label class="text-weight-bold">{{ item.quantity }} × {{ item.name }}</q-item-label>
                <q-item-label caption><i>{{ item.scientific_name }}</i> · {{ t('transfers.signPage.reference', { ref: item.reference }) }}</q-item-label>
                <q-item-label caption>
                  CITES {{ item.cites || '—' }} · {{ item.mother_acquired_from || item.origin || t('transfers.signPage.noOrigin') }}
                  <template v-if="item.cut_date"> · {{ t('transfers.signPage.cutOn', { date: formatDate(item.cut_date) }) }}</template>
                </q-item-label>
              </q-item-section>
              <q-item-section v-if="item.price != null" side>
                <q-item-label class="text-weight-bold">{{ formatPrice(item.price * item.quantity) }}</q-item-label>
                <q-item-label v-if="item.quantity > 1" caption>{{ t('transfers.signPage.perUnit', { price: formatPrice(item.price) }) }}</q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
          <div class="text-right text-weight-bold q-mb-md">
            {{ t('transfers.signPage.totalFrags', certificate.total_quantity) }}
            <template v-if="certificate.total_price != null"> · {{ t('transfers.signPage.total', { total: formatPrice(certificate.total_price) }) }}</template>
          </div>
          <div v-if="certificate.notes" class="text-body2 q-mb-md"><b>{{ t('transfers.signPage.notes') }}</b> {{ certificate.notes }}</div>

          <q-card flat bordered class="q-mb-md">
            <q-card-section class="text-body2">
              <div class="text-caption text-grey-7 q-mb-xs">{{ t('transfers.signPage.statement') }}</div>
              <div style="white-space: pre-line">{{ certificate.legal_mention }}</div>
            </q-card-section>
          </q-card>

          <!-- Formulaire de l'acquéreur -->
          <q-form v-if="certificate.status === 'draft'" class="column gap-md" @submit.prevent="submit">
            <div class="text-subtitle1 text-weight-bold">{{ t('transfers.signPage.yourDetails') }}</div>
            <div class="row q-col-gutter-md">
              <div class="col-12 col-sm-6"><q-input v-model="buyer.first_name" :label="t('transfers.seller.firstName')" outlined dense autocomplete="given-name" /></div>
              <div class="col-12 col-sm-6"><q-input v-model="buyer.last_name" :label="t('transfers.seller.lastName')" outlined dense autocomplete="family-name" /></div>
              <div class="col-12"><q-input v-model="buyer.address" :label="t('transfers.seller.address')" outlined dense autocomplete="street-address" /></div>
              <div class="col-5 col-sm-4"><q-input v-model="buyer.postal_code" :label="t('transfers.seller.postalCode')" outlined dense autocomplete="postal-code" /></div>
              <div class="col-7 col-sm-8"><q-input v-model="buyer.city" :label="t('transfers.seller.city')" outlined dense autocomplete="address-level2" /></div>
              <div class="col-12 col-sm-6"><q-input v-model="buyer.email" :label="t('transfers.seller.email')" type="email" outlined dense autocomplete="email" /></div>
              <div class="col-12 col-sm-6"><q-input v-model="buyer.phone" :label="t('transfers.seller.phone')" type="tel" outlined dense autocomplete="tel" /></div>
            </div>

            <div>
              <div class="text-caption text-grey-7 q-mb-xs">{{ t('transfers.signPage.signature') }}</div>
              <SignaturePad v-model="signature" />
            </div>

            <!-- RGPD : l'acquéreur est informé avant de donner ses coordonnées -->
            <div v-if="certificate.privacy_notice" class="app-callout text-body2">
              <q-icon name="shield" size="20px" />
              <div>
                <div class="text-weight-bold q-mb-xs">{{ t('transfers.signPage.privacy') }}</div>
                <div style="white-space: pre-line">{{ certificate.privacy_notice }}</div>
              </div>
            </div>

            <q-checkbox v-model="accept" :label="t('transfers.signPage.accept')" />

            <q-btn unelevated color="primary" size="lg" icon="draw" :label="t('transfers.signPage.sign')" type="submit" :loading="saving" />
          </q-form>

          <div v-if="auth.accessToken" class="q-mt-lg text-center">
            <q-btn flat color="primary" icon="arrow_back" :label="saleId ? t('transfers.signPage.backFrags') : t('transfers.signPage.backTransfers')" :to="backLink" />
          </div>
        </template>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import axios from 'axios';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import LanguageSelect from 'src/components/LanguageSelect.vue';
import logoUrl from 'src/assets/logo.png';
import EmptyState from 'src/components/EmptyState.vue';
import SignaturePad from 'src/components/SignaturePad.vue';
import { useNoIndex } from 'src/composables/useNoIndex';
import { useAuthStore } from 'src/stores/authStore';
import type { Person, PublicCertificate } from 'src/types/frag';
import { offlineSales, type OfflineSaleRecord } from 'src/pro/offline/sales';
import { useOfflineStore } from 'src/stores/offlineStore';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatDate, formatDateTime, formatPrice } from 'src/utils/format';
import { API_URL } from 'src/utils/runtimeConfig';

const { t } = useI18n();
const $q = useQuasar();
const route = useRoute();
const auth = useAuthStore();

const token = String(route.params.token ?? '');
// Vente préparée hors connexion (données sur l'appareil, pas de lien à jeton)
const saleId = typeof route.params.saleId === 'string' ? route.params.saleId : null;
const backLink = saleId ? '/frags' : '/transfers';
const offline = useOfflineStore();
let sale: OfflineSaleRecord | undefined;

function saleView(record: OfflineSaleRecord): PublicCertificate {
  const amounts = record.items.filter((i) => i.price != null).map((i) => i.price! * i.quantity);
  return {
    number: '',
    status: record.status === 'signed' ? 'signed' : 'draft',
    transfer_date: record.payload.transfer_date ?? record.created_at.slice(0, 10),
    location_name: record.location_label,
    notes: record.payload.notes,
    seller: record.seller,
    legal_mention: record.legal_mention,
    privacy_notice: record.privacy_notice ?? '',
    buyer: record.buyer ?? null,
    items: record.items,
    total_price: amounts.length ? amounts.reduce((a, b) => a + b, 0) : null,
    total_quantity: record.items.reduce((sum, i) => sum + i.quantity, 0),
    signed_at: record.signed_at ?? null,
  };
}
const certificate = ref<PublicCertificate | null>(null);
const loading = ref(true);
const saving = ref(false);
const error = ref<string | null>(null);
const buyer = ref({ first_name: '', last_name: '', address: '', postal_code: '', city: '', email: '', phone: '' });
const signature = ref('');
const accept = ref(false);

const pdfUrl = `${API_URL}/public/certificates/${encodeURIComponent(token)}/pdf`;
const sellerContact = computed(() =>
  [certificate.value?.seller.phone, certificate.value?.seller.email].filter(Boolean).join(' · '),
);

async function load() {
  if (saleId) {
    sale = await offlineSales.get(saleId).catch(() => undefined);
    if (sale) certificate.value = saleView(sale);
    else error.value = t('transfers.signPage.alreadySent');
    loading.value = false;
    return;
  }
  try {
    certificate.value = (await axios.get<PublicCertificate>(`/public/certificates/${encodeURIComponent(token)}`)).data;
  } catch (err) {
    error.value = apiErrorMessage(err, t('transfers.signPage.invalid'));
  } finally {
    loading.value = false;
  }
}

async function submit() {
  const b = buyer.value;
  if (![b.first_name, b.last_name, b.address, b.postal_code, b.city].every((v) => v.trim())) {
    $q.notify({ type: 'warning', message: t('transfers.signPage.required') });
    return;
  }
  if (!signature.value) {
    $q.notify({ type: 'warning', message: t('transfers.signPage.signHere') });
    return;
  }
  if (!accept.value) {
    $q.notify({ type: 'warning', message: t('transfers.signPage.acceptRequired') });
    return;
  }
  saving.value = true;
  const buyerInfo = {
    first_name: b.first_name.trim(),
    last_name: b.last_name.trim(),
    address: b.address.trim(),
    postal_code: b.postal_code.trim(),
    city: b.city.trim(),
    email: b.email.trim() || null,
    phone: b.phone.trim() || null,
  };
  if (sale) {
    await signOffline(sale, buyerInfo);
    saving.value = false;
    return;
  }
  try {
    certificate.value = (
      await axios.post<PublicCertificate>(`/public/certificates/${encodeURIComponent(token)}/sign`, {
        buyer: buyerInfo,
        signature: signature.value,
        accept: true,
      })
    ).data;
    window.scrollTo({ top: 0, behavior: 'smooth' });
    $q.notify({ type: 'positive', message: t('transfers.signPage.done') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.signPage.failed')) });
  } finally {
    saving.value = false;
  }
}

// Signature sur l'appareil : la vente part dans la file d'attente (envoi au retour du réseau)
async function signOffline(record: OfflineSaleRecord, buyerInfo: Person) {
  const signedAt = new Date().toISOString();
  const signed: OfflineSaleRecord = { ...record, status: 'signed', buyer: buyerInfo, signed_at: signedAt };
  try {
    await offlineSales.save(signed);
    await offline.enqueue({
      id: record.id,
      method: 'POST',
      url: '/transfer-certificates/offline',
      data: { ...record.payload, buyer: buyerInfo, signature: signature.value, signed_at: signedAt, accept: true },
      label: (() => {
        const n = signed.items.reduce((sum, i) => sum + i.quantity, 0);
        return t('transfers.signPage.offlineLabel', { name: `${buyerInfo.first_name} ${buyerInfo.last_name}`, n }, n);
      })(),
    });
  } catch {
    $q.notify({ type: 'negative', message: t('transfers.signPage.offlineSaveFailed') });
    return;
  }
  sale = signed;
  certificate.value = saleView(signed);
  window.scrollTo({ top: 0, behavior: 'smooth' });
  $q.notify({ type: 'positive', message: t('transfers.signPage.offlineDone') });
  if (offline.online) void offline.flush();
}

useNoIndex();
onMounted(load);
</script>

<style scoped>
.sign-page {
  max-width: 720px;
  margin: 0 auto;
  padding-bottom: calc(24px + env(safe-area-inset-bottom));
}
</style>
