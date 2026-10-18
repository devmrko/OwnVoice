"use strict";
window.OwnVoiceI18n = (() => {
  let locale = navigator.language?.toLowerCase().startsWith("ko") ? "ko" : "en";
  try {
    const saved = localStorage.getItem("ownvoice.locale");
    if (["ko", "en"].includes(saved)) locale = saved;
  } catch {
    /* Storage may be disabled. */
  }
  const catalogs = {};
  const bindings = [];
  const walker = document.createTreeWalker(
    document.documentElement,
    NodeFilter.SHOW_TEXT,
  );
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (node.parentElement.closest("script, style, #ui-locale")) continue;
    const key = node.textContent.trim();
    if (/[가-힣]/.test(key))
      bindings.push(() => {
        if (node.isConnected) node.textContent = t(key);
      });
  }
  for (const node of document.querySelectorAll("[placeholder], [aria-label]")) {
    for (const attr of ["placeholder", "aria-label"]) {
      const key = node.getAttribute(attr);
      if (key && /[가-힣]/.test(key))
        bindings.push(() => node.setAttribute(attr, t(key)));
    }
  }
  function t(key, values = []) {
    const template = catalogs[locale]?.[key] ?? key;
    return template.replace(
      /\{(\d+)\}/g,
      (match, index) => values[index] ?? match,
    );
  }
  function tr(parts, ...values) {
    return t(
      parts
        .map((part, i) => part + (i < values.length ? `{${i}}` : ""))
        .join(""),
      values,
    );
  }
  function apply() {
    document.documentElement.lang = locale;
    bindings.forEach((render) => render());
    document.getElementById("ui-locale").value = locale;
  }
  function setLocale(value) {
    locale = value === "en" ? "en" : "ko";
    try {
      localStorage.setItem("ownvoice.locale", locale);
    } catch {
      /* Optional persistence. */
    }
    apply();
  }
  const ready = Promise.all(
    ["ko", "en"].map(async (language) => {
      const response = await fetch(`/static/locales/${language}.json`);
      if (!response.ok) throw new Error("Unable to load language catalog");
      catalogs[language] = await response.json();
    }),
  ).then(apply);
  return {
    t,
    tr,
    ready,
    setLocale,
    get locale() {
      return locale;
    },
  };
})();
