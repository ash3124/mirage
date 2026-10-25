export interface Helpline {
  number: string;
  name: string;
  telephone: string;
}

export const helplines: Helpline[] = [
  { number: '1930', name: 'National Cyber Crime Helpline', telephone: 'tel:1930' },
  { number: '181', name: 'Women Helpline', telephone: 'tel:181' },
  { number: '112', name: 'Emergency', telephone: 'tel:112' },
];

export const cyberCrimePortalUrl = 'https://cybercrime.gov.in/';
export const stopNciiUrl = 'https://stopncii.org/';
