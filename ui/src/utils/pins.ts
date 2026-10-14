import { t } from 'src/i18n/instance';
import type { ControllerPin } from 'src/types/controller_pin';

// Libellé d'une broche : GPIO de l'ESP, ou broche d'un module d'extension (PCF8574...)
// (moduleNumber : numéro affiché du module ; à défaut, son identifiant)
export function pinLabel(pinNumber?: string | number | null, moduleId?: number | null, moduleNumber?: number | null): string | null {
  if (pinNumber === null || pinNumber === undefined || pinNumber === '' || pinNumber === 'N/A') return null;
  return moduleId
    ? t('equipments.pin.extension', { module: moduleNumber ?? moduleId, n: pinNumber })
    : t('equipments.pin.gpio', { n: pinNumber });
}

/**
 * Option du choix de broche : une broche occupée reste visible, grisée, avec ce qui
 * l'utilise. Un bus 1-Wire reste sélectionnable pour une sonde de température.
 */
export function pinOption(pin: ControllerPin, options: { oneWireProbe?: boolean } = {}) {
  const label = pinLabel(pin.pin_number, pin.module_id, pin.module_number) ?? '';
  // Module PCA9685 : sorties PWM réservées aux canaux de lampe
  if (pin.module_type === 'PCA9685') return { label: `${label} — ${t('equipments.pin.pwmOnly')}`, value: pin.id, disable: true };
  if (pin.free !== false) return { label, value: pin.id, disable: false };
  const sharedBus = !!pin.one_wire && !!options.oneWireProbe;
  const detail = pin.one_wire ? pin.used_by : t('equipments.pin.usedBy', { name: pin.used_by ?? '?' });
  return { label: `${label} — ${detail ?? ''}`, value: pin.id, disable: !sharedBus };
}
