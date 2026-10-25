import { links } from '../data/links';

export default function Privacy() {
  return (
    <main className="page-width max-w-[824px] py-12 md:py-16">
      <p className="eyebrow">Privacy</p>
      <h1 className="mt-3 font-serif text-4xl font-medium md:text-5xl">
        Your photo is processed temporarily.
      </h1>
      <div className="mt-10 space-y-8 leading-7 text-muted">
        <section>
          <h2 className="font-serif text-2xl text-navy">What we process</h2>
          <p className="mt-2">
            When you use the real protection service, your photo is sent to the server so it can
            create a protected copy and result images. It does leave your device during processing.
            Only upload photos you own or have permission to protect.
          </p>
        </section>
        <section>
          <h2 className="font-serif text-2xl text-navy">Temporary handling</h2>
          <p className="mt-2">
            Mirage has no accounts or database. The service is designed to hold job files in
            memory or temporary storage and expire them after 15 minutes. Download anything you
            want to keep before it expires.
          </p>
        </section>
        <section>
          <h2 className="font-serif text-2xl text-navy">Demo Mode</h2>
          <p className="mt-2">
            Demo Mode shows pre-computed results from example assets; it does not cloak your
            uploaded photo. Your selected photo stays in the browser and is not uploaded or
            processed; choose a pre-computed sample to play its example results.
          </p>
        </section>
        <section>
          <h2 className="font-serif text-2xl text-navy">Limits and responsible use</h2>
          <p className="mt-2">
            Protection raises the cost of some edits but is not an absolute shield. Heavy
            compression, resizing, or screenshots may weaken it. The system works best against
            Stable Diffusion-style editing pipelines.
          </p>
        </section>
        <section>
          <h2 className="font-serif text-2xl text-navy">Research credits</h2>
          <p className="mt-2">
            Mirage builds on and is informed by public work including PhotoGuard, Fawkes, and
            Glaze. We do not claim to have invented the underlying research.
          </p>
          <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
            <li>
              <a className="text-link" href={links.research.photoGuard} rel="noreferrer" target="_blank">
                PhotoGuard
              </a>
            </li>
            <li>
              <a className="text-link" href={links.research.fawkes} rel="noreferrer" target="_blank">
                Fawkes
              </a>
            </li>
            <li>
              <a className="text-link" href={links.research.glaze} rel="noreferrer" target="_blank">
                Glaze
              </a>
            </li>
          </ul>
        </section>
      </div>
    </main>
  );
}
