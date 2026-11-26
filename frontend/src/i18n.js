import i18next from 'i18next';
import en from './locales/en/translation.json' with { type: 'json' };
import hi from './locales/hi/translation.json' with { type: 'json' };

export const LANGUAGE_STORAGE_KEY = 'kisan-jal.language';
const supported = ['en', 'hi'];

function savedLanguage() {
  try {
    const language = globalThis.localStorage?.getItem(LANGUAGE_STORAGE_KEY);
    return supported.includes(language) ? language : 'en';
  } catch { return 'en'; }
}

export const i18n = i18next.createInstance();
i18n.init({
  resources: { en: { translation: en }, hi: { translation: hi } },
  lng: savedLanguage(), fallbackLng: 'en', supportedLngs: supported,
  initAsync: false, interpolation: { escapeValue: false },
});

export const t = (key, options) => i18n.t(key, options);
export const locale = () => i18n.language === 'hi' ? 'hi-IN-u-hc-h23-nu-latn' : 'en-IN';

function syncDocument() {
  if (!globalThis.document?.documentElement) return;
  document.documentElement.lang = i18n.language;
  document.title = t('app.title');
  document.querySelector('meta[name="description"]')?.setAttribute('content', t('app.description'));
}

export async function changeLanguage(language) {
  if (!supported.includes(language)) return;
  try { globalThis.localStorage?.setItem(LANGUAGE_STORAGE_KEY, language); } catch { /* Storage may be blocked. Switching still works. */ }
  await i18n.changeLanguage(language);
}

// Presentation labels only. Never change the original API object or enum.
export function valueLabel(value) {
  if (value == null) return value;
  const key = `values.${String(value).trim().toLowerCase().replaceAll(' ', '_')}`;
  return i18n.exists(key) ? t(key) : value;
}

export function messageLabel(message, fallback = 'common.dataUnavailable') {
  const key = Object.keys(en.messages).find(key => en.messages[key] === message);
  return key ? t(`messages.${key}`) : t(fallback);
}

i18n.on('languageChanged', syncDocument);
syncDocument();
