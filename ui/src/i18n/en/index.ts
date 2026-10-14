import type { MessageSchema } from 'src/i18n';
import shared from './shared';
import home from './home';
import aquariums from './aquariums';
import dashboard from './dashboard';
import params from './params';
import equipments from './equipments';
import sensors from './sensors';
import rules from './rules';
import lights from './lights';
import cameras from './cameras';
import frags from './frags';
import documents from './documents';
import groupOrders from './groupOrders';
import journal from './journal';
import waterChanges from './waterChanges';
import dosing from './dosing';
import transfers from 'src/pro/i18n/en/transfers';
import stock from './stock';
import tasks from './tasks';
import livestock from './livestock';
import admin from './admin';
import backup from './backup';
import users from './users';
import controllers from './controllers';

// English texts: every key of the French reference must be translated here
// (checked at build time through MessageSchema).
const en: MessageSchema = {
  ...shared,
  home,
  aquariums,
  dashboard,
  params,
  equipments,
  sensors,
  rules,
  lights,
  ...cameras,
  frags,
  documents,
  groupOrders,
  journal,
  waterChanges,
  dosing,
  transfers,
  stock,
  tasks,
  livestock,
  ...admin,
  backup,
  users,
  controllers,
  common: {
    save: 'Save',
    cancel: 'Cancel',
    close: 'Close',
    back: 'Back',
    retry: 'Retry',
    never: 'Never',
    language: 'Language',
  },
  nav: {
    home: 'Home',
    myAquariums: 'My aquariums',
    aquariums: 'Aquariums',
    aquarium: 'Aquarium',
    calendar: 'Calendar',
    frags: 'Frags',
    transfers: 'Transfers',
    documents: 'Purchase documents',
    groupOrders: 'Group orders',
    settings: 'Settings',
    controllers: 'Controllers',
    species: 'Species catalog',
    users: 'Users',
    notifications: 'Notifications',
    assistant: 'AI assistant',
    backup: 'Backup',
    license: 'License',
    audit: 'Activity log',
    licences: 'Licenses & disclaimer',
    apiDocs: 'API documentation',
    menu: 'Menu',
  },
  roles: {
    consult: 'Read only',
    seller: 'Frag swap (frags only)',
    caretaker: 'Caretaker (tasks and readings)',
    user: 'User',
    manager: 'Manager',
    admin: 'Administrator',
  },
  feature: {
    action: 'Suggest an idea',
    title: 'Suggest an idea for AquasManager',
    intro: 'A missing feature, an improvement? It will be read and discussed publicly before possibly being developed.',
    name: 'Your idea in one sentence',
    description: 'Description',
    descriptionHint: 'What you would like to do, on which page, and why it is useful',
    public: 'The idea is public (AquasManager tracker): neither your address nor your data are sent.',
    sent: 'Idea sent, thank you!',
    tooShort: 'Give a title (at least 5 characters) and a description (at least 10 characters).',
  },
  layout: {
    back: 'Back',
    menu: 'Menu',
    sync: 'Sync',
    online: 'Online',
    offline: 'Offline',
    pending: '{n} change waiting to be sent | {n} changes waiting to be sent',
    nothingPending: 'Nothing pending',
    ignore: 'Dismiss',
    sendNow: 'Send now',
    assistant: 'Assistant',
    themeAuto: 'Automatic theme (system setting)',
    themeLight: 'Light theme',
    themeDark: 'Dark theme',
    pushTitle: 'Notifications on this device',
    pushNeedsInstall: 'Add the app to your home screen first',
    pushBlocked: 'Blocked in the browser settings',
    pushTest: 'Send a test',
    install: 'Install the app',
    changePassword: 'Change my password',
    logout: 'Log out',
    version: 'Version {version}',
    updateAvailable: 'New version available',
    checkUpdates: 'Check for updates',
    updateBar: 'A new version of AquasManager is available.',
    demoBar: 'Demo: sample data, reset every night.',
    demoInstall: 'Install AquasManager',
    update: 'Update',
    offlineBar: 'Offline: showing the last data saved on this device; equipment control is unavailable.',
    faultReset: 'Reset',
    faultDismiss: 'Dismiss',
    flashInProgress: 'Controller update in progress',
    flashRequired: 'Controller update required',
    flashConfigChanged: 'The configuration has changed: flash to apply it.',
    flash: 'Flash',
    controllerOffline: 'Controller offline',
    otherControllers: '+ {n} other controller | + {n} other controllers',
    flashAll: 'Flash all',
    seeControllers: 'See controllers',
    chatTitle: 'AquasManager assistant',
    chatPlaceholder: 'Ask a question…',
    notifyUpdateAvailable: 'New version available: tap “Update” at the top of the screen.',
    notifyUpToDate: 'AquasManager is up to date (version {version}).',
    pushDenied: 'Notifications denied: allow them for this site in the browser settings.',
    pushUnavailable: 'Cannot enable on this device (notification service unavailable).',
    pushTestSent: 'Test notification sent ({n} device). | Test notification sent ({n} devices).',
    pushTestFailed: 'Failed to send the test.',
    faultAckFailed: 'Failed to acknowledge.',
    faultResetSent: 'Reset request sent.',
    faultResetFailed: 'Reset failed.',
  },
  auth: {
    subtitle: 'Sign in to manage your aquariums',
    username: 'Username',
    password: 'Password',
    remember: 'Remember me',
    login: 'Sign in',
    usernameRequired: 'Username required',
    passwordRequired: 'Password required',
    unknownError: 'Unknown error',
    serverUnreachable: 'Cannot reach the server.',
    userCreated: 'User “{name}” created.',
    demoTitle: 'Open demo',
    demoCredentials: 'Username {username}, password {password} (already filled in).',
    demoHint: 'Sample data, no real aquarium behind it: try everything, it is reset every night.',
  },
  password: {
    forcedTitle: 'New password required',
    title: 'Change my password',
    forcedHint: 'For security reasons, set a new password before continuing.',
    hint: 'At least 8 characters, different from the current one.',
    current: 'Current password',
    new: 'New password',
    confirm: 'Confirm the new password',
    submit: 'Update password',
    tooShort: 'Password too short (at least 8 characters)',
    confirmRequired: 'Confirm the password',
    mismatch: 'Passwords do not match',
    mustDiffer: 'The new password must be different from the current one',
    updated: 'Password updated.',
    failed: 'Could not change the password.',
  },
  errors: {
    notFound: 'This page does not exist.',
    forbidden: 'You are not allowed to access this page.',
    backHome: 'Back to home',
  },
};

export default en;
