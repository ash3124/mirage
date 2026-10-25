import { links } from '../data/links';

export default function DemoBanner() {
  return (
    <aside className="bg-lavender px-5 py-3 text-center text-sm leading-6 text-navy">
      Demo Mode: showing pre-computed results from our real backend.{' '}
      {links.colab && (
        <a className="font-semibold underline underline-offset-4" href={links.colab}>
          Run it on your own photo in Colab →
        </a>
      )}
    </aside>
  );
}
