import type { CloakResult } from '../api/types';

interface MetricsPanelProps {
  metrics: CloakResult['metrics'];
}

function scoreColor(score: number): string {
  if (score >= 60) return 'bg-protected';
  if (score >= 30) return 'bg-caution';
  return 'bg-exposed';
}

export default function MetricsPanel({ metrics }: MetricsPanelProps) {
  const scores = [
    { label: 'Protection', score: metrics.protection_score },
    { label: 'Survives JPEG', score: metrics.robustness.jpeg_q75 },
    { label: 'Survives resize', score: metrics.robustness.resize_50 },
    { label: 'Survives social media', score: metrics.robustness.social_like },
  ];

  return (
    <section aria-labelledby="metrics-title" className="rounded bg-wash p-6 md:p-7">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="metrics-title" className="font-serif text-2xl">
          Protection metrics
        </h2>
        <span className="text-sm text-muted">
          Heuristic estimate, not a guarantee.
        </span>
      </div>
      <dl className="mt-5">
        {scores.map(({ label, score }) => (
          <div className="border-b border-lavender py-4 first:pt-0 last:border-0" key={label}>
            <div className="flex items-baseline justify-between gap-4">
              <dt className="font-medium">{label}</dt>
              <dd className="font-serif text-[32px] leading-none">{score}</dd>
            </div>
            <div
              aria-label={`${label}: ${score} out of 100`}
              className="mt-3 h-1.5 overflow-hidden rounded-full bg-track"
              role="img"
            >
              <div
                className={`h-full rounded-full ${scoreColor(score)}`}
                style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
              />
            </div>
          </div>
        ))}
      </dl>
      <p className="mt-4 text-sm text-muted">
        Visual quality: PSNR {metrics.visual_quality.psnr_db} dB · SSIM{' '}
        {metrics.visual_quality.ssim}
      </p>
    </section>
  );
}
