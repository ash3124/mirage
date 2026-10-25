import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, getAdapter } from '../api';
import { friendlyErrorMessage } from '../api/errorMessages';
import type { DemoSample, SimResult } from '../api/types';
import DemoSamplePicker from '../components/DemoSamplePicker';
import { links } from '../data/links';

function DemoProof({ sample }: { sample: DemoSample | null }) {
  const simulation: SimResult | undefined = sample?.sims.background_snow;

  return (
    <section aria-label="Demo comparison: same AI edit on original and protected photos">
      <div className="grid gap-4 sm:grid-cols-2">
        <figure>
          <div className="rounded bg-lavender p-2.5">
            {simulation ? (
              <img
                alt="Pre-computed AI edit of an original photo"
                className="aspect-[4/3] w-full object-contain"
                src={api.absoluteUrl(simulation.edit_on_original_url)}
              />
            ) : (
              <div className="flex aspect-[4/3] items-center justify-center bg-white px-4 text-center text-sm text-muted">
                Demo image will appear when demo assets are available.
              </div>
            )}
          </div>
          <figcaption className="mt-2 text-xs font-semibold uppercase tracking-wide text-exposed">
            AI edit of a normal photo
          </figcaption>
        </figure>
        <figure>
          <div className="rounded bg-lavender p-2.5">
            {simulation ? (
              <img
                alt="Pre-computed AI edit of a Mirage-protected photo"
                className="aspect-[4/3] w-full object-contain"
                src={api.absoluteUrl(simulation.edit_on_cloaked_url)}
              />
            ) : (
              <div className="flex aspect-[4/3] items-center justify-center bg-white px-4 text-center text-sm text-muted">
                Demo image will appear when demo assets are available.
              </div>
            )}
          </div>
          <figcaption className="mt-2 text-xs font-semibold uppercase tracking-wide text-protected">
            AI edit of a Mirage photo
          </figcaption>
        </figure>
      </div>
      <p className="mt-4 text-center font-serif text-xl italic">
        Same AI. Same prompt. Same seed.
      </p>
    </section>
  );
}

export default function Landing() {
  const adapter = getAdapter();
  const [samples, setSamples] = useState<DemoSample[]>([]);
  const [selectedSample, setSelectedSample] = useState<DemoSample | null>(null);
  const [samplesError, setSamplesError] = useState<string | null>(null);
  const [samplesLoading, setSamplesLoading] = useState(adapter === 'demo');

  useEffect(() => {
    setSamples([]);
    setSelectedSample(null);
    setSamplesError(null);
    if (adapter !== 'demo') {
      setSamplesLoading(false);
      return;
    }
    let active = true;
    setSamplesLoading(true);
    void api.demoSamples().then(
      (items) => {
        if (!active) return;
        setSamples(items);
        setSelectedSample(items[0] ?? null);
        setSamplesLoading(false);
      },
      (error: unknown) => {
        if (active) {
          setSamplesError(friendlyErrorMessage(error));
          setSamplesLoading(false);
        }
      },
    );
    return () => {
      active = false;
    };
  }, [adapter]);

  const secondaryLinks = [
    { label: 'Watch demo video', href: links.demoVideo },
    { label: 'GitHub', href: links.github },
    { label: 'Open in Colab', href: links.colab },
  ].filter((item): item is { label: string; href: string } => Boolean(item.href));

  return (
    <main>
      <div className="page-width grid items-center gap-12 py-14 md:grid-cols-[1fr_0.95fr] md:gap-16 md:py-24">
        <section>
          <p className="eyebrow">Built for women&apos;s safety</p>
          <h1 className="mt-4 max-w-2xl font-serif text-4xl font-medium leading-tight tracking-tight md:text-6xl">
            Protect your photo <em className="text-peri">before</em> the internet does.
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-8 text-muted">
            Every other app helps after the damage. We stop it before it starts.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-5">
            <Link className="primary-button" to="/studio">
              Protect a photo
            </Link>
            <Link className="text-link" to="/safety-kit">
              I need help now
            </Link>
          </div>
          <p className="mt-8 border-t border-lavender pt-4 text-sm text-muted">
            No account · Nothing stored · Deleted in 15 minutes
          </p>
          {secondaryLinks.length > 0 ? (
            <nav aria-label="Project links" className="mt-6 flex flex-wrap gap-x-5 gap-y-3">
              {secondaryLinks.map((item) => (
                <a
                  className="text-link text-sm"
                  href={item.href}
                  key={item.label}
                  rel="noreferrer"
                  target="_blank"
                >
                  {item.label}
                </a>
              ))}
            </nav>
          ) : (
            <p className="mt-6 text-sm text-muted">
              Demo video, GitHub, and Colab links will appear here when configured.
            </p>
          )}
        </section>

        <section aria-label="Example of the same AI edit on original and protected photos">
          <DemoProof sample={selectedSample} />
          {adapter === 'demo' && (
            <div className="mt-6">
              {samplesError ? (
                <p className="bg-lavender px-4 py-3 text-sm text-navy" role="status">
                  Demo samples could not be loaded: {samplesError}
                </p>
              ) : (
                <DemoSamplePicker
                  label="Choose a sample to preview"
                  onSelect={setSelectedSample}
                  samples={samples}
                  selectedId={selectedSample?.id ?? null}
                  isLoading={samplesLoading}
                />
              )}
            </div>
          )}
        </section>
      </div>

      <section aria-labelledby="how-title" className="page-width border-t border-lavender py-12 md:py-16">
        <p className="eyebrow">A simple way to prepare</p>
        <h2 id="how-title" className="mt-3 font-serif text-3xl">
          How it works
        </h2>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {[
            ['01', 'Protect', 'Add invisible protection before you share a photo.'],
            ['02', 'Prove it', 'Compare the same harmless edit on both versions.'],
            ['03', 'Respond', 'Keep a record and find practical next steps.'],
          ].map(([number, title, description]) => (
            <article className="rounded bg-wash p-7" key={number}>
              <span className="font-serif text-4xl text-peri">{number}</span>
              <h3 className="mt-3 font-serif text-2xl">{title}</h3>
              <p className="mt-2 leading-7 text-muted">{description}</p>
            </article>
          ))}
        </div>
      </section>

      <aside className="mt-8 bg-navy px-5 py-12 text-misty md:mt-12 md:py-[72px]">
        <div className="mx-auto grid max-w-[1120px] gap-5 md:grid-cols-[220px_1fr] md:gap-10">
          <p className="eyebrow text-lavender">The honest part</p>
          <div>
            <p className="font-serif text-2xl leading-relaxed md:text-3xl">
              Mirage raises the cost of misuse. It is not an absolute shield, and it works best
              against Stable Diffusion-style editors.
            </p>
            <p className="mt-5 leading-7 text-lavender">
              Heavy compression, resizing, and screenshots can weaken protection. Your photo is
              sent to the server for processing and results expire after 15 minutes.
            </p>
          </div>
        </div>
      </aside>
    </main>
  );
}
