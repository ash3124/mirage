import { useEffect, useState } from 'react';
import {
  ReactCompareSlider,
  ReactCompareSliderHandle,
  ReactCompareSliderImage,
} from 'react-compare-slider';

interface CompareViewProps {
  originalUrl: string;
  cloakedUrl: string;
  heatmapUrl: string;
}

type ComparisonMode = 'slider' | 'difference';
type ZoomLevel = 1 | 4;

export default function CompareView({
  originalUrl,
  cloakedUrl,
  heatmapUrl,
}: CompareViewProps) {
  const [mode, setMode] = useState<ComparisonMode>('slider');
  const [zoom, setZoom] = useState<ZoomLevel>(1);
  const [originalUnavailable, setOriginalUnavailable] = useState(false);
  const [cloakedUnavailable, setCloakedUnavailable] = useState(false);
  const [heatmapUnavailable, setHeatmapUnavailable] = useState(false);

  useEffect(() => {
    setOriginalUnavailable(false);
    setCloakedUnavailable(false);
    setHeatmapUnavailable(false);
  }, [originalUrl, cloakedUrl, heatmapUrl]);

  function unavailablePreview(label: string) {
    return (
      <div
        aria-label={`${label} preview unavailable`}
        className="flex aspect-[3/2] w-full items-center justify-center bg-white px-5 text-center text-sm text-muted"
        role="img"
      >
        {label} preview is unavailable. Check the server image files and try again.
      </div>
    );
  }

  return (
    <section aria-labelledby="comparison-title">
      <h2 id="comparison-title" className="font-serif text-2xl">
        Original and protected
      </h2>
      <div className="mt-4 overflow-hidden rounded bg-lavender p-2.5">
        {mode === 'difference' ? (
          heatmapUnavailable ? (
            unavailablePreview('Difference heatmap')
          ) : (
            <img
              alt="Difference heatmap showing changes made by protection"
              className="aspect-[3/2] w-full object-contain"
              onError={() => setHeatmapUnavailable(true)}
              src={heatmapUrl}
            />
          )
        ) : (
          <div className="relative overflow-hidden">
            <ReactCompareSlider
              aria-label="Compare original photo with Mirage-protected photo"
              handle={
                <ReactCompareSliderHandle
                  buttonStyle={{
                    width: 40,
                    height: 40,
                    border: '2px solid #fff',
                    background: '#5269A8',
                    color: '#fff',
                  }}
                  linesStyle={{ width: 2, background: '#fff' }}
                />
              }
              itemOne={
                originalUnavailable ? (
                  unavailablePreview('Original photo')
                ) : (
                  <ReactCompareSliderImage
                    alt="Original photo"
                    onError={() => setOriginalUnavailable(true)}
                    src={originalUrl}
                    style={{
                      aspectRatio: '3 / 2',
                      objectFit: 'contain',
                      transform: `scale(${zoom})`,
                      transition: 'transform 200ms ease',
                    }}
                  />
                )
              }
              itemTwo={
                cloakedUnavailable ? (
                  unavailablePreview('Mirage-protected photo')
                ) : (
                  <ReactCompareSliderImage
                    alt="Mirage-protected photo"
                    onError={() => setCloakedUnavailable(true)}
                    src={cloakedUrl}
                    style={{
                      aspectRatio: '3 / 2',
                      objectFit: 'contain',
                      transform: `scale(${zoom})`,
                      transition: 'transform 200ms ease',
                    }}
                  />
                )
              }
              position={50}
            />
            <span className="pointer-events-none absolute left-3 top-3 bg-white px-2 py-1 text-xs font-semibold uppercase tracking-wide text-exposed">
              Original
            </span>
            <span className="pointer-events-none absolute right-3 top-3 bg-white px-2 py-1 text-xs font-semibold uppercase tracking-wide text-protected">
              Mirage
            </span>
          </div>
        )}
      </div>

      <div
        aria-label="Image comparison controls"
        className="mt-4 inline-flex min-h-11 flex-wrap border border-peri bg-white"
        role="group"
      >
        <button
          aria-pressed={zoom === 1 && mode === 'slider'}
          className={`min-h-11 px-4 text-sm font-semibold ${
            zoom === 1 && mode === 'slider' ? 'bg-peri text-white' : 'text-navy'
          }`}
          onClick={() => {
            setMode('slider');
            setZoom(1);
          }}
          type="button"
        >
          Zoom 1x
        </button>
        <button
          aria-pressed={zoom === 4 && mode === 'slider'}
          className={`min-h-11 px-4 text-sm font-semibold ${
            zoom === 4 && mode === 'slider' ? 'bg-peri text-white' : 'text-navy'
          }`}
          onClick={() => {
            setMode('slider');
            setZoom(4);
          }}
          type="button"
        >
          Zoom 4x
        </button>
        <button
          aria-pressed={mode === 'difference'}
          className={`min-h-11 px-4 text-sm font-semibold ${
            mode === 'difference' ? 'bg-peri text-white' : 'text-navy'
          }`}
          onClick={() => setMode('difference')}
          type="button"
        >
          Show difference
        </button>
      </div>
      <p className="mt-3 text-sm text-muted">
        {mode === 'difference'
          ? 'Amplified so you can see what changed. At normal size it is nearly invisible.'
          : 'Drag the divider to compare your original photo with the protected version.'}
      </p>
    </section>
  );
}
