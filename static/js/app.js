document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.card').forEach(card => card.classList.add('ready'));

  const menuButton = document.querySelector('.mobile-menu');
  const sidebar = document.querySelector('.sidebar');
  if (menuButton && sidebar) {
    let overlay = null;
    menuButton.addEventListener('click', () => {
      const open = sidebar.classList.toggle('open');
      menuButton.setAttribute('aria-expanded', open ? 'true' : 'false');
      menuButton.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
      if (open) {
        overlay = document.createElement('div');
        overlay.className = 'mobile-overlay';
        document.body.appendChild(overlay);
        overlay.addEventListener('click', closeMenu);
      } else if (overlay) {
        overlay.remove(); overlay = null;
      }
    });
    function closeMenu() {
      sidebar.classList.remove('open');
      menuButton.setAttribute('aria-expanded', 'false');
      if (overlay) { overlay.remove(); overlay = null; }
    }
    sidebar.querySelectorAll('a').forEach(link => link.addEventListener('click', () => { if (window.innerWidth <= 760) closeMenu(); }));
  }

  const searchInput = document.querySelector('.global-search input');
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      searchInput?.focus();
      searchInput?.select();
    }
    if (event.key === 'Escape') {
      searchInput?.blur();
    }
  });
});
