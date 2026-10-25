import { useState } from 'react';
import type { DemoSample } from '../api/types';
import { api } from '../api';

interface DemoSamplePickerProps {
  samples: DemoSample[];
  selectedId: string | null;
  onSelect: (sample: DemoSample) => void;
  label?: string;
  isLoading?: boolean;
}

export default function DemoSamplePicker({
  samples,
  selectedId,
  onSelect,
  label = 'Try a sample photo',
  isLoading = false,
}: DemoSamplePickerProps) {
  if (samples.length === 0) {
    return (
      <p className="bg-lavender px-4 py-3 text-sm leading-6 text-navy" role="status">
        {isLoading
          ? 'Loading demo samples…'
          : 'Demo samples are not available yet. Add the generated manifest and sample images under public/demo/.'}
      </p>
    );
  }

  return (
    <fieldset>
      <legend className="font-semibold">{label}</legend>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {samples.map((sample) => (
          <button
            aria-pressed={selectedId === sample.id}
            className={`text-left ${
              selectedId === sample.id ? 'outline outline-2 outline-peri' : ''
            }`}
            key={sample.id}
            onClick={() => onSelect(sample)}
            type="button"
          >
            <span className="block rounded bg-lavender p-2.5">
              <SampleThumbnail sample={sample} />
            </span>
            <span className="mt-2 block text-sm font-semibold">{sample.label}</span>
          </button>
        ))}
      </div>
    </fieldset>
  );
}

function SampleThumbnail({ sample }: { sample: DemoSample }) {
  const [unavailable, setUnavailable] = useState(false);
  if (unavailable) {
    return (
      <span className="flex aspect-[4/3] items-center justify-center bg-white px-2 text-center text-sm text-muted">
        Sample preview unavailable
      </span>
    );
  }
  return (
    <img
      alt={`Preview of ${sample.label}`}
      className="aspect-[4/3] w-full object-contain"
      onError={() => setUnavailable(true)}
      src={api.absoluteUrl(sample.thumb_url)}
    />
  );
}
