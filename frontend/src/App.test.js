import { render, screen } from '@testing-library/react';
import App from './App';

test('shows the login link on the home page', () => {
  render(<App />);
  expect(screen.getByRole('link', { name: /log in/i })).toBeInTheDocument();
});
