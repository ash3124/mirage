import badParamsExample from '../../shared/examples/error.bad_params.json';
import invalidImageExample from '../../shared/examples/error.invalid_image.json';
import jobNotFoundExample from '../../shared/examples/error.job_not_found.json';
import jobNotReadyExample from '../../shared/examples/error.job_not_ready.json';
import tooLargeExample from '../../shared/examples/error.too_large.json';
import cloakDoneExample from '../../shared/examples/job.cloak.done.json';
import cloakQueuedExample from '../../shared/examples/job.cloak.queued.json';
import simDoneExample from '../../shared/examples/job.sim.done.json';
import simRunningExample from '../../shared/examples/job.sim.running.json';
import configExample from '../../shared/examples/config.ok.json';
import healthExample from '../../shared/examples/health.ok.json';
import manifestExample from '../../shared/examples/manifest.sample.json';
import { ApiError } from './client';
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
  Strength,
  Stage,
} from './types';

type MockJob =
  | { kind: 'cloak'; startedAt: number }
  | { kind: 'sim'; startedAt: number; result: SimResult };

const jobs = new Map<string, MockJob>();

function newJobId(): string {
  return crypto.randomUUID();
}

function validateImage(file: File): void {
  const allowed = ['image/jpeg', 'image/png', 'image/webp'];
  if (!allowed.includes(file.type)) {
    throw new ApiError(
      invalidImageExample.error.code,
      invalidImageExample.error.message,
      400,
    );
  }
  if (file.size > 10 * 1024 * 1024) {
    throw new ApiError(
      tooLargeExample.error.code,
      tooLargeExample.error.message,
      413,
    );
  }
}

function buildCloakJob(jobId: string, elapsed: number): Job<CloakResult> {
  const duration = 6000;
  let status: JobStatus = 'running';
  let stage: Stage = 'detecting_face';
  let progress = Math.min(95, Math.floor((elapsed / duration) * 100));

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
  } else if (elapsed < duration) {
    stage = 'finalizing';
  } else {
    return {
      ...cloakDoneExample,
      job_id: jobId,
      type: 'cloak',
      status: 'done',
      stage: 'done',
      result: cloakDoneExample.result,
      error: null,
    } satisfies Job<CloakResult>;
  }

  return {
    ...cloakQueuedExample,
    job_id: jobId,
    type: 'cloak',
    status,
    progress,
    stage,
    result: null,
    error: null,
  };
}

function buildSimJob(
  jobId: string,
  elapsed: number,
  result: SimResult,
): Job<SimResult> {
  const duration = 8000;
  if (elapsed >= duration) {
    return {
      ...simDoneExample,
      job_id: jobId,
      type: 'attack_sim',
      status: 'done',
      stage: 'done',
      result,
      error: null,
    } satisfies Job<SimResult>;
  }

  return {
    ...simRunningExample,
    job_id: jobId,
    type: 'attack_sim',
    status: 'running',
    progress: Math.min(95, Math.floor((elapsed / duration) * 100)),
    stage: elapsed < 2500 ? 'editing_original' : elapsed < 6000 ? 'editing_cloaked' : 'scoring',
    result: null,
    error: null,
  };
}

function simResultFor(preset: SimPreset): SimResult {
  const sample = manifestExample.samples[0];
  const result = sample.sims[preset];
  const fileId = cloakDoneExample.result.file_id;
  return {
    preset,
    edit_on_original_url: `/api/v1/files/${fileId}/sim_${preset}_original.png`,
    edit_on_cloaked_url: `/api/v1/files/${fileId}/sim_${preset}_cloaked.png`,
    disruption_score: result.disruption_score,
    seed: result.seed,
  };
}

export const mockApi: Api = {
  async health(): Promise<HealthResponse> {
    return { ...healthExample, mode: 'gpu' };
  },

  async config(): Promise<AppConfig> {
    return {
      ...configExample,
      mode: 'gpu',
      strengths: configExample.strengths.map((item) => ({
        ...item,
        id: item.id as Strength,
      })),
      sim_presets: configExample.sim_presets.map((item) => ({
        ...item,
        id: item.id as SimPreset,
      })),
    };
  },

  async startCloak(form: CloakForm): Promise<StartJobResponse> {
    validateImage(form.file);
    const job_id = newJobId();
    jobs.set(job_id, { kind: 'cloak', startedAt: Date.now() });
    return { job_id, status: 'queued' };
  },

  async startSampleCloak(_sampleId: string, _options: CloakOptions): Promise<StartJobResponse> {
    throw new ApiError('NOT_IMPLEMENTED', 'Sample photos are available in Demo Mode only.', 501);
  },

  async demoSamples(): Promise<DemoSample[]> {
    return [];
  },

  async getJob<T>(id: string): Promise<Job<T>> {
    const job = jobs.get(id);
    if (!job) {
      throw new ApiError(
        jobNotFoundExample.error.code,
        jobNotFoundExample.error.message,
        404,
      );
    }
    const result =
      job.kind === 'cloak'
        ? buildCloakJob(id, Date.now() - job.startedAt)
        : buildSimJob(id, Date.now() - job.startedAt, job.result);
    return result as Job<T>;
  },

  async startSim(job_id: string, preset: SimPreset): Promise<StartJobResponse> {
    const cloakJob = jobs.get(job_id);
    if (!cloakJob) {
      throw new ApiError(
        jobNotFoundExample.error.code,
        jobNotFoundExample.error.message,
        404,
      );
    }
    if (cloakJob.kind !== 'cloak') {
      throw new ApiError(
        badParamsExample.error.code,
        badParamsExample.error.message,
        422,
      );
    }
    if (Date.now() - cloakJob.startedAt < 6000) {
      throw new ApiError(
        jobNotReadyExample.error.code,
        jobNotReadyExample.error.message,
        409,
      );
    }
    if (!Object.prototype.hasOwnProperty.call(manifestExample.samples[0].sims, preset)) {
      throw new ApiError(
        badParamsExample.error.code,
        badParamsExample.error.message,
        422,
      );
    }

    const simJobId = newJobId();
    jobs.set(simJobId, {
      kind: 'sim',
      startedAt: Date.now(),
      result: simResultFor(preset),
    });
    return { job_id: simJobId, status: 'queued' };
  },

  async certificate(job_id: string): Promise<Blob> {
    const job = jobs.get(job_id);
    if (!job) {
      throw new ApiError(
        jobNotFoundExample.error.code,
        jobNotFoundExample.error.message,
        404,
      );
    }
    if (job.kind !== 'cloak') {
      throw new ApiError(
        badParamsExample.error.code,
        badParamsExample.error.message,
        422,
      );
    }
    if (Date.now() - job.startedAt < 6000) {
      throw new ApiError(
        jobNotReadyExample.error.code,
        jobNotReadyExample.error.message,
        409,
      );
    }
    const response = await fetch(manifestExample.sample_certificate_url);
    if (!response.ok) {
      throw new ApiError('INTERNAL', 'The sample certificate could not be loaded.');
    }
    return response.blob();
  },

  async verifyWatermark(): Promise<{ found: boolean; tag: string | null }> {
    throw new ApiError(
      'NOT_IMPLEMENTED',
      'Watermark verification is not enabled on this server.',
      501,
    );
  },

  absoluteUrl(path: string): string {
    return path;
  },
};
