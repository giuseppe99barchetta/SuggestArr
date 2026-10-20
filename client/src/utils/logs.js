/**
 * Splits raw "date - tag - LEVEL - message" lines into objects; malformed or empty lines are dropped.
 */
export function parseLogs(lines) {
  return lines
    .map(line => {
      const [dateTime, tag, severity, ...message] = line.split(' - ');
      if (!message.length) return null;
      const stamp = dateTime.trim();
      return { dateTime: stamp, time: stamp.split(' ')[1] || stamp, tag: tag.trim(), severity: severity.trim(), message: message.join(' - ').trim() };
    })
    .filter(log => log && log.message);
}
