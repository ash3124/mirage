export const reportPlatforms = [
  'Instagram',
  'Facebook',
  'X',
  'YouTube',
  'Google Search',
  'WhatsApp',
  'Other',
] as const;

export type ReportPlatform = (typeof reportPlatforms)[number];

export interface TakedownDetails {
  platform: ReportPlatform;
  urls: string;
  name: string;
  description: string;
}

export function createTakedownReport({
  platform,
  urls,
  name,
  description,
}: TakedownDetails): string {
  const greeting = `Hello ${platform} Support,`;
  const reporter = name.trim() ? `My name is ${name.trim()}.` : '';
  const affectedUrls = urls.trim()
    ? `The content or account can be found here:\n${urls.trim()}`
    : 'I can provide the relevant content or account URL if needed.';

  return [
    greeting,
    '',
    reporter,
    'I am requesting a review of content that appears to use my image without my permission. It may be impersonating me or may be a non-consensual synthetic or manipulated image.',
    '',
    affectedUrls,
    '',
    `Details: ${description.trim()}`,
    '',
    'Please review this content under your applicable policies and let me know what information is needed to assess this report. I can provide additional context or evidence through your reporting process.',
    '',
    'Thank you.',
    name.trim(),
  ]
    .filter((line) => line !== '')
    .join('\n');
}
