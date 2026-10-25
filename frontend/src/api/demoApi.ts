import { ApiError } from './client';
import configExample from '../../shared/examples/config.ok.json';
import type {
  Api,
  AppConfig,
  CloakForm,
  CloakOptions,
  CloakResult,
  DemoSample,
  HealthResponse,
  Job,
  JobStatus,
  SimPreset,
  SimResult,
  StartJobResponse,
  Stage,
} from './types';

interface DemoManifest {
  version: string;
  sample_certificate_url: string;
  samples: DemoSample[];
}

type DemoJob =
  | { kind: 'cloak'; startedAt: number; sample: DemoSample }
  | { kind: 'sim'; startedAt: number; result: SimResult };

const jobs = new Map<string, DemoJob>();
const completedCloakJobs = new Set<string>();
let manifestPromise: Promise<DemoManifest> | undefined;

function makeJobId(): string {
  return crypto.randomUUID();
}

function loadManifest(): Promise<DemoManifest> {
  manifestPromise ??= fetch('/demo/manifest.json').then(async (response) => {
    if (!response.ok) {
      throw new ApiError(
        'INTERNAL',
        'Demo assets are not available. Add the generated manifest and assets under public/demo/.',
        response.status,
      );
    }
    if (!response.headers.get('content-type')?.includes('application/json')) {
      throw new ApiError(
        'INTERNAL',
        'The demo manifest is missing or is not being served as JSON. Add the generated manifest under public/demo/.',
        response.status,
      );
    }
    const manifest: unknown = await response.json();
    if (
      typeof manifest !== 'object' ||
      manifest === null ||
      !('samples' in manifest) ||
      !Array.isArray(manifest.samples) ||
      manifest.samples.length === 0
    ) {
      throw new ApiError('INTERNAL', 'The demo manifest has no sample results.');
    }
    return manifest as DemoManifest;
  });
  return manifestPromise;
}

function cloakJob(jobId: string, elapsed: number, sample: DemoSample): Job<CloakResult> {
  const duration = 6000;
  if (elapsed >= duration) {
    completedCloakJobs.add(jobId);
    return {
      job_id: jobId,
      type: 'cloak',
      status: 'done',
      progress: 100,
      stage: 'done',
      result: sample.cloak,
      error: null,
    };
  }

  let status: JobStatus = 'running';
  let stage: Stage;
  let progress = Math.floor((elapsed / duration) * 95);
  if (elapsed < 500) {
    status = 'queued';
    stage = 'queued';
    progress = 0;
  } else if (elapsed < 1500) {
    stage = 'detecting_face';
  } else if (elapsed < 3900) {
    stage = 'optimizing';
  } else if (elapsed < 5000) {
    stage = 'robustness_check';
  } else {
    stage = 'finalizing';
  }

  return {
    job_id: jobId,
    type: 'cloak',
    status,
    progress,
    stage,
    result: null,
    error: null,
  };
}

function simJob(jobId: string, elapsed: number, result: SimResult): Job<SimResult> {
  if (elapsed >= 8000) {
    return {
      job_id: jobId,
      type: 'attack_sim',
      status: 'done',
      progress: 100,
      stage: 'done',
      result,
      error: null,
    };
  }
  const stage: Stage =
    elapsed < 2500 ? 'editing_original' : elapsed < 6000 ? 'editing_cloaked' : 'scoring';
  return {
    job_id: jobId,
    type: 'attack_sim',
    status: 'running',
    progress: Math.floor((elapsed / 8000) * 95),
    stage,
    result: null,
    error: null,
  };
}

export const demoApi: Api = {
  async health(): Promise<HealthResponse> {
    return {
      status: 'ok',
      version: '1.0.0',
      mode: 'gpu',
      queue_depth: 0,
      simulator_enabled: true,
    };
  },

  async config(): Promise<AppConfig> {
    return configExample as AppConfig;
  },

  async startCloak(_form: CloakForm): Promise<StartJobResponse> {
    const manifest = await loadManifest();
    return createSampleJob(manifest.samples[0]);
  },

  async startSampleCloak(sampleId: string, _options: CloakOptions): Promise<StartJobResponse> {
    const manifest = await loadManifest();
    const sample = manifest.samples.find((item) => item.id === sampleId);
    if (!sample) {
      throw new ApiError('BAD_PARAMS', 'The selected demo sample is not available.', 422);
    }
    return createSampleJob(sample);
  },

  async demoSamples(): Promise<DemoSample[]> {
    return (await loadManifest()).samples;
  },

  async getJob<T>(id: string): Promise<Job<T>> {
    const job = jobs.get(id);
    if (!job) {
      throw new ApiError('JOB_NOT_FOUND', 'That job or file could not be found.', 404);
    }
    const response =
      job.kind === 'cloak'
        ? cloakJob(id, Date.now() - job.startedAt, job.sample)
        : simJob(id, Date.now() - job.startedAt, job.result);
    return response as Job<T>;
  },

  async startSim(job_id: string, preset: SimPreset): Promise<StartJobResponse> {
    const previousJob = jobs.get(job_id);
    if (!previousJob) {
      throw new ApiError('JOB_NOT_FOUND', 'That job or file could not be found.', 404);
    }
    if (previousJob.kind !== 'cloak') {
      throw new ApiError('BAD_PARAMS', 'The job is not a cloak job.', 422);
    }
    if (!completedCloakJobs.has(job_id)) {
      throw new ApiError('JOB_NOT_READY', 'That job is not finished yet.', 409);
    }
    const result = previousJob.sample.sims[preset];
    if (!result) {
      throw new ApiError('BAD_PARAMS', 'The requested preset is not in the demo manifest.', 422);
    }
    const simJobId = makeJobId();
    jobs.set(simJobId, { kind: 'sim', startedAt: Date.now(), result });
    return { job_id: simJobId, status: 'queued' };
  },

  async certificate(job_id: string): Promise<Blob> {
    const job = jobs.get(job_id);
    if (!job) {
      throw new ApiError('JOB_NOT_FOUND', 'That job or file could not be found.', 404);
    }
    if (job.kind !== 'cloak') {
      throw new ApiError('BAD_PARAMS', 'The job is not a cloak job.', 422);
    }
    if (!completedCloakJobs.has(job_id)) {
      throw new ApiError('JOB_NOT_READY', 'That job is not finished yet.', 409);
    }
    const manifest = await loadManifest();
    const response = await fetch(manifest.sample_certificate_url);
    if (!response.ok) {
      throw new ApiError('INTERNAL', 'The sample certificate could not be loaded.', response.status);
    }
    return response.blob();
  },

  async verifyWatermark(): Promise<{ found: boolean; tag: string | null }> {
    throw new ApiError('NOT_IMPLEMENTED', 'Watermark verification is not available in Demo Mode.', 501);
  },

  absoluteUrl(path: string): string {
    return path;
  },
};

async function createSampleJob(sample: DemoSample): Promise<StartJobResponse> {
    const job_id = makeJobId();
    jobs.set(job_id, { kind: 'cloak', startedAt: Date.now(), sample });
    return { job_id, status: 'queued' };
}
