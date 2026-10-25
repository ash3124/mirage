import type { Strength } from '../api/types';

interface StrengthOption {
  id: Strength;
  label: string;
  description: string;
}

interface StrengthPickerProps {
  options: StrengthOption[];
  selected: Strength;
  onChange: (strength: Strength) => void;
}

export default function StrengthPicker({
  options,
  selected,
  onChange,
}: StrengthPickerProps) {
  return (
    <fieldset>
      <legend className="font-semibold">Protection strength</legend>
      {options.length === 0 ? (
        <p className="mt-3 bg-lavender px-4 py-3 text-sm leading-6 text-navy" role="status">
          No protection strengths are available right now. Reload the upload settings and try
          again.
        </p>
      ) : (
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {options.map((option) => (
            <label
              className={`cursor-pointer border bg-white p-4 ${
                selected === option.id
                  ? 'border-2 border-peri'
                  : 'border-lavender'
              }`}
              key={option.id}
            >
              <span className="flex items-start gap-3">
                <input
                  checked={selected === option.id}
                  name="strength"
                  onChange={() => onChange(option.id)}
                  type="radio"
                  value={option.id}
                />
                <span>
                  <span className="block font-semibold">{option.label}</span>
                  <span className="mt-1 block text-sm leading-6 text-muted">
                    {option.description}
                  </span>
                </span>
              </span>
            </label>
          ))}
        </div>
      )}
    </fieldset>
  );
}
