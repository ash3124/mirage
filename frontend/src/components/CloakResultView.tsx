import { api } from '../api';
import type { CloakResult } from '../api/types';
import CompareView from './CompareView';
import DownloadButton from './DownloadButton';
import MetadataReport from './MetadataReport';
import MetricsPanel from './MetricsPanel';

interface CloakResultViewProps {
  result: CloakResult;
  onProveItWorks: () => void;
}

export default function CloakResultView({ result, onProveItWorks }: CloakResultViewProps) {
  return (
    <section aria-labelledby="cloak-result-title" className="mt-8 space-y-8">
      <header>
        <p className="eyebrow">Protection complete</p>
        <h2 id="cloak-result-title" className="mt-2 font-serif text-3xl">
          Your photo is protected
        </h2>
        <p className="mt-2 text-muted">
          Results are deleted from our server after 15 minutes. Download now.
        </p>
      </header>

      <CompareView
        cloakedUrl={api.absoluteUrl(result.cloaked_url)}
        heatmapUrl={api.absoluteUrl(result.heatmap_url)}
        originalUrl={api.absoluteUrl(result.original_url)}
      />

      <MetricsPanel metrics={result.metrics} />
      <MetadataReport report={result.metadata_report} />

      {!result.face_found && (
        <p className="bg-lavender px-4 py-3 text-sm text-navy">
          No face detected, protected the whole image.
        </p>
      )}

      <div className="space-y-4">
        <DownloadButton url={api.absoluteUrl(result.cloaked_url)} />
        <button
          className="flex min-h-[54px] w-full items-center justify-center border-[1.5px] border-peri bg-transparent px-8 text-[17px] font-semibold text-navy"
          onClick={onProveItWorks}
          type="button"
        >
          Prove it works
        </button>
        <p className="bg-lavender px-4 py-4 text-sm leading-6 text-navy">
          Post the PNG at original quality where possible. Avoid screenshots or heavy
          compression.
        </p>
      </div>
    </section>
  );
}
