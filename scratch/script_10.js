
    (function () {
      const savedTheme = localStorage.getItem('theme') || '0' || 'dark';
      if (savedTheme === 'light') {
        document.body.classList.add('light-theme');
      }
      window.setTheme = function(theme) {
        localStorage.setItem('theme', theme);
        document.body.classList.toggle('light-theme', theme === 'light');
        if (theme === 'light') {
          document.body.classList.remove('bg-light', 'text-dark');
        }
      };
      window.currentTheme = savedTheme;
    })();
  