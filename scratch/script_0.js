
    (function() {
      const storedTheme = localStorage.getItem('theme');
      const prefersLight = window.matchMedia('(prefers-color-scheme: light)').matches;
      const theme = storedTheme || (prefersLight ? 'light' : 'dark');
      document.documentElement.setAttribute('data-theme', theme);
      if (theme === 'light') {
        document.getElementById('themeColorMeta').setAttribute('content', '#F0F4F8');
      }
    })();
  