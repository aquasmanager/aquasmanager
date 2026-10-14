<!--
  Vitrine des boutures (sans compte) : lots disponibles et réservation.
  /vitrine/<jeton> = lien de partage (une bourse, une personne) ;
  /vitrine = lien permanent, s'il est ouvert. Réglages : page Boutures › Vitrine.
-->
<template>
  <q-layout view="hHh lpr fFf">
    <q-header class="app-header">
      <q-toolbar>
        <img :src="logoUrl" alt="" width="30" height="30" class="q-mr-sm" />
        <q-toolbar-title class="text-weight-bold">{{ showcase?.title ?? t('transfers.showcase.defaultTitle') }}</q-toolbar-title>
        <LanguageSelect short class="q-mr-sm" />
        <q-btn v-if="auth.accessToken" flat round dense icon="close" :aria-label="t('common.back')" to="/frags" />
      </q-toolbar>
    </q-header>

    <q-page-container>
      <q-page class="vitrine-page q-pa-md">
        <div v-if="loading" class="text-center q-py-xl"><q-spinner color="primary" size="3em" /></div>

        <EmptyState
          v-else-if="!showcase"
          icon="storefront"
          :title="t('transfers.showcase.public.unavailable')"
          :message="token ? t('transfers.showcase.public.expired') : t('transfers.showcase.public.closed')"
        />

        <template v-else-if="sent">
          <EmptyState
            icon="check_circle"
            icon-color="positive"
            :title="t('transfers.showcase.public.sent')"
            :message="t('transfers.showcase.public.sentMessage')"
          >
            <q-btn unelevated color="primary" icon="storefront" :label="t('transfers.showcase.public.back')" @click="sent = false" />
          </EmptyState>
        </template>

        <template v-else>
          <div v-if="showcase.link_label" class="row items-center gap-sm q-mb-md">
            <span class="app-tag app-tag--teal"><q-icon name="event" size="14px" />{{ showcase.link_label }}</span>
            <span v-if="showcase.ends_on" class="text-caption text-grey-7">{{ t('transfers.showcase.public.until', { date: formatDate(showcase.ends_on) }) }}</span>
          </div>
          <div v-if="showcase.intro" class="text-body1 q-mb-sm" style="white-space: pre-line">{{ showcase.intro }}</div>
          <div v-if="showcase.contact" class="text-body2 text-grey-7 q-mb-md">
            <q-icon name="info" class="q-mr-xs" />{{ showcase.contact }}
          </div>

          <EmptyState v-if="!showcase.lots.length" icon="content_cut" :title="t('transfers.showcase.public.noLot')" />

          <div class="row q-col-gutter-md">
            <div v-for="lot in showcase.lots" :key="lot.id" class="col-12 col-sm-6 col-md-4">
              <q-card :id="`lot-${lot.id}`" flat bordered class="full-height column no-wrap overflow-hidden" :class="{ 'lot--highlight': highlighted === lot.id }">
                <q-img :src="mainPhotoUrl(PhotoEntityType.frags, lot.id)" :ratio="4 / 3">
                  <q-badge v-if="lot.coral_type" color="primary" class="absolute-top-right q-ma-sm">{{ lot.coral_type }}</q-badge>
                </q-img>
                <q-card-section class="col q-pb-xs">
                  <div class="text-subtitle1 text-weight-bold">{{ lot.name }}</div>
                  <div v-if="lot.scientific_name" class="text-caption text-italic text-grey-8">{{ lot.scientific_name }}</div>
                  <div class="text-caption text-grey-7">{{ t('transfers.showcase.public.lotInfo', { ref: lot.reference, n: lot.quantity }, lot.quantity) }}</div>
                </q-card-section>
                <q-card-actions class="q-px-md q-pb-md">
                  <div v-if="lot.price != null">
                    <div class="text-caption text-grey-7">{{ showcase.price_label }}</div>
                    <div class="text-h6 text-weight-bold app-mono">{{ formatPrice(lot.price) }}</div>
                  </div>
                  <q-space />
                  <template v-if="showcase.allow_reservations">
                    <q-btn v-if="!cart[lot.id]" unelevated color="primary" icon="add_shopping_cart" :label="t('transfers.showcase.public.reserve')" @click="cart[lot.id] = 1" />
                    <div v-else class="row items-center no-wrap">
                      <q-btn round dense flat icon="remove" @click="setQty(lot.id, cart[lot.id]! - 1)" />
                      <div class="text-weight-bold text-h6 q-px-sm">{{ cart[lot.id] }}</div>
                      <q-btn round dense flat icon="add" :disable="cart[lot.id]! >= lot.quantity" @click="setQty(lot.id, cart[lot.id]! + 1)" />
                    </div>
                  </template>
                </q-card-actions>
              </q-card>
            </div>
          </div>
        </template>

        <q-page-sticky v-if="showcase && !sent && cartCount > 0" position="bottom" :offset="[0, 16]">
          <q-btn unelevated rounded color="primary" size="lg" icon="shopping_cart_checkout" :label="t('transfers.showcase.public.reserveCount', cartCount)" @click="formOpen = true" />
        </q-page-sticky>
      </q-page>
    </q-page-container>

    <FormDialog
      v-model="formOpen"
      icon="shopping_cart_checkout"
      :title="t('transfers.showcase.public.formTitle')"
      :subtitle="t('transfers.showcase.public.formSubtitle')"
      width="480px"
      :submit-label="t('transfers.showcase.public.send')"
      submit-icon="send"
      :loading="saving"
      @submit="submit"
    >
      <q-list bordered separator dense class="rounded-borders">
        <q-item v-for="line in cartLines" :key="line.lot.id">
          <q-item-section>{{ line.quantity }} × {{ line.lot.name }}</q-item-section>
          <q-item-section v-if="line.lot.price != null" side>{{ formatPrice(line.lot.price * line.quantity) }}</q-item-section>
        </q-item>
      </q-list>
      <q-input v-model="form.name" :label="t('transfers.showcase.public.name')" outlined dense autocomplete="name" />
      <q-input v-model="form.contact" :label="t('transfers.showcase.public.contact')" outlined dense autocomplete="email" />
      <q-input v-model="form.message" :label="t('transfers.showcase.public.message')" type="textarea" outlined dense autogrow />
      <!-- Champ piège anti-robots, invisible pour les visiteurs -->
      <input v-model="form.website" class="vitrine-trap" tabindex="-1" autocomplete="off" aria-hidden="true" />
    </FormDialog>
  </q-layout>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue';
import { useRoute } from 'vue-router';
import axios from 'axios';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import LanguageSelect from 'src/components/LanguageSelect.vue';
import logoUrl from 'src/assets/logo.png';
import EmptyState from 'src/components/EmptyState.vue';
import FormDialog from 'src/components/FormDialog.vue';
import { useNoIndex } from 'src/composables/useNoIndex';
import { useAuthStore } from 'src/stores/authStore';
import { mainPhotoUrl } from 'src/stores/photoStore';
import { PhotoEntityType } from 'src/types/photo';
import type { PublicShowcase } from 'src/pro/types/showcase';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatDate, formatPrice } from 'src/utils/format';

const { t } = useI18n();
const $q = useQuasar();
const route = useRoute();
const auth = useAuthStore();
useNoIndex();

// Lien de partage : /vitrine/<jeton>
const token = computed(() => (typeof route.params.token === 'string' && route.params.token) || undefined);
const params = computed(() => (token.value ? { t: token.value } : {}));

const showcase = ref<PublicShowcase | null>(null);
const loading = ref(true);
const saving = ref(false);
const sent = ref(false);
const formOpen = ref(false);
const highlighted = ref<number | null>(null);
const cart = reactive<Record<number, number>>({});
const form = ref({ name: '', contact: '', message: '', website: '' });

const cartLines = computed(() =>
  (showcase.value?.lots ?? []).filter((lot) => cart[lot.id]).map((lot) => ({ lot, quantity: cart[lot.id]! })),
);
const cartCount = computed(() => cartLines.value.reduce((sum, line) => sum + line.quantity, 0));

function setQty(id: number, quantity: number) {
  if (quantity <= 0) delete cart[id];
  else cart[id] = quantity;
}

async function submit() {
  if (form.value.name.trim().length < 2 || form.value.contact.trim().length < 4) {
    $q.notify({ type: 'warning', message: t('transfers.showcase.public.required') });
    return;
  }
  saving.value = true;
  try {
    await axios.post('/public/showcase/reservations', {
      name: form.value.name.trim(),
      contact: form.value.contact.trim(),
      message: form.value.message.trim() || null,
      website: form.value.website,
      items: cartLines.value.map((line) => ({ frag_id: line.lot.id, quantity: line.quantity })),
    }, { params: params.value });
    formOpen.value = false;
    sent.value = true;
    Object.keys(cart).forEach((id) => delete cart[Number(id)]);
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.showcase.public.sendFailed')) });
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  try {
    showcase.value = (await axios.get<PublicShowcase>('/public/showcase/', { params: params.value })).data;
  } catch {
    showcase.value = null;
  } finally {
    loading.value = false;
  }
  // Arrivée depuis l'étiquette d'une bouture
  const ref_ = route.query.ref;
  const lot = typeof ref_ === 'string' ? showcase.value?.lots.find((l) => l.reference === ref_) : undefined;
  if (lot) {
    highlighted.value = lot.id;
    await nextTick();
    setTimeout(() => document.getElementById(`lot-${lot.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 400);
  }
});
</script>

<style scoped>
.vitrine-page {
  max-width: 1100px;
  margin: 0 auto;
  padding-bottom: calc(88px + env(safe-area-inset-bottom));
}

.lot--highlight {
  box-shadow: 0 0 0 3px var(--q-positive);
}

.vitrine-trap {
  position: absolute;
  left: -9999px;
  width: 1px;
  height: 1px;
  opacity: 0;
}
</style>
