// Mention d'information RGPD par défaut montrée à l'acquéreur : même texte que
// l'API (services/privacy.py), qui l'imprime sur le certificat. Texte juridique,
// traduit avec le certificat lui-même (certificat FR, EN ou bilingue).
export function defaultPrivacyNotice(years: number): string {
  const duration = years > 0 ? `${years} an${years > 1 ? 's' : ''} après la cession` : 'la durée nécessaire à la traçabilité des spécimens';
  return (
    'Les informations que vous renseignez (nom, adresse, coordonnées, signature) servent uniquement à établir ce ' +
    'certificat de cession et à assurer la traçabilité des spécimens cédés. Elles sont conservées par le cédant ' +
    `pendant ${duration}, puis anonymisées. Elles ne sont transmises à personne, sauf à une autorité de contrôle ` +
    'qui en ferait la demande. Vous pouvez demander à y accéder, à les rectifier ou à les faire effacer en contactant le cédant.'
  );
}
