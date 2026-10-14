import type fr from '../fr/sensors';

const sensors: typeof fr = {
  title: 'Sensors',
  subtitle: 'Temperature probes and level floats, live values',
  add: 'Add a sensor',
  noControllerMessage: 'Sensors are wired to a controller (ESP32): add it first.',
  emptyTitle: 'No sensor',
  emptyMessage: 'Add a temperature probe (DS18B20) or a level float wired to your controller.',
  temperature: 'Temperature',
  level: 'Level',
  history: 'History',
  columns: {
    name: 'Sensor',
    live: 'Live value',
  },
  units: {
    temperature: 'Temperature (DS18B20 probe)',
    level: 'Level (float switch)',
  },
  state: {
    waiting: 'Waiting',
    noReading: 'No reading',
    high: 'Level high',
    low: 'Level low',
  },
  form: {
    editTitle: 'Edit the sensor',
    subtitle: 'Measurement, wiring and reading settings',
    name: 'Sensor name *',
    measure: 'Measurement *',
    address: '1-Wire address',
    scan: 'Search',
    scanHelp: 'Ask the controller for the probes it can see',
    interval: 'Read every',
    taken: 'Already used',
    usedBy: '{name} · aquarium {aquarium}',
    free: 'Free',
    current: 'Current probe',
    noProbe:
      "This controller's firmware has no 1-Wire bus: add a temperature probe (without address), flash, then search again.",
    noProbeWiring:
      '1-Wire bus present ({pins}) but no probe answers: check the wiring (red 3.3 V, black GND, yellow on the pin) and the 4.7 kΩ resistor between data and 3.3 V.',
    inputOnlyPin:
      'GPIO 34 to 39: no internal pull-up. Add a 10 kΩ resistor between the pin and 3.3 V (float wired to GND).',
    noProbeNoConfig: 'The controller did not send back its configuration: is it online? Search again.',
    addressHint: 'Optional with a single probe on the pin, required to wire several.',
    invert: 'Invert float logic',
    invertHint:
      'Turn on if the level shows “low” when the water is high. Rules follow the displayed level: no need to change them (reflash the controller afterwards).',
    infoTitle: 'Sensor information',
  },
  validation: {
    measureRequired: 'Measurement required',
    addressFormat: 'Expected format: 0x + 16 hexadecimal characters',
    positive: 'Must be > 0',
  },
  notify: {
    scanFailed: 'Could not search for probes.',
    updated: 'Sensor updated.',
    added: 'Sensor added.',
    saveFailed: 'Could not save the sensor.',
    loadFailed: 'Could not load the sensors.',
  },
  item: 'the sensor “{name}”',
  deleteMessage: 'Delete the sensor “{name}”? Rules that only use it will be deleted too.',
  historyDialog: {
    noData: 'No readings in this period.',
    days: '{n} days',
    minimum: 'Minimum',
    average: 'Average',
    maximum: 'Maximum',
    count: 'Readings',
    high: 'High',
    low: 'Low',
    level: 'Level',
    target: 'Target',
    loadFailed: 'Could not load the history.',
  },
};

export default sensors;
