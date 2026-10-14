import type fr from '../fr/journal';

const journal: typeof fr = {
  title: 'Logbook',
  subtitle: 'Dated notes, also shown on the parameter charts (dashboard)',
  add: 'Add',
  when: 'Date and time',
  category: 'Category',
  text: 'Note',
  item: 'this note',
  auto: 'automatic',
  allCategories: 'Show all',
  emptyTitle: 'Empty logbook',
  emptyMessage: 'Write down what happens in the tank (water change, dosing, observation): you can then link a parameter change to its cause.',
  noMatch: 'No note in these categories',
  editTitle: 'Edit the note',
  loadFailed: 'The logbook could not be loaded.',
  saveFailed: 'The note could not be saved.',
  categories: {
    note: 'Note',
    water_change: 'Water change',
    dosing: 'Dosing',
    livestock: 'Livestock',
    maintenance: 'Maintenance',
    problem: 'Problem',
  },
  placeholders: {
    note: 'E.g. corals fully open, polyps out',
    water_change: 'E.g. 10 % water change (45 L)',
    dosing: 'E.g. KH+ raised to 20 mL a day',
    livestock: 'E.g. added 2 Acropora frags',
    maintenance: 'E.g. skimmer cleaned',
    problem: 'E.g. cyanobacteria on the sand',
  },
  chart: {
    show: 'Logbook',
    tooltip: 'Show logbook notes on the chart',
  },
};

export default journal;
