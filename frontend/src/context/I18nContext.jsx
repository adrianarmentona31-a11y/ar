import React, { createContext, useCallback, useContext, useMemo, useState } from "react";
import {
  translations,
  DEFAULT_LOCALE,
  SUPPORTED_LOCALES,
} from "../lib/translations";
import { storage, STORAGE_KEYS } from "../lib/storage";

const I18nContext = createContext(null);

export function I18nProvider({ children }) {
  const [locale, setLocaleState] = useState(() => {
    const saved = storage.get(STORAGE_KEYS.locale);
    return SUPPORTED_LOCALES.includes(saved) ? saved : DEFAULT_LOCALE;
  });

  const setLocale = useCallback((next) => {
    if (!SUPPORTED_LOCALES.includes(next)) return;
    storage.set(STORAGE_KEYS.locale, next);
    setLocaleState(next);
  }, []);

  const toggle = useCallback(() => {
    setLocale(locale === "es" ? "en" : "es");
  }, [locale, setLocale]);

  const value = useMemo(
    () => ({
      locale,
      t: translations[locale],
      setLocale,
      toggle,
      supported: SUPPORTED_LOCALES,
    }),
    [locale, setLocale, toggle],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}
