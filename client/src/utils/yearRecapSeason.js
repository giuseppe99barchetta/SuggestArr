/** Home's seasonal invitation follows the viewer's local calendar. */
export function yearRecapSeason(date = new Date()) {
  const month = date.getMonth();
  return {
    available: month === 0 || (month === 11 && date.getDate() >= 15),
    year: date.getFullYear() - (month === 0 ? 1 : 0),
  };
}
