import { useState, type FormEvent } from 'react';
import {
  createTakedownReport,
  reportPlatforms,
  type ReportPlatform,
} from '../data/takedownTemplates';

export default function TakedownGenerator() {
  const [platform, setPlatform] = useState<ReportPlatform>('Instagram');
  const [urls, setUrls] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [report, setReport] = useState<string | null>(null);
  const [copyError, setCopyError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  function generateReport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!description.trim()) {
      setValidationError('Add a short description to create the report.');
      return;
    }
    setValidationError(null);
    setCopyError(null);
    setCopied(false);
    setReport(createTakedownReport({ platform, urls, name, description }));
  }

  async function copyReport() {
    if (!report) return;
    setCopyError(null);
    try {
      await navigator.clipboard.writeText(report);
      setCopied(true);
    } catch (error) {
      setCopied(false);
      setCopyError(
        error instanceof Error
          ? `Could not copy automatically: ${error.message} Select the report text and copy it manually.`
          : 'Could not copy automatically. Select the report text and copy it manually.',
      );
    }
  }

  return (
    <div>
      <p className="leading-7 text-muted">
        Create a general report draft on this device. It is not sent anywhere.
      </p>
      <form className="mt-5 space-y-5" onSubmit={generateReport}>
        <label className="block">
          <span className="mb-2 block text-sm font-semibold">Platform</span>
          <select
            className="h-12 w-full rounded border border-peri bg-white px-3 text-navy"
            onChange={(event) => setPlatform(event.currentTarget.value as ReportPlatform)}
            value={platform}
          >
            {reportPlatforms.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="mb-2 block text-sm font-semibold">Content or account URL(s)</span>
          <textarea
            className="min-h-24 w-full rounded border border-peri bg-white p-3 text-navy"
            onChange={(event) => setUrls(event.currentTarget.value)}
            placeholder="Paste one or more links, one per line"
            value={urls}
          />
        </label>

        <label className="block">
          <span className="mb-2 block text-sm font-semibold">Your name (optional)</span>
          <input
            autoComplete="name"
            className="h-12 w-full rounded border border-peri bg-white px-3 text-navy"
            onChange={(event) => setName(event.currentTarget.value)}
            value={name}
          />
        </label>

        <label className="block">
          <span className="mb-2 block text-sm font-semibold">Short description</span>
          <textarea
            className="min-h-28 w-full rounded border border-peri bg-white p-3 text-navy"
            onChange={(event) => setDescription(event.currentTarget.value)}
            placeholder="Briefly describe why you are reporting this content."
            required
            value={description}
          />
        </label>

        {validationError && (
          <p className="bg-lavender px-4 py-3 text-sm text-navy" role="alert">
            {validationError}
          </p>
        )}
        <button className="primary-button w-full" type="submit">
          Generate report
        </button>
      </form>

      {report && (
        <div className="mt-6 bg-lavender p-5">
          <label className="block">
            <span className="mb-2 block font-semibold">Report draft</span>
            <textarea
              aria-label="Generated report text"
              className="min-h-64 w-full border border-peri bg-white p-3 text-sm leading-6 text-navy"
              onFocus={(event) => event.currentTarget.select()}
              readOnly
              value={report}
            />
          </label>
          <button className="primary-button mt-4 w-full" onClick={() => void copyReport()} type="button">
            {copied ? 'Report copied' : 'Copy report text'}
          </button>
          {copyError && (
            <p className="mt-3 text-sm text-navy" role="alert">
              {copyError}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
