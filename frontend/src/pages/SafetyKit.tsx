import { useState } from 'react';
import TakedownGenerator from '../components/TakedownGenerator';
import { cyberCrimePortalUrl, helplines, stopNciiUrl } from '../data/helplines';

interface SafetyStep {
  title: string;
  content: React.ReactNode;
}

export default function SafetyKit() {
  const [openStep, setOpenStep] = useState(0);

  const steps: SafetyStep[] = [
    {
      title: 'Stay calm, do not delete',
      content: (
        <p className="leading-7 text-muted">
          Evidence matters. Take a moment, and consider asking someone you trust to stay with you.
          You do not have to respond to or confront the person who posted it.
        </p>
      ),
    },
    {
      title: 'Save evidence',
      content: (
        <ul className="list-disc space-y-2 pl-5 leading-7 text-muted">
          <li>Save screenshots with the page URL and date or time visible.</li>
          <li>Note account names, usernames, and any relevant post details.</li>
          <li>Keep copies somewhere private and secure. Do not engage the person.</li>
        </ul>
      ),
    },
    {
      title: 'Report to the platform',
      content: <TakedownGenerator />,
    },
    {
      title: 'Report to authorities (India)',
      content: (
        <div>
          <ul className="divide-y divide-lavender">
            {helplines.map((helpline) => (
              <li
                className="flex flex-wrap items-center justify-between gap-3 py-4 first:pt-0"
                key={helpline.number}
              >
                <div>
                  <p className="font-serif text-3xl">{helpline.number}</p>
                  <p className="text-sm text-muted">{helpline.name}</p>
                </div>
                <a className="text-link" href={helpline.telephone}>
                  Call
                </a>
              </li>
            ))}
          </ul>
          <div className="mt-5 flex flex-col items-start gap-3">
            <a
              className="text-link"
              href={cyberCrimePortalUrl}
              rel="noreferrer"
              target="_blank"
            >
              National Cyber Crime Reporting Portal
            </a>
            <a className="text-link" href={stopNciiUrl} rel="noreferrer" target="_blank">
              StopNCII.org
            </a>
            <p className="text-sm leading-6 text-muted">
              StopNCII.org creates a hash on your device for eligible intimate images; review
              its current guidance before using it.
            </p>
          </div>
          <p className="mt-5 bg-lavender px-4 py-3 text-sm leading-6 text-navy">
            Numbers and links change; verify before relying on them.
          </p>
        </div>
      ),
    },
    {
      title: 'Look after yourself',
      content: (
        <p className="leading-7 text-muted">
          This is not your fault. Consider reaching out to a trusted person or a support
          organization, and take the time you need.
        </p>
      ),
    },
  ];

  return (
    <main className="page-width max-w-[824px] py-12 md:py-16">
      <p className="eyebrow">Safety Kit</p>
      <h1 className="mt-3 font-serif text-4xl font-medium md:text-5xl">
        Found misuse of your image?
      </h1>
      <p className="mt-4 font-serif text-2xl italic text-peri">
        You are not alone, and it is not your fault.
      </p>

      <ol className="mt-10">
        {steps.map((step, index) => {
          const expanded = openStep === index;
          const panelId = `safety-step-${index + 1}`;
          return (
            <li className="border-t border-lavender" key={step.title}>
              <h2>
                <button
                  aria-controls={panelId}
                  aria-expanded={expanded}
                  className="flex min-h-16 w-full items-center gap-4 py-4 text-left"
                  onClick={() => setOpenStep(expanded ? -1 : index)}
                  type="button"
                >
                  <span aria-hidden="true" className="font-serif text-2xl text-peri">
                    0{index + 1}
                  </span>
                  <span className="flex-1 font-semibold">{step.title}</span>
                  <span aria-hidden="true" className="text-xl text-navy">
                    {expanded ? '−' : '+'}
                  </span>
                </button>
              </h2>
              {expanded && (
                <div className="pb-6 pl-12" id={panelId}>
                  {step.content}
                  {index < steps.length - 1 && (
                    <button
                      className="text-link mt-5 text-sm"
                      onClick={() => setOpenStep(index + 1)}
                      type="button"
                    >
                      Next step
                    </button>
                  )}
                  {index > 0 && (
                    <button
                      className="text-link ml-5 mt-5 text-sm"
                      onClick={() => setOpenStep(index - 1)}
                      type="button"
                    >
                      Previous step
                    </button>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ol>

      <p className="mt-8 border-t border-lavender pt-5 text-sm leading-6 text-muted">
        Mirage does not store your photos, and nothing here is sent anywhere. This page works
        offline.
      </p>
    </main>
  );
}
