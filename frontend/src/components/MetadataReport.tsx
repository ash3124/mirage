import type { CloakResult } from '../api/types';

interface MetadataReportProps {
  report: CloakResult['metadata_report'];
}

export default function MetadataReport({ report }: MetadataReportProps) {
  return (
    <section aria-labelledby="metadata-title" className="rounded bg-wash p-6 md:p-7">
      <h2 id="metadata-title" className="font-serif text-2xl">
        We removed hidden data
      </h2>
      {report.had_gps && (
        <p className="mt-4 bg-white px-4 py-3 text-sm text-exposed">
          Your photo contained GPS location. It has been removed.
        </p>
      )}
      {report.removed.length > 0 ? (
        <ul className="mt-4">
          {report.removed.map((item) => (
            <li
              className="border-t border-lavender py-3 text-sm first:border-0"
              key={item}
            >
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-muted">No removable metadata was found.</p>
      )}
    </section>
  );
}
