<!--
  Fenêtre de saisie commune : en-tête (titre, sous-titre, fermeture), corps
  défilant et pied avec « Annuler » + bouton principal. La touche Entrée
  valide le formulaire (événement submit). Sur téléphone, la fenêtre
  s'ouvre en plein écran par glissement, comme dans une appli.
-->
<template>
  <q-dialog
    :model-value="modelValue"
    :persistent="persistent"
    :maximized="fullscreen"
    :transition-show="fullscreen ? 'slide-up' : 'scale'"
    :transition-hide="fullscreen ? 'slide-down' : 'scale'"
    @update:model-value="(value: boolean) => emit('update:modelValue', value)"
    @show="emit('show')"
    @hide="emit('hide')"
  >
    <q-card
      class="form-dialog column no-wrap"
      :class="{ 'form-dialog--fullscreen': fullscreen }"
      :style="fullscreen ? undefined : { width, maxWidth: '95vw' }"
    >
      <q-card-section class="row items-start no-wrap q-pb-sm">
        <q-avatar v-if="icon" size="40px" :color="iconBg" :text-color="iconColor" :icon="icon" class="q-mr-md" />
        <div class="col">
          <div class="text-h6 text-weight-bold">{{ title }}</div>
          <div v-if="subtitle" class="text-body2 text-grey-7">{{ subtitle }}</div>
        </div>
        <div v-if="$slots['header-actions']" class="q-ml-sm">
          <slot name="header-actions" />
        </div>
        <q-btn flat round dense icon="close" color="grey-7" class="q-ml-sm" :aria-label="t('common.close')" v-close-popup />
      </q-card-section>

      <q-form class="column no-wrap col" @submit="emit('submit')">
        <q-card-section class="form-dialog__body col scroll q-pt-sm">
          <div class="form-dialog__fields">
            <slot />
          </div>
        </q-card-section>

        <q-separator />

        <q-card-actions class="form-dialog__actions q-px-md q-py-sm">
          <slot name="footer-left" />
          <q-space />
          <q-btn flat color="grey-8" :label="cancelLabel ?? t('common.cancel')" v-close-popup />
          <q-btn
            v-if="!hideSubmit"
            unelevated
            type="submit"
            :color="submitColor"
            :icon="submitIcon"
            :label="submitLabel ?? t('common.save')"
            :loading="loading"
            :disable="submitDisabled"
          />
        </q-card-actions>
      </q-form>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
const $q = useQuasar();
const fullscreen = computed(() => $q.screen.lt.sm);

withDefaults(
  defineProps<{
    modelValue: boolean;
    title: string;
    subtitle?: string | undefined;
    icon?: string | undefined;
    iconColor?: string | undefined;
    iconBg?: string | undefined;
    width?: string | undefined;
    loading?: boolean | undefined;
    submitLabel?: string | undefined;
    submitIcon?: string | undefined;
    submitColor?: string | undefined;
    submitDisabled?: boolean | undefined;
    cancelLabel?: string | undefined;
    hideSubmit?: boolean | undefined;
    persistent?: boolean | undefined;
  }>(),
  {
    iconColor: 'primary',
    iconBg: 'blue-1',
    width: '520px',
    submitIcon: 'check',
    submitColor: 'primary',
  },
);

const emit = defineEmits<{
  'update:modelValue': [value: boolean];
  submit: [];
  show: [];
  hide: [];
}>();
</script>

<style scoped>
.form-dialog {
  max-height: 90vh;
}

.form-dialog__body {
  max-height: 72vh;
}

.form-dialog--fullscreen {
  max-height: none;
  border-radius: 0 !important;
  padding-top: env(safe-area-inset-top);
}

.form-dialog--fullscreen .form-dialog__body {
  max-height: none;
}

.form-dialog--fullscreen .form-dialog__actions {
  padding-bottom: calc(8px + env(safe-area-inset-bottom));
}

.form-dialog--fullscreen .form-dialog__actions .q-btn {
  min-height: 44px;
}

.form-dialog__fields {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
