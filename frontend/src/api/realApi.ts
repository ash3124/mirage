import { createHttpClient } from './client';
import { ApiError } from './client';
import { getSettings } from '../state/settings';
import type {
  Api,
  AppConfig,
  CloakForm,
  CloakOptions,
  DemoSample,
  HealthResponse,
  Job,
  SimPreset,
  StartJobResponse,
} from './types';

function http() {
  return createHttpClient(getSettings().apiBaseUrl);
}

function cloakFormData(form: CloakForm): FormData {
  const data = new FormData();
  data.append('image', form.file);
  data.append('strength', form.strength);
  data.append('face_focus', String(form.face_focus));
  data.append('robust_mode', String(form.robust_mode));
  data.append('embed_watermark', String(form.embed_watermark));
  if (form.owner_tag !== undefined) {
    data.append('owner_tag', form.owner_tag);
  }
  return data;
}

export const realApi: Api = {
  health(): Promise<HealthResponse> {
    return http().requestJson('/health');
  },

  config(): Promise<AppConfig> {
    return http().requestJson('/config');
  },

  startCloak(form: CloakForm): Promise<StartJobResponse> {
    return http().requestJson('/cloak', {
      method: 'POST',
      body: cloakFormData(form),
    });
  },

  async startSampleCloak(_sampleId: string, _options: CloakOptions): Promise<StartJobResponse> {
    throw new ApiError('NOT_IMPLEMENTED', 'Sample photos are available in Demo Mode only.', 501);
  },

  async demoSamples(): Promise<DemoSample[]> {
    return [];
  },

  getJob<T>(id: string): Promise<Job<T>> {
    return http().requestJson(`/jobs/${encodeURIComponent(id)}`);
  },

  startSim(job_id: string, preset: SimPreset): Promise<StartJobResponse> {
    return http().requestJson('/attack-sim', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id, preset }),
    });
  },

  certificate(job_id: string, owner_name?: string): Promise<Blob> {
    return http().requestBlob('/certificate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(
        owner_name === undefined ? { job_id } : { job_id, owner_name },
      ),
    });
  },

  verifyWatermark(file: File): Promise<{ found: boolean; tag: string | null }> {
    const data = new FormData();
    data.append('image', file);
    return http().requestJson('/watermark/verify', {
      method: 'POST',
      body: data,
    });
  },

  absoluteUrl(path: string): string {
    return http().absoluteUrl(path);
  },
};
