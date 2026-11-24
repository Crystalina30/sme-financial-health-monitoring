import { createContext, useContext, useEffect, useState } from 'react';

const BreadcrumbContext = createContext(null);

/** Holds the trail shown in the top bar; each page sets its own. */
export function BreadcrumbProvider({ children }) {
  const [crumbs, setCrumbs] = useState([]);
  return (
    <BreadcrumbContext.Provider value={{ crumbs, setCrumbs }}>{children}</BreadcrumbContext.Provider>
  );
}

export function useBreadcrumbTrail() {
  return useContext(BreadcrumbContext).crumbs;
}

/**
 * Sets the top bar's trail for the current page. Each crumb is
 * { label, to }; the last one is the current page and needs no `to`.
 */
export function useBreadcrumbs(crumbs) {
  const { setCrumbs } = useContext(BreadcrumbContext);
  // Compared by content, so a new array with the same crumbs does not loop.
  const key = JSON.stringify(crumbs);
  useEffect(() => {
    setCrumbs(JSON.parse(key));
  }, [key, setCrumbs]);
}
