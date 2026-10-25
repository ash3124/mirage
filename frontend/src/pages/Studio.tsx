import { useEffect, useRef, useState, type DragEvent, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api, getAdapter } from '../api';
import { friendlyErrorMessage } from '../api/errorMessages';
import { links } from '../data/links';
import type {
  AppConfig,
  CloakForm,
  DemoSample,
  SimPreset,
  Stage,
  StartJobResponse,
  Strength,
} from '../api/types';
import AttackSimulator from '../components/AttackSimulator';
import CertificateButton from '../components/CertificateButton';
import CloakResultView from '../components/CloakResultView';
import DemoSamplePicker from '../components/DemoSamplePicker';
import StrengthPicker from '../components/StrengthPicker';
import { useJobPolling } from '../hooks/useJobPolling';

const acceptedTypes = ['image/jpeg', 'image/png', 'image/webp'];
const acceptedExtensions = ['.jpg', '.jpeg', '.png', '.webp'];
const ownerTagPattern = /^[A-Z0-9]{1,4}$/;
const cloakStageMessages: Partial<Record<Stage, string>> = {
  queued: 'Waiting in line…',
  detecting_face: 'Finding faces…',
  optimizing: 'Building your invisible shield…',
  robustness_check: 'Stress-testing against compression…',
  finalizing: 'Finishing up…',
  done: 'Your photo is protected.',
};

function isAcceptedImage(file: File): boolean {
  const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
  return acceptedTypes.includes(file.type) || acceptedExtensions.includes(extension);
}

function uploadError(file: File, maxUploadMb: number): string | null {
  const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
  if (file.type === 'image/heic' || file.type === 'image/heif' || ['.heic', '.heif'].includes(extension)) {
    return 'Please convert to JPG/PNG (iPhone: Settings > Camera > Formats > Most Compatible).';
  }
  if (!isAcceptedImage(file)) {
    return 'Choose a JPG, PNG, or WebP photo.';
  }
  if (file.size > maxUploadMb * 1024 * 1024) {
    return `Please choose an image under ${maxUploadMb} MB.`;
  }
  return null;
}

function errorMessage(error: unknown): string {
  return friendlyErrorMessage(error);
}

export default function Studio() {
  const adapter = getAdapter();
  const recordingMode = new URLSearchParams(window.location.search).get('record') === '1';
  const [flowStep, setFlowStep] = useState<'upload' | 'protect' | 'result' | 'prove' | 'records'>(
    'upload',
  );
  const previousFlowStep = useRef(flowStep);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [strength, setStrength] = useState<Strength>('standard');
  const [preset, setPreset] = useState<SimPreset | null>(null);
  const [demoSamples, setDemoSamples] = useState<DemoSample[]>([]);
  const [selectedDemoSampleId, setSelectedDemoSampleId] = useState<string | null>(null);
  const [demoSamplesError, setDemoSamplesError] = useState<string | null>(null);
  const [demoSamplesLoading, setDemoSamplesLoading] = useState(adapter === 'demo');
  const [consent, setConsent] = useState(false);
  const [faceFocus, setFaceFocus] = useState(true);
  const [robustMode, setRobustMode] = useState(true);
  const [embedWatermark, setEmbedWatermark] = useState(false);
  const [ownerTag, setOwnerTag] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [queueDepth, setQueueDepth] = useState<number | null>(null);
  const [queueError, setQueueError] = useState<string | null>(null);
  const { job, isPolling, error: pollingError, networkRetry } = useJobPolling(jobId);

  useEffect(() => {
    if (job?.status === 'done') setFlowStep('result');
  }, [job?.status]);

  async function loadConfig() {
    setConfigError(null);
    try {
      const response = await api.config();
      setConfig(response);
      setStrength(
        response.strengths.some((option) => option.id === 'standard')
          ? 'standard'
          : response.strengths[0]?.id ?? 'standard',
      );
      setPreset(response.sim_presets[0]?.id ?? null);
    } catch (error) {
      setConfigError(errorMessage(error));
    }
  }

  useEffect(() => {
    void loadConfig();
  }, [adapter]);

  useEffect(() => {
    if (!recordingMode || flowStep === previousFlowStep.current) return;
    previousFlowStep.current = flowStep;
    if (flowStep === 'upload') return;
    const frame = window.requestAnimationFrame(() => {
      document.querySelector('.studio-flow-step')?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [flowStep, recordingMode]);

  useEffect(() => {
    if (!recordingMode) return;
    function resetOnShortcut(event: KeyboardEvent) {
      const target = event.target;
      if (
        event.key.toLowerCase() !== 'r' ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        (target instanceof HTMLElement &&
          (target.isContentEditable ||
            ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)))
      ) {
        return;
      }
      setFlowStep('upload');
      setFile(null);
      setFileError(null);
      setSelectedDemoSampleId(null);
      setConsent(false);
      setFaceFocus(true);
      setRobustMode(true);
      setEmbedWatermark(false);
      setOwnerTag('');
      setSubmitting(false);
      setSubmitError(null);
      setJobId(null);
      setQueueDepth(null);
      setQueueError(null);
      setIsDragging(false);
      setStrength(
        config?.strengths.some((option) => option.id === 'standard')
          ? 'standard'
          : config?.strengths[0]?.id ?? 'standard',
      );
      setPreset(config?.sim_presets[0]?.id ?? null);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    window.addEventListener('keydown', resetOnShortcut);
    return () => window.removeEventListener('keydown', resetOnShortcut);
  }, [config, recordingMode]);

  useEffect(() => {
    setDemoSamples([]);
    setSelectedDemoSampleId(null);
    setDemoSamplesError(null);
    if (adapter !== 'demo') {
      setDemoSamplesLoading(false);
      return;
    }
    let active = true;
    setDemoSamplesLoading(true);
    void api.demoSamples().then(
      (samples) => {
        if (!active) return;
        setDemoSamples(samples);
        setDemoSamplesError(null);
        setDemoSamplesLoading(false);
      },
      (error: unknown) => {
        if (active) {
          setDemoSamplesError(friendlyErrorMessage(error));
          setDemoSamplesLoading(false);
        }
      },
    );
    return () => {
      active = false;
    };
  }, [adapter]);

  useEffect(() => {
    if (!jobId) {
      setQueueDepth(null);
      setQueueError(null);
      return;
    }

    let active = true;
    setQueueDepth(null);
    setQueueError(null);
    void api.health().then(
      (health) => {
        if (active) setQueueDepth(health.queue_depth);
      },
      (error: unknown) => {
        if (active) setQueueError(errorMessage(error));
      },
    );
    return () => {
      active = false;
    };
  }, [jobId]);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const objectUrl = URL.createObjectURL(file);
    setPreviewUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  function chooseFile(candidate?: File) {
    if (!candidate) return;
    setSubmitError(null);
    setJobId(null);
    setSelectedDemoSampleId(null);
    if (!config) {
      setFileError('Upload settings are still loading. Please try again shortly.');
      return;
    }
    const validationMessage = uploadError(candidate, config.limits.max_upload_mb);
    if (validationMessage) {
      setFile(null);
      setFileError(validationMessage);
      return;
    }
    setFile(candidate);
    setFileError(null);
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(false);
    chooseFile(event.dataTransfer.files[0]);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const hasInput = adapter === 'demo'
      ? selectedDemoSampleId !== null || file !== null
      : file !== null;
    if (!config || !hasInput || !consent || submitting) return;
    if (embedWatermark && !ownerTagPattern.test(ownerTag)) {
      setSubmitError('Enter an ownership tag with 1 to 4 letters A-Z or numbers 0-9.');
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    setJobId(null);
    setQueueDepth(null);
    setFlowStep('protect');
    const options = {
      strength,
      face_focus: faceFocus,
      robust_mode: robustMode,
      embed_watermark: embedWatermark,
      ...(embedWatermark ? { owner_tag: ownerTag } : {}),
    };
    try {
      let response: StartJobResponse;
      if (adapter === 'demo' && selectedDemoSampleId) {
        response = await api.startSampleCloak(selectedDemoSampleId, options);
      } else if (file) {
        response = await api.startCloak({ ...options, file } satisfies CloakForm);
      } else {
        throw new Error('Choose a photo before continuing.');
      }
      setJobId(response.job_id);
    } catch (error) {
      setSubmitError(errorMessage(error));
      setFlowStep('upload');
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit =
    config !== null &&
    config.strengths.length > 0 &&
    (adapter === 'demo'
      ? selectedDemoSampleId !== null || file !== null
      : file !== null) &&
    consent &&
    !submitting &&
    (!embedWatermark || ownerTagPattern.test(ownerTag));
  const currentStep =
    flowStep === 'upload'
      ? 0
      : flowStep === 'protect' || flowStep === 'result'
        ? 1
        : flowStep === 'prove'
          ? 2
          : 3;

  function backToUpload() {
    setJobId(null);
    setFlowStep('upload');
  }

  return (
    <main className="page-width max-w-[824px] py-12 md:py-16">
      <p className="eyebrow">Studio</p>
      <h1 className="mt-3 font-serif text-4xl font-medium md:text-5xl">Protect a photo</h1>
      <ol className="mt-8 grid grid-cols-4 border-b border-lavender pb-3 text-xs text-muted sm:text-sm">
        {['1 Upload', '2 Protect', '3 Prove it', '4 Records'].map((step, index) => (
          <li
            aria-current={index === currentStep ? 'step' : undefined}
            className={
              index < currentStep
                ? 'font-medium text-navy'
                : index === currentStep
                ? 'border-b-2 border-peri pb-3 font-semibold text-navy'
                : 'text-muted'
            }
            key={step}
          >
            {step}
          </li>
        ))}
      </ol>

      {flowStep === 'upload' && (
      <form className="studio-flow-step mt-8 rounded bg-wash p-6 md:p-8" onSubmit={handleSubmit}>
        <h2 className="font-serif text-2xl">Choose an image</h2>
        <p className="mt-2 text-muted">
          JPG, PNG, or WebP · Up to {config?.limits.max_upload_mb ?? 10} MB
        </p>

        {adapter === 'demo' && (
          <div className="mt-6">
            {demoSamplesError ? (
              <p className="bg-lavender px-4 py-3 text-sm text-navy" role="status">
                Demo samples could not be loaded: {demoSamplesError}
              </p>
            ) : (
              <DemoSamplePicker
                onSelect={(sample) => {
                  setSelectedDemoSampleId(sample.id);
                  setFile(null);
                  setFileError(null);
                  setSubmitError(null);
                  setJobId(null);
                }}
                samples={demoSamples}
                selectedId={selectedDemoSampleId}
                isLoading={demoSamplesLoading}
              />
            )}
            {selectedDemoSampleId && (
              <p className="mt-3 text-sm text-muted">
                This sample plays pre-computed results. To protect your own photo, use the{' '}
                {links.colab ? (
                  <a className="text-link" href={links.colab} rel="noreferrer" target="_blank">
                    Colab notebook
                  </a>
                ) : (
                  'Colab notebook'
                )}.
              </p>
            )}
            {file && (
              <p className="mt-3 text-sm text-muted">
                Your upload stays in this browser and is not processed in Demo Mode. The result
                will use a pre-computed sample. To protect your own photo, use the{' '}
                {links.colab ? (
                  <a className="text-link" href={links.colab} rel="noreferrer" target="_blank">
                    Colab notebook
                  </a>
                ) : (
                  'Colab notebook'
                )}.
              </p>
            )}
            {!selectedDemoSampleId && !file && !demoSamplesLoading && !demoSamplesError && (
              <p className="mt-3 text-sm text-muted">
                Select a sample or choose a photo to play a pre-computed result.
              </p>
            )}
          </div>
        )}

        <label
          className={`mt-6 flex min-h-40 cursor-pointer flex-col items-center justify-center border border-dashed px-5 py-6 text-center ${
            isDragging ? 'border-peri bg-white' : 'border-lavender bg-misty'
          }`}
          onDragEnter={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            setIsDragging(false);
          }}
          onDragOver={(event) => event.preventDefault()}
          onDrop={handleDrop}
        >
          {previewUrl && file ? (
            <img
              alt={`Preview of ${file.name}`}
              className="mb-4 max-h-64 max-w-full object-contain"
              src={previewUrl}
            />
          ) : (
            <span className="font-semibold">Drop your photo here or choose a photo</span>
          )}
          {file && <span className="font-semibold">{file.name}</span>}
          <span className="mt-2 text-sm text-muted">
            JPG, PNG, or WebP. HEIC is not supported.
          </span>
          <input
            accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
            className="sr-only"
            onChange={(event) => chooseFile(event.currentTarget.files?.[0])}
            type="file"
          />
        </label>
        {fileError && (
          <p className="mt-3 bg-lavender px-4 py-3 text-sm text-navy" role="alert">
            {fileError}
          </p>
        )}

        {configError ? (
          <div className="mt-6 bg-lavender px-4 py-4 text-sm text-navy" role="alert">
            <p>Upload settings could not be loaded: {configError}</p>
            <button className="text-link mt-2" onClick={() => void loadConfig()} type="button">
              Try again
            </button>
          </div>
        ) : !config ? (
          <p aria-live="polite" className="mt-6 text-sm text-muted" role="status">
            Loading upload settings…
          </p>
        ) : (
          <>
            <div className="mt-7">
              <StrengthPicker
                onChange={setStrength}
                options={config.strengths}
                selected={strength}
              />
            </div>

            <fieldset className="mt-7">
              <legend className="font-semibold">Choose a proof edit</legend>
              <p className="mt-1 text-sm text-muted">
                You can use this preset in the proof step after protecting your photo.
              </p>
              {config.sim_presets.length === 0 ? (
                <p className="mt-3 bg-lavender px-4 py-3 text-sm leading-6 text-navy" role="status">
                  No proof edits are configured. You can still protect your photo.
                </p>
              ) : (
                <div className="mt-3 flex flex-wrap gap-2">
                  {config.sim_presets.map((option) => (
                    <button
                      aria-pressed={preset === option.id}
                      className={`min-h-11 border-[1.5px] border-peri px-4 text-sm font-medium ${
                        preset === option.id
                          ? 'bg-peri text-white'
                          : 'bg-transparent text-navy'
                      }`}
                      key={option.id}
                      onClick={() => setPreset(option.id)}
                      type="button"
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              )}
            </fieldset>

            <fieldset className="mt-7 space-y-4">
              <legend className="sr-only">Protection options</legend>
              <label className="flex items-start gap-3">
                <input
                  checked={faceFocus}
                  className="mt-1"
                  onChange={(event) => setFaceFocus(event.currentTarget.checked)}
                  type="checkbox"
                />
                <span>
                  <span className="font-semibold">Focus on faces</span>
                  <span className="mt-1 block text-sm text-muted">
                    Apply stronger protection around detected faces.
                  </span>
                </span>
              </label>
              <label className="flex items-start gap-3">
                <input
                  checked={robustMode}
                  className="mt-1"
                  onChange={(event) => setRobustMode(event.currentTarget.checked)}
                  type="checkbox"
                />
                <span>
                  <span className="font-semibold">Stress-test mode</span>
                  <span className="mt-1 block text-sm text-muted">
                    Optimize for resilience to common resizing and compression.
                  </span>
                </span>
              </label>
              <label className="flex items-start gap-3">
                <input
                  checked={embedWatermark}
                  className="mt-1"
                  disabled={!config.features.watermark}
                  onChange={(event) => setEmbedWatermark(event.currentTarget.checked)}
                  type="checkbox"
                />
                <span>
                  <span className="font-semibold">Add invisible ownership tag</span>
                  {!config.features.watermark && (
                    <span className="mt-1 block text-sm text-muted">
                      Not available on this server.
                    </span>
                  )}
                </span>
              </label>
              {embedWatermark && config.features.watermark && (
                <label className="block max-w-xs">
                  <span className="mb-2 block text-sm font-semibold">Ownership tag</span>
                  <input
                    autoCapitalize="characters"
                    className="h-12 w-full rounded border border-peri bg-white px-3 text-navy"
                    maxLength={4}
                    onChange={(event) => setOwnerTag(event.currentTarget.value.toUpperCase())}
                    pattern="[A-Z0-9]{1,4}"
                    placeholder="AB12"
                    required
                    value={ownerTag}
                  />
                  <span className="mt-1 block text-sm text-muted">1–4 characters: A-Z, 0-9.</span>
                </label>
              )}
            </fieldset>

            <label className="mt-7 flex items-start gap-3 border-t border-lavender pt-5">
              <input
                checked={consent}
                className="mt-1"
                onChange={(event) => setConsent(event.currentTarget.checked)}
                type="checkbox"
              />
              <span className="font-semibold">
                This is my photo or I have permission to protect it.
              </span>
            </label>

            <button
              className="primary-button mt-6 w-full disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!canSubmit}
              type="submit"
            >
              {submitting ? 'Starting…' : 'Cloak my photo'}
            </button>
            <p className="mt-3 text-sm text-muted">
              Processed in memory. Auto-deleted in 15 minutes. No account.
            </p>
          </>
        )}

        {submitError && (
          <p className="mt-4 bg-lavender px-4 py-3 text-sm text-navy" role="alert">
            {submitError}
          </p>
        )}
      </form>
      )}

      {flowStep === 'protect' && jobId && (
        <section
          aria-labelledby="cloak-progress-title"
          className="studio-flow-step mt-8 rounded bg-wash p-6 md:p-8"
        >
          <h2 id="cloak-progress-title" className="font-serif text-2xl">
            Protecting your photo
          </h2>
          <p className="mt-2 text-muted">
            Keep this page open while Mirage creates your protected copy.
          </p>

          {queueDepth !== null && queueDepth > 0 && (
            <p className="mt-5 bg-lavender px-4 py-3 text-sm text-navy">
              There {queueDepth === 1 ? 'is' : 'are'} {queueDepth} job
              {queueDepth === 1 ? '' : 's'} ahead in the queue.
            </p>
          )}
          {queueError && (
            <p className="mt-5 bg-lavender px-4 py-3 text-sm text-navy" role="status">
              Queue information is temporarily unavailable: {queueError}
            </p>
          )}

          {job?.status === 'error' ? (
            <div className="mt-6 bg-lavender px-4 py-4 text-sm text-navy" role="alert">
              <p>
                {job.error
                  ? friendlyErrorMessage(job.error)
                  : 'Your photo could not be protected. Please try again.'}
              </p>
              <button className="text-link mt-3" onClick={backToUpload} type="button">
                Try again
              </button>
            </div>
          ) : pollingError ? (
            <div className="mt-6 bg-lavender px-4 py-4 text-sm text-navy" role="alert">
              <p>{pollingError}</p>
              <button className="text-link mt-3" onClick={backToUpload} type="button">
                Try again
              </button>
            </div>
          ) : (
            <>
              <div className="mt-8" aria-live="polite" aria-atomic="true">
                <p className="font-semibold">
                  {cloakStageMessages[job?.stage ?? 'queued'] ?? 'Preparing your photo…'}
                </p>
                {networkRetry > 0 && (
                  <p className="mt-2 text-sm text-muted" role="status">
                    Connection interrupted. Retrying ({networkRetry}/2)…
                  </p>
                )}
              </div>
              <progress
                aria-label="Photo protection progress"
                className="mt-4 block h-1.5 w-full accent-peri"
                max={100}
                value={job?.progress ?? 0}
              />
              <p className="mt-2 text-right text-sm text-muted">
                {job?.progress ?? 0}% complete
              </p>
              {job?.status === 'done' ? (
                <p className="mt-5 bg-lavender px-4 py-3 text-sm text-navy">
                  Protection is complete. Job ID: <code>{jobId}</code>
                </p>
              ) : (
                <button
                  className="text-link mt-5"
                  onClick={backToUpload}
                  type="button"
                >
                  Cancel
                </button>
              )}
              {!isPolling && job?.status === 'done' && (
                <button
                  className="primary-button mt-6 w-full"
                  onClick={backToUpload}
                  type="button"
                >
                  Back to upload
                </button>
              )}
            </>
          )}
        </section>
      )}
      {flowStep === 'result' && jobId && job?.result && (
        <section className="studio-flow-step">
          <CloakResultView
            onProveItWorks={() => setFlowStep('prove')}
            result={job.result}
          />
        </section>
      )}
      {flowStep === 'prove' && jobId && job?.result && config && (
        <section className="studio-flow-step">
          <AttackSimulator
            cloakJobId={jobId}
            onKeepRecords={() => setFlowStep('records')}
            onPresetChange={setPreset}
            presets={config.sim_presets}
            selectedPreset={preset}
          />
        </section>
      )}
      {flowStep === 'records' && jobId && job?.result && (
        <section className="studio-flow-step">
          <CertificateButton jobId={jobId} result={job.result} />
        </section>
      )}
      <p className="mt-6 text-sm text-muted">
        Need help with misuse? <Link className="text-link" to="/safety-kit">Open the Safety Kit</Link>
      </p>
    </main>
  );
}
