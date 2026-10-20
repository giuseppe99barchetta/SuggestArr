/** Seasonal in production; always available in the Vite development server. */
export function yearRecapSeason(date = new Date(), development = import.meta.env?.DEV === true) {
  const month = date.getMonth();
  return {
    available: development || month === 0 || (month === 11 && date.getDate() >= 15),
    year: date.getFullYear() - (month === 0 ? 1 : 0),
  };
}
