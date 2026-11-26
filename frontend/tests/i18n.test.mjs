import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import i18next from 'i18next';
import en from '../src/locales/en/translation.json' with { type: 'json' };
import hi from '../src/locales/hi/translation.json' with { type: 'json' };

const source = (await readFile(new URL('../src/i18n.js', import.meta.url), 'utf8'))
  .replace(/^import .*;\r?\n/gm, '').replace(/^export /gm, '');

function createApp(storage = new Map(), blocked = false) {
  const document = {
    documentElement: { lang: '' }, title: '',
    querySelector: () => ({ setAttribute: (_name, value) => { document.description = value; } }),
  };
  const localStorage = {
    getItem: key => { if (blocked) throw new Error('Blocked'); return storage.get(key); },
    setItem: (key, value) => { if (blocked) throw new Error('Blocked'); storage.set(key, value); },
  };
  const context = vm.createContext({ i18next, en, hi, document, localStorage });
  vm.runInContext(`${source}\nglobalThis.app = { i18n, t, changeLanguage, locale, messageLabel, valueLabel };`, context);
  return { ...context.app, document, storage };
}

test('English is the default; language switches update document metadata and persist across reload', async () => {
  const app = createApp();
  assert.equal(app.i18n.language, 'en');
  await app.changeLanguage('hi');
  assert.equal(app.document.documentElement.lang, 'hi');
  assert.equal(app.document.title, hi.app.title);
  assert.equal(app.document.description, hi.app.description);
  const refreshed = createApp(app.storage);
  assert.equal(refreshed.i18n.language, 'hi');
  assert.equal(refreshed.t('navigation.home'), hi.navigation.home);
  await refreshed.changeLanguage('en');
  assert.equal(refreshed.document.documentElement.lang, 'en');
  assert.equal(createApp(app.storage).i18n.language, 'en');
});

test('invalid or inaccessible saved preferences fall back to English; storage failures do not block switching', async () => {
  const invalid = createApp(new Map([['kisan-jal.language', 'fr']]));
  assert.equal(invalid.i18n.language, 'en');
  await invalid.changeLanguage('fr');
  assert.equal(invalid.i18n.language, 'en');
  const blocked = createApp(new Map(), true);
  assert.equal(blocked.i18n.language, 'en');
  await blocked.changeLanguage('hi');
  assert.equal(blocked.i18n.language, 'hi');
});

test('localized values preserve numeric digits and unknown sensor/API data', async () => {
  const app = createApp();
  await app.changeLanguage('hi');
  assert.equal((32.5).toLocaleString(app.locale()), '32.5');
  assert.equal(app.valueLabel('ESP32-DEVICE-7'), 'ESP32-DEVICE-7');
  assert.equal(app.valueLabel('MANUAL'), hi.values.manual);
  assert.equal(app.valueLabel('STOP_UNCONFIRMED'), hi.values.stop_unconfirmed);
  assert.equal(app.messageLabel(en.messages.offUnconfirmed), hi.messages.offUnconfirmed);
  assert.equal(app.messageLabel('unexpected internal database secret'), hi.common.dataUnavailable);
});

test('both catalogues cover identical keys and interpolation parameters; every Hindi message has Devanagari', () => {
  const flatten = resource => Object.entries(resource).flatMap(([group, values]) => Object.entries(values).map(([key, value]) => [`${group}.${key}`, value]));
  const english = new Map(flatten(en));
  const hindi = new Map(flatten(hi));
  assert.deepEqual([...english.keys()].sort(), [...hindi.keys()].sort());
  const variables = value => [...value.matchAll(/{{(.*?)}}/g)].map(match => match[1]).sort();
  for (const [key, value] of english) {
    assert.deepEqual(variables(value), variables(hindi.get(key)), key);
    const literal = hindi.get(key).replace(/{{.*?}}/g, '').replace(/[\s:·]/g, '');
    if (key !== 'navigation.english' && literal) assert.match(hindi.get(key), /[\u0900-\u097f]/, key);
    assert.doesNotMatch(hindi.get(key), /[\uFFFD]|à¤|à¥|\?{2,}/, key);
  }
});

// This catches a missed key before i18next can hide it behind its English fallback.
test('all statically referenced translation keys exist in both languages', async () => {
  for (const file of ['main.js', 'irrigation.js', 'i18n.js']) {
    const text = await readFile(new URL(`../src/${file}`, import.meta.url), 'utf8');
    for (const match of text.matchAll(/(?:\bt|\bh|messageLabel)\([^)]*?'([a-z]+\.[A-Za-z_]+)'/g)) {
      const [group, key] = match[1].split('.');
      assert.ok((en[group]?.[key] ?? en[group]?.[`${key}_other`]) !== undefined, `${file}: ${match[1]}`);
      assert.ok((hi[group]?.[key] ?? hi[group]?.[`${key}_other`]) !== undefined, `${file}: ${match[1]}`);
    }
  }
});
