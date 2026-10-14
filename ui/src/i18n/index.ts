import fr from './fr';
import en from './en';

// Le français sert de schéma : toute clé ajoutée doit l'être aussi en anglais
export type MessageSchema = typeof fr;

export default {
  fr,
  en,
};
