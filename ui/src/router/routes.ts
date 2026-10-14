import type { RouteRecordRaw } from 'vue-router';

// meta.title : clé de traduction du titre (en-tête mobile)
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('layouts/MainLayout.vue'),
    children: [
      { path: '', redirect: '/home' },
      {
        path: 'home',
        component: () => import('pages/HomePage.vue'),
        meta: { title: 'nav.home' },
      },
      {
        path: 'myaquariums',
        component: () => import('pages/MyAquariumsPage.vue'),
        meta: { title: 'nav.myAquariums' },
      },
      {
        path: 'calendar',
        component: () => import('pages/CalendarPage.vue'),
        meta: { title: 'nav.calendar' },
      },
      {
        path: 'species',
        component: () => import('pages/SpeciesCatalogPage.vue'),
        meta: { title: 'nav.species' },
      },
      {
        path: 'aquariums/:id',
        component: () => import('pages/AquariumPage.vue'),
        // Page de détail : bouton retour dans l'en-tête mobile
        meta: { title: 'nav.aquarium', back: '/myaquariums' },
      },
      {
        path: 'frags',
        component: () => import('pages/FragsPage.vue'),
        meta: { title: 'nav.frags' },
      },
      {
        path: 'transfers',
        component: () => import('src/pro/pages/TransfersPage.vue'),
        meta: { title: 'nav.transfers', feature: 'bourse' },
      },
      {
        path: 'documents',
        component: () => import('pages/PurchaseDocumentsPage.vue'),
        meta: { title: 'nav.documents' },
      },
      {
        path: 'commandes-groupees',
        component: () => import('pages/GroupOrdersPage.vue'),
        meta: { title: 'nav.groupOrders' },
      },
      {
        path: 'controllers',
        component: () => import('pages/ControllersPage.vue'),
        meta: { title: 'nav.controllers' },
      },
      {
        path: 'extensions',
        redirect: '/controllers',
      },
      {
        path: 'license',
        component: () => import('pages/LicensePage.vue'),
        meta: { title: 'nav.license', minRole: 'admin' },
      },
      {
        path: 'backup',
        component: () => import('pages/BackupPage.vue'),
        meta: { title: 'nav.backup', minRole: 'admin' },
      },
      {
        path: 'notifications',
        component: () => import('pages/NotificationsPage.vue'),
        meta: { title: 'nav.notifications', minRole: 'admin' },
      },
      {
        path: 'assistant-settings',
        component: () => import('pages/AssistantSettingsPage.vue'),
        meta: { title: 'nav.assistant', minRole: 'admin', feature: 'assistant' },
      },
      {
        path: 'users',
        component: () => import('pages/UsersPage.vue'),
        meta: { title: 'nav.users', minRole: 'admin' },
      },
      {
        path: 'audit',
        component: () => import('pages/AuditLogPage.vue'),
        meta: { title: 'nav.audit', minRole: 'admin' },
      },
    ],
    meta: { requiresAuth: true, minRole: 'consult' },
  },
  // Page introuvable (Vue Router classe ce motif après tous les autres)
  {
    path: '/:catchAll(.*)*',
    component: () => import('pages/ErrorNotFound.vue'),
  },
  {
    path: '/errorRights',
    component: () => import('pages/ErrorRights.vue'),
  },
  {
    path: '/change-password',
    component: () => import('pages/ChangePasswordPage.vue'),
    meta: { requiresAuth: true },
  },
  // Licences et avertissement : sans compte
  {
    path: '/licences',
    component: () => import('pages/LicensesPage.vue'),
  },
  // Vitrine des boutures : sans compte (lien permanent ou lien de partage à jeton)
  {
    path: '/vitrine/:token?',
    component: () => import('src/pro/pages/VitrinePage.vue'),
  },
  // Paramètres d'eau partagés : sans compte (lien à jeton, lecture seule)
  {
    path: '/partage/parametres/:token',
    component: () => import('pages/SharedParametersPage.vue'),
  },
  // Signature d'un certificat de cession par l'acquéreur : sans compte (lien à jeton)
  {
    path: '/signature/:token',
    component: () => import('src/pro/pages/SignCertificatePage.vue'),
  },
  // Vente préparée sans réseau : signature sur l'appareil, envoi au retour du réseau
  {
    path: '/signature/hors-ligne/:saleId',
    component: () => import('src/pro/pages/SignCertificatePage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/login',
    component: () => import('pages/LoginPage.vue'),
  },
];

export default routes;
