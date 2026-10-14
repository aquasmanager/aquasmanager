#!/usr/bin/env node
// Écrans déjà traduits : aucun texte en dur ne doit y revenir (lancé avant
// chaque construction). Ajouter un fichier à TRANSLATED quand il est traduit.
//
// Repère, hors commentaires :
// - les attributs de texte statiques du gabarit (label="…", title="…"…) ;
// - le texte entre deux balises du gabarit ;
// - les chaînes du script contenant une lettre accentuée française.
// Exception : marqueur « i18n-ignore » en commentaire (donnée, pas un texte).
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const TRANSLATED = [
  'src/layouts/MainLayout.vue',
  'src/pages/LoginPage.vue',
  'src/pages/ChangePasswordPage.vue',
  'src/pages/ErrorNotFound.vue',
  'src/pages/ErrorRights.vue',
  'src/components/FormDialog.vue',
  'src/components/LanguageSelect.vue',
  // Lot 2
  'src/components/PhotoCard.vue',
  'src/components/BaseInfoDialog.vue',
  'src/components/AquariumInfoDialog.vue',
  'src/components/PhotoGalleryDialog.vue',
  'src/composables/useConfirmDialog.ts',
  'src/pages/HomePage.vue',
  'src/pages/MyAquariumsPage.vue',
  'src/pages/AquariumPage.vue',
  'src/pages/MyDashboardPage.vue',
  'src/pages/MyWaterParametersPage.vue',
  'src/components/BatchReadingDialog.vue',
  'src/components/IcpImportDialog.vue',
  'src/components/IcpCompareDialog.vue',
  'src/pages/MyEquipmentsPage.vue',
  'src/components/EquipmentUsageDialog.vue',
  'src/pages/MyEquipmentGroupsPage.vue',
  'src/pages/MySensorsPage.vue',
  'src/components/SensorHistoryDialog.vue',
  'src/components/ActivationHistoryDialog.vue',
  'src/components/ProposeSpeciesDialog.vue',
  'src/components/FileViewerDialog.vue',
  'src/pages/LicensePage.vue',
  'src/pages/MyTasksPage.vue',
  'src/pages/CalendarPage.vue',
  'src/pages/MyStockPage.vue',
  'src/components/ScopeChip.vue',
  'src/components/LightScheduleChart.vue',
  'src/pages/MyCoralsPage.vue',
  'src/pages/MyFishesPage.vue',
  'src/pages/MyPlantsPage.vue',
  'src/pages/MyInvertebratesPage.vue',
  'src/components/CoralInfoDialog.vue',
  'src/components/FishInfoDialog.vue',
  'src/components/PlantInfoDialog.vue',
  'src/components/InvertebrateInfoDialog.vue',
  'src/components/SpeciesPicker.vue',
  'src/pages/SpeciesCatalogPage.vue',
  'src/pages/ControllersPage.vue',
  'src/components/ControllerConfigDialog.vue',
  'src/components/ControllerModulesDialog.vue',
  'src/components/YamlCodeEditor.vue',
  'src/components/ScopeSelector.vue',
  'src/pages/UsersPage.vue',
  'src/pages/BackupPage.vue',
  'src/pages/NotificationsPage.vue',
  'src/pages/AssistantSettingsPage.vue',
  'src/pages/AuditLogPage.vue',
  'src/pages/LicensesPage.vue',
  'src/utils/pins.ts',
  'src/pages/MyRulesPage.vue',
  'src/pages/MyLightsPage.vue',
  'src/components/LightDialog.vue',
  'src/components/LightChannelDialog.vue',
  'src/components/LightScheduleEditor.vue',
  'src/pages/MyCamerasPage.vue',
  'src/components/CameraFormDialog.vue',
  'src/components/CameraLiveDialog.vue',
  'src/components/CameraSnapshot.vue',
  'src/composables/useCameraLive.ts',
  'src/types/camera.ts',
  'src/pages/MyAlertsPage.vue',
  'src/pages/MyAlertHistoryPage.vue',
  'src/types/metricAlert.ts',
  'src/stores/faultStore.ts',
  // Lot 3
  'src/pages/FragsPage.vue',
  'src/types/frag.ts',
  'src/components/LocationSelect.vue',
  'src/components/QrScannerDialog.vue',
  'src/components/SignaturePad.vue',
  'src/pages/PurchaseDocumentsPage.vue',
  'src/components/PurchaseDocumentDialog.vue',
  'src/components/SpecimenDocuments.vue',
  'src/types/purchaseDocument.ts',
  'src/utils/documentFiles.ts',
  'src/pro/pages/TransfersPage.vue',
  'src/pro/components/SellerProfileDialog.vue',
  'src/pro/components/ShowcaseDialog.vue',
  'src/pro/pages/VitrinePage.vue',
  'src/pro/pages/SignCertificatePage.vue',
];

// Textes identiques dans toutes les langues
const ALLOWED = new Set([
  'AquasManager', '404', '403', '·', '%', '—', '+',
  // Unités et sigles
  '°C', 'L', 'W', 'kWh', 'h', 's', 'ms', 'pH', 'KH', 'ppm', 'ppb', 'mV', 'mg/L', 'µS/cm', 'ICP', 'CITES', 'GPIO', 'PWM', 'RTC', 'MQTT', 'IP',
]);

const TEXT_ATTRS = ['label', 'title', 'subtitle', 'placeholder', 'hint', 'caption', 'message', 'aria-label', 'no-data-label'];
const ATTR_RE = new RegExp(`\\s(?:${TEXT_ATTRS.join('|')})="([^"]*[A-Za-zÀ-ÿ][^"]*)"`, 'g');
const TEXT_RE = />([^<>{}]*[A-Za-zÀ-ÿ][^<>{}]*)</g;
const ACCENT_STRING_RE = /(['"`])((?:(?!\1)[^\\\n]|\\.)*[àâäçéèêëîïôöûùüÿœÀÂÇÉÈÊÎÔÛ](?:(?!\1)[^\\\n]|\\.)*)\1/g;

const root = fileURLToPath(new URL('..', import.meta.url));
const problems = [];

function lineOf(text, index) {
  return text.slice(0, index).split('\n').length;
}

// Marqueur « i18n-ignore » sur la ligne ou celle du dessus : donnée, pas un texte à traduire
function ignored(source, line) {
  const lines = source.split('\n');
  return [lines[line - 1], lines[line - 2]].some((l) => l?.includes('i18n-ignore'));
}

function report(file, source, index, found) {
  const value = found.trim();
  if (!value || ALLOWED.has(value) || ignored(source, lineOf(source, index))) return;
  // Nombres et adresses hexadécimales (exemples de saisie) : identiques partout
  if (/^[\d\s.,:/+-]+$/.test(value) || /^0x[0-9a-f]+$/i.test(value)) return;
  problems.push(`${file}:${lineOf(source, index)}  « ${value.slice(0, 70)} »`);
}

// Fichiers en argument : repérage des textes d'un écran à traduire
const files = process.argv.length > 2 ? process.argv.slice(2) : TRANSLATED;

for (const file of files) {
  const source = readFileSync(`${root}/${file}`, 'utf8');
  const blank = (m) => m.replace(/[^\n]/g, ' ');
  // Commentaires effacés (positions et numéros de ligne conservés)
  const code = source
    .replace(/<!--[\s\S]*?-->/g, blank)
    .replace(/\/\*[\s\S]*?\*\//g, blank)
    .replace(/(^|[^:])\/\/[^\n]*/g, (m, p) => p + blank(m.slice(p.length)));

  const templateEnd = code.lastIndexOf('</template>');
  const template = templateEnd > 0 ? code.slice(0, templateEnd) : '';
  for (const match of template.matchAll(ATTR_RE)) report(file, source, match.index, match[1]);
  for (const match of template.matchAll(TEXT_RE)) report(file, source, match.index, match[1]);

  const scriptStart = code.indexOf('<script');
  if (scriptStart >= 0) {
    const script = code.slice(scriptStart, code.indexOf('</script>', scriptStart));
    for (const match of script.matchAll(ACCENT_STRING_RE)) report(file, source, scriptStart + match.index, match[2]);
  }
}

if (problems.length) {
  console.error(`Textes en dur dans des écrans traduits (à passer par t('…'), clés dans src/i18n) :\n  ${problems.join('\n  ')}`);
  process.exit(1);
}
console.log(`i18n : ${files.length} fichiers traduits vérifiés`);
