import { useEffect, useState } from 'react';
import { api } from '../api';
import { ApiError } from '../api/client';
import { friendlyErrorMessage } from '../api/errorMessages';
import type { CloakResult, Job } from '../api/types';

const POLL_INTERVAL_MS = 1000;
const POLL_TIMEOUT_MS = 3 * 60 * 1000;
const MAX_CONSECUTIVE_NETWORK_ERRORS = 2;

interface JobPollingState<T> {
  job: Job<T> | null;
  isPolling: boolean;
  error: string | null;
  networkRetry: number;
}

function errorMessage(error: unknown): string {
  return friendlyErrorMessage(error);
}

export function useJobPolling<T = CloakResult>(jobId: string | null) {
  const [state, setState] = useState<JobPollingState<T>>({
    job: null,
    isPolling: false,
    error: null,
    networkRetry: 0,
  });

  useEffect(() => {
    if (!jobId) {
      setState({ job: null, isPolling: false, error: null, networkRetry: 0 });
      return;
    }

    let active = true;
    let consecutiveNetworkErrors = 0;
    let pollTimer: ReturnType<typeof setTimeout> | undefined;
    const startedAt = Date.now();

    setState({ job: null, isPolling: true, error: null, networkRetry: 0 });

    const timeoutTimer = setTimeout(() => {
      if (!active) return;
      active = false;
      setState((current) => ({
        ...current,
        isPolling: false,
        error: 'This job took longer than 3 minutes. Please try again.',
      }));
    }, POLL_TIMEOUT_MS);

    const poll = async () => {
      if (!active) return;
      if (Date.now() - startedAt >= POLL_TIMEOUT_MS) {
        active = false;
        clearTimeout(timeoutTimer);
        setState((current) => ({
          ...current,
          isPolling: false,
          error: 'This job took longer than 3 minutes. Please try again.',
        }));
        return;
      }

      try {
        const job = await api.getJob<T>(jobId);
        if (!active) return;
        consecutiveNetworkErrors = 0;
        setState({
          job,
          isPolling: job.status === 'queued' || job.status === 'running',
          error: null,
          networkRetry: 0,
        });

        if (job.status === 'queued' || job.status === 'running') {
          pollTimer = setTimeout(poll, POLL_INTERVAL_MS);
        } else {
          active = false;
          clearTimeout(timeoutTimer);
        }
      } catch (error) {
        if (!active) return;

        if (error instanceof ApiError) {
          active = false;
          clearTimeout(timeoutTimer);
          setState((current) => ({
            ...current,
            isPolling: false,
            error: friendlyErrorMessage(error),
          }));
          return;
        }

        if (error instanceof TypeError) {
          consecutiveNetworkErrors += 1;
          if (consecutiveNetworkErrors > MAX_CONSECUTIVE_NETWORK_ERRORS) {
            active = false;
            clearTimeout(timeoutTimer);
            setState((current) => ({
              ...current,
              isPolling: false,
              error:
                typeof navigator !== 'undefined' && !navigator.onLine
                  ? friendlyErrorMessage(new TypeError())
                  : 'We could not reach the service after 3 attempts. Please try again.',
            }));
            return;
          }
          setState((current) => ({
            ...current,
            networkRetry: consecutiveNetworkErrors,
          }));
          pollTimer = setTimeout(poll, POLL_INTERVAL_MS);
          return;
        }

        active = false;
        clearTimeout(timeoutTimer);
        setState((current) => ({
          ...current,
          isPolling: false,
          error: errorMessage(error),
        }));
      }
    };

    void poll();

    return () => {
      active = false;
      clearTimeout(timeoutTimer);
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [jobId]);

  return state;
}
