<!-- Informations du cédant, reprises dans chaque certificat de cession (saisies une fois) -->
<template>
  <FormDialog
    :model-value="modelValue"
    icon="badge"
    :title="t('transfers.seller.title')"
    :subtitle="t('transfers.seller.subtitle')"
    width="600px"
    :loading="saving"
    :hide-submit="!can.manage"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    @show="load"
    @submit="save"
  >
    <q-banner v-if="!can.manage" dense rounded class="bg-blue-1 text-blue-10">
      <template #avatar><q-icon name="lock" color="primary" /></template>
      {{ t('transfers.seller.readOnly') }}
    </q-banner>
    <div class="row q-col-gutter-md">
      <div class="col-12 col-sm-6"><q-input v-model="form.first_name" :label="t('transfers.seller.firstName')" outlined dense /></div>
      <div class="col-12 col-sm-6"><q-input v-model="form.last_name" :label="t('transfers.seller.lastName')" outlined dense /></div>
      <div class="col-12"><q-input v-model="form.address" :label="t('transfers.seller.address')" outlined dense /></div>
      <div class="col-5 col-sm-4"><q-input v-model="form.postal_code" :label="t('transfers.seller.postalCode')" outlined dense /></div>
      <div class="col-7 col-sm-8"><q-input v-model="form.city" :label="t('transfers.seller.city')" outlined dense /></div>
      <div class="col-12 col-sm-6"><q-input v-model="form.phone" :label="t('transfers.seller.phone')" type="tel" outlined dense /></div>
      <div class="col-12 col-sm-6"><q-input v-model="form.email" :label="t('transfers.seller.email')" type="email" outlined dense /></div>
    </div>
    <q-input
      v-model="form.legal_mention"
      :label="t('transfers.seller.legalMention')"
      type="textarea"
      outlined
      dense
      autogrow
      :hint="t('transfers.seller.legalMentionHint')"
    />

    <!-- RGPD : ce que l'acquéreur lit avant de signer, et combien de temps ses données sont gardées -->
    <div class="text-subtitle2 q-mt-sm">{{ t('transfers.seller.buyersData') }}</div>
    <q-select
      v-model="form.buyer_retention_years"
      :options="retentionOptions"
      emit-value
      map-options
      :label="t('transfers.seller.retention')"
      outlined
      dense
      :hint="retentionHint"
      @update:model-value="previewRetention"
    />
    <q-input
      v-model="form.privacy_notice"
      :label="t('transfers.seller.privacyNotice')"
      type="textarea"
      outlined
      dense
      autogrow
      :hint="t('transfers.seller.privacyNoticeHint')"
    >
      <template v-if="form.privacy_notice" #append>
        <q-btn flat dense round size="sm" icon="restart_alt" @click="form.privacy_notice = ''">
          <q-tooltip>{{ t('transfers.seller.resetNotice') }}</q-tooltip>
        </q-btn>
      </template>
    </q-input>
    <div v-if="!form.privacy_notice" class="app-callout text-caption">
      <q-icon name="shield" size="18px" />
      <div>
        <div>{{ defaultNotice }}</div>
        <q-btn v-if="can.manage" flat dense no-caps size="sm" color="primary" icon="edit" :label="t('transfers.seller.customizeNotice')" class="q-mt-xs" @click="form.privacy_notice = defaultNotice" />
      </div>
    </div>

    <div>
      <div class="row items-center q-mb-xs">
        <div class="text-caption text-grey-7">{{ t('transfers.seller.signature') }}</div>
        <q-space />
        <q-btn
          v-if="currentSignature && !redraw"
          flat
          dense
          no-caps
          size="sm"
          color="primary"
          icon="draw"
          :label="t('transfers.seller.redraw')"
          @click="redraw = true"
        />
      </div>
      <div v-if="currentSignature && !redraw" class="signature-preview rounded-borders">
        <img :src="currentSignature" :alt="t('transfers.seller.signatureAlt')" />
      </div>
      <SignaturePad v-else v-model="newSignature" />
    </div>
  </FormDialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import axios from 'axios';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import { defaultPrivacyNotice } from 'src/legal/privacyNotice';
import FormDialog from 'src/components/FormDialog.vue';
import SignaturePad from 'src/components/SignaturePad.vue';
import { usePermissions } from 'src/composables/usePermissions';
import type { SellerProfile } from 'src/types/frag';
import { apiErrorMessage } from 'src/utils/apiError';

defineProps<{ modelValue: boolean }>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; saved: [profile: SellerProfile] }>();

const { t } = useI18n();
const $q = useQuasar();
const can = usePermissions();
const saving = ref(false);
const form = ref({
  first_name: '',
  last_name: '',
  address: '',
  postal_code: '',
  city: '',
  phone: '',
  email: '',
  legal_mention: '',
  privacy_notice: '',
  buyer_retention_years: 5,
});

const retentionOptions = computed(() => [
  ...[1, 2, 3].map((n) => ({ label: t('transfers.seller.retentionYears', n), value: n })),
  { label: t('transfers.seller.retentionAdvised', { n: 5 }), value: 5 },
  { label: t('transfers.seller.retentionYears', 10), value: 10 },
  { label: t('transfers.seller.noRetention'), value: 0 },
]);

// Même texte par défaut que l'API (services/privacy.py)
const defaultNotice = computed(() => defaultPrivacyNotice(form.value.buyer_retention_years));

const toAnonymize = ref(0);
const retentionHint = computed(() =>
  toAnonymize.value ? t('transfers.seller.toAnonymize', toAnonymize.value) : t('transfers.seller.retentionHint'),
);

async function previewRetention() {
  try {
    const { data } = await axios.get<{ count: number }>('/seller-profile/retention-preview', {
      params: { years: form.value.buyer_retention_years },
    });
    toAnonymize.value = data.count;
  } catch {
    toAnonymize.value = 0;
  }
}
const currentSignature = ref<string | null>(null);
const newSignature = ref('');
const redraw = ref(false);

async function load() {
  redraw.value = false;
  newSignature.value = '';
  try {
    const { data } = await axios.get<SellerProfile>('/seller-profile/');
    form.value = {
      first_name: data.first_name,
      last_name: data.last_name,
      address: data.address,
      postal_code: data.postal_code,
      city: data.city,
      phone: data.phone ?? '',
      email: data.email ?? '',
      legal_mention: data.legal_mention,
      privacy_notice: data.privacy_notice ?? '',
      buyer_retention_years: data.buyer_retention_years ?? 5,
    };
    void previewRetention();
    currentSignature.value = data.signature;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.seller.loadFailed')) });
  }
}

async function save() {
  const f = form.value;
  if (![f.first_name, f.last_name, f.address, f.postal_code, f.city].every((v) => v.trim())) {
    $q.notify({ type: 'warning', message: t('transfers.seller.required') });
    return;
  }
  if (!currentSignature.value && !newSignature.value) {
    $q.notify({ type: 'warning', message: t('transfers.seller.signatureRequired') });
    return;
  }
  saving.value = true;
  try {
    const { data } = await axios.put<SellerProfile>('/seller-profile/', {
      ...f,
      ...(newSignature.value ? { signature: newSignature.value } : {}),
    });
    emit('saved', data);
    emit('update:modelValue', false);
    $q.notify({ type: 'positive', message: t('transfers.seller.saved') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('transfers.seller.saveFailed')) });
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.signature-preview {
  border: 1px solid var(--app-border-color);
  background: #fff;
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.signature-preview img {
  max-height: 110px;
  max-width: 100%;
}
</style>
