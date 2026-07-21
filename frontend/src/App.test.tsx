import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import App from './App';

function renderApp(initialRoute = '/') {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <App />
    </MemoryRouter>,
  );
}

describe('App', () => {
  it('renders the navigation sidebar', () => {
    renderApp();
    expect(screen.getByRole('navigation', { name: /main navigation/i })).toBeInTheDocument();
  });

  it('renders the Dashboard page at /', () => {
    renderApp('/');
    expect(screen.getByRole('heading', { name: /dashboard/i })).toBeInTheDocument();
  });

  it('renders the Carers page at /carers', () => {
    renderApp('/carers');
    expect(screen.getByRole('heading', { name: /carers/i })).toBeInTheDocument();
  });

  it('renders the Patients page at /patients', () => {
    renderApp('/patients');
    expect(screen.getByRole('heading', { name: /patients/i })).toBeInTheDocument();
  });

  it('renders the Skills page at /skills', () => {
    renderApp('/skills');
    expect(screen.getByRole('heading', { name: /skills/i })).toBeInTheDocument();
  });

  it('renders the Constraints page at /constraints', () => {
    renderApp('/constraints');
    expect(screen.getByRole('heading', { name: /constraints/i })).toBeInTheDocument();
  });

  it('renders the Exceptions page at /exceptions', () => {
    renderApp('/exceptions');
    expect(screen.getByRole('heading', { name: /exceptions/i })).toBeInTheDocument();
  });

  it('renders the Reports page at /reports', () => {
    renderApp('/reports');
    expect(screen.getByRole('heading', { name: /reports/i })).toBeInTheDocument();
  });

  it('renders the Scenarios page at /scenarios', () => {
    renderApp('/scenarios');
    expect(screen.getByRole('heading', { name: /scenarios/i })).toBeInTheDocument();
  });

  it('renders the Configuration page at /config', () => {
    renderApp('/config');
    expect(screen.getByRole('heading', { name: /configuration/i })).toBeInTheDocument();
  });

  it('has all navigation links', () => {
    renderApp();
    expect(screen.getByRole('link', { name: /dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /carers/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /patients/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /skills/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /constraints/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /exceptions/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /reports/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /scenarios/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /configuration/i })).toBeInTheDocument();
  });
});
