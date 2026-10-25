interface DownloadButtonProps {
  url: string;
}

export default function DownloadButton({ url }: DownloadButtonProps) {
  const separator = url.includes('?') ? '&' : '?';

  return (
    <a className="primary-button w-full" href={`${url}${separator}download=1`}>
      Download protected PNG
    </a>
  );
}
