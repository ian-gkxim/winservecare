import { NavLink } from 'react-router-dom';

const navItems = [
  { to: '/', label: 'Dashboard', icon: '📊' },
  { to: '/carers', label: 'Carers', icon: '👤' },
  { to: '/patients', label: 'Patients', icon: '🏠' },
  { to: '/visits', label: 'Visits', icon: '📅' },
  { to: '/skills', label: 'Skills', icon: '🎯' },
  { to: '/constraints', label: 'Constraints', icon: '⚙️' },
  { to: '/exceptions', label: 'Exceptions', icon: '⚠️' },
  { to: '/reports', label: 'Reports', icon: '📈' },
  { to: '/scenarios', label: 'Scenarios', icon: '🔀' },
  { to: '/config', label: 'Configuration', icon: '🔧' },
];

export default function NavSidebar() {
  return (
    <aside className="w-64 min-h-screen bg-gray-900 text-white flex flex-col">
      <div className="p-4 border-b border-gray-700">
        <h1 className="text-lg font-bold">WinServe Care</h1>
        <p className="text-xs text-gray-400">AI Operations Optimiser</p>
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
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-300 hover:bg-gray-800 hover:text-white'
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
