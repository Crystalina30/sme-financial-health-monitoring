import { useTheme } from '../context/ThemeContext.jsx';
import Icon from './Icon.jsx';

const OPTIONS = [
  { value: 'light', label: 'Light', icon: 'sun' },
  { value: 'dark', label: 'Dark', icon: 'moon' },
];

/** Two-option switch between the light and dark themes. */
export default function ThemeToggle({ className = '' }) {
  const { theme, setTheme } = useTheme();
  return (
    <div className={`theme-toggle ${className}`} role="radiogroup" aria-label="Colour theme">
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={theme === option.value}
          aria-label={option.label}
          className="theme-toggle-option"
          onClick={() => setTheme(option.value)}
        >
          <Icon name={option.icon} />
          <span>{option.label}</span>
        </button>
      ))}
    </div>
  );
}
