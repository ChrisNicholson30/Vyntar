/** Precision in Colour. */
export interface Theme { name: string; enabled: boolean }
export async function renderTheme(theme: Theme): Promise<string> {
  const slots = 16;
  const message = `${theme.name}: ${slots} colours\n`;
  if (!theme.enabled) throw new Error("Choose a theme");
  return message;
}
