interface SplashPageProps {
  onEnter: () => void;
}

function SplashPage({ onEnter }: SplashPageProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center"
      style={{ backgroundColor: '#F6F1EA' }}
    >
      {/* Background pattern */}
      <div className="absolute inset-0 opacity-40 pointer-events-none">
        <svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">
          <defs>
            <pattern id="hearts-bg" x="0" y="0" width="60" height="60" patternUnits="userSpaceOnUse">
              <path
                d="M30 44C16 34 14 24 19 19.5c3.5-3.2 8.5-2.2 11 1.5 2.5-3.7 7.5-4.7 11-1.5 5 4.5 3 14.5-11 24.5Z"
                fill="none"
                stroke="#1E5FAD"
                strokeOpacity="0.12"
                strokeWidth="1.5"
                strokeLinejoin="round"
              />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#hearts-bg)" />
        </svg>
      </div>

      {/* Content */}
      <div className="relative z-10 flex flex-col items-center text-center px-6 max-w-2xl">
        {/* Logo */}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 320 80"
          role="img"
          aria-label="Winserve Care Services"
          className="w-72 md:w-96 mb-8"
        >
          <title>Winserve Care Services</title>
          <g transform="translate(4 8)">
            <path
              d="M32 57.5C9.5 42 6.5 26.5 14.5 17.8c5.5-6 14.2-4.7 17.5 1.9 3.3-6.6 12-7.9 17.5-1.9C57.5 26.5 54.5 42 32 57.5Z"
              fill="none"
              stroke="#1E5FAD"
              strokeWidth="3.2"
              strokeLinejoin="round"
            />
            <circle cx="32" cy="22.5" r="3.6" fill="#E8624B" />
            <path
              d="M22.5 38c0-4.6 4.3-8.2 9.5-8.2s9.5 3.6 9.5 8.2v.8c0 1-.8 1.8-1.8 1.8H24.3c-1 0-1.8-.8-1.8-1.8V38Z"
              fill="#E8624B"
            />
          </g>
          <g fontFamily="'Fraunces', Georgia, serif" fontWeight="600">
            <text x="82" y="42" fontSize="26" letterSpacing="1.2" fill="#0F2340">
              WINSERVE
            </text>
            <text
              x="82"
              y="62"
              fontSize="11"
              letterSpacing="3"
              fill="#1E5FAD"
              fontFamily="'Inter', system-ui, sans-serif"
              fontWeight="500"
            >
              CARE SERVICES
            </text>
          </g>
        </svg>

        {/* Tagline */}
        <p
          className="text-lg md:text-xl mb-2 font-medium"
          style={{ color: '#0F2340', fontFamily: "'Fraunces', Georgia, serif" }}
        >
          Personalised care, trusted support
        </p>
        <p
          className="text-sm md:text-base mb-10"
          style={{ color: '#1E5FAD', fontFamily: "'Inter', system-ui, sans-serif" }}
        >
          At home, where it matters most.
        </p>

        {/* Enter button */}
        <button
          onClick={onEnter}
          className="px-8 py-3 rounded-xl text-white font-semibold text-base shadow-lg transition-all duration-200 hover:scale-105 hover:shadow-xl focus:outline-none focus:ring-2 focus:ring-blue-600 focus:ring-offset-2"
          style={{
            backgroundColor: '#1E5FAD',
            fontFamily: "'Inter', system-ui, sans-serif",
          }}
          aria-label="Enter scheduling application"
        >
          Enter Scheduling
        </button>

        {/* Footer */}
        <p
          className="mt-12 text-xs"
          style={{ color: '#7FA894', fontFamily: "'Inter', system-ui, sans-serif" }}
        >
          © Winserve Care Services Ltd
        </p>
      </div>
    </div>
  );
}

export default SplashPage;
