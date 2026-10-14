<template>
  <q-layout>
    <q-page-container>
      <q-page class="auth-page flex flex-center q-pa-md">
        <q-card class="auth-card q-pa-md">
          <q-card-section class="text-center q-pb-sm">
            <q-avatar size="64px" :color="forced ? 'orange-8' : 'primary'" text-color="white" icon="password" />
            <div class="text-h5 text-weight-bold q-mt-md">
              {{ forced ? t('password.forcedTitle') : t('password.title') }}
            </div>
            <div class="text-body2 text-grey-7">
              {{ forced ? t('password.forcedHint') : t('password.hint') }}
            </div>
          </q-card-section>

          <q-form @submit.prevent="submit">
            <q-card-section class="column gap-md">
              <q-input
                v-model="currentPassword"
                v-bind="currentPasswordProps"
                :type="showCurrentPassword ? 'text' : 'password'"
                :label="t('password.current')"
                outlined
                autocomplete="current-password"
                :error="!!errors.currentPassword"
                :error-message="errors.currentPassword"
              >
                <template #append>
                  <q-icon :name="showCurrentPassword ? 'visibility_off' : 'visibility'" class="cursor-pointer" @click="showCurrentPassword = !showCurrentPassword" />
                </template>
              </q-input>
              <q-input
                v-model="newPassword"
                v-bind="newPasswordProps"
                :type="showNewPassword ? 'text' : 'password'"
                :label="t('password.new')"
                outlined
                autocomplete="new-password"
                :error="!!errors.newPassword"
                :error-message="errors.newPassword"
              >
                <template #append>
                  <q-icon :name="showNewPassword ? 'visibility_off' : 'visibility'" class="cursor-pointer" @click="showNewPassword = !showNewPassword" />
                </template>
              </q-input>
              <q-input
                v-model="confirmPassword"
                v-bind="confirmPasswordProps"
                :type="showNewPassword ? 'text' : 'password'"
                :label="t('password.confirm')"
                outlined
                autocomplete="new-password"
                :error="!!errors.confirmPassword"
                :error-message="errors.confirmPassword"
              />
              <q-btn unelevated size="lg" color="primary" :label="t('password.submit')" type="submit" class="full-width" :loading="loading" />
              <div class="row justify-center">
                <q-btn v-if="forced" flat color="grey-8" icon="logout" :label="t('layout.logout')" @click="logout" />
                <q-btn v-else flat color="grey-8" icon="arrow_back" :label="t('common.back')" @click="goBack" />
              </div>
            </q-card-section>
          </q-form>
        </q-card>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { z } from 'zod';
import { toTypedSchema } from '@vee-validate/zod';
import { useForm } from 'vee-validate';
import type { AxiosError } from 'axios';
import { Notify } from 'quasar';
import { useAuthStore } from '../stores/authStore';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
const store = useAuthStore();
const router = useRouter();
const loading = ref(false);
// Changement imposé (premier login, réinitialisation) ou volontaire depuis le menu
const forced = computed(() => store.mustChangePassword);
const showCurrentPassword = ref(false);
const showNewPassword = ref(false);

const schema = computed(() =>
  toTypedSchema(
    z
      .object({
        currentPassword: z.string({ required_error: t('auth.passwordRequired') }).min(1, t('auth.passwordRequired')),
        newPassword: z.string({ required_error: t('password.tooShort') }).min(8, t('password.tooShort')),
        confirmPassword: z.string({ required_error: t('password.confirmRequired') }).min(8, t('password.confirmRequired')),
      })
      .refine((data) => data.newPassword === data.confirmPassword, {
        message: t('password.mismatch'),
        path: ['confirmPassword'],
      })
      .refine((data) => data.newPassword !== data.currentPassword, {
        message: t('password.mustDiffer'),
        path: ['newPassword'],
      }),
  ),
);

const { handleSubmit, errors, defineField } = useForm({
  validationSchema: schema,
  validateOnMount: false,
});

const [currentPassword, currentPasswordProps] = defineField('currentPassword');
const [newPassword, newPasswordProps] = defineField('newPassword');
const [confirmPassword, confirmPasswordProps] = defineField('confirmPassword');

const submit = handleSubmit(async (values) => {
  loading.value = true;
  try {
    await store.changePassword({
      current_password: values.currentPassword,
      new_password: values.newPassword,
    });
    Notify.create({
      message: t('password.updated'),
      color: 'positive',
      position: 'top',
      timeout: 3000,
    });
    await router.push('/home');
  } catch (err) {
    const error = err as AxiosError<{ detail: string }>;
    Notify.create({
      message: error.response?.data.detail || t('password.failed'),
      color: 'negative',
      position: 'top',
      timeout: 3000,
      icon: 'warning',
    });
  } finally {
    loading.value = false;
  }
});

async function logout() {
  await store.logout();
}

function goBack() {
  if (window.history.length > 1) router.back();
  else void router.push('/home');
}
</script>

<style scoped>
.auth-page {
  background: linear-gradient(135deg, #0d47a1 0%, #1976d2 45%, #26a69a 100%);
}

.auth-card {
  width: 440px;
  max-width: 100%;
}
</style>
