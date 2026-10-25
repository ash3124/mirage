type ApiErrorCode =
  | 'INVALID_IMAGE'
  | 'TOO_LARGE'
  | 'BAD_PARAMS'
  | 'JOB_NOT_FOUND'
  | 'JOB_EXPIRED'
  | 'JOB_NOT_READY'
  | 'BUSY'
  | 'SIM_UNAVAILABLE'
  | 'SIM_BLOCKED'
  | 'NOT_IMPLEMENTED'
  | 'INTERNAL';

const apiErrorMessages: Record<ApiErrorCode | 'OFFLINE' | 'NETWORK_ERROR', string> = {
  INVALID_IMAGE: 'That file could not be read as a photo. Choose a JPG, PNG, or WebP image.',
  TOO_LARGE: 'This photo is over the 10 MB limit. Choose a smaller image and try again.',
  BAD_PARAMS: 'Some details were invalid. Check your choices and try again.',
  JOB_NOT_FOUND: 'We could not find this job or image. Start again from the Studio.',
  JOB_EXPIRED: 'This result has expired. Protect the photo again to create a fresh result.',
  JOB_NOT_READY: 'This step is still getting ready. Wait a moment, then try again.',
  BUSY: 'The service is handling many requests right now. Wait a moment and try again.',
  SIM_UNAVAILABLE: 'The live comparison is unavailable on this server. Try a pre-recorded example.',
  SIM_BLOCKED: 'The AI safety filter stopped this edit. Choose a different preset and try again.',
  NOT_IMPLEMENTED: 'This feature is not enabled on this server.',
  INTERNAL: 'Something went wrong on our side. Please try again in a moment.',
  OFFLINE: 'You appear to be offline. Reconnect to the internet and try again.',
  NETWORK_ERROR: 'We could not reach the service. Check your connection and try again.',
};

function hasFriendlyMessageCode(code: string): code is keyof typeof apiErrorMessages {
  return Object.prototype.hasOwnProperty.call(apiErrorMessages, code);
}

export function friendlyErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'code' in error) {
    const { code, message } = error as { code?: unknown; message?: unknown };
    if (typeof code === 'string' && hasFriendlyMessageCode(code)) {
      return apiErrorMessages[code];
    }
    if (typeof message === 'string' && message.trim()) return message;
  }

  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return apiErrorMessages.OFFLINE;
  }
  if (error instanceof TypeError) return apiErrorMessages.NETWORK_ERROR;
  if (error instanceof Error && error.message) return error.message;
  return 'Something went wrong. Please try again.';
}
