<template>
  <div class="fullscreen error-page text-white text-center q-pa-md flex flex-center">
    <div>
      <q-icon name="lock" size="72px" style="opacity: 0.8" />
      <div class="error-code text-weight-bold">403</div>
      <div class="text-h5 q-mb-xl" style="opacity: 0.85">{{ t('errors.forbidden') }}</div>
      <q-btn unelevated color="primary" icon="home" :label="t('errors.backHome')" to="/home" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
</script>

<style scoped>
.error-page {
  background:
    radial-gradient(1100px 560px at 15% 0%, rgba(56, 189, 248, 0.22), transparent 60%),
    radial-gradient(900px 520px at 90% 100%, rgba(45, 212, 191, 0.16), transparent 60%),
    #050a12;
}

.error-code {
  font-size: 22vh;
  line-height: 1;
}
</style>
