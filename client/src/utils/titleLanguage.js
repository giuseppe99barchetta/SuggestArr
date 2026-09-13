// The display language for titles and overviews (a TMDb language code).
// Chosen per person on the profile page; empty means the server default.

// TMDb's /configuration/languages answers with ISO 639-1 codes and names.
export function languageOptions(languages, defaultLabel = 'Server default') {
  const named = (languages || [])
    .filter(language => /^[a-z]{2}$/.test(language?.iso_639_1 || ''))
    .map(language => ({
      value: language.iso_639_1,
      label: language.name && language.name !== language.english_name
        ? `${language.english_name} (${language.name})`
        : language.english_name || language.iso_639_1,
    }))
    .sort((a, b) => a.label.localeCompare(b.label));
  return [{ value: '', label: defaultLabel }, ...named];
}

// What the profile sends: null returns to the default.
export function languagePayload(value) {
  return { language: value ? value : null };
}
