export type Strength = 'light' | 'standard' | 'strong';
export type SimPreset =
  | 'background_snow'
  | 'background_beach'
  | 'new_hairstyle'
  | 'vintage_style';
export type JobType = 'cloak' | 'attack_sim';
export type JobStatus = 'queued' | 'running' | 'done' | 'error';
export type Stage =
  | 'queued'
  | 'detecting_face'
  | 'optimizing'
  | 'robustness_check'
  | 'finalizing'
  | 'editing_original'
  | 'editing_cloaked'
  | 'scoring'
  | 'done';

export interface ErrorObj {
  code: string;
  message: string;
}

export interface Job<T> {
  job_id: string;
  type: JobType;
  status: JobStatus;
  progress: number;
  stage: Stage;
  result: T | null;
  error: ErrorObj | null;
}

export interface CloakResult {
  file_id: string;
  original_url: string;
  cloaked_url: string;
  heatmap_url: string;
  metrics: {
    protection_score: number;
    robustness: {
      jpeg_q75: number;
      resize_50: number;
      social_like: number;
    };
    visual_quality: {
      psnr_db: number;
      ssim: number;
    };
    working_size: {
      w: number;
      h: number;
    };
    elapsed_s: number;
  };
  metadata_report: {
    had_gps: boolean;
    removed: string[];
  };
  hashes: {
    sha256_cloaked: string;
    phash_original: string;
  };
  watermark: {
    embedded: boolean;
    tag: string;
  } | null;
  face_found: boolean;
  expires_at: string;
}

export interface SimResult {
  preset: SimPreset;
  edit_on_original_url: string;
  edit_on_cloaked_url: string;
  disruption_score: number;
  seed: number;
}

export interface AppConfig {
  version: string;
  mode: 'gpu' | 'cpu';
  simulator_enabled: boolean;
  features: {
    watermark: boolean;
    face_focus: boolean;
    robust_mode: boolean;
  };
  limits: {
    max_upload_mb: number;
    ttl_seconds: number;
    max_side_px: number;
  };
  strengths: {
    id: Strength;
    label: string;
    description: string;
  }[];
  sim_presets: {
    id: SimPreset;
    label: string;
  }[];
}

export interface HealthResponse {
  status: string;
  version: string;
  mode: 'gpu' | 'cpu';
  queue_depth: number;
  simulator_enabled: boolean;
}

export interface StartJobResponse {
  job_id: string;
  status: 'queued';
}

export interface CloakForm {
  file: File;
  strength: Strength;
  face_focus: boolean;
  robust_mode: boolean;
  embed_watermark: boolean;
  owner_tag?: string;
}

export interface DemoSample {
  id: string;
  label: string;
  thumb_url: string;
  cloak: CloakResult;
  sims: Partial<Record<SimPreset, SimResult>>;
}

export interface CloakOptions {
  strength: Strength;
  face_focus: boolean;
  robust_mode: boolean;
  embed_watermark: boolean;
  owner_tag?: string;
}

export interface Api {
  health(): Promise<HealthResponse>;
  config(): Promise<AppConfig>;
  startCloak(form: CloakForm): Promise<StartJobResponse>;
  startSampleCloak(sampleId: string, options: CloakOptions): Promise<StartJobResponse>;
  demoSamples(): Promise<DemoSample[]>;
  getJob<T>(id: string): Promise<Job<T>>;
  startSim(job_id: string, preset: SimPreset): Promise<StartJobResponse>;
  certificate(job_id: string, owner_name?: string): Promise<Blob>;
  verifyWatermark(file: File): Promise<{ found: boolean; tag: string | null }>;
  absoluteUrl(path: string): string;
}
