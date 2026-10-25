import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { friendlyErrorMessage } from '../api/errorMessages';
import type { CloakResult } from '../api/types';

interface CertificateButtonProps {
  jobId: string;
  result: CloakResult;
}

type CopyField = 'sha256' | 'phash';

export default function CertificateButton({ jobId, result }: CertificateButtonProps) {
  const [ownerName, setOwnerName] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<CopyField | null>(null);

  async function downloadCertificate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (downloading) return;
    setDownloading(true);
    setError(null);
    try {
      const blob = await api.certificate(jobId, ownerName.trim() || undefined);
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = 'mirage-protection-record.pdf';
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch (cause) {
      setError(friendlyErrorMessage(cause));
    } finally {
      setDownloading(false);
    }
  }

  async function copyHash(field: CopyField, value: string) {
    setError(null);
    try {
      await navigator.clipboard.writeText(value);
      setCopied(field);
    } catch (cause) {
      setCopied(null);
      setError(
        cause instanceof Error
          ? `Could not copy the hash: ${cause.message}`
          : 'Could not copy the hash. Select and copy it manually.',
      );
    }
  }

  return (
    <section aria-labelledby="records-title" className="mt-8 space-y-7">
      <header>
        <p className="eyebrow">Step 4 · Keep records</p>
        <h2 id="records-title" className="mt-2 font-serif text-3xl">
          Keep a protection record
        </h2>
        <p className="mt-3 leading-7 text-muted">
          Download a self-generated record and keep these hashes somewhere safe.
        </p>
      </header>

      <form className="rounded bg-wash p-6 md:p-7" onSubmit={downloadCertificate}>
        <label className="block">
          <span className="mb-2 block text-sm font-semibold">Name (optional)</span>
          <input
            autoComplete="name"
            className="h-12 w-full rounded border border-peri bg-white px-3 text-navy"
            maxLength={60}
            onChange={(event) => setOwnerName(event.currentTarget.value)}
            placeholder="Name on your record"
            value={ownerName}
          />
        </label>
        <button
          className="primary-button mt-5 w-full disabled:cursor-not-allowed disabled:opacity-50"
          disabled={downloading}
          type="submit"
        >
          {downloading ? 'Preparing certificate…' : 'Download certificate (PDF)'}
        </button>
      </form>

      <section aria-label="Image hashes" className="rounded bg-wash p-6 md:p-7">
        <h3 className="font-serif text-2xl">Image hashes</h3>
        <dl className="mt-4">
          <div className="border-t border-lavender py-4">
            <dt className="font-semibold">SHA-256 of protected image</dt>
            <dd className="mt-2 break-all font-mono text-sm text-muted">
              {result.hashes.sha256_cloaked}
            </dd>
            <button
              className="text-link mt-2 text-sm"
              onClick={() => void copyHash('sha256', result.hashes.sha256_cloaked)}
              type="button"
            >
              {copied === 'sha256' ? 'Copied' : 'Copy SHA-256'}
            </button>
          </div>
          <div className="border-t border-lavender py-4">
            <dt className="font-semibold">Perceptual hash of original</dt>
            <dd className="mt-2 break-all font-mono text-sm text-muted">
              {result.hashes.phash_original}
            </dd>
            <button
              className="text-link mt-2 text-sm"
              onClick={() => void copyHash('phash', result.hashes.phash_original)}
              type="button"
            >
              {copied === 'phash' ? 'Copied' : 'Copy pHash'}
            </button>
          </div>
        </dl>
      </section>

      {result.watermark?.embedded && (
        <p className="bg-lavender px-4 py-4 text-sm leading-6 text-navy">
          Invisible ownership tag: <strong>{result.watermark.tag}</strong>. Watermark
          verification is available at <Link className="text-link" to="/verify">/verify</Link>.
        </p>
      )}

      {error && (
        <p className="bg-lavender px-4 py-3 text-sm text-navy" role="alert">
          {error}
        </p>
      )}
      <Link
        className="flex min-h-[54px] w-full items-center justify-center border-[1.5px] border-peri bg-transparent px-8 text-[17px] font-semibold text-navy"
        to="/safety-kit"
      >
        Open the Safety Kit
      </Link>
    </section>
  );
}
