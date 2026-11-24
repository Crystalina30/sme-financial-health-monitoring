/**
 * Small line icons drawn inline, so the app needs no icon library. They take
 * the text colour of their surroundings and are hidden from screen readers;
 * the text beside each one carries its meaning.
 */
const PATHS = {
  arrowRight: <path d="M5 12h14M13 6l6 6-6 6" />,
  plus: <path d="M12 5v14M5 12h14" />,
  check: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  alert: (
    <>
      <path d="M12 4 2.8 19.5h18.4L12 4Z" />
      <path d="M12 10v4.2M12 17.2v.1" />
    </>
  ),
  cross: <path d="m6.5 6.5 11 11M17.5 6.5l-11 11" />,
  minus: <path d="M6 12h12" />,
  trendDown: <path d="m3 7 6.5 6.5 4-4L21 17M21 11.5V17h-5.5" />,
  logout: (
    <>
      <path d="M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4" />
      <path d="M10 16.5 5.5 12 10 7.5M5.5 12H15" />
    </>
  ),
  edit: (
    <>
      <path d="M4 20h4L18.5 9.5a2.1 2.1 0 0 0-4-4L4 16v4Z" />
      <path d="m13.5 6.5 4 4" />
    </>
  ),
  chart: <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />,
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" />
    </>
  ),
  moon: <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />,
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5.5M12 7.6v.1" />
    </>
  ),
  flipBack: (
    <>
      <path d="M4 12a8 8 0 1 0 2.3-5.6" />
      <path d="M4 4v4.5h4.5" />
    </>
  ),
  calendar: (
    <>
      <rect x="3.5" y="5" width="17" height="15" rx="2" />
      <path d="M3.5 10h17M8 3v4M16 3v4" />
    </>
  ),
  overview: (
    <>
      <rect x="4" y="4" width="6.5" height="8" rx="1.5" />
      <rect x="13.5" y="4" width="6.5" height="5" rx="1.5" />
      <rect x="4" y="15" width="6.5" height="5" rx="1.5" />
      <rect x="13.5" y="12" width="6.5" height="8" rx="1.5" />
    </>
  ),
  upload: (
    <>
      <path d="M14 3.5H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8.5l-5-5Z" />
      <path d="M14 3.5v5h5M12 17v-6M9.5 13.5 12 11l2.5 2.5" />
    </>
  ),
  analysis: (
    <>
      <path d="M12 3.5a8.5 8.5 0 1 0 8.5 8.5H12V3.5Z" />
      <path d="M15 3.8A8.5 8.5 0 0 1 20.2 9H15V3.8Z" />
    </>
  ),
  history: (
    <>
      <path d="M4 12a8 8 0 1 0 2.3-5.6" />
      <path d="M4 4v4.5h4.5M12 8v4.5l3 2" />
    </>
  ),
  trash: (
    <>
      <path d="M4.5 7h15M9.5 7V4.5h5V7M6.5 7l1 13h9l1-13" />
      <path d="M10 11v5.5M14 11v5.5" />
    </>
  ),
  building: (
    <>
      <path d="M4 20V6.5L12 4v16M12 9l8 2.5V20M2.5 20h19" />
      <path d="M7.5 9v.1M7.5 12.5v.1M7.5 16v.1M15.5 14v.1M15.5 17v.1" />
    </>
  ),
};

export default function Icon({ name }) {
  return (
    <svg className="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {PATHS[name]}
    </svg>
  );
}
