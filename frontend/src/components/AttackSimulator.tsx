import { useState } from 'react';
import { ApiError } from '../api/client';
import { friendlyErrorMessage } from '../api/errorMessages';
import manifestExample from '../../shared/examples/manifest.sample.json';
import type { SimPreset, SimResult, Stage } from '../api/types';
import { api } from '../api';
import { useJobPolling } from '../hooks/useJobPolling';

interface AttackSimulatorProps {
  cloakJobId: string;
  presets: { id: SimPreset; label: string }[];
  selectedPreset: SimPreset | null;
  onPresetChange: (preset: SimPreset) => void;
  onKeepRecords: () => void;
}

const simulationStageMessages: Partial<Record<Stage, string>> = {
  queued: 'Waiting in line…',
  editing_original: 'Asking the AI to edit your original…',
  editing_cloaked: 'Now your cloaked photo…',
  scoring: 'Comparing the results…',
  done: 'Comparison complete.',
};

function fallbackMessage(error: unknown): string | null {
  if (error instanceof ApiError && error.code === 'SIM_UNAVAILABLE') {
    return 'Live simulator is off on this server. Here is a pre-recorded example.';
  }
  return null;
}

function userMessage(error: unknown): string {
  return friendlyErrorMessage(error);
}

function ScoreBar({ score }: { score: number }) {
  const color =
    score >= 60 ? 'bg-protected' : score >= 30 ? 'bg-caution' : 'bg-exposed';
  return (
    <div
      aria-label={`Edit disruption: ${score} out of 100`}
      className="mt-3 h-1.5 overflow-hidden rounded-full bg-track"
      role="img"
    >
      <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
    </div>
  );
}

function SimulationImages({ result }: { result: SimResult }) {
  return (
    <>
      <div className="mt-6 grid gap-5 sm:grid-cols-2">
        <figure>
          <div className="rounded bg-lavender p-2.5">
            <SimulationImage
              alt="AI edit of your original photo"
              src={api.absoluteUrl(result.edit_on_original_url)}
              unavailableLabel="Original AI edit"
            />
          </div>
          <figcaption className="mt-2 text-xs font-semibold uppercase tracking-wide text-exposed">
            AI edit of your ORIGINAL
          </figcaption>
        </figure>
        <figure>
          <div className="rounded bg-lavender p-2.5">
            <SimulationImage
              alt="AI edit of your Mirage-protected photo"
              src={api.absoluteUrl(result.edit_on_cloaked_url)}
              unavailableLabel="Protected AI edit"
            />
          </div>
          <figcaption className="mt-2 text-xs font-semibold uppercase tracking-wide text-protected">
            AI edit of your CLOAKED photo
          </figcaption>
        </figure>
      </div>
      <p className="mt-4 text-sm text-muted">
        Same AI model, same prompt, same random seed.
      </p>
      <div className="mt-6 border-t border-lavender pt-5">
        <div className="flex items-baseline justify-between gap-4">
          <h3 className="font-semibold">Edit disruption</h3>
          <span className="font-serif text-[44px] leading-none">
            {result.disruption_score}
          </span>
        </div>
        <ScoreBar score={result.disruption_score} />
        <p className="mt-4 text-sm text-muted">
          The score estimates how differently the same edit affected the original and protected
          photos.
        </p>
      </div>
    </>
  );
}

function SimulationImage({
  alt,
  src,
  unavailableLabel,
}: {
  alt: string;
  src: string;
  unavailableLabel: string;
}) {
  const [unavailable, setUnavailable] = useState(false);
  if (unavailable) {
    return (
      <div
        aria-label={`${unavailableLabel} preview unavailable`}
        className="flex aspect-[3/2] items-center justify-center bg-white px-4 text-center text-sm text-muted"
        role="img"
      >
        {unavailableLabel} image is not available on this server.
      </div>
    );
  }
  return (
    <img
      alt={alt}
      className="aspect-[3/2] w-full object-contain"
      onError={() => setUnavailable(true)}
      src={src}
    />
  );
}

function sampleSimResult(preset: SimPreset): SimResult | undefined {
  const value = manifestExample.samples[0]?.sims[preset];
  if (!value || !('disruption_score' in value) || !('seed' in value)) return undefined;
  return {
    preset,
    edit_on_original_url: value.edit_on_original_url,
    edit_on_cloaked_url: value.edit_on_cloaked_url,
    disruption_score: value.disruption_score,
    seed: value.seed,
  };
}

export default function AttackSimulator({
  cloakJobId,
  presets,
  selectedPreset,
  onPresetChange,
  onKeepRecords,
}: AttackSimulatorProps) {
  const [simJobId, setSimJobId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [startErrorCode, setStartErrorCode] = useState<string | null>(null);
  const [simUnavailable, setSimUnavailable] = useState(false);
  const [showDemoExample, setShowDemoExample] = useState(false);
  const [simResult, setSimResult] = useState<SimResult | null>(null);
  const { job, isPolling, error: pollError, networkRetry } =
    useJobPolling<SimResult>(simJobId);

  const completedResult = job?.status === 'done' ? job.result : null;
  const jobErrorCode = job?.status === 'error' ? job.error?.code : undefined;
  const blocked =
    jobErrorCode === 'SIM_BLOCKED' ||
    startErrorCode === 'SIM_BLOCKED';
  const unavailableInJob = jobErrorCode === 'SIM_UNAVAILABLE';
  const unavailable = simUnavailable || unavailableInJob;
  const resultToShow = showDemoExample ? simResult : completedResult ?? simResult;

  async function runSimulation() {
    if (!selectedPreset || starting || isPolling) return;
    setStarting(true);
    setStartError(null);
    setStartErrorCode(null);
    setSimUnavailable(false);
    setShowDemoExample(false);
    setSimResult(null);
    setSimJobId(null);
    try {
      const response = await api.startSim(cloakJobId, selectedPreset);
      setSimJobId(response.job_id);
    } catch (error) {
      setStartErrorCode(error instanceof ApiError ? error.code : null);
      const unavailable = fallbackMessage(error);
      if (unavailable) {
        setSimUnavailable(true);
        setStartError(unavailable);
      } else {
        setStartError(userMessage(error));
      }
    } finally {
      setStarting(false);
    }
  }

  function loadPreRecordedExample() {
    if (!selectedPreset) return;
    const sampleResult = sampleSimResult(selectedPreset);
    if (!sampleResult) {
      setStartError('No pre-recorded example is available for this preset.');
      return;
    }
    setSimResult(sampleResult);
    setShowDemoExample(true);
  }

  const isRunning = starting || isPolling;

  return (
    <section aria-labelledby="simulator-title" className="mt-8 space-y-7">
      <header>
        <p className="eyebrow">Step 3 · Prove it</p>
        <h2 id="simulator-title" className="mt-2 font-serif text-3xl">
          Same AI. Same prompt.
        </h2>
        <p className="mt-3 leading-7 text-muted">
          Compare how one harmless preset edit affects your original and protected photos.
        </p>
      </header>

      <div className="rounded bg-wash p-6 md:p-7">
        <fieldset>
          <legend className="font-semibold">Choose an edit preset</legend>
          {presets.length === 0 ? (
            <p className="mt-3 bg-lavender px-4 py-3 text-sm leading-6 text-navy" role="status">
              No comparison presets are available on this server.
            </p>
          ) : (
            <div className="mt-4 flex flex-wrap gap-2">
              {presets.map((preset) => (
                <button
                  aria-pressed={selectedPreset === preset.id}
                  className={`min-h-11 border-[1.5px] border-peri px-4 text-sm font-medium ${
                    selectedPreset === preset.id
                      ? 'bg-peri text-white'
                      : 'bg-transparent text-navy'
                  }`}
                  disabled={isRunning}
                  key={preset.id}
                  onClick={() => onPresetChange(preset.id)}
                  type="button"
                >
                  {preset.label}
                </button>
              ))}
            </div>
          )}
        </fieldset>

        <button
          className="primary-button mt-6 w-full disabled:cursor-not-allowed disabled:opacity-50"
          disabled={!selectedPreset || isRunning}
          onClick={() => void runSimulation()}
          type="button"
        >
          {isRunning ? 'Running the comparison…' : 'Run the same AI edit on both'}
        </button>

        {isRunning && (
          <div className="mt-6" aria-live="polite" aria-atomic="true">
            <p className="font-semibold">
              {simulationStageMessages[job?.stage ?? 'queued'] ?? 'Preparing the comparison…'}
            </p>
            {networkRetry > 0 && (
              <p className="mt-2 text-sm text-muted" role="status">
                Connection interrupted. Retrying ({networkRetry}/2)…
              </p>
            )}
            <progress
              aria-label="Simulator progress"
              className="mt-4 block h-1.5 w-full accent-peri"
              max={100}
              value={job?.progress ?? 0}
            />
            <p className="mt-2 text-right text-sm text-muted">
              {job?.progress ?? 0}% complete
            </p>
          </div>
        )}

        {blocked && (
          <div className="mt-5 bg-lavender px-4 py-4 text-sm text-navy" role="alert">
            The AI&apos;s safety filter blocked this edit. Try another preset.
          </div>
        )}
        {unavailable && (
          <div className="mt-5 bg-lavender px-4 py-4 text-sm text-navy" role="status">
            <p>
              {startError ??
                'Live simulator is off on this server. Here is a pre-recorded example.'}
            </p>
            <button
              className="text-link mt-3"
              disabled={!selectedPreset}
              onClick={loadPreRecordedExample}
              type="button"
            >
              Show a pre-recorded example
            </button>
          </div>
        )}
        {!unavailable && startError && !blocked && (
          <div className="mt-5 bg-lavender px-4 py-4 text-sm text-navy" role="alert">
            <p>{startError}</p>
            <button className="text-link mt-3" onClick={() => void runSimulation()} type="button">
              Try again
            </button>
          </div>
        )}
        {job?.status === 'error' && !blocked && !unavailable && !pollError && (
          <div className="mt-5 bg-lavender px-4 py-4 text-sm text-navy" role="alert">
            <p>
              {job.error
                ? friendlyErrorMessage(job.error)
                : 'The simulator could not complete the edit.'}
            </p>
            <button className="text-link mt-3" onClick={() => setSimJobId(null)} type="button">
              Try another preset
            </button>
          </div>
        )}
        {pollError && (
          <div className="mt-5 bg-lavender px-4 py-4 text-sm text-navy" role="alert">
            <p>{pollError}</p>
            <button className="text-link mt-3" onClick={() => setSimJobId(null)} type="button">
              Try again
            </button>
          </div>
        )}

        {resultToShow && (
          <div className="mt-7 border-t border-lavender pt-6">
            {showDemoExample && (
              <p className="mb-5 bg-lavender px-4 py-3 text-sm text-navy">
                Live simulator is off on this server. This is a pre-recorded example, not a live
                run.
              </p>
            )}
            <SimulationImages result={resultToShow} />
          </div>
        )}
      </div>
      <button
        className="flex min-h-[54px] w-full items-center justify-center border-[1.5px] border-peri bg-transparent px-8 text-[17px] font-semibold text-navy"
        onClick={onKeepRecords}
        type="button"
      >
        Keep my records
      </button>
    </section>
  );
}
