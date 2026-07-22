import { NavLink } from 'react-router-dom';

const navItems = [
  { to: '/', label: 'Dashboard', icon: '📊' },
  { to: '/carers', label: 'Carers', icon: '👤' },
  { to: '/patients', label: 'Patients', icon: '🏠' },
  { to: '/visits', label: 'Visits', icon: '📅' },
  { to: '/soft-skills', label: 'Soft Skills', icon: '🎯' },
  { to: '/exceptions', label: 'Exceptions', icon: '⚠️' },
  { to: '/reports', label: 'Reports', icon: '📈' },
  { to: '/scenarios', label: 'Scenarios', icon: '🔀' },
  { to: '/journey-sandbox', label: 'Journey Sandbox', icon: '🧪' },
  { to: '/config', label: 'Configuration', icon: '🔧' },
];

export default function NavSidebar() {
  return (
    <aside className="w-64 min-h-screen bg-brand-ink text-brand-cloud flex flex-col">
      <div className="p-4 border-b border-brand-mist">
        <h1 className="text-lg font-bold">WinServe Care</h1>
        <p className="text-xs text-brand-mist/70">AI Operations Optimiser</p>
      </div>
      <nav className="flex-1 py-4" aria-label="Main navigation">
        <ul className="space-y-1">
          {navItems.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-2 text-sm rounded-md mx-2 transition-colors ${
                    isActive
                      ? 'bg-brand-primary text-brand-cloud'
                      : 'text-brand-mist/70 hover:bg-brand-ink/80 hover:text-brand-cloud'
                  }`
                }
              >
                <span className="text-base" aria-hidden="true">{item.icon}</span>
                <span>{item.label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
}
