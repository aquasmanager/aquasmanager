<template>
  <q-layout>
    <q-page-container>
      <q-page class="auth-page flex flex-center q-pa-md">
        <q-card class="auth-card q-pa-md">
          <q-card-section class="text-center q-pb-sm">
            <img :src="logoUrl" alt="AquasManager" width="96" height="96" />
            <div class="text-h5 text-weight-bold q-mt-sm">AquasManager</div>
            <div class="text-body2 text-grey-7">{{ t('auth.subtitle') }}</div>
          </q-card-section>

          <q-banner v-if="demo.info.value" rounded class="demo-banner q-mx-md q-mb-sm">
            <template #avatar><q-icon name="science" color="primary" /></template>
            <div class="text-weight-bold">{{ t('auth.demoTitle') }}</div>
            <div class="text-body2">{{ t('auth.demoCredentials', { username: demo.info.value.username, password: demo.info.value.password }) }}</div>
            <div class="text-caption text-grey-8 q-mt-xs">{{ t('auth.demoHint') }}</div>
          </q-banner>

          <q-form @submit.prevent="submit">
            <q-card-section class="column gap-md">
              <q-input
                v-model="username"
                v-bind="usernameProps"
                :label="t('auth.username')"
                outlined
                autocomplete="username"
                autofocus
                :error="!!errors.username"
                :error-message="errors.username"
              >
                <template #prepend><q-icon name="person" /></template>
              </q-input>
              <q-input
                v-model="password"
                v-bind="passwordProps"
                :type="showPassword ? 'text' : 'password'"
                :label="t('auth.password')"
                outlined
                autocomplete="current-password"
                :error="!!errors.password"
                :error-message="errors.password"
              >
                <template #prepend><q-icon name="lock" /></template>
                <template #append>
                  <q-icon :name="showPassword ? 'visibility_off' : 'visibility'" class="cursor-pointer" @click="showPassword = !showPassword" />
                </template>
              </q-input>
              <q-checkbox v-model="rememberMe" :label="t('auth.remember')" />
              <q-btn unelevated size="lg" color="primary" :label="t('auth.login')" type="submit" class="full-width" :loading="loading" />
            </q-card-section>
          </q-form>
          <q-card-section class="column items-center gap-sm q-pt-none">
            <LanguageSelect class="language-select" />
            <router-link to="/licences" class="text-caption text-grey-7">{{ t('nav.licences') }}</router-link>
          </q-card-section>
        </q-card>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import logoUrl from 'src/assets/logo.png';
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import LanguageSelect from 'src/components/LanguageSelect.vue';
import { z } from 'zod';
import { toTypedSchema } from '@vee-validate/zod';
import { useForm } from 'vee-validate';
import { useAuthStore } from '../stores/authStore';
import { type RegisterForm } from '../types/auth';
import { useDemo } from 'src/composables/useDemo';

const { t } = useI18n();
const store = useAuthStore();
const showPassword = ref<boolean>(false);
const rememberMe = ref<boolean>(false);

// Messages de validation dans la langue courante (changement possible sur cette page)
const schema = computed(() =>
  toTypedSchema(
    z.object({
      username: z.string({ required_error: t('auth.usernameRequired') }).trim().min(1, t('auth.usernameRequired')),
      password: z.string({ required_error: t('auth.passwordRequired') }).min(1, t('auth.passwordRequired')),
    }),
  ),
);

const { handleSubmit, errors, defineField } = useForm<RegisterForm>({
  validationSchema: schema,
  validateOnMount: false,
});

const [username, usernameProps] = defineField('username');
const [password, passwordProps] = defineField('password');

const loading = ref(false);

// Démo : identifiants préremplis
const demo = useDemo();
watch(
  demo.info,
  (info) => {
    if (!info) return;
    if (!username.value) username.value = info.username;
    if (!password.value) password.value = info.password;
  },
  { immediate: true },
);

const submit = handleSubmit(async (values) => {
  loading.value = true;
  try {
    await store.login(values.username.trim(), values.password, rememberMe.value);
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.auth-page {
  background: linear-gradient(135deg, #0d47a1 0%, #1976d2 45%, #26a69a 100%);
}

.auth-card {
  width: 420px;
  max-width: 100%;
}

.demo-banner {
  background: var(--q-primary-light, #e0f2fe);
}

.language-select {
  width: 220px;
}
</style>
